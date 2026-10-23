"""Build native English letter and event-placeholder image archive. Dry first."""
import argparse
from collections import Counter
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr, untwiddle_indices
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import pixels, stamp
from disc_inventory import Disc
from prepare_story_letter import DEST as LETTER_RECIPE, OUT as LETTER_OUT, prepare, render
from rayblade_codec import compress, decompress

OUT = ROOT / 'work/output/story-images-draft-01'
DEST = ROOT / 'work/translation/en/ui/story-image-labels.en.json'
WAITING = (303, 307, 321, 333, 335, 337)
DUMMY = (481, 483)
SELECTED = (*WAITING, 379, *DUMMY)


def compose():
    disc = Disc(next(ROOT.glob('*.cue')))
    entry = next(r for r in disc.inventory() if r['path'] == 'ADV00.AFS')
    original = disc.read(entry['lba'], entry['size'])
    count = struct.unpack_from('<I', original, 4)[0]
    assert original[:4] == b'AFS\0' and count == 777
    offsets = [struct.unpack_from('<II', original, 8 + i * 8) for i in range(count)]
    assert all(a[0] + a[1] <= b[0] for a, b in zip(offsets, offsets[1:]))
    recipe = prepare()
    assert json.loads(LETTER_RECIPE.read_text('utf-8')) == recipe
    expected_letter, _, _, letter_report, *_ = render(recipe)
    assert (LETTER_OUT / 'letter.pvr').read_bytes() == expected_letter
    assert json.loads((LETTER_OUT / 'render-report.json').read_text('utf-8')) == letter_report
    target = bytearray(original)
    resources, labels, previews = [], [], {}
    sources, results = {}, {}
    for i in SELECTED:
        offset, size = offsets[i]
        packed = original[offset:offset + size]
        plain, used = decompress(packed[16:])
        assert packed[:4] == plain[:4] == b'GBIX' and used == len(packed) - 16
        before, info = decode_pvr(plain)
        if i == 379:
            assert digest(plain) == recipe['source_decoded_sha256'] and digest(packed) == recipe['source_packed_sha256']
            decoded = expected_letter
            kind, rows = 'Kasumi note', recipe['English_lines']
            assert decoded[:32] == plain[:32] and decoded[32::2] == plain[32::2]
            native = np.frombuffer(decoded[32:], np.uint8).reshape(256, 1024)
            old_native = np.frombuffer(plain[32:], np.uint8).reshape(256, 1024)
            assert np.array_equal(native[:, 640:], old_native[:, 640:]) and np.array_equal(native[240:], old_native[240:])
        else:
            assert info == {'pixel_format': 0, 'data_format': 1, 'width': 512, 'height': 512}
            plane = pixels(plain, 512, 512)
            after = plane.copy()
            background = Counter(map(int, plane[:240, :320].ravel())).most_common(1)[0][0]
            after[:240, :320] = background
            rows = ['Event Illustration', 'Work in Progress' if i in WAITING else 'Dummy']
            draws = [stamp(after, text, box, 1) for text, box in zip(rows, ([30, 22, 290, 54], [30, 62, 290, 94]))]
            assert np.array_equal(plane[:, 320:], after[:, 320:]) and np.array_equal(plane[240:], after[240:])
            linear = np.empty(512 * 512, dtype='<u2')
            linear[untwiddle_indices(512, 512).ravel()] = after.ravel()
            decoded = plain[:32] + linear.tobytes()
            kind = 'event illustration work-in-progress placeholder' if i in WAITING else 'event illustration dummy placeholder'
            labels.append({'id': f'adv00.{i:03d}', 'member': i, 'en_lines': rows,
                           'source_decoded_sha256': digest(plain), 'replace_box': [0, 0, 320, 240],
                           'draws': draws, 'font_source_scale': 'Uniform 1x supplied bitmap, 24-pixel cell height',
                           'meaning': kind, 'reachability': 'not established; shipped development artwork'})
        encoded = packed[:16] + compress(decoded)
        target_offset = offset
        capacity = offsets[i + 1][0] - offset
        if i == 379:
            # Keep the complete message and source-quality luma edits. The
            # compressed result needs more space than its old file slot.
            target_offset = 0x60000
            capacity = min(o for o, _ in offsets) - target_offset
            assert original[target_offset:target_offset + capacity] == bytes(capacity)
        assert len(encoded) <= capacity, (i, len(encoded), capacity)
        assert decompress(encoded[16:]) == (decoded, len(encoded) - 16)
        assert encoded[:16] == packed[:16] and decoded[:32] == plain[:32]
        target[target_offset:target_offset + len(encoded)] = encoded
        struct.pack_into('<II', target, 8 + i * 8, target_offset, len(encoded))
        resources.append({'member': i, 'kind': kind, **info, 'source_offset': offset, 'target_offset': target_offset,
                          'source_packed_bytes': size, 'target_packed_bytes': len(encoded), 'slot_capacity': capacity,
                          'decoded_bytes': len(decoded), 'source_packed_sha256': digest(packed),
                          'source_decoded_sha256': digest(plain), 'target_packed_sha256': digest(encoded),
                          'target_decoded_sha256': digest(decoded), 'en_lines': rows})
        sources[i], results[i] = plain, (encoded, decoded)
        previews[i] = (before, decode_pvr(decoded)[0])
    assert len(target) == len(original)
    for i, (offset, size) in enumerate(offsets):
        assert struct.unpack_from('<I', target, 8 + i * 8)[0] == (0x60000 if i == 379 else offset)
        if i not in SELECTED:
            assert target[offset:offset + size] == original[offset:offset + size]
    translation = {'source': 'Original ADV00.AFS event artwork', 'letter_recipe': str(LETTER_RECIPE.relative_to(ROOT)).replace('\\', '/'),
                   'placeholder_images': labels, 'story_library_draft_credit': 0,
                   'notes': ['Work in Progress translates the event-image preparation notice; Dummy preserves the development label.',
                             'No replacement artwork is invented for unfinished source illustrations.',
                             'Actual native reachability and live appearance remain unverified.']}
    report = {'source_build': '0.1.26', 'kind': 'English note and eight development placeholder images',
              'source_archive_sha256': digest(original), 'target_archive_sha256': digest(target),
              'archive_bytes': len(target), 'archive_members': count, 'changed_members': list(SELECTED),
              'unchanged_member_payloads': count - len(SELECTED),
              'member_offsets': 'Only letter member 379 moves to checked zero padding at 0x60000; 776 original offsets retained',
              'letter_recipe_sha256': digest(LETTER_RECIPE.read_bytes()), 'letter_render': letter_report,
              'resources': resources, 'normal_text_font_changed': False,
              'pending': ['Native PRS/texture and independent preservation checks', 'Disc packaging',
                          'Paper-estimate artwork review and live archive loading/image selection/appearance',
                          'Development-placeholder reachability and remaining image/PVM/movie audit'],
              'story_library_draft_credit': 0}
    return bytes(target), report, translation, previews, sources, results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archive, report, translation, previews, _, results = compose()
    print(json.dumps({k: v for k, v in report.items() if k not in ('resources', 'letter_render')}, indent=2))
    print('Native image slots:', [(r['member'], r['target_packed_bytes'], r['slot_capacity']) for r in report['resources']])
    if not args.write:
        print('DRY RUN: no archive candidate or image-label map written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'ADV00.AFS').write_bytes(archive)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    DEST.write_text(json.dumps(translation, indent=2) + '\n', 'utf-8')
    for i, (packed, decoded) in results.items():
        (OUT / f'member-{i:03d}.packed.bin').write_bytes(packed)
        (OUT / f'member-{i:03d}.pvr').write_bytes(decoded)
    sheet = Image.new('RGB', (1280, 1100), '#30333a')
    draw = ImageDraw.Draw(sheet)
    for n, i in enumerate((303, 379, 481)):
        for x, im in zip((0, 640), previews[i]):
            crop = im.crop((0, 0, 320, 240))
            crop.thumbnail((620, 320), Image.Resampling.NEAREST)
            sheet.paste(crop, (x + 8, n * 360 + 24), crop if crop.mode == 'RGBA' else None)
        draw.text((8, n * 360 + 4), f'Member {i}: original left / English right; asset preview, native display unverified', fill='white')
    sheet.save(OUT / 'story-images-preview.png')
    print('Wrote nine native image candidates; eight original slots and one verified-padding relocation:', OUT)


if __name__ == '__main__':
    main()
