"""Verify native effect UI compression, indices, geometry and preservation.

Independent scalar Morton addressing and source-font sampling; executes the
actual SH-4 PRS decoder and 4-bit texture-info routine. No GPU/file-I/O proof.
"""
import argparse
import json
import struct

import numpy as np

from audit_effect_palettes import original, parse, scalar_verify
from audit_pvm_archive import chunks
from build_bitmap_font import ROOT, digest
from build_effect_ui_patch import OUT, compose, NEW_BALLISTIC_BOX
from check_native_text_components import verify
from extract_effect_ui import analyze
from test_font_patch import CPU
from test_ui_images import reference_mask


def scalar_indices(texture):
    assert texture[8:12]==b'\0\5\0\0'
    w,h=struct.unpack_from('<HH',texture,12)
    assert (w,h)==(256,256) and len(texture)==16+32768
    result=np.zeros((h,w),np.uint8)
    for y in range(h):
        for x in range(w):
            offset=0
            for bit in range(8):
                offset+=((x>>bit)&1)<<(2*bit+1)
                offset+=((y>>bit)&1)<<(2*bit)
            byte=texture[16+offset//2]
            result[y,x]=(byte>>((y%2)*4))%16
    return result


def native_header(exe):
    cpu=CPU(exe,b'',0,0)
    buffer=bytearray(b'\xa5'*128)
    address=0x8c500020
    cpu.regions.insert(-1,(address-32,buffer))
    cpu.reg[4:8]=[address,256,256,0x500]
    cpu.pc=0x8c0e1c4c
    saved=cpu.reg[8:]
    for steps in range(10000):
        if cpu.pc==0xdead0000:
            break
        cpu.pc=cpu.execute(cpu.pc)
    else:
        raise ValueError('Native paletted texture-info instruction limit')
    assert cpu.reg[0]==0 and cpu.reg[8:]==saved
    # Expected native format, storage type, PAL4 bits, dimensions, data size
    # and flags. Independent of the generic 16-bit helper's size assumption.
    expected=[0x05000002,1,0x28000000,256,256,32768,36]
    actual=[cpu.read(address+i*4,4) for i in range(7)]
    assert actual==expected,actual
    assert buffer[:32]==b'\xa5'*32 and buffer[60:]==b'\xa5'*68
    return steps,expected


def check():
    built=compose()
    archive=(OUT/'EFFECT.AFS').read_bytes()
    report=json.loads((OUT/'component-report.json').read_text('utf-8'))
    packed=(OUT/'member-250.packed.bin').read_bytes()
    decoded=(OUT/'member-250.pvm').read_bytes()
    assert (archive,report,packed,decoded)==built[:4]
    source,members=original()
    original_plain,old_texture,pal,_,_,_=parse(members[250])
    plain,texture,palette,indices,colors,_=parse(packed)
    assert plain==decoded and pal==palette
    before,after=scalar_indices(old_texture),scalar_indices(texture)
    assert np.array_equal(after,indices)
    scalar_verify(texture,palette,after,colors)
    meta,*_=analyze()
    selected={r['sprite'] for r in report['draws']}
    allowed_pixels=np.zeros((256,256),bool)
    allowed_decoded=np.zeros(len(decoded),bool)
    source_chunks,target_chunks=chunks(original_plain),chunks(decoded)
    assert source_chunks[0][0]==target_chunks[0][0]
    assert source_chunks[1]==target_chunks[1]
    assert source_chunks[2][0]==target_chunks[2][0] and texture[:16]==old_texture[:16]
    geometry_offset=source_chunks[0][0]['chunk_offset']+16
    uv_position=geometry_offset+meta['rectangles'][94]['record_offset']+8
    allowed_decoded[uv_position:uv_position+8]=True
    pixel_position=source_chunks[2][0]['chunk_offset']+16
    allowed_decoded[pixel_position:pixel_position+32768]=True
    assert np.array_equal(np.frombuffer(original_plain,np.uint8)[~allowed_decoded],
                          np.frombuffer(decoded,np.uint8)[~allowed_decoded])
    for row in meta['rectangles']:
        start=geometry_offset+row['record_offset']
        src=struct.unpack_from('<HHhh6H',original_plain,start)
        target=struct.unpack_from('<HHhh6H',decoded,start)
        if row['sprite']==94:
            assert target==(*src[:4],*NEW_BALLISTIC_BOX,*src[-2:])
        else:
            assert target==src
        if row['sprite'] not in selected:
            x0,y0,x1,y1=row['source_box']
            assert np.array_equal(before[y0:y1,x0:x1],after[y0:y1,x0:x1])
    mask_pixels=0
    for row in report['draws']:
        x0,y0,x1,y1=row['target_box']
        allowed_pixels[y0:y1,x0:x1]=True
        ox,oy,ou,ov=row['source_box']
        allowed_pixels[oy:ov,ox:ou]=True
        ink=reference_mask(row['en'],row['font_scale_denominator'])
        height,width=ink.shape
        assert row['rendering']['mask_size']==[width,height]
        x=(x1-x0-width-1)//2
        y=(y1-y0-height-1)//2
        assert x>=0 and y>=0 and x+width+1<=x1-x0 and y+height+1<=y1-y0
        expected=np.zeros((y1-y0,x1-x0),np.uint8)
        for yy in range(height):
            for xx in range(width):
                if ink[yy,xx]:
                    expected[y+yy+1,x+xx+1]=8
        # Explicit expected coverage/index intervals check the defined source
        # ramp without reusing the production stamp/quantizer implementation.
        thresholds=[(36,6),(73,5),(109,4),(146,3),(182,2),(219,1),(255,7)]
        for yy in range(height):
            for xx in range(width):
                value=int(ink[yy,xx])
                if not value:
                    continue
                color=1 if row['sprite']==57 else next(index for cutoff,index in thresholds if value<=cutoff)
                expected[y+yy,x+xx]=color
        assert np.array_equal(expected,after[y0:y1,x0:x1]),row['id']
        mask_pixels+=ink.size
    # The original Ballistic prefix is no longer sampled. Its shared suffix
    # is now solely the standalone English Barrier; no old kana remain.
    assert not after[128:144,0:48].any()
    assert np.array_equal(before[~allowed_pixels],after[~allowed_pixels])
    allowed_bytes=np.zeros(len(archive),bool)
    allowed_bytes[8+250*8:8+251*8]=True
    offset,size=struct.unpack_from('<II',archive,8+250*8)
    assert offset==report['member_offset'] and size==len(packed)
    allowed_bytes[offset:offset+size]=True
    assert np.array_equal(np.frombuffer(source,np.uint8)[~allowed_bytes],
                          np.frombuffer(archive,np.uint8)[~allowed_bytes])
    spans=[]
    for n in range(460):
        pos,size=struct.unpack_from('<II',archive,8+n*8)
        assert pos%2048==0 and size>0 and pos+size<=len(archive)
        spans.append((pos,pos+size))
        if n!=250:
            assert (pos,size)==struct.unpack_from('<II',source,8+n*8)
            assert archive[pos:pos+size]==members[n]
    spans.sort()
    assert all(a[1]<=b[0] for a,b in zip(spans,spans[1:]))
    exe=(ROOT/'work/output/0.1.31/1ST_READ.BIN').read_bytes()
    steps=verify(exe,packed,decoded,len(original_plain),instruction_limit=8_000_000)
    header_steps,header_words=native_header(exe)
    return {'source_build':'0.1.31','executable_sha256':digest(exe),'archive_sha256':digest(archive),
            'label_count':9,'geometry_records':125,'protected_sprites':116,
            'unchanged_member_payloads_and_offsets':459,
            'source_font_mask_pixels_checked':mask_pixels,
            'independent_scalar_index_pixels':65536,'independent_palette_entries':256,
            'native_PRS_instructions':steps,'native_decoded_bytes':len(decoded),
            'native_texture_info_instructions':header_steps,'native_texture_info_words':header_words,
            'native_guard_and_ABI':'pass','archive_bytes_outside_declared_edits':'exact',
            'decoded_bytes_outside_texture_indices_and_one_UV_record':'exact',
            'pixels_outside_declared_label_rectangles':'exact','all_palettes':'byte-exact original',
            'native_texture_parameter_and_palette_selection':'raw parameters and NJTL declarations preserved; runtime binding not executed',
            'geometry_UV_changed_sprites':[94],'all_draw_sizes_anchors_and_raw_parameters':'byte-exact original',
            'native_file_loading':False,'native_sprite_submission':False,'GPU':False,
            'live_palette_and_battle_appearance':'pending'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: all native atlas index pixels/palettes, nine source masks, 125 records, 459 protected members, native PRS and PAL4 header.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    result=check()
    print(json.dumps(result,indent=2),flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
