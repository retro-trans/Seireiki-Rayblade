"""Insert the additional English D_SYSTEM profiles. Default dry run.

Rebuilds relative pointer tables, preserves headers/aliases and all words.
Member 0 relocates into verified zero AFS prefix space; member 1 stays put.
No executable/font edit or claim of runtime use is made.
"""
import argparse
import json
import struct

from PIL import Image,ImageDraw

from build_antialias_font import font_bytes
from build_bitmap_font import ROOT,digest
from build_font4x_patch import MEDIUM
from english_text_codec import encode,decode
from prepare_library_layouts import wrap_line,PEN
from prepare_system_profiles import DEST,prepare,original
from preview_font_sampling import packed_mask
from rayblade_text import relative_target

PRIOR='0.1.34'
OUT=ROOT/'work/output/system-profiles-draft-01'


def compose():
    recipe=json.loads(DEST.read_text('utf-8'))
    assert recipe==prepare()
    source,members=original()
    _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    paper=bytearray(384*4)
    records=[]
    for profile in recipe['profiles']:
        n=int(profile['id'].split('.')[-1])
        rows=[r for r in recipe['rows'] if r['profile']==n]
        assert len(rows)==(9 if n==0 else 7)
        lines=[wrap_line(r['en'],font) for r in rows]
        text='<NL>'.join(lines)
        assert text.replace('<NL>',' ').split()==' '.join(r['en'] for r in rows).split()
        payload=encode(text)
        assert decode(payload)==(text,255)
        offset=len(paper)
        header=bytes.fromhex(profile['header_hex'])
        paper.extend(header+payload)
        for i in profile['alias_indices']:
            struct.pack_into('<I',paper,i*4,offset-i*4)
        records.append({'id':profile['id'],'offset':offset,'header_hex':header.hex(),
                        'text_offset':offset+len(header),'end':len(paper),'text':text,
                        'source_record_sha256':profile['source_record_sha256'],
                        'alias_indices':profile['alias_indices'],'logical_lines':len(text.split('<NL>')),
                        'pen_widths':[sum(font[0xa0+MEDIUM.index(c)] for c in s) for s in text.split('<NL>')]})
    paper=bytes(paper)
    labels=bytearray(128*4)
    for row in recipe['existing_labels']:
        pos=row['index']*4
        struct.pack_into('<I',labels,pos,len(labels)-pos)
        payload=encode(row['text'])
        assert decode(payload)==(row['text'],255)
        labels.extend(payload)
    labels=bytes(labels)
    # First original slot is only 2048 bytes. The AFS reserved prefix is zero
    # after its header, and ample for both English profile records and table.
    target=bytearray(source)
    positions={0:0x800,1:struct.unpack_from('<I',source,16)[0]}
    replacements={0:paper,1:labels}
    assert len(paper)>2048 and len(paper)<0x8000
    assert positions[0]+len(paper)<struct.unpack_from('<I',source,8)[0]
    assert source[positions[0]:positions[0]+len(paper)]==bytes(len(paper))
    placements=[]
    for i,payload in replacements.items():
        offset,size=struct.unpack_from('<II',source,8+i*8)
        destination=positions[i]
        if i==1:
            assert len(payload)<=size
        target[destination:destination+len(payload)]=payload
        struct.pack_into('<II',target,8+i*8,destination,len(payload))
        placements.append({'member':i,'source_offset':offset,'source_bytes':size,
                           'target_offset':destination,'bytes':len(payload),'sha256':digest(payload)})
    for row in records:
        for i in row['alias_indices']:
            assert relative_target(paper,i*4)==row['offset']
    component={'source_build':PRIOR,'archive':'D_SYSTEM.AFS','source_archive_sha256':digest(source),
               'target_archive_sha256':digest(target),'archive_bytes':len(target),
               'translation_recipe':str(DEST.relative_to(ROOT)).replace('\\','/'),
               'translation_recipe_sha256':digest(DEST.read_bytes()),
               'new_Japanese_source_rows_drafted':16,'profile_count':2,'profile_references':384,
               'existing_English_labels_reencoded':128,'font_sha256':digest(font),
               'pen_pixels':PEN,'placements':placements,'profiles':records,
               'metadata':'All eleven profile header bytes and 384 source alias relationships retained',
               'limits':['Actual D_SYSTEM loading/reachability and legacy viewer compatibility remain unverified',
                         'No new shared-memory capacity claim; candidate profile payload is below 32 KiB but actual loader remains untraced',
                         'Current library identity/lore is not substituted for these older/different source statements',
                         'Independent meaning/name/category and live layout review remain pending']}
    return bytes(target),component,replacements


def preview(component,font):
    rows=max(p['logical_lines'] for p in component['profiles'])
    image=Image.new('RGB',(1120,100+rows*36),'#20242c')
    draw=ImageDraw.Draw(image)
    draw.text((12,12),'Additional D_SYSTEM profiles - offline current-font mockup; runtime use/layout unverified',fill='white')
    masks={c:packed_mask(font,c).resize((32,32),Image.Resampling.LANCZOS) for c in MEDIUM}
    for n,profile in enumerate(component['profiles']):
        left=12+n*550
        draw.text((left,45),profile['id']+' / source metadata preserved',fill='white')
        for row,line in enumerate(profile['text'].split('<NL>')):
            x=left
            for char in line:
                mask=masks[char]
                image.paste('white',(x,80+row*36,x+32,112+row*36),mask)
                x+=font[0xa0+MEDIUM.index(char)]*2
    return image


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,component,replacements=compose()
    print(json.dumps({k:component[k] for k in ('profile_count','new_Japanese_source_rows_drafted','existing_English_labels_reencoded','placements')},indent=2))
    print('Wrapped profile lines:',[r['logical_lines'] for r in component['profiles']],
          'maximum pen:',max(max(r['pen_widths']) for r in component['profiles']))
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'D_SYSTEM.AFS').write_bytes(archive)
    for i,payload in replacements.items():
        (OUT/f'member-{i:02d}.bin').write_bytes(payload)
    (OUT/'component-report.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
    _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    preview(component,font).save(OUT/'profile-preview.png')
    print('Wrote native English candidate and offline font mockup; no game build written.')


if __name__=='__main__':
    main()
