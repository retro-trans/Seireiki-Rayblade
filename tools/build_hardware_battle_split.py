"""0.7.45: battle display half of the failed 0.7.43 code, on passing 0.7.44."""
import argparse
import copy
import json
from build_bitmap_font import ROOT,digest
from build_hardware_asset_split import read,save

VERSION,PRIOR,FAILED='0.7.45','0.7.44','0.7.43'
BASE_SHA='1426cd32cbc942bed643ad6f5cd3e8e0fdcd0b1370867eb5599dc73e6a3a4d90'
FAILED_SHA='463e54d5244ca008410c8a47369b3f2a6e42906303dc8eaa6143b46b415c2c55'
TARGET_SHA='d13d6cf267e5ce6ec07a70439205901596174912042e41feed39fbc885bf107f'
GROUPS=(('0.7.19','0.7.20','Movement/range grid'),('0.7.20','0.7.21','Targeting and animation graphics'),('0.7.22','0.7.23','Lines, split clipping and selection bars'))


def compose():
    root=ROOT/'work/output'
    old=(root/PRIOR/'1ST_READ.BIN').read_bytes();failed=(root/FAILED/'1ST_READ.BIN').read_bytes()
    assert digest(old)==BASE_SHA and digest(failed)==FAILED_SHA and len(old)==len(failed)
    exe=bytearray(old);used=set();groups=[]
    for before,after,label in GROUPS:
        a=(root/before/'1ST_READ.BIN').read_bytes();b=(root/after/'1ST_READ.BIN').read_bytes()
        assert len(a)==len(b)==len(exe)
        delta={i for i,(x,y) in enumerate(zip(a,b)) if x!=y}
        assert not used.intersection(delta)
        for i in delta:
            assert exe[i]==a[i] and failed[i]==b[i],(label,hex(i))
            exe[i]=b[i]
        used.update(delta);groups.append({'before':before,'after':after,'feature':label,'changed_bytes':len(delta)})
    assert {i for i,(a,b) in enumerate(zip(old,exe)) if a!=b}==used
    remaining={i for i,(a,b) in enumerate(zip(exe,failed)) if a!=b}
    assert len(used)==413 and len(remaining)==508 and not used.intersection(remaining)
    assert digest(exe)==TARGET_SHA
    return bytes(exe),{'version':VERSION,'date':'2026-11-14','source_build':PRIOR,'failed_comparison':FAILED,
        'source_executable_sha256':BASE_SHA,'executable_sha256':digest(exe),
        'kind':'Battle display code half-split on passing 0.7.44',
        'feature_groups':groups,'changed_executable_bytes':len(used),'remaining_failed_build_bytes':len(remaining),
        'scope':'413 of the 921 differing bytes restored exactly from failed 0.7.43; all other executable bytes and every asset exact 0.7.44.',
        'restored':['Movement/range grid alignment','Targeting/animation graphics coordinates','Application line coordinates','Inclusive split-battle clipping','Full-width menu selection bars'],
        'excluded':['Status wrapper/gate and vertical alignment','Signed SP formatting and measured location-header code','Stage 6 runtime text compression','Custom map filename/snapping hook'],
        'retained':'Passing 0.7.44 Native font, hardware memory/window repairs, loading/movie fixes and all newer data files.',
        'on_pass':'Battle code alone does not reproduce the failure on matched tested paths. Split the remaining 508 bytes and their interactions; do not restore every remaining change together.',
        'on_fail':'Split this 413-byte group: movement/targeting versus clipping/lines/selectors, retaining the passing 0.7.44 assets and code baseline.',
        'limits':['Hardware confirmation pending; no full-route or physical GPU/timing claim.','Status/header/SP fixes and Stage 6 compression remain absent; associated defects may persist.'],
        'hardware_result':'pending','hardware_root_cause_confirmed':False,'public_release':False,'upgrade_patch':False}


def check(exe,report):
    from test_battle_grid import check_candidate as grid
    from test_battle_target import check_candidate as target
    from test_battle_clip import check_candidate as clip
    from build_hardware_status_bypass import check as constructors
    baseline=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    proof={'version':VERSION,'executable_sha256':digest(exe)}
    proof['grid']=grid(exe,baseline,report)
    proof['target']=target(exe,report)
    proof['clip']=clip(exe,report,text_memory_baseline=baseline)
    proof['constructors']=dict(constructors(exe),version=VERSION)
    proof['scope']='Current-executable SH-4 grid, targeting, clipping, line and selection fixtures; eight original constructors match 0.7.40. Text-memory regions remain exact 0.7.44. Bounded GPU/heap endpoints and historical RAM fixture; no new live emulator or physical test.'
    return proof


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe,report=compose();proof=check(exe,report)
    print('PASS: battle routines and eight original constructors; 413-byte split verified.',flush=True)
    root=ROOT/'work/output';archive=(root/PRIOR/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(read(root/PRIOR/'font-mode-details.json'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in p[3] if p[3][n]!=p[2][n]]==['1ST_READ.BIN']
    p[7].update(kind=report['kind'],component_manifest_name='hardware-battle-split-component.json',proof_scope=proof['scope'],
        current_native_evidence={'battle_split':'hardware-battle-split-native-test.json'},current_live_evidence={},
        inherited_proof_note='Historical evidence retains its tested identity; current routine tests do not establish hardware compatibility.',
        readme_component_text=report['scope']+'\n',pending=report['limits'])
    write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=root/VERSION
    for name,obj in [('hardware-battle-split-details.json',report),('hardware-battle-split-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,obj)
    m=read(out/'font4x-patch.json');m.update(version=VERSION,previous_build=PRIOR,status='Battle display half-split; hardware pending',current_payload_identities=p[7]['files'],hardware_battle_split=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    m['font_modes']={k:v for k,v in mode.items() if k not in ('labels','metrics','archive_packing')}
    m['hardware_consolidation']['current_build_exception']='0.7.44 plus battle display group only; see hardware_battle_split.'
    save(out/'font4x-patch.json',m);save(ROOT/'docs/hardware-battle-split.json',dict(report,native_validation=proof))
    return report


def audit():
    exe,report=compose();root=ROOT/'work/output';folder=root/f'dcp-{VERSION}-diagnostic'
    evidence=ROOT/'docs/hardware-0745-follow-up.json'
    follow_up=read(evidence) if evidence.exists() else None
    if follow_up:report.update(hardware_result=follow_up['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    target,base=[read(root/f'dcp-{v}-diagnostic/target-tree.json') for v in (VERSION,PRIOR)]
    assert len(target['files'])==141 and set(target['files'])==set(base['files'])
    assert [n for n in target['files'] if target['files'][n]!=base['files'][n]]==['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256']==digest(exe)
    bundle,applied=read(folder/'bundle-validation.json'),read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes())==bundle['sha256']
    assert applied['release_metadata_verified'] and applied['audio_tracks_preserved']
    assert applied['verified_game_tree_sha256']==bundle['game_tree_sha256']
    assert applied['bootsector_invariant_sha256']==bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag']=='1' and not bundle['public_release']
    report.update(native_validation=read(root/VERSION/'hardware-battle-split-native-test.json'),all_140_game_files_and_boot_checked=True,
        disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    if follow_up:report['DCP']['hardware_result']=follow_up['status']
    save(ROOT/'docs/hardware-battle-split.json',report)
    path=ROOT/'docs/hardware-chapter-transition.json';d=read(path)
    d['battle_split_candidate']={'version':VERSION,'documentation':'docs/hardware-battle-split.json','DCP':report['DCP']['path'],'status':'Original-input DCP verified; hardware pending','public_release':False,'upgrade_patch':False}
    if follow_up:d['battle_split_candidate'].update(status=follow_up['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    d['next_compatibility_candidate']=d['battle_split_candidate'];d['last_updated']=max(d.get('last_updated',''),'2026-11-14',follow_up['date'] if follow_up else '');save(path,d)
    path=ROOT/'docs/hardware-entry-hang-results.json';d=read(path)
    d['interpretation'].update(new_build_created='0.7.45: 413-byte battle-display group restored on passing 0.7.44; other 508 bytes and all assets unchanged',working_baseline_next_test='Compare cold-boot New Game and mission dialogues against 0.7.44, then check movement grid, targeting, split battles and selection bars. Split the failed group further based on result.')
    if follow_up:d['interpretation'].update(latest_report=VERSION+': '+follow_up['status'],battle_split_result=follow_up['interpretation'],working_baseline_next_test=follow_up['next_test'])
    d['last_updated']=max(d.get('last_updated',''),'2026-11-14',follow_up['date'] if follow_up else '');save(path,d)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');p.add_argument('--audit-package',action='store_true');a=p.parse_args()
    if a.write:r=audit() if a.audit_package else build()
    else:
        exe,r=compose()
        if a.check:r['native_validation']=check(exe,r)
    print(json.dumps(r,indent=2))
