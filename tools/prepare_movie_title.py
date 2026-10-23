"""Build English ending-title artwork and a source-timed MOV072 replacement.

Dry run by default. Supplied Latin contours use uniform scaling. This rebuilds
only the plain-background ending title; the moving-art titles remain pending.
"""
import argparse
from functools import lru_cache
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from build_bitmap_font import ROOT, ATLAS, digest
from build_chapter_cards import strip


FRAMES = ROOT / 'work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083'
OUT = ROOT / 'work/ui/movies/MOV072/english-title'
RECIPE = ROOT / 'work/translation/en/movies/MOV072-ending-title.en.json'
WITNESSES = (2961, 2965, 2969, 2980, 3000, 3045, 3065, 3083)


@lru_cache(maxsize=1)
def artwork():
    canvas = Image.new('RGBA', (320, 192))
    for text, scale, top, palette in [('SEIREIKI', 1, 28, 'gold'), ('RAYBLADE', 3, 64, 'silver')]:
        source = strip(text)
        ink = source.resize((source.width * scale, source.height * scale), Image.Resampling.BILINEAR)
        assert ink.width <= 290
        layer = Image.new('L', canvas.size)
        left = (320 - ink.width) // 2
        layer.paste(ink, (left, top))
        outline = layer.filter(ImageFilter.MaxFilter(3))
        glow = outline.filter(ImageFilter.GaussianBlur(7))
        blue = Image.new('RGBA', canvas.size, (30, 50, 255, 0))
        blue.putalpha(glow.point(lambda v: round(v * .8)))
        canvas = Image.alpha_composite(canvas, blue)
        rim = Image.new('RGBA', canvas.size, (210, 235, 255, 0))
        rim.putalpha(outline)
        canvas = Image.alpha_composite(canvas, rim)
        ys = np.arange(192)[:, None]
        phase = np.clip((ys - top) / ink.height, 0, 1)
        stops = [(0, (255, 250, 208)), (.45, (171, 119, 28)), (.5, (255, 237, 151)), (1, (163, 111, 14))] if palette == 'gold' else [
            (0, (249, 254, 255)), (.45, (135, 162, 190)), (.5, (242, 250, 255)), (1, (70, 103, 151))]
        rgb = np.zeros((192, 320, 3), dtype='uint8')
        for channel in range(3):
            rgb[:, :, channel] = np.interp(phase[:, 0], [p for p, _ in stops], [c[channel] for _, c in stops])[:, None]
        metallic = Image.fromarray(rgb).convert('RGBA')
        metallic.putalpha(layer)
        canvas = Image.alpha_composite(canvas, metallic)
    return canvas


def apply_title(frame, frame_number, recipe):
    if not recipe['start_frame'] <= frame_number < recipe['end_frame_exclusive']:
        return frame, False
    n = frame_number - recipe['start_frame']
    factor = 1 + max(0, 1 - n / 10) * 1.1
    base = artwork()
    w, h = round(base.width * factor), round(base.height * factor)
    enlarged = base.resize((w, h), Image.Resampling.BILINEAR)
    target = Image.new('RGBA', (320, 192), 'black')
    target.alpha_composite(enlarged, ((320 - w) // 2, (192 - h) // 2))
    target = target.convert('RGB')
    # The source ending has a neutral flash/background then a black fade.
    # Estimate that source envelope only; no moving artwork is reconstructed.
    mode = frame.getpixel((0, 191))
    assert max(mode) - min(mode) <= 4, (frame_number, mode)
    flash = sum(mode) / (3 * 255)
    if flash > 0:
        target = Image.blend(target, Image.new('RGB', target.size, 'white'), flash)
    if frame_number >= 3039:
        reference = fade_reference()
        current = np.asarray(frame).astype('float32')
        gain = float(np.clip(np.sum(reference * current) / np.sum(reference * reference), 0, 1))
        target = Image.fromarray(np.rint(np.asarray(target).astype('float32') * gain).astype('uint8'))
    return target, True


@lru_cache(maxsize=1)
def fade_reference():
    return np.asarray(Image.open(FRAMES / 'frame-03000.png').convert('RGB')).astype('float32')


def prepare():
    index = json.loads((FRAMES / 'index.json').read_text('utf-8'))
    by_frame = {row['index']: row for row in index['frames']}
    assert len(by_frame) == 361 and all(n in by_frame for n in WITNESSES)
    boundaries = []
    for n in (2960, 2961, 3083):
        f = by_frame[n]
        boundaries.append({'frame': n, 'pts': f['pts'], 'file': f['file'], 'sha256': digest((ROOT / f['file']).read_bytes())})
    return {'format': 1, 'id': 'movie.MOV072.title.ending', 'movie': 'MOV072.SFD',
            'en': 'Seireiki Rayblade', 'display_lines': ['SEIREIKI', 'RAYBLADE'], 'status': 'artwork/animation draft',
            'source_sha256': index['source_sha256'], 'source_dimensions': [320, 192],
            'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'), 'font_sha256': digest(ATLAS.read_bytes()),
            'uniform_source_scales': {'SEIREIKI': 1, 'RAYBLADE': 3},
            'artwork': str((OUT / 'title.png').relative_to(ROOT)).replace('\\', '/'),
            'artwork_pixel_sha256': digest(artwork().tobytes()),
            'start_frame': 2961, 'end_frame_exclusive': 3084, 'replace_rect': [0, 0, 320, 192],
            'boundary_evidence': boundaries, 'witness_frames': list(WITNESSES),
            'animation': 'Uniform 2.1x-to-1x zoom over first 10 frames; source bottom-left flash envelope; least-squares source-template fade from frame 3039',
            'background_sample': [0, 191],
            'scope': 'Plain-background ending only. Rebuilt English graphics, not a translated original 3D mesh.',
            'remaining': ['Original moving-art title in MOV072 frames 1489..1536',
                          'Original initial 3D logo in MOV072 frames 1417..1448',
                          'Corresponding title sequence found in opening movie MOV055',
                          'Animation/design/full-motion review and native playback'],
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    recipe = prepare()
    previews = []
    for n in range(2960, 3084):
        source = Image.open(FRAMES / f'frame-{n:05d}.png').convert('RGB')
        target, active = apply_title(source, n, recipe)
        assert active == (n >= 2961)
        if not active:
            assert source.tobytes() == target.tobytes()
        if n in WITNESSES:
            previews.append((n, source, target))
    report = {'title': recipe['en'], 'dimensions': list(artwork().size), 'animation_frames': 123,
              'witnesses': list(WITNESSES), 'font': recipe['font'],
              'uniform_source_scales': recipe['uniform_source_scales'],
              'moving_artwork_changed': False, 'game_build_changed': False,
              'remaining_title_sequences': recipe['remaining']}
    print(json.dumps(report, indent=2))
    if not args.write:
        print('DRY RUN: prepared and validated 123 ending frames; no files written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    artwork().save(OUT / 'title.png')
    RECIPE.write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
    pages = []
    for i, (n, source, target) in enumerate(previews):
        target.save(OUT / f'frame-{n:05d}.png')
        if i % 4 == 0:
            pages.append(Image.new('RGB', (1280, 440), '#30333a'))
        sheet = pages[-1]
        x = i % 4 * 320
        sheet.paste(source, (x, 25))
        sheet.paste(target, (x, 231))
        draw = ImageDraw.Draw(sheet)
        draw.text((x + 3, 4), f'Ending title f{n}: source above / English below', fill='white')
    for i, sheet in enumerate(pages):
        sheet.save(OUT / f'comparison-{i:02d}.png')
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
