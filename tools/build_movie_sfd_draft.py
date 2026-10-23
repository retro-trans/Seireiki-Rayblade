"""Create a template-scheduled Sofdec caption candidate. Dry run by default.

Preserve original audio packs, sector SCRs, system headers, Sofdec metadata and
file extent. Schedule MPEG-1 video units backwards against original coded-frame
delivery deadlines. Unused video sectors become padding. This is an offline
candidate; software decoding does not prove game playback or decoder buffering.
"""
import argparse
import bisect
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess

from audit_sfd_container import digest, inspect
from build_bitmap_font import ROOT


SOURCE = ROOT / 'work/source/movies/MOV072.SFD'
DRAFT = ROOT / 'work/output/movie-drafts/MOV072/attempt-02'


def units(data):
    result = []
    pending = 0
    group_offset = 0
    group_max = -1
    group_has_frames = False
    for match in re.finditer(b'\x00\x00\x01[\x00\xb3\xb8]', data):
        at = match.start()
        code = data[at + 3]
        if code in (0xb3, 0xb8):
            if pending is None:
                pending = at
            if code == 0xb8:
                if group_has_frames:
                    group_offset += group_max + 1
                group_max = -1
                group_has_frames = False
            continue
        temporal = data[at + 4] << 2 | data[at + 5] >> 6
        picture_type = data[at + 5] >> 3 & 7
        assert picture_type in (1, 2, 3)
        group_max = max(group_max, temporal)
        group_has_frames = True
        start = at if pending is None else pending
        result.append({'start': start, 'picture': at, 'presentation': group_offset + temporal, 'type': picture_type})
        pending = None
    assert result[0]['start'] == 0
    assert sorted(r['presentation'] for r in result) == list(range(len(result))), 'Incomplete/duplicate GOP presentation map'
    for i, row in enumerate(result):
        row['end'] = result[i + 1]['start'] if i + 1 < len(result) else len(data)
        assert row['start'] < row['picture'] + 4 < row['end']
    return result


def time_bytes(value, prefix):
    assert 0 <= value < 1 << 33
    return bytes([prefix | ((value >> 30 & 7) << 1) | 1, value >> 22 & 255,
                  (value >> 15 & 127) << 1 | 1, value >> 7 & 255, (value & 127) << 1 | 1])


def padding(length):
    assert length >= 7
    return b'\0\0\1\xbe' + (length - 6).to_bytes(2, 'big') + b'\x0f' + b'\xff' * (length - 7)


def video_sector(pack_header, data, picture=None):
    assert len(pack_header) == 12 and 0 < len(data) <= 2018
    # Native original declares the same 46 KiB STD video buffer in every PES.
    optional = b'\x60\x2e'
    if picture is None:
        optional = b'\xff' * 9 + optional + b'\x0f'
    else:
        pts, dts = picture
        optional += time_bytes(pts, 0x30) + time_bytes(dts, 0x10)
    extra = 2018 - len(data)
    if 0 < extra < 7:
        optional = b'\xff' * extra + optional
        extra = 0
    pes = b'\0\0\1\xe0' + (len(optional) + len(data)).to_bytes(2, 'big') + optional + data
    out = pack_header + pes + (padding(extra) if extra else b'')
    assert len(out) == 2048
    return out


def compose():
    original = SOURCE.read_bytes()
    source_report, packs, streams = inspect(original)
    report = json.loads((DRAFT / 'render-report.json').read_text('utf-8'))
    video = (ROOT / report['native_video']['path']).read_bytes()
    assert digest(original) == report['source_sha256']
    assert digest(video) == report['native_video']['sha256']
    old_units, new_units = units(streams[0xe0]), units(video)
    expected_frames = source_report['metadata']['video_frames']
    assert len(old_units) == len(new_units) == report['frame_count'] == expected_frames
    first_video = next(s for s in source_report['streams'] if s['id'] == '0xe0')
    assert first_video['first_timestamps'][0]['dts'] == 3006
    assert first_video['first_timestamps'][0]['std_buffer_bytes'] == 47104
    slots = [s['sector'] for s in packs if any(p['id'] == '0xe0' for p in s.get('packets', []))]
    old_offsets = [p['elementary_offset'] for s in packs for p in s.get('packets', []) if p['id'] == '0xe0']
    assert len(slots) == len(old_offsets)
    deadlines = [slots[bisect.bisect_right(old_offsets, r['end'] - 1) - 1] for r in old_units]
    assignments = {}
    cursor = len(slots) - 1
    for index in range(len(new_units) - 1, -1, -1):
        frame = new_units[index]
        while cursor >= 0 and slots[cursor] > deadlines[index]:
            cursor -= 1
        chunks = [video[i:min(i + 2018, frame['end'])] for i in range(frame['start'], frame['end'], 2018)]
        assert cursor - len(chunks) + 1 >= 0, 'Video cannot meet source delivery deadlines'
        for n in range(len(chunks) - 1, -1, -1):
            assignments[slots[cursor]] = (index, n, chunks[n])
            cursor -= 1
    # No stream changes outside the original video sectors.
    out = bytearray(original)
    occupancy = 0
    peak = 0
    completed = Counter()
    by_deadline = {}
    for i, deadline in enumerate(deadlines):
        by_deadline.setdefault(deadline, []).append(i)
    for sector in slots:
        offset = sector * 2048
        pack_header = original[offset:offset + 12]
        if sector in assignments:
            index, chunk_index, chunk = assignments[sector]
            frame = new_units[index]
            # Retain the source's approximate 3006-tick frame clock. Its PTS
            # convention has I/P PTS preceding DTS; do not claim MPEG STD proof.
            timing = (frame['presentation'] * 3006, (index + 1) * 3006) if chunk_index == 0 else None
            out[offset:offset + 2048] = video_sector(pack_header, chunk, timing)
            occupancy += len(chunk)
            completed[index] += len(chunk)
            peak = max(peak, occupancy)
        else:
            out[offset:offset + 2048] = pack_header + padding(2036)
        for index in by_deadline.get(sector, []):
            length = new_units[index]['end'] - new_units[index]['start']
            assert completed[index] == length, ('Frame incomplete by original deadline', index)
            occupancy -= length
            assert occupancy >= 0
    assert occupancy == 0
    assert peak <= 47104, ('Source-schedule compressed-video occupancy exceeds native declared buffer', peak)
    target_report, target_packs, target_streams = inspect(bytes(out))
    assert target_streams[0xc0] == streams[0xc0]
    assert target_streams[0xe0] == video
    assert target_report['metadata'] == source_report['metadata']
    assert target_report['scr_first_last_seconds'] == source_report['scr_first_last_seconds']
    allowed = set(slots)
    assert all(out[o:o + 2048] == original[o:o + 2048] for o in range(0, len(out), 2048) if o // 2048 not in allowed)
    assert all(out[p * 2048:p * 2048 + 12] == original[p * 2048:p * 2048 + 12] for p in slots)
    summary = {'status': 'Template-scheduled SFD translation candidate; live playback unverified', 'movie': SOURCE.name,
               'source_sha256': digest(original), 'candidate_sha256': digest(out), 'bytes': len(out),
               'video_sha256': digest(video), 'audio_sha256': digest(streams[0xc0]),
               'coded_frames': len(new_units), 'data_video_sectors': len(assignments),
               'padding_video_sectors': len(slots) - len(assignments),
               'source_deadline_scheduling': {'all_coded_units_delivered': True, 'peak_compressed_bytes': peak,
                                             'limit_bytes': 47104,
                                             'scope': 'Occupancy against original coded-unit delivery sectors; not an MPEG STD/VBV simulator'},
               'preservation': ['All original audio sector bytes and elementary payload',
                                'All pack SCRs/mux rate, system headers, Sofdec metadata and file length',
                                'All sectors outside original video slots'],
               'limitations': ['Original metadata still names original encoder; this is a template-based derivative',
                               'Original 3006-tick timing convention retained approximately for new video units',
                               'Native runtime buffering, A/V sync and playback remain unverified',
                               'Captured UI, logos, reading speed and whole-movie review remain unfinished'],
               'game_build_changed': False, 'container': target_report}
    return bytes(out), summary


def main():
    global DRAFT, SOURCE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--draft-dir', type=Path, default=DRAFT)
    ap.add_argument('--movie', choices=['MOV055.SFD', 'MOV072.SFD'], default='MOV072.SFD')
    args = ap.parse_args()
    DRAFT = args.draft_dir.resolve()
    SOURCE = ROOT / 'work/source/movies' / args.movie
    candidate, report = compose()
    print(json.dumps({k: v for k, v in report.items() if k != 'container'}, indent=2), flush=True)
    if not args.write:
        print('DRY RUN: candidate constructed/validated in memory; no files written')
        return
    output = DRAFT / ('MOV072-captions-candidate.SFD' if args.movie == 'MOV072.SFD' else 'MOV055-english-candidate.SFD')
    assert not output.exists(), 'Refuse to overwrite candidate'
    output.write_bytes(candidate)
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    probe = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(output)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    assert video['codec_name'] == 'mpeg1video' and int(video['nb_read_frames']) == report['coded_frames']
    assert audio['codec_name'] == 'adpcm_adx' and audio['sample_rate'] == '44100' and audio['channels'] == 2
    # Decode separately: null muxing both streams would add timestamp checks
    # unrelated to codec validity. Record those clocks independently above.
    for kind in ('v', 'a'):
        log = DRAFT / f'candidate-decode-{kind}.log'
        with log.open('wb') as stderr:
            subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(output), '-map', f'0:{kind}:0'] +
                           (['-vf', 'setpts=N*1001/(30000*TB)', '-an'] if kind == 'v' else ['-vn']) +
                           ['-f', 'null', '-'], check=True, stdout=subprocess.DEVNULL, stderr=stderr)
        assert not log.read_bytes(), log.read_text()
    report['software_decode'] = {'video_frames': report['coded_frames'], 'audio_codec': 'adpcm_adx', 'errors': 0,
                                  'scope': 'Codec/frame-count checks, not native playback or audio synchronization'}
    report['candidate'] = str(output.relative_to(ROOT)).replace('\\', '/')
    (DRAFT / 'sfd-candidate-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print('Candidate and full-stream decode checks written:', output)


if __name__ == '__main__':
    main()
