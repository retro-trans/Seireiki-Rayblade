"""Check the additional raw profile tables and native text compatibility.

Native filtering/constructed-viewer parsing execute on controlled inputs.
This does not establish D_SYSTEM file loading, real selection or reachability.
"""
import argparse
import json
import struct

import numpy as np

from build_antialias_font import font_bytes
from build_bitmap_font import ROOT,digest
from build_font4x_patch import MEDIUM
from build_system_profiles_patch import OUT,PRIOR,compose
from prepare_system_profiles import original,source,DEST
from preview_font_sampling import packed_mask
from test_library_layout import make_viewer,parse_page
from test_library_patch import filtered_page,reference_window


def raw_english(text):
    # Independently encode medium glyph IDs and NL, without production codec.
    parts=text.split('<NL>')
    result=bytearray()
    for i,line in enumerate(parts):
        if i:
            result.append(253)
        result.extend(MEDIUM.index(c) for c in line)
    return bytes(result)+b'\xff'


def pointer(data,index):
    offset=index*4
    return offset+int.from_bytes(data[offset:offset+4],'little')


def check():
    archive,component,replacements=compose()
    assert (OUT/'D_SYSTEM.AFS').read_bytes()==archive
    assert json.loads((OUT/'component-report.json').read_text('utf-8'))==component
    src,members=original()
    _,_,_,profiles,rows,labels=source()
    recipe=json.loads(DEST.read_text('utf-8'))
    assert [r['source_sha256'] for r in rows]==[r['source_sha256'] for r in recipe['rows']]
    assert len(archive)==len(src)
    allowed=np.zeros(len(src),bool)
    allowed[8:24]=True
    for entry in component['placements']:
        n=entry['member']
        offset,size=struct.unpack_from('<II',archive,8+n*8)
        assert (offset,size)==(entry['target_offset'],entry['bytes'])
        assert archive[offset:offset+size]==replacements[n]==(OUT/f'member-{n:02d}.bin').read_bytes()
        assert digest(replacements[n])==entry['sha256']
        allowed[offset:offset+size]=True
    assert np.array_equal(np.frombuffer(archive,np.uint8)[~allowed],np.frombuffer(src,np.uint8)[~allowed])
    # Original profile body is retained at its now-unreferenced source slot.
    assert archive[524288:524288+len(members[0])]==members[0]
    paper,existing=replacements[0],replacements[1]
    assert pointer(paper,0)==384*4 and pointer(existing,0)==128*4
    exe=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    assert digest(font)==component['font_sha256']
    viewers={}
    geometries=[]
    for height in (6,7):
        viewers[height],info=make_viewer(exe,font,height)
        geometries.append(info)
    count=filter_steps=parser_steps=parser_cases=max_page=0
    largest_ink=0
    payloads=[]
    for i,record in enumerate(component['profiles']):
        assert record['id']==profiles[i]['id']
        for alias in range(0 if i==0 else 128,128 if i==0 else 384):
            assert pointer(paper,alias)==record['offset']
        offset=record['offset']
        header=bytes.fromhex(record['header_hex'])
        assert paper[offset:offset+len(header)]==header==bytes.fromhex(profiles[i]['header_hex'])
        assert offset+len(header)==record['text_offset']
        text=record['text']
        expected=raw_english(text)
        actual=paper[record['text_offset']:record['end']]
        assert actual==expected
        original_english=' '.join(r['en'] for r in recipe['rows'] if r['profile']==i)
        assert text.replace('<NL>',' ').split()==original_english.split()
        for line in text.split('<NL>'):
            x=0
            for char in line:
                box=packed_mask(font,char).getbbox()
                if box:
                    largest_ink=max(largest_ink,x+(box[2]+3)//4+1)
                x+=font[0xa0+MEDIUM.index(char)]
            assert x<=236
        for skip,height in [(0,255)]+[(skip,height) for height in (6,7) for skip in range(record['logical_lines']+2)]:
            wanted,code=reference_window(expected[:-1],skip,height)
            got,returned,steps=filtered_page(exe,actual,set(),skip,height)
            assert (got,returned)==(wanted,code)
            count+=1
            filter_steps+=steps
            if height!=255:
                max_page=max(max_page,len(got))
        # Exercise all lines through both real, constructed current viewers.
        for height,cpu in viewers.items():
            for skip in range(0,record['logical_lines'],height):
                page,_=reference_window(expected[:-1],skip,height)
                payloads.append((height,page))
    assert largest_ink<=240 and max_page<=512
    # Existing English labels retain exact visible strings and leading spaces.
    previous_end=512
    for label in labels:
        i=label['index']
        pos=pointer(existing,i)
        assert pos==previous_end
        payload=raw_english(label['text'])
        assert existing[pos:pos+len(payload)]==payload
        previous_end=pos+len(payload)
        payloads.append((6,payload))
    assert previous_end==len(existing)
    glyph_count=0
    for height,payload in payloads:
        glyphs,steps=parse_page(viewers[height],payload)
        # Convert native IDs and positions back to the expected characters.
        line=x=0
        wanted=[]
        for value in payload[:-1]:
            if value==253:
                line+=16
                x=0
            else:
                wanted.append((MEDIUM[value],x,line,False))
                x+=font[0xa0+value]
        assert glyphs==wanted
        parser_steps+=steps
        parser_cases+=1
        glyph_count+=len(glyphs)
    return {'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(archive),
            'profile_count':2,'source_rows_drafted':16,'root_aliases_checked':384,'existing_English_labels_checked':128,
            'all_profile_header_bytes':'exact original','all_English_words_and_punctuation':'exact draft',
            'native_filter_cases':count,'native_filter_instructions':filter_steps,
            'native_parser_cases':parser_cases,'native_parser_instructions':parser_steps,
            'native_glyph_position_occurrences':glyph_count,'native_viewers':geometries,
            'maximum_native_page_bytes':max_page,'native_page_capacity':512,'maximum_logical_ink_extent':largest_ink,
            'native_guard_and_ABI':'pass','archive_bytes_outside_declared_edits':'exact',
            'raw_members':'Not PRS-compressed; no PRS proof is applicable',
            'limits':['Actual D_SYSTEM AFS loading, pointer selection, loader capacity and runtime use not executed/proved',
                      'Current library viewers are controlled compatibility fixtures; they do not establish which viewer this legacy archive uses',
                      'Glyph advances, graphics/allocation/clear endpoints use existing bounded fixtures; actual GPU and live appearance untested',
                      'Independent meaning, name/category and lore-difference review remains pending']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: 384 profile aliases, 16 drafts, 128 existing labels; exact guards/data, native filter windows and both current constructed viewers.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution/report')
        return
    result=check()
    print('PASS:',result['native_filter_cases'],'filter cases;',result['native_parser_cases'],'parser cases;',
          result['maximum_native_page_bytes'],'/ 512 page bytes;',result['maximum_logical_ink_extent'],'/ 240 ink pixels.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
