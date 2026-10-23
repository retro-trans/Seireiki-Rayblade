"""Package selected moving-logo subtitles over build 0.1.28. Dry run first.

Only the two movie payloads change; keep every native component and the real
identities/scope of preceding native proofs. No native movie playback claim.
"""
import argparse
import json
import re

from audit_sfd_container import inspect
from build_bitmap_font import ROOT, digest
from build_movie_test_disc import write_plan
import build_movie_sfd_draft as muxer
from build_test_disc import regenerate
from disc_inventory import Disc, SECTOR
from prepare_movie_moving_title import prepare, recipe_path

VERSION, PRIOR = '0.1.29', '0.1.28'
SOURCES = {'MOV055.SFD': 'work/output/movie-drafts/MOV055/intro-moving-subtitle-01',
           'MOV072.SFD': 'work/output/movie-drafts/MOV072/captions-ui-titles-subtitle-01'}


def read(path):
    return json.loads(path.read_text('utf-8'))


def plan():
    base = ROOT / 'work/output' / PRIOR
    previous = read(base / 'english-disc-report.json')
    assert previous['version'] == PRIOR and previous['validation']['reextracted_files'] == 'all 11 exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    inherited = {}
    for name, info in previous['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'], row['size'])
        assert digest(raw) == info['sha256'] and len(raw) == info['size']
        path = base / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
        assert path.read_bytes() == raw
        inherited[name] = raw
    historical = list(previous['historical_native_evidence'])
    proof_file = 'album-captions-native-test.json'
    data = (base / proof_file).read_bytes()
    proof = json.loads(data)
    assert digest(data) == previous['album_captions_proof_sha256']
    assert proof['archive_sha256'] == digest(inherited['ALBUM.AFS'])
    assert not any(r['file'] == proof_file for r in historical)
    historical.append({'file': proof_file, 'sha256': digest(data), 'actual_tested_build': proof['source_build'],
                       'executable_sha256': proof['executable_sha256'],
                       'scope': 'Historical album decoding/structure report; original scope and limitations retained'})
    assert len(historical) == 18
    for item in historical:
        raw = (base / item['file']).read_bytes()
        assert digest(raw) == item['sha256'] and json.loads(raw)['executable_sha256'] == item['executable_sha256']
    original_disc = Disc(next(ROOT.glob('*.cue')))
    original_entries = {r['path']: r for r in original_disc.inventory()}
    assert original_entries.keys() == entries.keys()
    targets = dict(inherited)
    native = {n: b for n, b in inherited.items() if not n.endswith('.SFD')}
    assert len(native) == 9
    changes, movies = [], []
    prior_movie_locations, target_movie_locations, audio_count = 0, 0, 0
    for name, relative in SOURCES.items():
        folder = ROOT / relative
        mux = read(folder / 'sfd-candidate-report.json')
        render = read(folder / 'render-report.json')
        decoded = read(folder / 'decoded-comparison.json')
        raw = (ROOT / mux['candidate']).read_bytes()
        assert digest(raw) == mux['candidate_sha256'] == decoded['candidate_sha256']
        muxer.SOURCE, muxer.DRAFT = ROOT / 'work/source/movies' / name, folder
        recomputed, _ = muxer.compose()
        assert raw == recomputed
        frame_count = 1840 if name == 'MOV055.SFD' else 3084
        moving_frames = 60 if name == 'MOV055.SFD' else 48
        assert decoded['exact_decoded_video_frames'] == render['frame_count'] == frame_count
        assert decoded['decoded_pcm_identical_to_original_adx'] and decoded['software_decode_errors'] == 0
        assert render['intro_title']['frames'] == render['intro_title']['source_index_matches'] == 32
        assert render['moving_title']['frames'] == render['moving_title']['source_index_matches'] == moving_frames
        moving = read(recipe_path(name))
        assert moving == prepare(name)
        assert digest(recipe_path(name).read_bytes()) == render['moving_title']['recipe_sha256']
        assert decoded['moving_title_witnesses'] == render['moving_title']['exact_static_witnesses'] == [r['frame'] for r in moving['witnesses']]
        if name == 'MOV072.SFD':
            assert len(render['exact_preview_witnesses']) == 13 and render['captured_ui']['label_count'] == 25
            assert render['ending_title']['frames'] == 123
        row = entries[name]
        assert row == original_entries[name]
        original = original_disc.read(row['lba'], row['size'])
        assert digest(original) == mux['source_sha256']
        original_info, packs, streams = inspect(original)
        target_info, _, target_streams = inspect(raw)
        assert len(raw) == len(original) == row['size']
        assert original_info['metadata'] == target_info['metadata']
        assert target_streams[0xc0] == streams[0xc0]
        assert digest(target_streams[0xe0]) == mux['video_sha256']
        slots = {p['sector'] for p in packs if any(q['id'] == '0xe0' for q in p.get('packets', []))}
        prior = inherited[name]
        changed = []
        for n in range(len(raw) // 2048):
            a, b, old = original[n*2048:(n+1)*2048], raw[n*2048:(n+1)*2048], prior[n*2048:(n+1)*2048]
            if old != a:
                prior_movie_locations += 1
            if b != a:
                target_movie_locations += 1
                assert n in slots
            assert a[:12] == b[:12]
            if n not in slots:
                assert a == b
            if b != old:
                assert n in slots
                changed.append(n)
        audio_count += original_info['packet_counts']['0xc0']
        handles = {}
        try:
            for n in changed:
                lba = row['lba'] + n
                track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
                filename = track['path'].name
                if filename not in handles:
                    handles[filename] = track['path'].open('rb')
                offset = (track['index'] + lba - track['start_lba']) * SECTOR
                handles[filename].seek(offset)
                sector = handles[filename].read(SECTOR)
                assert regenerate(sector) == sector and sector[16:2064] == prior[n*2048:(n+1)*2048]
                edited = bytearray(sector)
                edited[16:2064] = raw[n*2048:(n+1)*2048]
                changes.append((filename, offset, regenerate(edited)))
        finally:
            for handle in handles.values():
                handle.close()
        targets[name] = raw
        movies.append({'movie': name, 'extent': row, 'candidate_sha256': digest(raw), 'new_changed_sectors': len(changed),
                       'software_frames': frame_count, 'intro_title_frames': 32, 'moving_subtitle_frames': moving_frames,
                       'treatment': moving['treatment'], 'source_interval': [moving['start_frame'], moving['end_frame_exclusive']],
                       'original_audio': 'exact ADX and decoded PCM', 'source_schedule': mux['source_deadline_scheduling'],
                       'candidate_report': relative + '/sfd-candidate-report.json',
                       'decoded_report': relative + '/decoded-comparison.json',
                       'encoded_witness_frames': decoded['witness_frames'],
                       'encoded_contact_sheets': decoded['contact_sheets']})
    assert audio_count == 4041
    assert prior_movie_locations == 25099
    native_locations = previous['total_changed_sector_locations_from_original'] - prior_movie_locations
    assert native_locations == 3227
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5
    pending = [p for p in previous['pending'] if p != 'Moving-art title treatment selection and implementation']
    report = {'version': VERSION, 'source_build': PRIOR,
              'kind': 'Local selected original moving-logo artwork plus English subtitle; full translation/review incomplete',
              'movie_extent': entries['MOV072.SFD'], 'movie_extents': [m['extent'] for m in movies], 'movies': movies,
              'original_audio_sector_count': audio_count, 'new_changed_sectors': len(changes),
              'total_changed_sector_locations_from_original': native_locations + target_movie_locations,
              'non_movie_changed_sector_locations_from_original': native_locations,
              'files': {n: {'size': len(raw), 'sha256': digest(raw)} for n, raw in targets.items()},
              'historical_native_evidence': historical, 'component_manifest_name': 'moving-title-component.json',
              'inherited_components': 'All nine non-movie game payloads exact 0.1.28',
              'proof_scope': 'Software movie/frame/audio and disc preservation only; native reports retain actual tested identities',
              'readme_component_text': 'English story/UI/library/battle, map, credits, pictured note and 201 album captions remain exact 0.1.28.\n'
                                       'Normal text font is unchanged; font smoothing, two album caption readings and pictured album text remain unfinished.\n',
              'readme_movie_text': 'The opening and demo now use selected treatment A: original moving Japanese logo artwork plus an English subtitle.\n'
                                   'Subtitle timing/fades are indexed separately for the two movies. No opaque plaque or background reconstruction.\n'
                                   'Retains rebuilt English intro titles, 13 demo captions, 25 captured UI labels and English demo ending title.\n'
                                   'Original audio is exact; full native playback/synchronization/skipping/return remain untested.\n',
              'pending': pending, 'release': False, 'story_library_draft_credit': 0}
    return disc, cue, inherited, targets, changes, names, historical, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print('PASS:', len(planned[4]), 'movie sector deltas;', planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; nine native payloads, 18 historical identities and all original audio exact.', flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned, VERSION, PRIOR)
    out = ROOT / 'work/output' / VERSION
    for movie, folder in SOURCES.items():
        base = ROOT / folder
        for name in ('render-report.json', 'sfd-candidate-report.json', 'decoded-comparison.json'):
            (out / (movie[:6] + '-' + name)).write_bytes((base / name).read_bytes())


if __name__ == '__main__':
    main()
