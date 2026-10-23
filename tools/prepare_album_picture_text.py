"""Link the remaining album pictured text to English and exact source images.

Dry run first. No image pixels or game files are changed; native artwork and
thumbnail insertion require their own previews/verification.
"""
import argparse
import json

import numpy as np
from PIL import Image

from audit_texture_archive import decode_pvr
from build_bitmap_font import ROOT, digest
from extract_album_captions import analyze
from prepare_story_letter import prepare as prepare_letter
from rayblade_codec import decompress

DEST = ROOT / 'work/translation/en/ui/album-picture-text.en.json'


def prepare():
    info, archive, members, textures = analyze()
    letter = prepare_letter()
    pictures = []
    for member, expected_matches in ((15, [14, 25]), (81, [86])):
        plain, used = decompress(members[member][16:])
        assert used == len(members[member]) - 16
        image, fmt = decode_pvr(plain)
        assert fmt == {'pixel_format': 3, 'data_format': 9, 'width': 512, 'height': 256}
        full = image.crop((0, 0, 320, 224)).convert('RGB')
        if member == 15:
            # Thumbnail page uses white around the narrow greeting card.
            a = np.asarray(full).copy()
            a[:, :84] = 255
            a[:, 236:] = 255
            full = Image.fromarray(a)
        sample = np.asarray(full.resize((64, 48), Image.Resampling.BILINEAR), dtype=float)
        scores = []
        for row in info['rectangles']:
            x, y, x1, _ = row['source_box']
            crop = textures[row['texture_member']][1].crop((x, y, x1, y + 48)).convert('RGB')
            scores.append((float(np.abs(np.asarray(crop, dtype=float) - sample).mean()), row['sprite']))
        scores.sort()
        assert sorted(i for _, i in scores[:len(expected_matches)]) == expected_matches
        bindings = [r for r in info['rectangles'] if r['sprite'] in expected_matches]
        pictures.append({'id': f'album.picture.{member:03d}', 'member': member,
                         'source_packed_sha256': digest(members[member]), 'source_decoded_sha256': digest(plain),
                         'format': fmt, 'visible_image': [0, 0, 320, 224],
                         'gallery_bindings': bindings,
                         'thumbnail_matching': {'best_RGB_MAE': round(scores[0][0], 6),
                                                'method': 'Bilinear 320x224 to 64x48; card outer black replaced by white for matching only',
                                                'scope': 'Supports visual identity; not an exact resampling/color equivalence proof'},
                         'status': 'English source-linked recipe; native image rendering/insertion pending'})
    pictures[0].update(English_lines=['Happy New Year!', '2000'],
                       original_heart='Retain the source heart as part of the greeting artwork',
                       meaning='Polite New Year greeting with the year 2000 and a heart; no other message added',
                       source_text_region=[92, 0, 234, 52],
                       layout_note='Keep the portrait art below the greeting; render one uniform glyph scale per line')
    pictures[1].update(English_lines=letter['English_lines'], source_command=letter['source_command'],
                       related_draft_rows=letter['related_draft_rows'],
                       meaning=letter['meaning'], decisions=letter['decisions'],
                       layout_note='This album copy is 224 pixels high; ADV00 note is 240. Render against its own source paper rather than copying the other PVR blindly.')
    return {'archive': 'ALBUM.AFS', 'original_archive_sha256': digest(archive),
            'pictures': pictures, 'status': 'Two pictured-text English recipes prepared; no native image edits yet',
            'pending': ['Render/review both native picture candidates and three matching thumbnail regions',
                        'Exact source preservation, native decoding, archive allocation and packaging checks',
                        'Live album loading/navigation/appearance and independent meaning/artwork review'],
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    data = prepare()
    print('Plan:', [(r['member'], r['English_lines'], [b['id'] for b in r['gallery_bindings']]) for r in data['pictures']])
    print('Ten existing note rows linked; two full pictures and three thumbnail regions still unchanged.')
    if not args.write:
        print('DRY RUN: no translation recipe written')
        return
    DEST.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
