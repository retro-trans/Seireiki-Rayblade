"""Render and insert two English album pictures plus three matching thumbnails.

Default dry run. Retain current English captions and all other archive data.
Note changes only native luma; greeting changes only its header rectangle.
"""
import argparse
import json
import math
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from audit_texture_archive import decode_pvr, untwiddle_indices
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import pixels, mask
from extract_album_captions import analyze
from prepare_album_picture_text import DEST, prepare
from prepare_story_letter import BOXES, POSITIONS, cv2
from rayblade_codec import compress, decompress

OUT = ROOT / 'work/output/album-pictures-draft-01'
PRIOR = '0.1.29'


def greeting(plain, recipe):
    original = decode_pvr(plain)[0].convert('RGB')
    rgb = np.asarray(original).copy()
    x0, y0, x1, y1 = recipe['source_text_region']
    assert (x0, y0, x1, y1) == (92, 0, 234, 52)
    rgb[y0:y1, x0:x1] = 255
    image = Image.fromarray(rgb)
    placements = []
    for text, denominator, x, y in [('Happy New Year!', 1, 94, 19), ('2000', 2, 190, 2)]:
        ink = Image.fromarray(mask(text, denominator))
        edge = ink.filter(ImageFilter.MaxFilter(3))
        assert x >= x0 and y >= y0 and x + ink.width <= 214 and y + ink.height <= y1
        image.paste((237, 174, 68), (x, y, x + edge.width, y + edge.height), edge)
        image.paste((231, 47, 127), (x, y, x + ink.width, y + ink.height), ink)
        placements.append({'en': text, 'denominator': denominator, 'box': [x, y, x + ink.width, y + ink.height]})
    rgb = np.asarray(image).astype(float)
    raw = np.frombuffer(plain[32:], np.uint8).reshape(256, 1024)
    changed = raw.copy()
    # Full-range inverse of the local YUV preview convention. Only pairs in
    # the greeting header are re-encoded; original art/chroma elsewhere exact.
    region = rgb[y0:y1, x0:x1]
    r, g, b = region[:, :, 0], region[:, :, 1], region[:, :, 2]
    yy = .299 * r + .587 * g + .114 * b
    uu = 128 - .168736 * r - .331264 * g + .5 * b
    vv = 128 + .5 * r - .418688 * g - .081312 * b
    pairs = changed[y0:y1, x0*2:x1*2].reshape(y1-y0, (x1-x0)//2, 4)
    pairs[:, :, 0] = np.rint(uu.reshape(y1-y0, -1, 2).mean(axis=2)).clip(0, 255).astype(np.uint8)
    pairs[:, :, 2] = np.rint(vv.reshape(y1-y0, -1, 2).mean(axis=2)).clip(0, 255).astype(np.uint8)
    pairs[:, :, 1] = np.rint(yy[:, ::2]).clip(0, 255).astype(np.uint8)
    pairs[:, :, 3] = np.rint(yy[:, 1::2]).clip(0, 255).astype(np.uint8)
    # Preserve the original heart in complete chroma-sharing native pairs.
    changed[26:49, 214*2:232*2] = raw[26:49, 214*2:232*2]
    target = plain[:32] + changed.tobytes()
    allowed = np.zeros_like(raw, bool)
    allowed[y0:y1, x0*2:x1*2] = True
    allowed[26:49, 214*2:232*2] = False
    assert np.array_equal(raw[~allowed], changed[~allowed])
    report = {'member': 15, 'English_lines': recipe['English_lines'], 'draws': placements,
              'allowed_native_header_box': [x0, y0, x1, y1], 'original_heart_box': [214, 26, 232, 49],
              'original_heart_native_bytes': 'exact', 'portrait_and_all_bytes_outside_header': 'exact',
              'source_decoded_sha256': digest(plain), 'target_decoded_sha256': digest(target),
              'color_scope': 'Header-only YUV422 pairs; preview uses full-range approximate RGB conversion'}
    return target, report, {'changed': np.any(changed.reshape(256, 512, 2) != raw.reshape(256, 512, 2), axis=2)}


def note(plain, recipe):
    raw = np.frombuffer(plain[32:], np.uint8).reshape(256, 1024)
    luma = raw[:, 1::2].copy()
    angle = -19
    c, s = abs(math.cos(math.radians(angle))), abs(math.sin(math.radians(angle)))
    width, height = math.ceil(512*c + 256*s), math.ceil(256*c + 512*s)
    transform = cv2.getRotationMatrix2D((256, 128), angle, 1)
    transform[:, 2] += [width/2 - 256, height/2 - 128]
    # Undo this album copy's 240-to-224 vertical reduction before deskewing.
    transform = (np.vstack([transform, [0, 0, 1]]) @ np.diag([1., 240/224, 1.]))[:2]
    rotated = cv2.warpAffine(luma, transform, (width, height), flags=cv2.INTER_LINEAR)
    paper = cv2.morphologyEx(rotated, cv2.MORPH_CLOSE, np.ones((1, 15), np.uint8))
    region = np.zeros_like(rotated, np.uint8)
    for x0, y0, x1, y1 in BOXES:
        # Album resampling spreads faint ink beyond the story image's tight
        # character bounds. Keep a small shared margin around those regions.
        region[max(0,y0-2):y1+2, max(0,x0-2):x1+2] = 1
    difference = paper.astype(float) - rotated
    seeds = ((difference > 15) & (rotated < 140) & (region != 0)).astype(np.uint8)
    # Do not require a nearby <140 seed: the rescaled album copy includes
    # faint antialiased fragments with no dark core. Horizontal paper lines
    # remain in the local closing estimate; this is still an estimate.
    old = (difference > 3) & (region != 0)
    assert seeds.sum() > 100
    ink_y = int(np.percentile(rotated[seeds != 0], 20))
    ink = np.zeros_like(rotated, np.uint8)
    draws = []
    for text, (x, y) in zip(recipe['English_lines'], POSITIONS):
        glyphs = mask(text, 2)
        h, w = glyphs.shape
        assert x+w <= width and y+h <= height and not ink[y:y+h, x:x+w].any()
        ink[y:y+h, x:x+w] = glyphs
        draws.append({'en': text, 'box_in_deskewed_paper': [x, y, x+w, y+h]})
    inverse = cv2.invertAffineTransform(transform)
    erase = cv2.warpAffine(old.astype(np.float32), inverse, (512, 256), flags=cv2.INTER_LINEAR) > .05
    paper_y = cv2.warpAffine(paper, inverse, (512, 256), flags=cv2.INTER_LINEAR)
    alpha = cv2.warpAffine(ink, inverse, (512, 256), flags=cv2.INTER_LINEAR)
    source_text_region = cv2.warpAffine(region, inverse, (512, 256), flags=cv2.INTER_NEAREST) != 0
    allowed = erase | (alpha > 0)
    assert not allowed[:, 320:].any() and not allowed[224:].any()
    clean = np.where(erase, paper_y, luma).astype(float)
    target_y = np.rint(clean * (1-alpha/255) + ink_y * alpha/255).clip(0, 255).astype(np.uint8)
    target_y[~allowed] = luma[~allowed]
    changed = raw.copy()
    changed[:, 1::2] = target_y
    target = plain[:32] + changed.tobytes()
    assert target[32::2] == plain[32::2] and target[:32] == plain[:32]
    report = {'member': 81, 'English_lines': recipe['English_lines'], 'draws': draws,
              'source_decoded_sha256': digest(plain), 'target_decoded_sha256': digest(target),
              'original_chroma_and_headers': 'exact', 'visible_bounds': [0, 0, 320, 224],
              'changed_luma_pixels': int((target_y != luma).sum()), 'old_ink_seeds': int(seeds.sum()),
              'paper_recovery': 'Local estimates from this album source, not exact hidden original pixels',
              'transform': transform.tolist(), 'ink_luma': ink_y,
              'related_draft_rows': recipe['related_draft_rows']}
    return target, report, {'erase': erase, 'source_text_region': source_text_region,
                            'alpha': alpha, 'ink_y': ink_y, 'flat_English_ink': ink,
                            'rotated_source': rotated, 'old_ink': old}


def reduced(field):
    return np.asarray(Image.fromarray(field.astype(np.float32)).crop((0, 0, 320, 224)).resize((64, 48), Image.Resampling.BOX))


def thumbnail(original, picture, detail, member):
    source = np.asarray(original.convert('RGB'))
    if member == 15:
        image = picture.crop((0, 0, 320, 224)).convert('RGB')
        low = np.asarray(image.resize((64, 48), Image.Resampling.BOX))
        allowed = reduced(detail['changed']) > 0
        allowed[6:11, 43:47] = False
        target = source.copy()
        target[allowed] = low[allowed]
    else:
        # The independently authored thumbnail is not pixel-identical to a
        # reduction of the full YUV picture. Clean its own local paper over
        # mapped text regions, including a one-pixel phase margin.
        erase = cv2.dilate((reduced(detail['source_text_region']) > 0).astype(np.uint8),
                           np.ones((3, 3), np.uint8)) != 0
        alpha = reduced(detail['alpha'])
        allowed = erase | (alpha > 0)
        paper = cv2.morphologyEx(source, cv2.MORPH_CLOSE, np.ones((1, 9), np.uint8))
        clean = np.where(erase[:, :, None], paper, source).astype(float)
        a = alpha[:, :, None] / 255
        target = np.rint(clean*(1-a) + detail['ink_y']*a).clip(0, 255).astype(np.uint8)
        target[~allowed] = source[~allowed]
    return target, allowed


def compose():
    recipe = json.loads(DEST.read_text('utf-8'))
    assert recipe == prepare()
    info, _, original_members, _ = analyze()
    source = (ROOT / 'work/output' / PRIOR / 'ALBUM.AFS').read_bytes()
    positions = [struct.unpack_from('<II', source, 8+i*8) for i in range(244)]
    assert len(source) == 22493184
    members = [source[o:o+n] for o,n in positions]
    outputs, pictures, details, reports = {}, {}, {}, []
    for row, renderer in zip(recipe['pictures'], (greeting, note)):
        member = row['member']
        assert members[member] == original_members[member]
        decoded, used = decompress(members[member][16:])
        assert used == len(members[member])-16 and digest(decoded) == row['source_decoded_sha256']
        translated, report, detail = renderer(decoded, row)
        outputs[member] = translated
        pictures[member] = (decode_pvr(decoded)[0], decode_pvr(translated)[0])
        details[member] = detail
        reports.append(report)
    atlas_before, atlas_after, atlas_plain = {}, {}, {}
    thumbnail_reports, thumbnails = [], []
    for row in recipe['pictures']:
        for binding in row['gallery_bindings']:
            member = binding['texture_member']
            if member not in atlas_before:
                plain, used = decompress(members[member][16:])
                assert used == len(members[member])-16
                atlas_plain[member] = plain
                atlas_before[member] = pixels(plain, 256, 256)
                atlas_after[member] = atlas_before[member].copy()
            image = decode_pvr(atlas_plain[member])[0]
            x0, y0, x1, _ = binding['source_box']
            box = (x0, y0, x1, y0+48)
            crop = image.crop(box)
            rgb, allowed = thumbnail(crop, pictures[row['member']][1], details[row['member']], row['member'])
            cell = atlas_after[member][y0:y0+48, x0:x1]
            assert np.all((cell[allowed] >> 15) == 1), 'Thumbnail text edits leave the original opaque picture'
            q = (rgb.astype(np.uint16) * 31 + 127) // 255
            encoded = 32768 | q[:, :, 0] << 10 | q[:, :, 1] << 5 | q[:, :, 2]
            cell[allowed] = encoded[allowed]
            thumbnail_reports.append({'id': binding['id'], 'texture_member': member, 'picture_member': row['member'],
                                      'photo_box': list(box), 'changed_pixels': int(np.count_nonzero(atlas_before[member][y0:y0+48, x0:x1] != cell))})
            thumbnails.append((binding['id'], crop, Image.fromarray(rgb)))
    for member, plane in atlas_after.items():
        old = atlas_before[member]
        allowed = np.zeros((256, 256), bool)
        for binding in [b for row in recipe['pictures'] for b in row['gallery_bindings'] if b['texture_member'] == member]:
            x0,y0,x1,_ = binding['source_box']
            allowed[y0:y0+48,x0:x1] = True
        assert np.array_equal(old[~allowed], plane[~allowed])
        linear = np.empty(256*256, '<u2')
        linear[untwiddle_indices(256,256).ravel()] = plane.ravel()
        outputs[member] = atlas_plain[member][:32] + linear.tobytes()
    target = bytearray(source)
    resources = []
    packed_outputs = {}
    occupied = [(o,o+n) for o,n in positions]
    for member, decoded in sorted(outputs.items()):
        packed = members[member][:16] + compress(decoded)
        assert decompress(packed[16:]) == (decoded, len(packed)-16)
        old_offset, old_size = positions[member]
        next_offset = min([o for o,_ in positions if o > old_offset] + [len(source)])
        offset = old_offset
        if len(packed) > next_offset-old_offset:
            offset = next((o for o in range(0x10000, 0x80000, 2048)
                           if o+len(packed) <= 0x80000 and source[o:o+len(packed)] == bytes(len(packed))
                           and all(o+len(packed) <= a or o >= b for a,b in occupied)), None)
            assert offset is not None, 'No verified prefix space for translated picture'
            occupied.append((offset, offset+len(packed)))
        elif len(packed) > old_size:
            assert source[old_offset+old_size:old_offset+len(packed)] == bytes(len(packed)-old_size)
        target[offset:offset+len(packed)] = packed
        struct.pack_into('<II', target, 8+member*8, offset, len(packed))
        packed_outputs[member] = (packed, decoded)
        resources.append({'member': member, 'source_offset': old_offset, 'target_offset': offset,
                          'source_packed_bytes': old_size, 'target_packed_bytes': len(packed),
                          'target_decoded_bytes': len(decoded), 'target_decoded_sha256': digest(decoded),
                          'target_packed_sha256': digest(packed)})
    for member, (o,n) in enumerate(positions):
        if member not in outputs:
            assert struct.unpack_from('<II', target, 8+member*8) == (o,n)
            assert target[o:o+n] == source[o:o+n]
    assert set(outputs) == {15, 81, 216, 218, 225}
    report = {'source_build': PRIOR, 'source_archive_sha256': digest(source), 'target_archive_sha256': digest(target),
              'image_resource_count': 5, 'full_pictures': reports, 'thumbnail_edits': thumbnail_reports,
              'resources': resources, 'unchanged_member_payloads': 239, 'archive_members': 244,
              'recipe_sha256': digest(DEST.read_bytes()),
              'original_all_caption_areas_and_DAT_geometry': 'exact',
              'relocated_members': [r['member'] for r in resources if r['source_offset'] != r['target_offset']],
              'normal_text_font_changed': False, 'story_library_draft_credit': 0,
              'pending': ['Native pixel/archive/decode checks, packaging and independent meaning/artwork review',
                          'Native album I/O, unlocks, selection/navigation and live appearance',
                          'Two unresolved caption source readings and remaining game work']}
    return bytes(target), report, pictures, thumbnails, packed_outputs, details


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archive, report, pictures, thumbnails, outputs, details = compose()
    print('Plan:', [(r['member'], r['source_packed_bytes'], r['target_packed_bytes'], r['target_offset']) for r in report['resources']])
    print('Relocations:', report['relocated_members'], 'Target archive:', report['target_archive_sha256'])
    if not args.write:
        print('DRY RUN: no picture candidates or native archive written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'ALBUM.AFS').write_bytes(archive)
    (OUT/'component-report.json').write_text(json.dumps(report, indent=2)+'\n', 'utf-8')
    for member, (packed, decoded) in outputs.items():
        (OUT/f'member-{member:03d}.packed.bin').write_bytes(packed)
        (OUT/f'member-{member:03d}.pvr').write_bytes(decoded)
    for member, pair in pictures.items():
        sheet = Image.new('RGB', (1280, 480), '#30333a')
        for x, label, im in ((0,'Original',pair[0]), (640,'English native candidate - live appearance unverified',pair[1])):
            sheet.paste(im.crop((0,0,320,224)).resize((640,448),Image.Resampling.NEAREST),(x,24))
            ImageDraw.Draw(sheet).text((x+4,4),label,fill='white')
        sheet.save(OUT/f'picture-{member:03d}-before-after.png')
    sheet = Image.new('RGB', (768, 336), '#30333a')
    for i,(id,old,new) in enumerate(thumbnails):
        for y,im in ((24,old),(180,new)):
            sheet.paste(im.resize((256,144),Image.Resampling.NEAREST),(i*256,y))
        ImageDraw.Draw(sheet).text((i*256+4,4),id+' original / English',fill='white')
    sheet.save(OUT/'thumbnail-before-after.png')
    for name, field in details[81].items():
        if isinstance(field,np.ndarray):
            im = field.astype(np.uint8)*255 if field.dtype == bool else field
            Image.fromarray(im).save(OUT/('note-'+name+'.png'))


if __name__ == '__main__':
    main()
