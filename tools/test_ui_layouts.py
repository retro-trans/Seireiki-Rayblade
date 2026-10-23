"""Execute UI parser/lookup/position controls against actual English names.

Parameter-byte input and the single-tile context list are bounded fixtures;
native text parsing, nested table lookups and coordinate operations execute.
The independently verified raster is represented by its cursor advance here.
"""
import argparse,json,struct
from collections import deque
from PIL import Image,ImageDraw
from build_ui_layout_patch import ROOT,VERSION,PRIOR,digest
from build_font4x_patch import SMALL,MEDIUM
from build_genei_font import SMALL_DATA,MEDIUM_DATA
from english_text_codec import encode
from rayblade_text import relative_target
from test_inline_controls import InlineCPU,fresh,run,SOURCE,STOP,CURSOR,FLAGS,BASE
from check_native_text_components import verify

NAMES=0x8c900000


class UICPU(InlineCPU):
    def execute(self,pc,delay=False):
        opcode=self.read(pc,2)
        if opcode&0xff00==0xc700: # MOVA @(disp,PC),R0
            self.reg[0]=((pc+4)&~3)+(opcode&255)*4
            return pc+2
        if opcode&0xf0ff==0x0023: # BRAF Rn, with its real delay slot
            assert not delay
            target=(pc+4+self.reg[(opcode>>8)&15])&0xffffffff
            self.execute(pc+2,True)
            return target
        if pc==0x8c03c364:
            assert self.parameters,'Native parser consumed an unexpected parameter'
            self.reg[0]=self.parameters.popleft();self.parameter_reads+=1
            return self.pr
        if pc==0x8c0787d0:
            assert self.reg[6]==48
            self.write(self.reg[5],1,2) # one real-sized text tile, slot 1
            self.reg[0]=1;return self.pr
        return super().execute(pc,delay)


def parse_ui(exe,font,names,payload,args=(),*,x=8,y=0):
    cpu=fresh(exe,font,payload);cpu.__class__=UICPU
    cpu.regions.append((NAMES,bytearray(names)))
    # Actual root helper's mapping, including its special group-7 +0x400.
    globals_by_group={0:0x8c1dbef4,1:0x8c1dbef8,2:0x8c1dbefc,3:0x8c1dbf00,
        4:0x8c1dbf04,5:0x8c1dbf08,6:0x8c1dbf0c,8:0x8c1dbf14,
        9:0x8c1dbf18,10:0x8c1dbf10,11:0x8c1dbf1c,12:0x8c1dbf48}
    for group,address in globals_by_group.items():cpu.write(address,NAMES+relative_target(names,group*4),4)
    cpu.write(0x8c1db4ec,0x8c400000,4)
    parameters=[];offset=0
    for i,arg in enumerate(args):
        if isinstance(arg[0],int):parameters.extend(arg);continue
        text,small=arg;raw=encode(text,ascii_mode=small)
        cpu.write(0x8c400400+2*i,offset,2)
        block,at=cpu.area(0x8c400600+offset,len(raw));block[at:at+len(raw)]=raw
        parameters.extend((2*i,14));offset+=len(raw)
    cpu.parameters=deque(parameters);cpu.parameter_reads=0
    # Native context geometry used by FC absolute-position lookup.
    slot=92
    cpu.write(0x8c1f0d4a+slot,1,2);cpu.write(0x8c1f0d4c+slot,1,2)
    cpu.write(0x8c1f0d4e+slot,512,2);cpu.write(0x8c1f0d50+slot,256,2)
    cpu.write(CURSOR,x,2);cpu.write(CURSOR+2,y,2);cpu.write(FLAGS,128,1)
    frame=0x8c700500;cpu.reg[15]=frame
    cpu.write(frame+124,STOP,4);cpu.write(frame+128,cpu.reg[8],4)
    cpu.write(frame+132,SOURCE,4);cpu.write(frame+120,x,2);cpu.write(frame+118,y,2)
    cpu.write(frame+123,1,1);cpu.write(frame+115,1,1)
    steps=run(cpu,0x8c07ac64)
    assert cpu.reg[0]==SOURCE+len(payload) and not cpu.parameters
    assert cpu.parameter_reads==len(parameters)
    assert cpu.reg[15]==frame+132 and cpu.read(FLAGS,1)==128
    return cpu.glyphs,steps


def entry(names,key):
    _,g,i=key.split('.');p=relative_target(names,int(g[1:])*4)+int(i)*4
    start=relative_target(names,p);end=start
    while True:
        value=names[end]
        if value in (254,255):return names[start:end+1]
        end+=5 if value==252 and names[end+2]==0x3c else 3 if value==252 else 1


def specimen(path,glyphs,font):
    im=Image.new('RGBA',(1024,520),'#24211f');draw=ImageDraw.Draw(im)
    draw.text((12,8),'Offline native-parser UI layout preview; not an in-game screenshot',fill='white')
    for char,x,y,small in glyphs:
        chars=SMALL if small else MEDIUM;idx=chars.index(char);height=8 if small else 16
        start=(SMALL_DATA if small else MEDIUM_DATA)+idx*height*32
        mask=Image.new('L',(64,height*4))
        for yy in range(height*4):
            a,b=struct.unpack_from('<2I',font,start+yy*8)
            if font[:8]==b'RBLF4X\0\4' and idx<len(chars)-5:
                for xx in range(32):mask.putpixel((xx,yy),(0,85,187,255)[((a if xx<16 else b)>>(30-2*(xx%16)))&3])
            else:
                for xx in range(64):
                    if (a if xx<32 else b)&(1<<(31-xx%32)):mask.putpixel((xx,yy),255)
        ink=Image.new('RGBA',mask.size,'white');ink.putalpha(mask)
        im.alpha_composite(ink,(x*4,24+y*4))
    im.save(path)


def main():
    global VERSION,PRIOR
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.15','0.1.17','0.1.19','0.1.21'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    if VERSION=='0.1.17':PRIOR='0.1.16'
    elif VERSION=='0.1.19':PRIOR='0.1.18'
    elif VERSION=='0.1.21':PRIOR='0.1.20'
    print('Plan: original PRS decoder, native menu/stat/help parsing, nested hit-rate lookup, all 128 chapter titles.',flush=True)
    if not args.verify:print('DRY RUN: no native execution or report written');return
    out=ROOT/'work/output'/VERSION;base=ROOT/'work/output'/PRIOR
    exe=(out/'1ST_READ.BIN').read_bytes();afs=(out/'WIN00.AFS').read_bytes()
    if VERSION=='0.1.17':
        from build_antialias_font import compose
        files,_,_,_=compose();assert exe==files['1ST_READ.BIN'] and afs==files['WIN00.AFS']
    elif VERSION=='0.1.19':
        from build_library_header_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN'] and afs==files['WIN00.AFS']
    elif VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN'] and afs==files['WIN00.AFS']
    else:
        assert exe==(base/'1ST_READ.BIN').read_bytes() and afs==(base/'WIN00.AFS').read_bytes()
    off,size=struct.unpack_from('<II',afs,8);font=afs[off:off+size]
    names=(out/'text/D_NAMES.en.dec.bin').read_bytes();packed=(out/'text/D_NAMES.BIN').read_bytes()
    decoder_steps=verify(exe,packed,names,65536)
    metric=json.loads((out/('antialias-font-report.json' if VERSION in ('0.1.17','0.1.19','0.1.21') else 'bitmap-font-report.json')).read_text('utf-8'))['metrics']
    masks={bank:{r['character']:r['packed_mask_bounds'] for r in m['glyphs']} for bank,m in metric.items()}
    def box(g):
        char,x,y,small=g;b=masks['small' if small else 'medium'][char]
        return None if b is None else (x+b[0]/4,y+b[1]/4,x+b[2]/4+1,y+b[3]/4)
    def inside(gs,x0,x1,y1=None):
        for g in gs:
            b=box(g)
            if b:assert x0<=b[0] and b[2]<=x1 and (y1 is None or b[3]<=y1),('UI ink overflow',g,b,(x0,x1,y1))
    def word(gs,text,x,y):
        alltext=''.join(g[0] for g in gs);at=alltext.index(text);part=gs[at:at+len(text)]
        assert part[0][1:3]==(x,y),(text,part[0],x,y)
        return part
    steps=0;cases=[];previews={}
    def check(key,args=(),x=8,y=0,label=None):
        nonlocal steps
        gs,n=parse_ui(exe,font,names,entry(names,key),args,x=x,y=y);steps+=n
        cases.append({'id':label or key,'glyphs':len(gs),'SH4_instructions':n,'parameter_pairs':len(args)})
        return gs
    gs=check('names.g00.001',[('Retreat<NL>',False)])
    inside(gs,8,72,112);assert 'Counter Orders' in ''.join(g[0] for g in gs)
    common=[(1,2),('99',True),('999',True),(79,3),('9999',True),('9999',True),('200',False)]
    gs=check('names.g00.003',common+[('999',False),('999',False)],x=64,y=16)
    inside(word(gs,'Spirit',128,0),128,152)
    inside(word(gs,'Prana',184,0),184,208)
    # The last display fragment in the combat preview is itself a nested
    # group-1 lookup whose FC controls draw Hit Rate and its numeric value.
    gs=check('names.g00.160',common+[(49,1),('100',False)],x=64,y=16)
    inside(word(gs,'Spirit',128,0),128,152)
    inside(word(gs,'Hit Rate',184,0),184,224)
    inside(word(gs,'100%',224,0),224,256)
    gs=check('names.g00.162',[('-99',False)]);inside(word(gs,'Ht Diff',8,0),8,40)
    assert word(gs,'-99',40,0)
    for value in ('ON','OFF'):
        gs=check('names.g00.166',[(value,False)],label='cut-in.'+value);inside(gs,8,64)
    gs=check('names.g01.032');inside(gs,8,248,128);previews['settings']=gs
    text=''.join(g[0] for g in gs)
    # Check each choice independently rather than finding only the first ON.
    for y in (0,16,32):
        line=[g for g in gs if g[2]==y]
        assert word(line,'ON',160,y) and word(line,'OFF',208,y)
    line=[g for g in gs if g[2]==48]
    assert word(line,'Stereo',160,48) and word(line,'Mono',208,48)
    for i in range(34,42):
        key=f'names.g01.{i:03d}';gs=check(key);inside(gs,8,248,48)
        before=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
        original=next(r['en'] for r in before if r['id']==key).replace('<NL>',' ').split()
        visible=' '.join(''.join(g[0] for g in gs if g[2]==y) for y in sorted({g[2] for g in gs}))
        assert visible.split()==original
    for i in range(128):
        gs=check('names.g00.225',[(str(i+1),False),(i,10)],label=f'completed-chapter.{i:03d}')
        inside(gs,8,248,16)
    for key in ('names.g00.212','names.g00.235'):
        gs=check(key,[('99',False),('99',False),('99',False),(42,10)])
        inside(gs,8,248,32)
    proof={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),
        'names_sha256':digest(names),'packed_names_sha256':digest(packed),
        'native_PRS_instructions':decoder_steps,'native_UI_instructions':steps,'native_UI_cases':len(cases),'cases':cases,
        'checks':['Native UI FC coordinates and nested D_NAMES lookups execute','Spirit/Prana/height/hit fields do not overlap their value anchors',
            'Settings choices at fixed x160/x208 and 16-pixel rows','All eight help paragraphs keep every word/punctuation and fit three measured lines',
            'All 128 complete chapter titles fit the completed-chapter strip','Native PRS output/size/guards/stack/register preservation pass'],
        'limits':['Parameter stream and one-tile context selection use bounded fixtures; caller/UI context assembly not executed',
            'Glyph raster uses advances; independent native raster proof is retained by identical executable/font bytes',
            'Actual GPU submission, navigation and in-game appearance remain unverified']}
    print(json.dumps({k:v for k,v in proof.items() if k!='cases'},indent=2),flush=True)
    if args.write_report:
        (out/'ui-layout-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
        for name,gs in previews.items():specimen(out/(name+'-layout-preview.png'),gs,font)
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
        manifest['ui_layout']['native_validation']='pass; '+str(len(cases))+' native UI cases plus original PRS decoder'
        manifest['ui_layout']['version']=VERSION
        manifest['ui_layout']['proof_sha256']=digest((out/'ui-layout-native-test.json').read_bytes())
        manifest['status']='UI fields/help native-verified; local packaging and in-game checks pending'
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
