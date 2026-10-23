"""Native library header parameters, real contexts/parser and shared scratch isolation.

Execute parameter reset/build/read, number conversion, nested name lookup,
context construction and header parsing. Glyph raster and GPU endpoints remain
bounded fixtures. Stops before portrait loading and final GPU submission.
"""
import argparse,json,struct
from collections import Counter
from build_library_header_patch import ROOT,VERSION,PRIOR,SCRATCH,SCRATCH_BYTES,compose,digest
from test_library_layout import fresh,run,LibraryCPU,BASE,STOP
from build_antialias_font import font_bytes
from build_font4x_patch import MEDIUM,SMALL
from rayblade_text import relative_target
from english_text_codec import decode
from check_native_text_components import verify
from test_ui_layouts import specimen

SHARED=0x8c400000
NAMES=0x8c900000
CAPACITY=0x20000
GLOBALS={0:0x8c1dbef4,1:0x8c1dbef8,2:0x8c1dbefc,3:0x8c1dbf00,4:0x8c1dbf04,5:0x8c1dbf08,6:0x8c1dbf0c,8:0x8c1dbf14,9:0x8c1dbf18,10:0x8c1dbf10,11:0x8c1dbf1c,12:0x8c1dbf48}


class HeaderCPU(LibraryCPU):
    def execute(self,pc,delay=False):
        op=self.read(pc,2)
        if op&0xff00==0xc700:
            self.reg[0]=((pc+4)&~3)+(op&255)*4;return pc+2
        if op&0xf0ff==0x0023:
            assert not delay
            target=(pc+4+self.reg[(op>>8)&15])&0xffffffff
            self.execute(pc+2,True);return target
        if pc==0x8c07b28e:
            small=bool(self.read(0x8c1f36ba,1)&64)
            i=(self.reg[4]-32)&127 if small else self.reg[4];chars=SMALL if small else MEDIUM
            assert i<len(chars),('Invalid header glyph',self.reg[4],small)
            self.glyphs.append((chars[i],self.read(0x8c1f36b6,2),self.read(0x8c1f36b8,2),small))
            self.write(0x8c1f36b6,self.read(0x8c1f36b6,2)+self.font[(0x20 if small else 0xa0)+i],2)
            return self.pr
        return super().execute(pc,delay)


def call(cpu,pc,*args,stop=STOP):
    cpu.reg[15]=0x8c701800;cpu.pr=STOP
    cpu.reg[4:4+len(args)]=args
    return run(cpu,pc,stop)


def setup(exe,font,paper,names):
    c=fresh(exe,font);c.__class__=HeaderCPU
    c.regions[2]=(SHARED-32,bytearray(b'\xa5'*(CAPACITY+64)))
    b,o=c.area(SHARED+0x210,len(paper));b[o:o+len(paper)]=paper
    c.regions.append((NAMES,bytearray(names)))
    for group,addr in GLOBALS.items():c.write(addr,NAMES+relative_target(names,group*4),4)
    c.write(0x8c1dbf4c,SHARED,4);c.write(0x8c1f0cf4,SHARED,4);c.write(SHARED+8,SHARED+0x210,4)
    return c


def preserved(c,paper):
    b,o=c.area(SHARED+0x210,len(paper));assert bytes(b[o:o+len(paper)])==paper
    b,o=c.area(SHARED-32,CAPACITY+64)
    assert b[:32]==b'\xa5'*32 and b[-32:]==b'\xa5'*32


def params(c,kind,index):
    c.write(SHARED+12,index,2);c.write(0x8c1dbe74,0,4)
    return call(c,0x8c064920 if kind=='character' else 0x8c064bb0,
        stop=0x8c064ac4 if kind=='character' else 0x8c064c70)


def main():
    global VERSION
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--version',default=VERSION,choices=['0.1.19','0.1.21']);ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    print('Plan: reproduce old overlap, all 144 character/128 unit name-table slots, actual constructed headers and native scratch ring/decimal wrap checks.',flush=True)
    if not args.verify:print('DRY RUN: no execution/report');return
    out=ROOT/'work/output'/VERSION;prior=ROOT/'work/output'/PRIOR
    component_compose=compose
    if VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose as component_compose
    files,manifest,_=component_compose()
    for key in ('1ST_READ.BIN','WIN00.AFS','text/D_NAMES.BIN','text/D_NAMES.en.dec.bin'):
        assert files[key]==(out/key).read_bytes()
    exe=files['1ST_READ.BIN'];_,font=font_bytes(files['WIN00.AFS']);paper=files['text/D_PAPER.en.dec.bin'];names=files['text/D_NAMES.en.dec.bin']
    prs=verify(exe,files['text/D_NAMES.BIN'],names,65536)
    old=setup((prior/'1ST_READ.BIN').read_bytes(),font,paper,names)
    old_steps=call(old,0x8c03af90)+call(old,0x8c03b030,0xb01)
    b,o=old.area(SHARED+0x210,len(paper));changed=[i for i,(a,z) in enumerate(zip(paper,b[o:o+len(paper)])) if a!=z]
    assert changed==[0xeff0,0xeff1]
    source=json.loads((ROOT/'work/source/library/entries.json').read_text('utf-8'))
    english={r['id']:r['en'] for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    metrics=json.loads((out/'antialias-font-report.json').read_text('utf-8'))['metrics']
    bounds={bank:{r['character']:r['packed_mask_bounds'] for r in val['glyphs']} for bank,val in metrics.items()}
    counts=Counter();steps=Counter();cases=[];previews={};geometry=[]
    for kind,total,script in [('character',144,0xf62d),('mech',128,0xf7a7)]:
        c=setup(exe,font,paper,names);c.write(0x8c1dbe24,BASE+script+1,4)
        steps['constructor']+=call(c,0x8c07d978)
        ctx=0x8c1f0cf8
        assert [c.read(ctx+i,2) for i in (0x30,0x32,0x4e,0x50,0x52,0x54)]==[40,40,256,64 if kind=='character' else 32,1,3 if kind=='character' else 2]
        # Same visual frame as description viewer; header is inside its x40..280 ink area.
        geometry.append({'kind':kind,'script':hex(script),'origin':[40,40],'logical_surface':[256,64 if kind=='character' else 32],'physical_surface':[c.read(0x8cb00000+28,2),c.read(0x8cb00000+30,2)],'ink_width':240})
        for index in range(total):
            steps['parameters']+=params(c,kind,index);preserved(c,paper)
            assert c.read(0x8c1db4ec,4)==SHARED+SCRATCH
            queued=c.read(0x8c1db4e4,2);assert queued in (6,10,16)
            steps['clear']+=call(c,0x8c078a30,c.read(0x8c1f24cc,1))
            c.glyphs=[]
            steps['parser']+=call(c,0x8c076afc,4,135 if kind=='character' else 137,stop=0x8c076bac)
            assert c.read(0x8c1db4e4,2)==0,(kind,index,c.read(0x8c1db4e4,2));preserved(c,paper)
            name=english[f'names.g{11 if kind=="character" else 3:02d}.{index:03d}']
            text=''.join(g[0] for g in c.glyphs)
            assert text.startswith(name)
            lines={y:''.join(g[0] for g in c.glyphs if g[2]==y) for y in sorted({g[2] for g in c.glyphs})}
            for ch,x,y,small in c.glyphs:
                box=bounds['small' if small else 'medium'][ch]
                if box:
                    assert 0<=x+box[0]/4 and x+box[2]/4+1<=240,('Header ink overflow',kind,index,ch,x,box)
                    assert 0<=y+box[1]/4 and y+box[3]/4+1<=(48 if kind=='character' else 32)
                if kind=='character':
                    limit=(192 if x<192 else 240) if y==0 else (168 if x<168 else 240) if y==16 else 120 if x<120 else 192 if x<192 else 240
                else:limit=(136 if x<136 else 240) if y==0 else (96 if x<96 else 240)
                if box:assert x+box[2]/4+1<=limit,('Header field overlap',kind,index,ch,x,limit)
            e=source[index if kind=='character' else 160+index]
            if kind=='mech':
                a,z,scale=e['header_fields_raw']
                def decimal(v):return f'{v//10}.{v%10}' if not scale else str(v)+'0'*(scale-1)+'.0'
                assert lines[16]=='Length '+decimal(a)+'mWeight '+decimal(z)+'t',(index,lines,e['header_fields_raw'])
            else:
                age,h,w,bust,waist,hips=e['header_bytes']
                assert lines[0]==name+(str(age).rjust(2) if age else '??')+' years',(index,lines[0],name,age)
                # Native integer formatter pads height and weight to three columns.
                assert lines[16]=='Height '+(str(h).rjust(3) if h else '???')+'cmWeight '+(str(w).rjust(3) if w else '???')+'kg'
                assert lines.get(32,'')==('Bust'+str(bust).rjust(3)+'Waist'+str(waist).rjust(3)+'Hips'+str(hips).rjust(3) if bust else '')
            counts[kind]+=1;cases.append({'kind':kind,'index':index,'queued_parameter_bytes':queued,'glyphs':len(c.glyphs)})
            if index==1:previews[kind]=list(c.glyphs)
        print(kind,total,'headers pass',flush=True)
    # Stress the native common parameter queue at all 1024 bytes and across wraps.
    c=setup(exe,font,paper,names);steps['scratch_stress']+=call(c,0x8c03af90)
    for cycle in range(3):
        expected=bytes((i+cycle*47)&255 for i in range(1024))
        for value in expected:steps['scratch_stress']+=call(c,0x8c03afe4,value)
        assert c.read(0x8c1db4e4,2)==1024
        for value in expected:
            steps['scratch_stress']+=call(c,0x8c03c364);assert c.reg[0]&255==value
        assert c.read(0x8c1db4e4,2)==0;preserved(c,paper)
    # Repeated native decimal generation exercises both dot literals, offset
    # table wrap and the 1920-byte text scratch wrap; consume its two-byte handle.
    decimal_cases=0
    for scale in range(4):
        for value in [0,1,9,10,99,100,999,1000,9999,10000,65535]*12:
            steps['decimal_stress']+=call(c,0x8c03bae4,value,scale)
            steps['decimal_stress']+=call(c,0x8c03c364);lo=c.reg[0]&255
            steps['decimal_stress']+=call(c,0x8c03c364);hi=c.reg[0]&255
            handle=lo|(hi<<8);assert 0x1000<=handle<0x1200 and not handle&1
            slot=SHARED+SCRATCH+0x400+handle-0x1000;offset=c.read(slot,2);pointer=SHARED+SCRATCH+0x600+offset;raw=bytearray()
            while True:
                value_byte=c.read(pointer+len(raw),1);raw.append(value_byte)
                if value_byte==255:break
                assert len(raw)<16
            actual,_=decode(bytes(raw));expected=f'{value//10}.{value%10}' if not scale else str(value)+'0'*(scale-1)+'.0'
            assert actual==expected,(scale,value,actual,expected)
            assert c.read(0x8c1db4e4,2)==0;preserved(c,paper);decimal_cases+=1
    proof={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'names_sha256':digest(names),'library_sha256':digest(paper),'geometry':geometry,'counts':dict(counts),'cases':cases,'native_instructions':dict(steps),'native_PRS_instructions':prs,
        'old_bug_reproduction':{'build':PRIOR,'native_instructions':old_steps,'overwritten_library_offsets':[hex(i) for i in changed],'affected_profile':'library.character.026'},
        'scratch':manifest['library_header'],'queue_bytes_roundtripped':3072,'decimal_cases':decimal_cases,
        'checks':['All valid character/unit name-table slots, source metadata, unknown values and nested measurements parsed through actual constructed contexts','Complete years label, dynamic decimal points and individual field ink bounds pass','Expanded library and outer allocation guards unchanged after every header and queue/decimal stress case'],
        'limits':['Header preparation stops before portrait loading; final GPU submit is not executed','Glyph raster and graphics/allocation endpoints are bounded fixtures','Name-table slots include unused entries; complete live unlock/menu routing, GPU appearance and long-session gameplay remain unverified']}
    print(json.dumps({k:v for k,v in proof.items() if k!='cases'},indent=2),flush=True)
    if args.write_report:
        p=out/'library-header-native-test.json';p.write_text(json.dumps(proof,indent=2)+'\n','utf-8')
        for kind,gs in previews.items():specimen(out/f'library-{kind}-header-preview.png',gs,font)
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m['library_header'].update(native_validation='pass; 272 real-context headers plus native scratch/decimal wrap stress',proof_sha256=digest(p.read_bytes()));(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
