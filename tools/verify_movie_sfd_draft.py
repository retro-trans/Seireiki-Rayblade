"""Compare decoded draft SFD/video/audio and produce encoded caption contacts.

Read-only by default. --write runs FFmpeg checks and writes local QA evidence.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw

from audit_sfd_container import digest
from build_bitmap_font import ROOT
from build_movie_sfd_draft import DRAFT


def decode_hashes(ffmpeg, path, kind):
    command = [ffmpeg, '-hide_banner', '-v', 'error', '-i', str(path), '-map', f'0:{kind}:0']
    if kind == 'v':
        command += ['-vf', 'setpts=N*1001/(30000*TB)', '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', '-f', 'framemd5', '-']
    else:
        command += ['-c:a', 'pcm_s16le', '-f', 'hash', '-hash', 'sha256', '-']
    result = subprocess.run(command, capture_output=True, check=True)
    assert result.stderr == b'', result.stderr.decode(errors='replace')
    if kind == 'a':
        return result.stdout.decode().strip()
    return [tuple(line.split(',')[-2:]) for line in result.stdout.decode().splitlines() if line and not line.startswith('#')]


def main():
    global DRAFT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--draft-dir', type=Path, default=DRAFT)
    args = ap.parse_args()
    DRAFT = args.draft_dir.resolve()
    report = json.loads((DRAFT / 'sfd-candidate-report.json').read_text('utf-8'))
    render = json.loads((DRAFT / 'render-report.json').read_text('utf-8'))
    movie = render.get('movie', 'MOV072.SFD')
    recipe = json.loads((ROOT / 'work/translation/en/movies/MOV072.en.json').read_text('utf-8')) if movie == 'MOV072.SFD' else {'cues': []}
    video = ROOT / render['native_video']['path']
    audio = ROOT / render['original_audio']['path']
    candidate = ROOT / report['candidate']
    assert digest(candidate.read_bytes()) == report['candidate_sha256']
    assert digest(video.read_bytes()) == report['video_sha256']
    assert digest(audio.read_bytes()) == report['audio_sha256']
    if not args.write:
        print('DRY RUN: validated input hashes. Would compare all decoded RGB frames/audio PCM and produce indexed encoded witness contact sheets.')
        return
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    direct_frames = decode_hashes(ffmpeg, video, 'v')
    container_frames = decode_hashes(ffmpeg, candidate, 'v')
    assert direct_frames == container_frames and len(direct_frames) == render['frame_count']
    direct_audio = decode_hashes(ffmpeg, audio, 'a')
    container_audio = decode_hashes(ffmpeg, candidate, 'a')
    assert direct_audio == container_audio
    witnesses = {c['witness_frame']: c for c in recipe['cues']}
    if 'captured_ui' in render:
        for n in render['captured_ui']['exact_static_witnesses']:
            witnesses[n] = {'id': f'movie.MOV072.ui.frame-{n:05d}', 'witness_frame': n,
                            'witness_file': f'work/ui/asset-audit/movies/MOV072/frames-2310-2635/frame-{n:05d}.png'}
    if 'ending_title' in render:
        for n in render['ending_title']['exact_static_witnesses']:
            witnesses[n] = {'id': f'movie.MOV072.title.frame-{n:05d}', 'witness_frame': n,
                            'witness_file': f'work/ui/asset-audit/movies/MOV072/frames-1360-1556_2920-3083/frame-{n:05d}.png'}
    if 'intro_title' in render:
        intro = json.loads((ROOT / render['intro_title']['recipe']).read_text('utf-8'))
        assert digest((ROOT / render['intro_title']['recipe']).read_bytes()) == render['intro_title']['recipe_sha256']
        for row in intro['witnesses']:
            n = row['frame']
            witnesses[n] = {'id': f'movie.{movie[:6]}.intro.frame-{n:05d}', 'witness_frame': n, 'witness_file': row['file']}
    if 'moving_title' in render:
        moving = json.loads((ROOT / render['moving_title']['recipe']).read_text('utf-8'))
        assert digest((ROOT / render['moving_title']['recipe']).read_bytes()) == render['moving_title']['recipe_sha256']
        for row in moving['witnesses']:
            n = row['frame']
            witnesses[n] = {'id': f'movie.{movie[:6]}.moving.frame-{n:05d}', 'witness_frame': n, 'witness_file': row['file']}
    ordered = [row for _, row in sorted(witnesses.items())]
    selection = '+'.join(f'eq(n\\,{n})' for n in witnesses)
    result = subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(candidate), '-map', '0:v:0',
                             '-vf', 'select=' + selection + ',setpts=N/(30*TB)', '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                            capture_output=True, check=True)
    assert not result.stderr, result.stderr
    assert len(result.stdout) == len(witnesses) * 320 * 192 * 3
    out = ROOT / 'work/ui/movies' / movie[:6] / 'encoded-caption-review' / DRAFT.name
    out.mkdir(parents=True, exist_ok=True)
    pages = []
    for index, cue in enumerate(ordered):
        start = index * 320 * 192 * 3
        frame = Image.frombytes('RGB', (320, 192), result.stdout[start:start + 320 * 192 * 3])
        frame.save(out / (cue['id'].split('.')[-1] + '.png'))
        if index % 4 == 0:
            pages.append(Image.new('RGB', (1280, 440), '#30333a'))
        sheet = pages[-1]
        x = index % 4 * 320
        sheet.paste(Image.open(ROOT / cue['witness_file']).convert('RGB'), (x, 25))
        sheet.paste(frame, (x, 231))
        draw = ImageDraw.Draw(sheet)
        draw.text((x + 3, 4), f'{cue["id"]} / f{cue["witness_frame"]}', fill='white')
        draw.text((x + 3, 216), 'Decoded SFD candidate; no game build yet', fill='white')
    contacts = []
    for i, page in enumerate(pages):
        path = out / f'comparison-{i:02d}.png'
        page.save(path)
        contacts.append(str(path.relative_to(ROOT)).replace('\\', '/'))
    proof = {'candidate_sha256': report['candidate_sha256'], 'exact_decoded_video_frames': len(direct_frames),
             'decoded_pcm_audio_sha256': direct_audio, 'decoded_pcm_identical_to_original_adx': True,
             'contact_sheets': contacts, 'software_decode_errors': 0,
             'visual_review': 'pending', 'live_game_playback': 'pending',
             'scope': 'Software-decoded pixels/frame order and original decoded audio; no native timing/GPU/runtime proof'}
    proof['witness_frames'] = [r['witness_frame'] for r in ordered]
    proof['captured_UI_witnesses'] = render.get('captured_ui', {}).get('exact_static_witnesses', [])
    proof['ending_title_witnesses'] = render.get('ending_title', {}).get('exact_static_witnesses', [])
    proof['intro_title_witnesses'] = render.get('intro_title', {}).get('exact_static_witnesses', [])
    proof['moving_title_witnesses'] = render.get('moving_title', {}).get('exact_static_witnesses', [])
    (DRAFT / 'decoded-comparison.json').write_text(json.dumps(proof, indent=2) + '\n', 'utf-8')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
