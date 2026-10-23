"""Compare title-sequence source frames; do not assume a fixed movie offset.

Dry run by default. Thumbnail matches locate shared footage, not exact frame
equivalence or a replacement-time map. Japanese title pixels are local only.
"""
import argparse
import json
import numpy as np
from PIL import Image
from build_bitmap_font import ROOT, digest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    opening = ROOT / 'work/ui/asset-audit/movies/MOV055/frames-240-420'
    demo = ROOT / 'work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083'
    refs = list(range(1360, 1557))
    def thumbnail(path):
        return np.asarray(Image.open(path).convert('RGB').resize((32, 20), Image.Resampling.BOX), dtype='float32').reshape(-1)
    bank = np.stack([thumbnail(demo / f'frame-{n:05d}.png') for n in refs])
    matches = []
    for n in range(240, 421):
        image = thumbnail(opening / f'frame-{n:05d}.png')
        errors = np.abs(bank - image).mean(axis=1)
        at = int(errors.argmin())
        matches.append({'opening_frame': n, 'demo_frame': refs[at], 'thumbnail_MAE': round(float(errors[at]), 4),
                        'nonflat_source': float(image.std()) > 20})
    witnesses = [r for r in matches if r['opening_frame'] in (240, 255, 270, 277, 285, 300, 309, 330, 345, 349, 360, 375, 390, 396, 405, 420)]
    report = {'status': 'Shared title footage found in MOV055; title translation remains required',
              'opening_index': str((opening / 'index.json').relative_to(ROOT)).replace('\\', '/'),
              'opening_index_sha256': digest((opening / 'index.json').read_bytes()),
              'demo_index': str((demo / 'index.json').relative_to(ROOT)).replace('\\', '/'),
              'demo_index_sha256': digest((demo / 'index.json').read_bytes()),
              'opening_frames_indexed': 181, 'demo_title_source_frames_indexed': 361,
              'witness_matches': witnesses,
              'matching_scope': '32x20 RGB thumbnail nearest matches locate shared imagery; no exact equivalence, temporal alignment or full-audio review claimed',
              'all_matches': matches, 'game_files_changed': False}
    print(json.dumps({k: v for k, v in report.items() if k != 'all_matches'}, indent=2))
    if not args.write:
        print('DRY RUN: no files written')
        return
    (ROOT / 'docs/movie-title-sources.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
