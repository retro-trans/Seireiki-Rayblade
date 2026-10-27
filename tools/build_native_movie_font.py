"""Reproduce the 0.7.4 render experiment and fix movie coordinates as 0.7.5.

The original Sofdec byte streams are retained. Two application setters receive
scaled positions/sizes in the existing 640x480 framebuffer. Dry by default.
"""
import struct
from build_skies_native_font import compose as font_compose,ROOT
from build_bitmap_font import digest
from sh4_asm import Assembler

def render_074():
 e,a,f,m,r=font_compose();e=bytearray(e)
 assert e[0x10cb2:0x10cb4]==bytes.fromhex('00e4')
 e[0x10cb2:0x10cb4]=bytes.fromhex('31e4')
 asm=Assembler(0x8c07b6e0);asm.emit(0x4f22);asm.addi(-32,15)
 asm.rr('mov',4,1);asm.rr('mov',15,2);asm.imm(8,3)
 asm.label('copy');asm.emit(0x6016);asm.store('l',0,2);asm.addi(4,2);asm.unary('dt',3);asm.branch('bf','copy')
 for offset in (0,4,12,16):
  asm.imm(offset,0);asm.emit(0xf0f6);asm.emit(0xf000);asm.emit(0xff07)
 asm.rr('mov',15,4);asm.lit(0x8c0ab970,3);asm.emit(0x430b);asm.emit(0x0009)
 asm.addi(32,15);asm.emit(0x4f26);asm.emit(0x000b);asm.emit(0x0009)
 sprite=asm.pool_and_finish()
 poly=Assembler(asm.base+len(sprite));poly.push(8);poly.emit(0x4f22);poly.rr('mov',15,8)
 poly.rr('mov',5,3);poly.unary('shll2',3);poly.unary('shll',3);poly.addi(16,3);poly.rr('sub',3,15)
 poly.rr('mov',4,1);poly.rr('mov',15,2);poly.imm(4,3)
 poly.label('copystruct');poly.emit(0x6016);poly.store('l',0,2);poly.addi(4,2);poly.unary('dt',3);poly.branch('bf','copystruct')
 poly.load('l',4,1);poly.rr('mov',15,2);poly.addi(16,2);poly.store('l',2,15)
 poly.rr('mov',5,3);poly.unary('shll',3);poly.rr('tst',3,3);poly.branch('bt','call')
 poly.label('vertices');poly.emit(0xf019);poly.emit(0xf000);poly.emit(0xf20a);poly.addi(4,2);poly.unary('dt',3);poly.branch('bf','vertices')
 poly.label('call');poly.rr('mov',15,4);poly.lit(0x8c0a9db0,3);poly.emit(0x430b);poly.emit(0x0009)
 poly.rr('mov',8,15);poly.emit(0x4f26);poly.pop(8);poly.emit(0x000b);poly.emit(0x0009)
 polygon=poly.pool_and_finish()
 clip=Assembler(poly.base+len(polygon));clip.emit(0x4f22);clip.addi(-16,15)
 clip.rr('mov',5,1);clip.rr('mov',15,2);clip.imm(4,3)
 clip.label('rect');clip.emit(0xf019);clip.emit(0xf000);clip.emit(0xf20a);clip.addi(4,2);clip.unary('dt',3);clip.branch('bf','rect')
 clip.rr('mov',15,5);clip.lit(0x8c0a7c06,3);clip.emit(0x430b);clip.emit(0x0009)
 clip.addi(16,15);clip.emit(0x4f26);clip.emit(0x000b);clip.emit(0x0009)
 clipping=clip.pool_and_finish()
 code=sprite+polygon+clipping;assert 0x6b6e0+len(code)<=0x6b800,(len(code),hex(0x6b6e0+len(code)))
 assert e[0x6b6e0:0x6b6e0+len(code)]==bytes.fromhex('0900')*(len(code)//2)
 e[0x6b6e0:0x6b6e0+len(code)]=code
 p=0x6b8e4;assert struct.unpack_from('<I',e,p)[0]==0x8c0ab970
 struct.pack_into('<I',e,p,asm.base)
 edits=[]
 for p in range(0,0x90000,4):
  v=struct.unpack_from('<I',e,p)[0]
  if v in (0x8c0a9db0,0x8c0a7c06) and not 0x6b6e0<=p<0x6b800:
   edits.append((hex(p),hex(v)));struct.pack_into('<I',e,p,poly.base if v==0x8c0a9db0 else clip.base)
 assert e[0xda696:0xda698]==bytes.fromhex('0c31')
 e[0xda696:0xda698]=bytes.fromhex('0900')
 r['rendering']={'physical_framebuffer':[640,480], 'sprite_wrapper':hex(asm.base), 'polygon_wrapper':hex(poly.base), 'clip_wrapper':hex(clip.base), 'wrapper_bytes':len(code), 'pointer_edits':edits, 'cable_verified':'VGA only; TV and physical hardware unverified'}
 r['executable_sha256']=digest(e)
 assert digest(e)=='ead04815fd822e7be3bbe169818bb3a2f3f1e03f2a353798ebf950acdb188689'
 assert len(edits)==37
 return bytes(e),a,f,m,r

VERSION,PRIOR='0.7.5','0.7.3'
OUT=ROOT/'work/output/native-movie-fit-candidate'
MOVIE_ENTRY=0x8c07b7a8

def compose():
    exe,archive,font,masks,report=render_074();target=bytearray(exe)
    edits=[];cursor=MOVIE_ENTRY
    for pointer,callee,label in ((0x2a150,0x8c09fccc,'position'),(0x2a154,0x8c09fd18,'size')):
        a=Assembler(cursor)
        a.emit(0xf440) # FADD FR4,FR4: x or width
        a.emit(0xf550) # FADD FR5,FR5: y or height
        a.lit(callee,3);a.emit(0x432b);a.emit(0x0009)
        code=a.pool_and_finish();offset=cursor-0x8c010000
        assert offset+len(code)<=0x6b800
        assert target[offset:offset+len(code)]==bytes.fromhex('0900')*(len(code)//2)
        assert struct.unpack_from('<I',target,pointer)[0]==callee
        target[offset:offset+len(code)]=code;struct.pack_into('<I',target,pointer,cursor)
        edits.append({'setter':label,'pointer_offset':hex(pointer),'original':hex(callee),
                      'entry':hex(cursor),'bytes':len(code)})
        cursor+=len(code)
    allowed=set(range(MOVIE_ENTRY-0x8c010000,cursor-0x8c010000))|set(range(0x2a150,0x2a158))
    changed=[i for i,(a,b) in enumerate(zip(exe,target)) if a!=b]
    assert set(changed)<=allowed
    assert digest(archive)=='3483d353e24b456e6cb7688de9594f7e0d0a10ac00c14343b300d88c4d5462ad'
    report.update(version=VERSION,source_build='0.7.4 rendering experiment',
        source_render_executable_sha256=digest(exe),executable_sha256=digest(target),
        movie_geometry={'setters':edits,'source_pixels':'Original movie payloads remain byte-exact',
                        'mapping':'Uniform 2x position and size in the 640x480 framebuffer; aspect ratio and letterboxing retained',
                        'changed_executable_bytes_from_074':len(changed)},
        pending=['Physical Dreamcast and non-VGA verification','Full route/long-session coverage'])
    return bytes(target),archive,font,masks,report

def main():
    import argparse,json
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    exe,archive,font,masks,report=compose()
    print(json.dumps({k:report[k] for k in ('version','executable_sha256','archive_sha256','movie_geometry')},indent=2))
    if args.write:
        OUT.mkdir(exist_ok=True,parents=True)
        (OUT/'1ST_READ.BIN').write_bytes(exe);(OUT/'WIN00.AFS').write_bytes(archive)
        (OUT/'font-mode-component.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    else:print('DRY RUN: no files written')

if __name__=='__main__':main()
