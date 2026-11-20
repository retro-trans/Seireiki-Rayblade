"""0.7.38: isolate RGB565 on the 0.7.37 no-freeze texture-budget diagnostic."""
import argparse
import copy
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save

VERSION, PRIOR = '0.7.38', '0.7.37'
SOURCE_SHA = 'f04e4b011fa2ff42107a72ac65dda99733a0cc537fa529867014ea9b3dcf191a'


def compose():
    old = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    assert digest(old) == SOURCE_SHA
    assert old[0x10cb0:0x10cb4] == bytes.fromhex('04e531e4')
    exe = bytearray(old)
    exe[0x10cb0] = 0  # Katana enum 0 = RGB565, not enum 1 (RGB555).
    assert [i for i, (a, b) in enumerate(zip(old, exe)) if a != b] == [0x10cb0]
    return bytes(exe), {
        'version': VERSION, 'date': '2026-11-10', 'source_build': PRIOR,
        'kind': 'RGB565 framebuffer only on the no-freeze texture-budget diagnostic',
        'source_executable_sha256': SOURCE_SHA, 'executable_sha256': digest(exe),
        'changed_executable_bytes': 1, 'offset': '0x10cb0', 'old_byte': '04', 'new_byte': '00',
        'display': {'SDK_enum': 0, 'format': 'RGB565', 'resolution': [640, 480],
                    'buffers': 2, 'old_framebuffer_bytes': 1843200,
                    'new_framebuffer_bytes': 1228800, 'saved_bytes': 614400},
        'reason': 'The follow-up video progresses into Chapter 4 with normal battle shadows/dialogue, but the Office background and dialogue are white rectangles at 00:30-00:34. Test remaining texture pressure with one setting.',
        'evidence': 'docs/hardware-0737-video-follow-up.json',
        'retained': 'Every asset and other executable byte exact 0.7.37: original graphics reservation, Native Skies 1x only, story choices, map labels, stock sprite draw and full-size movies.',
        'excluded': 'No custom map hook, font-kernel update, atlas compaction, runtime text compression, loading/movie-edge, grid/target/clipping or later UI change.',
        'limits': ['Texture pressure is a hypothesis, not a physical memory measurement.',
                   'RGB565 has lower screen color precision; verify movies, fades and gradients on VGA.',
                   'Stock graphics reservation and historical visual issues remain. This is not full emulator feature parity.',
                   'New Game/Hallway, Clear 2 -> Next, Clear 3 -> Chapter 4 and busy battles need physical retesting.'],
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'public_release': False, 'upgrade_patch': False,
    }


def check(exe, report):
    from test_native_movie_font import DrawCPU, STOP, bits
    from build_battle_memory_fix import UNITS
    class CPU(DrawCPU):
        def execute(self, pc, delay=False):
            if pc == 0x8c0e77e0:
                self.reg[0] = self.query
                return self.pr
            return super().execute(pc, delay)
    def cpu(image):
        c = CPU(image, b'', 0, 0)
        c.regions = [(0x8c000000, bytearray(0x1000000))]
        c.regions[0][1][0x10000:0x10000+len(image)] = image
        c.reg[15] = 0x8cffe000
        c.pr = STOP
        c.fr = [bits(0.)]*16
        c.fpul = 0
        c.visited = set()
        return c
    formats, budgets = [], []
    old = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    for version, image, depth, wr, rd in [(PRIOR, old, 24, 4, 2), (VERSION, exe, 16, 1, 1)]:
        c = cpu(image)
        c.reg[4:8] = [640, 480, image[0x10cb0], 1]
        c.write(0x8c461bdc, image[0x10cb2], 4)
        c.pc = 0x8c0e9ce0
        n = 0
        while c.pc != 0x8c0e9e68:
            assert n < 2000
            c.pc = c.execute(c.pc)
            n += 1
        p = c.reg[14]
        assert c.reg[11] == depth and c.read(p+48, 4) == wr and c.read(p+60, 4) == rd
        fb = 640*480*depth//8
        formats.append({'version': version, 'SDK_enum': image[0x10cb0],
                        'bits_per_pixel': depth, 'write_format': wr, 'read_format': rd,
                        'framebuffer_bytes_each': fb, 'instructions': n})
        for query in (0, 1):
            c = cpu(image)
            c.query = query
            c.reg[13], c.reg[14] = 0x8c46214c, 0x8c419b38
            for at, value in [(0x8c461bd0, 0x800000), (0x8c46214c+92, 0x1b4fa8),
                              (0x8c46214c+96, fb), (0x8c46214c+100, 0xfd20)]:
                c.write(at, value, 4)
            c.pc, n = 0x8c0d230c, 0
            while c.pc not in (0x8c0d2368, 0x8c0d241a):
                assert n < 1000
                c.pc = c.execute(c.pc)
                n += 1
            assert c.pc == 0x8c0d2368 and c.reg[11] == UNITS
            assert c.read(0x8c46214c+88, 4) == UNITS
            c.pc = c.execute(c.pc)
            n += 1
            assert c.pc == 0x8c0e5200 and c.reg[4] == UNITS and UNITS > c.read(0x8c4621b0, 4)
            budgets.append({'version': version, 'query': query, 'framebuffer_bytes_each': fb,
                            'reservation_units': UNITS, 'reservation_bytes': UNITS*2,
                            'reaches_native_allocator': True, 'instructions': n})
    return {'version': VERSION, 'executable_sha256': digest(exe),
            'scope': 'Execute actual SDK format selection and budget/minimum/allocator-entry code with bounded inputs; no physical GPU or scene replay.',
            'actual_SDK_format_cases': formats, 'actual_SDK_budget_cases': budgets,
            'limits': ['Configuration query outcomes are bounded fixtures; query 1 is not a measured hardware state.',
                       'Pixel bit depth is checked in SDK code; buffer byte counts follow 640x480*depth/8. Physical allocation/rendering remains unmeasured.']}


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    proof = check(exe, report)
    base = ROOT/'work/output'/PRIOR
    mode = copy.deepcopy(read(base/'font-mode-details.json'))
    assert mode['native_only'] and mode['HD_bank_removed'] and not mode['title_selector']
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    archive = (base/'WIN00.AFS').read_bytes()
    planned, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in planned[3] if planned[3][n] != planned[2][n]] == ['1ST_READ.BIN']
    planned[7].update(kind=report['kind'], component_manifest_name='hardware-framebuffer-component.json',
        proof_scope=proof['scope'], readme_component_text=report['retained']+'\n'+report['excluded']+'\n',
        current_native_evidence={'framebuffer': 'hardware-framebuffer-native-test.json'},
        current_live_evidence={}, inherited_proof_note='Earlier evidence retains its actual tested executable identities; no new live run claimed.',
        pending=report['limits'])
    write_plan(planned, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = ROOT/'work/output'/VERSION
    save(out/'hardware-framebuffer-details.json', report)
    save(out/'hardware-framebuffer-native-test.json', proof)
    save(out/'font-mode-details.json', mode)
    manifest = read(out/'font4x-patch.json')
    manifest.update(version=VERSION, previous_build=PRIOR, status='RGB565-only diagnostic; physical result pending',
                    current_payload_identities=planned[7]['files'], hardware_framebuffer=report)
    manifest['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    manifest['font_modes'] = {k: v for k, v in mode.items() if k not in ('metrics', 'labels', 'archive_packing')}
    save(out/'font4x-patch.json', manifest)
    save(ROOT/'docs/hardware-framebuffer-diagnostic.json', dict(report, native_validation=proof))
    return report


def audit():
    exe, report = compose()
    root = ROOT/'work/output'
    folder = root/f'dcp-{VERSION}-diagnostic'
    target, old = read(folder/'target-tree.json'), read(root/f'dcp-{PRIOR}-diagnostic/target-tree.json')
    assert len(target['files']) == 141 and set(target['files']) == set(old['files'])
    assert [n for n in target['files'] if target['files'][n] != old['files'][n]] == ['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256'] == digest(exe)
    bundle, proof = read(folder/'bundle-validation.json'), read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes()) == bundle['sha256']
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256'] == bundle['game_tree_sha256']
    assert proof['bootsector_invariant_sha256'] == bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    native = read(root/VERSION/'hardware-framebuffer-native-test.json')
    assert native['executable_sha256'] == digest(exe)
    assert len(native['actual_SDK_budget_cases']) == 4 and len(native['actual_SDK_format_cases']) == 2
    report.update(all_140_game_files_and_boot_checked=True, all_assets_exact_0_7_37=True,
                  native_validation=native, disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],
                  DCP=dict(bundle, path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    manual = read(ROOT/'docs/hardware-entry-hang-results.json').get('results', {}).get(VERSION)
    if manual:
        report.update(hardware_result=manual['status'], hardware_report=manual, hardware_follow_up=manual.get('evidence'))
    save(ROOT/'docs/hardware-framebuffer-diagnostic.json', report)
    current = read(ROOT/'docs/hardware-chapter-transition.json')
    current['framebuffer_candidate'] = {'version': VERSION, 'documentation': 'docs/hardware-framebuffer-diagnostic.json',
        'DCP': report['DCP']['path'], 'status': 'Original-input DCP verified locally; hardware Office and freeze-regression tests pending',
        'public_release': False, 'upgrade_patch': False}
    current['next_compatibility_candidate'] = current['framebuffer_candidate']
    if manual:
        current['framebuffer_candidate'].update(status=manual['status'], hardware_report=manual)
    if 'window_atlas_candidate' in current:
        current['next_compatibility_candidate'] = current['window_atlas_candidate']
    if 'display_polish_candidate' in current:
        current['next_compatibility_candidate'] = current['display_polish_candidate']
    current['last_updated'] = max(current.get('last_updated', ''), '2026-11-10')
    save(ROOT/'docs/hardware-chapter-transition.json', current)
    current = read(ROOT/'docs/hardware-entry-hang-results.json')
    if not (ROOT/'docs/hardware-window-atlas-diagnostic.json').exists():
        current['interpretation']['new_build_created'] = '0.7.38: RGB565-only one-byte change from 0.7.37; original-input DCP verified; hardware result recorded separately' if manual else '0.7.38: physical result pending'
        current['interpretation']['working_baseline_next_test'] = '0.7.38: same Clear 3 Office scene at 00:30-00:34; continue to Chapter 4 and separately retest New Game/Hallway, Clear 2 and busy battles'
    save(ROOT/'docs/hardware-entry-hang-results.json', current)
    return report


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--audit-package', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.write:
        result = audit() if args.audit_package else build()
    else:
        exe, result = compose()
        if args.check:
            result['native_validation'] = check(exe, result)
    print(json.dumps(result, indent=2), flush=True)
