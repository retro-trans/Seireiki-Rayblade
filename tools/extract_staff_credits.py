"""Map original credit sprites and produce exact image witnesses. Default dry run."""
import argparse
import json
import struct

from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr
from build_bitmap_font import ROOT, digest
from disc_inventory import Disc
from rayblade_codec import decompress


def analyze():
    disc = Disc(next(ROOT.glob('*.cue')))
    entry = next(r for r in disc.inventory() if r['path'] == 'STAFF.AFS')
    archive = disc.read(entry['lba'], entry['size'])
    assert archive[:4] == b'AFS\0' and struct.unpack_from('<I', archive, 4)[0] == 22
    members = []
    for index in range(22):
        offset, size = struct.unpack_from('<II', archive, 8 + index * 8)
        assert offset % 2048 == 0 and offset + size <= len(archive)
        members.append(archive[offset:offset + size])
    dat, packed = members[19:21]
    assert dat[:4] == b'NJTL' and packed[:4] == b'GBIX'
    plain, consumed = decompress(packed[16:])
    assert consumed == len(packed) - 16
    image, texture = decode_pvr(plain)
    assert image.size == (1024, 256) and texture['pixel_format'] == 0
    pof = dat.index(b'POF0')
    start = pof + 8 + struct.unpack_from('<I', dat, pof + 4)[0]
    rows = []
    pos = start
    while struct.unpack_from('<H', dat, pos)[0]:
        width, height, cx, cy, u0, v0, u1, v1, tex, flags = struct.unpack_from('<HHhh6H', dat, pos)
        box = [u0 * 4, v0, u1 * 4, v1]
        assert box[2] - box[0] == width and box[3] - box[1] == height
        assert 0 <= box[0] < box[2] <= 1024 and 0 <= box[1] < box[3] <= 256
        rows.append({'id': f'staff.19.{len(rows):03d}', 'sprite': len(rows),
                     'record_offset': pos, 'source_box': box, 'draw_size': [width, height],
                     'anchor': [cx, cy], 'texture_id': tex, 'flags': flags,
                     'source_pixels_sha256': digest(image.crop(box).tobytes())})
        pos += 20
    assert len(rows) == 84 and pos == 1744
    report = {'archive': 'STAFF.AFS', 'source_archive_sha256': digest(archive),
              'dat_member': 19, 'texture_member': 20, 'dat_sha256': digest(dat),
              'packed_sha256': digest(packed), 'decoded_sha256': digest(plain),
              'texture': texture, 'rectangle_start': start, 'rectangles': rows,
              'scope': 'Original credit image geometry and witnesses; no game changes'}
    return report, archive, members, plain, image


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    info, _, _, _, image = analyze()
    print(json.dumps({k: v for k, v in info.items() if k != 'rectangles'}, indent=2))
    print('Credit sprites:', len(info['rectangles']), '; Japanese roles/company 21..41; people 42..83')
    if not args.write:
        print('DRY RUN: no files written')
        return
    out = ROOT / 'work/ui/asset-audit/STAFF'
    out.mkdir(parents=True, exist_ok=True)
    for page in range(3):
        sheet = Image.new('RGB', (1200, 840), '#30333a')
        draw = ImageDraw.Draw(sheet)
        for n, row in enumerate(info['rectangles'][page * 28:(page + 1) * 28]):
            x, y = n % 2 * 600, n // 2 * 60
            crop = image.crop(row['source_box'])
            crop = crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.NEAREST)
            sheet.paste(crop, (x, y), crop)
            draw.text((x, y + 47), row['id'] + ' ' + str(row['source_box']), fill='white')
        sheet.save(out / f'credit-sprites-{page:02d}.png')
    (out / 'rectangles.json').write_text(json.dumps(info, indent=2) + '\n', 'utf-8')
    print('Wrote 84 sprite records and three labeled source sheets.')


if __name__ == '__main__':
    main()
