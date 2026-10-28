"""Convert animation-renderer primitives to 640x480 once. Dry first."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from sh4_asm import Assembler

VERSION,PRIOR='0.7.21','0.7.20'
ENTRY=0x8c07b9a0
RAW_SITES={0x8c0ab898:(24,(0x16a98,0x174b4)),0x8c0ab714:(16,(0x17ea8,0x18664))}
LINE_SITES=(0x18b84,0x18bec)


def raw_adapter(base,stride,callee):
    a=Assembler(base);a.push(8);a.emit(0x4f22);a.rr('mov',15,8)
    a.imm(stride,0);a.rr('mov',5,3);a.rr('mul.l',0,3);a.unary('sts.macl',3)
    a.rr('sub',3,15);a.unary('shlr2',3);a.rr('mov',4,1);a.rr('mov',15,2)
    a.rr('tst',3,3);a.branch('bt','scaled')
    a.label('copy');a.emit(0x6016);a.store('l',0,2);a.addi(4,2);a.unary('dt',3);a.branch('bf','copy')
    a.label('scaled');a.rr('mov',15,1);a.rr('mov',5,2);a.rr('tst',2,2);a.branch('bt','draw')
    a.label('points')
    for step in (4,stride-4):
        a.emit(0xf018);a.emit(0xf000);a.emit(0xf10a);a.addi(step,1)
    a.unary('dt',2);a.branch('bf','points')
    a.label('draw');a.rr('mov',15,4);a.lit(callee,3);a.emit(0x430b);a.emit(0x0009)
    a.rr('mov',8,15);a.emit(0x4f26);a.pop(8);a.emit(0x000b);a.emit(0x0009)
    # R6 (blend) and R7 (textured blend) remain original arguments.
    return a.pool_and_finish()


@lru_cache(maxsize=1)
def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();exe=bytearray(old);code=b'';adapters=[];edits=[]
    for callee,(stride,sites) in RAW_SITES.items():
        entry=ENTRY+len(code);chunk=raw_adapter(entry,stride,callee);code+=chunk
        adapters.append({'entry':hex(entry),'callee':hex(callee),'vertex_stride':stride,'bytes':len(chunk),'kind':'raw strip'})
        for p in sites:
            assert struct.unpack_from('<I',old,p)[0]==callee
            struct.pack_into('<I',exe,p,entry);edits.append({'file_offset':hex(p),'old':hex(callee),'new':hex(entry)})
    # The animation line path has the same counted descriptor layout as the
    # battle grid. Clone its verified adapter, changing only its draw callee.
    entry=ENTRY+len(code);chunk=raw_descriptor_adapter(entry);code+=chunk
    adapters.append({'entry':hex(entry),'callee':'0x8c0a93bc','bytes':len(chunk),'kind':'counted line descriptor'})
    for p in LINE_SITES:
        assert struct.unpack_from('<I',old,p)[0]==0x8c0a93bc
        struct.pack_into('<I',exe,p,entry);edits.append({'file_offset':hex(p),'old':'0x8c0a93bc','new':hex(entry)})
    off=ENTRY-0x8c010000;assert off+len(code)<=0x6bad0,(len(code),hex(off+len(code)))
    assert old[off:off+len(code)]==bytes.fromhex('0900')*(len(code)//2)
    exe[off:off+len(code)]=code
    allowed=set(range(off,off+len(code)))|{p+j for p in (*LINE_SITES,*(p for _,sites in RAW_SITES.values() for p in sites)) for j in range(4)}
    changed=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b];assert set(changed)<=allowed
    return bytes(exe),{'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(old),'executable_sha256':digest(exe),
        'adapters':adapters,'pointer_edits':edits,'helper_bytes':len(code),'changed_executable_bytes':len(changed),
        'cause':'Animation colored/textured strips and lines bypassed the 640x480 display adapters, leaving reticles and other animation geometry at half position/size.',
        'mapping':'Scale only XY at the animation engine graphics boundary; preserve Z, inverse depth, UV, color, blend arguments, selected target and original input arrays.',
        'scope':'Six animation-engine call-site literals only; SDK initialization/fade and other draw callers remain unchanged. All disc assets and other executable bytes exact 0.7.20.',
        'release':False,'live_validation':'pending'}


def raw_descriptor_adapter(base):
    a=Assembler(base);a.push(8);a.emit(0x4f22);a.rr('mov',15,8);a.emit(0x5743)
    a.rr('mul.l',5,7);a.unary('sts.macl',7);a.rr('mov',7,3);a.unary('shll2',3);a.unary('shll',3);a.addi(16,3);a.rr('sub',3,15)
    a.rr('mov',4,1);a.rr('mov',15,2);a.imm(4,3)
    a.label('descriptor');a.emit(0x6016);a.store('l',0,2);a.addi(4,2);a.unary('dt',3);a.branch('bf','descriptor')
    a.load('l',4,1);a.rr('mov',15,2);a.addi(16,2);a.store('l',2,15);a.rr('mov',7,3);a.unary('shll',3);a.rr('tst',3,3);a.branch('bt','draw')
    a.label('points');a.emit(0xf019);a.emit(0xf000);a.emit(0xf20a);a.addi(4,2);a.unary('dt',3);a.branch('bf','points')
    a.label('draw');a.rr('mov',15,4);a.lit(0x8c0a93bc,3);a.emit(0x430b);a.emit(0x0009)
    a.rr('mov',8,15);a.emit(0x4f26);a.pop(8);a.emit(0x000b);a.emit(0x0009)
    return a.pool_and_finish()


def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local battle target/animation coordinate conversion',component_manifest_name='battle-target-component.json',
        current_native_evidence={'battle_target':'battle-target-native-test.json'},current_live_evidence={'battle_target':'battle-target-live-test.json'},
        readme_component_text='Corrects half-position/size animation reticles and related animation primitives at 640x480.\n'
            'Native Skies 1x font, all assets, grid and memory repairs unchanged.\n',
        proof_scope='Actual SDK raw vertex packet emission and adapter/source-preservation checks; separate live validation.',
        pending=['Physical Dreamcast/full-game animation and route review','Stage 6 issue #1'])
    return p,mode


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,r=compose();print(json.dumps(r,indent=2))
    if not a.write:print('DRY RUN: no files written');return
    from test_battle_target import check
    proof=check()
    if not a.disc:print(json.dumps(proof,indent=2));return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('battle-target-component.json',r),('battle-target-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:
        (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files']);m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
