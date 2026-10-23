"""Link Kasumi's pictured note to existing drafts and preview native luma edits.

Uses source-only paper estimates and uniformly scaled supplied Latin glyphs.
Only Y bytes can change in the original YUV422 texture; chroma stays exact.
Default dry run. Does not patch an archive or disc.
"""
import argparse
import json
import math
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr
from build_bitmap_font import ROOT, ATLAS, digest
from build_ui_atlas_patch import mask
from disc_inventory import Disc
from prepare_scenario_translation import fingerprint
from rayblade_codec import decompress

sys.path.insert(0, str(ROOT / 'work/vendor/opencv5'))
import cv2

DEST = ROOT / 'work/translation/en/ui/story-letter.en.json'
OUT = ROOT / 'work/output/story-letter-draft-01'
COMMAND = 'scenario.s_081.o00659'
BOXES = [[90, 18, 164, 37], [87, 53, 243, 72], [87, 68, 267, 88],
         [87, 82, 282, 103], [87, 97, 237, 118], [87, 139, 125, 159],
         [87, 154, 215, 177], [87, 180, 337, 204], [87, 198, 151, 218],
         [87, 211, 218, 236], [270, 248, 339, 277]]
POSITIONS = [[94, 22], [91, 56], [91, 70], [91, 84], [91, 98],
             [91, 143], [91, 157], [91, 185], [91, 201], [91, 215], [277, 253]]


def source():
    disc = Disc(next(ROOT.glob('*.cue')))
    entry = next(r for r in disc.inventory() if r['path'] == 'ADV00.AFS')
    head = disc.read(entry['lba'], 8192)
    offset, size = struct.unpack_from('<II', head, 8 + 379 * 8)
    packed = disc.read(entry['lba'] + offset // 2048, size)
    decoded, used = decompress(packed[16:])
    assert used == len(packed) - 16 and packed[:4] == decoded[:4] == b'GBIX'
    image, info = decode_pvr(decoded)
    assert info == {'pixel_format': 3, 'data_format': 9, 'width': 512, 'height': 256}
    return packed, decoded, image


def prepare():
    packed, decoded, _ = source()
    rows = [r for r in json.loads((ROOT / 'work/translation/en/scenario/s_081.json').read_text('utf-8'))
            if r.get('source_command_id') == COMMAND]
    originals = {r['id']: r for r in json.loads((ROOT / 'work/source/scenario-text/rows.json').read_text('utf-8'))}
    blocks = {b['id']: b for b in json.loads((ROOT / 'work/source/scenario-text/blocks.json').read_text('utf-8'))}
    assert len(rows) == 10
    links, lines = [], []
    for index, row in enumerate(rows):
        assert row['status'] == 'draft' and isinstance(row['en'], str) and not row['source_review_needed']
        assert originals[row['id']]['ja'] == row['ja']
        assert fingerprint(originals[row['id']], blocks[row['block_id']]['source_sha256']) == row['source_sha256']
        text = row['en']
        if index == 0:
            assert text.startswith('"')
            text = text[1:]
        if index == 9:
            assert text.endswith('"') and text.count('          ') == 1
            main, signature = text[:-1].split('          ')
            lines.extend([main, signature])
        else:
            lines.append(text)
        links.append({'id': row['id'], 'source_sha256': row['source_sha256'], 'draft_sha256': digest(row['en'].encode())})
    assert len(lines) == 11 and all(all(' ' <= ch <= '~' for ch in s) for s in lines)
    return {'image_id': 'adv00.379.kasumi-note', 'archive': 'ADV00.AFS', 'member': 379,
            'source_packed_sha256': digest(packed), 'source_decoded_sha256': digest(decoded),
            'source_command': COMMAND, 'related_draft_rows': links, 'English_lines': lines,
            'line_positions_in_deskewed_texture': POSITIONS, 'original_ink_boxes_in_deskewed_texture': BOXES,
            'deskew_clockwise_degrees': 19, 'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'),
            'font_sha256': digest(ATLAS.read_bytes()), 'font_source_scale': 'Uniform 1/2, twelve-pixel cell height',
            'meaning': 'Kasumi has made breakfast, asks Touya to reheat miso soup, leaves Yamato food despite not seeing her, apologizes for earlier, warns about sleeping dressed like that, and reminds him not to be late.',
            'decisions': 'Reuse all ten established English rows; remove only outer quotation marks and place signature separately. Clothing remains unspecified. No new story-row credit.',
            'status': 'Native image preview; paper recovery, fit and live appearance require review'}


def render(recipe):
    _, decoded, original = source()
    raw = np.frombuffer(decoded[32:], np.uint8).reshape(256, 1024)
    luma = raw[:, 1::2].copy()
    angle = -recipe['deskew_clockwise_degrees']
    c, s = abs(math.cos(math.radians(angle))), abs(math.sin(math.radians(angle)))
    width, height = math.ceil(512 * c + 256 * s), math.ceil(256 * c + 512 * s)
    transform = cv2.getRotationMatrix2D((256, 128), angle, 1)
    transform[:, 2] += [width / 2 - 256, height / 2 - 128]
    rotated = cv2.warpAffine(luma, transform, (width, height), flags=cv2.INTER_LINEAR)
    background = cv2.morphologyEx(rotated, cv2.MORPH_CLOSE, np.ones((1, 15), np.uint8))
    region = np.zeros_like(rotated, np.uint8)
    for x0, y0, x1, y1 in recipe['original_ink_boxes_in_deskewed_texture']:
        region[y0:y1, x0:x1] = 1
    difference = background.astype(np.float32) - rotated
    seeds = ((difference > 15) & (rotated < 140) & (region != 0)).astype(np.uint8)
    old_ink = (cv2.dilate(seeds, np.ones((3, 3), np.uint8)) != 0) & (difference > 3) & (region != 0)
    assert seeds.sum() > 100
    ink_y = int(np.percentile(rotated[seeds != 0], 20))
    target_ink = np.zeros_like(rotated, np.uint8)
    fits = []
    for text, (x, y) in zip(recipe['English_lines'], recipe['line_positions_in_deskewed_texture']):
        ink = mask(text, 2)
        h, w = ink.shape
        assert x >= 0 and y >= 0 and x + w <= width and y + h <= height
        assert not target_ink[y:y+h, x:x+w].any()
        target_ink[y:y+h, x:x+w] = ink
        fits.append({'en': text, 'box': [x, y, x+w, y+h]})
    inverse = cv2.invertAffineTransform(transform)
    erase_coverage = cv2.warpAffine(old_ink.astype(np.float32), inverse, (512, 256), flags=cv2.INTER_LINEAR)
    paper_y = cv2.warpAffine(background, inverse, (512, 256), flags=cv2.INTER_LINEAR)
    alpha = cv2.warpAffine(target_ink, inverse, (512, 256), flags=cv2.INTER_LINEAR)
    allowed = (erase_coverage > .05) | (alpha > 0)
    assert not allowed[:, 320:].any() and not allowed[240:, :].any(), 'Edit escapes the visible 320x240 photograph'
    # Set an estimated paper value, rather than adding a resampled brightness
    # delta to a different native sample; the latter makes bright text ghosts.
    clean_y = np.where(erase_coverage > .05, paper_y, luma).astype(np.float32)
    target_y = np.rint(clean_y * (1 - alpha / 255) + ink_y * alpha / 255).clip(0, 255).astype(np.uint8)
    target_y[~allowed] = luma[~allowed]
    target_raw = raw.copy()
    target_raw[:, 1::2] = target_y
    target = decoded[:32] + target_raw.tobytes()
    assert target[:32] == decoded[:32] and target[32::2] == decoded[32::2]
    assert np.array_equal(luma[~allowed], target_y[~allowed])
    report = {'source_decoded_sha256': digest(decoded), 'target_decoded_sha256': digest(target),
              'texture_size': [512, 256], 'native_pixel_format': 'YUV422 rectangular',
              'all_U_V_bytes_and_texture_headers': 'exact original',
              'native_luma_pixels_changed': int((target_y != luma).sum()),
              'old_ink_seed_pixels': int(seeds.sum()), 'old_ink_edit_pixels_deskewed': int(old_ink.sum()),
              'ink_luma_from_source_percentile': ink_y, 'deskewed_size': [width, height],
              'rotation_matrix': transform.tolist(), 'lines': fits,
              'recipe': str(DEST.relative_to(ROOT)).replace('\\', '/'),
              'limits': ['Source-only local paper estimates, not exact recovery of originally hidden paper pixels.',
                         'Native letter image not inserted; full pixel review and native decoding/packaging pending.',
                         'No extra story/library draft credit or live appearance claim.']}
    return target, original, decode_pvr(target)[0], report, rotated, old_ink, target_ink


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    recipe = prepare()
    target, original, translated, report, rotated, old_ink, target_ink = render(recipe)
    print(json.dumps({k: v for k, v in report.items() if k != 'lines'}, indent=2))
    print('English lines:', [(r['en'], r['box']) for r in report['lines']])
    if not args.write:
        print('DRY RUN: no image candidate or translation map written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
    (OUT / 'letter.pvr').write_bytes(target)
    (OUT / 'render-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    original.save(OUT / 'original.png')
    translated.save(OUT / 'English.png')
    Image.fromarray(rotated).save(OUT / 'deskewed-source-luma.png')
    Image.fromarray(old_ink.astype(np.uint8) * 255).save(OUT / 'original-ink-mask.png')
    Image.fromarray(target_ink).save(OUT / 'English-ink-mask.png')
    preview = Image.new('RGB', (1280, 560), '#30333a')
    draw = ImageDraw.Draw(preview)
    for x, label, image in [(0, 'Original', original), (640, 'English candidate - source-only paper estimates', translated)]:
        draw.text((x + 5, 5), label, fill='white')
        crop = image.crop((0, 0, 320, 240)).resize((640, 480), Image.Resampling.NEAREST)
        preview.paste(crop, (x, 25))
    draw.text((5, 525), 'Native asset preview; same source image and original chroma. Not an in-game screenshot.', fill='white')
    preview.save(OUT / 'before-after.png')
    print('Wrote native luma-only image candidate and linked English:', OUT)


if __name__ == '__main__':
    main()
