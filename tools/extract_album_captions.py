"""Map album selection captions to native sprite/texture cells. Dry run first."""
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
    entry = next(r for r in disc.inventory() if r['path'] == 'ALBUM.AFS')
    archive = disc.read(entry['lba'], entry['size'])
    assert archive[:4] == b'AFS\0' and struct.unpack_from('<I', archive, 4)[0] == 244
    members = []
    for i in range(244):
        offset, size = struct.unpack_from('<II', archive, 8 + i * 8)
        assert offset % 2048 == 0 and offset + size <= len(archive)
        members.append(archive[offset:offset+size])
    dat = members[214]
    pof = dat.index(b'POF0'); start = pof + 8 + struct.unpack_from('<I', dat, pof + 4)[0]
    assert start == 544
    textures = {}
    for i in range(215, 243):
        raw, used = decompress(members[i][16:])
        assert used == len(members[i]) - 16
        image, fmt = decode_pvr(raw)
        assert fmt == {'pixel_format': 0, 'data_format': 1, 'width': 256, 'height': 256}
        textures[i] = (raw, image)
    rows = []
    pos = start
    while struct.unpack_from('<H', dat, pos)[0]:
        w, h, cx, cy, u0, v0, u1, v1, tex, flags = struct.unpack_from('<HHhh6H', dat, pos)
        assert (w, h, cx, cy, u1-u0, v1-v0, flags) == (64, 72, 0, 0, 64, 72, 0)
        box, caption = [u0, v0, u1, v1], [u0, v0+48, u1, v1]
        member = 215 + tex
        assert 215 <= member <= 242
        image = textures[member][1]
        rows.append({'id': f'album.214.{len(rows):03d}', 'sprite': len(rows), 'record_offset': pos,
                     'texture_member': member, 'texture_id': tex, 'source_box': box,
                     'caption_box': caption, 'source_caption_sha256': digest(image.crop(caption).tobytes()),
                     'source_tile_sha256': digest(image.crop(box).tobytes())})
        pos += 20
    assert len(rows) == 224 and pos + 16 == len(dat)
    report = {'archive': 'ALBUM.AFS', 'source_archive_sha256': digest(archive),
              'dat_member': 214, 'dat_sha256': digest(dat), 'sprite_count': 224,
              'texture_members': list(textures), 'sprite_size': [64, 72],
              'photo_size': [64, 48], 'caption_size': [64, 24], 'rectangles': rows,
              'scope': 'Original gallery selection cells; caption text not yet transcribed or translated'}
    return report, archive, members, textures


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    info, _, _, textures = analyze()
    print(json.dumps({k: v for k, v in info.items() if k != 'rectangles'}, indent=2))
    if not args.write:
        print('DRY RUN: no image witnesses or geometry map written')
        return
    out = ROOT / 'work/ui/asset-audit/ALBUM/captions'
    out.mkdir(parents=True, exist_ok=True)
    for page in range(7):
        sheet = Image.new('RGB', (1024, 928), '#30333a')
        draw = ImageDraw.Draw(sheet)
        for n, row in enumerate(info['rectangles'][page*32:(page+1)*32]):
            x, y = n % 4 * 256, n // 4 * 116
            crop = textures[row['texture_member']][1].crop(row['caption_box'])
            crop = crop.resize((256, 96), Image.Resampling.NEAREST)
            sheet.paste(crop, (x, y), crop)
            draw.text((x, y+98), row['id'], fill='white')
        sheet.save(out / f'captions-{page:02d}.png')
    (out / 'rectangles.json').write_text(json.dumps(info, indent=2) + '\n', 'utf-8')
    print('Wrote 224 labeled caption witnesses and exact native rectangles.')


if __name__ == '__main__':
    main()
