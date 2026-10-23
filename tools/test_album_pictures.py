"""Verify native album pictures, preserved captions/archive bytes and decodes.

Dry run first. Independent scalar texture addressing and supplied-font masks;
paper recovery and thumbnail matching are estimates, not hidden-pixel proofs.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image

from build_album_picture_patch import OUT, PRIOR, compose
from build_bitmap_font import ROOT, digest
from check_native_text_components import verify
from extract_album_captions import analyze
from prepare_album_picture_text import DEST, prepare
from prepare_story_letter import POSITIONS
from rayblade_codec import decompress
from test_ui_images import reference_mask, scalar_plane, texture_info


def check():
    expected, component, _, _, outputs, _ = compose()
    target = (OUT / 'ALBUM.AFS').read_bytes()
    assert target == expected
    assert json.loads((OUT / 'component-report.json').read_text('utf-8')) == component
    recipe = json.loads(DEST.read_text('utf-8'))
    assert recipe == prepare() and len(recipe['pictures'][1]['related_draft_rows']) == 10
    source = (ROOT / 'work/output' / PRIOR / 'ALBUM.AFS').read_bytes()
    assert digest(source) == component['source_archive_sha256']
    selected = {15,81,216,218,225}
    permitted = np.zeros(len(source), bool)
    spans, relocated = [], []
    for member in range(244):
        old_off, old_size = struct.unpack_from('<II', source, 8+member*8)
        off, size = struct.unpack_from('<II', target, 8+member*8)
        assert off%2048 == 0 and size > 0 and off+size <= len(target)
        spans.append((off,off+size))
        if member not in selected:
            assert (off,size) == (old_off,old_size)
            assert target[off:off+size] == source[old_off:old_off+old_size]
        else:
            permitted[8+member*8:16+member*8] = True
            permitted[off:off+size] = True
            if off != old_off:
                assert member == 81 and 0x10000 <= off < off+size <= 0x80000
                assert source[off:off+size] == bytes(size)
                relocated.append(member)
    spans.sort()
    assert all(a[1] <= b[0] for a,b in zip(spans,spans[1:]))
    assert np.array_equal(np.frombuffer(source,np.uint8)[~permitted],np.frombuffer(target,np.uint8)[~permitted])
    assert relocated == component['relocated_members'] == [81]
    old_decoded = {}
    for member, (packed, decoded) in outputs.items():
        off,size = struct.unpack_from('<II', target, 8+member*8)
        assert target[off:off+size] == packed
        assert (OUT/f'member-{member:03d}.packed.bin').read_bytes() == packed
        assert (OUT/f'member-{member:03d}.pvr').read_bytes() == decoded
        assert decompress(packed[16:]) == (decoded,len(packed)-16)
        old_off,old_size = struct.unpack_from('<II', source, 8+member*8)
        old_packed = source[old_off:old_off+old_size]
        before,used = decompress(old_packed[16:])
        assert used == len(old_packed)-16 and packed[:16] == old_packed[:16]
        assert before[:32] == decoded[:32]
        old_decoded[member] = before
    before = np.frombuffer(old_decoded[15][32:],np.uint8).reshape(256,1024)
    after = np.frombuffer(outputs[15][1][32:],np.uint8).reshape(256,1024)
    allowed = np.zeros_like(before,bool)
    allowed[:52,92*2:234*2] = True
    allowed[26:49,214*2:232*2] = False
    assert np.array_equal(before[~allowed],after[~allowed])
    # Independent source-glyph masks validate both greeting lines before
    # color encoding; geometry/format checks retain their finite pixel scope.
    from build_ui_atlas_patch import mask
    for text,d in [('Happy New Year!',1),('2000',2)]:
        assert np.array_equal(reference_mask(text,d),mask(text,d))
    before = old_decoded[81]
    decoded = outputs[81][1]
    assert before[32::2] == decoded[32::2]
    a = np.frombuffer(before[32:],np.uint8).reshape(256,1024)
    b = np.frombuffer(decoded[32:],np.uint8).reshape(256,1024)
    assert np.array_equal(a[224:],b[224:]) and np.array_equal(a[:224,640:],b[:224,640:])
    ink = np.asarray(Image.open(OUT/'note-flat_English_ink.png').convert('L'))
    reference = np.zeros_like(ink)
    for text,(x,y) in zip(recipe['pictures'][1]['English_lines'],POSITIONS):
        glyphs = reference_mask(text,2)
        h,w = glyphs.shape
        reference[y:y+h,x:x+w] = glyphs
    assert np.array_equal(ink,reference)
    info,*_ = analyze()
    changed_photos = {14,25,86}
    captions, protected_photos = 0,0
    for member in (216,218,225):
        old = scalar_plane(old_decoded[member],256,256)
        new = scalar_plane(outputs[member][1],256,256)
        permitted_pixels = np.zeros((256,256),bool)
        for row in info['rectangles']:
            if row['texture_member'] != member:
                continue
            x0,y0,x1,y1 = row['source_box']
            assert np.array_equal(old[y0+48:y1,x0:x1],new[y0+48:y1,x0:x1])
            captions += 1
            if row['sprite'] in changed_photos:
                permitted_pixels[y0:y0+48,x0:x1] = True
            else:
                assert np.array_equal(old[y0:y0+48,x0:x1],new[y0:y0+48,x0:x1])
                protected_photos += 1
        assert np.array_equal(old[~permitted_pixels],new[~permitted_pixels])
    assert captions == 24 and protected_photos == 21
    # All other atlas payloads are among the 239 exact members checked above.
    assert len(info['rectangles']) == 224
    print('PASS: all 244 archive records; 239 unrelated payloads, all 224 captions and 221 other thumbnail photographs exact.',flush=True)
    exe = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    native = []
    for member,(packed,decoded) in sorted(outputs.items()):
        steps = verify(exe,packed[16:],decoded,len(decoded),instruction_limit=12_000_000)
        native.append({'member':member,'stream_sha256':digest(packed[16:]),'decoded_sha256':digest(decoded),
                       'decoded_bytes':len(decoded),'instructions':steps,'guard_ABI_exact_output':'pass'})
        print('PASS native PRS:',member,steps,'instructions',flush=True)
    headers = [{'dimensions':[512,256],'format':'0x903','GPU_pixel_bits':'0x18000000',
                'instructions':texture_info(exe,512,256,0x903,expected_pixel_bits=0x18000000)},
               {'dimensions':[256,256],'format':'0x100','instructions':texture_info(exe,256,256,0x100)}]
    return {'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(target),
            'image_resource_count':5,'full_pictures':2,'thumbnail_photographs':3,'native_PRS_streams':native,
            'native_texture_info':headers,'archive_members':244,'unchanged_member_payloads':239,
            'archive_bytes_outside_declared_edits':'exact','original_DAT_geometry':'exact',
            'all_224_caption_areas':'exact','other_221_thumbnail_photographs':'exact',
            'greeting_original_heart_and_outside_header':'exact','note_original_chroma_and_headers':'exact',
            'note_changes_within_visible_320x224':True,'independent_source_font_masks':'pass',
            'linked_story_note_rows':10,'relocated_member':81,'source_prefix_padding':'verified zero',
            'native_guard_and_ABI':'pass','native_file_loading':False,'GPU':False,
            'paper_and_thumbnail_cleanup':'Local estimates; no exact hidden-pixel recovery or source resampling equivalence proof',
            'live_album_unlock_selection_navigation_and_appearance':'pending',
            'normal_text_font_changed':False,'story_library_draft_credit':0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: two full pictures, three thumbnails, all captions/other photographs and archive bytes, independent glyphs, five native PRS streams and two texture headers.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    report = check()
    print('PASS:',sum(r['instructions'] for r in report['native_PRS_streams']),'native decoder instructions.',flush=True)
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')


if __name__ == '__main__':
    main()
