"""0.7.36: exact passing 0.7.31 executable with only the 0.7.6 asset group."""
import argparse
import copy
import json
from build_bitmap_font import ROOT, digest

VERSION, PRIOR, BASELINE = '0.7.36', '0.7.27', '0.7.31'
BASE_SHA = '054d99fbd8a29d981d4ba478b05a3817181c8dfd77267e30208bdbb0b15de020'


def read(path):
    return json.loads(path.read_text('utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def compose():
    root = ROOT/'work/output'
    old = (root/PRIOR/'1ST_READ.BIN').read_bytes()
    exe = (root/BASELINE/'1ST_READ.BIN').read_bytes()
    assert digest(exe) == BASE_SHA and len(exe) == len(old)
    differences = [i for i, (a, b) in enumerate(zip(old, exe)) if a != b]
    assert len(differences) == 86
    assert all(0x8d00 <= i < 0x8d60 or 0x6b724 <= i < 0x6b728 for i in differences)
    reports = {v: read(root/v/'english-disc-report.json') for v in (PRIOR, BASELINE)}
    assert set(reports[PRIOR]['files']) == set(reports[BASELINE]['files'])
    changed = []
    for name, identity in reports[PRIOR]['files'].items():
        relative = 'text/'+name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name
        data = (root/PRIOR/relative).read_bytes()
        base = (root/BASELINE/relative).read_bytes()
        assert len(data) == identity['size'] and digest(data) == identity['sha256']
        baseline_identity = reports[BASELINE]['files'][name]
        assert len(base) == baseline_identity['size'] and digest(base) == baseline_identity['sha256']
        if data != base:
            changed.append(name)
    assert set(changed) == {'1ST_READ.BIN', 'D_SCE.AFS', 'WMAP.AFS'}
    report = {
        'version': VERSION, 'date': '2026-11-07', 'source_build': PRIOR,
        'runtime_baseline': BASELINE, 'executable_sha256': digest(exe),
        'executable_exact_passing_baseline': True,
        'changed_executable_bytes_from_0_7_27': len(differences),
        'changed_game_files_from_passing_baseline': ['D_SCE.AFS', 'WMAP.AFS'],
        'kind': 'Historical asset/runtime regression split',
        'reason': '0.7.35 still fails New Game and post-dialogue transitions. Return to the small earlier 0.7.31/0.7.27 boundary instead of mixing later changes.',
        'scope': 'Exact 0.7.31 code and font; exact 0.7.27 assets. Only story-choice and map-label archives differ from 0.7.31. No custom map hook remains, including its unused body.',
        'known_limitations': 'Later loading, movie-edge, compact UI, memory, grid, targeting and clipping fixes are intentionally absent. Earlier visual defects can return. Native 1x only; no HD bank or selector.',
        'on_pass': 'The two assets alone are insufficient for the matched earlier failure; investigate the removed hook or its interaction. This does not identify the remaining full-feature 0.7.35 failure.',
        'on_fail': 'For a matched failure absent in 0.7.31, split D_SCE.AFS versus WMAP.AFS and archive/resource loading. Do not conclude that dialogue wording is faulty.',
        'test_paths': ['New Game first dialogue and later Koichiro/Kasumi Hallway', 'Clear 2 normal VMU save -> Next', 'Clear 3 save through all dialogue and the following scene'],
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'public_release': False, 'upgrade_patch': False,
    }
    return exe, report


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    root = ROOT/'work/output'
    base = root/PRIOR
    archive = (base/'WIN00.AFS').read_bytes()
    assert archive == (root/BASELINE/'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(root/BASELINE/'font-mode-details.json'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    planned, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in planned[3] if planned[3][n] != planned[2][n]] == ['1ST_READ.BIN']
    planned[7].update(kind=report['kind'], component_manifest_name='hardware-asset-split-component.json',
        proof_scope='Exact executable identity with reported-passing 0.7.31; exact asset identities with 0.7.27. No new emulator or hardware execution claimed.',
        readme_component_text=report['scope']+'\n'+report['known_limitations']+'\n',
        current_native_evidence={}, current_live_evidence={},
        inherited_proof_note='Historical proofs retain original executable identities. Current checks establish byte identity and disc/package integrity only.',
        pending=report['test_paths'])
    write_plan(planned, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = root/VERSION
    save(out/'hardware-asset-split-details.json', report)
    save(out/'font-mode-details.json', mode)
    manifest = read(out/'font4x-patch.json')
    manifest.update(version=VERSION, previous_build=PRIOR,
        status='Historical asset/runtime split; physical test pending',
        current_payload_identities=planned[7]['files'], hardware_asset_split=report)
    manifest['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    manifest['font_modes'] = {k: v for k, v in mode.items() if k not in ('metrics', 'labels', 'archive_packing')}
    save(out/'font4x-patch.json', manifest)
    save(ROOT/'docs/hardware-asset-runtime-split.json', report)
    return report


def audit_package():
    _, report = compose()
    root = ROOT/'work/output'
    folder = root/f'dcp-{VERSION}-diagnostic'
    target = read(folder/'target-tree.json')
    baseline = read(root/f'dcp-{BASELINE}-diagnostic/target-tree.json')
    parent = read(root/f'dcp-{PRIOR}-diagnostic/target-tree.json')
    assert len(target['files']) == 141 and set(target['files']) == set(baseline['files']) == set(parent['files'])
    assert {n for n in target['files'] if target['files'][n] != baseline['files'][n]} == {'D_SCE.AFS', 'WMAP.AFS'}
    assert [n for n in target['files'] if target['files'][n] != parent['files'][n]] == ['1ST_READ.BIN']
    bundle = read(folder/'bundle-validation.json')
    assert digest((folder/bundle['asset']).read_bytes()) == bundle['sha256']
    proof = read(folder/'original-apply-validation.json')
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256'] == bundle['game_tree_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    report.update(all_140_game_files_and_boot_checked=True,
        disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],
        DCP=dict(bundle, path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    manual = read(ROOT/'docs/hardware-entry-hang-results.json')['results'].get(VERSION)
    if manual:
        report.update(hardware_result=manual['status'], hardware_follow_up=manual,
                      last_updated=manual['reported_date'])
        report['DCP']['hardware_result'] = manual['status']
    save(ROOT/'docs/hardware-asset-runtime-split.json', report)
    path = ROOT/'docs/hardware-chapter-transition.json'
    current = read(path)
    current['asset_runtime_split_candidate'] = {
        'version': VERSION, 'documentation': 'docs/hardware-asset-runtime-split.json',
        'DCP': report['DCP']['path'], 'status': 'Original-input DCP verified locally; matched physical tests pending',
        'public_release': False, 'upgrade_patch': False}
    if manual:
        current['asset_runtime_split_candidate'].update(status=manual['status'], hardware_report=manual)
    current['next_compatibility_candidate'] = current['asset_runtime_split_candidate']
    if 'texture_budget_candidate' in current:
        current['next_compatibility_candidate'] = current['texture_budget_candidate']
    if 'framebuffer_candidate' in current:
        current['next_compatibility_candidate'] = current['framebuffer_candidate']
    if 'window_atlas_candidate' in current:
        current['next_compatibility_candidate'] = current['window_atlas_candidate']
    if 'display_polish_candidate' in current:
        current['next_compatibility_candidate'] = current['display_polish_candidate']
    current['last_updated'] = max(current.get('last_updated', ''), '2026-11-07')
    save(path, current)
    path = ROOT/'docs/hardware-entry-hang-results.json'
    current = read(path)
    if not manual:
        current['interpretation']['new_build_created'] = '0.7.36: original-input DCP verified; exact 0.7.31 executable plus 0.7.27 story-choice/map archives; physical result pending'
    current['last_updated'] = max(current.get('last_updated', ''), '2026-11-07')
    save(path, current)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--audit-package', action='store_true')
    args = parser.parse_args()
    result = (audit_package() if args.audit_package else build()) if args.write else compose()[1]
    print(json.dumps(result, indent=2), flush=True)
