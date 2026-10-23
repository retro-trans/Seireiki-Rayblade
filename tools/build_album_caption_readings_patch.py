"""Insert two newly read album captions; retain all preceding album work.

Default dry run. Only the two original 64x24 caption cells change. Reuses
the preceding 201-caption sampling/style without changing the normal font.
"""
import argparse
from collections import Counter
import json
import struct

import numpy as np
from PIL import Image,ImageDraw

from audit_texture_archive import decode_pvr,untwiddle_indices
from build_bitmap_font import ROOT,ATLAS,digest
from build_ui_atlas_patch import pixels
from extract_album_captions import analyze
from prepare_album_caption_readings import DEST,prepare
from prepare_album_translations import caption_mask
from rayblade_codec import compress,decompress

PRIOR='0.1.36'
OUT=ROOT/'work/output/album-caption-readings-draft-01'


def compose():
    recipe=json.loads(DEST.read_text('utf-8'))
    assert recipe==prepare()
    info,_,_,source_textures=analyze()
    source=(ROOT/'work/output'/PRIOR/'ALBUM.AFS').read_bytes()
    offsets=[struct.unpack_from('<II',source,8+i*8) for i in range(244)]
    result=bytearray(source)
    outputs={}
    resources=[]
    previews=[]
    for row in recipe['rows']:
        member=row['texture_member']
        assert member not in outputs
        offset,size=offsets[member]
        raw=source[offset:offset+size]
        plain,used=decompress(raw[16:])
        assert used==len(raw)-16
        before=pixels(plain,256,256)
        after=before.copy()
        x,y,u,v=row['caption_box']
        assert digest(decode_pvr(plain)[0].crop(row['caption_box']).tobytes())==row['source_caption_sha256']
        cell=after[y:v,x:u]
        bg=Counter(map(int,cell.ravel())).most_common(1)[0][0]
        assert bg&32768 and min((bg>>s)&31 for s in (10,5,0))>=24
        cell[:]=bg
        top=(24-len(row['wrapped_lines'])*8)//2
        draws=[]
        for line in row['wrapped_lines']:
            ink=caption_mask(line)
            h,w=ink.shape
            assert h==8 and w<=62 and top+h<=24
            for yy,xx in zip(*np.nonzero(ink)):
                a=int(ink[yy,xx])
                rgb=[(((bg>>s)&31)*(255-a)+127)//255 for s in (10,5,0)]
                cell[top+yy,1+xx]=32768|(rgb[0]<<10)|(rgb[1]<<5)|rgb[2]
            draws.append({'en':line,'box':[x+1,y+top,x+1+w,y+top+h],
                          'mask_sha256':digest(ink.tobytes())})
            top+=8
        allowed=np.zeros((256,256),bool)
        allowed[y:v,x:u]=True
        assert np.array_equal(before[~allowed],after[~allowed])
        linear=np.empty(256*256,'<u2')
        linear[untwiddle_indices(256,256).ravel()]=after.ravel()
        decoded=plain[:32]+linear.tobytes()
        packed=raw[:16]+compress(decoded)
        assert decompress(packed[16:])==(decoded,len(packed)-16)
        end=min([o for o,s in offsets if o>offset]+[len(source)])
        assert len(packed)<=end-offset,(member,len(packed),end-offset)
        if len(packed)>size:
            assert source[offset+size:offset+len(packed)]==bytes(len(packed)-size)
        result[offset:offset+len(packed)]=packed
        struct.pack_into('<I',result,12+member*8,len(packed))
        outputs[member]=(packed,decoded)
        resources.append({'member':member,'offset':offset,'source_packed_bytes':size,
                          'packed_bytes':len(packed),'slot_capacity':end-offset,'decoded_bytes':len(decoded),
                          'packed_sha256':digest(packed),'decoded_sha256':digest(decoded),
                          'changed_pixels':int((before!=after).sum()),'id':row['id'],'en':row['en'],
                          'caption_box':row['caption_box'],'background_pixel':bg,'draws':draws})
        previews.append((row,source_textures[member][1].crop(row['source_box']),
                          decode_pvr(decoded)[0].crop(row['source_box'])))
    assert len(result)==len(source) and set(outputs)=={225,227}
    component={'source_build':PRIOR,'archive':'ALBUM.AFS','source_archive_sha256':digest(source),
               'target_archive_sha256':digest(result),'archive_bytes':len(result),
               'new_caption_count':2,'combined_caption_count':203,'unresolved_caption_ids':[],
               'translation_recipe':str(DEST.relative_to(ROOT)).replace('\\','/'),
               'translation_recipe_sha256':digest(DEST.read_bytes()),
               'font_atlas_sha256':digest(ATLAS.read_bytes()),
               'font_sampling':'Same uniform 1/3 area coverage as 201 preceding captions, variable bearings and no per-letter stretching',
               'resources':resources,'all_geometry':'exact previous DAT214',
               'normal_font_changed':False,'story_library_draft_credit':0,
               'pending':['Independent newly resolved caption reading/wording review',
                          'Live album loading, unlock/selection/navigation, caption fit and appearance']}
    return bytes(result),component,outputs,previews


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,component,outputs,previews=compose()
    print(json.dumps(component['resources'],indent=2))
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'ALBUM.AFS').write_bytes(archive)
    (OUT/'component-report.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
    for member,(packed,decoded) in outputs.items():
        (OUT/f'member-{member:03d}.packed.bin').write_bytes(packed)
        (OUT/f'member-{member:03d}.pvr').write_bytes(decoded)
    sheet=Image.new('RGB',(1100,440),'#30333a')
    draw=ImageDraw.Draw(sheet)
    draw.text((12,10),'Original caption / newly read English caption; photos exact preceding build. Asset preview, not live.',fill='white')
    for i,(row,before,after) in enumerate(previews):
        x=12+i*550
        for j,im in enumerate((before,after)):
            crop=im.resize((256,288),Image.Resampling.NEAREST)
            sheet.paste(crop,(x+j*270,55),crop)
        draw.text((x,365),row['id']+' - '+row['en'],fill='white')
    sheet.save(OUT/'before-after.png')
    print('Wrote two native caption resources and comparison; no game build written.')


if __name__=='__main__':
    main()
