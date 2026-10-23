"""Execute four-level native rasterization against independent source pixels.

Includes all glyphs, colored text, shadow, resolution fallbacks and clipping.
Allocation/header/append/flush/DMA paths execute with bounded system stubs.
"""
import argparse,json,struct
from PIL import Image
from build_antialias_font import ROOT,ATLAS,VERSION,PRIOR,digest,font_bytes
from build_font4x_patch import SMALL,MEDIUM,SURFACE_BUDGET,BASE
from build_genei_font import SMALL_DATA,MEDIUM_DATA
from test_font4x_patch import HDCPU,TEX
from test_font_patch import CPU


def reference(cpu,char,flags,x,y,source,old):
    expected=bytearray(cpu.regions[3][1]);small=bool(flags&64)
    chars=SMALL if small else MEDIUM;index=chars.index(char);height=8 if small else 16;scale=1 if small else 2
    if char.isascii():
        code=ord(char)-32;gx=code%32*12;gy=code//32*24
        cell=source.crop((gx,gy,gx+12,gy+24))
        bounds=cell.point(lambda p:255 if p>=128 else 0).getbbox();left=bounds[0] if bounds else 0
        def coverage(xx,yy):
            if yy<4:return 0
            px=(xx-4)//scale+left;py=(yy-4)//scale
            return cell.getpixel((px,py)) if 0<=px<12 and py<24 else 0
        width=8
    else:
        start=(SMALL_DATA if small else MEDIUM_DATA)+index*height*32
        def coverage(xx,yy):
            bits=struct.unpack_from('<I',old,start+yy*8+(xx//32)*4)[0]
            return 255 if bits&(1<<(31-xx%32)) else 0
        width=16
    w=cpu.read(TEX+28,2);h=cpu.read(TEX+30,2);sx=1<<cpu.read(TEX+12,1);sy=1<<cpu.read(TEX+13,1)
    rgb=cpu.read(0x8c0980aa+(flags&14)*2,2)
    color=(((rgb>>11)&15)<<8)|(((rgb>>6)&15)<<4)|((rgb>>1)&15)
    observed=set()
    for yy in range(height*sy):
        py=y*sy+yy
        if py>=h:continue
        for xx in range(width*sx):
            px=x*sx+xx
            level=coverage(xx*4//sx,yy*4//sy);alpha=level//17;observed.add(alpha)
            if px>=w:continue
            if flags&128 and px+sx<w:struct.pack_into('<H',expected,32+(py*w+px+sx)*2,alpha<<12)
            if alpha:struct.pack_into('<H',expected,32+(py*w+px)*2,(alpha<<12)|color)
    return expected,observed


def surface_checks(exe,font,symbols):
    steps=0
    cases=[(32,32,0,0),(256,64,0,0),(512,64,0,0),(512,512,0,0),(256,64,1800000,0),(256,64,SURFACE_BUDGET,0),(256,64,0,2),(1024,32,0,0),(32,1024,0,0),(1024,1024,0,0),(320,64,0,0),(64,513,0,0)]
    for w,h,occupied,failures in cases:
        cpu=HDCPU(exe,font);cpu.reg[8]=0x8c1f0d3c
        cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
        if occupied:
            other=0x8cef0000;cpu.regions.append((other,bytearray(32)));cpu.write(other+20,occupied-32,4);cpu.write(cpu.reg[8]+92,other,4)
        cpu.pc=symbols['allocate'];cpu.fail_allocations=failures;steps+=cpu.run_until()
        ptr=cpu.reg[0];pw=cpu.read(ptr+28,2);ph=cpu.read(ptr+30,2);size=cpu.read(ptr+20,4)
        ex=cpu.read(ptr+12,1);ey=cpu.read(ptr+13,1)
        assert pw==w<<ex and ph==h<<ey and max(pw,ph)<=1024 and size==pw*ph*2
        assert size+32+occupied<=SURFACE_BUDGET or (ex,ey)==(0,0)
        assert len(cpu.calls)>=failures+1
        cpu.pr=0xdead0000;cpu.pc=BASE+0x6ab98;cpu.write(cpu.reg[15],ptr,4);cpu.write(cpu.reg[15]+123,7,1)
        steps+=cpu.run_until(BASE+0x6abfa)
        header=bytes(cpu.read(ptr+i,1) for i in range(32))
        assert header[:4]==b'GBIX' and header[16:20]==b'PVRT' and struct.unpack_from('<I',header,24)[0]==0x902
        assert struct.unpack_from('<HH',header,28)==(pw,ph) and header[12:14]==bytes((ex,ey))
        assert cpu.read(ptr+32,4)==0 and cpu.read(ptr+32+size-4,4)==0
        before=header;calls=len(cpu.calls);cpu.pc=BASE+0x6abb2;steps+=cpu.run_until(BASE+0x6abfa)
        assert bytes(cpu.read(ptr+i,1) for i in range(32))==before and len(cpu.calls)==calls
        cpu.pr=0xdead0000;cpu.pc=symbols['flush'];cpu.reg[4]=ptr;steps+=cpu.run_until();assert cpu.calls[-1]==('flush',ptr,size+32)
        cpu.pc=BASE+0x22d1a;cpu.reg[3]=ptr;cpu.regions.append((0x8c1716f8,bytearray(4)));steps+=cpu.run_until(BASE+0x22d68)
        assert cpu.read(0x8c1716f8,4)==(size+32+2047)//2048
    for w,h in [(0,32),(32,0),(1025,32),(32,1025),(2048,2048)]:
        cpu=HDCPU(exe,font);cpu.reg[8]=0x8c1f0d3c;cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
        cpu.pc=symbols['allocate'];steps+=cpu.run_until();assert cpu.reg[0]==0 and not cpu.calls
    return {'version':VERSION,'executable_sha256':digest(exe),'allocation_cases':len(cases),'invalid_dimension_cases':5,'SH4_instructions':steps,'allocation_fallbacks_and_1024_limit':'pass','headers_append_cache_flush_and_DMA_sizes':'pass','texture_format':'ARGB4444 (PVRT pixel type 2, layout 9)','limits':['Allocator/memset/cache calls are bounded fixtures; live GPU blending unverified']}


def texture_format_checks(exe):
    # Actual Ninja texture-info builder, including its native memory-size
    # helper. No format acceptance, pixel bits or size result are stubbed.
    cases=[]
    for w,h in [(128,32),(1024,128),(1024,256),(512,512)]:
        for fmt in (0x900,0x902):
            cpu=CPU(exe,b'',0,0);cpu.regions.insert(-1,(0x8c500000,bytearray(b'\xa5'*128)))
            cpu.reg[4:8]=[0x8c500020,w,h,fmt];cpu.pc=0x8c0e1c4c;saved=cpu.reg[8:]
            for n in range(10000):
                if cpu.pc==0xdead0000:break
                cpu.pc=cpu.execute(cpu.pc)
            else:raise ValueError('Native texture-info instruction limit')
            assert cpu.reg[0]==0 and cpu.reg[8:]==saved
            assert cpu.read(0x8c500028,4)==(0x10000000 if fmt==0x902 else 0)
            assert cpu.read(0x8c50002c,4)==w and cpu.read(0x8c500030,4)==h and cpu.read(0x8c500034,4)==w*h*2
            assert cpu.regions[-2][1][:32]==b'\xa5'*32 and cpu.regions[-2][1][64:]==b'\xa5'*64
            cases.append({'width':w,'height':h,'PVRT_format':hex(fmt),'GPU_format_bits':hex(cpu.read(0x8c500028,4)),'native_bytes':w*h*2,'SH4_instructions':n})
    return cases


def main():
    global VERSION,PRIOR
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--version',default=VERSION,choices=['0.1.17','0.1.19','0.1.21']);ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    if VERSION in ('0.1.19','0.1.21'):PRIOR='0.1.16'
    print('Plan: all glyphs, all color flags, source edge coverage, clipping and 17 allocation/header cases.',flush=True)
    if not args.verify:print('DRY RUN: no native execution or report written');return
    out=ROOT/'work/output'/VERSION;prior=ROOT/'work/output'/PRIOR
    exe=(out/'1ST_READ.BIN').read_bytes();_,font=font_bytes((out/'WIN00.AFS').read_bytes());_,old=font_bytes((prior/'WIN00.AFS').read_bytes())
    if VERSION=='0.1.19':
        from build_library_header_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN'] and (out/'WIN00.AFS').read_bytes()==files['WIN00.AFS']
    elif VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN'] and (out/'WIN00.AFS').read_bytes()==files['WIN00.AFS']
    assert font[:8]==b'RBLF4X\0\4' and font[0x20:0x120]==old[0x20:0x120]
    source=Image.open(ATLAS).convert('L');cases=[]
    for chars,mode,ex in [(SMALL,64,2),(MEDIUM,0,1)]:
        cases.extend((c,i+32 if mode else i,mode|(128 if i%2 else 0),512,32,ex,2,12,4) for i,c in enumerate(chars))
    for mode,chars in [(64,SMALL),(0,MEDIUM)]:
        for ex,ey in [(0,0),(0,2),(1,0),(1,1),(2,1),(2,2)]:
            for x,y in [(0,0),(31,31),(32,4),(26,28)]:
                for c in ('W','j','♪'):cases.append((c,chars.index(c)+(32 if mode else 0),mode|128,32,32,ex,ey,x,y))
        for color in range(0,16,2):
            for c in ('r','O','♪'):cases.append((c,chars.index(c)+(32 if mode else 0),mode|128|color,256,32,2,2,12,4))
    steps=0;alpha=set()
    for n,(ch,glyph,flags,w,h,ex,ey,x,y) in enumerate(cases):
        cpu=HDCPU(exe,font,glyph,flags,w,h,ex,ey);cpu.write(0x8c1f36b6,x,2);cpu.write(0x8c1f36b8,y,2)
        expected,levels=reference(cpu,ch,flags,x,y,source,old);alpha.update(levels);steps+=cpu.run_until(limit=300000)
        assert cpu.regions[3][1]==expected,('Coverage pixel/guard mismatch',ch,flags,ex,ey,x,y)
        index=glyph-32 if flags&64 else glyph;assert cpu.read(0x8c1f36b6,2)==x+old[(0x20 if flags&64 else 0xa0)+index]
        if (n+1)%100==0:print('Native coverage cases passed:',n+1,flush=True)
    assert alpha=={0,5,11,15},alpha
    proof={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'native_cases':len(cases),'supported_glyph_ids':len(SMALL)+len(MEDIUM),'SH4_instructions':steps,'alpha_levels':sorted(alpha),'pixel_reference':'Independent direct source-image luminance, same baseline/origin and original protected symbol masks','pixels_shadow_edges_and_guards':'exact','callee_saved_registers_and_stack':'pass','limits':['No live appearance or GPU blending proof','Supplied bitmap retains its original finite outline detail']}
    manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'));surface=surface_checks(exe,font,{k:int(v,16) for k,v in manifest['symbols'].items()})
    surface['native_texture_format_cases']=texture_format_checks(exe)
    print(json.dumps(proof,indent=2));print(json.dumps(surface,indent=2))
    if args.write_report:
        (out/'genei-font-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8');(out/'genei-surface-native-test.json').write_text(json.dumps(surface,indent=2)+'\n','utf-8')
        manifest['antialias_font']['native_validation']='pass; direct source coverage, colors, ABI, clipping and allocation/header/append/flush/DMA cases'
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
