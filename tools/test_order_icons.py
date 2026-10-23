"""Verify all fifteen order icons, native decoders/headers and selector.

Scalar texture/font reads and reference compositing are independent of the
production encoder. Default dry run; actual GPU/live review remains open.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image

from audit_effect_palettes import parse, scalar_verify
from audit_pvm_archive import chunks
from build_antialias_font import font_bytes
from build_bitmap_font import ROOT, digest
from build_font4x_patch import MEDIUM
from build_genei_font import MEDIUM_DATA
from build_order_icons_patch import PRIOR, OUT, compose, member
from check_native_text_components import verify
from check_order_icon_selection import check as selection
from extract_ui_atlases import analyze
from rayblade_codec import decompress
from test_chapter_cards import fresh as pvm_cpu, run as pvm_run
from test_effect_ui import scalar_indices, native_header
from test_ui_images import scalar_plane, texture_info


def reference_glyph(font, char):
    glyph = MEDIUM.index(char)
    image = Image.new('L', (64, 64))
    for y in range(64):
        for x in range(32):
            start = MEDIUM_DATA + glyph*512 + y*8 + (x//16)*4
            bits = int.from_bytes(font[start:start+4], 'little')
            image.putpixel((x, y), (0,85,187,255)[(bits >> (30-2*(x%16))) & 3])
    image = image.resize((16,16), Image.Resampling.LANCZOS)
    image = image.point(lambda v: min((0,85,187,255), key=lambda level:abs(v-level)))
    return image.crop(image.getbbox())


def reference_cell(template, ink, left, palette=None):
    expected = template.copy()
    region = template[2:15,left:left+10].ravel().tolist()
    background = max(set(region), key=region.count)
    expected[2:15,left:left+10] = background
    xx, yy = left+(9-ink.width)//2, 2+(12-ink.height)//2
    for delta, color in ((1,(16,16,16)), (0,(255,255,255))):
        for y in range(ink.height):
            for x in range(ink.width):
                alpha = ink.getpixel((x,y))
                if alpha == 0:
                    continue
                old = int(expected[yy+y+delta,xx+x+delta])
                if palette is None:
                    channels = []
                    for shift, target in zip((10,5,0), color):
                        channels.append((((old >> shift)&31)*(255-alpha)+(target*31//255)*alpha+127)//255)
                    new = 32768+channels[0]*1024+channels[1]*32+channels[2]
                else:
                    mixed = [(int(palette[old,k])*(255-alpha)+color[k]*alpha+127)//255 for k in range(3)]
                    new = min((n for n in range(16) if palette[n,3]),
                              key=lambda n:sum((int(palette[n,k])-mixed[k])**2 for k in range(3)))
                expected[yy+y+delta,xx+x+delta] = new
    return expected


def check():
    archives, component, replacements, decoded, _ = compose()
    assert json.loads((OUT/'component-report.json').read_text('utf-8')) == component
    exe = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    _, font = font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    assert font_bytes(archives['WIN00.AFS'])[1] == font
    glyphs = {ch:reference_glyph(font,ch) for ch in 'MCASD'}
    source_maps = {i['texture_member']:(i,p) for i,_,p,_ in analyze()[:2]}
    native_streams, headers, walkers = [], [], []
    protected_sprites, pixels_checked, palettes_checked = 0, 0, 0
    for name, archive in archives.items():
        assert (OUT/name).read_bytes() == archive
        source = (ROOT/'work/output'/PRIOR/name).read_bytes()
        count = struct.unpack_from('<I',source,4)[0]
        allowed = np.zeros(len(source),bool)
        spans = []
        for n in range(count):
            pos,size = struct.unpack_from('<II',archive,8+n*8)
            assert pos%2048==0 and size>0 and pos+size<=len(archive)
            spans.append((pos,pos+size))
            oldpos,oldsize = struct.unpack_from('<II',source,8+n*8)
            assert pos == oldpos
            if n not in replacements[name]:
                assert size == oldsize and member(archive,n)==member(source,n)
            else:
                allowed[12+n*8:16+n*8] = True
                allowed[pos:pos+size] = True
        spans.sort()
        assert all(a[1]<=b[0] for a,b in zip(spans,spans[1:]))
        assert np.array_equal(np.frombuffer(source,np.uint8)[~allowed],np.frombuffer(archive,np.uint8)[~allowed])
        for resource in (r for r in component['resources'] if r['archive']==name):
            n = resource['member']
            raw, old = member(archive,n), member(source,n)
            plain = decoded[name,n]
            assert raw == (OUT/f'{name}-{n:03d}.packed.bin').read_bytes()
            assert plain == (OUT/f'{name}-{n:03d}.decoded.bin').read_bytes()
            if name=='WIN00.AFS':
                oldplain,_ = decompress(old[16:])
                w,h = resource['dimensions']
                before,after = scalar_plane(oldplain,w,h),scalar_plane(plain,w,h)
                info, original = source_maps[n]
                original_plane = scalar_plane(original,w,h)
                a,b,c,d = info['rectangles'][58]['source_box']
                template = original_plane[b:d,a:c]
                assert raw[:16]==old[:16] and plain[:32]==oldplain[:32]
                assert member(archive,resource['dat_member'])==member(source,resource['dat_member'])
                steps = verify(exe,raw[16:],plain,len(oldplain),instruction_limit=25_000_000)
                headers.append(texture_info(exe,w,h,struct.unpack_from('<I',plain,24)[0]))
            else:
                oldplain,oldt,oldpal,_,_,_ = parse(old)
                parsed,texture,pal,indices,colors,_ = parse(raw)
                assert parsed==plain and oldpal==pal
                before,after = scalar_indices(oldt),scalar_indices(texture)
                assert np.array_equal(after,indices)
                scalar_verify(texture,pal,after,colors)
                palettes_checked += len(colors)*16
                oldchunks,newchunks = chunks(oldplain),chunks(plain)
                assert oldchunks[:2]==newchunks[:2] and oldt[:16]==texture[:16]
                start = oldchunks[2][0]['chunk_offset']+16
                assert plain[:start]==oldplain[:start] and plain[start+32768:]==oldplain[start+32768:]
                steps = verify(exe,raw,plain,len(oldplain))
                header_steps,_ = native_header(exe)
                headers.append(header_steps)
                for i,chunk in enumerate(newchunks):
                    cpu = pvm_cpu(exe,plain)
                    cpu.reg[4:7] = [0x8c500000,0,i]
                    saved = cpu.reg[8:].copy()
                    num = pvm_run(cpu,0x8c022060)
                    assert cpu.reg[0]==0x8c500000+chunk[0]['chunk_offset'] and cpu.reg[8:]==saved
                    walkers.append({'chunk':i,'instructions':num})
            allowed = np.zeros(before.shape,bool)
            for row in resource['draws']:
                x,y,u,v = row['source_box']
                allowed[y:v,x:u] = True
                ink = glyphs[row['initial']]
                assert digest(ink.tobytes())==row['rendering']['mask_sha256']
                expected = reference_cell(template if name=='WIN00.AFS' else before[y:v,x:u],ink,
                                          2 if name=='WIN00.AFS' and n==2 else 3,
                                          None if name=='WIN00.AFS' else colors[4])
                assert np.array_equal(after[y:v,x:u],expected),(name,n,row['sprite'])
            assert np.array_equal(before[~allowed],after[~allowed])
            # Every complete non-order sprite retains all of its sampled pixels.
            if name=='WIN00.AFS':
                rectangles = info['rectangles']
                key = 'index'
            else:
                from extract_effect_ui import analyze as geometry
                rectangles = geometry()[0]['rectangles']
                key = 'sprite'
            for row in rectangles:
                if 58<=row[key]<=62:
                    continue
                x,y,u,v = row['source_box']
                assert np.array_equal(before[y:v,x:u],after[y:v,x:u]),row
                protected_sprites += 1
            pixels_checked += before.size
            native_streams.append({'archive':name,'member':n,'instructions':steps,'decoded_bytes':len(plain)})
            print('PASS:',name,n,'native PRS/header, scalar pixels, five glyphs, borders and protected sprites.',flush=True)
    selected = selection()
    return {'source_build':PRIOR,'executable_sha256':digest(exe),
            'archives':{n:digest(a) for n,a in archives.items()},'icon_cells':15,
            'archive_bytes_outside_declared_edits':'exact','native_guard_and_ABI':'pass',
            'unchanged_member_payloads_and_offsets':{'WIN00.AFS':88,'EFFECT.AFS':459},
            'protected_sprite_records_and_pixels':protected_sprites,
            'independent_scalar_texture_pixels':pixels_checked,'palette_entries':palettes_checked,
            'native_font_samples':5*64*32,'normal_font':'exact 0.1.33',
            'native_PRS_streams':native_streams,'native_PRS_instructions':sum(r['instructions'] for r in native_streams),
            'native_texture_header_instructions':sum(headers),'native_PVM_wrapper_cases':walkers,
            'native_order_selector':selected,
            'limits':['Frame reconstruction uses the original Manual frame; WIN00 texture 2 is one pixel left of the other copies',
                      'PVM walker uses existing bounded memcmp; sprite constructor is captured, not executed',
                      'Actual archive loading, EFFECT runtime palette/selection, GPU/live appearance and initial discoverability remain unverified']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: 15 cells / 3 resources, scalar font/texture/palette, exact protected data, native PRS/headers/PVM and 80 native selector cases.',flush=True)
    if not args.verify:
        print('DRY RUN: no execution/report')
        return
    result=check()
    print('PASS:',result['native_PRS_instructions'],'PRS instructions;',result['independent_scalar_texture_pixels'],'pixels;',result['native_order_selector']['case_count'],'selector cases.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
