"""Verify moved GenEi helper entry points, allocation fallbacks and DMA sizes."""
import argparse,json,struct
from build_genei_font import ROOT,VERSION,compose,digest
from build_font4x_patch import BASE,SURFACE_BUDGET
from test_font4x_patch import HDCPU


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.11','0.1.12'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    assert not args.write_report or args.verify
    files,_,manifest,_=compose();exe=files['1ST_READ.BIN']
    if args.version=='0.1.12':
        from build_word_wrap_story import candidate_executable
        exe,_=candidate_executable()
    off,size=struct.unpack_from('<II',files['WIN00.AFS'],8);font=files['WIN00.AFS'][off:off+size]
    symbols={k:int(v,16) for k,v in manifest['symbols'].items()}
    cases=[(32,32,0,0),(256,64,0,0),(512,64,0,0),(512,512,0,0),
        (256,64,1800000,0),(256,64,SURFACE_BUDGET,0),(256,64,0,2),
        (1024,32,0,0),(32,1024,0,0),(1024,1024,0,0),(320,64,0,0),(64,513,0,0)]
    print('Plan:',len(cases),'allocation/header/append/flush/DMA cases and 5 invalid dimensions.')
    if not args.verify:print('DRY RUN: no native execution or report written');return
    instructions=0
    for w,h,occupied,failures in cases:
        cpu=HDCPU(exe,font);cpu.reg[8]=0x8c1f0d3c
        cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
        if occupied:
            other=0x8cef0000;cpu.regions.append((other,bytearray(32)))
            cpu.write(other+20,occupied-32,4);cpu.write(cpu.reg[8]+92,other,4)
        cpu.pc=symbols['allocate'];cpu.fail_allocations=failures;instructions+=cpu.run_until()
        ptr=cpu.reg[0];pw=cpu.read(ptr+28,2);ph=cpu.read(ptr+30,2)
        ex=cpu.read(ptr+12,1);ey=cpu.read(ptr+13,1);size=cpu.read(ptr+20,4)
        assert pw==w<<ex and ph==h<<ey and pw<=1024 and ph<=1024 and size==pw*ph*2
        assert size+32+occupied<=SURFACE_BUDGET or (ex,ey)==(0,0)
        assert len(cpu.calls)>=failures+1
        cpu.pr=0xdead0000;cpu.pc=BASE+0x6ab98
        cpu.write(cpu.reg[15],ptr,4);cpu.write(cpu.reg[15]+123,7,1)
        instructions+=cpu.run_until(BASE+0x6abfa)
        header=bytes(cpu.read(ptr+i,1) for i in range(32))
        assert header[:4]==b'GBIX' and header[16:20]==b'PVRT'
        assert struct.unpack_from('<I',header,8)[0]==0x407
        assert struct.unpack_from('<I',header,24)[0]==0x900
        assert header[12:14]==bytes([ex,ey]) and struct.unpack_from('<HH',header,28)==(pw,ph)
        assert cpu.read(ptr+32,4)==0 and cpu.read(ptr+32+size-4,4)==0
        before=bytes(cpu.read(ptr+i,1) for i in range(36));calls=len(cpu.calls)
        cpu.pc=BASE+0x6abb2;instructions+=cpu.run_until(BASE+0x6abfa)
        assert bytes(cpu.read(ptr+i,1) for i in range(36))==before and len(cpu.calls)==calls
        cpu.pr=0xdead0000;cpu.pc=symbols['flush'];cpu.reg[4]=ptr;instructions+=cpu.run_until()
        assert cpu.calls[-1]==('flush',ptr,size+32)
        cpu.pc=BASE+0x22d1a;cpu.reg[3]=ptr;cpu.regions.append((0x8c1716f8,bytearray(4)))
        instructions+=cpu.run_until(BASE+0x22d68)
        assert cpu.read(0x8c1716f8,4)==(size+32+2047)//2048
    for w,h in [(0,32),(32,0),(1025,32),(32,1025),(2048,2048)]:
        cpu=HDCPU(exe,font);cpu.reg[8]=0x8c1f0d3c
        cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
        cpu.pc=symbols['allocate'];instructions+=cpu.run_until()
        assert cpu.reg[0]==0 and not cpu.calls
    proof={'version':args.version,'executable_sha256':digest(exe),'allocation_cases':len(cases),
        'invalid_dimension_cases':5,'SH4_instructions':instructions,'allocation_fallbacks_and_1024_limit':'pass',
        'headers_append_cache_flush_and_DMA_sizes':'pass','limits':['Allocator/memset/cache system calls are bounded stubs; live GPU upload remains separate']}
    print(json.dumps(proof,indent=2))
    if args.write_report:(ROOT/'work/output'/args.version/'genei-surface-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
