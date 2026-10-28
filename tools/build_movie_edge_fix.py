"""Inset Sofdec texture sampling to valid pixel centers. Dry run before writing."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from sh4_asm import Assembler
from test_native_movie_font import fresh,run,bits,value,DrawCPU,BASE,OBJ
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.13','0.7.12'
START,END=0xac2e4,0xac3f4
OUT=ROOT/'work/output/movie-edge-candidate'


def geometry_code():
    a=Assembler(BASE+START)
    def getf(offset,fr):a.imm(offset,0);a.emit(0xf086|fr<<8) # @(R0,R8)
    def putf(offset,fr):a.imm(offset,0);a.emit(0xf907|fr<<4) # @(R0,R9)
    def getl(offset):a.imm(offset,0);a.emit(0x018e) # @(R0,R8),R1
    for r in (8,9,10):a.push(r)
    a.rr('mov',4,8);a.lit(152,0);a.emit(0x098e);a.imm(0,10)
    a.lit(bits(.5),0);a.emit(0x405a);a.emit(0xf20d) # half texel constant
    for fr,dim,extent in ((4,52,96),(5,56,100)):
        a.emit(0xf08d|fr<<8) # FLDI0
        getl(dim);a.emit(0x4115);a.branch('bf',f'axis{fr}')
        getf(extent,3);a.emit(0xf08d);a.emit(0xf305);a.branch('bf',f'axis{fr}')
        a.emit(0x415a);a.emit(0xf32d);a.emit(0xf02c|fr<<8);a.emit(0xf033|fr<<8)
        a.label(f'axis{fr}')
    a.label('quad')
    a.rr('mov',10,0);a.emit(0x8803);a.unary('movt',0);a.store('l',0,9)
    for axis,mask,pos,span,uv,uvspan,half in (('x',1,68,80,88,96,4),('y',2,72,84,92,100,5)):
        getf(pos,2);getf(uv,3)
        a.rr('mov',10,0);a.emit(0xc900|mask);a.rr('tst',0,0);a.branch('bt',axis+'low')
        getf(span,0);a.emit(0xf200);getf(uvspan,0);a.emit(0xf300);a.emit(0xf301|half<<4)
        a.branch('bra',axis+'store');a.emit(0x0009)
        a.label(axis+'low');a.emit(0xf300|half<<4)
        a.label(axis+'store');putf(4 if axis=='x' else 8,2);putf(16 if axis=='x' else 20,3)
    getf(76,2);putf(12,2)
    getl(104);a.emit(0x1916);getl(108);a.emit(0x1917)
    a.addi(32,9);a.addi(1,10);a.rr('mov',10,0);a.emit(0x8804);a.branch('bf','quad')
    for r in (10,9,8):a.pop(r)
    a.emit(0x000b);a.emit(0x0009)
    code=a.pool_and_finish();assert len(code)<=END-START,(len(code),END-START)
    return code+bytes.fromhex('0900')*((END-START-len(code))//2)


@lru_cache(maxsize=1)
def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    retail=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    assert old[START:END]==retail[START:END]
    exe=old[:START]+geometry_code()+old[END:]
    component={'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),
        'source_executable_sha256':digest(old),'patch_range':[hex(START),hex(END)],
        'change':'Sofdec four-corner UVs inset half a texel on each outer edge, derived independently from texture width/height.',
        'scope':'Screen rectangle, depth, colors, animation, original SFD video/audio and all other assets unchanged.',
        'startup_guard':'Zero/negative texture dimensions or UV spans retain zero inset for that axis.',
        'release':False,'live_validation':'pending'}
    return exe,component


class MovieEdgeCPU(DrawCPU):
    def execute(self,pc,delay=False):
        word=self.read(pc,2)
        if word&0xf00f==0xf001: # FSUB FRm,FRn
            n,m=word>>8&15,word>>4&15;self.fr[n]=bits(value(self.fr[n])-value(self.fr[m]));return pc+2
        if word&0xf00f==0xf003: # FDIV FRm,FRn
            n,m=word>>8&15,word>>4&15;self.fr[n]=bits(value(self.fr[n])/value(self.fr[m]));return pc+2
        if word&0xf00f==0xf005: # FCMP/GT FRm,FRn
            n,m=word>>8&15,word>>4&15;self.t=int(value(self.fr[n])>value(self.fr[m]));return pc+2
        if word&0xf0ff in (0xf00d,0xf08d):
            n=word>>8&15;self.fr[n]=self.fpul if word&255==13 else bits(0.);return pc+2
        return super().execute(pc,delay)


def fixture(exe,params):
    c=fresh(exe,MovieEdgeCPU);c.reg[4]=OBJ
    c.write(OBJ+152,OBJ+0x1000,4)
    for offset,n in params.items():c.write(OBJ+offset,n,4)
    before=bytes(c.regions[3][1]);steps=run(c,BASE+START)
    raw=bytes(c.read(OBJ+0x1000+i,1) for i in range(128))
    assert bytes(c.regions[3][1][:0x1000])==before[:0x1000]
    assert bytes(c.regions[3][1][0x1080:])==before[0x1080:]
    return c,raw,steps


def check():
    exe,component=compose();old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    dimensions=sorted({tuple(struct.unpack_from('<2I',exe,0x88e78+12*i)) for i in range(129)})
    dimensions=[(w,h) for w,h in dimensions if w and h]
    cases=steps=0;witness=[]
    for w,h in dimensions:
      tw,th=1<<(w-1).bit_length(),1<<(h-1).bit_length()
      for scale in (1.,2.,4.):
       for u0,v0 in ((0.,0.),(.125,.0625)):
        p={44:w,48:h,52:tw,56:th,68:bits(-12.5),72:bits(48.),76:bits(10.),
            80:bits(w*scale),84:bits(h*scale),88:bits(u0),92:bits(v0),96:bits(w/tw),100:bits(h/th),
            104:0xffeaeaea,108:0xff000000}
        _,a,n=fixture(old,p);steps+=n;c,b,n=fixture(exe,p);steps+=n
        for i in range(4):
            # UV is the only field allowed to change in either native/raw quad.
            off=i*32
            assert a[off:off+16]==b[off:off+16] and a[off+24:off+32]==b[off+24:off+32]
            uv=struct.unpack_from('<2f',b,off+16)
            expected=(u0+((w-.5) if i&1 else .5)/tw,v0+((h-.5) if i&2 else .5)/th)
            assert uv==expected,(i,uv,expected)
            # Bilinear footprint at every visible output pixel center stays
            # inside the decoded picture, including the last bottom/right row.
        sx,sy=int(w*scale),int(h*scale)
        for count,source in ((sx,w),(sy,h)):
            samples=[.5+(j+.5)/count*(source-1)-.5 for j in (0,count-1)]
            assert min(samples)>=0 and max(samples)<=source-1
        cases+=1
        if scale==2 and u0==0:witness.append({'source':[w,h],'texture':[tw,th],
            'old_bottom_v':h/th,'new_bottom_v':(h-.5)/th,'screen_pixels':[w*2,h*2]})
    for tw,th,uw,vh in ((0,0,0.,0.),(512,256,0.,0.),(512,0,.625,.75),(0,256,.625,.75),
                        (-1,256,.625,.75),(512,-1,.625,.75),(512,256,-.625,.75),(512,256,.625,-.75)):
        p={52:tw,56:th,68:bits(0.),72:bits(0.),76:bits(10.),80:bits(640.),84:bits(384.),
            88:bits(0.),92:bits(0.),96:bits(uw),100:bits(vh),104:0xffffffff,108:0}
        _,raw,n=fixture(exe,p);steps+=n
        hu=.5/tw if tw>0 and uw>0 else 0.;hv=.5/th if th>0 and vh>0 else 0.
        for i in range(4):assert struct.unpack_from('<2f',raw,i*32+16)==(uw-hu if i&1 else hu,vh-hv if i&2 else hv)
        cases+=1
    return {**component,'source_movie_dimensions':dimensions,'geometry_cases':cases,'SH4_instructions':steps,
        'movie_witnesses':witness,'checks':['Actual old/new Sofdec raw quad generation executes; only UV fields differ',
            'All table source sizes at 1x/2x/4x, zero/nonzero crop origins, initialization guards, ABI and input guards pass',
            'Bilinear pixel-center footprints stay within valid decoded rows/columns'],
        'limits':['Video decoding, texture upload and GPU rasterization require live validation','Physical hardware pending','Stage 6 issue #1 unresolved']}


def plan():
    exe,component=compose();base=ROOT/'work/output'/PRIOR
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    p,_=font_plan(compose_fn=lambda:(exe,(base/'WIN00.AFS').read_bytes(),b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local movie texture edge fix',component_manifest_name='movie-edge-component.json',
        current_native_evidence={'movie_edge':'movie-edge-native-test.json'},
        readme_component_text='Movie UV edges inset half a texel to avoid filtering unused texture padding.\n'
            'Screen size/placement, original movie bytes and all 0.7.12 fixes retained. Cold-boot the GDI.\n',
        proof_scope='Actual Sofdec geometry generation with protected fields/ABI; complete disc preservation.',
        pending=['Movie GPU and physical hardware confirmation','Stage 6 issue #1','Full-game translation review'])
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,component=compose()
    if not a.write:print(json.dumps(component,indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True);(OUT/'1ST_READ.BIN').write_bytes(exe)
    records=[('movie-edge-component.json',component),('movie-edge-native-test.json',proof)]
    for name,data in records:(OUT/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    print('PASS:',proof['geometry_cases'],'movie geometry cases.',flush=True)
    if a.disc:
        p=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=ROOT/'work/output'/VERSION
        for name,data in records:(out/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
        m['movie_edge']={'native_proof':'movie-edge-native-test.json','patch_range':[hex(START),hex(END)]}
        m['native_proof_reuse']={'source_build':PRIOR,'scope':'All assets and executable bytes outside Sofdec quad generation are exact.'}
        (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
        mode=json.loads((out/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
        (out/'font-mode-details.json').write_text(json.dumps(mode,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
