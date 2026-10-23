"""Three-times-detail Skies caption sprites, exact original photos. Dry first."""
import argparse
from collections import Counter
from functools import lru_cache
import json
import struct

import numpy as np
from PIL import Image, ImageDraw

from build_bitmap_font import ROOT, digest
from analyze_skies_font import read_executable, skies_glyph
from audit_texture_archive import untwiddle_indices
from build_ui_atlas_patch import pixels
from rayblade_codec import compress, decompress
from sh4_asm import Assembler

PRIOR = '0.1.39'
VERSION = '0.1.40'
OUT = ROOT / 'work/output/memory-album-draft-01'
BASE = 0x8c010000
ENTRY = BASE + 0x6b840
DRAW = 0x8c0ab970
POINTERS = (0x20f5c, 0x21084, 0x21184, 0x21220)
RESOURCE = 0x8c16ed5c + 29 * 48
RECIPE = ROOT / 'work/translation/en/ui/album-captions-current.en.json'


def dispatcher(enabled):
    a = Assembler(ENTRY)
    # Only the album gallery's slot and actual archive/member identity qualify.
    a.lit(0x8c17fba0, 0); a.load('l', 0, 0); a.rr('tst', 0, 0); a.branch('bt', 'tail')
    a.addi(38, 0); a.load('w', 0, 0); a.emit(0x881d); a.branch('bf', 'tail')
    a.lit(RESOURCE + 12, 0); a.load('l', 0, 0); a.lit(0x00d70018, 1)
    a.rr('cmp/eq', 1, 0); a.branch('bf', 'tail')
    a.lit(RESOURCE, 0); a.load('l', 0, 0); a.rr('tst', 0, 0); a.branch('bt', 'tail')
    a.addi(4, 0); a.load('l', 0, 0); a.emit(0x8823); a.branch('bf', 'tail')  # 35 textures
    a.lit(224, 0); a.rr('cmp/hs', 0, 5); a.branch('bt', 'tail')
    a.rr('mov', 5, 0); a.unary('shlr2', 0); a.unary('shlr', 0)
    a.lit('bits', 1); a.rr('add', 0, 1); a.load('b', 1, 1); a.rr('extu.b', 1, 1)
    a.rr('mov', 5, 0); a.imm(7, 2); a.rr('and', 2, 0)
    a.imm(1, 2); a.rr('shld', 0, 2); a.rr('tst', 2, 1); a.branch('bt', 'tail')
    a.emit(0x4f22)  # STS.L PR,@-R15
    a.push(4); a.push(5); a.push(6); a.emit(0xff4b)  # FMOV FR4,@-R15
    a.lit(224, 0); a.rr('add', 0, 5)
    a.lit(DRAW, 0); a.emit(0x400b); a.emit(0x0009)
    # Caption is drawn first; its opaque background replaces only the old
    # caption band. The original image then draws with that band transparent.
    a.emit(0xf4f9)  # FMOV @R15+,FR4
    a.pop(6); a.pop(5); a.pop(4); a.emit(0x4f26)
    a.label('tail'); a.lit(DRAW, 0); a.emit(0x402b); a.emit(0x0009)
    a.align(); a.label('bits')
    bits = bytearray(28)
    for i in enabled:
        bits[i // 8] |= 1 << (i % 8)
    a.data.extend(bits)
    return a.pool_and_finish()


def caption_mask(text, glyphs):
    width = sum(6 if ch == ' ' else glyphs[ch].getbbox()[2] - glyphs[ch].getbbox()[0] + 3 for ch in text)
    im = Image.new('L', (width, 24))
    x = 0
    for ch in text:
        if ch == ' ':
            x += 6
            continue
        g = glyphs[ch]; box = g.getbbox()
        crop = g.crop((box[0], 0, box[2], 24))
        im.paste(crop, (x, 0)); x += crop.width + 3
    assert x == width
    return im


def wrap(text, glyphs):
    lines, line = [], ''
    for word in text.split(' '):
        assert caption_mask(word, glyphs).width <= 186, word
        trial = (line + ' ' + word).strip()
        if line and caption_mask(trial, glyphs).width > 186:
            lines.append(line); line = word
        else:
            line = trial
    lines.append(line)
    assert len(lines) <= 3 and ' '.join(lines) == text
    return lines


def make_vq(coverage, page):
    # Exactly four opaque gray colors: the original Skies coverage blended
    # against the common original card background. VQ is lossless here.
    levels = (0, 85, 187, 255)
    colors = [0x8000 | sum((((29 * (255 - alpha) + 127) // 255) << s) for s in (10, 5, 0)) for alpha in levels]
    codebook = b''.join(struct.pack('<4H', *(colors[i >> shift & 3] for shift in (6, 4, 2, 0))) for i in range(256))
    indices = ((coverage[0::2, 0::2] << 6) | (coverage[1::2, 0::2] << 4)
               | (coverage[0::2, 1::2] << 2) | coverage[1::2, 1::2])
    linear = np.empty(512 * 256, np.uint8)
    linear[untwiddle_indices(512, 256).ravel()] = indices.ravel()
    gbix = b'GBIX' + struct.pack('<III', 8, 0x00e00000 + page, 0)
    raw = gbix + b'PVRT' + struct.pack('<IIHH', 8 + 2048 + len(linear), 0x300, 1024, 512) + codebook + linear.tobytes()
    assert len(raw) == 32 + 0x20800
    packed = gbix + compress(raw)
    assert decompress(packed[16:]) == (raw, len(packed) - 16)
    return packed, raw, colors


def expanded_dat(old):
    assert struct.unpack_from('<I', old, 12)[0] == 28
    names = []
    for i in range(28):
        p = 8 + struct.unpack_from('<I', old, 16 + i * 12)[0]
        names.append(old[p:old.index(0, p)])
    names += [f'en_cap_{i:02d}'.encode('ascii') for i in range(7)]
    payload = bytearray(struct.pack('<II', 8, 35) + bytes(35 * 12))
    for i, name in enumerate(names):
        struct.pack_into('<I', payload, 8 + i * 12, len(payload))
        payload.extend(name + b'\0')
    while len(payload) % 4:
        payload.append(0)
    # A complete ordinary POF0 list accompanies the manually relocated NJTL.
    relocs = bytes([0x40, 0x42] + [0x43] * 34)
    payload.extend(b'POF0' + struct.pack('<I', len(relocs)) + relocs)
    prefix = b'NJTL' + struct.pack('<I', len(payload) + 4) + payload
    original_start = struct.unpack_from('<I', old, 4)[0] + 4
    assert original_start == 544
    original_records = old[original_start:original_start + 224 * 20]
    overlay = bytearray()
    for i in range(224):
        page, cell = divmod(i, 32)
        x, y = cell % 5 * 192, cell // 5 * 72
        # Ninja's sprite builder divides every UV by 256, irrespective of
        # the selected texture size. Encode normalized units, not texels.
        overlay.extend(struct.pack('<HHhh6H', 64, 24, 0, -48,
                                   x//4, y//2, (x+192)//4, (y+72)//2, 28 + page, 0))
    result = prefix + original_records + overlay + old[original_start + 224 * 20:]
    assert result[len(prefix):len(prefix) + 224*20] == original_records
    assert struct.unpack_from('<I', result, 4)[0] + 4 == len(prefix)
    return result, len(prefix)


@lru_cache(maxsize=1)
def compose():
    base = ROOT / 'work/output' / PRIOR
    source = (base / 'ALBUM.AFS').read_bytes()
    members = []
    for i in range(244):
        off, size = struct.unpack_from('<II', source, 8 + i * 8)
        members.append(source[off:off+size])
    recipe = json.loads(RECIPE.read_text('utf-8'))
    rows = recipe['rows']
    assert len(rows) == 203 and len({r['sprite'] for r in rows}) == 203
    sky, _ = read_executable()
    glyphs = {chr(i): skies_glyph(sky, i, (0, 85, 187, 255)) for i in range(32, 127)}
    pages = [np.zeros((512, 1024), np.uint8) for _ in range(7)]
    allowed = {i: np.zeros((256, 256), bool) for i in range(215, 243)}
    records = []
    for row in rows:
        if not row['en']:
            continue
        i = row['sprite']; page, cell = divmod(i, 32)
        xx, yy = cell % 5 * 192, cell // 5 * 72
        lines = wrap(row['en'], glyphs)
        y = yy + (72 - len(lines) * 24) // 2
        for text in lines:
            mask = np.asarray(caption_mask(text, glyphs))
            idx = np.zeros_like(mask)
            for k, value in enumerate((0, 85, 187, 255)):
                idx[mask == value] = k
            pages[page][y:y+24, xx+3:xx+3+mask.shape[1]] = idx
            y += 24
        x, y, u, v = row['caption_box']
        allowed[row['texture_member']][y:v, x:u] = True
        records.append({'id': row['id'], 'sprite': i, 'en': row['en'], 'lines': lines,
                        'font_page': page, 'source_box': [xx, yy, xx+192, yy+72],
                        'logical_size': [64, 24], 'offset_y': 48})
    outputs, old_images = {}, {}
    for i in range(215, 243):
        raw, used = decompress(members[i][16:])
        assert used == len(members[i]) - 16
        original = pixels(raw, 256, 256)
        target = original.copy()
        target[allowed[i]] = 0
        assert np.array_equal(original[~allowed[i]], target[~allowed[i]])
        for row in rows:
            if row['texture_member'] == i:
                x, y, u, v = row['source_box']
                assert np.array_equal(original[y:y+48, x:u], target[y:y+48, x:u])
        linear = np.empty(256 * 256, '<u2')
        linear[untwiddle_indices(256, 256).ravel()] = target.ravel()
        decoded = raw[:32] + linear.tobytes()
        packed = members[i][:16] + compress(decoded)
        outputs[i] = (packed, decoded)
        old_images[i] = original
        members[i] = packed
    new_dat, sprite_start = expanded_dat(members[214])
    members[214] = new_dat
    manifest = members.pop()  # filename manifest, not an in-game picture
    for i, page in enumerate(pages):
        packed, decoded, colors = make_vq(page, i)
        outputs[243 + i] = (packed, decoded)
        members.append(packed)
    members.append(manifest)
    assert len(members) == 251 and members[250] == manifest
    required = sum((len(raw) + 2047) // 2048 * 2048 for raw in members)
    first = struct.unpack_from('<I', source, 8)[0]
    first -= max(0, (first + required - len(source) + 2047) // 2048) * 2048
    assert first >= 8 + len(members) * 8 + 8
    target = bytearray(b'AFS\0' + struct.pack('<I', len(members)) + bytes(len(members) * 8 + 8))
    target.extend(bytes(first - len(target)))
    for i, raw in enumerate(members):
        off = (len(target) + 2047) // 2048 * 2048
        target.extend(bytes(off - len(target))); target.extend(raw)
        struct.pack_into('<II', target, 8 + i * 8, off, len(raw))
    used = len(target)
    assert used <= len(source)
    target.extend(bytes(len(source) - used))
    code = dispatcher([r['sprite'] for r in records])
    source_exe = (base / '1ST_READ.BIN').read_bytes()
    exe = bytearray(source_exe)
    at = ENTRY - BASE
    assert at + len(code) <= 0x6bc00
    assert source_exe[at:at+len(code)] == b'\x09\x00' * (len(code) // 2)
    exe[at:at+len(code)] = code
    for p in POINTERS:
        assert struct.unpack_from('<I', source_exe, p)[0] == DRAW
        struct.pack_into('<I', exe, p, ENTRY)
    report = {'version': VERSION, 'source_build': PRIOR, 'source_archive_sha256': digest(source),
        'archive_sha256': digest(target), 'source_executable_sha256': digest(source_exe),
        'executable_sha256': digest(exe), 'source_caption_map_sha256': digest(RECIPE.read_bytes()),
        'captions': len(records), 'protected_photos': 224, 'protected_Coming_Soon_cells': 21,
        'original_gallery_texture_bytes': 28 * 256 * 256 * 2,
        'new_caption_texture_bytes': 7 * (2048 + 1024 * 512 // 4),
        'caption_textures': 7, 'caption_texture_dimensions': [1024, 512],
        'caption_pixel_size': [192, 72], 'logical_caption_size': [64, 24],
        'font_source': 'Original Skies 12x24 glyph pixels, unscaled, four shades',
        'method': 'Separate 3x caption sprites with lossless four-color VQ; original photo texels unchanged',
        'background': 'Common original card gray RGB555 29/29/29; five preceding 28/28/28 caption backgrounds normalized',
        'gallery_dat_sprite_start': sprite_start, 'gallery_dat_bytes': len(new_dat),
        'gallery_sprite_count': 448, 'gallery_texture_count': 35, 'archive_member_count': 251,
        'sprite_UV_units': '256 normalized units per dimension, matching native 1/256 conversion',
        'filename_manifest_member_before_after': [243, 250],
        'archive_first_data_offset': first, 'archive_used_bytes': used, 'archive_spare_bytes': len(target) - used,
        'dispatcher_address': hex(ENTRY), 'dispatcher_bytes': len(code), 'patched_draw_pointers': list(POINTERS),
        'records': records, 'resource_outputs': {str(i): {'packed_sha256': digest(p), 'decoded_sha256': digest(d),
            'packed_bytes': len(p), 'decoded_bytes': len(d)} for i, (p, d) in outputs.items()},
        'limits': ['Native registration, compression, VQ and dispatch tests are separate gates',
                   'GPU depth/alpha and live gallery navigation/appearance need a fresh-game test',
                   'The filename-only last member is moved; picture and original gallery IDs stay unchanged']}
    return bytes(target), bytes(exe), json.loads(json.dumps(report)), outputs, pages, old_images


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    archive, exe, report, outputs, pages, _ = compose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','resource_outputs')}, indent=2), flush=True)
    print('Sample:', [r for r in report['records'] if 64 <= r['sprite'] < 67], flush=True)
    if not args.write:
        print('DRY RUN: no files written')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'ALBUM.AFS').write_bytes(archive)
    (OUT / '1ST_READ.BIN').write_bytes(exe)
    (OUT / 'album-component.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    for i, (packed, decoded) in outputs.items():
        (OUT / f'member-{i:03d}.packed.bin').write_bytes(packed)
        (OUT / f'member-{i:03d}.pvr').write_bytes(decoded)
    levels = np.array([239, 156, 66, 0], np.uint8)
    for i, plane in enumerate(pages):
        Image.fromarray(levels[plane]).save(OUT / f'caption-page-{i:02d}.png')


if __name__ == '__main__':
    main()
