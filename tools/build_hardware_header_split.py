"""0.7.46: location-banner measurement only, on passing 0.7.45."""
import argparse
import copy
import json
from build_bitmap_font import ROOT,digest
from build_hardware_asset_split import read,save

VERSION,PRIOR,FAILED='0.7.46','0.7.45','0.7.43'
BASE_SHA='d13d6cf267e5ce6ec07a70439205901596174912042e41feed39fbc885bf107f'
FAILED_SHA='463e54d5244ca008410c8a47369b3f2a6e42906303dc8eaa6143b46b415c2c55'
TARGET_SHA='5bb81a7b491295d510780ed1dd152985e1d28456032d110c2df3c0812b005e38'
GROUPS=(('0.7.10','0.7.11','Measured location-banner widths'),)


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
    assert len(used)==260 and len(remaining)==248 and not used.intersection(remaining)
    assert digest(exe)==TARGET_SHA
    return bytes(exe),{'version':VERSION,'date':'2026-11-16','source_build':PRIOR,'failed_comparison':FAILED,
        'source_executable_sha256':BASE_SHA,'executable_sha256':digest(exe),
        'kind':'Location-header code half-split on passing 0.7.45',
        'feature_groups':groups,'changed_executable_bytes':len(used),'remaining_failed_build_bytes':len(remaining),
        'scope':'260 of the remaining 508 differing bytes restored exactly from failed 0.7.43; all other executable bytes and every asset exact 0.7.45.',
        'restored':['Location banners measure the current Native font advances; original right anchor, frame artwork and animation retained'],
        'excluded':['Status wrapper/gate and vertical alignment','Signed SP formatting','Stage 6 runtime text compression','Custom map filename/snapping hook'],
        'retained':'Passing 0.7.45 battle grid/target/line/clip/selector fixes, Native font, hardware memory/window repairs, loading/movie fixes and all data files.',
        'on_pass':'The location measurement change alone does not reproduce the failure on tested paths. Split the remaining 248 bytes and interactions; do not restore status/compression together.',
        'on_fail':'The 260-byte location-measurement change or its interaction with 0.7.45 reproduces the failure. Compare real call contexts and font/resource lifetime against the original routine; do not infer which instruction faults.',
        'limits':['Hardware confirmation pending; no full-route or physical GPU/timing claim.','Status alignment, signed-SP formatting and Stage 6 compression remain absent.'],
        'hardware_result':'pending','hardware_root_cause_confirmed':False,'public_release':False,'upgrade_patch':False}


def check(exe,report,*,strict_alignment=False):
    from build_location_header_fix import check_candidate,START,END
    from build_map_font_patch import member
    from build_hardware_status_bypass import check as constructors
    from check_native_text_components import verify
    base=ROOT/'work/output'/PRIOR
    old=(base/'1ST_READ.BIN').read_bytes()
    assert exe[:START]==old[:START] and exe[END:]==old[END:]
    names=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    paper=(base/'text/D_PAPER.en.dec.bin').read_bytes()
    banks=member((base/'WIN00.AFS').read_bytes(),0)
    assert len(banks)==198144 and not any(banks[0x200:99072])
    proof={'version':VERSION,'executable_sha256':digest(exe)}
    proof['names_PRS_instructions']=verify(exe,(base/'text/D_NAMES.BIN').read_bytes(),names,65536)
    proof['headers']=check_candidate(exe,old,names,paper,banks,report,modes=(1,),strict_alignment=strict_alignment)
    proof['constructors']=dict(constructors(exe),version=VERSION)
    proof['scope']='Actual current-executable location widths, unchanged other-name-group measurements, header geometry and original constructors, using Native bank only. Bounded font/GPU endpoints; no live emulator or hardware claim. Every byte outside the measurement routine matches passing 0.7.45.'
    return proof


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe,report=compose();proof=check(exe,report)
    print('PASS: Native location widths/geometry, other-name measurements and constructors; 260-byte split verified.',flush=True)
    root=ROOT/'work/output';archive=(root/PRIOR/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(read(root/PRIOR/'font-mode-details.json'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in p[3] if p[3][n]!=p[2][n]]==['1ST_READ.BIN']
    p[7].update(kind=report['kind'],component_manifest_name='hardware-header-split-component.json',proof_scope=proof['scope'],
        current_native_evidence={'header_split':'hardware-header-split-native-test.json'},current_live_evidence={},
        inherited_proof_note='Historical evidence retains its tested identity; current routine tests do not establish hardware compatibility.',
        readme_component_text=report['scope']+'\n',pending=report['limits'])
    write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=root/VERSION
    for name,obj in [('hardware-header-split-details.json',report),('hardware-header-split-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,obj)
    m=read(out/'font4x-patch.json');m.update(version=VERSION,previous_build=PRIOR,status='Location-header half-split; hardware pending',current_payload_identities=p[7]['files'],hardware_header_split=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    m['font_modes']={k:v for k,v in mode.items() if k not in ('labels','metrics','archive_packing')}
    m['hardware_consolidation']['current_build_exception']='0.7.45 plus location measurement only; see hardware_header_split.'
    save(out/'font4x-patch.json',m);save(ROOT/'docs/hardware-header-split.json',dict(report,native_validation=proof))
    return report


def audit():
    exe,report=compose();root=ROOT/'work/output';folder=root/f'dcp-{VERSION}-diagnostic'
    evidence=ROOT/'docs/hardware-0746-follow-up.json'
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
    report.update(native_validation=read(root/VERSION/'hardware-header-split-native-test.json'),all_140_game_files_and_boot_checked=True,
        disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    if follow_up:report['DCP']['hardware_result']=follow_up['status']
    save(ROOT/'docs/hardware-header-split.json',report)
    path=ROOT/'docs/hardware-chapter-transition.json';d=read(path)
    d['header_split_candidate']={'version':VERSION,'documentation':'docs/hardware-header-split.json','DCP':report['DCP']['path'],'status':'Original-input DCP verified; hardware pending','public_release':False,'upgrade_patch':False}
    if follow_up:d['header_split_candidate'].update(status=follow_up['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    d['next_compatibility_candidate']=d['header_split_candidate'];d['last_updated']=max(d.get('last_updated',''),'2026-11-16',follow_up['date'] if follow_up else '');save(path,d)
    path=ROOT/'docs/hardware-entry-hang-results.json';d=read(path)
    d['interpretation'].update(new_build_created='0.7.46: 260-byte location measurement restored on passing 0.7.45; remaining 248 bytes and all assets unchanged',working_baseline_next_test='Compare cold-boot New Game and mission dialogue against 0.7.45; inspect location banners such as Hallway, Office and Summoning Facility. Use matched outcomes to isolate location measurement versus remaining 248 bytes/interactions.')
    if follow_up:d['interpretation'].update(latest_report=VERSION+': '+follow_up['status'],header_split_result=follow_up['interpretation'],working_baseline_next_test=follow_up['next_test'])
    d['last_updated']=max(d.get('last_updated',''),'2026-11-16',follow_up['date'] if follow_up else '');save(path,d)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');p.add_argument('--audit-package',action='store_true');a=p.parse_args()
    if a.write:r=audit() if a.audit_package else build()
    else:
        exe,r=compose()
        if a.check:r['native_validation']=check(exe,r)
    print(json.dumps(r,indent=2))
