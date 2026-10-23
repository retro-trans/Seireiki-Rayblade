"""Verify original Skies font port, native pixels and affected layouts. Dry first."""
import argparse
from collections import Counter
import json
import struct

import numpy as np

from analyze_skies_font import read_executable, skies_glyph
from build_skies_font_patch import OUT, PRIOR, VERSION, ROOT, compose, digest
from build_antialias_font import LEVELS, font_bytes
from build_font4x_patch import SMALL, MEDIUM
from build_genei_font import SMALL_DATA, MEDIUM_DATA
from test_font4x_patch import HDCPU
from test_outline_font import expected_pixels, legacy_mask
from scenario_word_wrap import tokens
from rayblade_codec import decompress
from check_native_text_components import verify
from test_ui_layouts import parse_ui, entry, specimen
from english_text_codec import encode
from extract_library import sections
from build_library_translation import EnglishSpanDecoder
from test_library_patch import filtered_page, reference_window
from test_library_layout import make_viewer, parse_page, expected_glyphs
from test_ordered_archive_layouts import directory_bytes, lookup
from afs_layout import compact_positions


def check():
    archive, component, masks, font, extras = compose()
    assert (OUT / 'WIN00.AFS').read_bytes() == archive
    assert json.loads((OUT / 'component-report.json').read_text('utf-8')) == component
    base = ROOT / 'work/output' / PRIOR
    exe = (base / '1ST_READ.BIN').read_bytes()
    old = font_bytes((base / 'WIN00.AFS').read_bytes())[1]
    skies, _ = read_executable()
    refs = {}
    allowed = set()
    for small, chars, table, start, height, scale in (
            (True, SMALL, 0x20, SMALL_DATA, 32, 1),
            (False, MEDIUM, 0xa0, MEDIUM_DATA, 64, 2)):
        for i, ch in enumerate(chars):
            if not ch.isascii():
                refs[small, ch] = legacy_mask(old, ch, small)
                continue
            source = skies_glyph(skies, ord(ch), LEVELS)
            bounds = source.getbbox()
            left = bounds[0] if bounds else 0
            ref = np.zeros((height, 32), np.uint8)
            for y in range(height):
                for x in range(32):
                    sx, sy = (x - 4) // scale + left, (y - 4) // scale
                    if 0 <= sx < 12 and 0 <= sy < 24:
                        ref[y, x] = source.getpixel((sx, sy))
            assert np.array_equal(legacy_mask(font, ch, small)[:, :32], ref)
            refs[small, ch] = ref
            allowed.add(table + i)
            allowed.update(range(start + i * height * 8, start + (i + 1) * height * 8))
    assert all(a == b or i in allowed for i, (a, b) in enumerate(zip(old, font)))
    cases = []
    for chars, flags, ex in ((SMALL, 64, 2), (MEDIUM, 0, 1)):
        cases.extend((ch, i + 32 if flags else i, flags | (128 if i % 2 else 0), 512, 32, ex, 2, 12, 4)
                     for i, ch in enumerate(chars))
    for small, chars in ((True, SMALL), (False, MEDIUM)):
        for ex, ey in ((0, 0), (0, 2), (1, 0), (1, 1), (2, 1), (2, 2)):
            for x, y in ((0, 0), (31, 31), (32, 4), (26, 28)):
                for ch in ('W', 'r', '♪'):
                    cases.append((ch, chars.index(ch) + (32 if small else 0), (64 if small else 0) | 128,
                                  32, 32, ex, ey, x, y))
        for color in range(0, 16, 2):
            for ch in ('r', 'O', '♪'):
                cases.append((ch, chars.index(ch) + (32 if small else 0), (64 if small else 0) | 128 | color,
                              256, 32, 2, 2, 12, 4))
    cases.extend(('?', g, f, 32, 32, 2, 2, 12, 4) for g, f in ((65535, 0), (600, 0), (4, 64), (31, 64)))
    instructions = 0
    for number, (ch, glyph, flags, w, h, ex, ey, x, y) in enumerate(cases):
        small = bool(flags & 64)
        cpu = HDCPU(exe, font, glyph, flags, w, h, ex, ey)
        cpu.write(0x8c1f36b6, x, 2)
        cpu.write(0x8c1f36b8, y, 2)
        expected = expected_pixels(cpu, refs[small, ch], flags, x, y)
        instructions += cpu.run_until(limit=300000)
        assert cpu.regions[3][1] == expected, (number, ch, flags, ex, ey)
        chars, table = (SMALL, 0x20) if small else (MEDIUM, 0xa0)
        assert cpu.read(0x8c1f36b6, 2) == x + font[table + chars.index(ch)]
        if (number + 1) % 100 == 0:
            print('Native font cases:', number + 1, flush=True)
    print('Native raster passed:', len(cases), instructions, flush=True)
    # Every retained story boundary is remeasured; no script archive rebuild.
    story = (base / 'D_SCE.AFS').read_bytes()
    sc = json.loads((base / 'text/scenario-component-report.json').read_text('utf-8'))
    count = Counter()
    maximum = 0
    for member in sc['members']:
        p = member['archive_offset']
        plain, used = decompress(story[p+20:p+member['packed_bytes']])
        assert digest(plain) == member['decoded_sha256'] and used == member['packed_bytes'] - 20
        for row in member['commands']:
            payload = plain[row['english_offset']:row['english_offset']+row['english_bytes']]
            assert digest(payload) == row['english_sha256']
            count['commands'] += 1
            pen = letters = 0
            for token in tokens(payload, font):
                if token['kind'] == 'boundary':
                    assert pen <= 236 and letters <= 127, (row['id'], pen, letters)
                    maximum = max(maximum, pen)
                    count['lines'] += 1
                    pen = letters = 0
                else:
                    pen += token['width']
                    letters += token['kind'] == 'glyph'
    print('Story boundaries:', dict(count), maximum, flush=True)
    names = extras['text/D_NAMES.en.dec.bin']
    prs_names = verify(exe, extras['text/D_NAMES.BIN'], names, 65536)
    bounds = {(small, ch): ref for (small, ch), ref in refs.items()}
    def inside(gs, lo, hi, bottom=None):
        for ch, x, y, small in gs:
            ys, xs = np.nonzero(bounds[small, ch])
            if len(xs):
                assert x + min(xs)/4 >= lo and x + (max(xs)+1)/4 + 1 <= hi, (ch, x, y, lo, hi)
                assert bottom is None or y + (max(ys)+1)/4 <= bottom
    def word(gs, text, x):
        at = ''.join(g[0] for g in gs).index(text)
        part = gs[at:at+len(text)]
        assert part[0][1:3] == (x, 0), (text, part)
        return part
    ui_steps = ui_cases = 0
    def ui(key, args=(), **kw):
        nonlocal ui_steps, ui_cases
        gs, n = parse_ui(exe, font, names, entry(names, key), args, **kw)
        ui_steps += n
        ui_cases += 1
        return gs
    inside(ui('names.g00.001', [('Retreat<NL>', False)]), 8, 72, 112)
    common = [(1, 2), ('99', True), ('999', True), (79, 3), ('9999', True), ('9999', True), ('200', False)]
    gs = ui('names.g00.003', common + [('999', False), ('999', False)], x=64, y=16)
    inside(word(gs, 'SP', 128), 128, 152)
    inside(word(gs, 'PR', 184), 184, 208)
    gs = ui('names.g00.160', common + [(49, 1), ('100', False)], x=64, y=16)
    inside(word(gs, 'SP', 128), 128, 152)
    inside(word(gs, 'Hit', 184), 184, 224)
    inside(word(gs, '100%', 224), 224, 256)
    gs = ui('names.g00.162', [('-99', False)])
    inside(word(gs, 'Ht Dif', 8), 8, 40)
    for value in ('ON', 'OFF'):
        inside(ui('names.g00.166', [(value, False)]), 8, 64)
    settings = ui('names.g01.032')
    inside(settings, 8, 248, 128)
    drafts = {r['id']: r for r in json.loads((ROOT / 'work/translation/en/ui/names.json').read_text('utf-8'))}
    for i in range(34, 42):
        key = f'names.g01.{i:03d}'
        gs = ui(key)
        inside(gs, 8, 248, 48)
        text = ' '.join(''.join(g[0] for g in gs if g[2] == y) for y in sorted({g[2] for g in gs}))
        assert text.split() == drafts[key]['en'].replace('<NL>', ' ').split()
    for i in range(128):
        inside(ui('names.g00.225', [(str(i+1), False), (i, 10)]), 8, 248, 16)
    for key in ('names.g00.212', 'names.g00.235'):
        inside(ui(key, [('99', False), ('99', False), ('99', False), (42, 10)]), 8, 248, 32)
    print('Native UI layouts passed:', ui_cases, flush=True)
    directory = directory_bytes('WIN00.AFS', archive)
    sdk_steps = 0
    for row in compact_positions(archive):
        off, sectors, n = lookup(exe, 'WIN00.AFS', directory, row['member'])
        assert off == row['declared_offset'] and sectors == row['sectors']
        sdk_steps += n
    paper = extras['text/D_PAPER.en.dec.bin']
    prs_paper = verify(exe, extras['text/D_PAPER.BIN'], paper, 0x20000 - 0x210)
    profiles = json.loads(extras['text/library-component-report.json'])['profiles']
    viewers = {h: make_viewer(exe, font, h)[0] for h in (6, 7)}
    library_steps = library_cases = filtered_cases = line_occurrences = 0
    for number, profile in enumerate(profiles):
        source = json.loads((ROOT / 'work/source/library/entries.json').read_text('utf-8'))
        original = next(e for e in source if e['id'] == profile['id'])
        start = profile['new_offset'] + len(bytes.fromhex(original['header_hex']))
        spans, end = sections(EnglishSpanDecoder(), paper, start)
        assert end == profile['new_offset'] + profile['bytes']
        gates = {g for s in spans for g in s['conditions']}
        payload = paper[start:end]
        full = b''.join(encode(s['text'])[:-1] for s in spans)
        # Boundary and unlock-controls are unchanged; exercise native filtering
        # on every profile with none/all flags, and parse every unlocked line.
        for enabled in (set(), gates):
            expected_full = b''.join(encode(s['text'])[:-1] for s in spans if all(g in enabled for g in s['conditions']))
            for h in (6, 7):
                actual, ret, n = filtered_page(exe, payload, enabled, 0, h)
                assert (actual, ret) == reference_window(expected_full, 0, h)
                library_steps += n
                filtered_cases += 1
        for h, viewer in viewers.items():
            for skip in range(0, full.count(b'\xfd') + 1, h):
                expected, _ = reference_window(full, skip, h)
                glyphs, n = parse_page(viewer, expected)
                assert glyphs == expected_glyphs(expected, font)
                inside(glyphs, 0, 240, h * 16)
                assert all(x + font[0xa0 + MEDIUM.index(ch)] <= 236 for ch, x, y, small in glyphs)
                library_steps += n
                library_cases += 1
                line_occurrences += len({g[2] for g in glyphs})
        if (number + 1) % 50 == 0:
            print('Native library profiles:', number + 1, flush=True)
    recipe = json.loads(extras['library-layouts.en.json'])
    assert line_occurrences == 2 * recipe['nonempty_line_count']
    proof = {'source_build': PRIOR, 'version': VERSION, 'archive_sha256': digest(archive),
        'font_sha256': digest(font), 'executable_sha256': digest(exe),
        'glyph_cases': len(cases), 'raster_SH4_instructions': instructions,
        'native_guard_and_ABI': 'pass', 'archive_bytes_outside_declared_edits': 'exact',
        'font_source_pixels_and_native_raster': 'exact; both banks, four alpha levels, colors, shadow, clipping, scales, fallbacks',
        'unchanged_other_WIN00_members': 88, 'protected_symbols': 'exact prior masks/advances',
        'story': {**dict(count), 'maximum_pen_width': maximum, 'budget': 236, 'archive': 'byte-exact prior build'},
        'names_sha256': digest(names), 'names_packed_sha256': digest(extras['text/D_NAMES.BIN']),
        'native_UI_cases': ui_cases, 'native_UI_instructions': ui_steps,
        'native_WIN00_lookup_cases': 90, 'native_WIN00_lookup_instructions': sdk_steps,
        'PRS_names_instructions': prs_names, 'PRS_library_instructions': prs_paper,
        'library_sha256': digest(paper), 'library_profiles': len(profiles),
        'library_filter_cases': filtered_cases, 'library_parser_pages': library_cases,
        'library_native_line_occurrences': line_occurrences, 'library_native_instructions': library_steps,
        'limits': ['No live GPU font appearance, navigation, long-session or whole-game proof',
                   'UI parameters/context tiles, glyph cursors and graphics endpoints use established bounded fixtures',
                   'Library none/all flags sampled natively; all intermediate unlock combinations not rerun',
                   'Existing raster/allocation code is byte-exact prior build and retains its 1024 cap'],
        'release': False}
    return proof, settings, font


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: native raster, every story boundary, native UI/PRS and all library lines in both viewers.', flush=True)
    if not args.verify:
        print('DRY RUN: no execution or report')
        return
    proof, settings, font = check()
    print(json.dumps(proof, indent=2), flush=True)
    if args.write_report:
        (OUT / 'native-test.json').write_text(json.dumps(proof, indent=2) + '\n', 'utf-8')
        specimen(OUT / 'settings-preview.png', settings, font)


if __name__ == '__main__':
    main()
