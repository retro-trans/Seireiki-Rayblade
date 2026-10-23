"""Execute the actual native HD font patch in the SH-4 interpreter.

Independent pixel reference, allocation/budget/failure tests, PVR header and
DMA-size checks. No game files written. Does not replace runtime playtesting.
"""
import struct
from pathlib import Path
from build_font4x_patch import (ROOT,BASE,SMALL,MEDIUM,SMALL_Q,MEDIUM_Q,
    SURFACE_BUDGET,build)
from test_font_patch import CPU

TEX=0x8c800000


class HDCPU(CPU):
    def __init__(self,exe,font,glyph=65,flags=0x40,w=256,h=32,ex=2,ey=2):
        super().__init__(exe,font,glyph,flags)
        self.regions[3]=(TEX,bytearray([0x23,0x81])*((w<<ex)*(h<<ey)+64))
        self.regions.append((0x8c1f0cf8,bytearray(48*92)))
        self.write(0x8c1f36ac,TEX+32,4)
        self.write(0x8c1f36b0,w,2);self.write(0x8c1f36b2,h,2)
        self.write(TEX+12,ex,1);self.write(TEX+13,ey,1)
        self.write(TEX+20,(w<<ex)*(h<<ey)*2,4)
        self.write(TEX+28,w<<ex,2);self.write(TEX+30,h<<ey,2)
        self.calls=[];self.fail_allocations=0;self.heap=0x8cb00000

    def execute(self,pc,delay=False):
        if pc==0x8c03f748:
            size=self.reg[4];self.calls.append(('malloc',size))
            if self.fail_allocations:
                self.fail_allocations-=1;self.reg[0]=0
            else:
                address=self.heap;self.heap+=size+128
                self.regions.append((address,bytearray([0xcc])*size));self.reg[0]=address
            return self.pr
        if pc==0x8c093e80:
            address,value,count=self.reg[4:7]
            block,off=self.area(address,count);block[off:off+count]=bytes([value&255])*count
            self.calls.append(('memset',address,count));return self.pr
        if pc==0x8c0a437a:
            self.calls.append(('flush',self.reg[4],self.reg[5]));return self.pr
        return super().execute(pc,delay)

    def run_until(self,stop=0xdead0000,limit=150000):
        initial=self.reg[8:]
        for count in range(limit):
            if self.pc==stop:
                assert self.reg[8:]==initial,'Callee-saved registers/stack changed'
                return count
            self.pc=self.execute(self.pc)
        raise ValueError('Instruction limit exceeded at {:x}'.format(self.pc))


def expected_pixels(cpu,font,glyph,flags):
    out=bytearray(cpu.regions[3][1]);w=cpu.read(TEX+28,2)
    ex=cpu.read(TEX+12,1);ey=cpu.read(TEX+13,1);sx=1<<ex;sy=1<<ey
    if flags&64:
        idx=(glyph-32)&127;idx=idx if idx<len(SMALL) else SMALL_Q
        height=8;start=0x200+idx*128;advance=font[0x20+idx]
    else:
        idx=glyph&65535;idx=idx if idx<len(MEDIUM) else MEDIUM_Q
        height=16;start=0x4200+idx*256;advance=font[0xa0+idx]
    color=cpu.read(BASE+0x880a8+2+(flags&14)*2,2)
    for y in range(height*sy):
        row=struct.unpack_from('<I',font,start+(y*4//sy)*4)[0]
        for x in range(8*sx):
            bit=row & (1<<(31-x*4//sx))
            p=32+((4*sy+y)*w+12*sx+x)*2
            if flags&128:struct.pack_into('<H',out,p+sx*2,0x8000 if bit else 0)
            if bit:struct.pack_into('<H',out,p,color)
    return out,advance


def main():
    files,_,_,manifest=build(Path('C:/Windows/Fonts/tahoma.ttf'))
    exe=files['1ST_READ.BIN'];afs=files['WIN00.AFS'];off,length=struct.unpack_from('<II',afs,8);font=afs[off:off+length]
    symbols={k:int(v,16) for k,v in manifest['symbols'].items()}
    cases=[(32+i,0x40 | (0x80 if i%2 else 0),256,32,2,2) for i,c in enumerate(SMALL)]
    cases += [(i,0x80 if i%2 else 0,512,32,1,2) for i in range(len(MEDIUM))]
    for ex,ey in ((0,0),(1,1),(2,1),(1,0),(0,2)):
        for glyph,flags in ((73,0xc2),(105,0x42),(9,0x82),(35,2),(3327,0),(159,0x40),
                            (len(MEDIUM),0),(32+len(SMALL),0x40)):
            cases.append((glyph,flags,256,32,ex,ey))
    steps=0
    for glyph,flags,w,h,ex,ey in cases:
        cpu=HDCPU(exe,font,glyph,flags,w,h,ex,ey)
        expected,advance=expected_pixels(cpu,font,glyph,flags)
        steps+=cpu.run_until()
        assert cpu.regions[3][1]==expected,'Pixel mismatch '+str((glyph,flags,ex,ey))
        assert cpu.read(0x8c1f36b6,2)==12+advance,'Logical cursor advance changed'
    allocation_cases=[(32,32,0,0),(256,64,0,0),(512,64,0,0),(512,512,0,0),
                      (256,64,1800000,0),(256,64,SURFACE_BUDGET,0),(256,64,0,2),
                      (1024,32,0,0),(32,1024,0,0),(1024,1024,0,0),
                      (320,64,0,0),(64,513,0,0)]
    for w,h,occupied,failures in allocation_cases:
        cpu=HDCPU(exe,font);cpu.reg[8]=0x8c1f0d3c
        cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
        if occupied:
            other=0x8cef0000;cpu.regions.append((other,bytearray(32)))
            cpu.write(other+20,occupied-32,4);cpu.write(cpu.reg[8]+92,other,4)
        cpu.pc=symbols['allocate'];cpu.fail_allocations=failures;steps+=cpu.run_until()
        ptr=cpu.reg[0];pw=cpu.read(ptr+28,2);ph=cpu.read(ptr+30,2)
        ex=cpu.read(ptr+12,1);ey=cpu.read(ptr+13,1);size=cpu.read(ptr+20,4)
        assert pw==w<<ex and ph==h<<ey
        assert pw<=1024 and ph<=1024 and size==pw*ph*2
        assert size+32+occupied<=SURFACE_BUDGET or (ex,ey)==(0,0)
        assert len(cpu.calls)>=failures+1
        # Exercise the actual initialization hook, including the caller frame.
        cpu.pr=0xdead0000;cpu.pc=BASE+0x6ab98
        cpu.write(cpu.reg[15],ptr,4);cpu.write(cpu.reg[15]+123,7,1)
        steps+=cpu.run_until(BASE+0x6abfa)
        header=bytes(cpu.read(ptr+i,1) for i in range(32))
        assert header[:4]==b'GBIX' and header[16:20]==b'PVRT'
        assert struct.unpack_from('<I',header,8)[0]==0x407
        assert struct.unpack_from('<I',header,24)[0]==0x900
        assert header[12:14]==bytes([ex,ey])
        assert struct.unpack_from('<HH',header,28)==(pw,ph)
        assert cpu.read(ptr+32,4)==0 and cpu.read(ptr+32+size-4,4)==0
        before=bytes(cpu.read(ptr+i,1) for i in range(36));calls=len(cpu.calls)
        cpu.pc=BASE+0x6abb2;steps+=cpu.run_until(BASE+0x6abfa)
        assert bytes(cpu.read(ptr+i,1) for i in range(36))==before
        assert len(cpu.calls)==calls,'Append entry cleared the existing text surface'
        # Verify flushing and queued DMA use the physical allocation.
        cpu.pr=0xdead0000;cpu.pc=symbols['flush'];cpu.reg[4]=ptr;steps+=cpu.run_until()
        assert cpu.calls[-1]==('flush',ptr,size+32)
        cpu.pc=BASE+0x22d1a;cpu.reg[3]=ptr
        cpu.regions.append((0x8c1716f8,bytearray(4)))
        steps+=cpu.run_until(BASE+0x22d68)
        assert cpu.read(0x8c1716f8,4)==(size+32+2047)//2048
    for w,h in [(0,32),(32,0),(1025,32),(32,1025),(2048,2048)]:
        cpu=HDCPU(exe,font);cpu.reg[8]=0x8c1f0d3c
        cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
        cpu.pc=symbols['allocate'];steps+=cpu.run_until()
        assert cpu.reg[0]==0 and not cpu.calls,'Invalid surface allocated'
    print('PASS: {} HD glyph cases; {} allocation/header/flush/DMA cases; {:,} SH-4 instructions.'.format(len(cases),len(allocation_cases),steps))
    print('Logical advances preserved; physical text edges <=1024; fallback and full-surface clears verified.')
    print('Zero-sized and oversized logical surfaces rejected without allocating (5 cases).')
    print('Runtime playtesting remains required.')


if __name__=='__main__':main()
