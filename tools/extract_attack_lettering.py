"""Map remaining effect lettering and non-text suspects. Dry run first.

Exact source geometry/indices/palettes retained. No game or translation patch.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image,ImageDraw

from audit_effect_palettes import original,parse
from audit_pvm_archive import chunks
from build_bitmap_font import ROOT,digest
from check_attack_variant_selection import OUT

MEMBERS=[142,143,438,439,455,456]


def analyze():
    archive,members=original()
    resources,images,crops=[],{},{}
    for member in MEMBERS:
        plain,texture,palette,indices,colors,meta=parse(members[member])
        geometry=chunks(plain)[0][1][16:]
        pof=geometry.index(b'POF0')
        start=pof+8+struct.unpack_from('<I',geometry,pof+4)[0]
        position=start
        rows=[]
        while position+20<=len(geometry) and struct.unpack_from('<H',geometry,position)[0]:
            w,h,cx,cy,u0,v0,u1,v1,param0,param1=struct.unpack_from('<HHhh6H',geometry,position)
            assert 0<=u0<u1<=256 and 0<=v0<v1<=256
            assert (u1-u0)*meta['width']==w*256 and (v1-v0)*meta['height']==h*256
            box=[u0*meta['width']//256,v0*meta['height']//256,
                 u1*meta['width']//256,v1*meta['height']//256]
            x,y,u,v=box
            row={'id':f'effect.{member:03d}.{len(rows):03d}','sprite':len(rows),
                 'geometry_record_offset':position,'draw_size':[w,h],'anchor':[cx,cy],
                 'source_box':box,'UV_256':[u0,v0,u1,v1],
                 'parameter_words_raw':[param0,param1],
                 'source_index_sha256':digest(indices[y:v,x:u].tobytes())}
            rows.append(row)
            position+=20
        expected=26 if member in (142,143,455,456) else 3
        terminator=(b'\0\0'+b'\xff'*6+bytes(16)) if expected==26 else (b'\0\0'+b'\xff'*2+bytes(16))
        assert len(rows)==expected and geometry[position:]==terminator
        resources.append({'member':member,'names':meta['names'],'packed_sha256':digest(members[member]),
                          'decoded_sha256':digest(plain),'geometry_sha256':digest(geometry),
                          'palette_sha256':digest(palette),'palette_banks':meta['palette_banks'],
                          'texture_dimensions':[meta['width'],meta['height']],
                          'geometry_start':start,'terminator_hex':terminator.hex(),'rectangles':rows})
        images[member]=(indices,colors)
        if expected==26:
            for sprite,bank in [(8,5),(9,6)]:
                row=rows[sprite]
                x,y,u,v=row['source_box']
                crop=indices[y:v,x:u]
                yy,xx=np.nonzero(crop)
                bounds=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
                a,b,c,d=bounds
                trimmed=crop[b:d,a:c]
                row.update(discovery_preview_palette_bank=bank,nonzero_index_bounds=bounds,
                           trimmed_index_sha256=digest(trimmed.tobytes()),
                           trimmed_index_dimensions=[trimmed.shape[1],trimmed.shape[0]])
                crops[member,sprite]=(Image.fromarray(colors[bank][crop]),trimmed)
    assert np.array_equal(crops[142,8][1],crops[143,8][1])
    report={'archive':'EFFECT.AFS','source_archive_sha256':digest(archive),'resources':resources,
            'sprite_records_mapped':sum(len(r['rectangles']) for r in resources),
            'lettering_sprite_candidates':8,
            'exact_relationships':[{'a':'effect.142.008','b':'effect.143.008',
                                   'trimmed_indices':'byte-exact same 167x155 image',
                                   'placement_difference':'B is 40 source pixels lower in the same 200x200 cell'}],
            'readings':[{'sprites':['effect.142.008','effect.143.008'],
                         'ja':'破','English_lexical_draft':'BREAK',
                         'status':'Clear primary glyph; emphatic battle artwork wording/final context still under review'},
                        {'sprites':['effect.455.008','effect.456.008'],
                         'status':'Visually reversed primary glyph variants; native source selector pairing established separately; exact transform/submission still untested'},
                        {'sprites':[f'effect.{m:03d}.009' for m in [142,143,455,456]],
                         'status':'Smeared glyph/effect frames remain unresolved; do not invent a separate two-character phrase'}],
            'resolved_non_text_candidates':[{'members':[438,439],
                                             'finding':'Full-size sources show mech poses, shock/impact rings and small bursts; no kanji reading assigned'}],
            'limits':['Preview palette banks are explicit source color-table views, not native binding proof',
                      'No English artwork inserted; no palette animation, sprite transforms or whole attack/GPU execution',
                      'All original bytes unchanged; latest game build remains 0.1.32'],
            'game_build_changed':False}
    return report,images,crops


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    report,images,crops=analyze()
    print('Plan:',report['sprite_records_mapped'],'source records across six effect resources; eight lettering-frame candidates; two ring suspects resolved.',flush=True)
    print('Primary 142/143 glyph indices are exact after trimming; lower/effect frames still held. No game edit.')
    if not args.write:
        print('DRY RUN: no source map or labeled previews written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    for page,members in enumerate([(142,143),(455,456)]):
        sheet=Image.new('RGB',(1024,900),'#30333a')
        draw=ImageDraw.Draw(sheet)
        for row,member in enumerate(members):
            for col,sprite in enumerate([8,9]):
                im=crops[member,sprite][0]
                im.save(OUT/f'original-{member:03d}-{sprite:03d}.png')
                im=im.resize((400,400),Image.Resampling.NEAREST)
                x,y=col*512,row*450
                sheet.paste(im,(x,y),im)
                draw.text((x+2,y+410),f'effect.{member:03d}.{sprite:03d} / bank '+str(5 if sprite==8 else 6),fill='white')
        sheet.save(OUT/f'lettering-{page:02d}.png')
    (OUT/'source-map.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n','utf-8')
    print('Wrote exact source geometry/index maps and two lettering sheets; source art unchanged.')


if __name__=='__main__':
    main()
