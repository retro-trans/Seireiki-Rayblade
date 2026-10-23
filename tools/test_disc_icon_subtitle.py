"""Check disc-icon pixels, current glyph masks, native header and sector tails.

Actual Dreamcast BIOS/Flycast disc-list rendering remains unverified.
"""
import argparse
import json

import numpy as np
from PIL import Image,ImageFilter

from build_antialias_font import font_bytes
from build_bitmap_font import ROOT,digest
from build_disc_icon_subtitle import OUT,PRIOR,compose,original
from build_font4x_patch import MEDIUM
from build_genei_font import MEDIUM_DATA
from build_test_disc import regenerate
from disc_inventory import Disc,SECTOR
from package_archive_test_disc import substitute_payload_sector
from test_ui_images import scalar_plane,texture_info


def reference_word(font,text):
    canvas=np.zeros((64,512),np.uint8)
    cursor=0
    for char in text:
        index=MEDIUM.index(char)
        for y in range(64):
            for x in range(32):
                start=MEDIUM_DATA+index*512+y*8+(x//16)*4
                word=int.from_bytes(font[start:start+4],'little')
                value=(0,85,187,255)[(word>>(30-2*(x%16)))&3]
                canvas[y,cursor+x]=max(int(canvas[y,cursor+x]),value)
        cursor+=font[0xa0+index]*4
    im=Image.fromarray(canvas)
    a,_,b,_=im.getbbox()
    crop=im.crop((a,7,b,47))
    return crop.resize((round(crop.width/5),8),Image.Resampling.LANCZOS)


def sector_cases():
    disc=Disc(next(ROOT.glob('*.cue')))
    row=next(r for r in disc.inventory() if r['path']=='0GDTEX.PVR')
    source=original()
    cases=[]
    for index,length in ((0,2048),(64,32)):
        lba=row['lba']+index
        track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
        offset=(track['index']+lba-track['start_lba'])*SECTOR
        with track['path'].open('rb') as handle:
            handle.seek(offset)
            raw=handle.read(SECTOR)
        piece=source[index*2048:index*2048+length]
        assert len(piece)==length and raw[16:16+length]==piece
        altered=bytearray(piece)
        altered[-1]^=1
        result=substitute_payload_sector(raw,piece,bytes(altered))
        assert len(result)==SECTOR and regenerate(result)==result
        assert result[:16]==raw[:16]
        assert result[16:16+length]==altered and result[16+length:2064]==raw[16+length:2064]
        assert substitute_payload_sector(raw,piece,piece)==raw
        if length==2048:
            prior=bytearray(raw)
            prior[16:2064]=altered
            assert result==regenerate(prior)
        cases.append({'sector_index':index,'file_bytes_in_sector':length,
                      'other_payload_padding_bytes_preserved':2048-length,'EDC_ECC':'pass'})
    return cases


def check():
    target,component,_,_=compose()
    assert (OUT/'0GDTEX.PVR').read_bytes()==target
    assert json.loads((OUT/'component-report.json').read_text('utf-8'))==component
    src=original()
    before,after=scalar_plane(src,256,256),scalar_plane(target,256,256)
    _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    expected=before.copy()
    mask=Image.new('L',(256,256))
    for row in component['word_masks']:
        glyphs=reference_word(font,row['text'])
        assert list(glyphs.size)==row['mask_size'] and digest(glyphs.tobytes())==row['resized_mask_sha256']
        mask.paste(glyphs,tuple(row['origin']))
    outline=mask.filter(ImageFilter.MaxFilter(3))
    assert mask.tobytes()==Image.open(OUT/'subtitle-ink.png').tobytes()
    assert outline.tobytes()==Image.open(OUT/'subtitle-outline.png').tobytes()
    # Scalar ARGB1555 compositing, separate from vector production blending.
    for layer,color in ((outline,0),(mask,31)):
        for y in range(256):
            for x in range(256):
                alpha=layer.getpixel((x,y))
                if not alpha:
                    continue
                old=int(expected[y,x])
                value=32768
                for shift in (10,5,0):
                    mixed=(((old>>shift)&31)*(255-alpha)+color*alpha+127)//255
                    value|=mixed<<shift
                expected[y,x]=value
    assert np.array_equal(after,expected)
    changed=before!=after
    support=np.asarray(outline)>0
    assert not changed[~support].any()
    assert np.array_equal(before&32768,after&32768)
    assert not (support&((before&32768)==0)).any()
    bright=np.maximum.reduce([(before>>shift)&31 for shift in (10,5,0)])>12
    assert not changed[bright].any() and not changed[:239].any()
    assert target[:32]==src[:32] and len(target)==len(src)==131104
    exe=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    # SDK format packs storage layout in the second byte, not pixel format.
    assert src[24:28]==bytes.fromhex('00010000')
    header=texture_info(exe,256,256,0x100)
    return {'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(target),
            'subtitle_count':1,'scalar_texture_pixels':65536,'changed_pixels':int(changed.sum()),
            'protected_source_alpha_bits':65536,'protected_bright_source_pixels':int(bright.sum()),
            'source_native_font_samples':16*64*32,'native_texture_header_instructions':header,
            'native_guard_and_ABI':'pass','archive_bytes_outside_declared_edits':'exact',
            'source_bytes_outside_subtitle_strokes':'exact','PVR_header':'exact',
            'sector_substitution_cases':sector_cases(),'normal_font_changed':False,
            'limits':['Native header check executes the game SDK helper, not the Dreamcast BIOS disc renderer',
                      'No actual disc-menu/BIOS/Flycast icon rendering or small-caption readability proof',
                      'No PRS decoder applies to this uncompressed PVR file; original alpha silhouette and bright artwork stay exact']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: all 65536 source pixels/alpha bits, exact current font words, scalar blends, native SDK header and full/32-byte sector-tail fixtures.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution/report')
        return
    result=check()
    print('PASS:',result['changed_pixels'],'subtitle pixels;',result['protected_bright_source_pixels'],
          'bright artwork pixels protected; alpha/header/padding and native SDK header pass.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
