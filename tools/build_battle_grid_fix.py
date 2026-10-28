"""Scale the battle range overlay with its units. Dry first; local 0.7.20."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from sh4_asm import Assembler

VERSION,PRIOR='0.7.20','0.7.19'
ENTRY=0x8c07b940
POINTER=0x360c8
DRAW=0x8c0ab660


@lru_cache(maxsize=1)
def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();exe=bytearray(old)
    # This SDK API receives a count of polygons, each with descriptor[12]
    # vertices. The earlier 2D adapter receives a count of vertices instead.
    a=Assembler(ENTRY);a.push(8);a.emit(0x4f22);a.rr('mov',15,8)
    a.emit(0x5743)  # mov.l @(12,r4),r7: vertices per polygon
    a.rr('mul.l',5,7);a.unary('sts.macl',7)
    a.rr('mov',7,3);a.unary('shll2',3);a.unary('shll',3);a.addi(16,3);a.rr('sub',3,15)
    a.rr('mov',4,1);a.rr('mov',15,2);a.imm(4,3)
    a.label('descriptor');a.emit(0x6016);a.store('l',0,2);a.addi(4,2);a.unary('dt',3);a.branch('bf','descriptor')
    a.load('l',4,1);a.rr('mov',15,2);a.addi(16,2);a.store('l',2,15)
    a.rr('mov',7,3);a.unary('shll',3);a.rr('tst',3,3);a.branch('bt','draw')
    a.label('points');a.emit(0xf019);a.emit(0xf000);a.emit(0xf20a);a.addi(4,2);a.unary('dt',3);a.branch('bf','points')
    a.label('draw');a.rr('mov',15,4);a.lit(DRAW,3);a.emit(0x430b);a.emit(0x0009)
    a.rr('mov',8,15);a.emit(0x4f26);a.pop(8);a.emit(0x000b);a.emit(0x0009)
    code=a.pool_and_finish();off=ENTRY-0x8c010000
    assert off>=0x6b918 and off+len(code)<=0x6bad0
    assert old[off:off+len(code)]==bytes.fromhex('0900')*(len(code)//2)
    assert struct.unpack_from('<I',old,POINTER)[0]==DRAW
    exe[off:off+len(code)]=code;struct.pack_into('<I',exe,POINTER,ENTRY)
    allowed=set(range(off,off+len(code)))|set(range(POINTER,POINTER+4))
    changed=[i for i,(x,y) in enumerate(zip(old,exe)) if x!=y];assert set(changed)<=allowed
    return bytes(exe),{'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(old),
        'executable_sha256':digest(exe),'adapter':hex(ENTRY),'adapter_bytes':len(code),'draw_pointer_file_offset':hex(POINTER),
        'changed_executable_bytes':len(changed),'cause':'Battle range fill bypassed the 640x480 sprite/polygon adapters; its vertices remained on the 320x240 logical grid.',
        'mapping':'Copy the descriptor and polygon-count * vertices-per-polygon XY pairs to the stack; multiply XY by 2 exactly once at the battle fill call.',
        'preserved':'Input geometry, colors, priority, flags, primitive counts, UVs, all other executable bytes, every disc asset, Native 1x font and 0.7.19 memory allocation.',
        'release':False,'live_validation':'pending'}


def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local battle movement/range grid alignment',component_manifest_name='battle-grid-component.json',
        current_native_evidence={'battle_grid':'battle-grid-native-test.json'},current_live_evidence={'battle_grid':'battle-grid-live-test.json'},
        readme_component_text='Corrects battle movement/range fill alignment at 640x480. Native Skies 1x only.\n'
            'All 0.7.19 texture-memory repairs and all disc assets remain unchanged.\n',
        proof_scope='Actual battle fill construction and native scaling/ABI checks; live validation recorded separately.',
        pending=['Physical Dreamcast/full-game geometry and route review','Stage 6 issue #1'])
    return p,mode


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,r=compose();print(json.dumps(r,indent=2))
    if not a.write:print('DRY RUN: no files written');return
    from test_battle_grid import check
    proof=check()
    if not a.disc:print(json.dumps(proof,indent=2));return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('battle-grid-component.json',r),('battle-grid-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:
        (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe);(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
