"""0.7.35: bypass only the shared map-label sniffing hook on full 0.7.34."""
import argparse, copy, json, struct
from pathlib import Path
from build_bitmap_font import ROOT, digest

VERSION, PRIOR = '0.7.35', '0.7.34'
HOOK, DRAW = 0x8c018d00, 0x8c0ab970
SOURCE_SHA = '68f7102790efaaa52889da69bf4e1208671f72e27be7dd44fa0b88767ef250e8'


def compose():
    old = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    assert digest(old) == SOURCE_SHA
    sites = [p for p in range(0x6b6e0, 0x6b7a8, 4)
             if old[p:p+4] == struct.pack('<I', HOOK)]
    assert len(sites) == 1
    p = sites[0]
    baseline = (ROOT/'work/output/0.7.31/1ST_READ.BIN').read_bytes()
    assert baseline[p:p+4] == struct.pack('<I', DRAW)
    exe = bytearray(old)
    exe[p:p+4] = baseline[p:p+4]
    changed = [i for i, (a, b) in enumerate(zip(old, exe)) if a != b]
    assert changed and all(p <= i < p+4 for i in changed)
    report = {'version': VERSION, 'date': '2026-11-05', 'source_build': PRIOR,
        'kind': 'Shared map-label hook bypass on the full feature candidate',
        'source_executable_sha256': digest(old), 'executable_sha256': digest(exe),
        'changed_executable_bytes': len(changed), 'pointer_offset': hex(p),
        'old_target': hex(HOOK), 'new_target': hex(DRAW),
        'reason': '0.7.34 remains reported to freeze at New Game/scenario transitions despite repaired filename alignment. Isolate the entire custom map sniff/snap hook that was absent in passing 0.7.31/0.7.32.',
        'preserved': 'All 0.7.34 assets, story-choice boundaries, map labels, Native 1x font, RGB565, compact atlases, movie/loading/grid/target/clip/selector fixes and Stage 6 text codec.',
        'tradeoff': 'Map-label physical coordinates are no longer truncated to whole pixels. Fractional-position label edges may look slightly different while scrolling.',
        'scope': 'Only one draw target literal changes; the existing 2x sprite wrapper still executes. Original SDK sprite drawing receives the same descriptor except for removal of the custom map-only position truncation.',
        'hardware_root_cause_confirmed': False, 'hardware_result': 'pending',
        'release': False, 'upgrade_patch': False}
    return bytes(exe), report


def check(exe):
    from test_choice_map_fix import SnapCPU
    from test_native_movie_font import fresh, run, OBJ

    class NoSniffCPU(SnapCPU):
        def read(self, address, count):
            if OBJ+0x2000 <= address < OBJ+0x2100:
                raise AssertionError('Shared wrapper must not inspect texture-name state')
            return super().read(address, count)

        def execute(self, pc, delay=False):
            assert not (HOOK <= pc < HOOK+0x60)
            assert not (0x8c07b69c <= pc < 0x8c07b6c8)
            return super().execute(pc, delay)

    cases = steps = 0
    for ptr in (0, 1, OBJ+0x2000, 0xffffffff):
      for sprite in (0, 16, 17, 21, 26, 27, 129):
       for x, y in ((0., 0.), (160.25, 24.75), (-12.3, -.25)):
        c = fresh(exe, NoSniffCPU)
        raw = struct.pack('<5f3I', x, y, -.5, 1., 1., 0x1234, ptr, OBJ+0x2100)
        block = c.regions[3][1]
        block[0x1000:0x1020] = raw
        c.reg[4:7] = [OBJ+0x1000, sprite, 0x20]
        depth, stack, pr = c.fr[4], c.reg[15], c.pr
        saved, before = c.reg[8:15], bytes(block)
        steps += run(c, 0x8c07b6e0)
        expected = bytearray(raw)
        for offset in (0, 4, 12, 16):
            struct.pack_into('<f', expected, offset, struct.unpack_from('<f', raw, offset)[0]*2)
        assert c.observed == (bytes(expected), [sprite, 0x20], depth)
        assert bytes(block) == before and c.reg[8:15] == saved
        assert c.reg[15] == stack and c.pr == pr
        assert c.reg[0] == 0x12345678 and c.reg[2] == 0x8c5f0040
        cases += 1
    return {'version': VERSION, 'executable_sha256': digest(exe), 'draw_cases': cases,
        'SH4_instructions': steps, 'custom_hook_and_filename_reads': 'never executed',
        'scaled_descriptor_source_and_ABI': 'pass',
        'scope': 'Actual shared scaling wrapper; bounded original SDK draw endpoint. Invalid texture pointers are opaque witnesses only: no claim that the SDK can render invalid pointers. Physical scenario transitions remain untested.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    exe, report = compose()
    proof = check(exe)
    print(json.dumps({'component': report, 'proof': proof}, indent=2), flush=True)
    if not args.write:
        return
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    base = ROOT/'work/output'/PRIOR
    archive = (base/'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(json.loads((base/'font-mode-details.json').read_text('utf-8')))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    planned, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in planned[3] if planned[3][n] != planned[2][n]] == ['1ST_READ.BIN']
    planned[7].update(kind=report['kind'], component_manifest_name='hardware-map-bypass-component.json',
        proof_scope=proof['scope'], readme_component_text=report['scope']+'\n',
        current_native_evidence={'map_hook_bypass': 'hardware-map-bypass-native-test.json'},
        current_live_evidence={},
        inherited_proof_note='Parent 0.7.34 and earlier evidence retain their original tested identities. Only the shared wrapper is newly executed here; no new live emulator or physical hardware pass is claimed.',
        pending=[report['tradeoff'], 'New Game and Clear 2/Clear 3 transition retests on Dreamcast GDEMU/VGA'])
    write_plan(planned, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = ROOT/'work/output'/VERSION
    for name, obj in [('hardware-map-bypass-component.json', report),
                      ('hardware-map-bypass-native-test.json', proof), ('font-mode-details.json', mode)]:
        (out/name).write_text(json.dumps(obj, indent=2)+'\n', encoding='utf-8')
    path = out/'font4x-patch.json'
    manifest = json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION, previous_build=PRIOR, status='Shared map hook bypass; hardware result pending',
                    current_payload_identities=planned[7]['files'], hardware_map_bypass=report)
    manifest['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    manifest['font_modes'] = {k: v for k, v in mode.items() if k not in ('metrics', 'labels', 'archive_packing')}
    path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (out/'READ-ME.txt').write_text('Rayblade 0.7.35: one shared draw-target literal restored.\n'
        'All 0.7.34 assets/fixes retained; map-label fractional positions no longer snapped.\n'
        'Original-input DCP diagnostic; GDI output for GDEMU/VGA. Hardware result pending.\n', encoding='utf-8')


if __name__ == '__main__':
    main()
