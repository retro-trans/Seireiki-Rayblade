"""Record the 0.7.34 hardware follow-up and audit the 0.7.35 narrow diagnostic."""
import argparse, hashlib, json, shutil, struct, tempfile
from pathlib import Path
from rayblade_codec import decompress

ROOT = Path(__file__).resolve().parents[1]
REPORT = ('All the fixes work, with the exception of the game freezing when starting a "New Game" '
          'or entering subsequent missions in the scenario. Surprisingly, it does load the scenario '
          '"Clear 3: A Girl\'s Resolve" for a brief moment (perhaps this will help with the diagnosis '
          '\u2013 see screenshot). However, once the all dialogue ends, it just goes to a black screen.')


def read(path):
    return json.loads(path.read_text('utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scenario_comparison():
    output = ROOT/'work/output'
    versions = ('0.7.2', '0.7.31', '0.7.34')
    reports = {v: read(output/v/'text/scenario-component-report.json') for v in versions}
    result = []
    for index in (1, 4):
        rows = {v: reports[v]['members'][index] for v in versions}
        data, packed = {}, {}
        for v in versions:
            archive = (output/v/'D_SCE.AFS').read_bytes()
            start, size = struct.unpack_from('<II', archive, 8+index*8)
            packed[v] = archive[start:start+size]
            data[v], used = decompress(packed[v][20:])
            assert used == size-20
            assert hashlib.sha256(data[v]).hexdigest() == rows[v]['decoded_sha256']
        base = data['0.7.31']
        original_size = rows['0.7.31']['original_bytes']
        assert all(data[v][:original_size] == base[:original_size] for v in versions)
        assert base == data['0.7.34']
        result.append({'member': rows['0.7.34']['name'],
            'original_VM_program_exact_0_7_2_31_34': True,
            'entire_decoded_member_exact_0_7_31_34': True,
            'decoded_bytes': len(base), 'decoded_sha256': hashlib.sha256(base).hexdigest(),
            'packed_member_exact_0_7_31_34': packed['0.7.31'] == packed['0.7.34'],
            'dialogue_command_count': len(rows['0.7.34']['commands']),
            'first_command': rows['0.7.34']['commands'][0]['id'],
            'last_command': rows['0.7.34']['commands'][-1]['id'],
            'scope': 'Member contents are equal; this does not establish identical archive offsets, runtime resources, I/O or hardware execution.'})
    return result


def record_followup():
    folder = ROOT/'work/ui/hardware-0734-transition-20261105'
    folder.mkdir(parents=True, exist_ok=True)
    sources = [
        ('codex-clipboard-e1608aff-0fed-47e0-a90d-3ee5d1252724.png', '01-vmu-clear2-clear3.png',
         'Load screen lists Clear 2 and Clear 3 saves. The highlighted row is Clear 2; the still image alone does not prove which save was subsequently loaded.'),
        ('codex-clipboard-aa86ec97-0f03-4631-a54d-73551c7ef7eb.png', '02-s004-reamond-dialogue.png',
         'Battle terrain, units, selection arrows, portrait and Reamond dialogue are visible. No pale unit rectangles in this frame. This is the opening command scenario.s_004.o00181, not evidence of the exact final line before failure.')]
    evidence = []
    for name, target, observation in sources:
        source = Path(tempfile.gettempdir())/name
        dest = folder/target
        if not dest.exists():
            shutil.copyfile(source, dest)
        assert sha(source) == sha(dest)
        evidence.append({'source': str(source), 'copy': dest.relative_to(ROOT).as_posix(),
                         'sha256': sha(dest), 'observation': observation})
    index = {'date': '2026-11-05', 'version': '0.7.34',
             'version_basis': 'Follow-up to the supplied 0.7.34 test; version is inferred from conversation context, not shown in either photograph.',
             'images': evidence}
    save(folder/'index.json', index)
    comparisons = scenario_comparison()
    result = {'reported_date': '2026-11-05',
        'status': 'Other fixes reported working; New Game/scenario freezes persist, including black screen after dialogue from Clear 3 save',
        'report': REPORT, 'version_basis': index['version_basis'],
        'device': 'Previously established real Dreamcast / GDEMU / VGA',
        'evidence': (folder/'index.json').relative_to(ROOT).as_posix(),
        'observed_script': 'scenario.s_004.o00181',
        'new_game_exact_checkpoint': 'Awaiting clarification: before first dialogue or later in a conversation',
        'Clear_3_exact_final_line': 'Awaiting clarification; supplied dialogue is the first command in s_004',
        'alignment_repair_sufficient': False, 'hardware_fix_confirmed': False,
        'scope_limit': 'Reporter says other fixes work; do not expand this into a complete-game or every-feature pass.'}
    save(ROOT/'docs/hardware-0734-follow-up.json', {
        'hardware_report': result, 'evidence': index, 'scenario_comparison': comparisons,
        'interpretation': 'At least one battle/dialogue scene renders before failure. Alignment-only repair did not solve the reported transitions. Identical early scenario payloads favor inspecting runtime/resource transitions, without proving a cause.',
        'next_control': '0.7.35 bypasses only the custom map-label sniff/snap hook on 0.7.34; all assets/final fixes remain.',
        'on_pass': 'The bypass implicates the shared custom hook or its interaction for the matched tested transition. Confirm repeated passes before generalizing.',
        'on_fail': 'The shared-hook bypass is insufficient; keep the result and split remaining runtime/asset groups against the passing baseline. Do not repeat the alignment-only repair as a claimed fix.'})
    path = ROOT/'docs/hardware-entry-hang-results.json'
    current = read(path)
    current['last_updated'] = max(current.get('last_updated', ''), '2026-11-05')
    current['results']['0.7.34'] = result
    current['interpretation'].update(cause_confirmed=False,
        full_feature_report='docs/hardware-0734-follow-up.json',
        latest_report='0.7.34 other fixes reported working; New Game and scenario transitions remain unsuccessful.',
        synthetic_map_fault='Old unaligned reads remain a demonstrated code defect, but repairing them alone was insufficient on hardware.',
        pending_0_7_34_question='Exact New Game checkpoint and last dialogue/scene before the Clear 3 black screen')
    if '0.7.35' in current['results']:
        current['interpretation']['latest_report'] = current['results']['0.7.35']['status']
    save(path, current)
    path = ROOT/'docs/hardware-full-catchup.json'
    current = read(path)
    current.update(hardware_result=result['status'], hardware_status=result['status'], hardware_follow_up=result)
    current['DCP']['hardware_result'] = result['status']
    save(path, current)
    path = ROOT/'docs/hardware-chapter-transition.json'
    current = read(path)
    current['last_updated'] = max(current.get('last_updated', ''), '2026-11-05')
    current['full_catchup_candidate'].update(status=result['status'], hardware_report=result)
    current['next_compatibility_candidate'] = current['full_catchup_candidate']
    if 'map_hook_bypass_candidate' in current:
        current['next_compatibility_candidate'] = current['map_hook_bypass_candidate']
    if 'asset_runtime_split_candidate' in current:
        current['next_compatibility_candidate'] = current['asset_runtime_split_candidate']
    if 'texture_budget_candidate' in current:
        current['next_compatibility_candidate'] = current['texture_budget_candidate']
    if 'framebuffer_candidate' in current:
        current['next_compatibility_candidate'] = current['framebuffer_candidate']
    if 'window_atlas_candidate' in current:
        current['next_compatibility_candidate'] = current['window_atlas_candidate']
    if 'display_polish_candidate' in current:
        current['next_compatibility_candidate'] = current['display_polish_candidate']
    save(path, current)
    return result


def audit_package():
    before, after = [ROOT/'work/output'/v for v in ('0.7.34', '0.7.35')]
    component = read(after/'hardware-map-bypass-component.json')
    old, new = [(p/'1ST_READ.BIN').read_bytes() for p in (before, after)]
    changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    assert len(new) == len(old) and changed == [0x6b724, 0x6b725, 0x6b726]
    assert sha(after/'1ST_READ.BIN') == component['executable_sha256']
    old_disc, disc = [read(p/'english-disc-report.json') for p in (before, after)]
    assert set(old_disc['files']) == set(disc['files']) and len(disc['files']) == 15
    assert [n for n in disc['files'] if disc['files'][n] != old_disc['files'][n]] == ['1ST_READ.BIN']
    for name in disc['files']:
        if name == '1ST_READ.BIN':
            continue
        relative = 'text/'+name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name
        assert sha(before/relative) == sha(after/relative)
    native = read(after/'hardware-map-bypass-native-test.json')
    assert native['draw_cases'] == 84 and native['executable_sha256'] == component['executable_sha256']
    package = ROOT/'work/output/dcp-0.7.35-diagnostic'
    bundle = read(package/'bundle-validation.json')
    proof = read(package/'original-apply-validation.json')
    previous = read(ROOT/'work/output/dcp-0.7.34-diagnostic/target-tree.json')
    target = read(package/'target-tree.json')
    assert len(target['files']) == 141 and set(previous['files']) == set(target['files'])
    assert [n for n in target['files'] if target['files'][n] != previous['files'][n]] == ['1ST_READ.BIN']
    assert sha(package/bundle['asset']) == bundle['sha256']
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256'] == bundle['game_tree_sha256']
    assert proof['bootsector_invariant_sha256'] == bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    result = {**component, 'all_14_other_payloads_exact_0_7_34': True,
        'all_140_game_files_and_boot_checked': True, 'native_validation': native,
        'disc_validation': disc['validation'],
        'DCP': dict(bundle, path=(package/bundle['asset']).relative_to(ROOT).as_posix())}
    manual = read(ROOT/'docs/hardware-entry-hang-results.json')['results'].get('0.7.35')
    if manual:
        result.update(hardware_result=manual['status'], hardware_follow_up=manual,
                      last_updated=manual['reported_date'])
        result['DCP']['hardware_result'] = manual['status']
    save(ROOT/'docs/hardware-map-hook-bypass.json', result)
    path = ROOT/'docs/hardware-chapter-transition.json'
    current = read(path)
    current['map_hook_bypass_candidate'] = {'version': '0.7.35', 'source': '0.7.34 with one shared draw target changed',
        'documentation': 'docs/hardware-map-hook-bypass.json', 'DCP': result['DCP']['path'],
        'status': 'Original-input DCP verified locally; matched Dreamcast transition tests pending',
        'public_release': False, 'upgrade_patch': False}
    if manual:
        current['map_hook_bypass_candidate'].update(status=manual['status'], hardware_report=manual)
    current['next_compatibility_candidate'] = current['map_hook_bypass_candidate']
    if 'asset_runtime_split_candidate' in current:
        current['next_compatibility_candidate'] = current['asset_runtime_split_candidate']
    if 'texture_budget_candidate' in current:
        current['next_compatibility_candidate'] = current['texture_budget_candidate']
    if 'framebuffer_candidate' in current:
        current['next_compatibility_candidate'] = current['framebuffer_candidate']
    if 'window_atlas_candidate' in current:
        current['next_compatibility_candidate'] = current['window_atlas_candidate']
    if 'display_polish_candidate' in current:
        current['next_compatibility_candidate'] = current['display_polish_candidate']
    save(path, current)
    path = ROOT/'docs/hardware-entry-hang-results.json'
    current = read(path)
    if not manual:
        current['interpretation'].update(new_build_created='0.7.35: shared map-label hook bypass only; physical result pending',
            working_baseline_next_test='Compare 0.7.35 and failing 0.7.34 on matched New Game and Clear 3 post-dialogue transition. All assets/final features retained except map position snapping.')
    save(path, current)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('record', 'package'), required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if args.write:
        result = record_followup() if args.phase == 'record' else audit_package()
        print(json.dumps(result, indent=2))
    else:
        print('Dry run: record evidence or verify completed diagnostic packaging with --write.')
