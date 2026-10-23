"""Render denser, indexed movie frames for manual text review. Dry first.

Select every fifteenth frame plus scene changes. This is discovery coverage,
not an assertion that text cannot appear between selected frames.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from fractions import Fraction

from PIL import Image, ImageDraw
from build_font_patch import ROOT


def interval_contacts(details, dest):
    frames = [f for f in details['frames'] if f['index'] % 15 == 0]
    pages = []
    for start in range(0, len(frames), 12):
        sheet = Image.new('RGB', (1280, 672), '#30333a')
        draw = ImageDraw.Draw(sheet)
        draw.text((4, 3), details['movie'] + ' - every 15th frame (not continuous-frame review)', fill='white')
        for slot, frame in enumerate(frames[start:start + 12]):
            x, y = slot % 4 * 320, 24 + slot // 4 * 216
            sheet.paste(Image.open(ROOT / frame['file']), (x, y))
            draw.text((x + 2, y + 194), f'f{frame["index"]} / {frame["time"]:.3f}s', fill='white')
        filename = f'interval-contact-{start // 12:02d}.png'
        sheet.save(dest / filename)
        pages.append(str((dest / filename).relative_to(ROOT)).replace('\\', '/'))
    return pages


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--member', action='append', required=True)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--contacts-only', action='store_true', help='Use existing indexed PNGs without decoding again')
    ap.add_argument('--frame-range', action='append', default=[], help='Inclusive decoded frame interval, e.g. 1530:1930')
    args = ap.parse_args()
    ranges = [tuple(map(int, item.split(':'))) for item in args.frame_range]
    assert all(len(r) == 2 and 0 <= r[0] <= r[1] for r in ranges)
    selection = '+'.join(f'between(n\\,{lo}\\,{hi})' for lo, hi in ranges) if ranges else r'not(mod(n\,15))+gt(scene\,0.18)'
    assert all(re.fullmatch(r'MOV\d{3}\.SFD', n) for n in args.member)
    report = json.loads((ROOT / 'work/ui/asset-audit/movies/movie-index.json').read_text('utf-8'))
    selected = [r for r in report['entries'] if r['path'] in args.member]
    assert len(selected) == len(set(args.member))
    print('Plan:', ', '.join(args.member), ':', ('exact frame intervals ' + str(ranges)) if ranges else 'every 15th frame plus scene-score >0.18', '; manual review still required.', flush=True)
    if not args.write:
        print('DRY RUN: no decoding/output')
        return
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    for row in selected:
        source = ROOT / row['source']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256']
        dest = ROOT / 'work/ui/asset-audit/movies' / source.stem / 'dense'
        if ranges:
            dest = dest.parent / ('frames-' + '_'.join(f'{lo}-{hi}' for lo, hi in ranges))
        if args.contacts_only:
            details = json.loads((dest / 'index.json').read_text('utf-8'))
            assert details['source_sha256'] == row['sha256']
            details['interval_contact_pages'] = interval_contacts(details, dest)
            (dest / 'index.json').write_text(json.dumps(details, indent=2) + '\n', 'utf-8')
            print(source.name, len(details['interval_contact_pages']), 'interval sheets', flush=True)
            continue
        video = next(s for s in row['streams'] if s['codec_type'] == 'video')
        w, h = video['width'], video['height']
        command = [ffmpeg, '-hide_banner', '-loglevel', 'info', '-i', str(source),
                   '-map', '0:v:0', '-an', '-vf', 'showinfo@source,select=' + selection + ',showinfo@selected,setpts=N/(30*TB)',
                   '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
        result = subprocess.run(command, capture_output=True)
        log = result.stderr.decode('utf-8', 'replace')
        assert result.returncode == 0, log[-2000:]
        pattern = r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([\d.e+-]+)'
        before = [tuple(m.groups()) for line in log.splitlines() if '[showinfo@source ' in line
                  for m in [re.search(pattern, line)] if m]
        after = [tuple(m.groups()) for line in log.splitlines() if '[showinfo@selected ' in line
                 for m in [re.search(pattern, line)] if m]
        assert len(before) == row['frame_count'], (len(before), row['frame_count'], log[-1000:])
        by_pts = {int(pts): (int(n), float(t)) for n, pts, t in before}
        assert len(by_pts) == len(before), 'Duplicate input timestamps require explicit matching'
        assert len(result.stdout) == w * h * 3 * len(after)
        rate = Fraction(row['frame_rate'])
        frames = []
        dest.mkdir(parents=True, exist_ok=True)
        for n, (_, pts, time) in enumerate(after):
            index, source_time = by_pts[int(pts)]
            assert source_time == float(time)
            time = source_time - float(before[0][2])
            im = Image.frombytes('RGB', (w, h), result.stdout[n * w * h * 3:(n + 1) * w * h * 3])
            filename = f'frame-{index:05d}.png'
            im.save(dest / filename)
            frames.append({'index': index, 'time': time, 'pts': int(pts), 'file': str((dest / filename).relative_to(ROOT)).replace('\\', '/')})
        assert len({f['index'] for f in frames}) == len(frames)
        if ranges:
            assert {n for lo, hi in ranges for n in range(lo, hi + 1)} == {f['index'] for f in frames}
        else:
            assert {n for n in range(row['frame_count']) if n % 15 == 0} <= {f['index'] for f in frames}
        pages = []
        for start in range(0, len(frames), 12):
            # Native pixels, four columns. Labels retain exact frame/time links.
            sheet = Image.new('RGB', (1280, 3 * 216 + 24), '#30333a')
            draw = ImageDraw.Draw(sheet)
            draw.text((4, 3), source.name + ' - dense discovery samples; not every frame', fill='white')
            for slot, frame in enumerate(frames[start:start + 12]):
                x, y = slot % 4 * 320, 24 + slot // 4 * 216
                im = Image.open(ROOT / frame['file'])
                sheet.paste(im, (x, y))
                draw.text((x + 2, y + 194), f'f{frame["index"]} / {frame["time"]:.3f}s', fill='white')
            filename = f'contact-{start // 12:02d}.png'
            sheet.save(dest / filename)
            pages.append(str((dest / filename).relative_to(ROOT)).replace('\\', '/'))
        details = {'movie': source.name, 'source_sha256': row['sha256'],
                   'total_video_frames': row['frame_count'], 'frame_rate': str(rate),
                   'selected_frames': len(frames), 'selection': 'Exact inclusive frame intervals ' + str(ranges) if ranges else 'Every fifteenth frame plus scene score >0.18',
                   'frames': frames, 'contact_pages': pages,
                   'review': 'pending manual review',
                   'index_validation': 'Exact decoded input n and pts matched to selected output; no frame-rate-derived indices',
                   'limits': ['Text may occur between selected frames', 'No audio transcription or movie modification']}
        details['interval_contact_pages'] = interval_contacts(details, dest)
        if ranges:
            crops = []
            for start in range(0, len(frames), 50):
                sheet = Image.new('RGB', (1300, 780), '#30333a')
                draw = ImageDraw.Draw(sheet)
                draw.text((4, 2), source.name + ' - consecutive caption crops x60..319, y134..191', fill='white')
                for slot, frame in enumerate(frames[start:start + 50]):
                    x, y = slot % 5 * 260, 18 + slot // 5 * 76
                    sheet.paste(Image.open(ROOT / frame['file']).crop((60, 134, 320, 192)), (x, y))
                    draw.text((x + 2, y + 59), f'f{frame["index"]} / {frame["time"]:.3f}s', fill='white')
                name = f'caption-contact-{start // 50:02d}.png'
                sheet.save(dest / name)
                crops.append(str((dest / name).relative_to(ROOT)).replace('\\', '/'))
            details['caption_contact_pages'] = crops
        (dest / 'index.json').write_text(json.dumps(details, indent=2) + '\n', 'utf-8')
        print(source.name, len(frames), 'indexed frames,', len(pages), 'sheets', flush=True)


if __name__ == '__main__':
    main()
