"""Build a native English world-map archive candidate. Default dry run.

Changes ten place-label cells and the two sprite records needing wider text.
Only the texture member moves, into checked zero padding; it stays 512x512.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr, untwiddle_indices
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import pixels, mask, stamp
from extract_worldmap_labels import analyze
from prepare_worldmap_translation import DEST, prepare
from rayblade_codec import compress, decompress

OUT = ROOT / 'work/output/worldmap-draft-01'


def compose():
    recipe = json.loads(DEST.read_text('utf-8'))
    assert recipe == prepare()
    info, archive, members, plain, image = analyze()
    before = pixels(plain, 512, 512)
    plane = before.copy()
    allowed = np.zeros((512, 512), bool)
    dat = bytearray(members[17])
    draws = []
    for row in recipe['rows']:
        x0, y0, x1, y1 = row['source_box']
        assert digest(image.crop(row['source_box']).tobytes()) == row['source_pixels_sha256']
        allowed[y0:y1, x0:x1] = True
        plane[y0:y1, x0:x1] = 0
        ink = mask(row['en'], 2)
        width, height = row['draw_size']
        cx, cy = row['anchor']
        target_box = row['source_box']
        if ink.shape[1] + 1 > width:
            new_width = (ink.shape[1] + 2) // 2 * 2
            x0, y0 = 336, (112 if row['sprite'] == 24 else 132)
            assert row['sprite'] in (24, 26)
            target_box = [x0, y0, x0 + new_width, y0 + height]
            assert not before[y0:y0 + height, x0:x0 + new_width].any()
            # Keep the horizontal center relative to the original call point.
            cx += (new_width - width) // 2
            width = new_width
            struct.pack_into('<HHhh6H', dat, row['record_offset'], width, height, cx, cy,
                             x0 // 2, y0 // 2, (x0 + width) // 2, (y0 + height) // 2,
                             row['texture_id'], row['flags'])
            allowed[y0:y0 + height, x0:x0 + width] = True
        x0, y0, x1, y1 = target_box
        rendering = stamp(plane[y0:y1, x0:x1], row['en'], [0, 0, width, height], 2,
                          color=(19, 23, 24))
        draws.append({**row, 'target_box': target_box, 'target_size': [width, height],
                      'target_anchor': [cx, cy], 'rendering': rendering})
    assert np.array_equal(before[~allowed], plane[~allowed])
    for row in info['rectangles'][:17] + info['rectangles'][27:]:
        x0, y0, x1, y1 = row['source_box']
        assert np.array_equal(before[y0:y1, x0:x1], plane[y0:y1, x0:x1])
    linear = np.empty(512 * 512, dtype='<u2')
    linear[untwiddle_indices(512, 512).ravel()] = plane.ravel()
    decoded = plain[:32] + linear.tobytes()
    packed = members[18][:16] + compress(decoded)
    assert decompress(packed[16:]) == (decoded, len(packed) - 16)
    target = bytearray(archive)
    offsets = [struct.unpack_from('<II', archive, 8 + i * 8) for i in range(20)]
    source_offset, old_size = offsets[18]
    original_capacity = offsets[19][0] - source_offset
    # The larger English atlas cannot fit its original compressed slot.
    # Relocate this member only, retaining every other AFS offset and payload.
    target_texture_offset = offset = 0x78000
    capacity = min(o for o, _ in offsets) - offset
    assert offset % 2048 == 0 and len(packed) <= capacity
    assert archive[offset:offset + capacity] == bytes(capacity)
    target[offset:offset + len(packed)] = packed
    struct.pack_into('<II', target, 8 + 18 * 8, offset, len(packed))
    dat_offset, dat_size = offsets[17]
    assert len(dat) == dat_size
    target[dat_offset:dat_offset + dat_size] = dat
    assert len(target) == len(archive)
    for i, (offset, size) in enumerate(offsets):
        if i not in (17, 18):
            assert target[offset:offset + size] == members[i]
    report = {'kind': 'Native English world-map image candidate; not yet packaged or live verified',
              'source_build': '0.1.24', 'source_archive_sha256': digest(archive),
              'target_archive_sha256': digest(target), 'archive_bytes': len(target),
              'dat_sha256': digest(dat), 'texture_packed_sha256': digest(packed),
              'texture_decoded_sha256': digest(decoded), 'packed_bytes': len(packed),
              'original_packed_bytes': old_size, 'original_slot_capacity': original_capacity,
              'texture_source_offset': source_offset, 'texture_target_offset': target_texture_offset,
              'verified_zero_padding_capacity': capacity,
              'texture_dimensions': [512, 512], 'pixel_format': 'ARGB1555 twiddled',
              'translation_map_sha256': digest(DEST.read_bytes()),
              'label_count': len(draws), 'changed_pixels': int((before != plane).sum()),
              'unchanged_archive_member_payloads': 18, 'protected_sprites': 18,
              'changed_sprite_records': [24, 26], 'draws': draws,
              'pending': ['Native PRS/texture/geometry checks', 'Disc packaging',
                          'Live archive loading, map positions, label overlaps, selection and navigation'],
              'story_library_draft_credit': 0}
    return bytes(target), bytes(dat), packed, decoded, report, image, decode_pvr(decoded)[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archive, dat, packed, decoded, report, original, translated = compose()
    print(json.dumps({k: v for k, v in report.items() if k != 'draws'}, indent=2))
    print('Labels:', [(r['sprite'], r['en'], r['target_size']) for r in report['draws']])
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in [('WMAP.AFS', archive), ('worldmap-labels.dat', dat),
                      ('worldmap-labels.packed.bin', packed), ('worldmap-labels.pvr', decoded)]:
        (OUT / name).write_bytes(raw)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    sheet = Image.new('RGB', (1000, 630), '#30333a')
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 8), 'Original above / English below. Native asset preview; live map unverified.', fill='white')
    for n, row in enumerate(report['draws']):
        x, y = n % 2 * 500 + 8, n // 2 * 120 + 30
        for dy, im, box in [(0, original, row['source_box']), (48, translated, row['target_box'])]:
            crop = im.crop(box)
            crop = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.NEAREST)
            sheet.paste(crop, (x, y + dy), crop)
        draw.text((x, y + 98), row['id'] + ' ' + row['en'], fill='white')
    sheet.save(OUT / 'worldmap-labels-preview.png')
    print('Wrote', OUT)


if __name__ == '__main__':
    main()
