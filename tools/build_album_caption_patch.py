"""Insert complete English captions in original 64x24 album label areas.

All 224 photo areas, 21 Coming Soon cells, two unreadable captions and DAT
geometry stay exact. Full-size artwork, including pictured text, is unchanged.
Default dry run; font textures remain 256x256 native ARGB1555.
"""
import argparse
from collections import Counter
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr, untwiddle_indices
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import pixels
from extract_album_captions import analyze
from prepare_album_translations import DEST, prepare, caption_mask
from rayblade_codec import compress, decompress

OUT = ROOT / 'work/output/album-captions-draft-01'


def compose():
    recipe = json.loads(DEST.read_text('utf-8'))
    assert recipe == prepare() and not recipe['overflows']
    info, original, members, textures = analyze()
    target = bytearray(original)
    offsets = [struct.unpack_from('<II', original, 8+i*8) for i in range(244)]
    assert all(a[0]+a[1] <= b[0] for a,b in zip(offsets, offsets[1:]))
    free = 0x10000
    first_data = min(o for o,_ in offsets)
    resources, outputs, images = [], {}, {}
    for member, (plain, image) in textures.items():
        before = pixels(plain,256,256)
        after = before.copy()
        allowed = np.zeros((256,256),bool)
        rows = [r for r in recipe['rows'] if r['texture_member']==member and r['en']]
        draws = []
        for row in rows:
            x0,y0,x1,y1 = row['caption_box']
            assert digest(image.crop(row['caption_box']).tobytes()) == row['source_caption_sha256']
            cell = after[y0:y1,x0:x1]
            bg = Counter(map(int,cell.ravel())).most_common(1)[0][0]
            assert bg & 32768 and min((bg>>s)&31 for s in (10,5,0)) >= 24
            cell[:] = bg
            allowed[y0:y1,x0:x1] = True
            y = (24-len(row['wrapped_lines'])*8)//2
            line_draws = []
            for line in row['wrapped_lines']:
                ink = caption_mask(line)
                h,w = ink.shape
                assert h==8 and w<=62 and y+h<=24
                x=1
                for yy,xx in zip(*np.nonzero(ink)):
                    coverage = int(ink[yy,xx])
                    channels = [(((bg>>s)&31)*(255-coverage)+127)//255 for s in (10,5,0)]
                    cell[y+yy,x+xx] = 32768 | channels[0]<<10 | channels[1]<<5 | channels[2]
                line_draws.append({'en':line,'box':[x0+x,y0+y,x0+x+w,y0+y+h]})
                y += 8
            draws.append({'id':row['id'],'en':row['en'],'caption_box':row['caption_box'],
                          'background_pixel':hex(bg),'lines':line_draws})
        assert np.array_equal(before[~allowed],after[~allowed])
        for row in info['rectangles']:
            if row['texture_member']!=member:continue
            x0,y0,x1,y1=row['source_box']
            assert np.array_equal(before[y0:y0+48,x0:x1],after[y0:y0+48,x0:x1])
            if not any(r['id']==row['id'] for r in rows):
                assert np.array_equal(before[y0:y1,x0:x1],after[y0:y1,x0:x1])
        linear=np.empty(256*256,dtype='<u2')
        linear[untwiddle_indices(256,256).ravel()]=after.ravel()
        decoded=plain[:32]+linear.tobytes()
        packed=members[member][:16]+compress(decoded)
        assert decompress(packed[16:])==(decoded,len(packed)-16)
        source_offset,source_size=offsets[member]
        capacity=offsets[member+1][0]-source_offset
        offset=source_offset
        if len(packed)>capacity:
            offset=(free+2047)//2048*2048
            assert offset+len(packed)<=first_data,('Verified prefix space exhausted',member,len(packed),offset,first_data)
            assert original[offset:offset+len(packed)]==bytes(len(packed))
            capacity=first_data-offset
            free=offset+len(packed)
        target[offset:offset+len(packed)]=packed
        struct.pack_into('<II',target,8+member*8,offset,len(packed))
        outputs[member]=(packed,decoded)
        images[member]=(image,decode_pvr(decoded)[0])
        resources.append({'member':member,'source_offset':source_offset,'target_offset':offset,
                          'source_packed_bytes':source_size,'target_packed_bytes':len(packed),
                          'decoded_bytes':len(decoded),'source_decoded_sha256':digest(plain),
                          'target_decoded_sha256':digest(decoded),'target_packed_sha256':digest(packed),
                          'changed_pixels':int((before!=after).sum()),'caption_count':len(rows),'draws':draws})
    assert len(target)==len(original)
    for i,(offset,size) in enumerate(offsets):
        if i not in outputs:
            assert struct.unpack_from('<II',target,8+i*8)==(offset,size)
            assert target[offset:offset+size]==members[i]
    assert sum(r['caption_count'] for r in resources)==201
    report={'source_build':'0.1.27','source_archive_sha256':digest(original),'target_archive_sha256':digest(target),
            'archive_bytes':len(target),'archive_members':244,'changed_members':list(outputs),
            'caption_count':201,'unresolved_caption_ids':['album.214.082','album.214.102'],
            'protected_photo_areas':224,'protected_blank_Coming_Soon_cells':21,'native_sprite_geometry':'exact original DAT 214',
            'unchanged_archive_member_payloads':216,'relocated_members':[r['member'] for r in resources if r['source_offset']!=r['target_offset']],
            'translation_map_sha256':digest(DEST.read_bytes()),'resources':resources,
            'normal_text_font_changed':False,'story_library_draft_credit':0,
            'pending':['Two caption source readings and independent meaning review',
                       'Full-size album note and New Year greeting artwork plus matching thumbnail images',
                       'Native PRS/texture checks and disc packaging','Native album loading, unlock/selection/navigation, fit and appearance']}
    return bytes(target),report,images,outputs


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,report,images,outputs=compose()
    print(json.dumps({k:v for k,v in report.items() if k!='resources'},indent=2))
    print('Atlas byte counts:',[(r['member'],r['source_packed_bytes'],r['target_packed_bytes']) for r in report['resources']])
    if not args.write:
        print('DRY RUN: no native album candidate written');return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'ALBUM.AFS').write_bytes(archive)
    (OUT/'component-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    for i,(packed,decoded) in outputs.items():
        (OUT/f'member-{i:03d}.packed.bin').write_bytes(packed)
        (OUT/f'member-{i:03d}.pvr').write_bytes(decoded)
    info,*_=analyze()
    for page in range(7):
        sheet=Image.new('RGB',(1024,928),'#30333a');draw=ImageDraw.Draw(sheet)
        for n,row in enumerate(info['rectangles'][page*32:(page+1)*32]):
            crop=images[row['texture_member']][1].crop(row['caption_box'])
            crop=crop.resize((256,96),Image.Resampling.NEAREST);x=n%4*256;y=n//4*116
            sheet.paste(crop,(x,y),crop)
            draw.text((x,y+98),row['id'],fill='white')
        sheet.save(OUT/f'English-captions-{page:02d}.png')
    im=Image.new('RGB',(1536,480),'#30333a');d=ImageDraw.Draw(im)
    for x,label,source in [(0,'Original native album page',images[215][0]),(768,'English native album page - live appearance unverified',images[215][1])]:
        crop=source.crop((0,0,256,144)).resize((768,432),Image.Resampling.NEAREST)
        im.paste(crop,(x,24),crop);d.text((x+4,4),label,fill='white')
    im.save(OUT/'gallery-before-after.png')
    print('Wrote 28 caption atlases and seven English witness sheets:',OUT)


if __name__=='__main__':main()
