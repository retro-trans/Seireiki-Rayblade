"""Correct inclusive battle clip tiles, remaining 2D lines and menu bars. Dry first."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from sh4_asm import Assembler

VERSION,PRIOR='0.7.23','0.7.22'
ENTRY=0x8c07bbac
LINE_ENTRY=0x8c07ba50
LINE_POINTERS=(0x320d0,0x328f8,0x329c4,0x32a90,0x32b5c,0x32c0c,0x5b5e8,0x5c958,0x69a5c,0x69b58)
BAR_EDITS=((0xe727,7,15,'Counterattack forecast'),(0xfddb,9,15,'Counter policies'),(0xf056,4,8,'Unit action menu'))

def helper():
    a=Assembler(ENTRY);a.rr('mov',4,0);a.emit(0x8802);a.branch('bf','tail')
    a.emit(0xf19d) # FLDI1 FR1
    for offset in (8,12):
        a.imm(offset,0);a.emit(0xf056);a.emit(0xf010);a.emit(0xf507)
    a.label('tail');a.lit(0x8c0a7c06,3);a.emit(0x432b);a.emit(0x0009)
    raw=a.pool_and_finish();assert ENTRY+len(raw)<=0x8c07bbe0
    return raw

@lru_cache(maxsize=1)
def compose():
    before=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();exe=bytearray(before);code=helper();off=ENTRY-0x8c010000
    assert before[off:off+len(code)]==bytes.fromhex('0900')*(len(code)//2)
    assert struct.unpack_from('<I',before,0x6b7a4)[0]==0x8c0a7c06
    exe[off:off+len(code)]=code;struct.pack_into('<I',exe,0x6b7a4,ENTRY)
    for p in LINE_POINTERS:
        assert struct.unpack_from('<I',before,p)[0]==0x8c0a93bc
        struct.pack_into('<I',exe,p,LINE_ENTRY)
    for p,old,new,_ in BAR_EDITS:assert before[p]==old;exe[p]=new
    allowed=set(range(off,off+len(code)))|{0x6b7a4+i for i in range(4)}|{p+i for p in LINE_POINTERS for i in range(4)}|{p for p,_,_,_ in BAR_EDITS}
    changed={i for i,(a,b) in enumerate(zip(before,exe)) if a!=b};assert changed<=allowed
    return bytes(exe),{'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),'source_executable_sha256':digest(before),
        'clip_helper':hex(ENTRY),'helper_bytes':len(code),'clip_wrapper_tail_literal':'0x6b7a4',
        'mapping':'For SDK mode 2 tile rectangles: min *= 2, max = max * 2 + 1. Existing wrapper performs the multiplication; helper adds one to the two inclusive maximum tile indices. Other modes retain previous behavior.',
        'remaining_line_pointers':[hex(p) for p in LINE_POINTERS],'line_adapter':hex(LINE_ENTRY),
        'line_scope':'Remaining application 2D line descriptors use the existing XY-only 2x adapter. SDK internal callers and adapter callee literal remain untouched.',
        'selection_bars':[{'offset':hex(p),'before_tiles':a,'after_tiles':b,'label':label} for p,a,b,label in BAR_EDITS],
        'changed_executable_bytes':len(changed),'font_assets_wording_gameplay':'All unchanged from 0.7.22. Native Skies 1x only; lossless text VQ and Stage 6 fix preserved.',
        'release':False,'validation':'Native and live split-view/menu validation required'}

def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local battle clip/line and selection bar repair',component_manifest_name='battle-clip-component.json',
        current_native_evidence={'battle_clip':'battle-clip-native-test.json'},current_live_evidence={'battle_clip':'battle-clip-live-test.json'},
        readme_component_text='Corrects inclusive split-view tile clipping, application line coordinates and widened menu selection bars.\n',
        proof_scope='Actual native tile bounds and selection constructors, XY line adapter preservation; separate live split battle review.',
        pending=['Live split battle and menu review','Physical Dreamcast and full-route testing'])
    return p,mode

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,r=compose();print(json.dumps(r,indent=2))
    if not a.write:print('DRY RUN: no files written');return
    from test_battle_clip import check
    proof=check()
    if not a.disc:print(json.dumps(proof,indent=2));return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('battle-clip-component.json',r),('battle-clip-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:
        (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files']);m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')

if __name__=='__main__':main()
