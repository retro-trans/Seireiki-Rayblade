"""Check album caption pixels, archive preservation and native decoding.

Default dry run. Independent scalar font sampling and Morton addressing;
native PRS checks execute every changed stream. Does not test native I/O/GPU.
"""
import argparse
from collections import Counter
import json
import struct

import numpy as np
from PIL import Image

from build_album_caption_patch import OUT, compose
from build_bitmap_font import ROOT, ATLAS, digest
from check_native_text_components import verify
from extract_album_captions import analyze
from prepare_album_translations import DEST, prepare
from rayblade_codec import decompress
from test_ui_images import scalar_plane, texture_info


def reference_mask(text, atlas):
    glyphs = []
    for ch in text:
        if ch == ' ':
            glyphs.append(np.zeros((8, 2), np.uint8))
            continue
        code = ord(ch) - 32
        assert 0 <= code < 95
        cell = atlas[code // 32 * 24:code // 32 * 24 + 24,
                     code % 32 * 12:code % 32 * 12 + 12]
        columns = [x for x in range(12) if any(int(cell[y, x]) for y in range(24))]
        left, right = columns[0], columns[-1] + 1
        width = (right - left + 2) // 3
        glyph = np.zeros((8, width), np.uint8)
        for y in range(8):
            for x in range(width):
                total = 0
                for dy in range(3):
                    for dx in range(3):
                        sx = left + x * 3 + dx
                        if sx < right:
                            total += int(cell[y * 3 + dy, sx])
                glyph[y, x] = (total + 4) // 9
        glyphs.append(glyph)
    result = np.zeros((8, 1 + sum(g.shape[1] + 1 for g in glyphs)), np.uint8)
    x = 1
    for glyph in glyphs:
        result[:, x:x + glyph.shape[1]] = glyph
        x += glyph.shape[1] + 1
    return result


def check():
    expected, component, _, outputs = compose()
    target = (OUT / 'ALBUM.AFS').read_bytes()
    assert target == expected
    assert json.loads((OUT / 'component-report.json').read_text('utf-8')) == component
    recipe = json.loads(DEST.read_text('utf-8'))
    assert recipe == prepare()
    info, original, members, textures = analyze()
    permitted = np.zeros(len(target), bool)
    spans, relocated = [], []
    for i in range(244):
        old_offset, old_size = struct.unpack_from('<II', original, 8 + i * 8)
        offset, size = struct.unpack_from('<II', target, 8 + i * 8)
        assert offset % 2048 == 0 and size > 0 and offset + size <= len(target)
        spans.append((offset, offset + size))
        if i not in outputs:
            assert (offset, size) == (old_offset, old_size)
            assert target[offset:offset + size] == members[i]
        else:
            permitted[8 + i * 8:16 + i * 8] = True
            permitted[offset:offset + size] = True
            if offset != old_offset:
                assert offset >= 0x10000 and offset + size <= 0x80000
                assert original[offset:offset + size] == bytes(size)
                relocated.append(i)
    spans.sort()
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    assert np.array_equal(np.frombuffer(original, np.uint8)[~permitted],
                          np.frombuffer(target, np.uint8)[~permitted])
    assert relocated == component['relocated_members']
    atlas = np.asarray(Image.open(ATLAS).convert('L'))
    captions, photos, protected, font_pixels = 0, 0, 0, 0
    for resource in component['resources']:
        member = resource['member']
        packed, decoded = outputs[member]
        assert (OUT / f'member-{member:03d}.packed.bin').read_bytes() == packed
        assert (OUT / f'member-{member:03d}.pvr').read_bytes() == decoded
        offset, size = struct.unpack_from('<II', target, 8 + member * 8)
        assert target[offset:offset + size] == packed
        assert decompress(packed[16:]) == (decoded, len(packed) - 16)
        source = textures[member][0]
        assert source[:32] == decoded[:32] and packed[:16] == members[member][:16]
        assert struct.unpack_from('<IHH', decoded, 24) == (0x100, 256, 256)
        before, after = scalar_plane(source, 256, 256), scalar_plane(decoded, 256, 256)
        reference = before.copy()
        selected = [r for r in recipe['rows'] if r['texture_member'] == member and r['en']]
        for row in selected:
            assert ' '.join(row['wrapped_lines']) == row['en']
            assert 1 <= len(row['wrapped_lines']) <= 3
            x0, y0, x1, y1 = row['caption_box']
            bg = Counter(int(v) for v in before[y0:y1, x0:x1].flat).most_common(1)[0][0]
            cell = reference[y0:y1, x0:x1]
            cell[:] = bg
            top = (24 - len(row['wrapped_lines']) * 8) // 2
            for line in row['wrapped_lines']:
                mask = reference_mask(line, atlas)
                h, w = mask.shape
                assert h == 8 and w <= 62 and top + h <= 24
                for y in range(h):
                    for x in range(w):
                        a = int(mask[y, x])
                        if a:
                            channels = [((((bg >> s) & 31) * (255 - a) + 127) // 255)
                                        for s in (10, 5, 0)]
                            cell[top + y, 1 + x] = 32768 | channels[0] << 10 | channels[1] << 5 | channels[2]
                            font_pixels += 1
                top += 8
            captions += 1
        assert np.array_equal(reference, after), ('Independent caption pixels differ', member)
        selected_ids = {r['id'] for r in selected}
        for row in info['rectangles']:
            if row['texture_member'] != member:
                continue
            x0, y0, x1, y1 = row['source_box']
            assert np.array_equal(before[y0:y0 + 48, x0:x1], after[y0:y0 + 48, x0:x1])
            photos += 1
            if row['id'] not in selected_ids:
                assert np.array_equal(before[y0:y1, x0:x1], after[y0:y1, x0:x1])
                protected += 1
    assert (captions, photos, protected) == (201, 224, 23)
    print('PASS: 244 archive records, independent caption pixels, all 224 photographs and 23 protected cells.', flush=True)
    exe = (ROOT / 'work/output/0.1.27/1ST_READ.BIN').read_bytes()
    native = []
    for member, (packed, decoded) in outputs.items():
        steps = verify(exe, packed[16:], decoded, len(decoded), instruction_limit=8_000_000)
        native.append({'member': member, 'stream_sha256': digest(packed[16:]),
                       'decoded_sha256': digest(decoded), 'decoded_bytes': len(decoded),
                       'instructions': steps, 'guard_ABI_exact_output': 'pass'})
        print('PASS native PRS:', member, steps, 'instructions', flush=True)
    return {'source_build': '0.1.27', 'executable_sha256': digest(exe), 'archive_sha256': digest(target),
            'caption_count': captions, 'archive_members': 244, 'changed_texture_members': len(outputs),
            'native_PRS_streams': native,
            'native_texture_info': {'dimensions': [256, 256], 'format': '0x100',
                                    'instructions': texture_info(exe, 256, 256, 0x100)},
            'independent_scalar_pixel_addressing_and_font_coverage': 'pass',
            'independent_font_pixels': font_pixels, 'all_English_words_retained': True,
            'protected_photo_areas': photos, 'protected_whole_cells': protected,
            'DAT_0_and_DAT_214_sprite_geometry': 'exact', 'unchanged_member_payloads': 216,
            'relocated_members_in_verified_zero_padding': relocated,
            'archive_bytes_outside_declared_edits': 'exact', 'native_guard_and_ABI': 'pass',
            'normal_text_font_changed': False, 'native_file_loading': False, 'GPU': False,
            'live_album_unlock_navigation_selection_and_appearance': 'pending',
            'meaning_review': 'English image-caption drafts; independent review pending',
            'unresolved_caption_ids': component['unresolved_caption_ids'], 'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: 201 captions, 244 archive entries, 224 photographs, 23 protected cells, independent pixels, all 28 native PRS streams and one texture header.', flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    report = check()
    print('PASS: all album caption checks;', sum(r['instructions'] for r in report['native_PRS_streams']), 'native decoder instructions.', flush=True)
    if args.write_report:
        (OUT / 'native-test.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
