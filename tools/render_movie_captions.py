"""Render the 13 timed MOV072 captions into a complete MPEG-1 video draft.

Dry run by default. This is a movie work product, not an SFD/game build. Keep
the original audio elementary stream exact for subsequent native muxing.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from audit_sfd_container import digest, inspect
from build_bitmap_font import ROOT
from prepare_movie_translation import FONT_DENOMINATOR, mask, prepare
from prepare_movie_ui_layout import FRAMES as UI_FRAMES, RECIPE as UI_RECIPE, apply_ui, prepare as prepare_ui
from prepare_movie_title import FRAMES as TITLE_FRAMES, OUT as TITLE_PREVIEWS, RECIPE as TITLE_RECIPE, apply_title, prepare as prepare_title
from prepare_movie_intro_title import SPEC as INTRO_SPEC, apply_intro, prepare as prepare_intro, recipe_path as intro_path
from prepare_movie_moving_title import (SPEC as MOVING_SPEC, apply_moving, prepare as prepare_moving,
                                        recipe_path as moving_recipe_path, preview_dir as moving_preview_dir)


SOURCE = ROOT / 'work/source/movies/MOV072.SFD'
DEST = ROOT / 'work/output/movie-drafts/MOV072'


def checked(command, log):
    with log.open('wb') as stderr:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=stderr)


def read_frame(pipe, length):
    data = bytearray()
    while len(data) < length:
        chunk = pipe.read(length - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def render(include_ui=False, include_ending_title=False, include_intro_title=False, include_moving_title=False):
    recipe, _, previews = prepare()
    saved = json.loads((ROOT / 'work/translation/en/movies/MOV072.en.json').read_text('utf-8'))
    assert saved == recipe, 'Saved captions differ from source-linked recipe'
    ui_recipe = prepare_ui() if include_ui else None
    if include_ui:
        assert ui_recipe == json.loads(UI_RECIPE.read_text('utf-8')), 'Saved UI layout differs from prepared source'
    title_recipe = prepare_title() if include_ending_title else None
    if title_recipe:
        assert title_recipe == json.loads(TITLE_RECIPE.read_text('utf-8')), 'Saved title differs from prepared source'
    intro_recipe = prepare_intro('MOV072.SFD') if include_intro_title else None
    if intro_recipe:
        assert intro_recipe == json.loads(intro_path('MOV072.SFD').read_text('utf-8'))
    moving = prepare_moving('MOV072.SFD') if include_moving_title else None
    if moving:
        assert moving == json.loads(moving_recipe_path('MOV072.SFD').read_text('utf-8'))
    original = SOURCE.read_bytes()
    assert digest(original) == recipe['source_sha256']
    container, _, streams = inspect(original)
    assert container['metadata']['video_frames'] == 3084
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    DEST.mkdir(parents=True, exist_ok=True)
    video = DEST / 'MOV072-captions.m1v'
    audio = DEST / 'MOV072-original.sfa'
    preview = DEST / 'MOV072-captions-preview.mp4'
    for path in (video, audio, preview, DEST / 'render-report.json'):
        assert not path.exists(), f'Refuse to overwrite existing work product: {path}'
    audio.write_bytes(streams[0xc0])
    decoder_log = DEST / 'decoder.log'
    encoder_log = DEST / 'encoder.log'
    counts = Counter()
    witness_matches = []
    events = []
    ui_counts = Counter()
    ui_witnesses = []
    title_count = 0
    title_witnesses = []
    intro_count = 0
    intro_witnesses = []
    moving_count, moving_witnesses = 0, []
    frame_number = 0
    with decoder_log.open('wb') as decerr, encoder_log.open('wb') as encerr:
        decoder = subprocess.Popen([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(SOURCE),
                                    '-map', '0:v:0', '-an', '-vf', 'setpts=N*1001/(30000*TB)', '-fps_mode', 'passthrough',
                                    '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'], stdout=subprocess.PIPE, stderr=decerr)
        encoder = subprocess.Popen([ffmpeg, '-hide_banner', '-loglevel', 'warning', '-f', 'rawvideo',
                                    '-pix_fmt', 'rgb24', '-s', '320x192', '-framerate', recipe['frame_rate'],
                                    '-i', 'pipe:0', '-an', '-c:v', 'mpeg1video', '-b:v', '2200k',
                                    '-maxrate', '2458k', '-bufsize', '819200', '-g', '24', '-bf', '1', '-threads', '1',
                                    '-pix_fmt', 'yuv420p', '-f', 'mpeg1video', '-n', str(video)],
                                   stdin=subprocess.PIPE, stderr=encerr)
        try:
            last_id = None
            while True:
                raw = read_frame(decoder.stdout, 320 * 192 * 3)
                if not raw:
                    break
                assert len(raw) == 320 * 192 * 3
                cue = next((c for c in recipe['cues'] if c['start_frame'] <= frame_number < c['end_frame_exclusive']), None)
                current_id = cue['id'] if cue else None
                if current_id != last_id:
                    events.append({'frame': frame_number, 'cue': current_id})
                    last_id = current_id
                if cue:
                    frame = Image.frombytes('RGB', (320, 192), raw)
                    before = np.asarray(frame).copy()
                    x0, y0, x1, y1 = cue['replace_rect']
                    ImageDraw.Draw(frame).rectangle((x0, y0, x1 - 1, y1 - 1), fill='black')
                    x, y = cue['text_origin']
                    for i, line in enumerate(cue['wrapped_lines']):
                        ink = mask(line, FONT_DENOMINATOR)
                        frame.paste('white', (x, y + i * cue['line_step'], x + ink.width,
                                             y + i * cue['line_step'] + ink.height), ink)
                    after = np.asarray(frame)
                    changed = np.any(before != after, axis=2)
                    changed[y0:y1, x0:x1] = False
                    assert not changed.any(), ('Pixel changed outside caption rectangle', frame_number)
                    counts[current_id] += 1
                    if frame_number == cue['witness_frame']:
                        expected = next(target for item, _, target in previews if item['id'] == current_id)
                        assert frame.tobytes() == expected.tobytes(), ('Witness differs', current_id)
                        witness_matches.append(current_id)
                        frame.save(DEST / (current_id.split('.')[-1] + '.png'))
                    raw = frame.tobytes()
                if ui_recipe:
                    original_frame = Image.frombytes('RGB', (320, 192), raw)
                    ui_frame, active_ui, _ = apply_ui(original_frame, frame_number, ui_recipe)
                    if active_ui:
                        # These intervals do not overlap dialogue captions.
                        assert cue is None
                        indexed_source = Image.open(UI_FRAMES / f'frame-{frame_number:05d}.png').convert('RGB')
                        assert indexed_source.tobytes() == raw, ('UI source-frame index mismatch', frame_number)
                        for row in active_ui:
                            ui_counts[row['id']] += 1
                        if frame_number in (2400, 2475, 2490, 2565):
                            expected = Image.open(ROOT / f'work/ui/movies/MOV072/ui-overlay-drafts/frame-{frame_number:05d}.png').convert('RGB')
                            assert ui_frame.tobytes() == expected.tobytes()
                            ui_witnesses.append(frame_number)
                            ui_frame.save(DEST / f'ui-{frame_number:05d}.png')
                        raw = ui_frame.tobytes()
                if title_recipe:
                    original_frame = Image.frombytes('RGB', (320, 192), raw)
                    title_frame, active_title = apply_title(original_frame, frame_number, title_recipe)
                    if active_title:
                        assert cue is None and not active_ui
                        indexed_source = Image.open(TITLE_FRAMES / f'frame-{frame_number:05d}.png').convert('RGB')
                        assert indexed_source.tobytes() == raw, ('Title source-frame index mismatch', frame_number)
                        title_count += 1
                        if frame_number in title_recipe['witness_frames']:
                            expected = Image.open(TITLE_PREVIEWS / f'frame-{frame_number:05d}.png').convert('RGB')
                            assert title_frame.tobytes() == expected.tobytes()
                            title_witnesses.append(frame_number)
                            title_frame.save(DEST / f'title-{frame_number:05d}.png')
                        raw = title_frame.tobytes()
                if intro_recipe:
                    original_frame = Image.frombytes('RGB', (320, 192), raw)
                    intro_frame, active_intro = apply_intro(original_frame, frame_number, intro_recipe)
                    if active_intro:
                        assert cue is None and not active_ui and not active_title
                        indexed_source = Image.open(ROOT / INTRO_SPEC['MOV072.SFD'][0] / f'frame-{frame_number:05d}.png').convert('RGB')
                        assert indexed_source.tobytes() == raw
                        intro_count += 1
                        if frame_number in [r['frame'] for r in intro_recipe['witnesses']]:
                            expected = Image.open(ROOT / f'work/ui/movies/MOV072/english-intro-title/frame-{frame_number:05d}.png').convert('RGB')
                            assert intro_frame.tobytes() == expected.tobytes()
                            intro_witnesses.append(frame_number)
                            intro_frame.save(DEST / f'intro-{frame_number:05d}.png')
                        raw = intro_frame.tobytes()
                if moving:
                    frame = Image.frombytes('RGB', (320, 192), raw)
                    moving_frame, active_moving = apply_moving(frame, frame_number, moving)
                    if active_moving:
                        assert cue is None and not active_ui and not active_title and not active_intro
                        indexed = Image.open(ROOT / MOVING_SPEC['MOV072.SFD'][0] / f'frame-{frame_number:05d}.png').convert('RGB')
                        assert indexed.tobytes() == raw
                        moving_count += 1
                        if frame_number in [r['frame'] for r in moving['witnesses']]:
                            expected = Image.open(moving_preview_dir('MOV072.SFD') / f'frame-{frame_number:05d}.png').convert('RGB')
                            assert moving_frame.tobytes() == expected.tobytes()
                            moving_witnesses.append(frame_number)
                            moving_frame.save(DEST / f'moving-{frame_number:05d}.png')
                        raw = moving_frame.tobytes()
                encoder.stdin.write(raw)
                frame_number += 1
                if frame_number % 600 == 0:
                    print('Rendered', frame_number, 'frames', flush=True)
            encoder.stdin.close()
            decode_status = decoder.wait()
            encode_status = encoder.wait()
            assert decode_status == 0 and encode_status == 0, (decode_status, encode_status)
        finally:
            decoder.stdout.close()
            if not encoder.stdin.closed:
                encoder.stdin.close()
            for process in (decoder, encoder):
                if process.poll() is None:
                    process.terminate()
                process.wait()
    assert frame_number == 3084
    assert len(witness_matches) == 13
    assert all(counts[c['id']] == c['end_frame_exclusive'] - c['start_frame'] for c in recipe['cues'])
    if ui_recipe:
        assert len(ui_witnesses) == 4
        assert all(ui_counts[r['id']] == r['end_frame_exclusive'] - r['start_frame'] for r in ui_recipe['rows'])
    if title_recipe:
        assert title_count == 123 and len(title_witnesses) == 8
    if intro_recipe:
        assert intro_count == 32 and len(intro_witnesses) == 8
    if moving:
        assert moving_count == moving['end_frame_exclusive'] - moving['start_frame'] == 48
        assert moving_witnesses == [r['frame'] for r in moving['witnesses']]
    assert decoder_log.read_bytes() == b'', 'Source decoder reported an error'
    checked([ffmpeg, '-hide_banner', '-loglevel', 'warning', '-r', recipe['frame_rate'], '-i', str(video),
             '-i', str(audio), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-crf', '16',
             '-preset', 'fast', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-n', str(preview)],
            DEST / 'preview-encode.log')
    probe = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-count_frames', '-show_streams',
                                               '-of', 'json', str(video)]))
    native = probe['streams'][0]
    assert (native['codec_name'], native['width'], native['height'], int(native['nb_read_frames'])) == ('mpeg1video', 320, 192, 3084)
    checked([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(video), '-f', 'null', '-'], DEST / 'video-decode.log')
    assert (DEST / 'video-decode.log').read_bytes() == b''
    checked([ffmpeg, '-hide_banner', '-v', 'error', '-i', str(preview), '-f', 'null', '-'], DEST / 'preview-decode.log')
    assert (DEST / 'preview-decode.log').read_bytes() == b''
    assert digest(SOURCE.read_bytes()) == recipe['source_sha256']
    assert audio.read_bytes() == streams[0xc0]
    report = {'status': 'Complete caption' + ('/UI' if include_ui else '') + '-video draft encoded; not an SFD/game replacement',
              'source_sha256': recipe['source_sha256'], 'recipe_sha256': digest(json.dumps(recipe, sort_keys=True).encode()),
              'frame_count': frame_number, 'captioned_frames': sum(counts.values()),
              'per_cue_frames': dict(counts), 'transitions': events, 'exact_preview_witnesses': witness_matches,
              'unmodified_outside_caption_rectangles_before_encoding': True,
              'native_video': {'path': str(video.relative_to(ROOT)), 'sha256': digest(video.read_bytes()), 'bytes': video.stat().st_size,
                               'codec': native['codec_name'], 'dimensions': [320, 192], 'frames': 3084},
              'original_audio': {'path': str(audio.relative_to(ROOT)), 'sha256': digest(audio.read_bytes()), 'bytes': len(streams[0xc0]),
                                 'preserved_exactly': True},
              'watchable_preview': {'path': str(preview.relative_to(ROOT)), 'sha256': digest(preview.read_bytes()),
                                     'audio': 'AAC preview copy; native original ADX retained separately'},
              'full_decode_errors': 0, 'game_build_changed': False,
              'remaining': [('Two animated Japanese title-logo sequences remain' if include_ui else 'Captured Japanese UI and animated logos remain in this caption-only draft'),
                            'Caption reading speed and complete visual/audio review',
                            'Native Sofdec muxing, insertion and live playback',
                            'MPEG-1 encoding is lossy; pixel preservation assertion applies before encoding only']}
    if ui_recipe:
        report['captured_ui'] = {'recipe': str(UI_RECIPE.relative_to(ROOT)).replace('\\', '/'),
                                 'recipe_sha256': digest(UI_RECIPE.read_bytes()), 'label_count': len(ui_recipe['rows']),
                                 'per_label_frames': dict(ui_counts), 'label_frame_edits': sum(ui_counts.values()),
                                 'UI_present_frames': 134, 'source_index_matches': 134,
                                 'exact_static_witnesses': ui_witnesses,
                                 'unmodified_outside_declared_rectangles_before_encoding': True,
                                 'status': 'Timed English overlays encoded; native playback unverified'}
    if title_recipe:
        report['ending_title'] = {'recipe': str(TITLE_RECIPE.relative_to(ROOT)).replace('\\', '/'),
                                  'recipe_sha256': digest(TITLE_RECIPE.read_bytes()),
                                  'frames': title_count, 'source_index_matches': title_count,
                                  'start_frame': title_recipe['start_frame'], 'end_frame_exclusive': title_recipe['end_frame_exclusive'],
                                  'exact_static_witnesses': title_witnesses, 'moving_artwork_changed': False,
                                  'remaining': title_recipe['remaining']}
        report['status'] = 'Caption/UI/English ending-title video encoded; not an SFD/game replacement'
        report['remaining'][0] = 'Initial 3D/moving-art title remains Japanese; corresponding opening MOV055 title also needs replacement'
    if intro_recipe:
        path = intro_path('MOV072.SFD')
        report['intro_title'] = {'recipe': str(path.relative_to(ROOT)).replace('\\', '/'), 'recipe_sha256': digest(path.read_bytes()),
                                 'frames': intro_count, 'source_index_matches': intro_count,
                                 'exact_static_witnesses': intro_witnesses, 'moving_artwork_changed': False}
        report['remaining'][0] = 'Title over moving mech remains Japanese in MOV072/MOV055; rebuilt intro title needs animation/design review'
        report['status'] = 'English captions/UI/intro/ending-title video candidate encoded; native playback unverified'
    if moving:
        path = moving_recipe_path('MOV072.SFD')
        report['moving_title'] = {'recipe': str(path.relative_to(ROOT)).replace('\\', '/'),
                                  'recipe_sha256': digest(path.read_bytes()), 'frames': moving_count,
                                  'source_index_matches': moving_count, 'exact_static_witnesses': moving_witnesses,
                                  'treatment': 'A — Original artwork + English subtitle',
                                  'unmodified_outside_subtitle_strokes_before_encoding': True}
        report['remaining'][0] = 'Original Japanese moving-title artwork retained by explicit selection A; English subtitle added'
        report['status'] = 'English captions/UI/intro/ending and selected moving-title subtitle encoded; native playback unverified'
    (DEST / 'render-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print(json.dumps(report, indent=2), flush=True)


def main():
    global DEST
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--output-dir', type=Path, default=DEST)
    ap.add_argument('--include-ui', action='store_true', help='Include the reviewed timed English captured-UI layout')
    ap.add_argument('--include-ending-title', action='store_true', help='Include the rebuilt plain-background English ending title')
    ap.add_argument('--include-intro-title', action='store_true', help='Include the rebuilt early plain-background English title')
    ap.add_argument('--include-moving-title', action='store_true', help='Include selected original-logo plus English-subtitle treatment')
    args = ap.parse_args()
    DEST = args.output_dir.resolve()
    assert not args.include_ending_title or args.include_ui, 'Ending-title candidate includes reviewed UI as well'
    assert not args.include_intro_title or args.include_ending_title, 'Intro-title candidate retains the ending title and UI'
    assert not args.include_moving_title or args.include_intro_title, 'Moving-title candidate retains all preceding treatments'
    if not args.write:
        recipe, _, _ = prepare()
        print('DRY RUN: render', len(recipe['cues']), 'timed captions across 3084 frames at 320x192.')
        print('Outputs:', DEST)
        if args.include_ui:
            ui = prepare_ui()
            assert ui == json.loads(UI_RECIPE.read_text('utf-8'))
            print('Also render', len(ui['rows']), 'UI labels across 134 frames; 964 label/frame edits.')
        if args.include_ending_title:
            title = prepare_title()
            assert title == json.loads(TITLE_RECIPE.read_text('utf-8'))
            print('Also render 123 English ending-title frames; initial/moving titles in MOV072 and MOV055 remain pending.')
        if args.include_intro_title:
            intro = prepare_intro('MOV072.SFD')
            assert intro == json.loads(intro_path('MOV072.SFD').read_text('utf-8'))
            print('Also render 32 English intro-title frames; moving-art title remains pending.')
        if args.include_moving_title:
            moving = prepare_moving('MOV072.SFD')
            assert moving == json.loads(moving_recipe_path('MOV072.SFD').read_text('utf-8'))
            print('Selected treatment A adds 48 moving-title subtitle frames; original artwork retained.')
        print('Original SFD/audio and all game builds remain unchanged. Native muxing/UI/logos/readability are pending.')
        return
    render(args.include_ui, args.include_ending_title, args.include_intro_title, args.include_moving_title)


if __name__ == '__main__':
    main()
