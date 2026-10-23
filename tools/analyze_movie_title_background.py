"""Test source-frame recovery behind MOV072's moving-art Japanese title.

Dry run by default. Output is a diagnostic estimate, never game artwork. Warp
acceptance uses held-out feature error and visible-background photometric fit;
unseen pixels stay magenta. No generative or spatial inpainting is performed.

API references: https://docs.opencv.org/5.0/main_modules/video_track.html
https://github.com/opencv/opencv/blob/5.x/doc/tutorials/features/feature_homography/feature_homography.markdown
"""
import argparse
from functools import lru_cache
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from build_bitmap_font import ROOT, digest

sys.path.insert(0, str(ROOT / 'work/vendor/opencv5'))
import cv2

FRAMES = ROOT / 'work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083'
OUT = ROOT / 'work/ui/movies/MOV072/background-recovery'
TARGETS = (1491, 1499, 1507, 1515, 1523, 1531)
SOURCES = tuple(range(1487, 1537, 2))


@lru_cache(maxsize=100)
def rgb(n):
    return np.asarray(Image.open(FRAMES / f'frame-{n:05d}.png').convert('RGB'))


def edge(image):
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return cv2.Canny(cv2.GaussianBlur(gray, (3, 3), .6), 20, 55)


@lru_cache(maxsize=100)
def title_mask(n):
    if n < 1489:
        return np.zeros((192, 320), dtype='uint8'), {'scale': 0, 'score': None}
    expected = min(1, .2 + ((n - 1489) // 2) * .1)
    template = rgb(3000)
    target_edges = edge(rgb(n))
    best = None
    for scale in np.arange(max(.1, expected - .06), min(1.06, expected + .06) + .001, .01):
        w, h = round(320 * scale), round(192 * scale)
        if w > 320 or h > 192:
            continue
        picture = cv2.resize(template, (w, h), interpolation=cv2.INTER_AREA)
        pattern = edge(picture)
        if np.count_nonzero(pattern) < 10:
            continue
        score = cv2.matchTemplate(target_edges, pattern, cv2.TM_CCORR_NORMED)
        cx, cy = (320 - w) // 2, (192 - h) // 2
        x0, y0 = max(0, cx - 10), max(0, cy - 10)
        x1, y1 = min(score.shape[1], cx + 11), min(score.shape[0], cy + 11)
        _, value, _, pos = cv2.minMaxLoc(score[y0:y1, x0:x1])
        if best is None or value > best[0]:
            best = value, scale, (pos[0] + x0, pos[1] + y0), picture
    assert best is not None
    value, scale, (x, y), picture = best
    # Include silver/gold letters and the blue halo in the exclusion mask.
    # Broad masks are intentional: avoid tracking the logo as scene geometry.
    body = (picture.max(axis=2) > 22).astype('uint8') * 255
    body = cv2.dilate(body, np.ones((5, 5), dtype='uint8'))
    result = np.zeros((192, 320), dtype='uint8')
    result[y:y + body.shape[0], x:x + body.shape[1]] = body
    return result, {'scale': round(float(scale), 3), 'origin': [int(x), int(y)],
                    'edge_match_score': round(float(value), 4), 'excluded_pixels': int(np.count_nonzero(result))}


@lru_cache(maxsize=100)
def features(n):
    gray = cv2.cvtColor(rgb(n), cv2.COLOR_RGB2GRAY)
    gray = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(gray)
    mask = cv2.bitwise_not(title_mask(n)[0])
    mask = cv2.erode(mask, np.ones((5, 5), dtype='uint8'))
    points, descriptors = cv2.SIFT_create(nfeatures=1500, contrastThreshold=.01).detectAndCompute(gray, mask)
    if descriptors is None:
        return [], None
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    keep = [i for i, p in enumerate(points) if distance[min(191, round(p.pt[1])), min(319, round(p.pt[0]))] >= max(4, p.size)]
    return [points[i] for i in keep], descriptors[keep] if keep else None


@lru_cache(maxsize=100)
def tracking_gray(n):
    gray = cv2.cvtColor(rgb(n), cv2.COLOR_RGB2GRAY)
    return cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(gray)


def fit_points(p, q, record):
    record['correspondences'] = len(p)
    if len(p) < 12:
        record['rejection'] = 'fewer than twelve background correspondences'
        return None, record
    hold = np.arange(len(p)) % 3 == 0
    transform, inliers = cv2.estimateAffinePartial2D(p[~hold], q[~hold], method=cv2.RANSAC, ransacReprojThreshold=1.5)
    if transform is None or np.count_nonzero(inliers) < 6:
        record['rejection'] = 'affine RANSAC lacks six inliers'
        return None, record
    predicted = np.column_stack((p[hold], np.ones(np.count_nonzero(hold)))) @ transform.T
    residual = np.linalg.norm(predicted - q[hold], axis=1)
    record.update(inliers=int(np.count_nonzero(inliers)), held_out_points=len(residual),
                  held_out_median_pixels=round(float(np.median(residual)), 4),
                  scale=round(float(np.hypot(transform[0, 0], transform[1, 0])), 4))
    if np.median(residual) > 1.5 or not .25 < record['scale'] < 4:
        record['rejection'] = 'held-out geometric error/scale exceeds bounds'
        return None, record
    record['accepted'] = True
    record['transform'] = transform.tolist()
    return transform, record


@lru_cache(maxsize=2000)
def register_sift(source, target):
    a, da = features(source)
    b, db = features(target)
    record = {'method': 'SIFT ratio matches', 'source': source, 'target': target, 'source_features': len(a), 'target_features': len(b), 'accepted': False}
    if da is None or db is None or len(a) < 8 or len(b) < 8:
        record['rejection'] = 'insufficient uncontaminated background features'
        return None, record
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    matches = [m for m, other in pairs if m.distance < .72 * other.distance]
    record['ratio_matches'] = len(matches)
    p = np.float32([a[m.queryIdx].pt for m in matches])
    q = np.float32([b[m.trainIdx].pt for m in matches])
    return fit_points(p, q, record)


@lru_cache(maxsize=2000)
def register_lk(source, target):
    record = {'method': 'Forward/backward Lucas-Kanade tracks', 'source': source, 'target': target, 'accepted': False}
    mask_a = cv2.erode(cv2.bitwise_not(title_mask(source)[0]), np.ones((21, 21), dtype='uint8'))
    mask_b = cv2.erode(cv2.bitwise_not(title_mask(target)[0]), np.ones((21, 21), dtype='uint8'))
    p = cv2.goodFeaturesToTrack(tracking_gray(source), 500, .003, 4, mask=mask_a, blockSize=5)
    if p is None or len(p) < 12:
        record['rejection'] = 'insufficient background tracking corners'
        return None, record
    settings = {'winSize': (21, 21), 'maxLevel': 3, 'criteria': (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, .01)}
    q, status, _ = cv2.calcOpticalFlowPyrLK(tracking_gray(source), tracking_gray(target), p, None, **settings)
    back, reverse, _ = cv2.calcOpticalFlowPyrLK(tracking_gray(target), tracking_gray(source), q, None, **settings)
    p, q, back = p.reshape(-1, 2), q.reshape(-1, 2), back.reshape(-1, 2)
    valid = status[:, 0].astype(bool) & reverse[:, 0].astype(bool)
    valid &= np.linalg.norm(back - p, axis=1) < .5
    inside = (q[:, 0] >= 0) & (q[:, 0] < 320) & (q[:, 1] >= 0) & (q[:, 1] < 192)
    valid &= inside
    qi = np.clip(np.rint(q).astype(int), [0, 0], [319, 191])
    valid &= mask_b[qi[:, 1], qi[:, 0]] == 255
    record.update(initial_corners=len(p), forward_backward_tracks=int(np.count_nonzero(valid)))
    return fit_points(p[valid], q[valid], record)


def register(source, target):
    options = [register_sift(source, target), register_lk(source, target)]
    accepted = [option for option in options if option[0] is not None]
    if accepted:
        selected = min(accepted, key=lambda option: option[1]['held_out_median_pixels'])
        return selected[0], dict(selected[1])
    return None, {'source': source, 'target': target, 'accepted': False,
                  'rejection': 'Both background registration methods rejected', 'method_results': [r for _, r in options]}


def recover(target):
    picture = rgb(target)
    hole, fit = title_mask(target)
    visible = hole == 0
    estimate = picture.copy()
    estimate[~visible] = (255, 0, 255)
    quality = np.full((192, 320), np.inf, dtype='float32')
    provenance = np.full((192, 320), -1, dtype='int16')
    records = []
    for source in SOURCES:
        if source == target:
            continue
        transform, row = register(source, target)
        records.append(row)
        if transform is None:
            continue
        donor = cv2.warpAffine(rgb(source), transform, (320, 192), flags=cv2.INTER_LINEAR)
        donor_visible = cv2.warpAffine(cv2.bitwise_not(title_mask(source)[0]), transform, (320, 192), flags=cv2.INTER_NEAREST) == 255
        overlap = visible & donor_visible
        if np.count_nonzero(overlap) < 3000:
            row.update(accepted=False, rejection='too little jointly visible background')
            continue
        # Robust per-channel affine color fit compensates the source flash.
        corrected = np.zeros_like(donor, dtype='float32')
        residuals = []
        gains = []
        for channel in range(3):
            x, y = donor[:, :, channel][overlap].astype('float32'), picture[:, :, channel][overlap].astype('float32')
            keep = np.ones(len(x), dtype=bool)
            for _ in range(3):
                model = np.column_stack((x[keep], np.ones(np.count_nonzero(keep))))
                gain, bias = np.linalg.lstsq(model, y[keep], rcond=None)[0]
                errors = np.abs(gain * x + bias - y)
                cutoff = max(3, float(np.median(errors)) * 2.5)
                keep = errors <= cutoff
            corrected[:, :, channel] = donor[:, :, channel] * gain + bias
            residuals.append(float(np.median(errors)))
            gains.append(float(gain))
        error = max(residuals)
        row.update(visible_median_channel_errors=residuals, color_gains=gains)
        if error > 8 or any(not .1 < gain < 8 for gain in gains):
            row.update(accepted=False, rejection='visible photometric fit exceeds bounds')
            continue
        cost = error + row['held_out_median_pixels'] * 2 + abs(source - target) * .03
        fill = ~visible & donor_visible & (cost < quality)
        estimate[fill] = np.clip(np.rint(corrected[fill]), 0, 255).astype('uint8')
        provenance[fill] = source
        quality[fill] = cost
        row['contributed_pixels'] = int(np.count_nonzero(fill))
    assert np.array_equal(estimate[visible], picture[visible])
    total = int(np.count_nonzero(hole))
    recovered = int(np.count_nonzero(provenance >= 0))
    report = {'target_frame': target, 'logo_mask_fit': fit, 'mask_pixels': total,
              'source_estimate_pixels': recovered, 'unresolved_pixels': total - recovered,
              'source_estimate_fraction': round(recovered / total, 5),
              'accepted_registrations': sum(r['accepted'] for r in records), 'registrations': records,
              'outside_mask_exact': True,
              'scope': 'Warped/source-color-fit estimates, not proven hidden original pixels; unresolved holes magenta; not game-ready'}
    return estimate, provenance, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    cv2.setRNGSeed(0)
    cv2.setNumThreads(1)
    results = []
    for target in TARGETS:
        result = recover(target)
        results.append((target, *result))
        record = result[-1]
        print(f'f{target}: {record["source_estimate_pixels"]}/{record["mask_pixels"]} mask pixels estimated; {record["accepted_registrations"]} accepted registrations', flush=True)
    if not args.write:
        print('DRY RUN: no files written; no game/movie modifications')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    pages = []
    for i, (target, estimate, provenance, report) in enumerate(results):
        Image.fromarray(estimate).save(OUT / f'background-estimate-{target:05d}.png')
        Image.fromarray(title_mask(target)[0]).save(OUT / f'mask-{target:05d}.png')
        np.save(OUT / f'provenance-{target:05d}.npy', provenance)
        if i % 3 == 0:
            pages.append(Image.new('RGB', (960, 650), '#30333a'))
        sheet = pages[-1]
        x = i % 3 * 320
        sheet.paste(Image.fromarray(rgb(target)), (x, 25))
        marked = rgb(target).copy()
        marked[title_mask(target)[0] != 0] = (marked[title_mask(target)[0] != 0] // 2 + np.array([120, 0, 0], dtype='uint8'))
        sheet.paste(Image.fromarray(marked), (x, 235))
        sheet.paste(Image.fromarray(estimate), (x, 445))
        ImageDraw.Draw(sheet).text((x + 3, 4), f'f{target}: source / exclusion mask / estimate', fill='white')
    for i, sheet in enumerate(pages):
        sheet.save(OUT / f'comparison-{i:02d}.png')
    doc = {'status': 'Diagnostic temporal source-frame recovery; not movie artwork or native insertion',
           'opencv_version': cv2.__version__, 'package': 'opencv-python-headless==5.0.0.93 in ignored work/vendor/opencv5',
           'source_frames': list(SOURCES), 'targets': [r[-1] for r in results],
           'source_witness_sha256': {str(n): digest((FRAMES / f'frame-{n:05d}.png').read_bytes()) for n in set(SOURCES) | set(TARGETS) | {3000}},
           'limits': ['Template exclusion masks need pixel review', 'Visible-pixel registration does not prove accuracy behind opaque lettering',
                      'An affine scene model may fail for a rotating/deforming three-dimensional mech',
                      'No guessed/spatial/generative fills; unresolved pixels remain magenta', 'No game/video changes']}
    (OUT / 'analysis.json').write_text(json.dumps(doc, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
