"""Lossless VQ staging for Native text uploads; default dry run."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from sh4_asm import Assembler
from build_font4x_patch import mem,prologue,epilogue
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.22','0.7.21'
ENTRY=0x8c018d60
ALLOC=0x8c07bb7c
VALIDATE=0x8c018f80

def encoder():
    a=Assembler(ENTRY)
    def get(off,reg):a.emit(0x50f0|(reg<<8)|(off//4))
    def put(off,reg):a.emit(0x1f00|(reg<<4)|(off//4))
    prologue(a,locals=32);a.rr('mov',4,8)
    mem(a,'l',8,20,1);put(28,1)
    a.lit(4096,2);a.rr('cmp/hs',2,1);a.branch('bt','size_ok');a.branch('bra','original');a.emit(0x0009);a.label('size_ok')
    mem(a,'l',8,24,1);a.lit(0x902,2);a.rr('cmp/eq',2,1);a.branch('bt','format_ok');a.branch('bra','original');a.emit(0x0009);a.label('format_ok')
    a.imm(0,7)
    for off in (28,30):
        mem(a,'w',8,off,1);a.rr('extu.w',1,1);a.rr('mov',1,2);a.addi(-1,2);a.rr('and',1,2);a.rr('or',2,7)
        a.addi(-8,1);a.lit(1017,2);a.rr('cmp/hs',2,1);a.unary('movt',2);a.rr('or',2,7)
    mem(a,'w',8,28,1);a.rr('extu.w',1,1);mem(a,'w',8,30,2);a.rr('extu.w',2,2)
    a.rr('mul.l',2,1);a.unary('sts.macl',1);a.unary('shll',1);get(28,2);a.rr('cmp/eq',2,1);a.unary('movt',1);a.addi(-1,1);a.rr('or',1,7)
    a.rr('tst',7,7);a.branch('bt','dimensions_ok');a.branch('bra','original');a.emit(0x0009);a.label('dimensions_ok')
    get(28,9);a.rr('add',8,9);a.addi(32,9)
    a.rr('mov',8,1);a.rr('mov',9,2);a.imm(8,3)
    a.label('header');a.emit(0x6016);a.store('l',0,2);a.addi(4,2);a.unary('dt',3);a.branch('bf','header')
    a.rr('mov',9,10);a.addi(32,10);a.rr('mov',10,4);a.imm(0,5);a.lit(2048,6)
    a.lit(0x8c093e80,3);a.emit(0x430b);a.emit(0x0009)
    a.rr('mov',10,1);a.lit(2048,2);a.rr('add',2,1);put(24,1)
    mem(a,'w',8,28,1);a.rr('extu.w',1,1);a.rr('mov',1,2);a.unary('shll',2);put(0,2)
    a.unary('shlr',1);put(4,1)
    mem(a,'w',8,30,2);a.rr('extu.w',2,2);a.unary('shlr',2);put(8,2)
    a.rr('cmp/hs',2,1);a.branch('bf','side');a.rr('mov',2,1)
    a.label('side');a.rr('mov',1,5);a.imm(0,3);a.imm(2,4)
    a.label('mask');a.unary('shlr',1);a.rr('tst',1,1);a.branch('bt','mask_done')
    a.rr('or',4,3);a.unary('shll2',4);a.branch('bra','mask');a.emit(0x0009)
    a.label('mask_done');a.rr('mov',3,6);a.unary('shlr',6)
    a.rr('mul.l',5,5);a.unary('sts.macl',5);a.addi(-1,5)
    get(28,2);a.unary('shlr2',2);a.unary('shlr',2);a.addi(-1,2);a.emit(0x225a)
    get(4,1);get(8,4);a.rr('cmp/hs',4,1);a.branch('bf','y_tiles');a.rr('or',2,3)
    a.branch('bra','masks_saved');a.emit(0x0009)
    a.label('y_tiles');a.rr('or',2,6)
    a.label('masks_saved');put(16,3);put(20,6)
    a.imm(1,11);a.rr('mov',8,12);a.addi(32,12);a.imm(0,14)
    a.label('row');get(4,0);put(12,0);a.imm(0,13)
    a.label('block');a.load('l',12,4);get(0,1);a.rr('add',12,1);a.load('l',1,5);a.addi(4,12)
    a.rr('mov',4,0);a.rr('or',5,0);a.rr('tst',0,0);a.branch('bt','index')
    a.rr('mov',10,1);a.addi(8,1);a.imm(1,2)
    a.label('find');a.rr('cmp/eq',11,2);a.branch('bt','new')
    a.load('l',1,3);a.rr('cmp/eq',4,3);a.branch('bf','next')
    a.emit(0x5311);a.rr('cmp/eq',5,3);a.branch('bt','found')
    a.label('next');a.addi(8,1);a.addi(1,2);a.branch('bra','find');a.emit(0x0009)
    a.label('new');a.lit(256,3);a.rr('cmp/eq',3,11);a.branch('bt','original')
    a.store('l',4,1);a.emit(0x1151);a.addi(1,11)
    a.label('found');a.rr('mov',2,0)
    a.label('index');a.rr('mov',13,1);a.rr('or',14,1);get(24,2);a.rr('add',2,1);a.store('b',0,1)
    get(16,1);a.rr('sub',1,13);a.rr('and',1,13)
    get(12,0);a.addi(-1,0);put(12,0);a.rr('tst',0,0);a.branch('bf','block')
    get(0,1);a.rr('add',1,12);get(20,1);a.rr('sub',1,14);a.rr('and',1,14)
    get(8,0);a.addi(-1,0);put(8,0);a.rr('tst',0,0);a.branch('bf','row')
    # PVR VQ entries use column-major order within each 2x2 block.
    a.label('transpose');a.load('l',10,1);a.emit(0x52a1)
    a.rr('extu.w',1,0);a.rr('extu.w',2,3);a.unary('shll16',3);a.rr('or',3,0);a.store('l',0,10)
    a.unary('shlr16',1);a.unary('shlr16',2);a.unary('shll16',2);a.rr('or',2,1);a.emit(0x1a11)
    a.addi(8,10);a.unary('dt',11);a.branch('bf','transpose')
    a.lit(0x302,1);mem(a,'l',9,24,1,True)
    get(28,1);a.unary('shlr2',1);a.unary('shlr',1);a.lit(2048,2);a.rr('add',2,1);mem(a,'l',9,20,1,True)
    a.rr('mov',9,4);a.rr('mov',1,5);a.addi(32,5);a.lit(0x8c0a437a,3);a.emit(0x430b);a.emit(0x0009)
    a.rr('mov',9,0);a.branch('bra','return');a.emit(0x0009)
    a.label('original');a.rr('mov',8,0)
    a.label('return');epilogue(a,locals=32)
    raw=a.pool_and_finish();assert ENTRY+len(raw)<=VALIDATE, len(raw)
    return raw

def validation():
    # The SDK computes rectangular VQ sizes/control words, but returns error 4
    # for all non-square format-3 headers. Admit only otherwise-valid ARGB4444
    # VQ dimensions supported by the PVR; keep every other result unchanged.
    a=Assembler(VALIDATE);prologue(a,regs=range(8,11))
    a.rr('mov',7,8);a.rr('mov',5,9);a.rr('mov',6,10)
    a.lit(0x8c0e1c4c,3);a.emit(0x430b);a.emit(0x0009)
    a.emit(0x8804);a.branch('bf','return');a.lit(0x302,1);a.rr('cmp/eq',8,1);a.branch('bf','return')
    for reg in (9,10):
        a.imm(8,1);a.rr('cmp/hs',1,reg);a.branch('bf','return')
        a.lit(1025,1);a.rr('cmp/hs',1,reg);a.branch('bt','return')
        a.rr('mov',reg,2);a.addi(-1,2);a.rr('and',reg,2);a.rr('tst',2,2);a.branch('bf','return')
    a.imm(0,0);a.label('return');epilogue(a,regs=range(8,11))
    raw=a.pool_and_finish();assert VALIDATE+len(raw)<=0x8c019000
    return raw

def allocation(labels):
    a=Assembler(ALLOC);a.rr('mov',14,4);a.rr('mov',14,0);a.addi(-32,0)
    a.unary('shlr2',0);a.unary('shlr',0);a.lit(2080+2047,1);a.rr('add',1,0)
    a.lit(0xfffff800,1);a.rr('and',1,0);a.rr('add',0,4);a.imm(0,5)
    a.labels['resume']=labels['a_malloc']+4;a.branch('bra','resume');a.emit(0x0009)
    return a.pool_and_finish()

def upload():
    base=0x8c032d1a;a=Assembler(base)
    for reg in range(4,8):a.push(reg)
    a.emit(0x4f22);a.rr('mov',3,4);a.lit(ENTRY,0);a.emit(0x400b);a.emit(0x0009)
    a.lit(0x8c171704,1);a.store('l',0,1);a.rr('mov',0,4)
    a.emit(0x5545);a.rr('mov',5,3);a.lit(2079,1);a.rr('add',1,3)
    a.imm(-11,1);a.rr('shld',1,3);a.lit(0x8c1716f8,1);a.store('l',3,1)
    a.emit(0x4f26)
    for reg in reversed(range(4,8)):a.pop(reg)
    a.lit(0x8c032d68,0);a.emit(0x402b);a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=0x4e,len(raw)
    return raw+bytes.fromhex('0900')*((0x4e-len(raw))//2)

@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(old)
    labels=json.loads((base/'font-mode-details.json').read_text('utf-8'))['labels']
    enc=encoder();malloc=allocation(labels);up=upload();guard=validation();hook=labels['a_malloc']-0x8c010000
    assert not any(old[0x8d60:0x8d60+len(enc)])
    assert old[0x6bb7c:0x6bb7c+len(malloc)]==bytes.fromhex('0900')*(len(malloc)//2)
    assert old[hook:hook+4]==bytes.fromhex('e36400e5')
    a=Assembler(labels['a_malloc']);a.labels['helper']=ALLOC;a.branch('bra','helper');a.emit(0x0009)
    guard_off=VALIDATE-0x8c010000
    assert not any(old[guard_off:guard_off+len(guard)])
    for off in (0xb8f60,0xe21e0):assert struct.unpack_from('<I',old,off)[0]==0x8c0e1c4c
    edits=[(0x8d60,enc),(guard_off,guard),(0x6bb7c,malloc),(0x22d1a,up),(hook,a.pool_and_finish()[:4]),
           (0xb8f60,struct.pack('<I',VALIDATE)),(0xe21e0,struct.pack('<I',VALIDATE))]
    for i,(p,raw) in enumerate(edits):
        assert all(p+len(raw)<=q or q+len(other)<=p for q,other in edits[i+1:])
    for p,raw in edits:exe[p:p+len(raw)]=raw
    assert len(exe)==len(old)
    changed=[i for i,(x,y) in enumerate(zip(old,exe)) if x!=y]
    assert all(any(p<=i<p+len(raw) for p,raw in edits) for i in changed)
    return bytes(exe),{'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),'source_executable_sha256':digest(old),
        'encoder':hex(ENTRY),'encoder_bytes':len(enc),'allocation_helper':hex(ALLOC),'allocation_helper_bytes':len(malloc),
        'rectangular_VQ_admission':hex(VALIDATE),'admission_bytes':len(guard),
        'edits':[{'file_offset':hex(p),'bytes':len(raw)} for p,raw in edits],'changed_executable_bytes':len(changed),
        'policy':'Losslessly encode generated Native text into standard PVR VQ only when every 2x2 block fits a 256-entry exact dictionary. Otherwise upload the unchanged uncompressed source.',
        'pixels':'No quantization, resampling, alpha/color change, font change or geometry change. Original RGB plane remains editable for append text.',
        'staging':'Extra CPU allocation after the original RGB plane, rounded to 2048 bytes. Lives and is freed with the original surface; no transient freed DMA source.',
        'release':False,'validation':'candidate; native and Stage 6 replay required'}

def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local lossless Native text texture compression',component_manifest_name='stage-six-text-component.json',
        current_native_evidence={'stage6_text':'stage6-text-native-test.json'},current_live_evidence={'stage6_text':'stage6-text-live-test.json'},
        readme_component_text='Losslessly compresses Native text uploads to reduce video memory use. Font pixels and alpha remain exact.\n',
        proof_scope='Exact native encoder/decoded texel equality, allocator/upload/append and supplied Stage 6 VMU replay.',
        pending=['Stage 6 visual/menu validation','Physical Dreamcast and complete-route review'])
    return p,mode

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');ap.add_argument('--finish',action='store_true');a=ap.parse_args()
    exe,r=compose();print(json.dumps(r,indent=2))
    if not a.write:print('DRY RUN: no files written');return
    from test_stage6_text import check
    proof=check()
    if not a.disc:print(json.dumps(proof,indent=2));return
    p,mode=plan()
    if not a.finish:write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()})
    out=ROOT/'work/output'/VERSION
    report=json.loads((out/'english-disc-report.json').read_text('utf-8'))
    assert report['validation']['changed_sector_EDC_ECC']=='pass' and (out/'1ST_READ.BIN').read_bytes()==exe
    for name,row in report['files'].items():
        assert digest(p[3][name])==row['sha256']
        if (out/name).exists():assert digest((out/name).read_bytes())==row['sha256']
    report['component_manifest_name']='stage-six-text-component.json'
    (out/'english-disc-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    for name,obj in [('stage-six-text-component.json',r),('stage6-text-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:
        (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=report['files'])
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe);(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
    (out/'READ-ME.txt').write_text('Seireiki Rayblade English local 0.7.22\n\nOpen disc/Rayblade English Test 0.7.22.gdi.\nLossless Native text VQ reduces video memory use; original 1x glyph pixels and alpha remain exact.\nStage 6 replay and menu/save evidence is recorded separately. Physical Dreamcast and complete-route coverage remain pending.\nLocal build only; no GitHub release.\n','utf-8')

if __name__=='__main__':main()
