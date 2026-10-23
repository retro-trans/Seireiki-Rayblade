"""Correct all three native copies of the five counterattack-order icons.

Default dry run. Keeps the current font, all frames, palettes and geometry.
The 0.1.20 Sup/Nil labels were wrong: these orders are Aggressive/Safe.
"""
import argparse
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from audit_effect_palettes import original as original_effect, parse
from audit_pvm_archive import chunks
from audit_texture_archive import untwiddle_indices
from build_antialias_font import font_bytes
from build_bitmap_font import ROOT, digest
from build_ui_atlas_patch import pixels
from extract_effect_ui import analyze as effect_geometry
from extract_ui_atlases import analyze as win_geometry
from preview_font_sampling import packed_mask
from rayblade_codec import compress, decompress

PRIOR = '0.1.33'
OUT = ROOT / 'work/output/order-icons-draft-01'
DEST = ROOT / 'work/translation/en/ui/counterattack-orders.en.json'
ORDERS = [('マ', 'Manual', 'M'), ('反', 'Always Counterattack', 'C'),
          ('積', 'Be Aggressive', 'A'), ('無', 'Play It Safe', 'S'),
          ('防', 'Always Defend', 'D')]


def member(archive, index):
    offset, size = struct.unpack_from('<II', archive, 8 + index * 8)
    return archive[offset:offset + size]


def masks(font):
    result = {}
    for _, _, letter in ORDERS:
        # Same 1/4 scale for every 64-square native glyph; trim bearings only.
        native = packed_mask(font, letter)
        small = native.resize((16, 16), Image.Resampling.LANCZOS)
        # Retain the game's four coverage levels, also removing tiny ringing.
        levels = np.array([0, 85, 187, 255], np.int16)
        values = np.asarray(small).astype(np.int16)
        small = Image.fromarray(levels[np.abs(values[:, :, None]-levels).argmin(axis=2)].astype(np.uint8))
        small = small.crop(small.getbbox())
        assert small.width + 1 <= 10 and small.height + 1 <= 13
        result[letter] = small
    return result


def recipe():
    names = json.loads((ROOT / 'work/translation/en/ui/names.json').read_text('utf-8'))
    context = next(r for r in names if r['id'] == 'names.g00.174')
    assert context['ja'] == 'マニュアル<NL>必ず反撃する<NL>積極的にいけ<NL>無理はするな<NL>必ず防御しろ'
    assert context['en'].split('<NL>') == [r[1] for r in ORDERS]
    return {'status': 'Source-linked correction; offline native/packaging checks required',
            'source_build': PRIOR, 'context_id': context['id'],
            'context_source_sha256': context['source_sha256'], 'full_menu': context['en'],
            'native_selection': {'start': '0x8c0627d8', 'stop': '0x8c062810',
                                 'order_byte': 'unit record + 8, bits 5:3',
                                 'sprite': '58 + order', 'resource': 3},
            'historical_correction': '0.1.20 Sup/Resupply and Nil/None for sprites 60/61 were incorrect. Superseded in all three copies; Manual 58 was also missing.',
            'rows': [{'order': i, 'sprite': 58+i, 'ja_ui': ja, 'en': en, 'initial': letter}
                     for i, (ja, en, letter) in enumerate(ORDERS)],
            'limits': 'Native selector binds the five WIN00 order sprites. EFFECT copy shares exact source art/coordinates; its live selection/palette binding is not proved.'}


def rgba1555(values):
    return np.stack([((values >> shift) & 31) * 255 // 31 for shift in (10, 5, 0)]
                    + [np.where(values & 0x8000, 255, 0)], axis=-1).astype(np.uint8)


def draw_cell(original, ink, palette=None, interior_left=3):
    cell = original.copy()
    right = interior_left+10
    ids, counts = np.unique(original[2:15, interior_left:right], return_counts=True)
    background = int(ids[counts.argmax()])
    # Actual bevel is wider than one pixel. Preserve the source outline and
    # only erase its 10x13 text interior; restore the old WIN00 patch's bevel.
    cell[2:15, interior_left:right] = background
    x = interior_left + (10-ink.width-1)//2
    y = 2 + (13-ink.height-1)//2
    coverage = np.asarray(ink)
    def blend(xx, yy, alpha, color):
        old = int(cell[yy, xx])
        if palette is None:
            rgb = [(old >> shift) & 31 for shift in (10, 5, 0)]
            target = [int(v*31//255) for v in color]
            mixed = [(a*(255-alpha)+b*alpha+127)//255 for a, b in zip(rgb, target)]
            cell[yy, xx] = 0x8000 | (mixed[0]<<10) | (mixed[1]<<5) | mixed[2]
        else:
            mixed = (palette[old, :3].astype(np.int32)*(255-alpha) + np.array(color)*alpha + 127)//255
            distance = ((palette[:, :3].astype(np.int32)-mixed)**2).sum(axis=1)
            distance[palette[:, 3] == 0] = 2**30
            cell[yy, xx] = int(distance.argmin())
    for color, delta in [((16, 16, 16), 1), ((255, 255, 255), 0)]:
        for yy, xx in zip(*np.nonzero(coverage)):
            blend(x+int(xx)+delta, y+int(yy)+delta, int(coverage[yy, xx]), color)
    assert np.array_equal(cell[0], original[0]) and np.array_equal(cell[-1], original[-1])
    assert np.array_equal(cell[:, 0], original[:, 0]) and np.array_equal(cell[:, -1], original[:, -1])
    return cell, {'background': background, 'interior_box': [interior_left, 2, right, 15],
                  'ink_xy': [x, y], 'mask_size': list(ink.size),
                  'mask_sha256': digest(ink.tobytes())}


def replace_slots(source, replacements):
    target = bytearray(source)
    count = struct.unpack_from('<I', source, 4)[0]
    placements = []
    for n, packed in replacements.items():
        offset, size = struct.unpack_from('<II', source, 8+n*8)
        end = struct.unpack_from('<I', source, 16+n*8)[0] if n+1<count else len(source)
        assert len(packed) <= end-offset, (n, len(packed), end-offset)
        if len(packed)>size:
            assert source[offset+size:offset+len(packed)] == bytes(len(packed)-size)
        target[offset:offset+len(packed)] = packed
        struct.pack_into('<I', target, 12+n*8, len(packed))
        placements.append({'member': n, 'offset': offset, 'source_packed_bytes': size,
                           'packed_bytes': len(packed), 'slot_capacity': end-offset,
                           'packed_sha256': digest(packed)})
    return bytes(target), placements


def compose():
    base = ROOT / 'work/output' / PRIOR
    source_win = (base / 'WIN00.AFS').read_bytes()
    source_effect = (base / 'EFFECT.AFS').read_bytes()
    _, font = font_bytes(source_win)
    assert digest(font) == '63407f4c30151aa0bece46ef72b5372fa2cbe4120fd9c7ce9fe79f5e28a1c6fa'
    glyphs = masks(font)
    mapping = recipe()
    replacements = {'WIN00.AFS': {}, 'EFFECT.AFS': {}}
    decoded = {}
    resources = []
    previews = []
    for info, original_dat, source_plain, original_image in win_geometry()[:2]:
        n = info['texture_member']
        assert member(source_win, info['dat_member']) == original_dat
        raw = member(source_win, n)
        plain, used = decompress(raw[16:])
        assert used == len(raw)-16
        before = pixels(plain, info['width'], info['height'])
        original_plane = pixels(source_plain, info['width'], info['height'])
        a, b, c, d = info['rectangles'][58]['source_box']
        frame_template = original_plane[b:d, a:c]
        after = before.copy()
        draws = []
        for row in mapping['rows']:
            box = info['rectangles'][row['sprite']]['source_box']
            x, y, u, v = box
            # Texture 2's artwork is one pixel left of texture 6's duplicate.
            # Use the cleanable Manual source frame consistently: some other
            # Japanese glyphs overwrote their own bevel with white strokes.
            new, rendering = draw_cell(frame_template, glyphs[row['initial']],
                                       interior_left=2 if n==2 else 3)
            rendering['frame_template_sprite'] = 58
            after[y:v, x:u] = new
            draws.append({**row, 'source_box': box, 'rendering': rendering})
            previews.append((f'WIN00 {n:02d} / {row["en"]}', original_image.crop(box),
                             Image.fromarray(rgba1555(before[y:v, x:u])), Image.fromarray(rgba1555(new))))
        linear = np.empty(before.size, '<u2')
        linear[untwiddle_indices(info['width'], info['height']).ravel()] = after.ravel()
        target_plain = plain[:32] + linear.tobytes()
        packed = raw[:16] + compress(target_plain)
        assert decompress(packed[16:]) == (target_plain, len(packed)-16)
        replacements['WIN00.AFS'][n] = packed
        decoded[('WIN00.AFS', n)] = target_plain
        resources.append({'archive': 'WIN00.AFS', 'member': n, 'dat_member': info['dat_member'],
                          'dimensions': [info['width'], info['height']], 'draws': draws,
                          'decoded_sha256': digest(target_plain), 'decoded_bytes': len(target_plain),
                          'changed_pixels': int((before != after).sum())})
    raw = member(source_effect, 250)
    plain, texture, pal, before, colors, _ = parse(raw)
    geometry, *_ = effect_geometry()
    _, source_members = original_effect()
    _, _, _, original_indices, original_colors, _ = parse(source_members[250])
    after = before.copy()
    draws = []
    for row in mapping['rows']:
        box = geometry['rectangles'][row['sprite']]['source_box']
        x, y, u, v = box
        # These five source cells were untouched in every preceding effect patch.
        assert np.array_equal(before[y:v, x:u], original_indices[y:v, x:u])
        new, rendering = draw_cell(before[y:v, x:u], glyphs[row['initial']], colors[4])
        after[y:v, x:u] = new
        draws.append({**row, 'source_box': box, 'rendering': rendering})
        previews.append((f'EFFECT 250 / {row["en"]}', Image.fromarray(original_colors[4][original_indices[y:v, x:u]]),
                         Image.fromarray(colors[4][before[y:v, x:u]]), Image.fromarray(colors[4][new])))
    linear = np.empty(before.size, np.uint8)
    linear[untwiddle_indices(256, 256).ravel()] = after.ravel()
    position = chunks(plain)[2][0]['chunk_offset']+16
    target_plain = plain[:position] + (linear[::2] | (linear[1::2]<<4)).tobytes() + plain[position+32768:]
    packed = compress(target_plain)
    assert decompress(packed) == (target_plain, len(packed))
    replacements['EFFECT.AFS'][250] = packed
    decoded[('EFFECT.AFS', 250)] = target_plain
    resources.append({'archive': 'EFFECT.AFS', 'member': 250, 'dimensions': [256, 256],
                      'draws': draws, 'decoded_sha256': digest(target_plain), 'decoded_bytes': len(target_plain),
                      'palette_sha256': digest(pal), 'preview_palette_bank': 4,
                      'changed_pixels': int((before != after).sum())})
    archives, reports = {}, {}
    for name, source in [('WIN00.AFS', source_win), ('EFFECT.AFS', source_effect)]:
        archives[name], placements = replace_slots(source, replacements[name])
        reports[name] = {'source_archive_sha256': digest(source), 'target_archive_sha256': digest(archives[name]),
                         'archive_bytes': len(source), 'placements': placements}
    report = {'source_build': PRIOR, 'kind': 'Five counterattack-order icons, all three native atlas copies',
              'font_sha256': digest(font), 'font_scale': 'Uniform 1/4 for all five glyphs; trimmed bearings only',
              'recipe': mapping, 'archives': reports, 'resources': resources,
              'icon_cells': 15, 'normal_font_changed': False,
              'pending': ['Independent wording/initial discoverability review', 'Live unit-list, battle and palette/appearance validation']}
    return archives, report, replacements, decoded, previews


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archives, report, replacements, decoded, previews = compose()
    print(json.dumps({n: r['placements'] for n, r in report['archives'].items()}, indent=2))
    if not args.write:
        print('DRY RUN: no files written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in archives.items():
        (OUT / name).write_bytes(raw)
    for (name, n), plain in decoded.items():
        (OUT / f'{name}-{n:03d}.decoded.bin').write_bytes(plain)
        (OUT / f'{name}-{n:03d}.packed.bin').write_bytes(replacements[name][n])
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2)+'\n', 'utf-8')
    DEST.write_text(json.dumps(report['recipe'], ensure_ascii=False, indent=2)+'\n', 'utf-8')
    page = Image.new('RGB', (1000, 70+len(previews)*112), '#30333a')
    draw = ImageDraw.Draw(page)
    draw.text((12, 12), 'Original source | preceding English build | corrected order initial', fill='white')
    draw.text((12, 30), 'Native 16x16 cells enlarged 5x for inspection. Live palette/appearance unverified.', fill='white')
    for i, (label, *images) in enumerate(previews):
        y = 70+i*112
        for j, image in enumerate(images):
            crop = image.resize((80, 80), Image.Resampling.NEAREST)
            page.paste(crop, (j*140+12, y), crop)
        draw.text((450, y+25), label, fill='white')
    page.save(OUT / 'before-after.png')
    print('Wrote two native archive candidates and fifteen labeled icon witnesses; no game build written.')


if __name__ == '__main__':
    main()
