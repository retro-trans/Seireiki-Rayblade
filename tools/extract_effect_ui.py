"""Map EFFECT member 250 UI rectangles and source pixels. Dry run first.

The final texture-parameter word is recorded raw; no unverified palette or
runtime binding interpretation is used. Preview uses palette bank zero.
"""
import argparse
import json
import struct

from PIL import Image, ImageDraw

from audit_effect_palettes import original, parse, false_color
from audit_pvm_archive import chunks
from build_bitmap_font import ROOT, digest

OUT = ROOT/'work/ui/asset-audit/EFFECT/ui-250'


def analyze():
    archive,members = original()
    data,texture,pal,indices,colors,info = parse(members[250])
    geometry = chunks(data)[0][1][16:]
    pof = geometry.index(b'POF0')
    start = pof+8+struct.unpack_from('<I',geometry,pof+4)[0]
    assert start == 288 and len(geometry)==2800
    image = Image.fromarray(colors[0][indices])
    rows,position = [],start
    while struct.unpack_from('<H',geometry,position)[0]:
        w,h,cx,cy,u0,v0,u1,v1,param0,param1 = struct.unpack_from('<HHhh6H',geometry,position)
        assert 0<=u0<u1<=256 and 0<=v0<v1<=256
        assert (w,h)==(u1-u0,v1-v0)
        box = [u0,v0,u1,v1]
        rows.append({'id':f'effect.250.{len(rows):03d}','sprite':len(rows),'record_offset':position,
                     'draw_size':[w,h],'anchor':[cx,cy],'source_box':box,
                     'texture_parameter_raw_hex':geometry[position+16:position+20].hex(),
                     'parameter_words_raw':[param0,param1],
                     'source_pixel_sha256':digest(image.crop(box).tobytes()),
                     'source_index_sha256':digest(indices[v0:v1,u0:u1].tobytes())})
        position += 20
    # The table ends with a zero width followed by ten 0xff bytes, not
    # zero padding. Preserve and fingerprint that observed terminator.
    assert len(rows)==125 and geometry[position:]==b'\0\0'+b'\xff'*10
    return {'archive':'EFFECT.AFS','member':250,'source_archive_sha256':digest(archive),
            'packed_sha256':digest(members[250]),'decoded_sha256':digest(data),
            'geometry_sha256':digest(geometry),'texture_sha256':digest(texture),'palette_sha256':digest(pal),
            'palette_banks':info['palette_banks'],'declared_texture_bindings':info['declared_texture_bindings'],
            'sprite_count':len(rows),'rectangle_start':start,'terminator_hex':geometry[position:].hex(),
            'preview_palette_bank':0,'rectangles':rows,
            'scope':'Source UI discovery only. Raw texture parameter and native palette binding remain unproven; source art unchanged'},image,false_color(indices)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    info,image,index_view=analyze()
    print('Plan:',info['sprite_count'],'UI sprites;',info['palette_banks'],'palette banks; source parameter word retained raw.')
    print('First records:',[(r['id'],r['source_box'],r['texture_parameter_raw_hex']) for r in info['rectangles'][:4]])
    if not args.write:
        print('DRY RUN: no geometry map or witnesses written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    for page in range(4):
        sheet=Image.new('RGB',(1024,960),'#30333a')
        draw=ImageDraw.Draw(sheet)
        for n,row in enumerate(info['rectangles'][page*32:(page+1)*32]):
            crop=image.crop(row['source_box'])
            factor=max(1,min(5,248//crop.width,84//crop.height))
            crop=crop.resize((crop.width*factor,crop.height*factor),Image.Resampling.NEAREST)
            x,y=n%4*256,n//4*120
            sheet.paste(crop,(x,y),crop)
            draw.text((x+2,y+87),row['id'],fill='white')
            draw.text((x+2,y+102),str(row['source_box']),fill='#c6ccd6')
        sheet.save(OUT/f'sprites-{page:02d}.png')
    image.resize((1024,1024),Image.Resampling.NEAREST).save(OUT/'atlas-4x.png')
    index_view.resize((1024,1024),Image.Resampling.NEAREST).save(OUT/'indices-4x.png')
    (OUT/'rectangles.json').write_text(json.dumps(info,indent=2)+'\n','utf-8')
    print('Wrote all 125 labeled source rectangles and native/index atlas views.')


if __name__=='__main__':
    main()
