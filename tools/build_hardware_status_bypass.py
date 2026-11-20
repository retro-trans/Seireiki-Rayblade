"""0.7.43: bypass only the shared status-panel constructor hook in 0.7.42."""
import argparse
import copy
import json
import struct
from build_bitmap_font import ROOT,digest
from build_hardware_asset_split import read,save

VERSION,PRIOR='0.7.43','0.7.42'
POINTER=0x8b1d4
SOURCE_SHA='ce66d2b4ea9a6d8a6d50913ee6eebe42e740d9c58439b0540e59b1a707c6ac94'
ORIGINAL=0x8c07d978


def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    baseline=(ROOT/'work/output/0.7.40/1ST_READ.BIN').read_bytes()
    assert digest(old)==SOURCE_SHA
    assert struct.unpack_from('<I',old,POINTER)[0]==0x8c018d00
    assert struct.unpack_from('<I',baseline,POINTER)[0]==ORIGINAL
    exe=bytearray(old);struct.pack_into('<I',exe,POINTER,ORIGINAL)
    changed=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]
    assert changed==[POINTER,POINTER+1,POINTER+2]
    return bytes(exe),{'version':VERSION,'date':'2026-11-13','source_build':PRIOR,
        'kind':'Shared status-constructor bypass; single-pointer diagnostic',
        'source_executable_sha256':SOURCE_SHA,'executable_sha256':digest(exe),'changed_executable_bytes':3,
        'pointer_file_offset':hex(POINTER),'before':'0x8c018d00','after':hex(ORIGINAL),
        'reason':'0.7.42 still black-screens during mission dialogue and New Game. The shared constructor dispatch still enters the restored status gate even for non-status dialogue contexts.',
        'change':'Dispatch directly to the original constructor as in working 0.7.40. Leave unused helper bodies unchanged to isolate the call target.',
        'retained':'Every asset and all other code exact 0.7.42: UI text, headers, room/map assets, grid, targeting, clipping, selectors, Native font, memory repairs, loading and movies.',
        'disabled':['Trust/Skills vertical marker-alignment adjustment (two logical pixels)',
                    'Runtime text compression remains disabled exactly as in 0.7.42'],
        'on_pass':'A matched 0.7.42 fail / 0.7.43 pass implicates invocation of the status gate/wrapper or its interaction. It does not identify a faulty instruction or explain every historical freeze.',
        'on_fail':'The remaining restored code/assets are sufficient to reproduce the failure without either status hook or text compression; split remaining UI/header versus battle/asset changes against 0.7.40.',
        'limits':['Diagnostic only; hardware confirmation pending.',
                  'Trust/Skills vertical marker alignment may be slightly off; Skills horizontal indentation and all wording remain.',
                  'Stage 6 missing/white text can return because compression is still disabled.',
                  '0.7.42 failure proves compression removal alone insufficient, not that compression is harmless.'],
        'evidence':'docs/hardware-0742-follow-up.json','hardware_result':'pending','hardware_root_cause_confirmed':False,
        'public_release':False,'upgrade_patch':False}


def check(exe):
    from test_library_layout import fresh,BASE,STOP
    from build_map_font_patch import member
    baseline=(ROOT/'work/output/0.7.40/1ST_READ.BIN').read_bytes()
    font=member((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes(),0)
    cases=[];steps=0
    for script in (0xeee6,0xef01,0xef15,0xef29,0xe70b,0xfdbf,0xf634,0xf7ae):
        results=[]
        for image in (baseline,exe):
            c=fresh(image,font);c.write(0x8c1dbe24,BASE+script+1,4)
            saved=c.reg[8:];pr=c.pr;c.pc=struct.unpack_from('<I',image,POINTER)[0]
            assert c.pc==ORIGINAL
            for n in range(600000):
                if c.pc==STOP:break
                assert not 0x8c018d00<=c.pc<0x8c019000
                assert not 0x8c07bad0<=c.pc<0x8c07bb7c
                c.pc=c.execute(c.pc)
            else:raise AssertionError('Constructor did not return')
            steps+=n;assert c.reg[8:]==saved and c.pr==pr
            results.append((c.reg[0],bytes(c.regions[1][1]),c.reg[8:],c.pr))
        assert results[0]==results[1],hex(script)
        cases.append({'script':hex(script),'return_and_VM_context_memory_exact_0_7_40':True,'status_helpers_entered':False})
    return {'version':VERSION,'executable_sha256':digest(exe),'constructor_cases':cases,'SH4_instructions':steps,
        'scope':'Actual constructor selected through the candidate dispatch pointer, compared against 0.7.40. Status gate/wrapper forbidden; VM/context memory and return ABI exact. Heap/graphics endpoints are bounded fixtures, not a live GPU/hardware test.'}


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe,report=compose();proof=check(exe)
    print('PASS: eight constructors match 0.7.40, status hook never entered; only three pointer bytes change.',flush=True)
    base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(read(base/'font-mode-details.json'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in p[3] if p[3][n]!=p[2][n]]==['1ST_READ.BIN']
    p[7].update(kind=report['kind'],component_manifest_name='hardware-status-bypass-component.json',proof_scope=proof['scope'],
        current_native_evidence={'constructor':'hardware-status-bypass-native-test.json'},current_live_evidence={},
        inherited_proof_note='All historical evidence retains its original tested identity. Status alignment and compression are disabled; no live hardware pass claimed.',
        readme_component_text='Only bypass the status constructor hook from 0.7.42. All other code/assets unchanged. Hardware test pending.\n',pending=report['limits'])
    write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=ROOT/'work/output'/VERSION
    for name,obj in [('hardware-status-bypass-details.json',report),('hardware-status-bypass-native-test.json',proof),
                     ('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,obj)
    m=read(out/'font4x-patch.json');m.update(version=VERSION,previous_build=PRIOR,status='Status-constructor bypass; hardware pending',
        current_payload_identities=p[7]['files'],hardware_status_bypass=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    m['font_modes']={k:v for k,v in mode.items() if k not in ('labels','metrics','archive_packing')}
    m['hardware_consolidation']['current_build_exception']='0.7.43 disables status vertical alignment and runtime text compression; see hardware_status_bypass.'
    save(out/'font4x-patch.json',m)
    save(ROOT/'docs/hardware-status-bypass.json',dict(report,native_validation=proof))
    return report


def audit():
    exe,report=compose();root=ROOT/'work/output';folder=root/f'dcp-{VERSION}-diagnostic'
    evidence=ROOT/'docs/hardware-0743-follow-up.json'
    if evidence.exists():report.update(hardware_result=read(evidence)['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    target=read(folder/'target-tree.json');old=read(root/f'dcp-{PRIOR}-diagnostic/target-tree.json')
    assert len(target['files'])==141 and set(target['files'])==set(old['files'])
    assert [n for n in target['files'] if target['files'][n]!=old['files'][n]]==['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256']==digest(exe)
    bundle,applied=read(folder/'bundle-validation.json'),read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes())==bundle['sha256']
    assert applied['release_metadata_verified'] and applied['audio_tracks_preserved']
    assert applied['verified_game_tree_sha256']==bundle['game_tree_sha256']
    assert applied['bootsector_invariant_sha256']==bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag']=='1' and not bundle['public_release']
    report.update(native_validation=read(root/VERSION/'hardware-status-bypass-native-test.json'),all_140_game_files_and_boot_checked=True,
        disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    save(ROOT/'docs/hardware-status-bypass.json',report)
    path=ROOT/'docs/hardware-chapter-transition.json';d=read(path)
    d['status_bypass_candidate']={'version':VERSION,'documentation':'docs/hardware-status-bypass.json','DCP':report['DCP']['path'],
        'status':report['hardware_result'],'public_release':False,'upgrade_patch':False}
    d['next_compatibility_candidate']=d.get('code_asset_split_candidate',d['status_bypass_candidate']);d['last_updated']=max(d.get('last_updated',''),'2026-11-13');save(path,d)
    if d.get('code_asset_split_candidate'):return report
    path=ROOT/'docs/hardware-entry-hang-results.json';d=read(path)
    d['interpretation'].update(new_build_created='0.7.43: only the shared constructor pointer restored from working 0.7.40; all other 0.7.42 code/assets exact',
        working_baseline_next_test='Compare 0.7.43 with failed 0.7.42 at the same cold-boot New Game and mission dialogues. 0.7.40 remains the reported working fallback.')
    d['last_updated']='2026-11-13';save(path,d)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--audit-package',action='store_true');a=p.parse_args()
    r=(audit() if a.audit_package else build()) if a.write else compose()[1]
    print(json.dumps(r,indent=2),flush=True)
