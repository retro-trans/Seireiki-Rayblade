"""Encode the full MOV055 opening with the 32-frame English intro-title stage.

Dry run by default. The later title over moving art remains Japanese. Original
audio is preserved separately for native muxing; MP4 audio is a preview copy.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image

from audit_sfd_container import inspect, digest
from build_bitmap_font import ROOT
from prepare_movie_intro_title import SPEC, apply_intro, prepare, recipe_path
from prepare_movie_moving_title import (SPEC as MOVING_SPEC, apply_moving, prepare as prepare_moving,
                                        recipe_path as moving_recipe_path, preview_dir as moving_preview_dir)
from render_movie_captions import checked, read_frame


MOVIE = 'MOV055.SFD'
SOURCE = ROOT / 'work/source/movies' / MOVIE


def render(out, include_moving_title=False):
    recipe = prepare(MOVIE)
    recipe_file = recipe_path(MOVIE)
    assert recipe == json.loads(recipe_file.read_text('utf-8'))
    moving = prepare_moving(MOVIE) if include_moving_title else None
    if moving:
        assert moving == json.loads(moving_recipe_path(MOVIE).read_text('utf-8'))
    source = SOURCE.read_bytes()
    assert digest(source) == recipe['source_sha256']
    container, _, streams = inspect(source)
    total_frames = container['metadata']['video_frames']
    assert total_frames == 1840
    assert not out.exists(), 'Refuse to overwrite existing movie work product'
    out.mkdir(parents=True)
    video, audio, preview = out / 'MOV055-title.m1v', out / 'MOV055-original.sfa', out / 'MOV055-title-preview.mp4'
    audio.write_bytes(streams[0xc0])
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    count = 0
    active_frames = 0
    witnesses = []
    moving_count, moving_witnesses = 0, []
    with (out / 'decoder.log').open('wb') as decerr, (out / 'encoder.log').open('wb') as encerr:
        decoder = subprocess.Popen([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(SOURCE), '-map', '0:v:0', '-an',
                                    '-vf', 'setpts=N*1001/(30000*TB)', '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24',
                                    '-f', 'rawvideo', '-'], stdout=subprocess.PIPE, stderr=decerr)
        encoder = subprocess.Popen([ffmpeg, '-hide_banner', '-v', 'warning', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                    '-s', '320x192', '-framerate', '30000/1001', '-i', 'pipe:0', '-an',
                                    '-c:v', 'mpeg1video', '-b:v', '2200k', '-maxrate', '2458k', '-bufsize', '819200',
                                    '-g', '24', '-bf', '1', '-threads', '1', '-pix_fmt', 'yuv420p', '-f', 'mpeg1video',
                                    '-n', str(video)], stdin=subprocess.PIPE, stderr=encerr)
        try:
            while True:
                raw = read_frame(decoder.stdout, 320 * 192 * 3)
                if not raw:
                    break
                assert len(raw) == 320 * 192 * 3
                frame = Image.frombytes('RGB', (320, 192), raw)
                target, active = apply_intro(frame, count, recipe)
                if active:
                    indexed = Image.open(ROOT / SPEC[MOVIE][0] / f'frame-{count:05d}.png').convert('RGB')
                    assert indexed.tobytes() == raw
                    active_frames += 1
                    if count in [r['frame'] for r in recipe['witnesses']]:
                        expected = Image.open(ROOT / f'work/ui/movies/MOV055/english-intro-title/frame-{count:05d}.png').convert('RGB')
                        assert target.tobytes() == expected.tobytes()
                        witnesses.append(count)
                        target.save(out / f'intro-{count:05d}.png')
                    raw = target.tobytes()
                else:
                    assert target.tobytes() == raw
                if moving:
                    frame = Image.frombytes('RGB', (320, 192), raw)
                    moving_frame, moving_active = apply_moving(frame, count, moving)
                    if moving_active:
                        assert not active
                        indexed = Image.open(ROOT / MOVING_SPEC[MOVIE][0] / f'frame-{count:05d}.png').convert('RGB')
                        assert indexed.tobytes() == raw
                        moving_count += 1
                        if count in [r['frame'] for r in moving['witnesses']]:
                            expected = Image.open(moving_preview_dir(MOVIE) / f'frame-{count:05d}.png').convert('RGB')
                            assert moving_frame.tobytes() == expected.tobytes()
                            moving_witnesses.append(count)
                            moving_frame.save(out / f'moving-{count:05d}.png')
                        raw = moving_frame.tobytes()
                encoder.stdin.write(raw)
                count += 1
                if count % 600 == 0:
                    print('Opening:', count, 'frames encoded', flush=True)
            encoder.stdin.close()
            assert decoder.wait() == 0 and encoder.wait() == 0
        finally:
            decoder.stdout.close()
            if not encoder.stdin.closed:
                encoder.stdin.close()
            for process in (decoder, encoder):
                if process.poll() is None:
                    process.terminate()
                process.wait()
    assert count == 1840 and active_frames == 32 and len(witnesses) == 8
    if moving:
        assert moving_count == moving['end_frame_exclusive'] - moving['start_frame'] == 60
        assert moving_witnesses == [r['frame'] for r in moving['witnesses']]
    assert not (out / 'decoder.log').read_bytes()
    checked([ffmpeg, '-hide_banner', '-v', 'warning', '-r', '30000/1001', '-i', str(video), '-i', str(audio),
             '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast',
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-n', str(preview)], out / 'preview-encode.log')
    probe = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(video)]))['streams'][0]
    assert probe['codec_name'] == 'mpeg1video' and int(probe['nb_read_frames']) == 1840
    for file, name in ((video, 'video'), (preview, 'preview')):
        checked([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(file), '-f', 'null', '-'], out / f'{name}-decode.log')
        assert not (out / f'{name}-decode.log').read_bytes()
    assert digest(SOURCE.read_bytes()) == recipe['source_sha256']
    assert audio.read_bytes() == streams[0xc0]
    report = {'status': 'Opening English intro-title candidate encoded; moving-art title and native playback pending',
              'movie': MOVIE, 'source_sha256': recipe['source_sha256'], 'frame_count': count,
              'native_video': {'path': str(video.relative_to(ROOT)).replace('\\', '/'), 'sha256': digest(video.read_bytes()),
                               'bytes': video.stat().st_size, 'codec': 'mpeg1video', 'dimensions': [320, 192], 'frames': count},
              'original_audio': {'path': str(audio.relative_to(ROOT)).replace('\\', '/'), 'sha256': digest(audio.read_bytes()),
                                 'bytes': audio.stat().st_size, 'preserved_exactly': True},
              'watchable_preview': {'path': str(preview.relative_to(ROOT)).replace('\\', '/'), 'sha256': digest(preview.read_bytes()),
                                     'audio': 'AAC review copy; original ADX retained for native candidate'},
              'intro_title': {'recipe': str(recipe_file.relative_to(ROOT)).replace('\\', '/'), 'recipe_sha256': digest(recipe_file.read_bytes()),
                               'frames': 32, 'source_index_matches': 32, 'exact_static_witnesses': witnesses, 'moving_artwork_changed': False},
              'full_decode_errors': 0, 'outside_title_interval_before_encoding': 'exact source RGB frames',
              'game_build_changed': False, 'remaining': recipe['remaining'] + ['Lossy encoding quality and full audio/content review'],
              'story_library_draft_credit': 0}
    if moving:
        path = moving_recipe_path(MOVIE)
        report.update(status='Opening English intro and selected moving-title subtitle encoded; native playback pending',
                      outside_title_interval_before_encoding='Exact original RGB outside intro replacement and moving-subtitle strokes',
                      remaining=['Native playback/sync/skip/loop/return', 'Lossy encoding quality and full motion/audio/content review'])
        report['moving_title'] = {'recipe': str(path.relative_to(ROOT)).replace('\\', '/'),
                                  'recipe_sha256': digest(path.read_bytes()), 'frames': moving_count,
                                  'source_index_matches': moving_count, 'exact_static_witnesses': moving_witnesses,
                                  'treatment': 'A — Original artwork + English subtitle',
                                  'unmodified_outside_subtitle_strokes_before_encoding': True}
    (out / 'render-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print(json.dumps(report, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'work/output/movie-drafts/MOV055/intro-title-01')
    ap.add_argument('--include-moving-title', action='store_true')
    args = ap.parse_args()
    if not args.write:
        recipe = prepare(MOVIE)
        assert recipe == json.loads(recipe_path(MOVIE).read_text('utf-8'))
        print('DRY RUN: 1840 opening frames, 32 English title frames, original ADX retained. Later moving-art title remains Japanese.')
        print('Output:', args.output_dir.resolve())
        if args.include_moving_title:
            moving = prepare_moving(MOVIE)
            assert moving == json.loads(moving_recipe_path(MOVIE).read_text('utf-8'))
            print('Selected treatment A adds 60 moving-title subtitle frames; original artwork retained.')
        return
    render(args.output_dir.resolve(), args.include_moving_title)


if __name__ == '__main__':
    main()
