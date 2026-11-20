"""Audit matched Native-only historical controls and record original entry-hang focus.

Read-only unless --write; requires completed original-input DCP round trips.
No source scripts or Japanese dialogue are copied into the report.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    hardware_path = ROOT/'docs/hardware-entry-hang-results.json'
    hardware = read(hardware_path) if hardware_path.exists() else None
    baseline = ROOT/'work/output/0.7.27'
    baseline_report = read(baseline/'midpoint-hardware-diagnostic.json')
    cases = []
    for version, historical in (('0.7.29','0.7.11'), ('0.7.30','0.7.8')):
        out = ROOT/'work/output'/version
        source = ROOT/'work/output'/historical
        report = read(out/'midpoint-hardware-diagnostic.json')
        assert report['normalization_edits'] == baseline_report['normalization_edits']
        assert report['changed_executable_bytes'] == baseline_report['changed_executable_bytes'] == 438
        assert (out/'WIN00.AFS').read_bytes() == (baseline/'WIN00.AFS').read_bytes()
        old_exe, new_exe = [(p/'1ST_READ.BIN').read_bytes() for p in (source,out)]
        base_old, base_new = [(ROOT/'work/output'/v/'1ST_READ.BIN').read_bytes() for v in ('0.7.6','0.7.27')]
        assert len(old_exe)==len(new_exe)==len(base_old)==len(base_new)
        edits = [(i,a,b) for i,(a,b) in enumerate(zip(old_exe,new_exe)) if a!=b]
        assert edits == [(i,a,b) for i,(a,b) in enumerate(zip(base_old,base_new)) if a!=b]
        parent_files = read(source/'english-disc-report.json')['files']
        disc = read(out/'english-disc-report.json')
        assert set(parent_files) == set(disc['files'])
        assert disc['source_build'] == historical
        for name,row in parent_files.items():
            if name not in ('1ST_READ.BIN','WIN00.AFS'):
                assert row == disc['files'][name], name
        native = read(out/'midpoint-hardware-native-test.json')
        assert native['executable_sha256'] == sha(out/'1ST_READ.BIN') == report['executable_sha256']
        assert native['native_glyph_cases'] == 804
        assert len(native['allocation_cases']) == 8
        assert native['VGA_cases'] == 96 and native['movie_cases'] == 129
        package = ROOT/f'work/output/dcp-{version}-diagnostic'
        bundle = read(package/'bundle-validation.json')
        assert sha(package/bundle['asset']) == bundle['sha256']
        proof = read(package/'original-apply-validation.json')
        assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
        assert proof['verified_game_tree_sha256'] == bundle['game_tree_sha256']
        assert disc['validation']['changed_sector_EDC_ECC'] == 'pass'
        assert disc['validation']['unrelated_track_bytes'] == 'all unchanged'
        cases.append({'version':version, 'historical_source':historical,
                      'role':report['role'], 'normalization':report,
                      'identical_438_byte_normalization_to_0_7_27':True,
                      'entire_WIN00_identical_to_0_7_27':True,
                      'all_other_payloads_exact_parent':True,
                      'payload_count':len(disc['files']), 'native_validation':native,
                      'disc_validation':disc['validation'],
                      'DCP':dict(bundle,path=str((package/bundle['asset']).relative_to(ROOT)).replace('\\','/')),
                      'hardware_result':hardware['results'][version] if hardware else 'pending'})
    result = {
        'date':'2026-11-01', 'focus':'Original immediate conversation-start / mission-entry hang',
        'user_request':'Prepare both normalized 0.7.11 and 0.7.8 diagnostics for hardware testing.',
        'known_results':{
            '0.7.2':'Tester reports New Game, missions and exact later Hallway exchange pass.',
            'public_0.7.11':'Both selectable fonts reportedly hang immediately. Native selection still retained HD bank/selector.',
            '0.7.27':'Native-only 0.7.6 enters New Game/missions, but freezes later in Hallway. Not a full pass.'},
        'hallway_probe':{'version':'0.7.28','hardware_result':'pending',
                         'purpose':'Historical 0.7.4 probe for the later Hallway checkpoint; not an upper control for original entry hang.',
                         'evidence':'docs/hardware-hallway-midpoint.json'},
        'normalization_note':'All three comparison builds use byte-identical 438-byte executable normalization and the exact same complete WIN00 archive. Resource lengths/offsets remain historical; no later font renderer backport.',
        'test_protocol':[
            'Apply each full DCP independently to the original Japanese image; output GDI for GDEMU/VGA.',
            'Cold boot each version. Start New Game and record whether first dialogue appears and advances, or immediate hang/black.',
            'Separately load normal Clear 2 VMU save -> Next and record conversation entry.',
            'If entry works, record later Koichiro/Kasumi Hallway behavior separately. Do not collapse it into an entry failure.'],
        'interpretation':{
            'upper_control_fails_immediately':'If 0.7.29 fails at entry, use 0.7.30: entry pass narrows to 0.7.9-0.7.11; immediate fail narrows to 0.7.7-0.7.8, relative to 0.7.27.',
            'upper_control_enters':'If 0.7.29 enters, original selectable 0.7.11 and normalized 0.7.11 differ in the shared normalization or its interaction. Do not blame or clear individual historical changes without further controls.',
            'nonmonotonic_results':'If 0.7.30 fails at entry but 0.7.29 passes, stop monotonic bisection and investigate interactions or test reproducibility.'},
        'cause_confirmed':False, 'symptoms_proven_independent_causes':False,
        'public_release':False, 'upgrade_patches':False, 'builds':cases}
    if hardware:
        result.update(last_updated=hardware.get('last_updated',hardware['date']),hardware_follow_up=hardware,
                      hardware_follow_up_source='docs/hardware-entry-hang-results.json')
        result['known_results'].update({v:r['status']+': '+r['report'] for v,r in hardware['results'].items()})
        if '0.7.28' in hardware['results']:
            result['hallway_probe']['hardware_result'] = hardware['results']['0.7.28']
    if args.write:
        (ROOT/'docs/hardware-entry-hang-diagnostics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        path=ROOT/'docs/hardware-chapter-transition.json'
        current=read(path)
        # Preserve all earlier Hallway evidence and its pending probe.
        current['current_focus']='Original immediate conversation-start / mission-entry hang; later Hallway tracked separately'
        current['entry_hang_investigation']={
            'documentation':'docs/hardware-entry-hang-diagnostics.json',
            'status':'Both full original-input Native-only DCP controls verified locally; hardware results pending',
            'upper_control':'0.7.29 = Native-only historical 0.7.11',
            'midpoint':'0.7.30 = Native-only historical 0.7.8',
            'baseline':'0.7.27 = Native-only historical 0.7.6; passes entry only',
            'cause_confirmed':False}
        previous = current.get('next_compatibility_candidate', {})
        if previous.get('version') == '0.7.28':
            current['hallway_compatibility_candidate'] = previous
        candidates = [{'version':case['version'], 'historical_midpoint':case['historical_source'],
                       'role':case['role'], 'status':'Verified locally; hardware result pending',
                       'documentation':'docs/hardware-entry-hang-diagnostics.json',
                       'DCP':case['DCP']['path'], 'public_release':False,
                       'upgrade_patch':False, 'source':'Original Japanese image only',
                       'test':'Cold boot GDI on GDEMU/VGA; original immediate conversation-start hang first; later Hallway separately'}
                      for case in cases]
        current['next_compatibility_candidate'] = candidates[0]
        current['additional_entry_hang_candidate'] = candidates[1]
        if hardware:
            current['last_updated'] = hardware.get('last_updated',hardware['date'])
            current['entry_hang_investigation']['status'] = 'Both diagnostics reported unsuccessful; 0.7.30 conversation checkpoint clarification pending'
            current['entry_hang_investigation']['hardware_follow_up'] = 'docs/hardware-entry-hang-results.json'
            current['entry_hang_investigation']['latest_results'] = hardware['results']
            current['next_compatibility_candidate']['status'] = hardware['results']['0.7.29']['status']
            current['additional_entry_hang_candidate']['status'] = hardware['results']['0.7.30']['status']
            current['entry_hang_investigation']['next_step'] = hardware['interpretation']['pending_question']
            if '0.7.28' in hardware['results']:
                current['hallway_compatibility_candidate']['status'] = hardware['results']['0.7.28']['status']
                current['hallway_compatibility_candidate']['hardware_report'] = hardware['results']['0.7.28']
                current['hallway_bisection'].update(
                    good='0.7.28: Native-only historical 0.7.4, reported no black screen/freezes on tested paths; quarter-screen movies remain',
                    narrowed_group='Historical 0.7.5 movie scaling versus 0.7.6 choice/map changes, for matched Hallway behavior',
                    cause_confirmed=False)
        # A later verified movie-only control supersedes the already tested
        # upper control as the next candidate; retain both earlier results.
        if (ROOT/'docs/hardware-movie-only-diagnostic.json').exists():
            current['tested_entry_upper_control'] = candidates[0]
            current['next_compatibility_candidate'] = current['working_baseline_movie_control']
        if 'cosmetic_candidate' in current:
            current['next_compatibility_candidate']=current['cosmetic_candidate']
        if 'map_grid_candidate' in current:
            current['next_compatibility_candidate']=current['map_grid_candidate']
        if 'full_catchup_candidate' in current:
            current['next_compatibility_candidate']=current['full_catchup_candidate']
        if 'map_hook_bypass_candidate' in current:
            current['next_compatibility_candidate']=current['map_hook_bypass_candidate']
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
        path.write_text(json.dumps(current,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':[{k:c[k] for k in ('version','historical_source','role','payload_count','DCP')} for c in cases],
                      'exact_shared_normalization':True,'hardware_result':hardware['results'] if hardware else 'pending','written':args.write},indent=2))


if __name__=='__main__':
    main()
