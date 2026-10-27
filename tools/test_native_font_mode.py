"""Check both selectable font banks with the actual SH-4 raster/allocator."""
import json
from build_native_font_mode import compose, MODE, PRIOR, TITLE_HOOK, TITLE_RANGE, FRAME_CALLEE
from build_font4x_patch import SMALL, MEDIUM, BASE, START, END, assemble
from build_genei_font import SMALL_DATA, MEDIUM_DATA
from build_bitmap_font import ROOT, digest
from test_font4x_patch import HDCPU, TEX
from test_outline_font import legacy_mask, expected_pixels
from afs_layout import require_native_layouts


def check():
    exe, archive, font, masks, report = compose()
    n = len(font)//2
    # Existing callers without the new options still produce exact old code.
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    original,_,_=assemble(wide=True,small_data=SMALL_DATA,medium_data=MEDIUM_DATA,antialias=True)
    assert old[START:0x6b800]==original[:0x6b800-START]
    assert exe[0x6b840:0x6b900]==old[0x6b840:0x6b900]
    assert font[:n][0x20:0x120]==font[n:][0x20:0x120]
    assert digest(font[:n])==report['HD_bank_sha256']
    require_native_layouts({'WIN00.AFS':archive})
    steps=cases=0
    for mode in (0,1):
        bank=font[n:] if mode==0 else font[:n]
        for small,chars in ((True,SMALL),(False,MEDIUM)):
            for i,char in enumerate(chars):
                for ex,ey in (((0,0),) if mode==0 else ((0,0),(1,2),(2,2))):
                    flags=(64 if small else 0)|(128 if i%2 else 0)
                    glyph=i+32 if small else i
                    cpu=HDCPU(exe,font,glyph,flags,w=64,h=32,ex=ex,ey=ey)
                    cpu.write(MODE,mode,1)
                    coverage=legacy_mask(bank,char,small)
                    if char.isascii():coverage=coverage[:,:32]
                    expected=expected_pixels(cpu,coverage,flags,12,4)
                    steps+=cpu.run_until(limit=300000)
                    assert cpu.regions[3][1]==expected,(mode,small,char,ex,ey)
                    assert cpu.read(0x8c1f36b6,2)==12+bank[(0x20 if small else 0xa0)+i]
                    cases+=1
        for w,h in ((32,32),(256,128),(512,64),(1024,32)):
            cpu=HDCPU(exe,font);cpu.write(MODE,mode,1);cpu.reg[8]=0x8c1f0d3c
            cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
            cpu.pc=report['labels']['allocate'];steps+=cpu.run_until()
            ptr=cpu.reg[0];ex,ey=cpu.read(ptr+12,1),cpu.read(ptr+13,1)
            if mode==0:assert (ex,ey)==(0,0)
            assert cpu.read(ptr+28,2)==w<<ex and cpu.read(ptr+30,2)==h<<ey
            assert max(w<<ex,h<<ey)<=1024
    return {'version':report['version'],'executable_sha256':digest(exe),
            'archive_sha256':digest(archive),'native_raster_cases':cases,
            'allocator_cases':8,'SH4_instructions':steps,'ABI_guards_pixels_advances':'pass',
            'HD_bank_unchanged':True,'native_archive_layout':'pass'}


if __name__=='__main__':print(json.dumps(check(),indent=2))
