"""Render diagnostic tile interpretations of WIN00.AFS entry 0.

Default is a dry run. These are candidate interpretations, not a verified font.
"""
import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    data = (ROOT / 'work/source/disc/WIN00.AFS').read_bytes()
    offset, length = struct.unpack_from('<II', data, 8)
    configs = [(8, 8, 0), (8, 16, 0x300), (16, 16, 0x300)]
    output = ROOT / 'work/ui/font-probe.png'
    print('Source WIN00.AFS entry 0: offset 0x{:x}, {} bytes'.format(offset, length))
    print('Candidate interpretations: {}'.format(configs))
    print('Will render candidate layouts, swapping adjacent bits in every byte, to {}'.format(output))
    if not args.write:
        print('DRY RUN: no files written')
        return
    from PIL import Image, ImageDraw
    sheet = Image.new('RGB', (3 * 640, 1120), '#202020')
    draw = ImageDraw.Draw(sheet)
    blob = bytes(((b & 0x55) << 1) | ((b & 0xaa) >> 1) for b in data[offset:offset + length])
    for panel, (width, height, start) in enumerate(configs):
        draw.text((panel * 640 + 5, 4), '{}x{} offset {:x}, candidate'.format(width, height, start), fill='white')
        for tile in range(256):
            image = Image.new('L', (width, height))
            for y in range(height):
                for x in range(width):
                    bit = start * 8 + tile * width * height + y * width + x
                    value = blob[bit // 8] >> (7 - bit % 8) & 1
                    image.putpixel((x, y), value * 255)
            image = image.resize((width * 3, height * 3), Image.Resampling.NEAREST)
            sheet.paste(image, (panel * 640 + tile % 10 * 64, 30 + tile // 10 * 42))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print('Wrote diagnostic image')


if __name__ == '__main__':
    main()
