"""Execute original Skies pixels through the new native-density SH-4 raster."""
import argparse,json,struct
import numpy as np
from build_skies_native_font import ROOT,OUT,PRIOR,compose,MODE
from build_font4x_patch import SMALL,MEDIUM,START,END,SURFACE_BUDGET
from test_font4x_patch import HDCPU,TEX
from test_outline_font import legacy_mask,expected_pixels
from afs_layout import require_native_layouts
from build_bitmap_font import digest
from test_title_font_selector import check as title_check


def check(*,compose_fn=compose,render_hook=False):
    exe,archive,font,_,report=compose_fn();n=len(font)//2
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    if render_hook:
        assert exe[0x6b800:0x6b8e4]==old[0x6b800:0x6b8e4]
        assert exe[0x6b8e8:END]==old[0x6b8e8:END]
        assert struct.unpack_from('<I',exe,0x6b8e4)[0]==int(report['rendering']['sprite_wrapper'],16)
    else:
        assert exe[0x6b800:END]==old[0x6b800:END]
    assert font[:n][0x20:0x120]==font[n:][0x20:0x120]
    require_native_layouts({'WIN00.AFS':archive})
    steps=cases=0
    for mode in (0,1):
        bank=font[n:] if mode==0 else font[:n]
        for small,chars in ((True,SMALL),(False,MEDIUM)):
            for i,ch in enumerate(chars):
                ex,ey=(1,1) if mode==0 else (2,2)
                flags=(64 if small else 0)|128
                cpu=HDCPU(exe,font,i+32 if small else i,flags,w=64,h=32,ex=ex,ey=ey)
                cpu.write(MODE,mode,1)
                mask=legacy_mask(bank,ch,small)
                if ch.isascii():mask=mask[:,:32]
                expected=expected_pixels(cpu,mask,flags,12,4,shadow_pixels=1 if mode==0 else None)
                steps+=cpu.run_until(limit=300000)
                assert cpu.regions[3][1]==expected,(mode,small,ch)
                assert cpu.read(0x8c1f36b6,2)==12+bank[(0x20 if small else 0xa0)+i]
                cases+=1
    allocations=[]
    for mode in (0,1):
        for w,h,occupied,failures in [(32,32,0,0),(256,128,0,0),(512,64,0,0),
                    (1024,32,0,0),(32,1024,0,0),(256,128,0,1),(256,128,1900000,0)]:
            cpu=HDCPU(exe,font);cpu.write(MODE,mode,1);cpu.reg[8]=0x8c1f0d3c
            cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
            if occupied:
                cpu.regions.append((0x8cef0000,bytearray(32)));cpu.write(0x8cef0014,occupied-32,4)
                cpu.write(cpu.reg[8]+92,0x8cef0000,4)
            cpu.fail_allocations=failures;cpu.pc=report['labels']['allocate'];steps+=cpu.run_until()
            ptr=cpu.reg[0];ex,ey=cpu.read(ptr+12,1),cpu.read(ptr+13,1)
            if mode==0 and not occupied and not failures:
                assert (ex,ey)==(int(w<=512),int(h<=512))
            assert max(w<<ex,h<<ey)<=1024
            assert cpu.read(ptr+20,4)==(w<<ex)*(h<<ey)*2
            allocations.append({'mode':mode,'logical':[w,h],'physical':[w<<ex,h<<ey],
                                'occupied':occupied,'allocation_failures':failures})
    return {'version':report['version'],'executable_sha256':digest(exe),'archive_sha256':digest(archive),
            'source_skies_executable_sha256':report['source_skies_executable_sha256'],
            'original_Skies_medium_masks_exact':sum(r['source_pixels_exact'] for r in report['metrics']),
            'glyph_cases':cases,'allocation_cases':allocations,'SH4_instructions':steps,
            'ABI_guards_pixels_advances':'pass','HD_bank_unchanged':True,
            'source_pixel_mapping':'Native medium: original 12x24 coverage samples at 1:1 output density',
            'native_archive_layout':'pass','physical_edges_max':1024}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    proof=check();selector=title_check(compose_fn=compose)
    print(json.dumps({k:v for k,v in proof.items() if k!='allocation_cases'},indent=2))
    print('Selector:',selector['native_instructions'],'instructions; repeated switches and VM/ABI pass.')
    if args.write_report:
        OUT.mkdir(exist_ok=True,parents=True)
        for name,value in [('font-mode-native-test.json',proof),('title-font-native-test.json',selector)]:
            (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
