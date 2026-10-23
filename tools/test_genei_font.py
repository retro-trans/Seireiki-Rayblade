"""Verify real SH-4 GenEi raster output against direct FreeType masks.

Includes wide glyphs, every supported character, all resolution exponents,
shadow writes and surface edges. No game input or process memory writes.
"""
import argparse,json,struct
from PIL import Image,ImageDraw,ImageFont
from build_genei_font import ROOT,VERSION,FONT,SMALL,MEDIUM,compose,digest
from build_font4x_patch import make_executable,START,END
from test_font4x_patch import HDCPU,TEX


def reference(cpu,char,flags,metrics,x,y):
    expected=bytearray(cpu.regions[3][1])
    w=cpu.read(TEX+28,2);h=cpu.read(TEX+30,2)
    ex=cpu.read(TEX+12,1);ey=cpu.read(TEX+13,1);sx=1<<ex;sy=1<<ey
    height=8 if flags&64 else 16
    face=ImageFont.truetype(str(FONT),metrics['em_at_4x'],layout_engine=ImageFont.Layout.BASIC)
    mask=Image.new('L',(64,height*4))
    ImageDraw.Draw(mask).text((4,metrics['baseline_at_4x']),'—' if char=='ー' else char,
        font=face,fill=255,anchor='ls')
    color=cpu.read(0x8c0980aa+(flags&14)*2,2)
    for yy in range(height*sy):
        py=y*sy+yy
        if py>=h:continue
        for xx in range(16*sx):
            px=x*sx+xx
            bit=mask.getpixel((xx*4//sx,yy*4//sy))>=128
            if flags&128 and px+sx<w:
                struct.pack_into('<H',expected,32+(py*w+px+sx)*2,0x8000 if bit else 0)
            if bit and px<w:struct.pack_into('<H',expected,32+(py*w+px)*2,color)
    return expected


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.11','0.1.12'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    assert not args.write_report or args.verify
    files,_,manifest,report=compose();exe=files['1ST_READ.BIN']
    if args.version=='0.1.12':
        from build_word_wrap_story import candidate_executable
        exe,_=candidate_executable()
    saved=ROOT/'work/output'/args.version
    assert (saved/'1ST_READ.BIN').read_bytes()==exe
    afs=files['WIN00.AFS'];offset,size=struct.unpack_from('<II',afs,8);font=afs[offset:offset+size]
    # Old default assembly remains byte-identical; this is an opt-in format.
    original=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    old,_,_,_=make_executable(original)
    assert old[START:END]==(ROOT/'work/output/0.1.10/1ST_READ.BIN').read_bytes()[START:END]
    cases=[]
    for chars,mode,ex in [(SMALL,64,2),(MEDIUM,0,1)]:
        cases.extend((c,i if not mode else i+32,mode|(128 if i%2 else 0),512,32,ex,2,12,4)
            for i,c in enumerate(chars))
    for mode,chars in [(64,SMALL),(0,MEDIUM)]:
        for ex,ey in [(0,0),(0,2),(1,0),(1,1),(2,1),(2,2)]:
            for x,y in [(0,0),(31,31),(32,4),(26,28)]:
                for c in ('W','j','♪'):
                    i=chars.index(c);cases.append((c,i+32 if mode else i,mode|128,32,32,ex,ey,x,y))
    print('Plan:',len(cases),'native raster/mask/ABI/edge cases; all 201 supported glyph IDs.',flush=True)
    if not args.verify:print('DRY RUN: no native execution or report written');return
    instructions=0
    for index,(char,glyph,flags,w,h,ex,ey,x,y) in enumerate(cases):
        cpu=HDCPU(exe,font,glyph,flags,w,h,ex,ey)
        cpu.write(0x8c1f36b6,x,2);cpu.write(0x8c1f36b8,y,2)
        metrics=report['metrics']['small' if flags&64 else 'medium']
        expected=reference(cpu,char,flags,metrics,x,y)
        instructions+=cpu.run_until()
        assert cpu.regions[3][1]==expected,('Pixel/guard mismatch',char,flags,ex,ey,x,y)
        advance=metrics['glyphs'][(glyph-32 if flags&64 else glyph)]['advance']
        assert cpu.read(0x8c1f36b6,2)==x+advance
        if (index+1)%100==0:print('Raster cases passed:',index+1,flush=True)
    proof={'version':args.version,'executable_sha256':digest(exe),'font_sha256':digest(font),
        'native_cases':len(cases),'supported_glyph_ids':len(SMALL)+len(MEDIUM),
        'SH4_instructions':instructions,'pixel_reference':'Direct FreeType masks at a common em/baseline; no per-letter resize',
        'pixels_shadow_edges_and_guards':'exact','callee_saved_registers_and_stack':'pass',
        'legacy_default_kernel':'byte-exact 0.1.10',
        'limits':['No live game appearance proof','Natural advance rounding uses the native integer logical grid',
            'Word-aware wrapping and other UI layout remain separate work']}
    print(json.dumps(proof,indent=2))
    if args.write_report:(saved/'genei-font-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
