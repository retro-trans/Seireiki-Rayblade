"""Verify the two newly read album caption cells and protected album work.

Independent scalar font/Morton sampling and both native PRS/header checks.
Source reading is manual editorial evidence, not proved by these byte tests.
"""
import argparse
from collections import Counter
import json
import struct

import numpy as np
from PIL import Image

from build_album_caption_readings_patch import OUT,PRIOR,compose
from build_bitmap_font import ROOT,ATLAS,digest
from check_native_text_components import verify
from extract_album_captions import analyze
from prepare_album_caption_readings import DEST
from test_album_captions import reference_mask
from test_ui_images import scalar_plane,texture_info
from rayblade_codec import decompress


def check():
    archive,component,outputs,_=compose()
    assert (OUT/'ALBUM.AFS').read_bytes()==archive
    assert json.loads((OUT/'component-report.json').read_text('utf-8'))==component
    source=(ROOT/'work/output'/PRIOR/'ALBUM.AFS').read_bytes()
    source_map,*_=analyze()
    recipe=json.loads(DEST.read_text('utf-8'))
    previous=json.loads((ROOT/'work/translation/en/ui/album-captions.en.json').read_text('utf-8'))
    old_ids={r['id'] for r in previous['rows'] if r['en']}
    new_ids={r['id'] for r in recipe['rows']}
    assert len(old_ids)==201 and len(new_ids)==2 and not old_ids&new_ids
    assert len(old_ids|new_ids)==203
    allowed=np.zeros(len(source),bool)
    spans=[]
    for n in range(244):
        a,b=struct.unpack_from('<II',archive,8+n*8)
        olda,oldb=struct.unpack_from('<II',source,8+n*8)
        assert a==olda and a%2048==0 and b>0 and a+b<=len(archive)
        spans.append((a,a+b))
        if n not in outputs:
            assert b==oldb and archive[a:a+b]==source[a:a+oldb]
        else:
            allowed[12+n*8:16+n*8]=True
            allowed[a:a+b]=True
    spans.sort()
    assert all(a[1]<=b[0] for a,b in zip(spans,spans[1:]))
    assert np.array_equal(np.frombuffer(source,np.uint8)[~allowed],np.frombuffer(archive,np.uint8)[~allowed])
    atlas=np.asarray(Image.open(ATLAS).convert('L'))
    exe=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    streams=[]
    protected_cells=protected_photos=mask_samples=header_steps=0
    for resource in component['resources']:
        n=resource['member']
        packed,decoded=outputs[n]
        assert packed==(OUT/f'member-{n:03d}.packed.bin').read_bytes()
        assert decoded==(OUT/f'member-{n:03d}.pvr').read_bytes()
        olda,oldb=struct.unpack_from('<II',source,8+n*8)
        old=source[olda:olda+oldb]
        plain,used=decompress(old[16:])
        assert used==len(old)-16 and len(plain)==len(decoded)==131104
        assert old[:16]==packed[:16] and plain[:32]==decoded[:32]
        before,after=scalar_plane(plain,256,256),scalar_plane(decoded,256,256)
        row=next(r for r in recipe['rows'] if r['id']==resource['id'])
        x,y,u,v=row['caption_box']
        cell=before[y:v,x:u]
        bg=Counter(map(int,cell.ravel())).most_common(1)[0][0]
        assert bg==resource['background_pixel']
        expected=np.full((24,64),bg,np.uint16)
        yy=(24-8*len(row['wrapped_lines']))//2
        for i,line in enumerate(row['wrapped_lines']):
            mask=reference_mask(line,atlas)
            assert mask.shape[1]<=62 and mask.shape[0]==8
            assert digest(mask.tobytes())==resource['draws'][i]['mask_sha256']
            for sy in range(8):
                for sx in range(mask.shape[1]):
                    a=int(mask[sy,sx])
                    if not a:
                        continue
                    value=32768
                    for shift in (10,5,0):
                        value|=((((bg>>shift)&31)*(255-a)+127)//255)<<shift
                    expected[yy+sy,1+sx]=value
            mask_samples+=mask.size
            yy+=8
        assert np.array_equal(after[y:v,x:u],expected)
        allowed=np.zeros((256,256),bool)
        allowed[y:v,x:u]=True
        assert np.array_equal(before[~allowed],after[~allowed])
        for other in source_map['rectangles']:
            if other['texture_member']!=n:
                continue
            a,b,c,d=other['source_box']
            assert np.array_equal(before[b:b+48,a:c],after[b:b+48,a:c])
            protected_photos+=1
            if other['id'] not in new_ids:
                a,b,c,d=other['caption_box']
                assert np.array_equal(before[b:d,a:c],after[b:d,a:c])
                protected_cells+=1
        steps=verify(exe,packed[16:],decoded,len(plain),instruction_limit=12_000_000)
        fmt=int.from_bytes(decoded[24:28],'little')
        header_steps+=texture_info(exe,256,256,fmt)
        streams.append({'member':n,'native_PRS_instructions':steps,'decoded_bytes':len(decoded),
                        'packed_sha256':digest(packed),'decoded_sha256':digest(decoded)})
    assert protected_photos==16 and protected_cells==14
    # Other 208 photos/208 caption cells are protected by exact member bytes.
    return {'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(archive),
            'new_caption_count':2,'combined_caption_count':203,'unresolved_caption_ids':[],
            'protected_existing_English_caption_cells':201,'protected_Coming_Soon_cells':21,
            'protected_photo_regions':224,'geometry_member_214':'exact preceding build',
            'unchanged_member_payloads_and_offsets':242,'source_font_mask_samples':mask_samples,
            'independent_scalar_texture_pixels':131072,'native_PRS_streams':streams,
            'native_PRS_instructions':sum(s['native_PRS_instructions'] for s in streams),
            'native_texture_header_instructions':header_steps,
            'native_guard_and_ABI':'pass','archive_bytes_outside_declared_edits':'exact',
            'source_pixels_outside_two_caption_cells':'exact preceding build',
            'normal_font_changed':False,'limits':['Manual glyph readings/wording are editorial decisions; byte/native tests do not prove Japanese meaning',
                                                 'Native file loading, actual album selection/unlock/navigation and GPU/live appearance remain unverified']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: two caption cells, independent scalar fonts/pixels, 201 English captions/21 blanks/224 photos protected, two native PRS/header checks.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution/report')
        return
    result=check()
    print('PASS:',result['native_PRS_instructions'],'native PRS instructions; 203 combined captions;',
          result['independent_scalar_texture_pixels'],'scalar pixels.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
