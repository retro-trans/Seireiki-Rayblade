"""Record bounded title-background recovery and unselected artwork options."""
import argparse
import json

import numpy as np
from PIL import Image

from build_bitmap_font import ROOT, digest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    folder = ROOT / 'work/ui/movies/MOV072/background-recovery'
    raw = (folder / 'analysis.json').read_bytes()
    analysis = json.loads(raw)
    assert analysis['opencv_version'] == '5.0.0'
    assert len(analysis['targets']) == 6 and len(analysis['source_frames']) == 25
    frames = ROOT / 'work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083'
    for n, sha in analysis['source_witness_sha256'].items():
        assert digest((frames / f'frame-{int(n):05d}.png').read_bytes()) == sha
    summaries = []
    for row in analysis['targets']:
        n = row['target_frame']
        source = np.asarray(Image.open(frames / f'frame-{n:05d}.png').convert('RGB'))
        estimate = np.asarray(Image.open(folder / f'background-estimate-{n:05d}.png').convert('RGB'))
        mask = np.asarray(Image.open(folder / f'mask-{n:05d}.png').convert('L')) != 0
        provenance = np.load(folder / f'provenance-{n:05d}.npy', allow_pickle=False)
        assert provenance.shape == (192, 320)
        assert set(np.unique(provenance)) <= set(analysis['source_frames']) | {-1}
        assert np.count_nonzero(provenance >= 0) == row['source_estimate_pixels']
        assert np.count_nonzero(mask) == row['mask_pixels']
        assert np.array_equal(source[~mask], estimate[~mask])
        unresolved = mask & (provenance < 0)
        assert np.all(estimate[unresolved] == (255, 0, 255))
        assert np.count_nonzero(unresolved) == row['unresolved_pixels']
        summaries.append({key: row[key] for key in ('target_frame', 'mask_pixels', 'source_estimate_pixels',
                                                   'unresolved_pixels', 'source_estimate_fraction', 'accepted_registrations')})
    options_file = ROOT / 'work/ui/movies/title-treatment-options/options.json'
    options = json.loads(options_file.read_text('utf-8'))
    assert len(options['comparisons']) == 2
    for row in options['comparisons']:
        assert digest((ROOT / row['source_file']).read_bytes()) == row['source_sha256']
        assert digest((ROOT / row['comparison']).read_bytes()) == row['sha256']
    best = max(r['source_estimate_fraction'] for r in summaries)
    assert best < .5
    doc = {'status': 'Source-frame recovery is incomplete on tested witnesses; moving-title artwork treatment awaiting user preference',
           'analysis': str((folder / 'analysis.json').relative_to(ROOT)).replace('\\', '/'), 'analysis_sha256': digest(raw),
           'methods': ['SIFT ratio correspondences', 'Forward/backward Lucas-Kanade background tracking',
                       'Affine RANSAC with held-out geometric errors', 'Visible-region robust per-channel color fit'],
           'coverage': summaries, 'best_estimated_mask_fraction': best,
           'acceptance_scope': 'Accepted warps estimate some hidden pixels; they do not prove those pixels equal the hidden original artwork',
           'visual_review': 'Both diagnostic sheets and both static treatment comparisons inspected',
           'no_game_movie_edits': True,
           'treatment_options': options,
           'user_preference': 'pending; no original-logo/subtitle or opaque-plaque treatment selected',
           'limits': analysis['limits'],
           'next_work': ['Resolve the moving-title artwork treatment', 'Finish remaining translation/review and native testing'],
           'story_library_draft_credit': 0}
    print(f'Verified six diagnostic witnesses: best source estimate covers {best:.1%} of exclusion mask; unresolved pixels remain explicit. Two unselected treatment comparisons ready.')
    if not args.write:
        print('DRY RUN: no documentation changed')
        return
    def save(path, data):
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')
    save(ROOT / 'docs/movie-title-background.json', doc)
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status['moving_title_artwork'] = doc
    movie_path = ROOT / 'docs/movie-text-audit.json'
    movie = json.loads(movie_path.read_text('utf-8'))
    movie['moving_title_artwork'] = doc
    save(movie_path, movie)
    status['movie_text_audit'] = movie
    save(status_path, status)


if __name__ == '__main__':
    main()
