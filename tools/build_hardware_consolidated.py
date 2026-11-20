"""0.7.41: port final emulator fixes onto the working 0.7.40 font runtime.

No HD pixels/selector, upgrade patch or publication. This is deliberately not
the failed 0.7.35 executable: retain the earlier renderer and avoid invoking
the status adjustment wrapper from ordinary scenario constructors.
"""
import argparse
import copy
import json
import struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_hardware_asset_split import read,save
from build_map_font_patch import member
from sh4_asm import Assembler

VERSION,BASELINE,DONOR='0.7.41','0.7.40','0.7.23'
BASE_SHA='1426cd32cbc942bed643ad6f5cd3e8e0fdcd0b1370867eb5599dc73e6a3a4d90'
DONOR_SHA='6899e263653b1a29de45ee7bf04778e1ad240c40a99763511bd2da7ce9abbffe'
STATUS_GATE=0x8c018d00


def status_gate(*, entry=STATUS_GATE, capacity=0x60):
    # Constructor arguments come from the VM instruction, not R0/R1/R3.
    # Non-status callers reach the retail entry with PR/SP/nonvolatile regs
    # untouched and without the old wrapper's 116-byte frame.
    a=Assembler(entry)
    a.lit(0x8c1dbe24,1);a.load('l',1,1)
    for p in (0x8c01ef02,0x8c01ef2a):
        a.lit(p,0);a.rr('cmp/eq',0,1);a.branch('bt','status')
    a.lit(0x8c07d978,3);a.emit(0x432b);a.emit(0x0009)
    a.label('status');a.lit(0x8c07bad0,3);a.emit(0x432b);a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=capacity
    return raw+bytes.fromhex('0900')*((capacity-len(raw))//2)


@lru_cache(maxsize=1)
def compose():
    root=ROOT/'work/output'
    old=(root/BASELINE/'1ST_READ.BIN').read_bytes()
    donor=(root/DONOR/'1ST_READ.BIN').read_bytes()
    assert digest(old)==BASE_SHA and digest(donor)==DONOR_SHA
    exe=bytearray(old);edits=[]
    # Exact incremental feature edits, not a wholesale final-kernel restore.
    # Stage 6's allocator branch is regenerated for the preserved kernel.
    mode=copy.deepcopy(read(root/BASELINE/'font-mode-details.json'))
    final_labels=read(root/DONOR/'font-mode-details.json')['labels']
    retired_malloc=final_labels['a_malloc']-0x8c010000
    allowed=set()
    for before,after,feature in [('0.7.7','0.7.11','status, signed SP and measured location headers'),
                                 ('0.7.19','0.7.23','grid, target, lines, text memory, split clipping and selectors')]:
        a=(root/before/'1ST_READ.BIN').read_bytes();b=(root/after/'1ST_READ.BIN').read_bytes()
        delta=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y and not retired_malloc<=i<retired_malloc+4]
        assert not allowed.intersection(delta)
        for i in delta:
            assert exe[i]==a[i],(feature,hex(i),exe[i],a[i])
            exe[i]=b[i]
        allowed.update(delta);edits.append({'feature':feature,'before':before,'after':after,'bytes':len(delta)})
    from build_stage6_text_fix import allocation,ALLOC
    hook=mode['labels']['a_malloc']-0x8c010000
    assert old[hook:hook+4]==bytes.fromhex('e36400e5')
    a=Assembler(mode['labels']['a_malloc']);a.labels['helper']=ALLOC;a.branch('bra','helper');a.emit(0x0009)
    replacements=[(hook,a.pool_and_finish()[:4]),(ALLOC-0x8c010000,allocation(mode['labels'])),
                  (STATUS_GATE-0x8c010000,status_gate()),(0x8b1d4,struct.pack('<I',STATUS_GATE))]
    for p,raw in replacements:
        exe[p:p+len(raw)]=raw;allowed.update(range(p,p+len(raw)))
    # Reclamation of the unused map body must not touch the adjacent encoder.
    assert exe[0x8d60:0x9000]==donor[0x8d60:0x9000]
    assert exe[0x6b724:0x6b728]==struct.pack('<I',0x8c0ab970)
    from build_font4x_patch import START
    kernel_end=START+mode['kernel_bytes']
    assert [i for i in range(START,kernel_end) if exe[i]!=old[i]]==[i for i in range(hook,hook+4) if exe[i]!=old[i]]
    assert exe[0x684b0:0x684b4]==old[0x684b0:0x684b4]
    assert exe[0x6ab98:0x6abfa]==old[0x6ab98:0x6abfa]
    assert exe[0x22118:0x2211c]==old[0x22118:0x2211c]
    for lo,hi in [(0x10cb0,0x10cb4),(0x6b900,0x6b918),(0xc234e,0xc2356),(0xc24b4,0xc24b8),
                  (0x9c690,0x9c694),(0xac2e4,0xac3f4),(0x2a150,0x2a158),(0x6b800,0x6b840)]:
        assert exe[lo:hi]==old[lo:hi]
    changed=[i for i,(x,y) in enumerate(zip(old,exe)) if x!=y]
    assert set(changed)<=allowed and len(exe)==len(old)
    archive=(root/BASELINE/'WIN00.AFS').read_bytes()
    final_win=(root/DONOR/'WIN00.AFS').read_bytes()
    assert all(member(archive,i)==member(final_win,i) for i in range(1,90))
    assert member(archive,0)[99072:]==member(final_win,0)
    assert not any(member(archive,0)[0x200:99072])
    mode.update(version=VERSION,source_build=BASELINE,executable_sha256=digest(exe),archive_sha256=digest(archive))
    report={'version':VERSION,'date':'2026-11-12','runtime_baseline':BASELINE,'asset_donor':DONOR,
        'kind':'Consolidated compatibility candidate with all later user-visible emulator bug fixes',
        'executable_sha256':digest(exe),'source_executable_sha256':BASE_SHA,'asset_donor_executable_sha256':DONOR_SHA,
        'changed_executable_bytes_from_0_7_40':len(changed),'feature_delta_sources':edits,
        'retained':'0.7.40 rasterizer, initialization, cache flush, Native font resource, RGB565, original geometry reservation, compact atlases, loading and movie-edge/size fixes.',
        'restored':['Compact weapons/movie names, status marker alignment, full Trust help/popup aliases',
                    'Signed SP, compact notices, room tags and measured location banners',
                    'Movement grid, animation targeting and application lines',
                    'Lossless Stage 6 generated-text compression with allocation adapted to the retained renderer',
                    'Inclusive split-battle clipping and full-width selection bars'],
        'compatibility_changes':{'status_gate':hex(STATUS_GATE),'status_only_VM_contexts':['0x8c01ef02','0x8c01ef2a'],
            'other_contexts':'Tail-call the original constructor without an extra stack frame',
            'allocator_hook':hex(hook),'allocation_resume':hex(mode['labels']['a_malloc']+4),
            'shared_map_draw':'Original SDK draw, as in passing 0.7.40; no filename sniff/snap hook'},
        'asset_policy':'Every non-WIN asset exact final emulator 0.7.23. WIN exact 0.7.40; all 89 nonfont members already match 0.7.23, Native pixels exact with compatibility padding.',
        'font':'Original Skies Native 1x only; no HD pixels/bank or title selector',
        'hardware_result':'pending','hardware_root_cause_confirmed':False,
        'public_release':False,'upgrade_patch':False,
        'limits':['Combined 0.7.41 requires its own hardware test; 0.7.40 passing does not validate restored hooks.',
                  'No full-route pass or proof of the earlier freeze cause is claimed.',
                  'Fractional world-map label snapping remains bypassed for compatibility; translated lettering remains.',
                  'Existing incomplete translation/room-tag/save-label limitations are outside this consolidation.']}
    return bytes(exe),archive,mode,report


def check(exe,archive,mode,report):
    from test_hardware_consolidated import check_candidate
    return check_candidate(exe,archive,mode,report)


def build(proof_path=None):
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe,archive,mode,report=compose()
    proof=read(proof_path) if proof_path else check(exe,archive,mode,report)
    assert proof['version']==VERSION and proof['executable_sha256']==digest(exe) and proof['archive_sha256']==digest(archive)
    # Use the final asset donor for copying all translated components, while
    # replacing its executable and font archive with the compatibility port.
    p,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=DONOR,version=VERSION)
    assert set(n for n in p[3] if p[3][n]!=p[2][n])=={'1ST_READ.BIN','WIN00.AFS'}
    p[7].update(kind=report['kind'],component_manifest_name='hardware-consolidated-component.json',
        proof_scope=proof['scope'],current_native_evidence={'consolidated':'hardware-consolidated-native-test.json'},
        current_live_evidence={},inherited_proof_note='Historical proofs retain their original tested identities; no new live or hardware run claimed.',
        readme_component_text='Consolidated bug fixes on the 0.7.40 compatibility runtime. Original-input DCP only; hardware retest required.\n',pending=report['limits'])
    write_plan(p,VERSION,DONOR,{'1ST_READ.BIN':exe,'WIN00.AFS':archive})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('hardware-consolidated-details.json',report),('hardware-consolidated-native-test.json',proof),
                     ('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,obj)
    m=read(out/'font4x-patch.json');m.update(version=VERSION,previous_build=BASELINE,
        status='Combined local candidate; hardware pending',current_payload_identities=p[7]['files'],hardware_consolidation=report)
    for n in ('1ST_READ.BIN','WIN00.AFS'):m['files'][n]['target_sha256']=digest(p[3][n])
    m['font_modes']={k:v for k,v in mode.items() if k not in ('labels','metrics','archive_packing')}
    m['symbols']={k:hex(mode['labels'][k]) for k in ('raster','allocate','initialize','flush')}
    m['kernel_bytes_used']=mode['kernel_bytes']
    off,size=struct.unpack_from('<II',archive,8+52*8);m['library'].update(archive_member_offset=off,archive_member_bytes=size)
    save(out/'font4x-patch.json',m)
    library=read(out/'library-patch-report.json');library.update(archive_member_offset=off,archive_member_bytes=size);save(out/'library-patch-report.json',library)
    save(ROOT/'docs/hardware-consolidated-fixes.json',dict(report,native_validation=proof))
    return report


def audit():
    exe,archive,mode,report=compose()
    evidence=ROOT/'docs/hardware-0741-follow-up.json'
    if evidence.exists():report.update(hardware_result=read(evidence)['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    root=ROOT/'work/output';out=root/VERSION;folder=root/f'dcp-{VERSION}-diagnostic'
    target,baseline,donor=[read(root/f'{name}/target-tree.json') for name in
        (f'dcp-{VERSION}-diagnostic',f'dcp-{BASELINE}-diagnostic','dcp-0.7.23')]
    assert len(target['files'])==141 and set(target['files'])==set(baseline['files'])==set(donor['files'])
    assert {n for n in target['files'] if target['files'][n]!=donor['files'][n]}=={'1ST_READ.BIN','WIN00.AFS'}
    assert target['files']['1ST_READ.BIN']['sha256']==digest(exe)
    assert target['files']['WIN00.AFS']==baseline['files']['WIN00.AFS']
    assert (out/'1ST_READ.BIN').read_bytes()==exe and (out/'WIN00.AFS').read_bytes()==archive
    proof=read(out/'hardware-consolidated-native-test.json')
    assert proof['executable_sha256']==digest(exe) and proof['archive_sha256']==digest(archive)
    bundle,applied=read(folder/'bundle-validation.json'),read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes())==bundle['sha256']
    assert applied['release_metadata_verified'] and applied['audio_tracks_preserved']
    assert applied['verified_game_tree_sha256']==bundle['game_tree_sha256']
    assert applied['bootsector_invariant_sha256']==bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag']=='1' and not bundle['public_release']
    report.update(native_validation=proof,all_140_game_files_and_boot_checked=True,
        changed_game_files_from_0_7_40=[n for n in target['files'] if target['files'][n]!=baseline['files'][n]],
        disc_validation=read(out/'english-disc-report.json')['validation'],
        DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    save(ROOT/'docs/hardware-consolidated-fixes.json',report)
    path=ROOT/'docs/hardware-chapter-transition.json';current=read(path)
    current['consolidated_candidate']={'version':VERSION,'documentation':'docs/hardware-consolidated-fixes.json',
        'DCP':report['DCP']['path'],'runtime_baseline':BASELINE,
        'status':report['hardware_result'],'public_release':False,'upgrade_patch':False}
    current['next_compatibility_candidate']=current.get('status_bypass_candidate',current.get('text_upload_split_candidate',current['consolidated_candidate']))
    current['last_updated']=max(current.get('last_updated',''),'2026-11-12');save(path,current)
    if current.get('text_upload_split_candidate'):return report
    path=ROOT/'docs/hardware-entry-hang-results.json';current=read(path)
    current['interpretation'].update(new_build_created='0.7.41: consolidated later fixes on the 0.7.40 renderer, status-only gate and adapted text allocation; original-input DCP verified',
        working_baseline_next_test='0.7.40 reported working; independently retest New Game/Hallway, Clear 2/3 transitions, Office, grid/battles and Stage 6 on combined 0.7.41.')
    current['last_updated']='2026-11-12';save(path,current)
    return report


if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');p.add_argument('--proof-file',type=Path);p.add_argument('--audit-package',action='store_true');args=p.parse_args()
    if args.write:result=audit() if args.audit_package else build(args.proof_file)
    else:
        exe,archive,mode,result=compose()
        if args.check:result['native_validation']=check(exe,archive,mode,result)
    print(json.dumps(result,indent=2),flush=True)
