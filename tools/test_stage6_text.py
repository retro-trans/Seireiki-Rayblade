"""Execute the SH-4 lossless text encoder and the actual SDK VQ allocator."""
import argparse,json,struct
import numpy as np
from build_stage6_text_fix import ROOT,PRIOR,VERSION,ENTRY,ALLOC,VALIDATE,compose,digest
from test_native_movie_font import DrawCPU,STOP,bits,run
from audit_texture_archive import untwiddle_indices

PTR=0x8c800000

class CodecCPU(DrawCPU):
    def execute(self,pc,delay=False):
        if pc==0x8c093e80:
            p,value,size=self.reg[4:7];assert value==0 and size==2048
            off=p&0xffffff;self.regions[0][1][off:off+size]=bytes(size);return self.pr
        if pc==0x8c0a437a:
            self.flushes.append(tuple(self.reg[4:6]));return self.pr
        if pc==0x8c03f748:
            self.heap.append(tuple(self.reg[4:6]));self.reg[0]=PTR;return self.pr
        return super().execute(pc,delay)

def fresh(exe,ram=None):
    c=CodecCPU(exe,b'',0,0);raw=bytearray(ram) if ram is not None else bytearray(0x1000000)
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    if ram is None:raw[0x10000:0x10000+len(exe)]=exe
    else:
        for i,(x,y) in enumerate(zip(old,exe)):
            if x!=y:raw[0x10000+i]=y
    c.regions=[(0x8c000000,raw)];c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set();c.heap=[];c.flushes=[]
    return c

def decode(data,w,h):
    table=np.frombuffer(data[:2048],dtype='<u2').reshape(256,4)
    indices=np.frombuffer(data[2048:],dtype=np.uint8)[untwiddle_indices(w//2,h//2)]
    blocks=table[indices];a=np.zeros((h,w),dtype='<u2')
    a[0::2,0::2]=blocks[:,:,0];a[1::2,0::2]=blocks[:,:,1]
    a[0::2,1::2]=blocks[:,:,2];a[1::2,1::2]=blocks[:,:,3]
    return a.tobytes()

def encode_case(exe,plane,w,h,expect=True,fmt=0x902):
    c=fresh(exe);size=len(plane);assert size==w*h*2
    head=bytearray(32);head[:4]=b'GBIX';struct.pack_into('<3I',head,4,8,0x401,0x101)
    head[16:20]=b'PVRT';struct.pack_into('<IIHH',head,20,size,fmt,w,h)
    original=bytes(head)+plane;cap=len(original)+((size//8+2080+2047)&~2047)
    off=PTR&0xffffff;c.regions[0][1][off:off+cap+64]=b'\xa5'*(cap+64);c.regions[0][1][off:off+len(original)]=original
    c.reg[4]=PTR;n=run(c,ENTRY,limit=12000000);p=c.reg[0]
    assert bytes(c.regions[0][1][off:off+len(original)])==original
    assert bytes(c.regions[0][1][off+cap:off+cap+64])==b'\xa5'*64
    if expect:
        assert p==PTR+len(original) and c.read(p+24,4)==0x302
        used=c.read(p+20,4);assert used==2048+w*h//4
        payload=bytes(c.regions[0][1][(p&0xffffff)+32:(p&0xffffff)+32+used])
        assert decode(payload,w,h)==plane
        assert c.flushes==[(p,used+32)]
    else:assert p==PTR and not c.flushes;used=size
    return c,n,{'physical':[w,h],'RGB_bytes':size,'upload_bytes':used,'lossless':True,'compressed':p!=PTR,'instructions':n}

def check():
    exe,component=compose();steps=0;cases=[]
    # Actual generated dialogue plane, plus rectangular/square layout witnesses.
    ram=(ROOT/'work/source/issue-1/current-0721.ram').read_bytes();p=struct.unpack_from('<I',ram,0x1f0cf8+0x44)[0]&0xffffff
    w,h=struct.unpack_from('<HH',ram,p+28);plane=ram[p+32:p+32+w*h*2]
    c,n,row=encode_case(exe,plane,w,h);steps+=n;row['case']='Actual S0c8 dialogue';cases.append(row)
    failed_ram=(ROOT/'work/source/issue-1/white-bridge-0721.ram').read_bytes()
    failed_ptr=struct.unpack_from('<I',failed_ram,0x1f0cf8+92+0x44)[0]&0xffffff
    fw,fh=struct.unpack_from('<HH',failed_ram,failed_ptr+28)
    failed_plane=failed_ram[failed_ptr+32:failed_ptr+32+fw*fh*2]
    _,n,row=encode_case(exe,failed_plane,fw,fh);steps+=n;row['case']='Actual white-panel source at S0c8 VM 0x8c010cbe';cases.append(row)
    for w,h in ((64,32),(32,128),(64,64)):
        a=np.zeros((h,w),dtype='<u2')
        for y in range(h):
            for x in range(w):a[y,x]=(0xffff,0xbfff,0x5fff,0xf000,0)[(x%4+3*(y%4))%5]
        _,n,row=encode_case(exe,a.tobytes(),w,h);steps+=n;row['case']='Rectangular twiddle and exact 16-bit values';cases.append(row)
    # More than 256 distinct blocks must retain the complete uncompressed source.
    a=np.arange(64*64,dtype='<u2').reshape(64,64)
    _,n,row=encode_case(exe,a.tobytes(),64,64,False);steps+=n;row['case']='Dictionary overflow fallback';cases.append(row)
    _,n,row=encode_case(exe,bytes(16*16*2),16,16,False);steps+=n;row['case']='Small surface fallback';cases.append(row)
    _,n,row=encode_case(exe,bytes(64*32*2),64,32,False,0x900);steps+=n;row['case']='Unchanged non-ARGB4444 source';cases.append(row)
    for w,h in ((96,64),(4,1024)):
        _,n,row=encode_case(exe,bytes(w*h*2),w,h,False);steps+=n;row['case']='Invalid VQ dimensions retain original source';cases.append(row)
    # Append modifies the original editable RGB surface, then re-encodes it.
    c,n,row=encode_case(exe,bytes(64*32*2),64,32);steps+=n
    c.write(PTR+32,0xbfff,2);updated=bytes(c.regions[0][1][(PTR&0xffffff)+32:(PTR&0xffffff)+32+4096])
    c.reg[4]=PTR;c.pr=STOP;steps+=run(c,ENTRY,limit=12000000);out=c.reg[0];used=c.read(out+20,4)
    assert decode(bytes(c.regions[0][1][(out&0xffffff)+32:(out&0xffffff)+32+used]),64,32)==updated
    # Execute the patched worker entry through its original resume address.
    c.reg[3]=PTR;c.pr=STOP;stack=c.reg[15];saved=c.reg[4:];c.pc=0x8c032d1a
    for n in range(12000000):
        if c.pc==0x8c032d68:break
        c.pc=c.execute(c.pc)
    else:raise AssertionError('Upload worker did not resume')
    steps+=n;out=c.read(0x8c171704,4)
    assert c.reg[4:]==saved and c.reg[15]==stack and c.pr==STOP
    assert out==PTR+4096+32 and c.read(0x8c1716f8,4)==(2560+32+2047)//2048
    assert decode(bytes(c.regions[0][1][(out&0xffffff)+32:(out&0xffffff)+32+2560]),64,32)==updated
    # Run the real text allocator and verify its retained RGB metadata and tail capacity.
    labels=json.loads((ROOT/'work/output'/PRIOR/'font-mode-details.json').read_text('utf-8'))['labels']
    allocations=[]
    for w,h in ((256,64),(256,128),(128,128),(512,64)):
        c=fresh(exe);ctx=0x8cf60000;c.reg[8]=ctx;c.write(ctx+10,w,2);c.write(ctx+12,h,2)
        steps+=run(c,labels['allocate'],limit=100000);assert c.reg[0]==PTR and len(c.heap)==1
        size=c.read(PTR+20,4);expected=size+32+((size//8+2080+2047)&~2047)
        assert c.heap==[(expected,0)] and c.read(PTR+12,2)==0x101
        allocations.append({'logical':[w,h],'RGB_bytes':size,'allocation_bytes':expected})
    # Reproduce the real failed allocation, then fit the exact VQ source.
    gpu=[]
    for fmt,initializer in ((0x902,0x8c0e1c4c),(0x302,VALIDATE)):
        c=fresh(exe,failed_ram);p=0x8cffd100;c.reg[4:8]=[p,1024,128,fmt];c.pr=STOP;steps+=run(c,initializer)
        assert c.reg[0]==0;size=c.read(p+20,4)
        c.reg[4:6]=[size,p];c.pr=STOP;steps+=run(c,0x8c0e52a0,limit=100000)
        gpu.append({'format':hex(fmt),'bytes':size,'result':c.reg[0]})
    assert gpu==[{'format':'0x902','bytes':262144,'result':3},{'format':'0x302','bytes':34816,'result':0}],gpu
    guard_cases=0
    for fmt in (0x900,0x902,0x100,0x302,0x301,0x402):
      for w,h in ((8,8),(64,32),(1024,128),(32,1024),(7,16),(16,0),(2048,32),(256,256)):
        statuses=[];descriptors=[]
        for entry in (0x8c0e1c4c,VALIDATE):
            c=fresh(exe);p=0x8cffd100;c.reg[4:8]=[p,w,h,fmt];c.pr=STOP;steps+=run(c,entry)
            statuses.append(c.reg[0]);descriptors.append(bytes(c.regions[0][1][(p&0xffffff):(p&0xffffff)+40]))
        valid=all(8<=n<=1024 and not n&(n-1) for n in (w,h))
        assert statuses[1]==(0 if fmt==0x302 and valid else statuses[0])
        assert descriptors[0]==descriptors[1];guard_cases+=1
    return {**component,'encoder_cases':cases,'append_reencoding':'exact','text_allocations':allocations,
        'actual_failed_Stage6_SDK_allocation_cases':gpu,'upload_worker_pointer_count_resume_ABI':'pass',
        'SDK_admission_cases':guard_cases,'SH4_instructions':steps,
        'scope':'Native encoder and SDK size/allocation execute. Memory-clear/cache-flush/heap endpoints are bounded fixtures. GPU and Stage 6 replay require separate live checks.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.parse_args();print(json.dumps(check(),indent=2))

if __name__=='__main__':main()
