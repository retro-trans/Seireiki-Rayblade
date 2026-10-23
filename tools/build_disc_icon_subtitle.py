"""Add English identification below the original Dreamcast disc icon logo.

Default dry run. Original bright logo/mech pixels and all bytes outside the
small subtitle strokes remain exact. Uses current inferred Latin contours.
"""
import argparse
import json

import numpy as np
from PIL import Image,ImageDraw,ImageFilter

from audit_texture_archive import untwiddle_indices,decode_pvr
from build_antialias_font import font_bytes
from build_bitmap_font import ROOT,digest
from build_font4x_patch import MEDIUM
from build_ui_atlas_patch import pixels
from disc_inventory import Disc
from preview_font_sampling import packed_mask

PRIOR='0.1.35'
OUT=ROOT/'work/output/disc-icon-subtitle-draft-01'
DEST=ROOT/'work/translation/en/ui/disc-icon-subtitle.en.json'
TEXT='SEIREIKI RAYBLADE'


def original():
    disc=Disc(next(ROOT.glob('*.cue')))
    row=next(r for r in disc.inventory() if r['path']=='0GDTEX.PVR')
    raw=disc.read(row['lba'],row['size'])
    assert len(raw)==131104 and digest(raw)=='832744af5cf281e3665f204eb3d4f9ef92221ea72e1fc7214748494f5a3df02e'
    return raw


def word_mask(font,text=TEXT):
    canvas=Image.new('L',(512,64))
    cursor=0
    for char in text:
        mask=packed_mask(font,char)
        # Adjacent glyph ink may share a bearing; retain maximum coverage.
        plane=np.array(canvas)
        plane[:,cursor:cursor+64]=np.maximum(plane[:,cursor:cursor+64],np.asarray(mask))
        canvas=Image.fromarray(plane)
        cursor+=font[0xa0+MEDIUM.index(char)]*4
    bounds=canvas.getbbox()
    assert bounds[1]>=7 and bounds[3]<=47
    # Fixed cap band retains one baseline and scale across both words, even
    # when a word's contours occupy one fewer source row.
    band=[bounds[0],7,bounds[2],47]
    trimmed=canvas.crop(band)
    # One common whole-word scale; no individual glyph stretching.
    resized=trimmed.resize((round(trimmed.width*8/trimmed.height),8),Image.Resampling.LANCZOS)
    return resized,{'native_assembled_bounds':list(bounds),'common_cap_band':band,
                    'native_word_sha256':digest(trimmed.tobytes()),
                    'resized_mask_sha256':digest(resized.tobytes()),'mask_size':list(resized.size),
                    'whole_word_scale':8/trimmed.height}


def compose():
    source=original()
    glossary=json.loads((ROOT/'work/glossary/glossary.json').read_text('utf-8'))
    assert next(r['en'] for r in glossary['entries'] if r['id']=='term.001').upper()==TEXT
    _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    ink=Image.new('L',(256,256))
    parts=[]
    for word,left,top in [('SEIREIKI',92,240),('RAYBLADE',132,240)]:
        mask,info=word_mask(font,word)
        assert info['whole_word_scale']==0.2
        ink.paste(mask,(left,top))
        parts.append({'text':word,'origin':[left,top],**info})
    outline=ink.filter(ImageFilter.MaxFilter(3))
    a=np.asarray(ink)
    b=np.asarray(outline)
    before=pixels(source,256,256)
    after=before.copy()
    def blend(mask,color):
        alpha=mask.astype(np.uint32)
        selected=alpha>0
        result=np.zeros(before.shape,np.uint16)
        for shift in (10,5,0):
            old=(after.astype(np.uint32)>>shift)&31
            channel=(old*(255-alpha)+color*alpha+127)//255
            result|=(channel.astype(np.uint16)<<shift)
        after[selected]=result[selected]|32768
    blend(b,0)
    blend(a,31)
    changed=before!=after
    rgb=np.stack([((before>>shift)&31) for shift in (10,5,0)],axis=2)
    # The margin includes faint blue glow, but no bright logo/mech contour.
    protected=rgb.max(axis=2)>12
    assert not changed[protected].any()
    assert not ((b>0)&((before&32768)==0)).any()
    assert np.array_equal(before&32768,after&32768)
    assert not changed[:239].any() and not (changed&(b==0)).any()
    linear=np.empty(256*256,'<u2')
    linear[untwiddle_indices(256,256).ravel()]=after.ravel()
    target=source[:32]+linear.tobytes()
    assert len(target)==len(source) and target[:32]==source[:32]
    recipe={'id':'disc-icon.subtitle','file':'0GDTEX.PVR','source_sha256':digest(source),
            'en':TEXT,'glossary_id':'term.001','treatment':'Original artwork + English subtitle',
            'stroke_bounds':list(outline.getbbox()),'word_origins':[r['origin'] for r in parts],
            'method':'Current inferred Latin masks/advances, one common whole-word scale to eight ink pixels high; black outline and white coverage blended into original ARGB1555 pixels',
            'font_sha256':digest(font),'normal_font_changed':False,
            'interword_gap':'Sixteen pixels of visual space retains the original central blade tip',
            'source_transparency':'All 65536 alpha bits exact; subtitle stays inside opaque disc',
            'limits':'Dreamcast/Flycast disc-selection appearance and readability unverified; not a replacement English logo'}
    component={'source_build':PRIOR,'file':'0GDTEX.PVR','source_archive_sha256':digest(source),
               'target_archive_sha256':digest(target),'file_bytes':len(target),
               'subtitle_count':1,'text':TEXT,'dimensions':[256,256],'changed_pixels':int(changed.sum()),
               'font_sha256':digest(font),'word_masks':parts,'recipe':recipe,
               'bright_logo_mech_pixels':'All source channels above 12/31 protected; none changed',
               'outside_subtitle_strokes':'exact source','PVR_header':'exact source',
               'live_validation':'pending'}
    return target,component,ink,outline


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    target,component,ink,outline=compose()
    print(json.dumps({k:component[k] for k in ('dimensions','changed_pixels','word_masks','bright_logo_mech_pixels')},indent=2))
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'0GDTEX.PVR').write_bytes(target)
    (OUT/'component-report.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
    DEST.write_text(json.dumps(component['recipe'],indent=2)+'\n','utf-8')
    ink.save(OUT/'subtitle-ink.png')
    outline.save(OUT/'subtitle-outline.png')
    before=decode_pvr(original())[0]
    after=decode_pvr(target)[0]
    page=Image.new('RGB',(1080,600),'#30333a')
    draw=ImageDraw.Draw(page)
    draw.text((12,12),'Original disc icon / Original artwork + English subtitle (2x preview, live appearance unverified)',fill='white')
    for x,image in ((12,before),(552,after)):
        crop=image.resize((512,512),Image.Resampling.NEAREST)
        page.paste(crop,(x,55),crop)
    page.save(OUT/'before-after.png')
    print('Wrote native disc-icon candidate and comparison; no game build written.')


if __name__=='__main__':
    main()
