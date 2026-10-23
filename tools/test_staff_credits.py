"""Verify credit atlas preservation and native decoding. Default dry run.

Name meanings/readings and live credit timing/order are outside this test.
"""
import argparse
import json
import struct

import numpy as np

from build_bitmap_font import ROOT, digest
from build_staff_credits import OUT, compose
from check_native_text_components import verify
from extract_staff_credits import analyze
from rayblade_codec import decompress
from test_ui_images import reference_mask, scalar_plane, texture_info


def check():
    target = (OUT / 'STAFF.AFS').read_bytes()
    dat = (OUT / 'staff-credits.dat').read_bytes()
    decoded = (OUT / 'staff-credits.pvr').read_bytes()
    packed = (OUT / 'staff-credits.packed.bin').read_bytes()
    report = json.loads((OUT / 'component-report.json').read_text('utf-8'))
    assert (target, dat, packed, decoded, report) == compose()[:5]
    info, original, members, plain, _ = analyze()
    before, after = scalar_plane(plain, 1024, 256), scalar_plane(decoded, 1024, 256)
    assert decoded[:32] == plain[:32] and packed[:16] == members[20][:16]
    assert decompress(packed[16:]) == (decoded, len(packed) - 16)
    allowed_pixels = np.zeros((256, 1024), bool)
    allowed_bytes = np.zeros(len(target), bool)
    allowed_bytes[8 + 20 * 8 + 4:8 + 21 * 8] = True
    dat_offset = struct.unpack_from('<I', original, 8 + 19 * 8)[0]
    for index in (21, 36):
        position = info['rectangle_start'] + index * 20
        allowed_bytes[dat_offset + position:dat_offset + position + 20] = True
    texture_offset = struct.unpack_from('<I', target, 8 + 20 * 8)[0]
    assert texture_offset == report['texture_offset']
    allowed_bytes[texture_offset:texture_offset + len(packed)] = True
    assert np.array_equal(np.frombuffer(target, np.uint8)[~allowed_bytes],
                          np.frombuffer(original, np.uint8)[~allowed_bytes])
    spans = []
    for i in range(22):
        offset, size = struct.unpack_from('<II', target, 8 + i * 8)
        assert offset == struct.unpack_from('<I', original, 8 + i * 8)[0]
        assert offset % 2048 == 0 and 0 < size and offset + size <= len(target)
        spans.append((offset, offset + size))
        if i not in (19, 20):
            assert target[offset:offset + size] == members[i]
    spans.sort()
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    selected = {r['sprite']: r for r in report['draws']}
    protected = []
    mask_pixels = 0
    for source in info['rectangles']:
        pos = source['record_offset']
        width, height, cx, cy, u0, v0, u1, v1, tex, flags = struct.unpack_from('<HHhh6H', dat, pos)
        assert (u1 - u0) * 4 == width and v1 - v0 == height
        assert 0 <= u0 < u1 <= 256 and 0 <= v0 < v1 <= 256
        if source['sprite'] not in (21, 36):
            assert dat[pos:pos + 20] == members[19][pos:pos + 20]
        assert (tex, flags) == (source['texture_id'], source['flags'])
        if source['sprite'] not in selected:
            x0, y0, x1, y1 = source['source_box']
            assert np.array_equal(before[y0:y1, x0:x1], after[y0:y1, x0:x1])
            protected.append(source['id'])
            continue
        row = selected[source['sprite']]
        x0, y0, x1, y1 = row['target_box']
        assert [u0 * 4, v0, u1 * 4, v1] == row['target_box']
        assert [width, height] == row['target_size'] and [cx, cy] == row['target_anchor']
        assert width - 2 * cx == source['draw_size'][0] - 2 * source['anchor'][0]
        assert cy == source['anchor'][1] and height == source['draw_size'][1]
        ink = reference_mask(row['en'], 2)
        rh, rw = ink.shape
        assert rw + 1 <= width and rh + 1 <= height
        x, y = (width - rw - 1) // 2, (height - rh - 1) // 2
        expected = np.zeros((height, width), np.uint16)
        for yy, xx in zip(*np.nonzero(ink)):
            a = int(ink[yy, xx]); component = (2 * a + 127) // 255
            expected[y + yy + 1, x + xx + 1] = 32768 | component << 10 | component << 5 | component
        for yy, xx in zip(*np.nonzero(ink)):
            old = int(expected[y + yy, x + xx]); a = int(ink[yy, xx])
            channels = [(((old >> s) & 31) * (255 - a) + 31 * a + 127) // 255 for s in (10, 5, 0)]
            expected[y + yy, x + xx] = 32768 | channels[0] << 10 | channels[1] << 5 | channels[2]
        assert np.array_equal(after[y0:y1, x0:x1], expected), row['id']
        mask_pixels += int(np.count_nonzero(ink))
        for box in (source['source_box'], row['target_box']):
            a, b, c, d = box
            allowed_pixels[b:d, a:c] = True
        if source['sprite'] in (21, 36):
            a, b, c, d = source['source_box']
            assert not after[b:d, a:c].any()
    assert len(selected) == 56 and len(protected) == 28
    assert np.array_equal(before[~allowed_pixels], after[~allowed_pixels])
    assert all(name in protected for name in report['unresolved_names_preserved'])
    exe = (ROOT / 'work/output/0.1.25/1ST_READ.BIN').read_bytes()
    steps = verify(exe, packed[16:], decoded, len(decoded), instruction_limit=18_000_000)
    header_steps = texture_info(exe, 1024, 256, 0xd00)
    return {'source_build': '0.1.25', 'executable_sha256': digest(exe),
            'archive_sha256': digest(target), 'label_count': 56,
            'roles_company': 21, 'supported_name_readings': 35,
            'unresolved_original_name_sprites': report['unresolved_names_preserved'],
            'sprite_geometry_records': 84, 'protected_sprite_count': len(protected),
            'unchanged_member_payloads': 20, 'member_offsets': 'all original offsets retained',
            'independent_font_mask_pixels': mask_pixels,
            'independent_pixel_addressing_and_source_font_masks': 'pass',
            'original_pixels_and_archive_bytes_outside_declared_edits': 'exact',
            'native_PRS_instructions': steps, 'native_texture_info_instructions': header_steps,
            'native_decoded_bytes': len(decoded), 'native_guard_and_ABI': 'pass',
            'texture_dimensions': [1024, 256], 'changed_sprite_records': [21, 36],
            'name_reading_accuracy': 'secondary references; seven unresolved, further review pending',
            'native_file_loading': False, 'native_sprite_pipeline': False, 'GPU': False,
            'live_credit_timing_order_layout_appearance': 'pending'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: 56 labels, 84 geometry records, 28 protected sprites including seven unresolved names, exact outside edits, native decoder/texture info.', flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    result = check()
    print(json.dumps(result, indent=2), flush=True)
    if args.write_report:
        (OUT / 'native-test.json').write_text(json.dumps(result, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
