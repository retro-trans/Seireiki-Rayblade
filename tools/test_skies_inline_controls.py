"""Check all 166 story commands with inline controls using the ported font."""
import argparse
import json
import struct

from build_skies_font_patch import OUT, ROOT, PRIOR, VERSION, compose, digest
from build_font4x_patch import SMALL, MEDIUM
from rayblade_codec import decompress
from scenario_word_wrap import command_payloads, tokens, PEN_WIDTH
from test_scenario_pages import native_format
from test_inline_controls import execute_stream


def check():
    _, component, _, font, _ = compose()
    exe = (ROOT / 'work/output' / PRIOR / '1ST_READ.BIN').read_bytes()
    base = ROOT / 'work/output' / PRIOR
    archive = (base / 'D_SCE.AFS').read_bytes()
    recipe = json.loads((base / 'text/scenario-component-report.json').read_text('utf-8'))
    wanted = {}
    for _, row, payload in command_payloads():
        controls = [t for t in tokens(payload, font) if 'fc' in t]
        if controls and not all(t['fc'] == 0x3e for t in controls):
            wanted[row['id']] = payload
    actual = {}
    for member in recipe['members']:
        records = [r for r in member['commands'] if r['id'] in wanted]
        if not records:
            continue
        p = member['archive_offset']
        plain, used = decompress(archive[p+20:p+member['packed_bytes']])
        assert digest(plain) == member['decoded_sha256']
        for row in records:
            payload = plain[row['english_offset']:row['english_offset']+row['english_bytes']]
            assert digest(payload) == row['english_sha256']
            actual[row['id']] = payload
    assert len(actual) == len(wanted) == 166
    steps = maximum_x = maximum_y = 0
    for n, (key, source) in enumerate(wanted.items()):
        before, count = native_format(exe, source, width=30, limit=8191, capacity=8192)
        steps += count
        after, count = native_format(exe, actual[key], width=127, limit=8191, capacity=8192)
        steps += count
        original, count, effects, states = execute_stream(exe, font, before, key)
        steps += count
        current, count, changed_effects, changed_states = execute_stream(exe, font, after, key)
        steps += count
        assert effects == changed_effects and states == changed_states
        assert ''.join(g[0] for g in original.glyphs if g[0] != ' ') == ''.join(g[0] for g in current.glyphs if g[0] != ' ')
        for ch, x, y, small in current.glyphs:
            index = (SMALL if small else MEDIUM).index(ch)
            advance = font[(0x20 if small else 0xa0) + index]
            assert 64 <= x and x + advance <= 64 + PEN_WIDTH and 16 <= y and y + (8 if small else 16) <= 64
            maximum_x = max(maximum_x, x + advance)
            maximum_y = max(maximum_y, y + (8 if small else 16))
        if (n + 1) % 50 == 0:
            print('Native inline commands:', n + 1, flush=True)
    return {'version': VERSION, 'source_build': PRIOR, 'font_sha256': digest(font),
            'executable_sha256': digest(exe), 'archive_sha256': digest(archive),
            'commands': 166, 'SH4_instructions': steps, 'maximum_pen_end_x': maximum_x,
            'maximum_glyph_bottom_y': maximum_y, 'effects_resume_states_and_glyph_order': 'exact',
            'cursor_bounds': 'pass', 'limits': ['Glyph drawing uses verified advances; effect/GPU endpoints are bounded fixtures; live timing unverified']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: all 166 inline-control command pairs, native formatting, effects/resume order and current-font cursor bounds.', flush=True)
    if not args.verify:
        print('DRY RUN: no execution or report')
        return
    report = check()
    print(json.dumps(report, indent=2), flush=True)
    if args.write_report:
        (OUT / 'inline-native-test.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
