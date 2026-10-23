"""Prepare timed English MOV072 UI overlays with reviewed numeric boundaries.

Dry first. Each label uses the same half-source bitmap scale. Three standard
abbreviations retain full terms in the recipe; no individual glyph stretching.
"""
import argparse
from collections import Counter
import json

import numpy as np
from PIL import Image, ImageDraw

from build_bitmap_font import ROOT, ATLAS, digest
from prepare_movie_translation import mask
from prepare_movie_ui import prepare as ui_drafts


FRAMES = ROOT / 'work/ui/asset-audit/movies/MOV072/frames-2310-2635'
OUT = ROOT / 'work/ui/movies/MOV072/ui-overlay-drafts'
RECIPE = ROOT / 'work/translation/en/movies/MOV072-ui-layout.en.json'
INTERVALS = {'status_commands': [2397, 2427], 'unit_commands': [2469, 2487],
             'weapon_list': [2489, 2515], 'battle_preview': [2563, 2623]}

# key: erase rectangle, text origin, clean same-row sampling columns.
# Weapon panels instead use the clean, already-open panel on source frame 2488.
LAYOUT = {
    'status_commands.name': ([70, 120, 113, 134], [72, 121], [115, 146]),
    'status_commands.spirit': ([14, 178, 37, 192], [15, 179], [58, 65]),
    'status_commands.prana': ([72, 178, 102, 192], [74, 179], [146, 150]),
    'status_commands.move': ([270, 144, 299, 160], [273, 146], [270, 272]),
    'status_commands.trust': ([270, 160, 299, 176], [273, 162], [270, 272]),
    'status_commands.abilities': ([269, 176, 299, 192], [270, 178], [270, 272]),
    'unit_commands.attack': ([270, 162, 299, 178], [271, 164], [270, 272]),
    'unit_commands.wait': ([270, 178, 299, 192], [273, 179], [270, 272]),
    'weapon_list.weapon': ([79, 24, 118, 40], [80, 26], None),
    'weapon_list.power': ([192, 24, 219, 40], [194, 26], None),
    'weapon_list.range': ([231, 24, 259, 40], [233, 26], None),
    'weapon_list.accuracy': ([272, 24, 299, 40], [274, 26], None),
    'weapon_list.weapon_name': ([38, 41, 133, 58], [40, 43], None),
    'weapon_list.ammo': ([23, 120, 65, 136], [24, 122], None),
    'weapon_list.spirit_required': ([167, 120, 226, 136], [169, 122], None),
    'weapon_list.prana_cost': ([167, 136, 226, 152], [169, 138], None),
    'battle_preview.name': ([70, 0, 113, 14], [72, 1], [115, 146]),
    'battle_preview.spirit_left': ([14, 56, 37, 72], [15, 58], [59, 68]),
    'battle_preview.hit_rate_left': ([78, 56, 115, 72], [80, 58], [59, 68]),
    'battle_preview.spirit_right': ([168, 56, 190, 72], [169, 58], [212, 226]),
    'battle_preview.hit_rate_right': ([231, 56, 270, 72], [233, 58], [212, 226]),
    'battle_preview.weapon_left': ([14, 86, 153, 103], [16, 89], [125, 145]),
    'battle_preview.weapon_right': ([168, 86, 306, 103], [170, 89], [276, 298]),
    'battle_preview.cut_in': ([14, 119, 56, 135], [16, 121], [72, 76]),
    'battle_preview.height_difference': ([239, 119, 279, 135], [241, 121], [279, 283]),
}
COMPACT = {'weapon_list.accuracy': ('Acc.', 'Standard abbreviation for Accuracy in the fixed column.'),
           'weapon_list.spirit_required': ('Spirit Req.', 'Compact label retains the required Spirit stat; full term remains in en.'),
           'battle_preview.height_difference': ('Ht. Diff.', 'Standard Height Difference abbreviation; preserve the adjacent signed value.')}


def apply_ui(frame, frame_number, recipe):
    before = np.asarray(frame).copy()
    result = frame.copy()
    allowed = np.zeros((192, 320), dtype=bool)
    active = [r for r in recipe['rows'] if r['start_frame'] <= frame_number < r['end_frame_exclusive']]
    clean = None
    for row in active:
        x0, y0, x1, y1 = row['replace_rect']
        allowed[y0:y1, x0:x1] = True
        if row['background']['mode'] == 'clean_source_panel':
            if clean is None:
                clean = Image.open(ROOT / row['background']['file']).convert('RGB')
            result.paste(clean.crop((x0, y0, x1, y1)), (x0, y0))
        else:
            lo, hi = row['background']['sample_x']
            stripe = np.median(before[y0:y1, lo:hi], axis=1).astype('uint8')
            patch = np.repeat(stripe[:, None, :], x1 - x0, axis=1)
            result.paste(Image.fromarray(patch), (x0, y0))
        ink = mask(row['display_en'], 2)
        x, y = row['text_origin']
        result.paste('white', (x, y, x + ink.width, y + ink.height), ink)
        for move in row.get('icon_moves', []):
            box = move['source_rect']
            destination = tuple(move['destination'])
            result.paste(frame.crop(box), destination)
            xx, yy = destination
            allowed[yy:yy + box[3] - box[1], xx:xx + box[2] - box[0]] = True
    after = np.asarray(result)
    assert np.array_equal(before[~allowed], after[~allowed]), ('UI edits outside declared rectangles', frame_number)
    return result, active, allowed


def prepare():
    drafts = ui_drafts()
    index = json.loads((FRAMES / 'index.json').read_text('utf-8'))
    by_frame = {r['index']: r for r in index['frames']}
    assert len(by_frame) == 326
    clean = FRAMES / 'frame-02488.png'
    rows = []
    for draft in drafts['rows']:
        key = '.'.join(draft['id'].split('.')[-2:])
        rect, origin, samples = LAYOUT[key]
        group = key.split('.')[0]
        start, end = INTERVALS[group]
        text, decision = COMPACT.get(key, (draft['en'], 'Full English term retained at one uniform font scale.'))
        ink = mask(text, 2)
        assert rect[0] <= origin[0] and origin[0] + ink.width <= rect[2], (key, text, ink.width)
        assert rect[1] <= origin[1] and origin[1] + ink.height <= rect[3], (key, ink.height)
        background = {'mode': 'clean_source_panel', 'frame': 2488, 'file': str(clean.relative_to(ROOT)).replace('\\', '/'),
                      'sha256': digest(clean.read_bytes())} if samples is None else {'mode': 'same_row_median', 'sample_x': samples}
        boundaries = [by_frame[n] for n in (start - 1, start, end - 1, end)]
        row = {**draft, 'display_en': text, 'layout_decision': decision, 'replace_rect': rect,
               'initial_candidate_box': draft['candidate_box'], 'candidate_box': rect,
               'x': rect[0], 'y': rect[1], 'width': rect[2] - rect[0], 'height': rect[3] - rect[1],
               'initial_full_term_width_fit': draft['width_fit_candidate'], 'width_fit_candidate': True,
               'text_origin': origin, 'font_denominator': 2, 'font_cell_height': 12,
               'measured_width': ink.width, 'width_fit': True,
               'start_frame': start, 'end_frame_exclusive': end,
               'timing': 'All UI-present frames and transition boundaries visually inspected in consecutive source contact sheets',
               'boundary_evidence': [{'frame': f['index'], 'file': f['file'], 'pts': f['pts'],
                                      'sha256': digest((ROOT / f['file']).read_bytes())} for f in boundaries],
               'geometry_status': 'Pixel-reviewed erase bounds exclude neighboring values, borders, portraits, arrows and HP bars',
               'background': background, 'reinsertion': 'offline movie overlay; not yet in game'}
        if key == 'weapon_list.weapon_name':
            row['icon_moves'] = [{'source_rect': [109, 47, 118, 56], 'destination': [121, 47],
                                  'reason': 'Move the original small P attribute marker right of the longer English name; source pixels retained.'}]
        rows.append(row)
    assert len(rows) == len(LAYOUT) == 25
    return {'format': 1, 'movie': 'MOV072.SFD', 'source_sha256': index['source_sha256'],
            'status': 'Timed UI overlay candidate; native playback and whole-movie review pending',
            'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'), 'font_sha256': digest(ATLAS.read_bytes()),
            'source_dimensions': [320, 192], 'intervals': INTERVALS, 'rows': rows,
            'full_terms_preserved_in_en': True, 'source_panel_clean_frame': 2488,
            'protected': drafts['preserve'] + ['Original ON state, signed Spirit/height values, accuracy values and small weapon attribute marker'],
            'limits': ['Movie text is a lossy 320x192 recording; source-level game UI translation remains a separate component',
                       'Same-row background reconstruction replaces only declared text rectangles',
                       'Source and native playback timing, English caption reading speed and two title sequences remain review items'],
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    recipe = prepare()
    counts = Counter()
    results = {}
    for n in range(2310, 2636):
        source = Image.open(FRAMES / f'frame-{n:05d}.png').convert('RGB')
        target, active, _ = apply_ui(source, n, recipe)
        for row in active:
            counts[row['id']] += 1
        if n in (2400, 2475, 2490, 2565):
            results[n] = (source, target)
    assert all(counts[r['id']] == r['end_frame_exclusive'] - r['start_frame'] for r in recipe['rows'])
    proof = {'source_frames_checked': 326, 'UI_present_frames': 134, 'label_frame_edits': sum(counts.values()),
             'label_counts': dict(counts), 'outside_declared_rectangles': 'exact before encoding',
             'compacted_terms': len(COMPACT), 'individual_glyph_stretching': False, 'game_build_changed': False}
    print(json.dumps(proof, indent=2))
    if not args.write:
        print('DRY RUN: all frame/fit checks completed; no files written')
        return
    RECIPE.write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
    (ROOT / 'work/ui/movies/MOV072/timed-layout.json').write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    for n, (source, target) in results.items():
        target.save(OUT / f'frame-{n:05d}.png')
        sheet = Image.new('RGB', (640, 810), '#30333a')
        draw = ImageDraw.Draw(sheet)
        draw.text((4, 4), f'MOV072 f{n}: source above / English below; uniform 2x preview', fill='white')
        sheet.paste(source.resize((640, 384), Image.Resampling.NEAREST), (0, 22))
        sheet.paste(target.resize((640, 384), Image.Resampling.NEAREST), (0, 422))
        sheet.save(OUT / f'comparison-{n:05d}.png')
    (OUT / 'validation.json').write_text(json.dumps(proof, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
