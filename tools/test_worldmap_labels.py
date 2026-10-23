"""Check map archive preservation, independent pixels and native PRS/texture info.

Does not run native file I/O, world-map navigation, sprite drawing or the GPU.
"""
import argparse
import json
import struct

import numpy as np

from build_bitmap_font import ROOT, digest
from build_worldmap_labels import OUT, compose
from check_native_text_components import verify
from extract_worldmap_labels import analyze
from rayblade_codec import decompress
from test_ui_images import reference_mask, scalar_plane, texture_info


def check():
    target = (OUT / 'WMAP.AFS').read_bytes()
    dat = (OUT / 'worldmap-labels.dat').read_bytes()
    decoded = (OUT / 'worldmap-labels.pvr').read_bytes()
    packed = (OUT / 'worldmap-labels.packed.bin').read_bytes()
    report = json.loads((OUT / 'component-report.json').read_text('utf-8'))
    built = compose()
    assert (target, dat, packed, decoded, report) == built[:5]
    info, original, members, plain, _ = analyze()
    before, after = scalar_plane(plain, 512, 512), scalar_plane(decoded, 512, 512)
    assert decoded[:32] == plain[:32] and packed[:16] == members[18][:16]
    assert decompress(packed[16:]) == (decoded, len(packed) - 16)
    allowed_pixels = np.zeros((512, 512), bool)
    allowed_bytes = np.zeros(len(target), bool)
    allowed_bytes[8 + 18 * 8:8 + 19 * 8] = True
    dat_offset = struct.unpack_from('<I', original, 8 + 17 * 8)[0]
    for index in (24, 26):
        position = info['rectangle_start'] + index * 20
        allowed_bytes[dat_offset + position:dat_offset + position + 20] = True
    texture_offset = struct.unpack_from('<I', target, 8 + 18 * 8)[0]
    assert texture_offset == report['texture_target_offset'] == 0x78000
    assert original[texture_offset:texture_offset + len(packed)] == bytes(len(packed))
    allowed_bytes[texture_offset:texture_offset + len(packed)] = True
    assert np.array_equal(np.frombuffer(target, np.uint8)[~allowed_bytes],
                          np.frombuffer(original, np.uint8)[~allowed_bytes])
    spans = []
    for i in range(20):
        offset, size = struct.unpack_from('<II', target, 8 + i * 8)
        assert offset % 2048 == 0 and 0 < size and offset + size <= len(target)
        spans.append((offset, offset + size))
        if i not in (17, 18):
            assert (offset, size) == struct.unpack_from('<II', original, 8 + i * 8)
            assert target[offset:offset + size] == members[i]
    spans.sort()
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    count = 0
    for source in info['rectangles']:
        pos = source['record_offset']
        record = struct.unpack_from('<HHhh6H', dat, pos)
        width, height, cx, cy, u0, v0, u1, v1, tex, flags = record
        assert (u1 - u0) * 2 == width and (v1 - v0) * 2 == height
        assert 0 <= u0 < u1 <= 256 and 0 <= v0 < v1 <= 256
        if source['sprite'] not in (24, 26):
            assert dat[pos:pos + 20] == members[17][pos:pos + 20]
        assert (tex, flags) == (source['texture_id'], source['flags'])
        if source['sprite'] not in range(17, 27):
            x0, y0, x1, y1 = source['source_box']
            assert np.array_equal(before[y0:y1, x0:x1], after[y0:y1, x0:x1])
            continue
        row = next(r for r in report['draws'] if r['sprite'] == source['sprite'])
        x0, y0, x1, y1 = row['target_box']
        assert [u0 * 2, v0 * 2, u1 * 2, v1 * 2] == row['target_box']
        assert [width, height] == row['target_size'] and [cx, cy] == row['target_anchor']
        assert width - 2 * cx == source['draw_size'][0] - 2 * source['anchor'][0]
        assert cy == source['anchor'][1] and height == source['draw_size'][1]
        ink = reference_mask(row['en'], 2)
        rh, rw = ink.shape
        assert rw + 1 <= width and rh + 1 <= height
        x, y = (width - rw - 1) // 2, (height - rh - 1) // 2
        expected = np.zeros((height, width), np.uint16)
        for yy, xx in zip(*np.nonzero(ink)):
            a = int(ink[yy, xx])
            component = (2 * a + 127) // 255
            expected[y + yy + 1, x + xx + 1] = 32768 | component << 10 | component << 5 | component
        for yy, xx in zip(*np.nonzero(ink)):
            old = int(expected[y + yy, x + xx]); a = int(ink[yy, xx])
            channels = [(((old >> s) & 31) * (255 - a) + c * a + 127) // 255
                        for s, c in zip((10, 5, 0), (19, 23, 24))]
            expected[y + yy, x + xx] = 32768 | channels[0] << 10 | channels[1] << 5 | channels[2]
        assert np.array_equal(after[y0:y1, x0:x1], expected), row['id']
        for box in (source['source_box'], row['target_box']):
            a, b, c, d = box
            allowed_pixels[b:d, a:c] = True
        if source['sprite'] in (24, 26):
            a, b, c, d = source['source_box']
            assert not after[b:d, a:c].any()
        count += 1
    assert count == 10 and np.array_equal(before[~allowed_pixels], after[~allowed_pixels])
    exe = (ROOT / 'work/output/0.1.24/1ST_READ.BIN').read_bytes()
    steps = verify(exe, packed[16:], decoded, len(decoded), instruction_limit=16_000_000)
    header_steps = texture_info(exe, 512, 512, 0x100)
    return {'source_build': '0.1.24', 'executable_sha256': digest(exe),
            'archive_sha256': digest(target), 'label_count': count, 'sprite_geometry_records': 28,
            'protected_sprite_count': 18, 'unchanged_member_payloads_and_offsets': 18,
            'independent_pixel_addressing_and_source_font_masks': 'pass',
            'original_pixels_and_archive_bytes_outside_declared_edits': 'exact',
            'native_PRS_instructions': steps, 'native_texture_info_instructions': header_steps,
            'native_decoded_bytes': len(decoded), 'native_guard_and_ABI': 'pass',
            'texture_dimensions': [512, 512], 'changed_sprite_records': [24, 26],
            'relocated_member': {'index': 18, 'offset': texture_offset,
                                 'original_zero_padding': True},
            'native_file_loading': False, 'native_sprite_pipeline': False, 'GPU': False,
            'live_map_appearance_navigation_and_overlap': 'pending'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: ten labels, all 28 geometry records, 18 protected sprites/members, exact outside edits, native decoder and texture info.', flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    result = check()
    print(json.dumps(result, indent=2), flush=True)
    if args.write_report:
        (OUT / 'native-test.json').write_text(json.dumps(result, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
