"""0.7.42: isolate runtime text compression from failed combined 0.7.41.

Restore only the seven codec/allocation/admission regions from passing 0.7.40.
All other code and every asset remain exact 0.7.41. Original-input DCP only.
"""
import argparse
import copy
import json
import struct
from build_bitmap_font import ROOT,digest
from build_hardware_asset_split import read,save

VERSION,PRIOR,BASELINE='0.7.42','0.7.41','0.7.40'
SOURCE_SHA='1632f331219b96ffa982b4a647cd29987060847fc5042800debafaadf23b5b84'
BASE_SHA='1426cd32cbc942bed643ad6f5cd3e8e0fdcd0b1370867eb5599dc73e6a3a4d90'


def compose():
    root=ROOT/'work/output'
    old=(root/PRIOR/'1ST_READ.BIN').read_bytes();base=(root/BASELINE/'1ST_READ.BIN').read_bytes()
    assert digest(old)==SOURCE_SHA and digest(base)==BASE_SHA
    mode=read(root/PRIOR/'font-mode-details.json')
    stage=read(root/'0.7.22/stage-six-text-component.json')
    final_labels=read(root/'0.7.23/font-mode-details.json')['labels']
    old_hook=final_labels['a_malloc']-0x8c010000
    actual_hook=mode['labels']['a_malloc']-0x8c010000
    exe=bytearray(old);spans=[];allowed=set()
    for row in stage['edits']:
        p,n=int(row['file_offset'],16),row['bytes']
        if p==old_hook:p=actual_hook
        assert old[p:p+n]!=base[p:p+n]
        assert not allowed.intersection(range(p,p+n))
        exe[p:p+n]=base[p:p+n];allowed.update(range(p,p+n))
        spans.append({'file_offset':hex(p),'bytes':n,'restored_sha256':digest(base[p:p+n])})
    changed=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]
    assert len(changed)==705 and set(changed)<=allowed
    assert len(exe)==len(old) and all(exe[i]==old[i] for i in range(len(old)) if i not in allowed)
    assert exe[0x8d00:0x8d60]==old[0x8d00:0x8d60] # New status-only gate survives.
    assert exe[0x6bbac:0x6bbe0]==old[0x6bbac:0x6bbe0] # Adjacent clip helper survives.
    assert exe[actual_hook:actual_hook+4]==bytes.fromhex('e36400e5')
    for p in (0xb8f60,0xe21e0):assert struct.unpack_from('<I',exe,p)[0]==0x8c0e1c4c
    report={'version':VERSION,'date':'2026-11-12','source_build':PRIOR,'upload_baseline':BASELINE,
        'kind':'Controlled runtime text-compression removal from failed combined build',
        'source_executable_sha256':SOURCE_SHA,'executable_sha256':digest(exe),
        'changed_executable_bytes':len(changed),'reverted_spans':spans,
        'retained':'All 0.7.41 assets, translation/UI changes, status-only routing, grid/target/line/clip/selector fixes and all working 0.7.40 graphics, font, loading and movie repairs.',
        'disabled':'Runtime generated-text VQ encoder, extended CPU allocation, encoded upload selection and rectangular-VQ SDK admission; all seven regions restored together.',
        'font':'Native Skies 1x only; unchanged font resource, no HD or selector',
        'hardware_result':'pending','hardware_root_cause_confirmed':False,'public_release':False,'upgrade_patch':False,
        'evidence':'docs/hardware-0741-follow-up.json',
        'on_pass':'If the same cold-boot/New Game/mission dialogue paths now pass, the removed compression group or its interaction is implicated on this combined baseline. Repair that group before claiming feature parity.',
        'on_fail':'The remaining 0.7.41 additions or their interactions are still sufficient to fail; return to 0.7.40 and split those remaining changes. A failed test does not prove compression harmless.',
        'limits':['This is a diagnostic, not a confirmed hardware fix.',
                  'Stage 6 missing/white text may return because its text-memory repair is disabled.',
                  'Earlier 0.7.24 also disabled compression on a different baseline that retained other failing changes; its failure does not settle this comparison.',
                  'Test matching New Game and mission dialogue checkpoints from a cold boot using normal VMU saves.']}
    return bytes(exe),report


def check(exe,report):
    from test_stage6_text import fresh,PTR
    from test_native_movie_font import run,STOP
    base=(ROOT/'work/output'/BASELINE/'1ST_READ.BIN').read_bytes()
    labels=read(ROOT/'work/output'/PRIOR/'font-mode-details.json')['labels']
    steps=0;cases=[]
    forbidden=((0x8c018d60,0x8c018fe4),(0x8c07bb7c,0x8c07bba0))
    def execute(c,start,stop=STOP):
        c.pc=start
        for n in range(100000):
            if c.pc==stop:return n
            assert not any(lo<=c.pc<hi for lo,hi in forbidden),hex(c.pc)
            c.pc=c.execute(c.pc)
        raise AssertionError('Uncompressed path did not return')
    for w,h in ((16,16),(64,32),(128,128),(256,64),(256,128),(512,64),(512,256),(1024,128)):
        results=[]
        for image in (base,exe):
            c=fresh(image);ctx=0x8cf60000;c.reg[8]=ctx
            c.write(ctx+10,w,2);c.write(ctx+12,h,2);saved=c.reg[8:];sp=c.reg[15]
            steps+=execute(c,labels['allocate'])
            assert c.reg[0]==PTR and c.reg[8:]==saved and c.reg[15]==sp
            size=c.read(PTR+20,4);assert c.heap==[(size+32,0)]
            header=bytes(c.regions[0][1][PTR&0xffffff:(PTR&0xffffff)+32])
            c.reg[3]=PTR;c.write(0x8c171704,PTR,4);c.pr=STOP
            registers=c.reg[4:];steps+=execute(c,0x8c032d1a,0x8c032d68)
            assert c.reg[4:]==registers and c.reg[15]==sp and c.pr==STOP
            assert c.read(0x8c171704,4)==PTR and c.read(0x8c1716f8,4)==(size+32+2047)//2048
            assert not c.flushes and header==bytes(c.regions[0][1][PTR&0xffffff:(PTR&0xffffff)+32])
            results.append((c.heap,header,c.read(0x8c1716f8,4)))
        assert results[0]==results[1]
        cases.append({'logical':[w,h],'allocation_bytes':results[1][0][0][0],'upload_sectors':results[1][2],'source_pointer':'original editable surface','matches_0_7_40':True})
    # Tests of unaffected features retain their actual 0.7.41 identities.
    # Equality outside the seven restored spans is exhaustive in compose().
    return {'version':VERSION,'executable_sha256':digest(exe),'allocation_upload_cases':cases,'SH4_instructions':steps,
        'removed_encoder_helper_and_validator':'Never executed in these cases; both SDK entry literals restored',
        'other_feature_evidence':'0.7.41 native tests are historical; corresponding feature bytes and assets unchanged, not a new live pass.',
        'scope':'Actual retained allocator and restored upload worker compared with 0.7.40. Heap endpoint is bounded; GPU/DMA timing and physical dialogue transitions remain untested.'}


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe,report=compose();proof=check(exe,report)
    print('PASS: eight actual allocation/upload cases match 0.7.40; only seven compression regions change.',flush=True)
    base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(read(base/'font-mode-details.json'))
    mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe),runtime_text_compression=False)
    p,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in p[3] if p[3][n]!=p[2][n]]==['1ST_READ.BIN']
    p[7].update(kind=report['kind'],component_manifest_name='hardware-text-upload-split-component.json',proof_scope=proof['scope'],
        current_native_evidence={'uncompressed_text':'hardware-text-upload-split-native-test.json'},current_live_evidence={},
        inherited_proof_note='Earlier proofs retain their original build identities. Codec disabled; no current Stage 6 fix or hardware pass claimed.',
        readme_component_text='Only text compression is removed from 0.7.41. All other fixes/assets stay. Stage 6 missing text can return.\n',pending=report['limits'])
    write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('hardware-text-upload-split-details.json',report),('hardware-text-upload-split-native-test.json',proof),
                     ('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,obj)
    m=read(out/'font4x-patch.json');m.update(version=VERSION,previous_build=PRIOR,status='Text-compression isolation; hardware pending',
        current_payload_identities=p[7]['files'],hardware_text_upload_split=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    m['font_modes']={k:v for k,v in mode.items() if k not in ('labels','metrics','archive_packing')}
    m['hardware_consolidation']['historical_build']=PRIOR
    m['hardware_consolidation']['current_build_exception']='0.7.42 disables runtime text compression; see hardware_text_upload_split.'
    save(out/'font4x-patch.json',m)
    save(ROOT/'docs/hardware-text-upload-split.json',dict(report,native_validation=proof))
    return report


def audit():
    exe,report=compose();root=ROOT/'work/output';folder=root/f'dcp-{VERSION}-diagnostic'
    evidence=ROOT/'docs/hardware-0742-follow-up.json'
    if evidence.exists():report.update(hardware_result=read(evidence)['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    existing=read(ROOT/'docs/hardware-text-upload-split.json')
    if 'dependency_review' in existing:report['dependency_review']=existing['dependency_review']
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
    report.update(native_validation=read(root/VERSION/'hardware-text-upload-split-native-test.json'),all_140_game_files_and_boot_checked=True,
        disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    save(ROOT/'docs/hardware-text-upload-split.json',report)
    path=ROOT/'docs/hardware-chapter-transition.json';d=read(path)
    d['text_upload_split_candidate']={'version':VERSION,'documentation':'docs/hardware-text-upload-split.json','DCP':report['DCP']['path'],
        'status':report['hardware_result'],'public_release':False,'upgrade_patch':False}
    d['next_compatibility_candidate']=d.get('status_bypass_candidate',d['text_upload_split_candidate'])
    d['last_updated']=max(d.get('last_updated',''),'2026-11-12');save(path,d)
    if d.get('status_bypass_candidate'):return report
    path=ROOT/'docs/hardware-entry-hang-results.json';d=read(path)
    d['interpretation'].update(new_build_created='0.7.42: only the seven text-compression regions restored from working 0.7.40; all other 0.7.41 code/assets exact',
        working_baseline_next_test='Compare 0.7.42 against failed 0.7.41 at matching New Game and mission-dialogue checkpoints; 0.7.40 remains the reported working fallback.')
    save(path,d)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--audit-package',action='store_true');a=p.parse_args()
    r=(audit() if a.audit_package else build()) if a.write else compose()[1]
    print(json.dumps(r,indent=2),flush=True)
