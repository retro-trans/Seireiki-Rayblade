"""0.7.44: exact working 0.7.40 executable with all 0.7.43 assets."""
import argparse
import copy
import json
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save

VERSION, PRIOR, BASELINE = '0.7.44', '0.7.43', '0.7.40'
BASE_SHA = '1426cd32cbc942bed643ad6f5cd3e8e0fdcd0b1370867eb5599dc73e6a3a4d90'
DATA_CHANGES = {'D_NAMES.BIN', 'ITM00.AFS', 'WMAP.AFS'}


def compose():
    root = ROOT/'work/output'
    exe = (root/BASELINE/'1ST_READ.BIN').read_bytes()
    old = (root/PRIOR/'1ST_READ.BIN').read_bytes()
    assert digest(exe) == BASE_SHA and len(exe) == len(old)
    reports = {v: read(root/f'dcp-{v}-diagnostic/target-tree.json') for v in (PRIOR, BASELINE)}
    assert set(reports[PRIOR]['files']) == set(reports[BASELINE]['files'])
    changed = {n for n in reports[PRIOR]['files'] if reports[PRIOR]['files'][n]!=reports[BASELINE]['files'][n]}
    for name in read(root/PRIOR/'english-disc-report.json')['files']:
        relative = 'text/'+name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name
        raw = (root/PRIOR/relative).read_bytes()
        identity = reports[PRIOR]['files'][name]
        assert digest(raw) == identity['sha256'] and len(raw) == identity['bytes']
    assert changed == DATA_CHANGES | {'1ST_READ.BIN'}
    return exe, {'version': VERSION, 'date': '2026-11-13', 'source_build': PRIOR,
        'runtime_baseline': BASELINE, 'executable_sha256': digest(exe),
        'source_executable_sha256': digest(old), 'executable_exact_0_7_40': True,
        'changed_executable_bytes_from_0_7_43': sum(a != b for a,b in zip(old,exe)),
        'changed_game_files_from_0_7_40': sorted(DATA_CHANGES),
        'kind': 'Remaining executable versus asset regression split',
        'reason': '0.7.43 still black-screens in New Game and mission dialogue despite status/map hook bypass and disabled text compression.',
        'scope': 'Exact reported-working 0.7.40 executable, including every unused helper byte; every other file exact 0.7.43. No selective code transplantation.',
        'retained': '0.7.40 Native-only font, hardware memory/window repairs, loading placement and movie fixes; newer D_NAMES.BIN, ITM00.AFS and WMAP.AFS assets.',
        'tradeoffs': 'Later executable UI/status/SP/header and battle grid/target/line/clip/selector fixes revert to 0.7.40. Stage 6 text compression remains absent. Some visual defects may return.',
        'on_pass': 'On matching checkpoints, the newer assets alone are insufficient to cause the failure. Split the removed executable changes, including their interaction with assets; do not conclude every asset is harmless.',
        'on_fail': 'If matched 0.7.40 still passes, split the three changed data files and their interaction with the baseline runtime. Recheck image identity and cold boot before attributing a cause.',
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'public_release': False, 'upgrade_patch': False,
        'validation_scope': 'Byte identity and disc/package integrity; no new live emulator or hardware execution claimed.'}


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    root = ROOT/'work/output'
    archive = (root/PRIOR/'WIN00.AFS').read_bytes()
    assert archive == (root/BASELINE/'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(root/BASELINE/'font-mode-details.json'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    p,_ = plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in p[3] if p[3][n]!=p[2][n]] == ['1ST_READ.BIN']
    p[7].update(kind=report['kind'],component_manifest_name='hardware-code-asset-split-component.json',
        proof_scope=report['validation_scope'],current_native_evidence={},current_live_evidence={},
        inherited_proof_note='Historical routine proofs retain their tested identities; this candidate restores the entire 0.7.40 executable.',
        readme_component_text=report['scope']+'\n'+report['tradeoffs']+'\n',pending=['Matched cold-boot New Game and mission-dialogue hardware tests'])
    write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe})
    out=root/VERSION
    for name,obj in [('hardware-code-asset-split-details.json',report),('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,obj)
    m=read(out/'font4x-patch.json')
    m.update(version=VERSION,previous_build=PRIOR,status='Code/asset diagnostic; hardware pending',current_payload_identities=p[7]['files'],hardware_code_asset_split=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    m['font_modes']={k:v for k,v in mode.items() if k not in ('labels','metrics','archive_packing')}
    m['hardware_consolidation']['current_build_exception']='Entire executable restored to 0.7.40; see hardware_code_asset_split.'
    save(out/'font4x-patch.json',m)
    save(ROOT/'docs/hardware-code-asset-split.json',report)
    return report


def audit():
    exe, report=compose(); root=ROOT/'work/output';folder=root/f'dcp-{VERSION}-diagnostic'
    evidence=ROOT/'docs/hardware-0744-follow-up.json'
    follow_up=read(evidence) if evidence.exists() else None
    if follow_up:report.update(hardware_result=follow_up['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    target,old,base=[read(root/f'dcp-{v}-diagnostic/target-tree.json') for v in (VERSION,PRIOR,BASELINE)]
    assert len(target['files'])==141 and set(target['files'])==set(old['files'])==set(base['files'])
    assert {n for n in target['files'] if target['files'][n]!=base['files'][n]}==DATA_CHANGES
    assert [n for n in target['files'] if target['files'][n]!=old['files'][n]]==['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256']==digest(exe)
    bundle,applied=read(folder/'bundle-validation.json'),read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes())==bundle['sha256']
    assert applied['release_metadata_verified'] and applied['audio_tracks_preserved']
    assert applied['verified_game_tree_sha256']==bundle['game_tree_sha256']
    assert applied['bootsector_invariant_sha256']==bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag']=='1' and not bundle['public_release']
    report.update(all_140_game_files_and_boot_checked=True,disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    if follow_up:report['DCP']['hardware_result']=follow_up['status']
    save(ROOT/'docs/hardware-code-asset-split.json',report)
    path=ROOT/'docs/hardware-chapter-transition.json';d=read(path)
    d['code_asset_split_candidate']={'version':VERSION,'documentation':'docs/hardware-code-asset-split.json','DCP':report['DCP']['path'],'status':'Original-input DCP verified; hardware pending','public_release':False,'upgrade_patch':False}
    if follow_up:d['code_asset_split_candidate'].update(status=follow_up['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    d['next_compatibility_candidate']=d['code_asset_split_candidate'];d['last_updated']=max(d.get('last_updated',''),'2026-11-13',follow_up['date'] if follow_up else '');save(path,d)
    path=ROOT/'docs/hardware-entry-hang-results.json';d=read(path)
    d['interpretation'].update(new_build_created='0.7.44: exact 0.7.40 executable and exact 0.7.43 assets',working_baseline_next_test='Compare matched cold-boot New Game and mission dialogues in 0.7.44 versus reported-working 0.7.40; only three data files differ.')
    if follow_up:d['interpretation'].update(latest_report=follow_up['status'],code_asset_split_result=follow_up['interpretation'],working_baseline_next_test=follow_up['next_test'])
    save(path,d)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--audit-package',action='store_true');a=p.parse_args()
    print(json.dumps((audit() if a.audit_package else build()) if a.write else compose()[1],indent=2))
