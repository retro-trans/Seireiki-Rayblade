"""Execute inclusive tile clipping and selection setup on the actual SH-4 code."""
import argparse,json,struct
from build_battle_clip_fix import ROOT,VERSION,PRIOR,ENTRY,LINE_ENTRY,LINE_POINTERS,BAR_EDITS,compose,digest
from test_native_movie_font import DrawCPU,STOP,bits,value,run

class ClipCPU(DrawCPU):
    def execute(self,pc,delay=False):
        w=self.read(pc,2)
        if w&0xf0ff==0xf03d:
            self.fpul=int(value(self.fr[w>>8&15]))&0xffffffff;return pc+2
        if w&0xf0ff==0x005a:
            self.reg[w>>8&15]=self.fpul;return pc+2
        if w&0xf0ff in (0xf08d,0xf09d):
            self.fr[w>>8&15]=bits(1. if w&0xf0ff==0xf09d else 0.);return pc+2
        if w&0xf0ff==0xf04d:
            self.fr[w>>8&15]^=0x80000000;return pc+2
        if w&0xf00f==0xf00e:
            n,m=w>>8&15,w>>4&15;self.fr[n]=bits(value(self.fr[0])*value(self.fr[m])+value(self.fr[n]));return pc+2
        if pc in (0x8c0c7d34,0x8c0c8a04,0x8c0c7d92,0x8c0d0340,0x8c0d0b00,0x8c093ba4):
            if pc==0x8c093ba4:
                n=self.reg[0];src=self.reg[2];dst=self.reg[1]
                for i in range(n):self.write(dst+i,self.read(src+i,1),1)
            return self.pr
        if pc in (0x8c0c7df0,0x8c0c7ec2):self.reg[0]=0xe0000000;return self.pr
        if pc==0x8c0c89bc:return self.pr
        if pc==0x8c0d2fea:
            self.tiles.append([self.reg[6],self.reg[7],self.read(self.reg[15],4),self.read(self.reg[15]+4,4)])
            return self.pr
        if pc==0x8c0a7c06:
            self.rects.append([value(self.read(self.reg[5]+i*4,4)) for i in range(4)])
            # Continue through the real SDK conversion and state writes.
            return super(DrawCPU,self).execute(pc,delay)
        if pc==0x8c0a93bc:
            p=self.reg[4];count=self.reg[5]*self.read(p+12,4)
            self.lines.append([value(self.read(self.read(p,4)+i*4,4)) for i in range(count*2)])
            return self.pr
        return super().execute(pc,delay)

def fresh(exe):
    c=ClipCPU(exe,b'',0,0);r=bytearray(0x1000000);r[0x10000:0x10000+len(exe)]=exe
    c.regions=[(0x8c000000,r),(0xe0000000,bytearray(0x10000))]
    c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(i+.25) for i in range(16)];c.fpul=0;c.visited=set();c.rects=[];c.tiles=[];c.lines=[]
    c.write(0x8c419a38,0x8c600000,4);c.write(0x8c119fac,0,4)
    for p in range(0x8c119f30,0x8c119f44,4):c.write(p,1,4)
    for p,f in zip(range(0x8c419324,0x8c419330,4),(0.,640.,480.)):c.write(p,bits(f),4)
    return c

def check():
    exe,component=compose();old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();steps=0;rects=[];bars=[];lines=[]
    for box in [(0.,0.,4.,6.),(5.,0.,9.,6.),(0.,0.,9.,6.),(0.,0.,9.,3.),(0.,4.,9.,6.),(1.,2.,7.,5.)]:
      for mode in (0,1,2):
        c=fresh(exe);p=0x8cf00000;c.reg[4:6]=[mode,p];raw=struct.pack('<4f',*box)
        c.regions[0][1][p&0xffffff:(p&0xffffff)+16]=raw
        steps+=run(c,0x8c07b77c,100000)
        want=[v*2+(1 if mode==2 and i>=2 else 0) for i,v in enumerate(box)]
        assert c.rects==[want],(mode,box,c.rects,want)
        assert c.regions[0][1][p&0xffffff:(p&0xffffff)+16]==raw
        if mode==2:
            pixel=[value(c.read(0x8c419340+i*4,4)) for i in range(4)]
            expected=[want[0]*32,want[1]*32,want[2]*32+31,want[3]*32+31]
            assert pixel==expected,(pixel,expected)
            assert c.tiles[-1]==[int(v) for v in want],c.tiles
        rects.append({'mode':mode,'source_tiles':box,'submitted_tiles':want,'pixel_bounds':pixel if mode==2 else 'full-screen SDK fallback retained'})
    for pos,oldwidth,newwidth,label in BAR_EDITS:
        opcode=pos-8
        assert exe[opcode:opcode+2]==b'\x8a\x10'
        ctx=exe[opcode+2];outputs=[]
        for image in (old,exe):
            c=fresh(image);c.write(0x8c1dbe24,0x8c010000+opcode+1,4);c.pc=0x8c07dd3c
            for n in range(2000):
                if c.pc==0x8c07deaa:break
                c.pc=c.execute(c.pc)
            else:raise AssertionError('Selection setup limit')
            steps+=n;outputs.append([c.read(0x8c1f1e38+208*ctx+i,2) for i in range(0x20,0x3a,2)])
        a,b=outputs;assert b[9]==newwidth and a[9]==oldwidth,(label,a,b)
        assert all(x==y for i,(x,y) in enumerate(zip(a,b)) if i!=9)
        bars.append({'label':label,'width_before':oldwidth*8,'width_after':newwidth*8,'other_selection_fields_exact':True})
    for site in LINE_POINTERS:
      for xy in [(160.,0.,160.,256.),(-8.5,12.,318.,232.)]:
        c=fresh(exe);p=0x8cf00000;q=p+32;c.reg[4:7]=[p,1,0x60];c.fr[4]=bits(.25)
        for i,v in enumerate((q,q+0x100,q+0x200,2)):c.write(p+i*4,v,4)
        for i,v in enumerate(xy):c.write(q+i*4,bits(v),4)
        raw=bytes(c.regions[0][1][p&0xffffff:(p&0xffffff)+64]);entry=struct.unpack_from('<I',exe,site)[0];assert entry==LINE_ENTRY
        steps+=run(c,entry,100000);assert c.lines==[[v*2 for v in xy]]
        assert bytes(c.regions[0][1][p&0xffffff:(p&0xffffff)+64])==raw
        lines.append({'site':hex(site),'source':xy,'output':c.lines[0]})
    assert exe[0x6baa4:0x6baa8]==old[0x6baa4:0x6baa8] # adapter callee must not recurse
    stage=json.loads((ROOT/'work/output/0.7.22/stage-six-text-component.json').read_text('utf-8'))
    for e in stage['edits']:
        p=int(e['file_offset'],16);n=e['bytes'];assert exe[p:p+n]==old[p:p+n]
    return {**component,'clip_cases':rects,'selection_cases':bars,'line_cases':lines,'SH4_instructions':steps,
        'scope':'Real clip wrapper and SDK tile-to-pixel bounds execute; GPU/material submission and byte-copy endpoint are bounded. Actual selection field parser and line adapter execute. Separate live battle review is required.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args();r=check();print(json.dumps(r,indent=2))
    if a.write:(ROOT/'work/output'/VERSION/'battle-clip-native-test.json').write_text(json.dumps(r,indent=2)+'\n','utf-8')
