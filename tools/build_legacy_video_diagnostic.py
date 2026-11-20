"""Local 0.7.25: isolate the stock 0.7.2 rendering path. Dry first; no release."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION, PRIOR = '0.7.25', '0.7.23'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def compose():
    root = ROOT / 'work/output'
    old = (root / PRIOR / '1ST_READ.BIN').read_bytes()
    stock = (root / '0.7.2/1ST_READ.BIN').read_bytes()
    assert digest(old) == '6899e263653b1a29de45ee7bf04778e1ad240c40a99763511bd2da7ce9abbffe'
    exe, changes = bytearray(old), []

    def restore(offset, size, reason, expected=None):
        if expected is not None:
            assert old[offset:offset+size] == expected, (hex(offset), reason)
        before, after = old[offset:offset+size], stock[offset:offset+size]
        assert before != after, (hex(offset), reason)
        exe[offset:offset+size] = after
        changes.append({'file_offset': hex(offset), 'bytes': size, 'before': before.hex(),
                        'after': after.hex(), 'reason': reason})

    # The application and VGA commit use exactly the working release's flags.
    restore(0x10cb0, 4, 'Stock 320x240 RGB888 initialization', bytes.fromhex('00e531e4'))
    restore(0xda696, 2, 'Stock VGA scan-doubling compensation', bytes.fromhex('0900'))
    restore(0xc234e, 8, 'Original SDK geometry-budget selection')
    rendering = json.loads((root / '0.7.5/font-mode-details.json').read_text(encoding='utf-8'))['rendering']
    for position, callee in rendering['pointer_edits']:
        p, callee = int(position, 16), int(callee, 16)
        assert struct.unpack_from('<I', stock, p)[0] == callee
        expected = int(rendering['polygon_wrapper'] if callee == 0x8c0a9db0 else rendering['clip_wrapper'], 16)
        restore(p, 4, 'Original polygon/clipping call', struct.pack('<I', expected))
    restore(0x6b8e4, 4, 'Original sprite submission', struct.pack('<I', int(rendering['sprite_wrapper'], 16)))
    for p, callee in ((0x2a150, 0x8c09fccc), (0x2a154, 0x8c09fd18), (0x360c8, 0x8c0ab660)):
        assert struct.unpack_from('<I', stock, p)[0] == callee
        restore(p, 4, 'Original movie setter / range-grid submission')
    from build_battle_target_fix import RAW_SITES, LINE_SITES
    from build_battle_clip_fix import LINE_POINTERS
    for callee, (_, sites) in RAW_SITES.items():
        for p in sites:
            assert struct.unpack_from('<I', stock, p)[0] == callee
            restore(p, 4, 'Original animation primitive submission')
    for p in (*LINE_SITES, *LINE_POINTERS):
        assert struct.unpack_from('<I', stock, p)[0] == 0x8c0a93bc
        restore(p, 4, 'Original line submission')
    before = (root / '0.7.11/1ST_READ.BIN').read_bytes()
    after = (root / '0.7.12/1ST_READ.BIN').read_bytes()
    loading = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(loading) == 1
    restore(loading[0], 1, 'Original NOW LOADING cell size')

    permitted = {i for row in changes for i in range(int(row['file_offset'], 16), int(row['file_offset'], 16)+row['bytes'])}
    actual = {i for i, (a, b) in enumerate(zip(old, exe)) if a != b}
    assert actual and actual <= permitted
    assert exe[0xda5c0:0xda7b5] == stock[0xda5c0:0xda7b5]
    assert exe[0xc234e:0xc2356] == stock[0xc234e:0xc2356]
    # Keep the removed selector removed, the single Native glyph bank and VQ fix.
    from build_map_font_patch import member
    archive = (root / PRIOR / 'WIN00.AFS').read_bytes()
    assert digest(member(archive, 0)) == '1b909b7fc3e2755a74f2d2da5dbc0b9b67dad90d31eb808ad5ed016adb71820e'
    for lo, hi in ((0x10150, 0x10154), (0x8d60, 0x9000), (0x22d1a, 0x22d68), (0x6bb7c, 0x6bba0)):
        assert exe[lo:hi] == old[lo:hi]
    return bytes(exe), {
        'version': VERSION, 'source_build': PRIOR, 'release': False,
        'kind': 'Stock-rendering hardware isolation diagnostic; not a confirmed fix',
        'date': '2026-10-30', 'source_executable_sha256': digest(old),
        'executable_sha256': digest(exe), 'changed_bytes': len(actual), 'edits': changes,
        'rendering': {'logical_framebuffer': [320, 240], 'format': 'RGB888',
                      'VGA_scanout': [640, 480], 'mode_and_VGA_commit': 'Exact working 0.7.2 path',
                      'graphics_coordinate_adapters': 'Bypassed consistently for sprites, polygons, clipping, grid, animations, lines, movies and loading text'},
        'preserved': 'All 14 non-executable payloads; Native-only Skies glyph bank, translation, UI sizing, original movies and Stage 6 lossless text compression.',
        'font_caveat': 'Native bank is exact and HD/selector stay removed. The stock lower-resolution renderer samples it at lower display detail; this is a compatibility diagnostic, not a final font-quality decision.',
        'required_tests': 'Real Dreamcast GDEMU/VGA: cold boot, New Game, then normal Clear 2 VMU save -> Next. Physical confirmation pending.',
    }


def check(exe):
    from test_vga_patch import VideoCPU
    from test_native_movie_font import DrawCPU, MovieCPU, fresh, run, value, BASE, OBJ, STOP, bits
    stock = (ROOT / 'work/output/0.7.2/1ST_READ.BIN').read_bytes()
    cases, steps = 0, 0
    for entry in (0xda5c0, 0xbbe00):
        for cable in range(4):
            for flags in (0, 1, 0x10, 0x11, 0x20, 0x21, 0x40, 0x41, 0x42, 0x43, 0x60, 0x61):
                actual, expected = [VideoCPU(image, cable, flags, entry) for image in (exe, stock)]
                steps += actual.run_video(); expected.run_video()
                assert actual.reg == expected.reg and actual.t == expected.t
                assert actual.calls == expected.calls and actual.fallback == expected.fallback
                for (a, b), (c, d) in zip(actual.regions[-3:], expected.regions[-3:]):
                    assert a == c and b == d
                cases += 1
    class BudgetCPU(DrawCPU):
        def execute(self, pc, delay=False):
            if pc == 0x8c0e77e0:
                self.reg[0] = self.query
                return self.pr
            return super().execute(pc, delay)
    budgets = []
    for query in (0, 1):
        results = []
        for image in (exe, stock):
            c = BudgetCPU(image, b'', 0, 0)
            c.regions = [(0x8c000000, bytearray(0x1000000))]
            c.regions[0][1][0x10000:0x10000+len(image)] = image
            c.reg[15], c.pr, c.query = 0x8cffe000, STOP, query
            c.fr, c.fpul, c.visited = [bits(0.)]*16, 0, set()
            c.reg[13], c.reg[14] = 0x8c46214c, 0x8c419b38
            for p, v in ((0x8c461bd0, 0x800000), (0x8c4621a8, 0x1b4fa8), (0x8c4621ac, 230400), (0x8c4621b0, 17280)):
                c.write(p, v, 4)
            c.pc = 0x8c0d230c
            for n in range(1000):
                if c.pc in (0x8c0d2368, 0x8c0d241a): break
                c.pc = c.execute(c.pc)
            assert c.pc == 0x8c0d2368
            results.append((c.reg[11], c.read(0x8c4621a4, 4)))
        assert results[0] == results[1] == (384176, 384176)
        budgets.append({'configuration': query, 'TA_allocator_units': results[0][0], 'matches_072': True})
    movies = []
    for index in range(129):
        name, w, h = struct.unpack_from('<3I', exe, 0x88e74 + 12*index)
        c = fresh(exe, MovieCPU)
        c.write(OBJ, OBJ+0x200, 4)
        c.write(OBJ+0x200+40, 0xdead1000, 4); c.write(OBJ+0x200+24, 0xdead2000, 4)
        c.reg[4] = index
        steps += run(c, BASE+0x29fe8)
        if name == BASE+0x87bac: continue
        rectangle = [value(c.read(OBJ+o, 4)) for o in (116, 120, 128, 132)]
        assert rectangle == [(320-w)//2, (240-h)//2, w, h]
        movies.append({'id': index, 'logical_rectangle': rectangle})
    return {'version': VERSION, 'executable_sha256': digest(exe), 'native_VGA_cases': cases,
            'SDK_budget_cases': budgets, 'native_movie_cases': len(movies), 'movie_rectangles': movies,
            'native_instructions': steps,
            'scope': 'Actual SH-4 VGA code/MMIO, original geometry-budget arithmetic and movie setters. Cable/configuration/allocation/start endpoints are fixtures. No physical GPU success claimed.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true'); ap.add_argument('--disc', action='store_true')
    args = ap.parse_args()
    exe, report = compose()
    print(json.dumps({k: report[k] for k in ('version', 'executable_sha256', 'changed_bytes', 'rendering')}, indent=2), flush=True)
    if not args.write:
        print('DRY RUN: no files written.'); return
    proof = check(exe)
    if not args.disc:
        print('PASS native cases:', proof['native_VGA_cases'], proof['native_movie_cases'], flush=True); return
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    source = ROOT / 'work/output' / PRIOR
    mode = json.loads((source / 'font-mode-details.json').read_text(encoding='utf-8'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe), output_resolution=[320, 240], VGA_scanout=[640, 480], rendering_diagnostic=True)
    archive = (source / 'WIN00.AFS').read_bytes()
    p, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    p[7].update(kind=report['kind'], component_manifest_name='legacy-video-component.json',
                readme_component_text=report['kind'] + '\n' + report['font_caveat'] + '\n',
                pending=[report['required_tests'], 'Full Native font/display-quality review'])
    write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = ROOT / 'work/output' / VERSION
    for name, value in [('legacy-video-diagnostic.json', report), ('legacy-video-native-test.json', proof), ('font-mode-details.json', mode)]:
        (out / name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    (out / 'READ-ME.txt').write_text('Rayblade 0.7.25 STOCK-RENDERING HARDWARE DIAGNOSTIC\n\n' + report['required_tests'] + '\n\n' + report['preserved'] + '\n\n' + report['font_caveat'] + '\n\nNo public release or confirmed hardware fix.\n', encoding='utf-8')
    print('PASS: native cases and complete disc preservation. Physical test pending.', flush=True)


if __name__ == '__main__': main()
