"""Prepare shared English plain-background title animation for MOV055/MOV072.

Dry run by default. Rebuilds the early zoom/logo stage, leaving the original
flash and moving-mech title stage intact. No original 3D mesh claim.
"""
import argparse
from functools import lru_cache
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from build_bitmap_font import ROOT, digest
from prepare_movie_title import artwork


SPEC = {
    'MOV055.SFD': ('work/ui/asset-audit/movies/MOV055/frames-240-420', 277, 309),
    'MOV072.SFD': ('work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083', 1417, 1449),
}
OFFSETS = (0, 4, 8, 12, 16, 22, 26, 31)


def recipe_path(movie):
    return ROOT / 'work/translation/en/movies' / (movie[:6] + '-intro-title.en.json')


@lru_cache(maxsize=1)
def rays():
    image = Image.new('RGB', (320, 192))
    draw = ImageDraw.Draw(image)
    for i in range(128):
        a = i * 2 * math.pi / 128
        x, y = 170 + round(math.cos(a) * 380), 110 + round(math.sin(a) * 380)
        shade = 20 + (i * 47 % 110)
        draw.line((170, 110, x, y), fill=(shade * 2 // 3, shade, shade // 3), width=1 + i % 2)
    return image.filter(ImageFilter.GaussianBlur(.6))


def apply_intro(frame, frame_number, recipe):
    if not recipe['start_frame'] <= frame_number < recipe['end_frame_exclusive']:
        return frame, False
    n = frame_number - recipe['start_frame']
    progress = min(1, n / 22)
    factor = 1 + 2 * (1 - progress) ** 2
    base = artwork()
    w, h = round(320 * factor), round(192 * factor)
    assert max(w, h) <= 1024
    enlarged = base.resize((w, h), Image.Resampling.BILINEAR)
    # A shared white/blue silhouette replaces the source's white 3D letters.
    alpha = enlarged.getchannel('A')
    white = Image.new('RGBA', enlarged.size, (230, 246, 255, 255))
    white.putalpha(alpha)
    backdrop = Image.new('RGB', (320, 192), (0, 0, 0))
    if n >= 24:
        backdrop = Image.blend(backdrop, rays(), min(1, (n - 23) / 8))
    target = backdrop.convert('RGBA')
    target.alpha_composite(white, ((320 - w) // 2, (192 - h) // 2))
    # Ease in after the source neutral flash, then meet its outgoing burst.
    target = Image.blend(backdrop, target.convert('RGB'), min(1, (n + 1) / 4))
    if n >= 28:
        yy, xx = np.indices((192, 320), dtype='float32')
        radius = (n - 27) * 14
        bloom = np.clip(1 - np.hypot(xx - 170, yy - 110) / radius, 0, 1)
        src = np.asarray(target).astype('float32')
        target = Image.fromarray(np.rint(src * (1 - bloom[:, :, None]) + 255 * bloom[:, :, None]).astype('uint8'))
    return target, True


def prepare(movie):
    folder, start, end = SPEC[movie]
    folder = ROOT / folder
    index = json.loads((folder / 'index.json').read_text('utf-8'))
    frames = {r['index']: r for r in index['frames']}
    witnesses = []
    for offset in OFFSETS:
        source = frames[start + offset]
        witnesses.append({'frame': source['index'], 'file': source['file'], 'pts': source['pts'],
                          'sha256': digest((ROOT / source['file']).read_bytes())})
    boundaries = [frames[n] for n in (start - 1, start, end - 1, end)]
    assert end - start == 32
    return {'format': 1, 'id': f'movie.{movie[:6]}.title.intro', 'movie': movie,
            'en': 'Seireiki Rayblade', 'status': 'Rebuilt plain-background English intro title candidate',
            'source_sha256': index['source_sha256'], 'source_dimensions': [320, 192],
            'artwork_pixel_sha256': digest(artwork().tobytes()),
            'start_frame': start, 'end_frame_exclusive': end, 'replace_rect': [0, 0, 320, 192],
            'witnesses': witnesses, 'boundary_evidence': boundaries,
            'animation': 'Uniform 3x-to-1x zoom, four-frame fade-in, white/blue silhouette, radial rays and final bloom',
            'font_scale': 'Same source contour proportions and baseline as the English ending wordmark',
            'maximum_intermediate_dimensions': [960, 576], 'output_dimensions': [320, 192],
            'scope': 'Entire plain-background graphic sequence is rebuilt; original 3D geometry and lighting are not reconstructed',
            'remaining': ['Title over moving mech artwork later in this movie remains Japanese',
                          'Full-motion/design and native playback checks'], 'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    data = []
    for movie in SPEC:
        recipe = prepare(movie)
        folder = ROOT / SPEC[movie][0]
        previews = []
        for n in range(recipe['start_frame'] - 1, recipe['end_frame_exclusive'] + 1):
            source = Image.open(folder / f'frame-{n:05d}.png').convert('RGB')
            target, active = apply_intro(source, n, recipe)
            assert active == (recipe['start_frame'] <= n < recipe['end_frame_exclusive'])
            if not active:
                assert source.tobytes() == target.tobytes()
            if n in [r['frame'] for r in recipe['witnesses']]:
                previews.append((n, source, target))
        print(movie, '32 rebuilt frames;', len(previews), 'witnesses; source flash/moving artwork outside interval unchanged')
        data.append((movie, recipe, previews))
    if not args.write:
        print('DRY RUN: no files written')
        return
    for movie, recipe, previews in data:
        recipe_path(movie).write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
        out = ROOT / 'work/ui/movies' / movie[:6] / 'english-intro-title'
        out.mkdir(parents=True, exist_ok=True)
        pages = []
        for i, (n, source, target) in enumerate(previews):
            target.save(out / f'frame-{n:05d}.png')
            if i % 4 == 0:
                pages.append(Image.new('RGB', (1280, 440), '#30333a'))
            page = pages[-1]
            x = i % 4 * 320
            page.paste(source, (x, 25))
            page.paste(target, (x, 231))
            ImageDraw.Draw(page).text((x + 3, 4), f'{movie} f{n} - source above / English below', fill='white')
        for i, page in enumerate(pages):
            page.save(out / f'comparison-{i:02d}.png')


if __name__ == '__main__':
    main()
