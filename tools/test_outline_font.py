"""Execute current SH-4 raster with inferred font masks. Dry run first.

Expected pixels come from saved unpacked masks, independently of native word
packing; unchanged small/protected masks come from the preceding build.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image

from build_antialias_font import LEVELS, font_bytes
from build_bitmap_font import ROOT, digest
from build_font4x_patch import SMALL, MEDIUM, BASE, START
from build_genei_font import SMALL_DATA, MEDIUM_DATA
from test_font4x_patch import HDCPU, TEX
from trace_bitmap_font import OUT, PRIOR, compose


def legacy_mask(font,char,small):
    chars = SMALL if small else MEDIUM
    height = 32 if small else 64
    start = (SMALL_DATA if small else MEDIUM_DATA)+chars.index(char)*height*8
    out = np.zeros((height,64),np.uint8)
    for y in range(height):
        a,b = struct.unpack_from('<2I',font,start+y*8)
        for x in range(64 if not char.isascii() else 32):
            if char.isascii():
                value = LEVELS[((a if x<16 else b)>>(30-2*(x%16)))&3]
            else:
                value = 255 if (a if x<32 else b)&(1<<(31-x%32)) else 0
            out[y,x] = value
    return out


def expected_pixels(cpu,coverage,flags,x,y,*,shadow_pixels=None):
    out = bytearray(cpu.regions[3][1])
    w,h = cpu.read(TEX+28,2),cpu.read(TEX+30,2)
    sx,sy = 1<<cpu.read(TEX+12,1),1<<cpu.read(TEX+13,1)
    shadow = sx if shadow_pixels is None else shadow_pixels
    color = cpu.read(0x8c0980aa+(flags&14)*2,2)
    rgb = ((color>>11)&15)<<8 | ((color>>6)&15)<<4 | (color>>1)&15
    width = 8 if coverage.shape[1]==32 else 16
    for yy in range(coverage.shape[0]//4*sy):
        py = y*sy+yy
        if py>=h:
            continue
        for xx in range(width*sx):
            px = x*sx+xx
            if px>=w:
                continue
            alpha = int(coverage[yy*4//sy,xx*4//sx])//17
            if flags&128 and px+shadow<w:
                struct.pack_into('<H',out,32+(py*w+px+shadow)*2,alpha<<12)
            if alpha:
                struct.pack_into('<H',out,32+(py*w+px)*2,(alpha<<12)|rgb)
    return out


def check():
    archive,component,_,old,font = compose()
    assert (OUT/'WIN00.AFS').read_bytes() == archive
    assert json.loads((OUT/'component-report.json').read_text('utf-8')) == component
    prior = (ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()
    off,expected_old = font_bytes(prior)
    assert old == expected_old and len(font)==len(old)==99072
    assert prior[:off] == archive[:off] and prior[off+len(old):] == archive[off+len(old):]
    assert font[0x20:0x120] == old[0x20:0x120] and font[:MEDIUM_DATA] == old[:MEDIUM_DATA]
    masks = {}
    allowed = np.zeros(len(font),bool)
    max_edge_growth = 0
    for row in component['glyphs']:
        char = row['character']
        mask = np.asarray(Image.open(OUT/'glyphs'/f'{ord(char):03d}.png').convert('L'))
        assert mask.shape == (64,64) and digest(mask.tobytes()) == row['mask_sha256']
        assert not mask[:,32:].any()
        masks[char] = mask[:,:32]
        start = MEDIUM_DATA+row['glyph_id']*512
        allowed[start:start+512] = True
        assert row['source_topology'] == row['candidate_topology']
        if row['source_coverage_sum']:
            ratio = row['candidate_coverage_sum_at_source_scale']/row['source_coverage_sum']
            assert .85<=ratio<=1.15
            old_box,new_box = row['old_mask_bounds'],row['new_mask_bounds']
            assert all(new_box[k]>=old_box[k]-1 for k in (0,1))
            assert all(new_box[k]<=old_box[k]+1 for k in (2,3))
            max_edge_growth = max(max_edge_growth,new_box[2]-old_box[2])
    assert np.array_equal(np.frombuffer(font,np.uint8)[~allowed],np.frombuffer(old,np.uint8)[~allowed])
    exe = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    cases = []
    for chars,flags,ex in ((SMALL,64,2),(MEDIUM,0,1)):
        for i,char in enumerate(chars):
            cases.append((char,i+32 if flags else i,flags|(128 if i%2 else 0),512,32,ex,2,12,4))
    for small,chars in ((True,SMALL),(False,MEDIUM)):
        for ex,ey in ((0,0),(0,2),(1,0),(1,1),(2,1),(2,2)):
            for x,y in ((0,0),(31,31),(32,4),(26,28)):
                for char in ('W','j','♪'):
                    cases.append((char,chars.index(char)+(32 if small else 0),(64 if small else 0)|128,32,32,ex,ey,x,y))
        for color in range(0,16,2):
            for char in ('r','O','♪'):
                cases.append((char,chars.index(char)+(32 if small else 0),(64 if small else 0)|128|color,256,32,2,2,12,4))
    # Small glyph IDs wrap (raw-32)&127: 0/255 are valid protected-symbol
    # aliases, while 4/31 select the invalid 100/127 indices before fallback.
    cases.extend(('?',glyph,flags,32,32,2,2,12,4) for glyph,flags in ((65535,0),(600,0),(4,64),(31,64)))
    steps = 0
    for n,(char,glyph,flags,w,h,ex,ey,x,y) in enumerate(cases):
        small = bool(flags&64)
        if not small and char.isascii():
            coverage = masks[char]
        else:
            coverage = legacy_mask(old,char,small)
            if char.isascii():
                coverage = coverage[:,:32]
        cpu = HDCPU(exe,font,glyph,flags,w,h,ex,ey)
        cpu.write(0x8c1f36b6,x,2)
        cpu.write(0x8c1f36b8,y,2)
        expected = expected_pixels(cpu,coverage,flags,x,y)
        steps += cpu.run_until(limit=300000)
        assert cpu.regions[3][1] == expected,(n,char,glyph,flags,ex,ey,x,y)
        chars,table = (SMALL,0x20) if small else (MEDIUM,0xa0)
        assert cpu.read(0x8c1f36b6,2) == x+old[table+chars.index(char)]
        if (n+1)%100==0:
            print('PASS native inferred-font cases:',n+1,flush=True)
    return {'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(archive),
            'source_font_sha256':digest(old),'font_sha256':digest(font),'glyph_cases':len(cases),
            'ASCII_outline_glyphs':95,'SH4_instructions':steps,'native_guard_and_ABI':'pass',
            'pixels_colors_shadow_clipping_fallback_and_advances':'exact expected masks / prior cursor widths',
            'archive_bytes_outside_declared_edits':'exact','all_non_font_member_payloads':'exact',
            'small_bank_and_protected_symbols':'exact','outline_topology_changes':[],
            'per_glyph_coverage_ratio_bound':[.85,1.15],'maximum_right_edge_growth_physical_pixels':max_edge_growth,
            'native_texture_dimensions':'Allocation code/executable unchanged; existing <=1024 cap retained',
            'independent_mask_reference':'Unpacked saved inferred-outline masks; preceding build for small/protected symbols',
            'no_original_vector_recovery_claim':True,'GPU':False,'live_font_appearance_and_Skies_comparison':'pending',
            'story_library_draft_credit':0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: inferred glyph masks, topology/coverage/bounds and unchanged archive bytes; all glyphs/colors, six surface scales, shadow/clipping/fallback and native advances.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    proof = check()
    print('PASS:',proof['glyph_cases'],'native cases;',proof['SH4_instructions'],'SH-4 instructions.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')


if __name__ == '__main__':
    main()
