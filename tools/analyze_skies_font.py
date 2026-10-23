"""Read-only comparison of the user's Skies disc and Rayblade font.

Default is a dry run. --write saves research images/reports only.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw

from disc_inventory import Disc
from build_antialias_font import font_bytes
from preview_font_sampling import packed_mask
from build_font4x_patch import MEDIUM

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/ui/skies-font-comparison'
CUE = Path(r'E:\Games\Skies of Arcadia (USA) (Disc 1).cue')
ATLAS = ROOT / 'incoming/fonts/user-bitmap/dialogue-atlas.png'
EXPECTED_EXE = '4218c07829d63080be2da86413ec023e6d77001c13a1494648db6e2e5cb73611'


def skies_glyph(exe, code, levels):
    """Decode 6x12 VQ indices into their 12x24 coverage mask.

    The codebook generator at 0x8c02ad8e enumerates four nested
    0..3 loops. Its four ARGB4444 words are TL, BL, TR, BR.
    """
    offset = 0x360cd4 + (code - 32) * 72
    raw = exe[offset:offset + 72]
    im = Image.new('L', (12, 24))
    for y in range(12):
        for x in range(6):
            value = raw[y * 6 + x]
            for dx, dy, shift in ((0, 0, 6), (0, 1, 4), (1, 0, 2), (1, 1, 0)):
                im.putpixel((x * 2 + dx, y * 2 + dy), levels[value >> shift & 3])
    # Every decoded pixel can reconstruct the original stored VQ index.
    restored = bytearray()
    for y in range(12):
        for x in range(6):
            restored.append(sum(levels.index(im.getpixel((x * 2 + dx, y * 2 + dy))) << shift
                                for dx, dy, shift in ((0, 0, 6), (0, 1, 4), (1, 0, 2), (1, 1, 0))))
    assert bytes(restored) == raw
    return im


def source_glyph(atlas, code):
    i = code - 32
    return atlas.crop((i % 32 * 12, i // 32 * 24,
                       i % 32 * 12 + 12, i // 32 * 24 + 24))


def specimen(glyphs, advances, height):
    text = 'Good morning, Touya!  r O o R 0'
    im = Image.new('L', (sum(advances[c] for c in text) + 32, height))
    x = 0
    for ch in text:
        im.paste(glyphs[ch], (x, 0))
        x += advances[ch]
    return im


def check_native_codebook(exe, colors):
    from test_font_patch import CPU
    cpu = CPU.__new__(CPU)
    cpu.reg = [0x12340000 + i * 0x100 for i in range(16)]
    cpu.reg[4] = 0x8c600040
    cpu.reg[15] = 0x8c700800
    cpu.pr = 0xdead0000
    cpu.macl = cpu.t = 0
    cpu.pc = 0x8c02ad8e
    output = bytearray([0xa5] * (2048 + 128))
    cpu.regions = [(0x8c010000, bytearray(exe)), (0x8c600000, output),
                   (0x8c700000, bytearray(0x1000))]
    instructions = cpu.run()
    expected = b''.join(struct.pack('<4H', *(colors[index >> s & 3] for s in (6, 4, 2, 0)))
                        for index in range(256))
    assert output[64:2112] == expected
    assert output[:64] == bytes([0xa5] * 64) and output[2112:] == bytes([0xa5] * 64)
    return {'routine': '0x8c02ad8e', 'entries': 256, 'exact_bytes': 2048,
            'integer_sh4_instructions': instructions, 'output_guards': 'pass',
            'callee_saved_registers_and_stack': 'pass',
            'sha256': hashlib.sha256(expected).hexdigest(),
            'scope': 'Actual codebook generator in integer interpreter; not GPU rendering'}


def read_executable():
    disc = Disc(CUE)
    rows = disc.inventory()
    row = next(r for r in rows if r['path'] == '1ST_READ.BIN')
    return disc.read(row['lba'], row['size']), rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    exe, rows = read_executable()
    assert hashlib.sha256(exe).hexdigest() == EXPECTED_EXE
    offset = int.from_bytes(exe[0x1a210:0x1a214], 'little') - 0x8c010000
    assert offset == 0x360cd4
    count = 96
    colors = struct.unpack_from('<4H', exe, 0x3ea0f0)
    assert colors == (0x0000, 0x5fff, 0xbfff, 0xffff)
    levels = tuple((color >> 12) * 17 for color in colors)
    native_check = check_native_codebook(exe, colors)
    width, height = 12, 24
    page = Image.new('L', (32 * width, 3 * height))
    atlas = Image.open(ATLAS).convert('L')
    native, supplied, current = {}, {}, {}
    _, font = font_bytes((ROOT / 'work/output/0.1.38/WIN00.AFS').read_bytes())
    changes = []
    for i in range(count):
        glyph = skies_glyph(exe, i + 32, levels)
        page.paste(glyph, (i % 32 * width, i // 32 * height))
        if i >= 95:
            continue
        ch = chr(i + 32)
        native[ch] = glyph
        supplied[ch] = source_glyph(atlas, i + 32)
        # Put the 2x contour mask back on a common source-pixel grid.
        # This preview is not the runtime's point decimator or GPU filter.
        current[ch] = packed_mask(font, ch).resize((32, 32), Image.Resampling.BOX)
        a, b = glyph.tobytes(), supplied[ch].tobytes()
        changes.append({'character': ch, 'different_pixels': sum(x != y for x, y in zip(a, b)),
                        'skies_coverage_sum': sum(a), 'supplied_coverage_sum': sum(b),
                        'skies_bounds': glyph.getbbox(), 'supplied_bounds': supplied[ch].getbbox()})
    comparison = Image.new('RGB', (1000, 440), '#171b24')
    draw = ImageDraw.Draw(comparison)
    draw.text((16, 12), 'Original Skies disc / supplied atlas / current Rayblade font', fill='white', font_size=20)
    fixed = {ch: 12 for ch in native}
    advances = {ch: font[0xa0 + MEDIUM.index(ch)] * 2 for ch in native}
    samples = [
        ('Skies embedded Latin: original 12 x 24 masks; fixed cells for this comparison',
         specimen(native, fixed, 32)),
        ('Supplied bitmap: original 12 x 24 masks; same fixed cells',
         specimen(supplied, fixed, 32)),
        ('Rayblade 0.1.38: reconstructed contours and current variable advances',
         specimen(current, advances, 32)),
    ]
    for y, (label, sample) in zip((55, 165, 275), samples):
        draw.text((16, y), label, fill='#c6ccd6', font_size=16)
        sample = sample.resize((sample.width * 2, sample.height * 2), Image.Resampling.NEAREST)
        comparison.paste('white', (16, y + 26, 16 + sample.width, y + 26 + sample.height), sample)
    draw.text((16, 390), 'Offline masks at a common pixel scale. This is not a game screenshot or GPU simulation.', fill='#c6ccd6', font_size=15)
    draw.text((16, 414), 'Skies and the supplied atlas use the same four alpha levels: 0, 85, 187, 255.', fill='#c6ccd6', font_size=15)
    report = {
        'source_disc': str(CUE), 'disc_file_count': len(rows),
        'executable_sha256': hashlib.sha256(exe).hexdigest(),
        'embedded_latin_font': {
            'offset': hex(offset), 'glyph_size': [width, height],
            'format': '6 x 12 VQ indices; each byte selects a 2 x 2 block',
            'glyph_count': count, 'first_code': 32, 'last_code': 127,
            'native_routine': '0x8c02a1b8',
            'native_ascii_branch': '0x8c02a1ce..0x8c02a20c',
            'native_glyph_stride': '(character - 32) * 72',
            'native_row_copy': '6 VQ index bytes per block row, 12 block rows, then zero right padding',
            'native_next_table': hex(offset + count * 72),
            'coverage_values': levels,
            'codebook_generator': '0x8c02ad8e..0x8c02ae36',
            'codebook_color_table_address': '0x8c3fa0f0',
            'codebook_color_words': [hex(v) for v in colors],
            'roundtripped_glyphs': count,
            'live_dialogue_usage': 'not independently traced',
        },
        'supplied_atlas_sha256': hashlib.sha256(ATLAS.read_bytes()).hexdigest(),
        'current_rayblade_font_sha256': hashlib.sha256(font).hexdigest(),
        'native_codebook_check': native_check,
        'ascii_comparison': {
            'compared_glyphs': len(changes),
            'identical_glyphs': sum(r['different_pixels'] == 0 for r in changes),
            'different_glyphs': sum(r['different_pixels'] != 0 for r in changes),
            'skies_total_coverage': sum(r['skies_coverage_sum'] for r in changes),
            'supplied_total_coverage': sum(r['supplied_coverage_sum'] for r in changes),
            'glyphs': changes,
        },
        'findings': [
            'The embedded Skies Latin font and supplied atlas do not have identical pixel masks.',
            'Skies coverage is decoded from its generated VQ codebook, not inferred from nibble counts.',
            'The supplied atlas and embedded Skies font have the same four alpha levels.',
            'Rayblade currently reconstructs outlines, trims side columns and uses new variable advances.',
            'Rayblade surface reduction point-samples source coverage, which can discard edge samples.',
        ],
        'limitations': [
            'The actual Skies dialogue draw call, blend state, filtering and screen scale are not traced.',
            'The preview normalizes source-mask scale and does not simulate the GPU or native decimator.',
            'This comparison does not change the selected font or create a playable build.',
        ],
        'game_files_changed': False,
        'outputs': [str(OUT / 'skies-embedded-latin.png'), str(OUT / 'font-comparison.png')],
    }
    brief = {**report, 'ascii_comparison': {k: v for k, v in report['ascii_comparison'].items() if k != 'glyphs'}}
    brief['ascii_comparison']['skies_to_supplied_coverage_ratio'] = (
        report['ascii_comparison']['skies_total_coverage'] / report['ascii_comparison']['supplied_total_coverage'])
    print(json.dumps(brief, indent=2))
    if not args.write:
        print('DRY RUN: no files written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    page.resize((1152, 216), Image.Resampling.NEAREST).save(OUT / 'skies-embedded-latin.png')
    comparison.save(OUT / 'font-comparison.png')
    (OUT / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    (ROOT / 'docs/skies-font-comparison.json').write_text(json.dumps(brief, indent=2) + '\n', 'utf-8')
    # Discard only this tool's superseded exploratory nibble-decoding outputs.
    for name in ('probe.json', 'executable-font-probe.png'):
        (OUT / name).unlink(missing_ok=True)


if __name__ == '__main__':
    main()
