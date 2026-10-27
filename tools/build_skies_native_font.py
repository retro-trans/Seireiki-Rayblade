"""Use original Skies glyphs at one texel per 640x480 output pixel. Dry first.

Rayblade UI coordinates are 320x240. Native output therefore requires two
font texels per logical coordinate, not the reduced 0.7.3 logical-size bank.
"""
import argparse
import json
import struct
import numpy as np
from PIL import Image,ImageDraw
from build_bitmap_font import ROOT,digest
from build_font4x_patch import BASE,START,END,SMALL,MEDIUM,make_executable
from build_genei_font import SMALL_DATA,MEDIUM_DATA
from build_antialias_font import LEVELS
from build_native_font_mode import MODE,quantize
from analyze_skies_font import read_executable,skies_glyph,EXPECTED_EXE
from test_outline_font import legacy_mask

VERSION,PRIOR='0.7.4','0.7.3'
OUT=ROOT/'work/output/skies-native-candidate'


def native_bank(hd,skies):
    # Medium data already stores exact twofold repeats of the original
    # 12x24 source. Sampling it at exponent 1 recovers every original pixel.
    native=bytearray(hd);masks={};metrics=[]
    for small,chars,height,start,table in ((True,SMALL,8,SMALL_DATA,0x20),
                                          (False,MEDIUM,16,MEDIUM_DATA,0xa0)):
        bank='small' if small else 'medium';masks[bank]={}
        for i,ch in enumerate(chars):
            old=legacy_mask(hd,ch,small)
            if small and ch.isascii():
                source=skies_glyph(skies,ord(ch),LEVELS);box=source.getbbox()
                normalized=Image.new('L',(12,24))
                normalized.paste(source,(-(box[0] if box else 0),0))
                target=Image.new('L',(32,16))
                target.paste(Image.fromarray(quantize(normalized.resize((8,16),Image.Resampling.BOX))),(0,0))
                repeated=np.repeat(np.repeat(np.asarray(target),2,axis=0),2,axis=1)
                assert not repeated[:,32:].any()
                for y in range(32):
                    words=[sum(LEVELS.index(int(repeated[y,half*16+x]))<<(30-2*x)
                               for x in range(16)) for half in range(2)]
                    struct.pack_into('<2I',native,start+i*256+y*8,*words)
            else:
                repeated=old
                target=Image.fromarray(old[::2,::2].copy())
            masks[bank][ch]=target
            if not small and ch.isascii():
                source=skies_glyph(skies,ord(ch),LEVELS);box=source.getbbox();left=box[0] if box else 0
                expected=Image.new('L',(32,32));expected.paste(source,(2-left,2))
                assert target.tobytes()==expected.tobytes(),('Original Skies pixel mismatch',ch)
            bounds=target.getbbox()
            if small and ch.isascii() and bounds:
                assert bounds[2]<=hd[table+i]*2,('Small glyph advance overflow',ch,bounds)
            metrics.append({'bank':bank,'character':ch,'output_cell':list(target.size),
                'output_bounds':bounds,'output_mask_sha256':digest(target.tobytes()),
                'source_pixels_exact':not small and ch.isascii()})
    assert native[:SMALL_DATA]==hd[:SMALL_DATA]
    assert native[MEDIUM_DATA:]==hd[MEDIUM_DATA:]
    return bytes(native),masks,metrics


def compose():
    base=ROOT/'work/output'/PRIOR;source=(base/'WIN00.AFS').read_bytes()
    offset,size=struct.unpack_from('<II',source,8);assert size==198144
    hd=source[offset:offset+size//2]
    assert digest(hd)=='5fe1480136b8c7d2bb15a32b17588edc0459fcf9c1079c9aa4b1075e11a4d181'
    skies,_=read_executable();assert digest(skies)==EXPECTED_EXE
    native,masks,metrics=native_bank(hd,skies)
    archive=source[:offset]+hd+native+source[offset+size:]
    old_exe=(base/'1ST_READ.BIN').read_bytes()
    exe,labels,used,_=make_executable(old_exe,wide=True,small_data=SMALL_DATA,
        medium_data=MEDIUM_DATA,antialias=True,font_mode_address=MODE,
        native_font_offset=len(hd),native_surface_exponent=1,native_shadow_pixels=1)
    assert START+used<=0x6b800
    exe=bytearray(exe);exe[0x6b800:END]=old_exe[0x6b800:END]
    previous=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    report={'version':VERSION,'source_build':PRIOR,'native_default':True,
        'mode_address':hex(MODE),'native_font_offset':len(hd),'font_member_bytes':size,
        'HD_bank_sha256':digest(hd),'native_bank_sha256':digest(native),
        'combined_font_sha256':digest(hd+native),'source_skies_executable_sha256':digest(skies),
        'executable_sha256':digest(exe),'archive_sha256':digest(archive),
        'kernel_bytes':used,'labels':labels,'maximum_texture_edge':1024,
        'native_surface_scale':2,'output_resolution':[640,480],'logical_UI_grid':[320,240],
        'native_medium':'Exact original 12x24 Skies pixels and four alpha levels, one texel per output pixel',
        'native_small':'Uniform 2/3 Skies source, prepared as 8x16 pixels for the compact status line',
        'native_shadow_pixels':1,'native_filter':'Nearest at physical output density',
        'width_tables':'Byte-exact both banks; wording and compiled line wrapping retained',
        'HD_pixels':'Byte-exact original bank','archive_nonfont_members':'89 byte-exact; all offsets unchanged',
        'title_hook':previous['title_hook'],'metrics':metrics,
        'pending':['Native renderer/source pixel proof','Flycast 1x appearance and original hardware validation']}
    return bytes(exe),archive,hd+native,masks,report


def preview(masks,font):
    im=Image.new('RGB',(640,220),'#24282e');d=ImageDraw.Draw(im)
    d.text((12,8),'Skies source pixels at native 640x480 density - offline',fill='white')
    for bank,y,text,table,chars in [('medium',40,'Hah hah hah... We have finally found her...',0xa0,MEDIUM),
                                   ('small',84,'Lv 3 Exp 41   HP 420/420',0x20,SMALL),
                                   ('medium',124,'Touya  Zeifon  Move Type Land',0xa0,MEDIUM)]:
        x=12
        for ch in text:
            mask=masks[bank][ch];im.paste('white',(x,y,x+mask.width,y+mask.height),mask)
            x+=font[table+chars.index(ch)]*2
    return im


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    exe,archive,font,masks,report=compose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('metrics','labels','title_hook')},indent=2))
    if not args.write:print('DRY RUN: no files written');return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'1ST_READ.BIN').write_bytes(exe);(OUT/'WIN00.AFS').write_bytes(archive)
    (OUT/'font-mode-component.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    preview(masks,font).save(OUT/'native-preview.png')


if __name__=='__main__':main()
