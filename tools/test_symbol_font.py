"""Exercise symbol bytes through the actual original parser and patched raster.

Also protect all old Latin bitmap/advance slots against accidental changes.
Read-only; this is native instruction execution, not gameplay validation.
"""
import struct
from pathlib import Path
from build_font4x_patch import ROOT,BASE,SMALL,MEDIUM,SYMBOLS,build
from english_text_codec import encode
from test_font4x_patch import HDCPU,expected_pixels


def main():
    files,_,_,_=build(Path('C:/Windows/Fonts/tahoma.ttf'))
    exe=files['1ST_READ.BIN'];afs=files['WIN00.AFS']
    off,size=struct.unpack_from('<II',afs,8);font=afs[off:off+size]
    old=(ROOT/'work/output/0.1.4/WIN00.AFS').read_bytes()
    old_off,old_size=struct.unpack_from('<II',old,8);old_font=old[old_off:old_off+old_size]
    assert len(font)==len(old_font)==99072
    for count,table,data,old_data,stride in [(95,0x20,0x200,0x100,128),(96,0xa0,0x4200,0x4100,256)]:
        assert font[table:table+count]==old_font[table:table+count]
        # Legacy unused medium advances overwrote the first 32 bytes of the
        # small space bitmap. Keep every other Latin shape; fix that space.
        first=1 if table==0x20 else 0
        assert font[data+first*stride:data+count*stride]==old_font[old_data+first*stride:old_data+count*stride]
    assert not any(font[0x200:0x280])
    assert 0xa0+128<=0x200 and 0x200+128*128<=0x4200
    # Each new mark has ink and is neither the fallback nor another mark.
    for chars,table,data,stride in [(SMALL,0x20,0x200,128),(MEDIUM,0xa0,0x4200,256)]:
        shapes=[];q=chars.index('?');fallback=font[data+q*stride:data+(q+1)*stride]
        for c in SYMBOLS:
            i=chars.index(c);shape=font[data+i*stride:data+(i+1)*stride]
            assert any(shape) and shape!=fallback and shape not in shapes,c
            assert 1<=font[table+i]<=8;shapes.append(shape)
    # The untouched native parser reads this stack-local input pointer.
    pointer_offset=struct.unpack_from('<h',exe,0x6ad18)[0]
    assert pointer_offset==0x84
    cases=steps=toggles=0
    for small in [False,True]:
        for background in [0,0x80]:
            for ex,ey in [(0,0),(1,2),(2,2)]:
                for char in SYMBOLS:
                    text='<ASCII:ON>'+char+'<ASCII:OFF>' if small else char
                    stream=encode(text);address=0x8ce00000
                    cpu=HDCPU(exe,font,flags=background,w=256,h=32,ex=ex,ey=ey)
                    cpu.regions.append((address,bytearray(stream)))
                    cpu.write(cpu.reg[15]+pointer_offset,address,4)
                    if small:
                        before=bytes(cpu.regions[3][1]);cursor=cpu.read(0x8c1f36b6,2)
                        cpu.pc=BASE+0x6ac64;steps+=cpu.run_until(BASE+0x6b252)
                        assert cpu.read(0x8c1f36ba,1)==background|0x40
                        assert bytes(cpu.regions[3][1])==before and cpu.read(0x8c1f36b6,2)==cursor
                        toggles+=1
                    pos=cpu.read(cpu.reg[15]+pointer_offset,4)-address
                    glyph=stream[pos];flags=background|(0x40 if small else 0)
                    expected,advance=expected_pixels(cpu,font,glyph,flags)
                    cpu.pc=BASE+0x6ac64;steps+=cpu.run_until(BASE+0x6b252)
                    assert cpu.regions[3][1]==expected,(char,small,background,ex,ey)
                    assert cpu.read(0x8c1f36b6,2)==12+advance
                    assert cpu.read(cpu.reg[15]+pointer_offset,4)==address+pos+1
                    if small:
                        before=bytes(cpu.regions[3][1]);cursor=cpu.read(0x8c1f36b6,2)
                        cpu.pc=BASE+0x6ac64;steps+=cpu.run_until(BASE+0x6b252)
                        assert cpu.read(0x8c1f36ba,1)==background
                        assert bytes(cpu.regions[3][1])==before and cpu.read(0x8c1f36b6,2)==cursor
                        toggles+=1
                    cases+=1
    print('PASS: 190 old Latin shapes and all191 advances unchanged; small space repaired; tables/bitmaps disjoint; 10 distinct symbol glyphs.')
    print('PASS: {} symbol cases through original parser and native raster, {} mode toggles; {:,} SH-4 instructions.'.format(cases,toggles,steps))
    print('Both sizes, opaque/transparent styles and native/2x/4x scale combinations covered; gameplay remains pending.')


if __name__=='__main__':main()
