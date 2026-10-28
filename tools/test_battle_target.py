"""Execute animation adapters and original SDK vertex packet emission."""
import argparse,json,struct
from build_battle_target_fix import ROOT,VERSION,PRIOR,compose,RAW_SITES,LINE_SITES,digest
from test_native_movie_font import DrawCPU,STOP,bits,value,run


class TargetCPU(DrawCPU):
    def execute(self,pc,delay=False):
        w=self.read(pc,2)
        if w&0xf0ff==0x0083:
            p=self.reg[w>>8&15]
            if 0xe0000000<=p<0xe0010000:
                self.packets.append(bytes(self.read(p+i,1) for i in range(32)))
            return pc+2
        if pc in (0x8c0c7d34,0x8c0c8a04,0x8c0c8c0a,0x8c0c7d92):
            self.headers.append((pc,self.reg[4]));return self.pr
        if pc in (0x8c0c7ec2,0x8c0c7df0,0x8c0c7ff8,0x8c0c7f4c):
            self.reg[0]=0xe0000000;return self.pr
        if pc==0x8c0c89bc:
            self.commit=self.reg[4];return self.pr
        if pc==0x8c0a93bc:
            p=self.reg[4];count=self.reg[5]*self.read(p+12,4)
            self.lines.append({'tail':[self.read(p+i,4) for i in (4,8,12)],'count':self.reg[5],'flags':self.reg[6],
                'depth':self.fr[4],'xy':[value(self.read(self.read(p,4)+j*4,4)) for j in range(count*2)]})
            return self.pr
        return super().execute(pc,delay)


def fresh(exe):
    c=TargetCPU(exe,b'',0,0)
    c.regions=[(0x8c010000,bytearray(exe)),(0x8cf00000,bytearray(b'\xa5'*0x10000)),
        (0x8cfe0000,bytearray(b'\xa5'*0x10000)),(0xe0000000,bytearray(b'\xa5'*0x10000))]
    c.reg[15]=0x8cfe8000;c.pr=STOP;c.fr=[bits(i+.25) for i in range(16)];c.fpul=0;c.visited=set();c.packets=[];c.headers=[];c.lines=[];c.commit=None
    return c


def check():
    exe,component=compose();old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();steps=0;cases=[]
    for callee,(stride,sites) in RAW_SITES.items():
        for count in (3,4,8,17):
          for blend in (0,1):
            for x,y in ((158.,98.),(-15.25,260.5)):
                payload=b''
                for i in range(count):
                    xy=[x+i*1.25,y-i*.75];z=-1./(128+i)
                    payload+=struct.pack('<5fI',*xy,z,i/32.,i/16.,0x806df439+i) if stride==24 else struct.pack('<3fI',*xy,z,0x806df439+i)
                results=[]
                for image,entry in ((old,callee),(exe,struct.unpack_from('<I',exe,sites[0])[0])):
                    c=fresh(image);c.regions[1][1][0:len(payload)]=payload;c.reg[4:8]=[0x8cf00000,count,7 if stride==24 else blend,blend]
                    before=bytes(c.regions[1][1]);steps+=run(c,entry,100000)
                    assert bytes(c.regions[1][1])==before and len(c.packets)==count
                    # The setup entry sees the intentionally copied input
                    # pointer. Material/texture values and commit stay exact.
                    results.append((c.packets,c.commit,[h for h in c.headers if h[0]!=0x8c0c7d34]))
                first,last=results;assert first[1:]==last[1:]
                for a,b in zip(first[0],last[0]):
                    want=bytearray(a)
                    for p in (4,8):struct.pack_into('<f',want,p,struct.unpack_from('<f',a,p)[0]*2)
                    assert b==want
                cases.append({'vertex_stride':stride,'count':count,'blend':blend,'center':[x,y],'SDK_packets':count,'XY_only_doubled':True})
    fixtures=[]
    entry=struct.unpack_from('<I',exe,LINE_SITES[0])[0]
    for count,verts in ((1,2),(4,2),(2,3),(0,2)):
        outputs=[]
        for image,at in ((old,0x8c0a93bc),(exe,entry)):
            c=fresh(image);p=0x8cf00000;q=p+32;c.reg[4:7]=[p,count,0x60]
            c.regions[1][1][:16]=struct.pack('<4I',q,q+0x1000,q+0x2000,verts)
            pts=[158.+i*.25 if i%2==0 else 98.-i*.5 for i in range(count*verts*2)]
            c.regions[1][1][32:32+len(pts)*4]=struct.pack('<'+'f'*len(pts),*pts)
            before=bytes(c.regions[1][1]);steps+=run(c,at,100000);assert bytes(c.regions[1][1])==before;outputs.append(c.lines[0])
        a,b=outputs;assert b=={**a,'xy':[v*2 for v in a['xy']]};fixtures.append({'polygons':count,'vertices_each':verts,'XY_only_doubled':True})
    assert exe[0x6b900:0x6b998]==old[0x6b900:0x6b998] # startup, stock budget, grid adapter
    return {**component,'SDK_raw_packet_cases':len(cases),'SDK_emitted_packets':sum(r['SDK_packets'] for r in cases),
        'raw_cases':cases,'line_descriptor_cases':fixtures,'SH4_instructions':steps,
        'checks':['Original SDK strip-to-PVR vertex emission executes','Only packet X/Y change; Z, UV, ARGB, primitive commands and output pointer exact',
            'Original blend/texture header arguments retained','Source arrays, callee-saved registers, FPU registers and stack restored',
            '0.7.19 memory literal/startup and 0.7.20 grid code byte-exact'],
        'scope':'GPU submission/material allocation endpoints are bounded stubs; SDK raw vertex emission is actual. Line endpoint records descriptors. Live reticle and combat review separate.'}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args();r=check()
    print(json.dumps({k:v for k,v in r.items() if k!='raw_cases'},indent=2))
    if a.write:(ROOT/'work/output'/VERSION/'battle-target-native-test.json').write_text(json.dumps(r,indent=2)+'\n','utf-8')
