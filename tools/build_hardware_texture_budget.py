"""0.7.37: change only graphics reservation on the 0.7.36 asset-split control."""
import argparse
import copy
import json
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save

VERSION, PRIOR = '0.7.37', '0.7.36'
SOURCE_SHA = '054d99fbd8a29d981d4ba478b05a3817181c8dfd77267e30208bdbb0b15de020'
TARGET_SHA = 'f04e4b011fa2ff42107a72ac65dda99733a0cc537fa529867014ea9b3dcf191a'
SPANS = ((0x6b900, 0x6b918), (0xc234e, 0xc2356), (0xc24b4, 0xc24b8))


def compose():
    from build_hardware_map_grid_fix import compose as reservation_source
    root = ROOT/'work/output'
    old = (root/PRIOR/'1ST_READ.BIN').read_bytes()
    assert digest(old) == SOURCE_SHA
    donor, detail = reservation_source()
    assert donor == (root/'0.7.33/1ST_READ.BIN').read_bytes()
    before = (root/'0.7.32/1ST_READ.BIN').read_bytes()
    exe = bytearray(old)
    for start, end in SPANS:
        assert old[start:end] == before[start:end]
        exe[start:end] = donor[start:end]
    changes = [i for i, (a, b) in enumerate(zip(old, exe)) if a != b]
    assert len(changes) == 33 and digest(exe) == TARGET_SHA
    assert all(any(start <= i < end for start, end in SPANS) for i in changes)
    report = {
        'version': VERSION, 'date': '2026-11-09', 'source_build': PRIOR,
        'kind': 'Graphics reservation only on the reported no-freeze asset split',
        'source_executable_sha256': SOURCE_SHA, 'executable_sha256': TARGET_SHA,
        'changed_executable_bytes': len(changes),
        'allowed_spans': [[hex(a), hex(b)] for a, b in SPANS],
        'graphics_reservation': detail['graphics_reservation'],
        'reason': 'Video shows early white rectangles in battle overlays/dialogue, then readable portraits/text/shadows and further scene progression. Test graphics resource pressure with one functional change.',
        'evidence': 'docs/hardware-0736-video-follow-up.json',
        'baseline_version_basis': 'User explicitly confirmed on 2026-11-09: Yes, 0.7.36. The recording itself does not display a version.',
        'retained': 'Every asset and other executable byte exact 0.7.36: Native 1x only, story choices, map lettering, original sprite draw target, RGB888, full-size movies. No font selector.',
        'excluded': 'No map sniff/snap hook, RGB565 conversion, runtime text compression, atlas compaction, grid/target/clipping or loading/movie-edge correction is introduced.',
        'limits': [
            'Video is consistent with graphics resource pressure but provides no physical memory capture; cause remains unconfirmed.',
            'A smaller geometry reservation trades list-growth headroom for texture space. Busy-battle and scenario regressions need physical testing.',
            'This is not full emulator feature parity. Small/misplaced loading text and other historical graphical issues can remain.'
        ],
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'public_release': False, 'upgrade_patch': False,
    }
    return bytes(exe), report


def check(exe, report):
    from build_hardware_map_grid_fix import budget_check
    old = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    proof = budget_check(exe, old, report)
    for case in proof['actual_SDK_budget_cases']:
        case['version'] = PRIOR if case['version'] == '0.7.32' else VERSION
    proof.update(version=VERSION, baseline=PRIOR)
    return proof


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    proof = check(exe, report)
    base = ROOT/'work/output'/PRIOR
    archive = (base/'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(base/'font-mode-details.json'))
    assert mode['native_only'] and mode['HD_bank_removed'] and not mode['title_selector']
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    planned, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in planned[3] if planned[3][n] != planned[2][n]] == ['1ST_READ.BIN']
    planned[7].update(kind=report['kind'], component_manifest_name='hardware-texture-budget-component.json',
        proof_scope=proof['scope'], readme_component_text=report['retained']+'\n'+report['excluded']+'\n',
        current_native_evidence={'graphics_reservation': 'hardware-texture-budget-native-test.json'},
        current_live_evidence={}, inherited_proof_note='Earlier evidence retains its actual tested executable identities. No new physical or live-emulator run claimed.',
        pending=report['limits'])
    write_plan(planned, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = ROOT/'work/output'/VERSION
    save(out/'hardware-texture-budget-details.json', report)
    save(out/'hardware-texture-budget-native-test.json', proof)
    save(out/'font-mode-details.json', mode)
    manifest = read(out/'font4x-patch.json')
    manifest.update(version=VERSION, previous_build=PRIOR,
        status='Graphics reservation diagnostic; physical result pending',
        current_payload_identities=planned[7]['files'], hardware_texture_budget=report)
    manifest['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    manifest['font_modes'] = {k: v for k, v in mode.items() if k not in ('metrics', 'labels', 'archive_packing')}
    save(out/'font4x-patch.json', manifest)
    save(ROOT/'docs/hardware-texture-budget-diagnostic.json', dict(report, native_validation=proof))
    return report


def audit():
    _, report = compose()
    root = ROOT/'work/output'
    folder = root/f'dcp-{VERSION}-diagnostic'
    target = read(folder/'target-tree.json')
    previous = read(root/f'dcp-{PRIOR}-diagnostic/target-tree.json')
    assert len(target['files']) == 141 and set(target['files']) == set(previous['files'])
    assert [n for n in target['files'] if target['files'][n] != previous['files'][n]] == ['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256'] == TARGET_SHA
    bundle = read(folder/'bundle-validation.json')
    assert digest((folder/bundle['asset']).read_bytes()) == bundle['sha256']
    proof = read(folder/'original-apply-validation.json')
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256'] == bundle['game_tree_sha256']
    assert proof['bootsector_invariant_sha256'] == bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    native = read(root/VERSION/'hardware-texture-budget-native-test.json')
    assert native['executable_sha256'] == TARGET_SHA and len(native['actual_SDK_budget_cases']) == 4
    report.update(all_140_game_files_and_boot_checked=True,
        all_13_other_modified_payloads_exact_0_7_36=True, native_validation=native,
        disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],
        DCP=dict(bundle, path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    manual = read(ROOT/'docs/hardware-entry-hang-results.json').get('results', {}).get(VERSION)
    if manual:
        report.update(hardware_result=manual['status'], hardware_report=manual, hardware_follow_up=manual.get('evidence'))
    save(ROOT/'docs/hardware-texture-budget-diagnostic.json', report)
    path = ROOT/'docs/hardware-chapter-transition.json'
    current = read(path)
    current['texture_budget_candidate'] = {'version': VERSION, 'documentation': 'docs/hardware-texture-budget-diagnostic.json',
        'DCP': report['DCP']['path'], 'status': 'Original-input DCP verified locally; physical graphics and freeze-regression tests pending',
        'public_release': False, 'upgrade_patch': False}
    current['next_compatibility_candidate'] = current['texture_budget_candidate']
    if manual:
        current['texture_budget_candidate'].update(status=manual['status'], hardware_report=manual)
    if 'framebuffer_candidate' in current:
        current['next_compatibility_candidate'] = current['framebuffer_candidate']
    if 'window_atlas_candidate' in current:
        current['next_compatibility_candidate'] = current['window_atlas_candidate']
    if 'display_polish_candidate' in current:
        current['next_compatibility_candidate'] = current['display_polish_candidate']
    current['last_updated'] = max(current.get('last_updated', ''), '2026-11-09')
    save(path, current)
    path = ROOT/'docs/hardware-entry-hang-results.json'
    current = read(path)
    if not (ROOT/'docs/hardware-framebuffer-diagnostic.json').exists():
        current['interpretation']['new_build_created'] = '0.7.37: only graphics reservation changed from 0.7.36; original-input DCP verified; '+('hardware result recorded separately' if manual else 'physical result pending')
    save(path, current)
    return report


if __name__ == '__main__':
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
