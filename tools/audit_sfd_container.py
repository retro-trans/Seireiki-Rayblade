"""Inspect sector-aligned MPEG-1 Sofdec packs without modifying source files.

Default is read-only. --write saves an English-only JSON audit and exact
elementary streams under work/source/movie-streams/<member>/.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from build_bitmap_font import ROOT


def digest(data):
    return hashlib.sha256(data).hexdigest()


def timestamp(data):
    assert len(data) == 5 and all(data[i] & 1 for i in (0, 2, 4))
    return ((data[0] >> 1 & 7) << 30 | data[1] << 22 |
            (data[2] >> 1) << 15 | data[3] << 7 | data[4] >> 1)


def inspect(data):
    assert len(data) % 2048 == 0
    packs = []
    streams = {}
    metadata = None
    for offset in range(0, len(data), 2048):
        sector = data[offset:offset + 2048]
        if sector[:4] == b'\0\0\1\xb9':
            assert offset == len(data) - 2048
            packs.append({'sector': offset // 2048, 'end': True})
            continue
        assert sector[:4] == b'\0\0\1\xba' and sector[4] >> 4 == 2, offset
        scr = timestamp(sector[4:9])
        assert sector[9] & 128 and sector[11] & 1
        rate = ((sector[9] & 127) << 15 | sector[10] << 7 | sector[11] >> 1) * 50
        pos = 12
        packets = []
        while pos < 2048:
            assert sector[pos:pos + 3] == b'\0\0\1', (offset, pos)
            sid = sector[pos + 3]
            length = int.from_bytes(sector[pos + 4:pos + 6], 'big')
            end = pos + 6 + length
            assert end <= 2048 and end > pos
            record = {'id': hex(sid), 'size': length + 6}
            start = pos + 6
            if sid == 0xbf:
                assert metadata is None
                metadata = sector[32:]
                record['sofdec_tag'] = metadata[:24].decode('ascii')
            elif 0xc0 <= sid <= 0xef:
                while sector[start] == 0xff:
                    start += 1
                    assert start < end
                if sector[start] & 0xc0 == 0x40:
                    record['std_buffer_bytes'] = (int.from_bytes(sector[start:start + 2], 'big') & 0x1fff) * (1024 if sector[start] & 32 else 128)
                    start += 2
                if sector[start] >> 4 == 2:
                    record['pts'] = timestamp(sector[start:start + 5])
                    start += 5
                elif sector[start] >> 4 == 3:
                    record['pts'] = timestamp(sector[start:start + 5])
                    record['dts'] = timestamp(sector[start + 5:start + 10])
                    start += 10
                else:
                    assert sector[start] == 15, (offset, start, sector[start])
                    start += 1
                payload = sector[start:end]
                stream = streams.setdefault(sid, bytearray())
                record.update(payload_bytes=len(payload), elementary_offset=len(stream))
                stream.extend(payload)
            else:
                assert sid in (0xbb, 0xbe), hex(sid)
            packets.append(record)
            pos = end
        assert pos == 2048
        packs.append({'sector': offset // 2048, 'scr': scr, 'mux_bytes_per_second': rate, 'packets': packets})
    assert metadata is not None
    scrs = [p['scr'] for p in packs if 'scr' in p]
    regressions = [{'previous_sector': a['sector'], 'sector': b['sector'], 'previous_scr': a['scr'], 'scr': b['scr']}
                   for a, b in zip(packs, packs[1:]) if 'scr' in a and 'scr' in b and b['scr'] < a['scr']]
    fields = {name: struct.unpack_from('<I', metadata, off)[0] for name, off in
              [('system_bytes_per_second', 0x94), ('audio_ms', 0x98), ('video_ms', 0x9c),
               ('video_frames', 0xa0), ('maximum_picture_bytes', 0xa4), ('average_picture_bytes', 0xa8)]}
    report = {'source_bytes': len(data), 'source_sha256': digest(data),
              'sectors': len(packs), 'packet_counts': dict(Counter(p['id'] for s in packs for p in s.get('packets', []))),
              'mux_bytes_per_second': sorted(set(p['mux_bytes_per_second'] for p in packs if 'scr' in p)),
              'scr_first_last_seconds': [scrs[0] / 90000, scrs[-1] / 90000],
              'scr_regressions': regressions,
              'metadata': fields, 'streams': []}
    for sid, payload in streams.items():
        ps = [(p, packet) for p in packs for packet in p.get('packets', []) if packet['id'] == hex(sid)]
        timed = [(p, packet) for p, packet in ps if 'pts' in packet]
        item = {'id': hex(sid), 'bytes': len(payload), 'sha256': digest(payload), 'timed_packets': len(timed),
                'first_timestamps': [dict(sector=p['sector'], scr=p['scr'], **packet) for p, packet in timed[:4]],
                'last_timestamps': [dict(sector=p['sector'], scr=p['scr'], **packet) for p, packet in timed[-2:]]}
        if sid == 0xe0:
            start = payload.index(b'\0\0\1\xb3') + 4
            header = int.from_bytes(payload[start:start + 8], 'big')
            item['sequence'] = {'width': header >> 52, 'height': header >> 40 & 0xfff,
                                'rate_code': header >> 32 & 15, 'bitrate': (header >> 14 & 0x3ffff) * 400,
                                'vbv_bytes': (header >> 3 & 0x3ff) * 2048}
            picture_types = Counter()
            at = 0
            while True:
                at = payload.find(b'\0\0\1\0', at)
                if at < 0:
                    break
                picture_types[(payload[at + 5] >> 3) & 7] += 1
                at += 4
            item['picture_types'] = dict(picture_types)
        elif sid == 0xc0:
            assert payload[:2] == b'\x80\0'
            item['adx'] = {'header_bytes': int.from_bytes(payload[2:4], 'big') + 4,
                           'block_bytes': payload[5], 'sample_bits': payload[6], 'channels': payload[7],
                           'sample_rate': int.from_bytes(payload[8:12], 'big'),
                           'sample_count': int.from_bytes(payload[12:16], 'big')}
        report['streams'].append(item)
    return report, packs, streams


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=ROOT / 'work/source/movies/MOV072.SFD')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    report, packs, streams = inspect(args.source.read_bytes())
    print(json.dumps(report, indent=2))
    if not args.write:
        print('DRY RUN: source read only; no files written')
        return
    out = ROOT / 'work/source/movie-streams' / args.source.stem
    out.mkdir(parents=True, exist_ok=True)
    for sid, raw in streams.items():
        path = out / (hex(sid) + ('.m1v' if sid >= 0xe0 else '.sfa'))
        if path.exists():
            assert path.read_bytes() == raw, 'Refuse to replace different elementary stream'
        else:
            path.write_bytes(raw)
    (out / 'container.json').write_text(json.dumps(dict(report, packs=packs), indent=2) + '\n', 'utf-8')
    summary = ROOT / 'docs/movie-container-audit.json'
    summary.write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
