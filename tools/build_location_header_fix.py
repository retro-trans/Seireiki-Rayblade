"""Measure location banners with the integrated font; preserve other callers."""
import argparse,json,struct
from functools import lru_cache
from PIL import Image
from build_bitmap_font import ROOT,digest
from build_font4x_patch import BASE,MEDIUM
from build_map_font_patch import member
from sh4_asm import Assembler
from test_library_headers import setup,call,HeaderCPU
from test_ui_layouts import entry,parse_ui
from test_outline_font import legacy_mask
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.11','0.7.10'
OUT=ROOT/'work/output/location-header-candidate'
START,END=0x66d38,0x66e4e


def measure_code():
    a=Assembler(BASE+START)
    for r in (8,9,10):a.push(r)
    a.emit(0x4f22);a.rr('mov',4,8);a.imm(0,9)
    a.rr('mov',4,0);a.unary('shlr8',0);a.imm(31,4);a.rr('and',0,4)
    a.lit(0x8c034bde,3);a.emit(0x430b);a.emit(0x0009)
    a.rr('mov',0,2);a.rr('mov',8,0);a.emit(0xc9ff);a.unary('shll2',0)
    a.rr('add',0,2);a.load('l',2,10);a.rr('add',2,10)
    a.rr('mov',8,0);a.unary('shlr8',0);a.emit(0xc91f);a.emit(0x8806);a.emit(0x0829)
    a.label('loop');a.lit(320,1);a.rr('cmp/hs',1,9);a.branch('bt','overflow')
    a.load('b',10,0);a.rr('extu.b',0,0);a.lit(255,1);a.rr('cmp/eq',1,0);a.branch('bt','done')
    a.lit(0xf0,1);a.rr('cmp/hs',1,0);a.branch('bt','wide_control')
    a.rr('tst',8,8);a.branch('bt','fixed')
    a.imm(len(MEDIUM),1);a.rr('cmp/hs',1,0);a.branch('bf','latin')
    a.imm(MEDIUM.index('?'),0)
    a.label('latin');a.lit(0x8c1f36a4,1);a.load('l',1,1);a.lit(0xa0,2)
    a.rr('add',2,1);a.rr('add',0,1);a.load('b',1,0);a.rr('extu.b',0,0)
    a.rr('add',0,9);a.branch('bra','next');a.emit(0x0009)
    a.label('fixed');a.addi(8,9);a.branch('bra','next');a.emit(0x0009)
    a.label('wide_control');a.lit(0xfa,1);a.rr('cmp/hs',1,0);a.branch('bt','control')
    a.addi(1,10);a.addi(12,9);a.branch('bra','next');a.emit(0x0009)
    a.label('control');a.lit(252,1);a.rr('cmp/eq',1,0);a.branch('bf','next');a.addi(2,10)
    a.load('b',10,0);a.rr('extu.b',0,0);a.emit(0x883c);a.branch('bf','next');a.addi(2,10)
    a.label('next');a.addi(1,10);a.branch('bra','loop');a.emit(0x0009)
    a.label('overflow');a.imm(0,9)
    a.label('done');a.rr('mov',9,0);a.emit(0x4f26)
    for r in (10,9,8):a.pop(r)
    a.emit(0x000b);a.emit(0x0009)
    code=a.pool_and_finish();assert len(code)<=END-START
    return code+bytes.fromhex('0900')*((END-START-len(code))//2)


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old=(base/'1ST_READ.BIN').read_bytes()
    retail=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    assert old[START:END]==retail[START:END]
    exe=old[:START]+measure_code()+old[END:]
    assert exe[:START]==old[:START] and exe[END:]==old[END:]
    component={'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(old),
        'executable_sha256':digest(exe),'patch_range':[hex(START),hex(END)],
        'reason':'The original measurement reserves 8 pixels per Latin byte, while the integrated font has variable advances.',
        'scope':'Only group 6 location widths use current font advances; other groups retain original 8/12 counting and controls.',
        'right_anchor':313,'text_y':22,'decorative_geometry_and_animation':'unchanged original code',
        'font_and_all_assets':'byte-exact 0.7.10','release':False,'live_validation':'pending'}
    return exe,component


class LocationCPU(HeaderCPU):
    def execute(self,pc,delay=False):
        if pc in (0x8c078e20,0x8c078a30,0x8c076afc,0x8c02fb6c,0x8c0312c4):
            self.geometry.append((pc,list(self.reg[4:8]),self.read(self.reg[15],4),self.read(self.reg[15]+4,4)))
            self.reg[0]=7;return self.pr
        return super().execute(pc,delay)


def header_phase(exe,font,paper,names,index):
    c=setup(exe,font,paper,names);c.__class__=LocationCPU;c.geometry=[]
    c.regions.append((0x8c480000,bytearray(0x4000)));c.write(0x8c09b2b4,0x8c480000,4)
    c.reg[1]=0x8c09b2b4;c.write(0x8c701800+24,index,2)
    steps=call(c,0x8c0843a4,stop=0x8c08448e)
    return c.geometry,steps


def check():
    exe,component=compose();base=ROOT/'work/output'/PRIOR
    old=(base/'1ST_READ.BIN').read_bytes();names=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    paper=(base/'text/D_PAPER.en.dec.bin').read_bytes();banks=member((base/'WIN00.AFS').read_bytes(),0)
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
    cases=[];steps=0;regressions=0;geometry_cases=0
    for mode in (0,1):
        font=banks[mode*99072:(mode+1)*99072]
        current=setup(exe,font,paper,names);prior=setup(old,font,paper,names)
        for row in rows:
            if row['source_record_kind']=='unused_table_root_sentinel':continue
            _,g,idx=row['id'].split('.');group=int(g[1:]);idx=int(idx);handle=group*256+idx
            # Actual game measurement scans every byte/control through FF.
            saved=current.reg[8:];steps+=call(current,BASE+START,handle);width=current.reg[0]
            assert current.reg[8:]==saved
            steps+=call(prior,BASE+START,handle);before=prior.reg[0]
            if group!=6:
                assert width==before,(row['id'],width,before);regressions+=1;continue
            payload=entry(names,row['id']);assert all(b<0xf0 for b in payload[:-1]),row['id']
            expected=sum(font[0xa0+b] for b in payload[:-1]);assert width==expected<320
            gs,n=parse_ui(exe,font,names,payload,x=0);steps+=n
            bounds={ch:Image.fromarray(legacy_mask(font,ch,False)).getbbox() for ch,x,y,s in gs}
            right=max((x+bounds[ch][2]/4+1 for ch,x,y,s in gs if bounds[ch]),default=0)
            assert right<=width+1,(row['id'],right,width)
            geometry,n=header_phase(exe,font,paper,names,idx);steps+=n;geometry_cases+=1
            assert [g[0] for g in geometry]==[0x8c078e20,0x8c078a30,0x8c076afc,0x8c02fb6c,0x8c02fb6c,0x8c0312c4]
            assert geometry[0][1][1:3]==[313-width,22]
            assert geometry[2][1][:2]==[7,handle]
            assert geometry[3][1][1:3]==[297-width,16] and geometry[3][2:]==(61,75)
            tiles=(width+16)//8
            assert geometry[4][1][1:3]==[(313-width-tiles*16)&0xffffffff,16] and geometry[4][2:]==(61,76)
            assert geometry[5][1][1:3]==[tiles*100,100]
            cases.append({'font_bank':('HD','Native')[mode],'id':row['id'],'old_width':before,'width':width,
                'text_x':313-width,'ink_right':right,'right_margin':320-(313-width+right)})
    return {**component,'location_cases':cases,'unchanged_other_group_cases':regressions,'native_header_geometry_cases':geometry_cases,
        'SH4_instructions':steps,'checks':['All location widths match original native font advances in both banks',
            'All other valid name rows match the prior native measurement exactly',
            'Only the measurement function differs; location placement, caps, body sizing and animation remain byte-exact'],
        'limits':['Native location geometry executes; final text/GPU submission endpoints are bounded fixtures.',
            'Live GPU appearance and physical hardware pending','Stage 6 issue #1 unresolved']}


def plan():
    exe,component=compose();base=ROOT/'work/output'/PRIOR
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    p,_=font_plan(compose_fn=lambda:(exe,(base/'WIN00.AFS').read_bytes(),b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local measured location headers',component_manifest_name='location-header-component.json',
        current_native_evidence={'location_header':'location-header-native-test.json'},
        readme_component_text='Location banners now measure the original Skies variable-width font.\n'
            'Retains the Japanese version right anchor, border artwork, padding and animation.\n'
            'All 0.7.10 fixes and all assets retained. Cold-boot and use a normal VMU save.\n',
        proof_scope='Native location widths and unchanged other-group measurements in both font banks; executable range and complete disc preservation.',
        pending=['Live location-banner appearance','Unidentified room tag sprite 66','Stage 6 issue #1','Full-game translation review'])
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,component=compose()
    if not a.write:print(json.dumps(component,indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True);(OUT/'1ST_READ.BIN').write_bytes(exe)
    for name,value in [('location-header-component.json',component),('location-header-native-test.json',proof)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    print('PASS:',len(proof['location_cases']),'location cases;',proof['unchanged_other_group_cases'],'unchanged other-group cases.',flush=True)
    if a.disc:
        p=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=ROOT/'work/output'/VERSION
        for name,value in [('location-header-component.json',component),('location-header-native-test.json',proof)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
        m['location_header']={'native_proof':'location-header-native-test.json','measurement_range':[hex(START),hex(END)]}
        m['native_proof_reuse']={'source_build':PRIOR,'scope':'All assets and executable bytes outside the independently tested measurement function are exact.'}
        (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
        mode=json.loads((out/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
        (out/'font-mode-details.json').write_text(json.dumps(mode,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
