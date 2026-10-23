"""Author eight English BREAK frames in the existing native effect atlases.

Dry run first. Reuses the current inferred Latin font, original palettes and
all geometry/animation commands. Glow/trail artwork is newly authored, not
an exact reconstruction of the original brush lettering or motion field.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image,ImageDraw,ImageFilter,ImageOps

from audit_effect_palettes import parse
from audit_pvm_archive import chunks
from audit_texture_archive import untwiddle_indices
from build_antialias_font import font_bytes
from build_bitmap_font import ROOT,digest
from build_font4x_patch import MEDIUM
from extract_attack_lettering import analyze
from preview_font_sampling import packed_mask
from rayblade_codec import compress,decompress

OUT=ROOT/'work/output/attack-lettering-draft-01'
PRIOR='0.1.32'
RECIPE=ROOT/'work/translation/en/ui/attack-lettering.en.json'
MEMBERS=(142,143,455,456)


def word_mask():
    win=(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()
    _,font=font_bytes(win)
    font_report=json.loads((ROOT/'work/output/font-outline-draft-01/component-report.json').read_text('utf-8'))
    assert digest(font)==font_report['target_font_sha256']
    line=np.zeros((64,256),np.uint8)
    cursor=0
    advances=[]
    for char in 'BREAK':
        glyph=np.asarray(packed_mask(font,char))
        line[:,cursor:cursor+64]=np.maximum(line[:,cursor:cursor+64],glyph)
        advance=font[0xa0+MEDIUM.index(char)]*4
        advances.append(advance)
        cursor+=advance
    image=Image.fromarray(line)
    bounds=image.getbbox()
    cropped=image.crop(bounds)
    factor=136/cropped.width
    resized=cropped.resize((136,round(cropped.height*factor)),Image.Resampling.LANCZOS)
    return resized,{'font_sha256':digest(font),'current_font_origin_build':'0.1.31',
                    'word':'BREAK','native_word_bounds':list(bounds),'native_advances_physical':advances,
                    'native_word_mask_sha256':digest(cropped.tobytes()),
                    'resized_mask_size':list(resized.size),'resized_mask_sha256':digest(resized.tobytes()),
                    'uniform_scale':factor,'sampling':'Whole-word Lanczos at one common scale; original native glyph masks/advances, no individual stretch'}


def placed(ink,center):
    mask=Image.new('L',(200,200))
    x=round(center[0]-ink.width/2)
    y=round(center[1]-ink.height/2)
    assert 0<=x and 0<=y and x+ink.width<=200 and y+ink.height<=200
    mask.paste(ink,(x,y))
    return mask


def colored_indices(mask,palette,source_indices,primary):
    a=np.asarray(mask,dtype=np.float32)/255
    halo=np.asarray(mask.filter(ImageFilter.GaussianBlur(6)),dtype=np.float32)/255
    far=np.asarray(mask.filter(ImageFilter.GaussianBlur(12)),dtype=np.float32)/255
    if primary:
        red=np.minimum(222,halo*210+far*80)
        rgb=np.stack([red*(1-a)+255*a,255*a,255*a],axis=2)
    else:
        soft=np.asarray(mask.filter(ImageFilter.GaussianBlur(1.4)),dtype=np.float32)/255
        # A short diagonal trail belongs to this newly authored English
        # effect. It is not an inferred native transform or hidden-pixel copy.
        trail=np.zeros_like(a)
        for shift in range(1,7):
            trail[shift:,:-shift]+=a[:-shift,shift:]*(7-shift)/21
        intensity=np.clip(.6*soft+.4*a+.22*trail+.34*halo+.15*far,0,1)
        value=intensity*255
        rgb=np.stack([value,value,(intensity**9)*255],axis=2)
    support=(a>0)|(halo>=2/255)|(far>=3/255)
    used=np.unique(source_indices)
    choices=np.array([int(i) for i in used if i and palette[i,3]==255],np.uint8)
    assert len(choices)>3
    rgb=np.rint(rgb).clip(0,255).astype(np.int32)
    colors=palette[choices,:3].astype(np.int32)
    difference=((rgb[:,:,None,:]-colors[None,None,:,:])**2).sum(axis=3)
    result=choices[difference.argmin(axis=2)]
    result[~support]=0
    return result.astype(np.uint8)


def compose():
    recipe=json.loads(RECIPE.read_text('utf-8'))
    assert len(recipe['rows'])==8 and all(r['English_target']=='BREAK' for r in recipe['rows'])
    source_map,_,_=analyze()
    resources={r['member']:r for r in source_map['resources']}
    source=(ROOT/'work/output'/PRIOR/'EFFECT.AFS').read_bytes()
    assert source[:4]==b'AFS\0' and struct.unpack_from('<I',source,4)[0]==460
    offsets=[struct.unpack_from('<II',source,8+i*8) for i in range(460)]
    target=bytearray(source)
    ink,font=word_mask()
    replacements,details,images={},{},{}
    prefix_cursor=0x10000
    for member in MEMBERS:
        offset,size=offsets[member]
        packed=source[offset:offset+size]
        plain,texture,palette,before,colors,info=parse(packed)
        original=resources[member]
        assert digest(packed)==original['packed_sha256']
        assert digest(plain)==original['decoded_sha256']
        plane=before.copy()
        allowed=np.zeros_like(plane,bool)
        draws=[]
        for row in [r for r in recipe['rows'] if r['source_member']==member]:
            sprite=row['sprite']
            box=row['source_box']
            x,y,u,v=box
            source_cell=before[y:v,x:u]
            assert digest(source_cell.tobytes())==row['source_index_sha256']
            if sprite==8:
                # Retain the primary glyph's optical placement, including
                # the source's exact 40-pixel vertical variant difference.
                colors_here=colors[5][source_cell]
                yy,xx=np.nonzero((colors_here[:,:,:3].min(axis=2)>=245)&(colors_here[:,:,3]>0))
                assert len(xx)>100
                center=[(int(xx.min())+int(xx.max())+1)/2,(int(yy.min())+int(yy.max())+1)/2]
                frame=placed(ImageOps.mirror(ink) if member in (455,456) else ink,center)
                angle=0
            else:
                center=[100,100]
                angle=-12 if member in (142,455) else 12
                frame=placed(ink,center).rotate(angle,Image.Resampling.BICUBIC,expand=False)
            if sprite==9 and member in (455,456):
                # These source frames already contain reversed lettering.
                # Keep that variant relationship without altering native flags.
                frame=ImageOps.mirror(frame)
            bank=5 if sprite==8 else 6
            cell=colored_indices(frame,colors[bank],source_cell,sprite==8)
            plane[y:v,x:u]=cell
            allowed[y:v,x:u]=True
            draws.append({'id':row['id'],'sprite':sprite,'en':'BREAK','source_box':box,
                          'source_index_sha256':row['source_index_sha256'],
                          'target_index_sha256':digest(cell.tobytes()),'preview_palette_bank':bank,
                          'ink_center':center,'whole_word_rotation_degrees':angle,
                          'reversed_source_variant':member in (455,456),
                          'word_mask_sha256':digest(frame.tobytes())})
        assert np.array_equal(before[~allowed],plane[~allowed])
        for row in original['rectangles']:
            if row['sprite'] in (8,9):
                continue
            x,y,u,v=row['source_box']
            assert np.array_equal(before[y:v,x:u],plane[y:v,x:u]),row['id']
        order=untwiddle_indices(512,512).ravel()
        linear=np.empty(512*512,np.uint8)
        linear[order]=plane.ravel()
        indices=(linear[::2]|linear[1::2]<<4).tobytes()
        tex_offset=chunks(plain)[2][0]['chunk_offset']
        edited=plain[:tex_offset+16]+indices+plain[tex_offset+len(texture):]
        assert len(edited)==len(plain)
        encoded=compress(edited)
        assert decompress(encoded)==(edited,len(encoded))
        parsed,_,new_palette,decoded_indices,new_colors,_=parse(encoded)
        assert parsed==edited and palette==new_palette and np.array_equal(colors,new_colors)
        assert np.array_equal(plane,decoded_indices)
        capacity=min(o for o,n in offsets if o>offset)-offset
        destination=offset
        if len(encoded)>capacity:
            destination=prefix_cursor
            reserve=(len(encoded)+2047)//2048*2048
            assert destination+reserve<=min(o for o,n in offsets)
            assert target[destination:destination+reserve]==bytes(reserve)
            prefix_cursor+=reserve
        elif len(encoded)>size:
            assert target[offset+size:offset+len(encoded)]==bytes(len(encoded)-size)
        target[destination:destination+len(encoded)]=encoded
        struct.pack_into('<II',target,8+member*8,destination,len(encoded))
        replacements[member]=(encoded,edited)
        details[member]={'member':member,'source_offset':offset,'target_offset':destination,
                         'source_packed_bytes':size,'source_slot_capacity':capacity,'packed_bytes':len(encoded),
                         'packed_sha256':digest(encoded),'decoded_bytes':len(edited),'decoded_sha256':digest(edited),
                         'geometry_sha256':original['geometry_sha256'],'palette_sha256':original['palette_sha256'],
                         'palette_banks':info['palette_banks'],'texture_dimensions':[512,512],
                         'protected_sprites':24,'changed_pixels':int((before!=plane).sum()),'draws':draws}
        images[member]=(before,plane,colors)
    for member,(offset,size) in enumerate(offsets):
        if member not in MEMBERS:
            assert target[offset:offset+size]==source[offset:offset+size]
    assert len(target)==len(source)
    report={'kind':'Native English BREAK artwork candidate; native checks/packaging/live review pending',
            'source_build':PRIOR,'source_archive_sha256':digest(source),'target_archive_sha256':digest(target),
            'archive_bytes':len(source),'translation_recipe_sha256':digest(RECIPE.read_bytes()),
            'font':font,'artwork_frame_count':8,'resources':list(details.values()),
            'unchanged_member_payloads_and_offsets':456,'all_geometry_and_palettes':'byte-exact original',
            'artwork_method':'Current inferred Latin masks, one common whole-word scale, optical primary placements, reversed variants, reauthored red glow and yellow rotated/trailing frames',
            'fidelity_limit':'New English effect artwork approximates the original glow/motion treatment; no exact brush-contour or motion-field reconstruction claimed',
            'pending':['Independent native index/mask/archive preservation and decoder checks','Disc packaging',
                       'Whole attack, native frame transforms, palette animation/timing and live artwork/meaning review']}
    return bytes(target),report,replacements,images


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,report,replacements,images=compose()
    print('Plan: eight English effect frames in four native resources; all geometry/palettes and 456 other members exact.',flush=True)
    print('Compressed sizes/slots:',[(r['member'],r['packed_bytes'],r['source_slot_capacity'],r['target_offset']) for r in report['resources']])
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'EFFECT.AFS').write_bytes(archive)
    (OUT/'component-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    for member,(encoded,plain) in replacements.items():
        (OUT/f'member-{member:03d}.packed.bin').write_bytes(encoded)
        (OUT/f'member-{member:03d}.pvm').write_bytes(plain)
    for member,(before,after,colors) in images.items():
        sheet=Image.new('RGB',(820,870),'#30333a')
        draw=ImageDraw.Draw(sheet)
        rows=next(r for r in report['resources'] if r['member']==member)['draws']
        for n,row in enumerate(rows):
            bank=row['preview_palette_bank']
            for col,plane in enumerate((before,after)):
                im=Image.fromarray(colors[bank][plane]).crop(row['source_box'])
                im=im.resize((400,400),Image.Resampling.NEAREST)
                sheet.paste(im,(col*410,n*435),im)
            draw.text((2,n*435+408),row['id']+' source / English; explicit palette bank '+str(bank),fill='white')
        sheet.save(OUT/f'before-after-{member:03d}.png')
    print('Wrote candidate and eight source/target frame witnesses; no game build written.')


if __name__=='__main__':
    main()
