"""Check nine native image replacements and three unique PRS streams. Dry first.

Does not prove native archive I/O, image reachability, GPU appearance or that
the estimated blank paper reproduces hidden original paper pixels exactly.
"""
import argparse
from collections import Counter
import json
import struct

import numpy as np
from PIL import Image

from build_bitmap_font import ROOT, digest
from build_story_image_patch import OUT, DEST, SELECTED, compose
from check_native_text_components import verify
from disc_inventory import Disc
from prepare_story_letter import OUT as LETTER_OUT, prepare
from rayblade_codec import decompress
from test_ui_images import reference_mask, scalar_plane, texture_info


def reference_stamp(plane, text, box):
    x0, y0, x1, y1 = box
    ink = reference_mask(text, 1)
    h, w = ink.shape
    assert w + 1 <= x1 - x0 and h + 1 <= y1 - y0
    x, y = x0 + (x1 - x0 - w - 1) // 2, y0 + (y1 - y0 - h - 1) // 2
    for yy, xx in zip(*np.nonzero(ink)):
        a = int(ink[yy, xx]); old = int(plane[y+yy+1, x+xx+1])
        c = [((((old >> s) & 31) if old & 32768 else 0) * (255-a) + 2*a + 127) // 255 for s in (10, 5, 0)]
        plane[y+yy+1, x+xx+1] = 32768 | c[0] << 10 | c[1] << 5 | c[2]
    for yy, xx in zip(*np.nonzero(ink)):
        a = int(ink[yy, xx]); old = int(plane[y+yy, x+xx])
        c = [((((old >> s) & 31) if old & 32768 else 0) * (255-a) + 31*a + 127) // 255 for s in (10, 5, 0)]
        plane[y+yy, x+xx] = 32768 | c[0] << 10 | c[1] << 5 | c[2]


def check():
    expected, component, translation, _, sources, results = compose()
    target = (OUT / 'ADV00.AFS').read_bytes()
    assert target == expected
    assert json.loads((OUT / 'component-report.json').read_text('utf-8')) == component
    assert json.loads(DEST.read_text('utf-8')) == translation
    disc = Disc(next(ROOT.glob('*.cue')))
    entry = next(r for r in disc.inventory() if r['path'] == 'ADV00.AFS')
    original = disc.read(entry['lba'], entry['size'])
    permitted = np.zeros(len(target), bool)
    spans = []
    for i in range(777):
        old_offset, old_size = struct.unpack_from('<II', original, 8 + i * 8)
        offset, size = struct.unpack_from('<II', target, 8 + i * 8)
        assert offset % 2048 == 0 and size > 0 and offset + size <= len(target)
        spans.append((offset, offset + size))
        if i not in SELECTED:
            assert (offset, size) == (old_offset, old_size)
            assert target[offset:offset+size] == original[old_offset:old_offset+old_size]
        else:
            permitted[8+i*8+(0 if i == 379 else 4):8+i*8+8] = True
            permitted[offset:offset+size] = True
            assert offset == (0x60000 if i == 379 else old_offset)
            if i == 379:
                assert original[offset:offset+size] == bytes(size)
    spans.sort()
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    assert np.array_equal(np.frombuffer(original, np.uint8)[~permitted], np.frombuffer(target, np.uint8)[~permitted])
    unique = {}
    for row in component['resources']:
        i = row['member']; packed, decoded = results[i]
        assert (OUT / f'member-{i:03d}.packed.bin').read_bytes() == packed
        assert (OUT / f'member-{i:03d}.pvr').read_bytes() == decoded
        assert decompress(packed[16:]) == (decoded, len(packed) - 16)
        offset, size = struct.unpack_from('<II', target, 8 + i * 8)
        assert target[offset:offset+size] == packed and size <= row['slot_capacity']
        source_offset, source_size = struct.unpack_from('<II', original, 8 + i * 8)
        old_packed = original[source_offset:source_offset+source_size]
        assert packed[:16] == old_packed[:16] and decoded[:32] == sources[i][:32]
        assert digest(decoded) == row['target_decoded_sha256'] and digest(packed) == row['target_packed_sha256']
        if i == 379:
            assert decoded[32::2] == sources[i][32::2]
            a = np.frombuffer(sources[i][32:], np.uint8).reshape(256, 1024)
            b = np.frombuffer(decoded[32:], np.uint8).reshape(256, 1024)
            assert np.array_equal(a[:, 640:], b[:, 640:]) and np.array_equal(a[240:], b[240:])
        else:
            old_plane = scalar_plane(sources[i], 512, 512)
            plane = scalar_plane(decoded, 512, 512)
            reference = old_plane.copy()
            reference[:240, :320] = Counter(map(int, old_plane[:240, :320].ravel())).most_common(1)[0][0]
            for text, box in zip(row['en_lines'], ([30, 22, 290, 54], [30, 62, 290, 94])):
                reference_stamp(reference, text, box)
            assert np.array_equal(reference, plane), i
        stream_hash = digest(packed[16:])
        if stream_hash in unique:
            assert unique[stream_hash]['decoded_sha256'] == digest(decoded)
            unique[stream_hash]['members'].append(i)
        else:
            unique[stream_hash] = {'members': [i], 'decoded_sha256': digest(decoded),
                                   'packed': packed[16:], 'decoded': decoded}
    # Compare every English letter glyph against an independent source-atlas
    # mask before rotation, and retain the ten original draft-row fingerprints.
    letter = prepare()
    ink = np.asarray(Image.open(LETTER_OUT / 'English-ink-mask.png').convert('L'))
    reference = np.zeros_like(ink)
    for text, (x, y) in zip(letter['English_lines'], letter['line_positions_in_deskewed_texture']):
        glyphs = reference_mask(text, 2); h, w = glyphs.shape
        reference[y:y+h, x:x+w] = glyphs
    assert np.array_equal(reference, ink) and len(letter['related_draft_rows']) == 10
    assert len(unique) == 3
    exe = (ROOT / 'work/output/0.1.26/1ST_READ.BIN').read_bytes()
    native = []
    for stream_hash, item in unique.items():
        steps = verify(exe, item['packed'], item['decoded'], len(item['decoded']), instruction_limit=20_000_000)
        native.append({'members': item['members'], 'stream_sha256': stream_hash,
                       'decoded_sha256': item['decoded_sha256'], 'decoded_bytes': len(item['decoded']),
                       'instructions': steps, 'guard_ABI_exact_output': 'pass'})
        print('PASS native PRS:', item['members'], steps, 'instructions', flush=True)
    headers = [{'dimensions': [512, 512], 'format': '0x100', 'instructions': texture_info(exe, 512, 512, 0x100)},
               {'dimensions': [512, 256], 'format': '0x903', 'GPU_pixel_bits': '0x18000000',
                'instructions': texture_info(exe, 512, 256, 0x903, expected_pixel_bits=0x18000000)}]
    return {'source_build': '0.1.26', 'executable_sha256': digest(exe), 'archive_sha256': digest(target),
            'image_resource_count': 9, 'unique_PRS_streams': native, 'native_texture_info': headers,
            'unaltered_member_payloads': 768, 'unaltered_member_offsets': 776,
            'relocated_letter': {'member': 379, 'offset': 0x60000, 'source_zero_padding': True},
            'archive_bytes_outside_declared_edits': 'exact', 'independent_placeholder_pixels': 'pass',
            'letter_original_U_V_and_headers': 'exact', 'letter_visible_bounds': 'all edits within 320x240 photograph',
            'independent_English_letter_glyph_masks': 'pass', 'linked_story_rows': 10,
            'native_guard_and_ABI': 'pass', 'native_file_loading': False, 'GPU': False,
            'paper_recovery': 'source-only estimate; not exact hidden-pixel reconstruction',
            'placeholder_reachability_and_live_image_selection_appearance': 'pending',
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: nine images, all 777 archive entries, exact outside edits, independent font/pixels, three unique native PRS decodes and two texture headers.', flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    report = check()
    print(json.dumps(report, indent=2), flush=True)
    if args.write_report:
        (OUT / 'native-test.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
