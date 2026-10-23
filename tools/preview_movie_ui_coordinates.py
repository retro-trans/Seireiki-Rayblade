"""Draw enlarged source-panel coordinate guides. Dry run by default."""
import argparse
from PIL import Image, ImageDraw
from build_bitmap_font import ROOT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    specs = [(2400, (0, 112, 160, 192)), (2400, (250, 135, 310, 192)),
             (2475, (250, 153, 310, 192)), (2490, (0, 15, 310, 158)), (2565, (0, 0, 320, 136))]
    if not args.write:
        print('DRY RUN: five native-source coordinate guides at uniform 4x nearest scale; no game change')
        return
    root = ROOT / 'work/ui/asset-audit/movies/MOV072/dense'
    out = ROOT / 'work/ui/movies/MOV072/geometry-review'
    out.mkdir(parents=True, exist_ok=True)
    for i, (frame, box) in enumerate(specs):
        im = Image.open(root / f'frame-{frame:05d}.png').crop(box)
        im = im.resize((im.width * 4, im.height * 4), Image.Resampling.NEAREST)
        canvas = Image.new('RGB', (im.width + 40, im.height + 24), '#30333a')
        canvas.paste(im, (40, 24))
        draw = ImageDraw.Draw(canvas)
        for x in range(box[0], box[2], 10):
            xx = 40 + (x - box[0]) * 4
            draw.text((xx, 3), str(x), fill='white')
            draw.line((xx, 20, xx, 24), fill='yellow')
        for y in range(box[1], box[3], 5):
            yy = 24 + (y - box[1]) * 4
            draw.text((0, yy), str(y), fill='white')
            draw.line((36, yy, 40, yy), fill='yellow')
        canvas.save(out / f'coords-{i}.png')


if __name__ == '__main__':
    main()
