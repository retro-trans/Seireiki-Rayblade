"""Prepare a uniformly filtered bitmap-font candidate; dry run first.

Keeps the existing native format, advances, baseline and protected marks.
This is an offline candidate, not a packaged game build or new outlines.
"""
import argparse
import hashlib
import json
import struct

from PIL import Image, ImageDraw

from build_antialias_font import LEVELS, font_bytes
from build_bitmap_font import ATLAS, ROOT
from build_font4x_patch import MEDIUM
from build_genei_font import MEDIUM_DATA
from preview_font_sampling import packed_mask

OUT = ROOT / 'work/output/font-smoothing-draft-01'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def scalar_resize(cell):
    """Independent 2x separable bilinear reference with edge clamping."""
    w, h = cell.size
    result = Image.new('L', (w * 2, h * 2))
    for y in range(h * 2):
        iy, fy = divmod(2 * y - 1, 4)
        y0, y1 = max(0, min(h - 1, iy)), max(0, min(h - 1, iy + 1))
        for x in range(w * 2):
            ix, fx = divmod(2 * x - 1, 4)
            x0, x1 = max(0, min(w - 1, ix)), max(0, min(w - 1, ix + 1))
            a = (cell.getpixel((x0, y0)) * (4 - fx) + cell.getpixel((x1, y0)) * fx + 2) // 4
            b = (cell.getpixel((x0, y1)) * (4 - fx) + cell.getpixel((x1, y1)) * fx + 2) // 4
            result.putpixel((x, y), (a * (4 - fy) + b * fy + 2) // 4)
    return result


def compose(version):
    archive = (ROOT / 'work/output' / version / 'WIN00.AFS').read_bytes()
    offset, old = font_bytes(archive)
    assert old[:8] == b'RBLF4X\0\4'
    source = Image.open(ATLAS).convert('L')
    new = bytearray(old)
    records = []
    for ch in (chr(i) for i in range(32, 127)):
        code = ord(ch) - 32
        cell = source.crop((code % 32 * 12, code // 32 * 24,
                            code % 32 * 12 + 12, code // 32 * 24 + 24))
        bounds = cell.point(lambda v: 255 if v >= 128 else 0).getbbox()
        left = bounds[0] if bounds else 0
        enlarged = cell.resize((24, 48), Image.Resampling.BILINEAR)
        assert enlarged.tobytes() == scalar_resize(cell).tobytes(), ch
        mask = Image.new('L', (64, 64))
        mask.paste(enlarged, (4 - left * 2, 4))
        mask = mask.point(lambda v: min(LEVELS, key=lambda a: abs(a - v)))
        assert not mask.crop((32, 0, 64, 64)).getbbox(), ch
        i = MEDIUM.index(ch)
        start = MEDIUM_DATA + i * 512
        for y in range(64):
            for half in range(2):
                word = sum(LEVELS.index(mask.getpixel((half * 16 + x, y))) << (30 - x * 2)
                           for x in range(16))
                struct.pack_into('<I', new, start + y * 8 + half * 4, word)
        assert packed_mask(new, ch).tobytes() == mask.tobytes()
        before = packed_mask(old, ch)
        records.append({'character': ch, 'advance': old[0xa0 + i],
                        'changed_samples': sum(a != b for a, b in zip(before.tobytes(), mask.tobytes())),
                        'old_coverage_sum': sum(before.tobytes()), 'new_coverage_sum': sum(mask.tobytes())})
    allowed = {p for ch in (chr(i) for i in range(32, 127))
               for p in range(MEDIUM_DATA + MEDIUM.index(ch) * 512,
                              MEDIUM_DATA + (MEDIUM.index(ch) + 1) * 512)}
    changed = {i for i, (a, b) in enumerate(zip(old, new)) if a != b}
    assert changed <= allowed and new[:MEDIUM_DATA] == old[:MEDIUM_DATA]
    assert new[0x20:0x120] == old[0x20:0x120]
    target = archive[:offset] + new + archive[offset + len(new):]
    report = {'source_build': version, 'status': 'offline font candidate; not installed or packaged',
              'source_atlas_sha256': sha(ATLAS.read_bytes()), 'source_font_sha256': sha(old),
              'candidate_font_sha256': sha(new), 'candidate_WIN00_sha256': sha(target),
              'method': 'Uniform 2x bilinear enlargement, quantized to existing four alpha levels',
              'ASCII_glyphs_checked': len(records), 'independent_scalar_sampling': 'exact',
              'changed_font_bytes': len(changed),
              'advances_baseline_small_font_and_protected_marks': 'unchanged',
              'limits': ['Interpolation smooths the existing bitmap; no new contour detail',
                         'No live Skies of Arcadia comparison', 'Native and GPU appearance pending'],
              'glyphs': records}
    return bytes(old), bytes(new), bytes(target), report


def specimen(old, new):
    canvas = Image.new('RGB', (1060, 680), '#171b24')
    d = ImageDraw.Draw(canvas)
    d.text((16, 10), 'Same bitmap contours, spacing and baseline - offline candidate, not a game capture', fill='white')
    d.text((16, 32), 'Current font', fill='#c6ccd6')
    d.text((546, 32), 'Filtered source enlargement (four stored alpha levels)', fill='#c6ccd6')
    for row, scale in enumerate((.5, 1, 2)):
        y = 64 + row * 192
        d.text((16, y), f'Identical output scale: {scale:g}x stored glyph size', fill='#c6ccd6')
        for x, font in ((16, old), (546, new)):
            line = Image.new('L', (1040, 64))
            pen = 0
            for ch in 'r O o R 0 - Morning, Touya!':
                line.paste(packed_mask(font, ch), (pen, 0))
                pen += font[0xa0 + MEDIUM.index(ch)] * 4
            line = line.crop((0, 0, pen + 8, 64))
            # Identical point output sampling exposes only the stored-font
            # change. This deliberately does not impersonate a native GPU.
            display = line.resize((round(line.width * scale), round(line.height * scale)), Image.Resampling.NEAREST)
            if display.width > 510:
                display = display.crop((0, 0, 510, display.height))
            canvas.paste('white', (x, y + 26, x + display.width, y + 26 + display.height), display)
    d.text((16, 651), 'Interpolation softens edges. A real high-resolution match still needs reconstructed contours and live validation.', fill='#c6ccd6')
    return canvas


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version', default='0.1.27')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    old, new, archive, report = compose(args.version)
    print(json.dumps({k: v for k, v in report.items() if k != 'glyphs'}, indent=2))
    if not args.write:
        print('DRY RUN: no files written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'WIN00.AFS').write_bytes(archive)
    (OUT / 'font.bin').write_bytes(new)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    specimen(old, new).save(OUT / 'comparison.png')
    print(OUT / 'comparison.png')


if __name__ == '__main__':
    main()
