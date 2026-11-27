"""Bounded audit of the ranged-attack report; does not claim a gameplay fix.

Uses supplied current components and the original executable, so deleted
historical build directories are not required. Never changes a disc or save.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(version='0.7.51'):
    from build_battle_target_fix import RAW_SITES
    from test_battle_target import fresh as raw_cpu
    from test_battle_clip import fresh as clip_cpu
    from test_native_movie_font import run, bits, value

    exe = (ROOT / 'work/output' / version / '1ST_READ.BIN').read_bytes()
    original = (ROOT / 'work/source/disc/1ST_READ.BIN').read_bytes()
    steps = 0
    strips = []
    for callee, (stride, sites) in RAW_SITES.items():
        for site in sites:
            entry = struct.unpack_from('<I', exe, site)[0]
            for count in (3, 4, 17, 64):
                for blend in (0, 1):
                    payload = b''
                    for i in range(count):
                        xyz = (-12.5 + i * 6, 220.25 - i * 4, -1. / (128 + i))
                        payload += (struct.pack('<5fI', *xyz, i / 64., i / 128., 0x806df439 + i)
                                    if stride == 24 else struct.pack('<3fI', *xyz, 0x806df439 + i))
                    results = []
                    for image, address in ((original, callee), (exe, entry)):
                        c = raw_cpu(image)
                        c.regions[1][1][:len(payload)] = payload
                        c.reg[4:8] = [0x8cf00000, count, 7 if stride == 24 else blend, blend]
                        before = bytes(c.regions[1][1])
                        steps += run(c, address, 200000)
                        assert bytes(c.regions[1][1]) == before
                        assert len(c.packets) == count
                        results.append((c.packets, c.commit, [h for h in c.headers if h[0] != 0x8c0c7d34]))
                    stock, current = results
                    assert stock[1:] == current[1:]
                    for a, b in zip(stock[0], current[0]):
                        expected = bytearray(a)
                        for off in (4, 8):
                            struct.pack_into('<f', expected, off, struct.unpack_from('<f', a, off)[0] * 2)
                        assert b == expected
                    strips.append(dict(site=hex(site), stride=stride, count=count, blend=blend))

    clips = []
    for box in ((0., 0., 4., 6.), (5., 0., 9., 6.), (0., 0., 9., 6.),
                (0., 0., 9., 3.), (0., 4., 9., 6.), (1., 2., 7., 5.)):
        for mode in (0, 1, 2):
            c = clip_cpu(exe)
            p = 0x8cf00000
            c.reg[4:6] = [mode, p]
            for i, coordinate in enumerate(box):
                c.write(p + i * 4, bits(coordinate), 4)
            steps += run(c, 0x8c07b77c, 100000)
            expected = [v * 2 + (1 if mode == 2 and i >= 2 else 0) for i, v in enumerate(box)]
            assert c.rects == [expected]
            assert [value(c.read(p + i * 4, 4)) for i in range(4)] == list(box)
            if mode == 2:
                assert c.tiles[-1] == [int(v) for v in expected]
                pixels = [value(c.read(0x8c419340 + i * 4, 4)) for i in range(4)]
                assert pixels == [expected[0] * 32, expected[1] * 32, expected[2] * 32 + 31, expected[3] * 32 + 31]
            clips.append(dict(mode=mode, source_tiles=box, submitted_tiles=expected))

    return dict(version=version, executable_sha256=hashlib.sha256(exe).hexdigest(),
                raw_strip_cases=strips, clip_cases=clips, SH4_instructions=steps,
                result='pass within bounded fixtures; reported ranged-attack failure remains unresolved',
                checks=['Actual SDK strip packets preserve depth, UV, colors, blend and primitive commands; only XY doubles.',
                        'All four patched strip call sites tested, including 64 vertices and offscreen coordinates.',
                        'Actual SDK clip state conversion, inclusive tile bounds, source buffers and ABI checked.'],
                limits=['GPU submission/material allocation endpoints are bounded stubs.',
                        'No actual ranged-attack sequence or live texture residency is validated.',
                        'A passing audit does not establish correct rendering on an emulator or hardware.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.7.51')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = audit(args.version)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('raw_strip_cases', 'clip_cases')}, indent=2))
