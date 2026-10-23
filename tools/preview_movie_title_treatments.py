"""Preview two explicit treatments for title text over moving artwork.

Dry run by default. These are design comparisons, not an implicit selection
or movie replacement: original logo plus English subtitle, or opaque English
plaque covering the source logo area. No background pixels are invented.
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageDraw

from build_bitmap_font import ROOT, digest
from build_chapter_cards import strip
from prepare_movie_title import artwork


def subtitle(source):
    ink = strip('SEIREIKI RAYBLADE')
    assert ink.width <= 300 and ink.height == 24
    result = source.copy()
    x, y = (320 - ink.width) // 2, 167
    result.paste('black', (x + 1, y + 1, x + 1 + ink.width, y + 1 + ink.height), ink)
    result.paste('white', (x, y, x + ink.width, y + ink.height), ink)
    assert np.array_equal(np.asarray(result)[:167], np.asarray(source)[:167])
    return result


def plaque(source):
    box = (14, 16, 306, 171)
    result = source.copy().convert('RGBA')
    draw = ImageDraw.Draw(result)
    draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=(4, 7, 18), outline=(105, 132, 171), width=1)
    logo = artwork().resize((256, 154), Image.Resampling.BILINEAR)
    result.alpha_composite(logo, ((320 - logo.width) // 2, box[1]))
    result = result.convert('RGB')
    allowed = np.zeros((192, 320), dtype=bool)
    allowed[box[1]:box[3], box[0]:box[2]] = True
    assert np.array_equal(np.asarray(result)[~allowed], np.asarray(source)[~allowed])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    refs = [('MOV055', 375, 'work/ui/asset-audit/movies/MOV055/frames-240-420/frame-00375.png'),
            ('MOV072', 1515, 'work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083/frame-01515.png')]
    prepared = []
    for movie, n, path in refs:
        source = Image.open(ROOT / path).convert('RGB')
        prepared.append((movie, n, path, source, subtitle(source), plaque(source)))
    print('Prepared two explicit title treatments for both movie witnesses; source outside declared edit areas exact. No selection or movie change.')
    if not args.write:
        print('DRY RUN: no files written')
        return
    out = ROOT / 'work/ui/movies/title-treatment-options'
    out.mkdir(parents=True, exist_ok=True)
    proof = []
    for movie, n, path, source, a, b in prepared:
        sheet = Image.new('RGB', (960, 240), '#20242d')
        draw = ImageDraw.Draw(sheet)
        for x, title, note, frame in [
            (0, 'Original', 'Japanese logo covers moving artwork', source),
            (320, 'A: Original logo + English subtitle', 'Keeps the logo art; English title below', a),
            (640, 'B: English plaque', 'Removes Japanese; covers part of mech art', b),
        ]:
            draw.text((x + 5, 4), title, fill='white')
            sheet.paste(frame, (x, 24))
            draw.text((x + 5, 220), note, fill='#d2d8e3')
        output = out / f'{movie}-comparison.png'
        sheet.save(output)
        proof.append({'movie': movie, 'frame': n, 'source_file': path, 'source_sha256': digest((ROOT / path).read_bytes()),
                      'comparison': str(output.relative_to(ROOT)).replace('\\', '/'), 'sha256': digest(output.read_bytes())})
    report = {'status': 'Unselected artwork-treatment comparisons; no movie/game change', 'comparisons': proof,
              'A': 'Original Japanese title artwork retained, English title added below at one common source font scale',
              'B': 'English wordmark on an opaque plaque, covering the original logo and underlying mech pixels in its rectangle',
              'scope': 'Two static design witnesses; timing/animation and final treatment not selected',
              'game_build_changed': False, 'native_playback': 'pending'}
    (out / 'options.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
