"""Prepare the user's selected original-logo plus English-subtitle treatment.

Default dry run. Separate source-indexed intervals for the opening and demo;
all source RGB pixels outside the subtitle strokes remain unchanged.
"""
import argparse
from functools import lru_cache
import json

import numpy as np
from PIL import Image, ImageDraw

from build_bitmap_font import ROOT, ATLAS, digest
from build_chapter_cards import strip
from preview_movie_title_treatments import subtitle

SPEC = {
    'MOV055.SFD': ('work/ui/asset-audit/movies/MOV055/frames-240-420', 349, 409, 4, 4),
    'MOV072.SFD': ('work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083', 1489, 1537, 4, 12),
}


def recipe_path(movie):
    return ROOT / 'work/translation/en/movies' / (movie[:6] + '-moving-title.en.json')


def preview_dir(movie):
    return ROOT / 'work/ui/movies' / movie[:6] / 'moving-title-subtitle'


@lru_cache(maxsize=1)
def edit_mask():
    ink = strip('SEIREIKI RAYBLADE')
    layer = Image.new('L', (320, 192))
    x = (320 - ink.width) // 2
    layer.paste(ink, (x + 1, 168))
    # Use max, not paste, to keep the union of foreground and shadow.
    a = np.asarray(layer).copy()
    b = np.zeros((192, 320), np.uint8)
    b[167:191, x:x + ink.width] = np.asarray(ink)
    return np.maximum(a, b) != 0


def apply_moving(frame, number, recipe):
    start, end = recipe['start_frame'], recipe['end_frame_exclusive']
    if not start <= number < end:
        return frame, False
    opacity = min(1., (number - start + 1) / recipe['fade_in_frames'],
                  (end - number) / recipe['fade_out_frames'])
    target = Image.blend(frame, subtitle(frame), opacity)
    assert np.array_equal(np.asarray(frame)[~edit_mask()], np.asarray(target)[~edit_mask()])
    return target, True


def prepare(movie):
    folder, start, end, fade_in, fade_out = SPEC[movie]
    index_path = ROOT / folder / 'index.json'
    index = json.loads(index_path.read_text('utf-8'))
    frames = {r['index']: r for r in index['frames']}
    witnesses = sorted({start, start + 1, start + fade_in - 1, start + 11,
                        375 if movie == 'MOV055.SFD' else 1515,
                        end - fade_out - 1, end - fade_out, end - 2, end - 1})
    return {'format': 1, 'id': f'movie.{movie[:6]}.moving-title.subtitle', 'movie': movie,
            'en': 'SEIREIKI RAYBLADE', 'treatment': 'A — Original artwork + English subtitle',
            'selection': 'Explicit user reply received 2026-10-23; keep original Japanese logo artwork',
            'source_sha256': index['source_sha256'], 'source_index': str(index_path.relative_to(ROOT)).replace('\\', '/'),
            'source_index_sha256': digest(index_path.read_bytes()),
            'start_frame': start, 'end_frame_exclusive': end,
            'fade_in_frames': fade_in, 'fade_out_frames': fade_out,
            'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'), 'font_sha256': digest(ATLAS.read_bytes()),
            'font_scale': 'Uniform source scale, consistent with selected static treatment A',
            'subtitle_origin_y': 167, 'output_dimensions': [320, 192],
            'edit_scope': 'Only English foreground/shadow strokes below row 167; no opaque plaque or background reconstruction',
            'witnesses': [{'frame': n, 'file': frames[n]['file'], 'pts': frames[n]['pts'],
                           'sha256': digest((ROOT / frames[n]['file']).read_bytes())} for n in witnesses],
            'boundary_evidence': [frames[n] for n in (start - 1, start, end - 1, end)],
            'remaining': ['Full-motion/design review and native movie playback/sync/skip/loop/return'],
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    prepared = []
    for movie in SPEC:
        recipe = prepare(movie)
        folder = ROOT / SPEC[movie][0]
        previews = []
        for n in range(recipe['start_frame'] - 1, recipe['end_frame_exclusive'] + 1):
            source = Image.open(folder / f'frame-{n:05d}.png').convert('RGB')
            target, active = apply_moving(source, n, recipe)
            assert active == (recipe['start_frame'] <= n < recipe['end_frame_exclusive'])
            if not active:
                assert source.tobytes() == target.tobytes()
            if n in [r['frame'] for r in recipe['witnesses']]:
                previews.append((n, source, target))
            if n == (375 if movie == 'MOV055.SFD' else 1515):
                assert target.tobytes() == subtitle(source).tobytes(), 'Selected static treatment changed'
        print(movie, recipe['start_frame'], recipe['end_frame_exclusive'], len(previews),
              'witnesses; original artwork outside subtitle strokes exact', flush=True)
        prepared.append((movie, recipe, previews))
    if not args.write:
        print('DRY RUN: no recipe or previews written')
        return
    for movie, recipe, previews in prepared:
        recipe_path(movie).write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
        out = preview_dir(movie)
        out.mkdir(parents=True, exist_ok=True)
        pages = []
        for i, (n, source, target) in enumerate(previews):
            target.save(out / f'frame-{n:05d}.png')
            if i % 4 == 0:
                pages.append(Image.new('RGB', (1280, 440), '#30333a'))
            x = i % 4 * 320
            page = pages[-1]
            page.paste(source, (x, 25))
            page.paste(target, (x, 231))
            ImageDraw.Draw(page).text((x + 3, 4), f'{movie} f{n} - original above / selected A below', fill='white')
        for i, page in enumerate(pages):
            page.save(out / f'comparison-{i:02d}.png')


if __name__ == '__main__':
    main()
