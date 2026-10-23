"""Map MOV072's captured UI to English terms and candidate native bounds.

Geometry/timing and actual movie integration remain review items. Dry first.
"""
import argparse
import json
import re

from build_bitmap_font import ROOT, digest
from prepare_movie_translation import mask


def prepare():
    root = ROOT / 'work/ui/asset-audit/movies/MOV072/dense'
    names = {r['id']: r for r in json.loads((ROOT / 'work/translation/en/ui/names.json').read_text('utf-8'))}
    rows = []
    groups = [
        ('status_commands', 2400, [
            ('name', 'Touya', None, [71, 121, 113, 134]),
            ('spirit', 'Spirit', 'names.g00.003', [15, 178, 44, 192]),
            ('prana', 'Prana', 'names.g00.003', [73, 178, 102, 192]),
            ('move', 'Move', 'names.g00.009', [272, 144, 297, 160]),
            ('trust', 'Trust', 'names.g00.011', [272, 160, 297, 176]),
            ('abilities', 'Abilities', 'names.g00.016', [272, 176, 297, 192]),
        ]),
        ('unit_commands', 2475, [
            ('attack', 'Attack', 'names.g00.010', [273, 163, 297, 178]),
            ('wait', 'Wait', 'names.g00.017', [273, 178, 297, 192]),
        ]),
        ('weapon_list', 2490, [
            ('weapon', 'Weapon', 'names.g00.096', [69, 24, 118, 40]),
            ('power', 'Power', 'names.g00.096', [188, 24, 219, 40]),
            ('range', 'Range', 'names.g00.096', [224, 24, 255, 40]),
            ('accuracy', 'Accuracy', 'names.g00.096', [268, 24, 299, 40]),
            ('weapon_name', 'Mighty Sword Zeulear', 'names.g04.001', [38, 41, 158, 57]),
            ('ammo', 'Ammo', 'names.g00.098', [23, 120, 65, 136]),
            ('spirit_required', 'Required Fighting Spirit', 'names.g00.097', [168, 120, 230, 136]),
            ('prana_cost', 'Prana Cost', 'names.g00.097', [168, 136, 230, 152]),
        ]),
        ('battle_preview', 2565, [
            ('name', 'Touya', None, [71, 0, 113, 14]),
            ('spirit_left', 'Spirit', 'names.g00.160', [14, 55, 43, 72]),
            ('hit_rate_left', 'Hit Rate', 'names.g01.049', [78, 55, 119, 72]),
            ('spirit_right', 'Spirit', 'names.g00.160', [170, 55, 200, 72]),
            ('hit_rate_right', 'Hit Rate', 'names.g01.049', [231, 55, 272, 72]),
            ('weapon_left', 'Mighty Sword Zeulear', 'names.g04.001', [15, 87, 152, 103]),
            ('weapon_right', 'Divine Sword Daifozon', 'names.g04.002', [168, 87, 305, 103]),
            ('cut_in', 'Cut-In', 'names.g00.166', [15, 119, 61, 135]),
            ('height_difference', 'Height Difference', 'names.g00.162', [240, 119, 283, 135]),
        ]),
    ]
    for group, frame, entries in groups:
        path = root / f'frame-{frame:05d}.png'
        assert path.is_file()
        for key, en, reference, box in entries:
            ref = names[reference] if reference else None
            assert not ref or ref['en']
            assert not re.search(r'[\u3040-\u30ff\u3400-\u9fff]', en)
            x0, y0, x1, y1 = box
            assert 0 <= x0 < x1 <= 320 and 0 <= y0 < y1 <= 192
            width = mask(en, 2).width
            rows.append({
                'id': f'movie.MOV072.ui.{group}.{key}', 'en': en, 'status': 'draft',
                'reference_id': reference or 'character.001',
                'reference_source_sha256': ref['source_sha256'] if ref else None,
                'witness_frame': frame, 'witness_file': str(path.relative_to(ROOT)).replace('\\', '/'),
                'witness_sha256': digest(path.read_bytes()), 'candidate_box': box,
                'x': x0, 'y': y0, 'width': x1 - x0, 'height': y1 - y0,
                'geometry_status': 'Candidate native-frame bounds; exact erase mask, numbers and borders need pixel review',
                'twelve_pixel_font_width': width,
                'width_fit_candidate': width <= x1 - x0 - 2,
                'timing': 'pending frame-complete segment boundaries', 'reinsertion': 'not inserted',
            })
    return {'format': 1, 'movie': 'MOV072.SFD', 'source_dimensions': [320, 192],
            'status': 'Captured UI label drafts mapped; geometry/timing and movie reinsertion pending',
            'rows': rows,
            'preserve': ['Original HP/level/experience and numeric values', 'Original question-mark concealment labels',
                         'Attack icons, health bars and selection indicators'],
            'pending': ['Measured compact-label or window layout for overflowing full terms',
                        'Erase masks and exact frame intervals', 'Native movie encoding/insertion and playback'],
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    data = prepare()
    print('Mapped', len(data['rows']), 'captured UI label occurrences;',
          sum(not r['width_fit_candidate'] for r in data['rows']), 'need width/layout review. No game change.')
    if not args.write:
        print('DRY RUN: no files written')
        return
    p = ROOT / 'work/translation/en/movies/MOV072-ui.en.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')
    p = ROOT / 'work/ui/movies/MOV072/layout.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
