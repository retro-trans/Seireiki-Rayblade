"""Restore SDK print geometry in the native framebuffer. Dry run first."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from test_native_movie_font import fresh,run,bits,value,DrawCPU,BASE,STOP,OBJ

VERSION,PRIOR='0.7.12','0.7.11'
OUT=ROOT/'work/output/loading-position-candidate'
OFFSET=0x9c690


@lru_cache(maxsize=1)
def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    assert struct.unpack_from('<f',old,OFFSET)[0]==8.
    exe=bytearray(old);struct.pack_into('<f',exe,OFFSET,16.)
    assert [i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]==[OFFSET+2]
    component={'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(old),
        'executable_sha256':digest(exe),'changed_byte':hex(OFFSET+2),
        'SDK_print_default_cell_pixels':{'before':8,'after':16},
        'loading_cell_origin':[27,26],'physical_origin_before':[216,208],
        'physical_origin_after':[432,416],
        'reason':'Ninja SDK print bypasses the game sprite/polygon adapters. Its cell size also controls cell coordinates.',
        'scope':'SDK print default only; loading character cells, animation, colors, all game font banks and assets unchanged.',
        'release':False,'live_validation':'pending'}
    return bytes(exe),component


class PrintCPU(DrawCPU):
    def execute(self,pc,delay=False):
        op=self.read(pc,2)
        if op&0xf0ff==0x0083: # PREF: capture store-queue packet; no GPU fixture.
            address=self.reg[op>>8&15]
            self.packets.append(bytes(self.read(address+i,1) for i in range(32)))
            return pc+2
        if op&0xf0ff==0xf03d: # FTRC FRn,FPUL
            self.fpul=int(value(self.fr[op>>8&15]))&0xffffffff;return pc+2
        if op&0xf0ff==0x005a: # STS FPUL,Rn
            self.reg[op>>8&15]=self.fpul;return pc+2
        if op&0xf00f==0xf00e: # FMAC FR0,FRm,FRn
            n,m=op>>8&15,op>>4&15
            self.fr[n]=bits(value(self.fr[n])+value(self.fr[0])*value(self.fr[m]));return pc+2
        if pc==0x8c093bb0: # bounded 12-byte application color copy, before draw
            assert self.reg[0]==12 and self.reg[2]==0x8c0973e0
            for i in range(12):self.write(self.reg[1]+i,self.read(self.reg[2]+i,1),1)
            return self.pr
        if pc==0x8c0ac6c8:
            self.glyphs.append({'xy':[self.reg[4],self.reg[5]],'char':chr(self.reg[6]&255),
                'size':value(self.read(0x8c4222ec,4)),'color':self.read(0x8c4222e8,4)})
        return super().execute(pc,delay)


def setup(exe):
    c=fresh(exe,PrintCPU)
    c.regions.extend([(0x8c410000,bytearray(0x20000)),(0x8c098000,bytearray(0x1000)),
        (0xe0100000,bytearray(0x10000)),(0xff000000,bytearray(0x100))])
    c.write(0x8c419a58,OBJ+0x100,4);c.write(OBJ+0x108,0x00100000,4)
    c.packets=[];c.glyphs=[]
    # Execute the real SDK initializer through its default-size store. Resource
    # allocation starts after this boundary and is irrelevant to its cell size.
    c.reg[4:7]=[0,0,256];c.pc=0x8c0ac5c0
    while c.pc!=0x8c0ac5da:c.pc=c.execute(c.pc)
    size=c.read(0x8c4222ec,4)
    c.reg[15]=0x8c708000;c.pr=STOP
    return c,size


def check():
    exe,component=compose();old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    legacy=(ROOT/'work/output/0.7.2/1ST_READ.BIN').read_bytes()
    for lo,hi in ((0x10a50,0x10c9c),(0x9c5c0,0x9c970),(0x873e0,0x8740c)):
        assert legacy[lo:hi]==old[lo:hi],('Pre-640 loading code changed',hex(lo))
    cases=[];steps=0
    for frame in range(121):
        results=[]
        for code,scale in ((old,1),(exe,2)):
            c,size=setup(code);assert value(size)==8*scale
            c.write(0x8c098ad8,frame,1)
            steps+=run(c,0x8c020a50)
            assert ''.join(g['char'] for g in c.glyphs)=='NOWLOADING'
            cells=[27,28,29,31,32,33,34,35,36,37]
            assert [g['xy'] for g in c.glyphs]==[[x*8*scale,26*8*scale] for x in cells]
            assert all(g['size']==8*scale for g in c.glyphs)
            assert c.read(0x8c098ad8,1)==(frame+1 if frame<120 else 0)
            # Each native njPrint call submits a header and two 32-byte sprite
            # packets; the original SDK produces actual four-corner geometry.
            assert len(c.packets)==30,len(c.packets)
            corners=[]
            for i,g in enumerate(c.glyphs):
                p=c.packets[i*3+1]+c.packets[i*3+2]
                xy=[[struct.unpack_from('<f',p,o)[0],struct.unpack_from('<f',p,o+4)[0]] for o in (4,16,28,40)]
                x,y=g['xy'];s=8*scale
                assert xy==[[x,y],[x+s,y],[x+s,y+s],[x,y+s]],(i,xy,g)
                corners.append(xy)
            results.append((c.glyphs,c.packets,corners))
        a,b=results
        assert [g['color'] for g in a[0]]==[g['color'] for g in b[0]]
        for i in range(10):
            assert a[1][i*3]==b[1][i*3]
            pa=a[1][i*3+1]+a[1][i*3+2];pb=b[1][i*3+1]+b[1][i*3+2]
            xybytes={j for off in (4,8,16,20,28,32,40,44) for j in range(off,off+4)}
            assert all(pa[j]==pb[j] for j in range(64) if j not in xybytes)
        cases.append({'frame':frame,'glyphs':len(b[0]),'origin':b[0][0]['xy'],'colors':[hex(g['color']) for g in b[0]]})
    return {**component,'animation_frame_cases':len(cases),'native_glyph_quads':len(cases)*10*2,
        'SH4_instructions':steps,'pre_640_reference':'0.7.2 loading routine, SDK print code and character/color data are byte-exact in 0.7.11',
        'checks':['Actual SDK initialization, loading function, SDK string renderer and four-corner submissions execute',
            'Each old glyph corner maps uniformly 2x; cell gaps, Z, UV, headers, colors and full 121-frame counter cycle retained',
            'Only one executable byte changes; all other game bytes retained'],
        'limits':['Store queues captured before GPU; allocation and the 12-byte color copy are bounded fixtures',
            'Live VGA/physical hardware confirmation pending','Stage 6 issue #1 unresolved']}


def plan():
    exe,component=compose();base=ROOT/'work/output'/PRIOR
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    p,_=font_plan(compose_fn=lambda:(exe,(base/'WIN00.AFS').read_bytes(),b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local startup loading geometry fix',component_manifest_name='loading-position-component.json',
        current_native_evidence={'loading_position':'loading-position-native-test.json'},
        readme_component_text='Restores NOW LOADING to its pre-640-mode physical size and position.\nAll 0.7.11 fixes and assets retained. Cold-boot; do not use an emulator save state.\n',
        proof_scope='Actual SDK print initialization, loading animation and submitted glyph geometry; one-byte edit and complete disc preservation.',
        pending=['Live loading-screen appearance on hardware','Stage 6 issue #1','Full-game translation review'])
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,component=compose()
    if not a.write:print(json.dumps(component,indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True);(OUT/'1ST_READ.BIN').write_bytes(exe)
    records=[('loading-position-component.json',component),('loading-position-native-test.json',proof)]
    for name,data in records:(OUT/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    print('PASS:',proof['animation_frame_cases'],'animation frames;',proof['native_glyph_quads'],'native glyph quads.',flush=True)
    if a.disc:
        p=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=ROOT/'work/output'/VERSION
        for name,data in records:(out/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
        m['loading_position']={'native_proof':'loading-position-native-test.json','changed_byte':hex(OFFSET+2)}
        m['native_proof_reuse']={'source_build':PRIOR,'scope':'All assets and executable bytes except one SDK print default-size byte are exact.'}
        (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
        mode=json.loads((out/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
        (out/'font-mode-details.json').write_text(json.dumps(mode,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
