"""Compare bitmap sampling at matched sizes. No game files are changed."""
import argparse
import hashlib
import json
import struct

from PIL import Image, ImageDraw

from build_antialias_font import LEVELS, font_bytes
from build_bitmap_font import ATLAS, ROOT
from build_font4x_patch import MEDIUM
from build_genei_font import MEDIUM_DATA


def packed_mask(font, ch):
    i = MEDIUM.index(ch)
    mask = Image.new('L', (64, 64))
    for y in range(64):
        a, b = struct.unpack_from('<2I', font, MEDIUM_DATA + i * 512 + y * 8)
        for x in range(32):
            mask.putpixel((x, y), LEVELS[((a if x < 16 else b) >> (30 - 2 * (x % 16))) & 3])
    return mask


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version', default='0.1.22')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    source = Image.open(ATLAS).convert('L')
    _, font = font_bytes((ROOT / 'work/output' / args.version / 'WIN00.AFS').read_bytes())
    assert font[:8] == b'RBLF4X\0\4'
    text = 'r O o R 0 - Good morning, Touya!'
    layers = [Image.new('L', (980, 64)) for _ in range(3)]
    x = 8
    exact = 0
    for ch in text:
        code = ord(ch) - 32
        cell = source.crop((code % 32 * 12, code // 32 * 24,
                            code % 32 * 12 + 12, code // 32 * 24 + 24))
        bounds = cell.point(lambda v: 255 if v >= 128 else 0).getbbox()
        left = bounds[0] if bounds else 0
        original = packed_mask(font, ch)
        expected = Image.new('L', (64, 64))
        expected.paste(cell.resize((24, 48), Image.Resampling.NEAREST), (4 - left * 2, 4))
        assert original.tobytes() == expected.tobytes(), ch
        exact += 1
        # Smooth enlargement is a proposal only: same cell size/origin/advance.
        # Quantize back to the existing two-bit coverage levels, so the
        # preview does not imply that the current font stores 256 alpha levels.
        smooth = Image.new('L', (64, 64))
        smooth.paste(cell.resize((24, 48), Image.Resampling.BILINEAR), (4 - left * 2, 4))
        smooth = smooth.point(lambda v: min(LEVELS, key=lambda level: abs(v - level)))
        # Paste masks directly; using a mask while pasting would square alpha.
        layers[0].paste(original, (x, 0))
        layers[1].paste(smooth, (x, 0))
        x += font[0xa0 + MEDIUM.index(ch)] * 4
    # Same current texture reduced to its logical display dimensions. This is
    # an offline area-filter reference, not a claim about the actual GPU.
    layers[2] = layers[0].resize((490, 32), Image.Resampling.BOX)
    canvas = Image.new('RGB', (1000, 300), '#171b24')
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 8), 'Sampling diagnosis - offline references, not game screenshots', fill='white')
    labels = [
        'Current texture pixels: source doubled with nearest-neighbor sampling',
        'Proposal: bilinear enlargement, then the same four stored coverage levels',
        'Current font at logical 1x: area-filter reference (actual GPU filtering unverified)',
    ]
    for y, label, mask in zip((35, 125, 215), labels, layers):
        draw.text((12, y), label, fill='#c6ccd6')
        canvas.paste('white', (12, y + 20, 12 + mask.width, y + 20 + mask.height), mask)
    report = {
        'version_inspected': args.version,
        'source_sha256': hashlib.sha256(ATLAS.read_bytes()).hexdigest(),
        'font_sha256': hashlib.sha256(font).hexdigest(),
        'matched_sample_characters': exact,
        'finding': 'Medium bitmap repeats each source sample in a 2x2 block; previews show physical texture pixels at 1:1',
        'stored_alpha': list(LEVELS),
        'proposal': 'Uniform bilinear source enlargement quantized to existing four coverage levels; same baseline and advances',
        'limitations': ['Interpolation softens existing contours; it cannot recover missing outline detail',
                        'Proposal is not installed in the game',
                        'Actual game/GPU filtering and Skies of Arcadia rendering have not been compared'],
        'game_files_changed': False,
    }
    # Matched output sizes make this comparison useful: the old specimen
    # displayed physical texture pixels, not the final text on screen. Pillow
    # bilinear is illustrative, not a PVR/GPU implementation or live capture.
    short = Image.new('L', (300, 64))
    pen = 8
    for ch in 'r O o R 0':
        short.paste(packed_mask(font, ch), (pen, 0))
        pen += font[0xa0 + MEDIUM.index(ch)] * 4
    short = short.crop((0, 0, pen + 8, 64))
    display = Image.new('RGB', (1000, 540), '#171b24')
    dd = ImageDraw.Draw(display)
    dd.text((12, 10), 'Same stored font / same output size - offline sampling illustration', fill='white')
    dd.text((12, 29), 'Point sampling (before 0.1.22)', fill='#c6ccd6')
    dd.text((510, 29), 'Bilinear illustration (enabled natively in 0.1.22)', fill='#c6ccd6')
    for y, factor in ((57, .25), (143, .5), (229, .75), (337, 1.5)):
        size = (round(short.width * factor), round(short.height * factor))
        dd.text((12, y), f'{factor:g}x physical texture size; identical dimensions on both sides', fill='#c6ccd6')
        samples = [short.resize(size, method) for method in (Image.Resampling.NEAREST, Image.Resampling.BILINEAR)]
        for x, sample in zip((12, 510), samples):
            display.paste('white', (x, y + 20, x + size[0], y + 20 + size[1]), sample)
    dd.text((12, 502), 'Texture-size factors are illustrative, not measured game or Skies of Arcadia screen sizes.', fill='#c6ccd6')
    dd.text((12, 520), 'Interpolation softens edges. A doubled bitmap does not contain new high-resolution outline detail.', fill='#c6ccd6')
    report['matched_display_preview'] = {
        'file': 'sampling-display-comparison.png',
        'physical_texture_size_factors': [.25, .5, .75, 1.5],
        'same_input_pixels_and_output_dimensions': True,
        'bilinear_illustration': 'Pillow resampling, not native PVR sampling or a live screenshot',
        'native_filter_build': '0.1.22',
        'native_filter_evidence': 'docs/font-filtering.json',
        'live_comparison': 'pending',
    }
    print(json.dumps(report, indent=2))
    if not args.write:
        print('DRY RUN: no files written')
        return
    out = ROOT / 'work/ui/font-sampling'
    out.mkdir(parents=True, exist_ok=True)
    canvas.save(out / 'sampling-comparison.png')
    display.save(out / 'sampling-display-comparison.png')
    (out / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
