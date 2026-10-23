"""Port the original Skies Latin pixels and remeasure layouts. Dry run first."""
import argparse
from functools import lru_cache
import json
import math
import struct

from PIL import Image, ImageDraw

from analyze_skies_font import read_executable, skies_glyph, check_native_codebook, EXPECTED_EXE
from build_antialias_font import font_bytes, LEVELS
from build_bitmap_font import ROOT, digest
from build_font4x_patch import SMALL, MEDIUM
from build_genei_font import SMALL_DATA, MEDIUM_DATA
from build_chapter_cards import repack
from build_library_translation import build as library_component
from prepare_library_layouts import prepare as library_layouts
from build_names_translation import compose as names_component
from build_library_header_patch import recipe as old_ui_layout

VERSION, PRIOR = '0.1.39', '0.1.38'
OUT = ROOT / 'work/output/skies-font-draft-01'


def make_font(old, exe):
    target = bytearray(old)
    masks, metrics = {}, {}
    for bank, chars, height, scale, table, start in (
            ('small', SMALL, 8, 1, 0x20, SMALL_DATA),
            ('medium', MEDIUM, 16, 2, 0xa0, MEDIUM_DATA)):
        masks[bank] = {}
        metrics[bank] = []
        for i, ch in enumerate(chars):
            if not ch.isascii():
                continue
            source = skies_glyph(exe, ord(ch), LEVELS)
            box = source.getbbox()
            left = box[0] if box else 0
            mask = Image.new('L', (64, height * 4))
            mask.paste(source.resize((12 * scale, 24 * scale), Image.Resampling.NEAREST),
                       (4 - left * scale, 4))
            assert not mask.crop((32, 0, 64, height * 4)).getbbox()
            # One rule for all letters, preserving their original pixel shapes.
            advance = math.ceil((box[2] - left) * scale / 4) + 1 if box else old[table + i]
            target[table + i] = advance
            for y in range(height * 4):
                words = [sum(LEVELS.index(mask.getpixel((half * 16 + x, y))) << (30 - 2 * x)
                             for x in range(16)) for half in range(2)]
                struct.pack_into('<2I', target, start + i * height * 32 + y * 8, *words)
            assert sum(mask.tobytes()) == sum(source.tobytes()) * scale * scale
            masks[bank][ch] = mask
            metrics[bank].append({'character': ch, 'glyph_id': i, 'advance': advance,
                'prior_advance': old[table + i], 'source_bounds': box,
                'packed_mask_bounds': mask.getbbox(), 'coverage_mask_sha256': digest(mask.tobytes())})
        for i, ch in enumerate(chars):
            if not ch.isascii():
                at = start + i * height * 32
                assert target[at:at + height * 32] == old[at:at + height * 32]
                assert target[table + i] == old[table + i]
    return bytes(target), masks, metrics


def ui_layout(font):
    rows = {r['id']: r for r in json.loads((ROOT / 'work/translation/en/ui/names.json').read_text('utf-8'))}
    recipe = old_ui_layout()
    def add(key, en, reason):
        old = rows[key]
        recipe['rows'][key] = {'en': en, 'source_sha256': old['source_sha256'],
                              'prior_en_sha256': digest(old['en'].encode()), 'reason': reason}
    for key, replacements in {
        'names.g00.001': [('Counter Orders', 'Counters')],
        'names.g00.003': [('Spirit', 'SP'), ('Prana', 'PR')],
        'names.g00.160': [('Spirit', 'SP')],
        'names.g00.162': [('Ht Diff', 'Ht Dif')],
        'names.g01.049': [('Hit Rate', 'Hit')],
        'names.g00.212': [('Cleared Ch. ', 'Clear '), ('"', '')],
        'names.g00.225': [('Cleared Ch. ', 'Clear '), ('"', '')],
        'names.g00.235': [('Cleared Ch. ', 'Clear '), ('"', '')],
    }.items():
        en = recipe['rows'].get(key, rows[key])['en']
        for before, after in replacements:
            assert before in en
            en = en.replace(before, after)
        add(key, en, 'Compact display label for original Skies glyph widths; full terms stay in glossary/drafts')
    width = lambda s: sum(font[0xa0 + MEDIUM.index(c)] for c in s)
    for i in range(34, 42):
        key = f'names.g01.{i:03d}'
        words = rows[key]['en'].replace('<NL>', ' ').split()
        lines, line = [], ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if width(candidate) > 236:
                assert line
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        assert len(lines) <= 3 and ' '.join(lines).split() == words
        add(key, '<NL>'.join(lines), 'Rewrap all original help words for the Skies font, at most three lines')
    recipe.update(version=VERSION, font_build=VERSION)
    return recipe


@lru_cache(maxsize=1)
def compose():
    base = ROOT / 'work/output' / PRIOR
    source = (base / 'WIN00.AFS').read_bytes()
    offset, old = font_bytes(source)
    exe, _ = read_executable()
    assert digest(exe) == EXPECTED_EXE
    codebook = check_native_codebook(exe, (0x0000, 0x5fff, 0xbfff, 0xffff))
    font, masks, metrics = make_font(old, exe)
    # Establish that the reconstruction recipes still reproduce the current build.
    old_library_recipe = library_layouts()
    old_paper, old_packed, _ = library_component(section_overrides=old_library_recipe['sections'])
    assert old_paper == (base / 'text/D_PAPER.en.dec.bin').read_bytes()
    old_ui = old_ui_layout()
    old_names, old_names_packed, _ = names_component(overrides=old_ui['rows'])
    assert old_names == (base / 'text/D_NAMES.en.dec.bin').read_bytes()
    assert old_names_packed == (base / 'text/D_NAMES.BIN').read_bytes()
    library_recipe = library_layouts(font=font)
    library_recipe.update(version=VERSION, source_build=PRIOR)
    paper, packed, paper_report = library_component(section_overrides=library_recipe['sections'], version=VERSION)
    assert len(paper) == len(old_paper)
    assert all(a == b or (a, b) in ((0, 253), (253, 0)) for a, b in zip(old_paper, paper))
    ui = ui_layout(font)
    names, packed_names, names_report = names_component(overrides=ui['rows'], version=VERSION)
    assert len(packed_names) <= len(old_names_packed)
    names_report['stream_bytes'] = len(packed_names)
    names_report['stream_sha256'] = digest(packed_names)
    packed_names += bytes(len(old_names_packed) - len(packed_names))
    names_report.update(file_bytes=len(packed_names), file_sha256=digest(packed_names),
                        zero_tail_bytes=len(packed_names) - names_report['stream_bytes'])
    decoded_names, consumed_names = __import__('rayblade_codec').decompress(packed_names)
    assert decoded_names == names and consumed_names == names_report['stream_bytes']
    assert not any(packed_names[consumed_names:])
    archive, packing = repack(source, {0: font, 52: packed})
    packing['validation'] = 'Only font member 0 and library member 52 replaced; other 88 member payloads exact; compact sector order retained'
    assert len(archive) == len(source)
    old_member_off, old_member_size = struct.unpack_from('<II', source, 8 + 52 * 8)
    assert source[old_member_off:old_member_off + old_member_size] == old_packed
    for i in range(90):
        a, n = struct.unpack_from('<II', source, 8 + i * 8)
        b, m = struct.unpack_from('<II', archive, 8 + i * 8)
        if i not in (0, 52):
            assert n == m and source[a:a+n] == archive[b:b+m]
    extras = {'text/D_NAMES.en.dec.bin': names, 'text/D_NAMES.BIN': packed_names,
              'text/names-component-report.json': json.dumps(names_report, indent=2).encode() + b'\n',
              'text/D_PAPER.en.dec.bin': paper, 'text/D_PAPER.BIN': packed,
              'text/library-component-report.json': json.dumps(paper_report, indent=2).encode() + b'\n',
              'library-layouts.en.json': json.dumps(library_recipe, indent=2).encode() + b'\n',
              'ui-layouts.en.json': json.dumps(ui, indent=2).encode() + b'\n'}
    report = {'version': VERSION, 'source_build': PRIOR,
        'method': 'Original Skies VQ coverage decoded exactly; uniform 1x small / 2x medium repeats, no contour reconstruction',
        'source_skies_executable_sha256': digest(exe), 'source_font_sha256': digest(old),
        'target_font_sha256': digest(font), 'source_archive_sha256': digest(source),
        'target_archive_sha256': digest(archive),
        'executable_sha256': digest((base / '1ST_READ.BIN').read_bytes()),
        'font_member_bytes': len(font), 'glyphs_per_bank': 95, 'coverage_levels': LEVELS,
        'native_skies_codebook_check': codebook, 'metrics': metrics,
        'library': {k: v for k, v in library_recipe.items() if k != 'sections'},
        'library_changed_decoded_bytes': sum(a != b for a, b in zip(old_paper, paper)),
        'library_sha256': digest(paper), 'library_packed_sha256': digest(packed),
        'names_sha256': digest(names), 'names_packed_sha256': digest(packed_names),
        'names_compressed_stream_bytes': names_report['stream_bytes'],
        'names_file_zero_tail_bytes': names_report['zero_tail_bytes'],
        'ui_overrides': ui['rows'],
        'archive_repack': {k: v for k, v in packing.items() if k != 'members'},
        'unchanged_other_archive_members': 88,
        'limits': ['Original bitmap detail, not a higher resolution vector font',
                   'Native raster/layout verification and local packaging are separate gates',
                   'GPU filtering/blending and actual in-game appearance still require testing']}
    return archive, json.loads(json.dumps(report)), masks, font, extras


def preview(masks, font):
    im = Image.new('RGB', (1024, 300), '#171b24')
    draw = ImageDraw.Draw(im)
    draw.text((16, 12), 'Rayblade 0.1.39 - original Skies bitmap, variable spacing (offline)', fill='white', font_size=20)
    for y, text in ((55, 'r O o R 0 - Good morning, Touya!'),
                    (130, 'The teacher is coming this way...'),
                    (205, 'Attack  Wait  Counters  Objectives')):
        x = 16
        for ch in text:
            mask = masks['medium'][ch]
            im.paste('white', (x, y, x + mask.width, y + mask.height), mask)
            x += font[0xa0 + MEDIUM.index(ch)] * 4
        assert x < 1024
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archive, report, masks, font, extras = compose()
    print(json.dumps({k: v for k, v in report.items() if k not in ('metrics', 'ui_overrides')}, indent=2), flush=True)
    for key in ('names.g00.001', 'names.g00.003', 'names.g00.162', 'names.g01.034'):
        print(key, report['ui_overrides'][key]['en'], flush=True)
    if not args.write:
        print('DRY RUN: no files written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'WIN00.AFS').write_bytes(archive)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    for path, raw in extras.items():
        dest = OUT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    for bank, glyphs in masks.items():
        folder = OUT / 'glyphs' / bank
        folder.mkdir(parents=True, exist_ok=True)
        for ch, mask in glyphs.items():
            mask.save(folder / f'{ord(ch):03d}.png')
    preview(masks, font).save(OUT / 'font-preview.png')
    print('Wrote candidate:', OUT, flush=True)


if __name__ == '__main__':
    main()
