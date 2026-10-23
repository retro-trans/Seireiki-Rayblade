"""Audit raw PRS-compressed PVM texture containers missed by GBIX-only scans.

Walks declared chunk sizes, including the game's zero-dimension geometry PVRT
chunk. Uses the existing 16-bit PVR decoder; unsupported formats are explicit.
Default dry run. Original game data is read only.
"""
import argparse
import json
import re
import struct

from PIL import Image, ImageDraw

from audit_texture_archive import decode_pvr
from build_bitmap_font import ROOT, digest
from disc_inventory import Disc
from rayblade_codec import decompress


def chunks(data):
    assert data[:4] == b'PVMH' and len(data) >= 12
    header_size = struct.unpack_from('<I', data, 4)[0] + 8
    assert 12 <= header_size <= len(data)
    expected = struct.unpack_from('<H', data, 10)[0]
    position, found, result = header_size, 0, []
    while position < len(data):
        assert position + 8 <= len(data)
        tag = data[position:position + 4]
        count = struct.unpack_from('<I', data, position + 4)[0] + 8
        assert 8 <= count <= len(data) - position, (position, count, len(data))
        assert tag in (b'PVRT', b'PVPL', b'GBIX'), (position, tag)
        chunk = data[position:position + count]
        if tag == b'PVRT':
            assert count >= 16
            width, height = struct.unpack_from('<HH', chunk, 12)
            result.append(({'chunk_offset': position, 'chunk_bytes': count,
                            'texture_index_in_container': found,
                            'width': width, 'height': height,
                            'classification': 'texture' if width and height else 'geometry/metadata'}, chunk))
            found += 1
        else:
            result.append(({'chunk_offset': position, 'chunk_bytes': count,
                            'classification': tag.decode('ascii') + ' metadata'}, chunk))
        position += count
    assert position == len(data) and found == expected, (found, expected)
    return result


def preview_texture(raw, details):
    """Decode bounded 16-bit planes; retain source layout and mip provenance."""
    expected_bytes = 16 + details['width'] * details['height'] * 2
    padding, preview_raw, mipmaps = 0, raw, []
    if raw[8] in (0, 1, 2, 3) and raw[9] in (1, 9, 13) and len(raw) == expected_bytes + 16:
        assert raw[expected_bytes:] == bytes(16), 'Nonzero trailing PVR data'
        preview_raw, padding = raw[:expected_bytes], 16
    if raw[9] == 0x12:
        width, height = details['width'], details['height']
        assert raw[8] in (0, 1, 2) and width == height and width & (width - 1) == 0
        # The observed alternate mipmap stream has six leading zero bytes,
        # then every twiddled 16-bit level from 1x1 through the base size.
        # Verify every span and total length rather than ignoring extra data.
        position = 22
        assert raw[16:position] == bytes(6)
        for exponent in range(width.bit_length()):
            side = 1 << exponent
            end = position + side * side * 2
            assert end <= len(raw)
            mipmaps.append({'side': side, 'offset_in_chunk': position, 'bytes': end - position,
                            'sha256': digest(raw[position:end])})
            position = end
        assert position == len(raw)
        base = mipmaps[-1]
        header = bytearray(raw[:16])
        header[9] = 1
        struct.pack_into('<I', header, 4, base['bytes'] + 8)
        preview_raw = bytes(header) + raw[base['offset_in_chunk']:]
    image, fmt = decode_pvr(preview_raw)
    fmt['data_format'] = raw[9]
    extra = {'verified_trailing_zero_bytes': padding}
    if mipmaps:
        extra.update(verified_mipmap_leading_zero_bytes=6, mipmap_levels=mipmaps,
                     preview_scope='Base mip level; all smaller level spans/hashes accounted for')
    return image, fmt, extra


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', required=True)
    ap.add_argument('--member', action='append', type=int, default=[])
    ap.add_argument('--output-tag', default='pvm', help='Separate audit folder, preserving older report hashes')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    assert re.fullmatch(r'[A-Z0-9_]+\.AFS', args.archive)
    assert re.fullmatch(r'[a-z0-9-]+', args.output_tag)
    disc = Disc(next(ROOT.glob('*.cue')))
    entry = next(r for r in disc.inventory() if r['path'] == args.archive)
    archive = disc.read(entry['lba'], entry['size'])
    assert archive[:4] == b'AFS\0'
    count = struct.unpack_from('<I', archive, 4)[0]
    assert 8 + count * 8 <= len(archive)
    print('Plan:', args.archive, count, 'members; decode raw/PVMH-prefix PRS containers and walk every declared chunk.', flush=True)
    if not args.write:
        print('DRY RUN: no extraction or contact sheets written')
        return
    out = ROOT / 'work/ui/asset-audit' / args.archive[:-4] / args.output_tag
    out.mkdir(parents=True, exist_ok=True)
    textures, containers, skipped, errors = [], [], [], []
    page = None
    for index in range(count):
        offset, size = struct.unpack_from('<II', archive, 8 + index * 8)
        assert offset % 2048 == 0 and offset + size <= len(archive)
        packed = archive[offset:offset + size]
        if packed[:4] == b'PVMH':
            data, method = packed, 'uncompressed PVM'
        elif packed[1:5] == b'PVMH':
            try:
                data, used = decompress(packed)
                assert used == len(packed)
            except Exception as e:
                errors.append({'member': index, 'stage': 'PRS', 'error': repr(e)})
                continue
            method = 'native PRS'
        else:
            skipped.append({'member': index, 'bytes': size, 'prefix_hex': packed[:8].hex(),
                            'classification': 'GBIX handled by separate audit' if packed[:4] == b'GBIX' else 'outside PVMH-prefix decoder'})
            continue
        try:
            items = chunks(data)
        except Exception as e:
            errors.append({'member': index, 'stage': 'PVM chunks', 'error': repr(e)})
            continue
        record = {'member': index, 'method': method, 'packed_bytes': len(packed),
                  'decoded_bytes': len(data), 'packed_sha256': digest(packed),
                  'decoded_sha256': digest(data), 'chunks': [i for i, _ in items]}
        containers.append(record)
        for details, raw in items:
            if details['classification'] != 'texture':
                continue
            try:
                im, fmt, preview_details = preview_texture(raw, details)
            except Exception as e:
                errors.append({'member': index, 'chunk': details, 'stage': 'PVR pixels', 'error': repr(e)})
                continue
            n = len(textures)
            if n % 96 == 0:
                if page is not None:
                    page.save(out / f'contact-{n // 96 - 1:02d}.png')
                page = Image.new('RGB', (1280, 1200), '#30333a')
            thumb = im.copy()
            thumb.thumbnail((156, 80), Image.Resampling.LANCZOS)
            x, y = n % 8 * 160, n % 96 // 8 * 100
            page.paste(thumb, (x, y), thumb if thumb.mode == 'RGBA' else None)
            label = f'{index}:{details["texture_index_in_container"]}'
            ImageDraw.Draw(page).text((x, y + 81), label + f' {im.width}x{im.height}', fill='white')
            item = {'member': index, **details, **fmt, 'texture_sha256': digest(raw),
                    **preview_details,
                    'contact_page': n // 96, 'contact_cell': n % 96}
            if index in args.member:
                filename = f'member-{index:03d}-texture-{details["texture_index_in_container"]:02d}.png'
                im.save(out / filename)
                item['full_image'] = filename
            textures.append(item)
        if len(containers) % 50 == 0:
            print('PVM containers:', len(containers), '; decoded textures:', len(textures), flush=True)
    if page is not None:
        page.save(out / f'contact-{(len(textures) - 1) // 96:02d}.png')
    report = {'archive': args.archive, 'source_archive_sha256': digest(archive), 'archive_members': count,
              'PVM_containers': len(containers), 'texture_count': len(textures),
              'containers': containers, 'textures': textures, 'skipped_members': skipped,
              'unsupported_or_failed': errors,
              'format_reference': 'https://github.com/nickworonekin/puyotools/wiki/PVR-Texture',
              'scope': 'Structural/pixel discovery only; thumbnails are not complete image-text or reachability review',
              'limitations': ['Only raw PVM and PRS containers with the PVMH literal prefix are decoded.',
                              'Paletted/other unsupported PVR formats remain explicit errors.',
                              'YUV previews use the existing approximate conversion, not native GPU color proof.']}
    (out / 'texture-index.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print(f'Wrote {len(textures)} textures from {len(containers)} PVM containers; {len(errors)} errors; {len(skipped)} outside this decoder.', flush=True)


if __name__ == '__main__':
    main()
