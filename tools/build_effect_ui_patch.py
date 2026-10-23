"""Build nine English labels in the native EFFECT paletted atlas. Dry run first.

Preserves all palettes, draw sizes/anchors and texture-parameter words.
The full Ballistic Barrier label moves into unused atlas space so the shared
standalone Barrier sprite can retain its own centered English text.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from audit_effect_palettes import original, parse
from audit_pvm_archive import chunks
from audit_texture_archive import untwiddle_indices
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import mask
from extract_effect_ui import analyze
from prepare_effect_ui_translation import DEST, prepare
from rayblade_codec import compress, decompress

OUT=ROOT/'work/output/effect-ui-draft-01'
NEW_BALLISTIC_BOX=[0,208,96,224]
# Keep original indexed color roles. Main labels already use 7 for the light
# stroke, 1..6 for its shaded edge, 8 for the dark drop shadow, 0 transparent.
# Prana's original monochrome label uses 1/8/0 instead.
EDGE=[6,5,4,3,2,1,7]


def stamp(cell,text,denominator,monochrome=False):
    ink=mask(text,denominator)
    h,w=ink.shape
    assert w+1<=cell.shape[1] and h+1<=cell.shape[0]
    x=(cell.shape[1]-w-1)//2
    y=(cell.shape[0]-h-1)//2
    for yy,xx in zip(*np.nonzero(ink)):
        cell[y+yy+1,x+xx+1]=8
    for yy,xx in zip(*np.nonzero(ink)):
        coverage=int(ink[yy,xx])
        cell[y+yy,x+xx]=1 if monochrome else EDGE[min(6,(coverage*7)//256)]
    return {'mask_size':[w,h],'ink_box':[x,y,x+w+1,y+h+1],
            'color_roles':'1/8/0' if monochrome else '7 core, 1..6 edge, 8 shadow, 0 transparent'}


def compose():
    recipe=json.loads(DEST.read_text('utf-8'))
    assert recipe==prepare()[0]
    geometry_info,*_=analyze()
    archive,members=original()
    plain,texture,pal,before,colors,info=parse(members[250])
    target_plane=before.copy()
    selected={r['sprite'] for r in recipe['rows']}
    allowed=np.zeros((256,256),bool)
    draws=[]
    for row in recipe['rows']:
        x0,y0,x1,y1=row['source_box']
        assert digest(before[y0:y1,x0:x1].tobytes())==row['source_index_sha256']
        target_plane[y0:y1,x0:x1]=0
        allowed[y0:y1,x0:x1]=True
    x0,y0,x1,y1=NEW_BALLISTIC_BOX
    assert not before[y0:y1,x0:x1].any()
    # The destination must be unused by every existing source sprite.
    for source in geometry_info['rectangles']:
        a,b,c,d=source['source_box']
        assert max(a,x0)>=min(c,x1) or max(b,y0)>=min(d,y1)
    target=bytearray(plain)
    geometry_offset=chunks(plain)[0][0]['chunk_offset']+16
    for row in recipe['rows']:
        box=NEW_BALLISTIC_BOX if row['sprite']==94 else row['source_box']
        x0,y0,x1,y1=box
        allowed[y0:y1,x0:x1]=True
        rendering=stamp(target_plane[y0:y1,x0:x1],row['en'],row['font_scale_denominator'],row['sprite']==57)
        draws.append({**row,'target_box':box,'rendering':rendering})
        if row['sprite']==94:
            # UV coordinates only; original dimensions, center and packed
            # texture/palette parameter remain byte-for-byte unchanged.
            struct.pack_into('<4H',target,geometry_offset+row['record_offset']+8,*box)
    assert np.array_equal(before[~allowed],target_plane[~allowed])
    for source in geometry_info['rectangles']:
        if source['sprite'] in selected:
            continue
        a,b,c,d=source['source_box']
        assert np.array_equal(before[b:d,a:c],target_plane[b:d,a:c]),source['id']
    morton=untwiddle_indices(256,256).ravel()
    linear=np.empty(256*256,np.uint8)
    linear[morton]=target_plane.ravel()
    packed_indices=(linear[::2]|(linear[1::2]<<4)).tobytes()
    texture_offset=chunks(plain)[2][0]['chunk_offset']
    target[texture_offset+16:texture_offset+len(texture)]=packed_indices
    target=bytes(target)
    packed=compress(target)
    assert decompress(packed)==(target,len(packed))
    # Parse the newly authored native resource and verify every palette bank
    # still maps precisely the original stored color entries.
    decoded,new_texture,new_palette,new_indices,new_colors,_=parse(packed)
    assert decoded==target and new_palette==pal and np.array_equal(colors,new_colors)
    assert new_texture[:16]==texture[:16] and np.array_equal(new_indices,target_plane)
    offsets=[struct.unpack_from('<II',archive,8+n*8) for n in range(460)]
    offset,source_size=offsets[250]
    capacity=offsets[251][0]-offset
    assert len(packed)<=capacity
    if len(packed)>source_size:
        assert archive[offset+source_size:offset+len(packed)]==bytes(len(packed)-source_size)
    result=bytearray(archive)
    result[offset:offset+len(packed)]=packed
    struct.pack_into('<II',result,8+250*8,offset,len(packed))
    assert len(result)==len(archive)
    for n,(pos,size) in enumerate(offsets):
        if n!=250:
            assert result[pos:pos+size]==members[n]
    report={'kind':'Native English effect/UI candidate; native checks and packaging pending',
            'source_build':'0.1.31','archive':'EFFECT.AFS','member':250,
            'source_archive_sha256':digest(archive),'target_archive_sha256':digest(result),
            'archive_bytes':len(result),'source_packed_sha256':digest(members[250]),
            'packed_sha256':digest(packed),'decoded_sha256':digest(target),
            'source_packed_bytes':source_size,'packed_bytes':len(packed),'slot_capacity':capacity,
            'member_offset':offset,'decoded_bytes':len(target),
            'source_geometry_sha256':geometry_info['geometry_sha256'],
            'palette_sha256':digest(pal),'palette_banks':info['palette_banks'],
            'texture_dimensions':[256,256],'pixel_format':'External ARGB1555 palette, 4-bit twiddled indices',
            'translation_map_sha256':digest(DEST.read_bytes()),
            'label_count':len(draws),'draws':draws,'geometry_record_count':125,
            'protected_sprite_count':125-len(draws),'unchanged_member_payloads_and_offsets':459,
            'changed_pixels':int((before!=target_plane).sum()),'geometry_UV_changed_sprites':[94],
            'draw_sizes_anchors_and_raw_texture_parameters':'all unchanged',
            'pending':['Native PRS and independent geometry/index/mask/archive checks',
                       'Disc packaging','Native palette binding, live archive loading and battle label appearance',
                       'Four status icons, calligraphy and remaining image discovery/meaning review']}
    images=(Image.fromarray(colors[4][before]),Image.fromarray(colors[4][target_plane]),colors,before,target_plane)
    return bytes(result),report,packed,target,images


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,report,packed,decoded,images=compose()
    print('Plan:',report['label_count'],'English labels;',report['packed_bytes'],'/',report['slot_capacity'],
          'compressed slot bytes; 459 other members and 116 other sprites exact.',flush=True)
    print('Sprite 094 UV moves to',NEW_BALLISTIC_BOX,'inside the existing 256x256 atlas; all sizes/anchors/palettes exact.')
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in [('EFFECT.AFS',archive),('member-250.packed.bin',packed),('member-250.pvm',decoded)]:
        (OUT/name).write_bytes(data)
    (OUT/'component-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n','utf-8')
    source,target,colors,old,new=images
    # Explicit bank-four text witnesses and the Prana label's original bank
    # zero. These previews do not claim to execute native palette selection.
    sheet=Image.new('RGB',(1000,40+len(report['draws'])*95),'#30333a')
    draw=ImageDraw.Draw(sheet)
    draw.text((4,4),'Source / English native-index candidate. Bank 4; Prana bank 0. Live palette/GPU pending.',fill='white')
    for n,row in enumerate(report['draws']):
        bank=0 if row['sprite']==57 else 4
        for xx,plane,box in [(0,old,row['source_box']),(500,new,row['target_box'])]:
            image=Image.fromarray(colors[bank][plane]).crop(box)
            image=image.resize((image.width*4,image.height*4),Image.Resampling.NEAREST)
            sheet.paste(image,(xx,36+n*95),image)
        draw.text((2,104+n*95),row['id']+' '+row['en'],fill='white')
    sheet.save(OUT/'labels-before-after.png')
    target.resize((1024,1024),Image.Resampling.NEAREST).save(OUT/'atlas-bank-04-4x.png')
    print('Wrote native archive candidate and nine source/target witnesses; no game build written.')


if __name__=='__main__':
    main()
