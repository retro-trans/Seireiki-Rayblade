"""Check coordinated English attack textures and native source selection.

Independent scalar texture/font decoding and exact preservation. Native PRS,
PVM walking, PAL4 header and variant dispatch execute; file/GPU remain open.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image,ImageFilter,ImageOps

from audit_effect_palettes import parse,scalar_verify
from audit_pvm_archive import chunks
from build_antialias_font import font_bytes
from build_attack_lettering_patch import OUT,PRIOR,MEMBERS,compose
from build_bitmap_font import ROOT,digest
from build_font4x_patch import MEDIUM
from build_genei_font import MEDIUM_DATA
from check_attack_variant_selection import check as variant_check
from check_native_text_components import verify
from extract_attack_lettering import analyze
from test_chapter_cards import fresh as pvm_cpu,run as pvm_run
from test_font_patch import CPU


def scalar_plane(texture):
    assert texture[8:12]==b'\0\5\0\0' and texture[12:16]==b'\0\2\0\2'
    result=np.zeros((512,512),np.uint8)
    for y in range(512):
        for x in range(512):
            position=0
            for bit in range(9):
                position+=((y>>bit)&1)<<(bit*2)
                position+=((x>>bit)&1)<<(bit*2+1)
            result[y,x]=(texture[16+position//2]>>(4*(y&1)))&15
    return result


def reference_word(font,expected):
    canvas=np.zeros((64,256),np.uint8)
    cursor=0
    for char in 'BREAK':
        glyph=MEDIUM.index(char)
        for y in range(64):
            for x in range(32):
                start=MEDIUM_DATA+glyph*512+y*8+(x//16)*4
                word=int.from_bytes(font[start:start+4],'little')
                value=[0,85,187,255][(word>>(30-(x%16)*2))&3]
                canvas[y,cursor+x]=max(canvas[y,cursor+x],value)
        cursor+=font[0xa0+glyph]*4
    image=Image.fromarray(canvas)
    bounds=image.getbbox()
    native=image.crop(bounds)
    assert list(bounds)==expected['native_word_bounds']
    assert digest(native.tobytes())==expected['native_word_mask_sha256']
    scaled=native.resize((136,round(native.height*136/native.width)),Image.Resampling.LANCZOS)
    assert digest(scaled.tobytes())==expected['resized_mask_sha256']
    return scaled


def header(exe):
    c=CPU(exe,b'',0,0)
    block=bytearray(b'\xa5'*128)
    c.regions.insert(-1,(0x8c500000,block))
    c.reg[4:8]=[0x8c500020,512,512,0x500]
    c.pc=0x8c0e1c4c
    saved=c.reg[8:]
    for steps in range(10000):
        if c.pc==0xdead0000:
            break
        c.pc=c.execute(c.pc)
    else:
        raise ValueError('Native PAL4 header instruction limit')
    expected=[0x05000002,1,0x28000000,512,512,131072,36]
    assert [c.read(0x8c500020+i*4,4) for i in range(7)]==expected
    assert c.reg[0]==0 and c.reg[8:]==saved
    assert block[:32]==b'\xa5'*32 and block[60:]==b'\xa5'*68
    return steps


def check():
    built=compose()
    archive=(OUT/'EFFECT.AFS').read_bytes()
    report=json.loads((OUT/'component-report.json').read_text('utf-8'))
    assert (archive,report)==built[:2]
    source=(ROOT/'work/output'/PRIOR/'EFFECT.AFS').read_bytes()
    exe=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    assert digest(font)==report['font']['font_sha256']
    word=reference_word(font,report['font'])
    source_map,*_=analyze()
    maps={r['member']:r for r in source_map['resources']}
    allowed_bytes=np.zeros(len(source),bool)
    spans=[]
    for member in range(460):
        offset,size=struct.unpack_from('<II',archive,8+member*8)
        old_offset,old_size=struct.unpack_from('<II',source,8+member*8)
        assert offset%2048==0 and 0<size and offset+size<=len(archive)
        spans.append((offset,offset+size))
        if member not in MEMBERS:
            assert (offset,size)==(old_offset,old_size)
            assert archive[offset:offset+size]==source[old_offset:old_offset+old_size]
        else:
            allowed_bytes[8+member*8:16+member*8]=True
            allowed_bytes[offset:offset+size]=True
    spans.sort()
    assert all(a[1]<=b[0] for a,b in zip(spans,spans[1:]))
    assert np.array_equal(np.frombuffer(archive,np.uint8)[~allowed_bytes],np.frombuffer(source,np.uint8)[~allowed_bytes])
    streams=[]
    walker_cases=[]
    total_pixels,total_palette=0,0
    for resource in report['resources']:
        member=resource['member']
        packed=(OUT/f'member-{member:03d}.packed.bin').read_bytes()
        plain=(OUT/f'member-{member:03d}.pvm').read_bytes()
        assert (packed,plain)==built[2][member]
        offset,size=struct.unpack_from('<II',archive,8+member*8)
        assert archive[offset:offset+size]==packed
        before_offset,before_size=struct.unpack_from('<II',source,8+member*8)
        old=source[before_offset:before_offset+before_size]
        old_plain,old_texture,pal,_,_,_=parse(old)
        parsed,texture,new_pal,vector_indices,colors,_=parse(packed)
        assert parsed==plain and new_pal==pal
        src_chunks,dst_chunks=chunks(old_plain),chunks(plain)
        assert src_chunks[0]==dst_chunks[0] and src_chunks[1]==dst_chunks[1]
        assert texture[:16]==old_texture[:16]
        tex_position=src_chunks[2][0]['chunk_offset']
        assert plain[:tex_position+16]==old_plain[:tex_position+16]
        assert plain[tex_position+len(texture):]==old_plain[tex_position+len(texture):]
        before=scalar_plane(old_texture)
        after=scalar_plane(texture)
        assert np.array_equal(after,vector_indices)
        scalar_verify(texture,new_pal,after,colors)
        total_pixels+=after.size
        total_palette+=colors.shape[0]*16
        allowed=np.zeros_like(after,bool)
        for row in resource['draws']:
            x,y,u,v=row['source_box']
            allowed[y:v,x:u]=True
            assert digest(after[y:v,x:u].tobytes())==row['target_index_sha256']
            assert digest(before[y:v,x:u].tobytes())==row['source_index_sha256']
            assert set(np.unique(after[y:v,x:u]))<=set(np.unique(before[y:v,x:u]))
            mask=Image.new('L',(200,200))
            if row['sprite']==8:
                rgba=colors[5][before[y:v,x:u]]
                yy,xx=np.nonzero((rgba[:,:,:3].min(axis=2)>=245)&(rgba[:,:,3]>0))
                center=[(int(xx.min())+int(xx.max())+1)/2,(int(yy.min())+int(yy.max())+1)/2]
                assert center==row['ink_center']
                ink=ImageOps.mirror(word) if member in (455,456) else word
                left,top=round(center[0]-ink.width/2),round(center[1]-ink.height/2)
                assert 0<=left and 0<=top and left+ink.width<=200 and top+ink.height<=200
                mask.paste(ink,(left,top))
            else:
                mask.paste(word,(round(100-word.width/2),round(100-word.height/2)))
                angle=-12 if member in (142,455) else 12
                assert angle==row['whole_word_rotation_degrees']
                mask=mask.rotate(angle,Image.Resampling.BICUBIC,expand=False)
                if member in (455,456):
                    mask=ImageOps.mirror(mask)
            assert digest(mask.tobytes())==row['word_mask_sha256']
            a=np.asarray(mask)
            halo=np.asarray(mask.filter(ImageFilter.GaussianBlur(6)))
            far=np.asarray(mask.filter(ImageFilter.GaussianBlur(12)))
            support=(a>0)|(halo>=2)|(far>=3)
            assert np.array_equal(after[y:v,x:u]>0,support),row['id']
            if row['sprite']==8:
                rgba=colors[5][after[y:v,x:u]]
                assert np.all(rgba[a==255,:3]==255)
                assert np.count_nonzero(a==255)>200
        assert np.array_equal(before[~allowed],after[~allowed])
        for row in maps[member]['rectangles']:
            if row['sprite'] in (8,9):
                continue
            x,y,u,v=row['source_box']
            assert np.array_equal(before[y:v,x:u],after[y:v,x:u])
        steps=verify(exe,packed,plain,len(old_plain),instruction_limit=12_000_000)
        streams.append({'member':member,'instructions':steps,'decoded_bytes':len(plain),
                        'packed_sha256':digest(packed),'decoded_sha256':digest(plain)})
        for i,chunk in enumerate(dst_chunks):
            c=pvm_cpu(exe,plain)
            c.reg[4:7]=[0x8c500000,0,i]
            saved=c.reg[8:]
            steps=pvm_run(c,0x8c022060)
            assert c.reg[0]==0x8c500000+chunk[0]['chunk_offset'] and c.reg[8:]==saved
            walker_cases.append({'member':member,'chunk':i,'wrapper_offset':chunk[0]['chunk_offset'],'instructions':steps})
    selector=variant_check()
    assert selector['native_cases']==16
    header_steps=header(exe)
    return {'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(archive),
            'artwork_frame_count':8,'texture_resources':4,'unchanged_member_payloads_and_offsets':456,
            'protected_sprite_records_and_pixels':96,'all_source_geometry_and_palettes':'byte-exact',
            'independent_scalar_index_pixels':total_pixels,'independent_palette_entries':total_palette,
            'source_native_font_pixels_checked':5*64*32,'English_word':'BREAK',
            'source_font_sha256':digest(font),'native_PRS_streams':streams,
            'native_PRS_instructions':sum(r['instructions'] for r in streams),
            'native_PVM_wrapper_cases':walker_cases,'native_PAL4_header_instructions':header_steps,
            'native_variant_selector':selector,
            'native_guard_and_ABI':'pass','archive_bytes_outside_declared_edits':'exact',
            'texture_indices_outside_eight_word_cells':'exact',
            'preceding_member_250_English_UI':'stored bytes and descriptor exact 0.1.32',
            'limits':['Glow/trail artwork is reauthored, not original brush contours or motion-field reconstruction',
                      'PVM walker uses the existing bounded memcmp fixture; native file I/O and async loader are not executed',
                      'Native source selector phases 1/2 remain outside the fixture; fresh branch/load/join checks cover 16 source-state cases',
                      'Whole attack reachability, actual sprite transforms, runtime palette/timing and GPU/live appearance remain unverified']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: eight word cells, independent font/texture/palette decoding, 456 protected members/96 sprites, four native PRS streams, twelve PVM wrappers, PAL4 header and 16 variant cases.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution/report')
        return
    result=check()
    print('PASS:',result['native_PRS_instructions'],'PRS instructions;',result['independent_scalar_index_pixels'],
          'index pixels;',len(result['native_PVM_wrapper_cases']),'PVM wrappers; 16 variant cases.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
