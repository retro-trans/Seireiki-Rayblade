"""Integrate translated credit roles and researched readings. Default dry run.

Preserves seven unresolved name images and all 21 original English/blank sprites.
Every texture remains at or below 1024 pixels; no emulator replacements.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr, untwiddle_indices
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import pixels, mask, stamp
from extract_staff_credits import analyze
from prepare_staff_credits import DEST, prepare
from rayblade_codec import compress, decompress

OUT = ROOT / 'work/output/staff-credits-draft-01'


def compose():
    recipe = json.loads(DEST.read_text('utf-8'))
    assert recipe == prepare()[0]
    info, archive, members, plain, image = analyze()
    before = pixels(plain, 1024, 256)
    plane = before.copy()
    allowed = np.zeros((256, 1024), bool)
    dat = bytearray(members[19])
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
            new_width = (ink.shape[1] + 4) // 4 * 4
            x0, y0 = 768, (0 if row['sprite'] == 21 else 20)
            assert row['sprite'] in (21, 36)
            target_box = [x0, y0, x0 + new_width, y0 + height]
            assert not before[y0:y0 + height, x0:x0 + new_width].any()
            cx += (new_width - width) // 2
            width = new_width
            struct.pack_into('<HHhh6H', dat, row['record_offset'], width, height, cx, cy,
                             x0 // 4, y0, (x0 + width) // 4, y0 + height,
                             row['texture_id'], row['flags'])
            allowed[y0:y0 + height, x0:x0 + width] = True
        x0, y0, x1, y1 = target_box
        rendering = stamp(plane[y0:y1, x0:x1], row['en'], [0, 0, width, height], 2)
        draws.append({**row, 'target_box': target_box, 'target_size': [width, height],
                      'target_anchor': [cx, cy], 'rendering': rendering})
    assert np.array_equal(before[~allowed], plane[~allowed])
    selected = {r['sprite'] for r in draws}
    for row in info['rectangles']:
        if row['sprite'] in selected:
            continue
        x0, y0, x1, y1 = row['source_box']
        assert np.array_equal(before[y0:y1, x0:x1], plane[y0:y1, x0:x1])
    linear = np.empty(1024 * 256, dtype='<u2')
    linear[untwiddle_indices(1024, 256).ravel()] = plane.ravel()
    decoded = plain[:32] + linear.tobytes()
    packed = members[20][:16] + compress(decoded)
    assert decompress(packed[16:]) == (decoded, len(packed) - 16)
    offsets = [struct.unpack_from('<II', archive, 8 + i * 8) for i in range(22)]
    texture_offset, old_size = offsets[20]
    capacity = offsets[21][0] - texture_offset
    assert len(packed) <= capacity, (len(packed), capacity)
    target = bytearray(archive)
    target[texture_offset:texture_offset + len(packed)] = packed
    struct.pack_into('<I', target, 8 + 20 * 8 + 4, len(packed))
    dat_offset, dat_size = offsets[19]
    assert len(dat) == dat_size
    target[dat_offset:dat_offset + dat_size] = dat
    assert len(target) == len(archive)
    for i, (offset, size) in enumerate(offsets):
        if i not in (19, 20):
            assert target[offset:offset + size] == members[i]
    report = {'kind': 'Native translated credits candidate; seven name readings unresolved',
              'source_build': '0.1.25', 'source_archive_sha256': digest(archive),
              'target_archive_sha256': digest(target), 'archive_bytes': len(target),
              'dat_sha256': digest(dat), 'texture_packed_sha256': digest(packed),
              'texture_decoded_sha256': digest(decoded), 'packed_bytes': len(packed),
              'original_packed_bytes': old_size, 'slot_capacity': capacity,
              'texture_offset': texture_offset, 'member_offsets': 'All original offsets retained',
              'texture_dimensions': [1024, 256], 'pixel_format': 'ARGB1555 twiddled rectangle',
              'translation_map_sha256': digest(DEST.read_bytes()),
              'translated_roles_company': 21, 'supported_personal_name_readings': 35,
              'unresolved_names_preserved': recipe['unresolved_name_ids'],
              'label_count': len(draws), 'changed_pixels': int((before != plane).sum()),
              'unchanged_archive_member_payloads': 20, 'protected_sprites': 28,
              'changed_sprite_records': [21, 36], 'draws': draws,
              'pending': ['Seven unresolved name readings and independent confirmation of secondary-reference names',
                          'Native PRS/texture/geometry checks and disc packaging',
                          'Live credits timing/order, layout/overlaps and appearance'],
              'story_library_draft_credit': 0}
    return bytes(target), bytes(dat), packed, decoded, report, image, decode_pvr(decoded)[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archive, dat, packed, decoded, report, original, translated = compose()
    print(json.dumps({k: v for k, v in report.items() if k != 'draws'}, indent=2))
    print('Expanded cells:', [(r['sprite'], r['en'], r['target_size']) for r in report['draws'] if r['sprite'] in (21, 36)])
    if not args.write:
        print('DRY RUN: no candidate written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in [('STAFF.AFS', archive), ('staff-credits.dat', dat),
                      ('staff-credits.packed.bin', packed), ('staff-credits.pvr', decoded)]:
        (OUT / name).write_bytes(raw)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    for page in range(4):
        sheet = Image.new('RGB', (1200, 800), '#30333a')
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 8), 'Original above / English below. Asset preview; native credits display unverified.', fill='white')
        for n, row in enumerate(report['draws'][page * 14:(page + 1) * 14]):
            x, y = n % 2 * 600 + 8, n // 2 * 108 + 30
            for dy, im, box in [(0, original, row['source_box']), (48, translated, row['target_box'])]:
                crop = im.crop(box)
                crop = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.NEAREST)
                sheet.paste(crop, (x, y + dy), crop)
            draw.text((x, y + 94), row['id'] + ' ' + row['en'], fill='white')
        sheet.save(OUT / f'credits-preview-{page:02d}.png')
    print('Wrote candidate and four before/after sheets:', OUT)


if __name__ == '__main__':
    main()
