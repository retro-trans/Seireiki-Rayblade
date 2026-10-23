"""Prepare source-linked English MOV072 captions and offline fit previews.

The SFD and the disc are unchanged. A timed draft is not movie reinsertion.
Japanese transcription lives only in ignored work/source, never the .en.json.
"""
import argparse
import hashlib
import json
import re

from PIL import Image, ImageDraw
from build_bitmap_font import ROOT, ATLAS
from build_ui_atlas_patch import mask as array_mask

digest = lambda b: hashlib.sha256(b).hexdigest()
RANGE_DIR = ROOT / 'work/ui/asset-audit/movies/MOV072/frames-1530-1935_2630-2700'
FONT_DENOMINATOR = 2
LINE_STEP = 13


def mask(text, denominator):
    return Image.fromarray(array_mask(text, denominator))


def rows(member, block, first=0, last=None):
    data = json.loads((ROOT / 'work/translation/en/scenario' / (member + '.json')).read_text('utf-8'))
    found = [r for r in data if r['block_id'] == 'scenario.' + member + '.' + block]
    assert found
    return found[first:last]


def fit(text, width):
    words = text.split()
    lines = []
    line = ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if mask(candidate, FONT_DENOMINATOR).width <= width:
            line = candidate
        else:
            assert line and mask(word, FONT_DENOMINATOR).width <= width, word
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    assert ' '.join(lines) == ' '.join(words)
    return lines


def prepare():
    metadata = json.loads((RANGE_DIR / 'index.json').read_text('utf-8'))
    assert metadata['index_validation'].startswith('Exact decoded input n')
    frames = {r['index']: r for r in metadata['frames']}
    source = ROOT / 'work/source/movies/MOV072.SFD'
    assert digest(source.read_bytes()) == metadata['source_sha256']
    variants = json.loads((ROOT / 'work/source/movies/MOV072-variant-transcriptions.json').read_text('utf-8'))
    specifications = [
        (1557, 1615, 1560, rows('s_002', 'o01872'), None, None),
        (1615, 1669, 1620, rows('s_002', 'o018cc', 0, 3), None, None),
        (1669, 1689, 1680, rows('s_002', 'o018cc', 3, 6), None, None),
        (1689, 1709, 1695, rows('s_00a', 'o00b94'), None, None),
        (1709, 1745, 1710, rows('s_00a', 'o00bf4'), None, None),
        (1745, 1781, 1755, rows('s_00a', 'o00c0e'), None, None),
        (1783, 1806, 1800, rows('s_00a', 'o00c53'), None, None),
        (1807, 1825, 1815, rows('s_002', 'o01527'), None, None),
        (1827, 1851, 1830, rows('s_002', 'o01556'), None, None),
        (1853, 1883, 1860, rows('s_002', 'o01568') + rows('s_002', 'o015c4'),
         'Touya: "Well, most people laugh at me like I\'m an idiot when I say that. You\'re only the third person who hasn\'t."',
         'Movie condenses two playable-script commands and omits the alternative disbelieving look. Translate the captured wording separately.'),
        (1883, 1909, 1890, rows('s_002', 'o015ea'),
         'Ai: "Hmm... What\'s the kitty\'s name?"',
         'Movie uses a thoughtful interjection rather than the playable script\'s attention-getting Hey.'),
        (1909, 1927, 1920, rows('s_002', 'o01609'), None, None),
    ]
    battle = json.loads((ROOT / 'work/translation/en/battle/battle.json').read_text('utf-8'))
    b = [r for r in battle if r['span_id'] == 'battle.o2364f' and r['page_index'] == 0]
    assert len(b) == 2
    specifications.append((2649, 2691, 2655, b, None, None))
    cues = []
    transcriptions = []
    previews = []
    for number, (start, end, witness, refs, override, decision) in enumerate(specifications, 1):
        assert all(r['en'] and r['status'] == 'draft' for r in refs)
        en = override or ' '.join(r['en'].strip() for r in refs)
        en = re.sub(r'<[^>]+>', '', en)
        assert not re.search(r'[\u3040-\u30ff\u3400-\u9fff]', en)
        japanese = ''.join(r['ja'].strip() for r in refs)
        if str(number) in variants:
            japanese = variants[str(number)]
        box = [60, 134, 320, 192] if number < 13 else [28, 160, 320, 192]
        origin = [box[0] + 3, box[1] + 2]
        lines = fit(en, box[2] - origin[0] - 3)
        assert (len(lines) - 1) * LINE_STEP + 12 <= box[3] - origin[1], (number, len(lines))
        picture = ROOT / frames[witness]['file']
        original = Image.open(picture).convert('RGB')
        assert original.size == (320, 192)
        translated = original.copy()
        ImageDraw.Draw(translated).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill='black')
        for line_number, line in enumerate(lines):
            ink = mask(line, FONT_DENOMINATOR)
            translated.paste('white', (origin[0], origin[1] + line_number * LINE_STEP,
                                      origin[0] + ink.width, origin[1] + line_number * LINE_STEP + ink.height), ink)
        # Caption replacement must leave every pixel outside its declared box.
        for region in ((0, 0, 320, box[1]), (0, box[1], box[0], 192)):
            assert translated.crop(region).tobytes() == original.crop(region).tobytes()
        duration = frames[end]['time'] - frames[start]['time']
        cue = {
            'id': f'movie.MOV072.caption.{number:02d}', 'en': en, 'status': 'draft',
            'start_frame': start, 'end_frame_exclusive': end,
            'start_seconds': frames[start]['time'], 'end_seconds': frames[end]['time'],
            'timing_evidence': 'Consecutive source-frame caption crops manually inspected at each boundary',
            'witness_frame': witness, 'witness_file': frames[witness]['file'],
            'witness_sha256': digest(picture.read_bytes()),
            'related_draft_rows': [{'id': r['id'], 'source_sha256': r['source_sha256'],
                                    'draft_sha256': digest(r['en'].encode())} for r in refs],
            'source_relation': 'edited movie variant' if override else 'matching playable dialogue page',
            'decisions': decision or 'Reuse established English wording and glossary names; no new story-row credit.',
            'replace_rect': box, 'text_origin': origin, 'font_source_scale': 'uniform 1/2, twelve-pixel cell height',
            'line_step': LINE_STEP,
            'wrapped_lines': lines, 'maximum_line_pixels': max(mask(line, FONT_DENOMINATOR).width for line in lines),
            'source_duration_seconds': duration,
            'reading_speed_characters_per_second': round(len(en) / duration, 1),
            'readability_review': 'Original demo timings are fast; English reading speed and final presentation need review',
            'reinsertion': 'not inserted',
        }
        cues.append(cue)
        transcriptions.append({'id': cue['id'], 'ja': japanese,
                               'transcription': 'Manually read movie pixels; related playable-script source used as reference',
                               'source_relation': cue['source_relation'], 'witness_file': cue['witness_file']})
        previews.append((cue, original, translated))
    return {
        'format': 1, 'movie': 'MOV072.SFD', 'source_sha256': metadata['source_sha256'],
        'source_dimensions': [320, 192], 'frame_rate': metadata['frame_rate'],
        'status': 'Thirteen timed dialogue drafts prepared; no SFD/disc modification',
        'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'), 'font_sha256': digest(ATLAS.read_bytes()),
        'cues': cues,
        'remaining': ['Captured UI drafts are in MOV072-ui.en.json; geometry/timing and their insertion remain pending',
                      'Two animated Japanese title-logo sequences',
                      'Independent transcription/meaning and fast-demo readability review',
                      'Frame-complete movie audit, audio/content review and native movie reinsertion/playback'],
        'story_library_draft_credit': 0,
    }, transcriptions, previews


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    recipe, jp, previews = prepare()
    print('Prepared', len(recipe['cues']), 'timed caption drafts;', sum(c['source_relation'] == 'edited movie variant' for c in recipe['cues']), 'movie-specific variants.')
    print('All words preserved under measured wrapping; SFD/disc unchanged. Menus, logos, reading speed and reinsertion remain pending.')
    if not args.write:
        print('DRY RUN: no files written')
        return
    dest = ROOT / 'work/translation/en/movies'
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'MOV072.en.json').write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
    (ROOT / 'work/source/movies/MOV072-captions.json').write_text(json.dumps(jp, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    srt = '\n\n'.join(f'{i}\n{srt_time(c["start_seconds"])} --> {srt_time(c["end_seconds"])}\n' + '\n'.join(c['wrapped_lines'])
                        for i, c in enumerate(recipe['cues'], 1)) + '\n'
    (dest / 'MOV072.en.srt').write_text(srt, 'utf-8')
    dest = ROOT / 'work/ui/movies/MOV072/english-caption-drafts'
    dest.mkdir(parents=True, exist_ok=True)
    pages = []
    for number, (cue, original, translated) in enumerate(previews):
        translated.save(dest / (cue['id'].split('.')[-1] + '.png'))
        if number % 4 == 0:
            sheet = Image.new('RGB', (1280, 440), '#30333a')
            pages.append(sheet)
        x = number % 4 * 320
        sheet.paste(original, (x, 25))
        sheet.paste(translated, (x, 231))
        draw = ImageDraw.Draw(sheet)
        draw.text((x + 3, 4), cue['id'] + f' / f{cue["witness_frame"]}', fill='white')
        draw.text((x + 3, 216), 'Offline English draft - not in the game', fill='white')
    for n, sheet in enumerate(pages):
        sheet.save(dest / f'comparison-{n:02d}.png')


if __name__ == '__main__':
    main()
