"""Prepare native-size Skies glyphs beside the unchanged HD bank. Dry first.

The renderer's existing point sampler reads fourfold repeats of prefiltered
native pixels. No emulator replacement, vector reconstruction or per-letter
stretching. Both banks retain identical widths and character IDs.
"""
import argparse
import json
import struct
import numpy as np
from PIL import Image, ImageDraw
from build_bitmap_font import ROOT, digest
from build_font4x_patch import SMALL, MEDIUM, BASE, START, END, make_executable, mem, prologue
from build_genei_font import SMALL_DATA, MEDIUM_DATA
from build_antialias_font import LEVELS, font_bytes
from build_chapter_cards import repack
from test_outline_font import legacy_mask
from sh4_asm import Assembler
from english_text_codec import encode

VERSION, PRIOR = '0.7.3', '0.7.2'
OUT = ROOT/'work/output/native-font-candidate'
MODE = BASE+END-32
TITLE_HOOK = BASE+0x6b900
TITLE_RANGE = (BASE+0x923c,BASE+0x9420)
FRAME_CALLEE = 0x8c082268


def call(a, address):
    a.lit(address,0); a.emit(0x400b); a.emit(0x0009)


def title_hook():
    a=Assembler(TITLE_HOOK)
    prologue(a,regs=range(15),locals=4)
    a.lit(MODE,8)
    a.lit(0x8c1dbe24,0);a.load('l',0,9)
    a.lit(TITLE_RANGE[0],1);a.rr('cmp/hs',1,9);a.branch('bf','outside')
    a.lit(TITLE_RANGE[1],1);a.rr('cmp/hs',1,9);a.branch('bt','outside')
    a.load('b',8,10)
    # Held buttons are debounced locally; a repeated held X/Y cannot toggle.
    a.lit(0x8c169bac,0);a.load('l',0,0);a.addi(8,0);a.load('l',0,1)
    a.lit(0x600,0);a.rr('and',0,1)
    mem(a,'l',8,8,2);mem(a,'l',8,8,1,True)
    a.emit(0x6227)  # NOT R2,R2
    a.rr('and',2,1)
    a.lit(0x400,0);a.rr('tst',0,1);a.branch('bt','check_y');a.imm(0,10)
    a.branch('bra','selected');a.emit(0x0009)
    a.label('check_y');a.lit(0x200,0);a.rr('tst',0,1);a.branch('bt','selected');a.imm(1,10)
    a.label('selected');a.store('b',10,8)
    mem(a,'b',8,1,0);a.rr('tst',0,0);a.branch('bf','existing')
    # The original VM constructor is called synchronously. Its PC is restored
    # before returning to the main loop; no script opcode is skipped.
    a.imm(0,0);a.store('b',0,8)
    a.lit('descriptor',1);a.lit(0x8c1dbe24,0);a.store('l',1,0)
    call(a,0x8c07d978)
    a.lit(0x8c1dbe24,0);a.store('l',9,0)
    a.store('b',10,8)
    a.lit(0x8c1f24d7,0);a.load('b',0,0);a.rr('extu.b',0,0);a.emit(0x88ff)
    a.branch('bt','done')
    a.imm(1,0);mem(a,'b',8,1,0,True,scratch=1)
    a.branch('bra','redraw');a.emit(0x0009)
    a.label('existing');mem(a,'b',8,2,0);a.rr('cmp/eq',10,0);a.branch('bt','done')
    a.label('redraw')
    # The selector itself always uses a native-size surface, so it remains
    # readable while previewing either mode at a native output resolution.
    a.imm(0,0);a.store('b',0,8)
    a.lit(0x8c1f24d7,0);a.load('b',0,12);a.rr('extu.b',12,12)
    a.rr('mov',12,4);call(a,0x8c078a30)
    a.lit('native_label',0);a.rr('tst',10,10);a.branch('bt','label_selected')
    a.lit('hd_label',0)
    a.label('label_selected');a.store('l',0,15)
    a.rr('mov',12,4);a.lit(0x80,5);a.imm(0,6);a.imm(0,7);call(a,0x8c07a854)
    a.store('b',10,8);mem(a,'b',8,2,10,True)
    a.branch('bra','done');a.emit(0x0009)
    a.label('outside');mem(a,'b',8,1,0);a.rr('tst',0,0);a.branch('bt','done')
    a.lit(0x8c1f24d7,0);a.load('b',0,12);a.rr('extu.b',12,12)
    a.rr('mov',12,4);call(a,0x8c078cf0)
    a.rr('mov',12,4);call(a,0x8c0784c2)
    a.lit(0x8c1f24d7,0);a.imm(-1,1);a.store('b',1,0)
    a.imm(0,0);mem(a,'b',8,1,0,True,scratch=1);mem(a,'l',8,8,0,True,scratch=1)
    a.label('done');a.addi(4,15);a.emit(0x4f26)
    for r in reversed(range(15)):a.pop(r)
    a.lit(FRAME_CALLEE,0);a.emit(0x402b);a.emit(0x0009)
    a.align();a.label('descriptor')
    # 8A22 operands: named context 15, layer 0, x=80, y=224, template 17.
    # Its ink occupies y225..237, below the original copyright line.
    a.data.extend(bytes.fromhex('22 0f 00 0a 1c 11'))
    a.label('native_label');a.data.extend(encode('Font: Native (1x)   X:Native  Y:HD'))
    a.label('hd_label');a.data.extend(encode('Font: HD (4x)   X:Native  Y:HD'))
    raw=a.pool_and_finish()
    assert TITLE_HOOK+len(raw)<=MODE,(len(raw),MODE-TITLE_HOOK)
    return raw,a.labels


def filtering_hook():
    from build_text_filter_patch import ENTRY,SETTER
    a=Assembler(ENTRY)
    a.lit(0x8c17fba0,0);a.load('l',0,0);a.rr('tst',0,0);a.branch('bt','tail')
    a.addi(38,0);a.load('w',0,0);a.rr('extu.w',0,0);a.emit(0x883f);a.branch('bf','tail')
    a.lit(MODE,0);a.load('b',0,4)  # Native nearest / HD bilinear
    a.label('tail');a.lit(SETTER,0);a.emit(0x402b);a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=64
    return raw


def quantize(mask):
    pixels = np.asarray(mask).astype(np.int16)
    levels = np.array(LEVELS, dtype=np.int16)
    return levels[np.abs(pixels[..., None]-levels).argmin(axis=-1)].astype(np.uint8)


def native_bank(hd):
    native = bytearray(hd)
    masks, metrics = {}, []
    for small, chars, height, start in ((True, SMALL, 8, SMALL_DATA),
                                        (False, MEDIUM, 16, MEDIUM_DATA)):
        bank = 'small' if small else 'medium'
        masks[bank] = {}
        for i, char in enumerate(chars):
            original = legacy_mask(hd, char, small)
            # Uniform area integration over every 4x4 block prevents the
            # previous renderer's one-in-sixteen point decimation at 1x.
            if small and char.isascii():
                # Recover the unchanged source-shaped 12x24 cell at the HD
                # bank's normalized bearing. All small letters use 1/3 scale
                # so the ink fills the native eight-pixel line height.
                source = Image.fromarray(original).crop((4,4,16,28))
                filtered = Image.new('L',(16,height))
                filtered.paste(source.resize((4,8),Image.Resampling.BOX),(0,0))
            else:
                filtered = Image.fromarray(original).resize((16, height), Image.Resampling.BOX)
            pixels = quantize(filtered)
            if not char.isascii():
                pixels = np.where(pixels >= 85, 255, 0).astype(np.uint8)
            repeated = np.repeat(np.repeat(pixels, 4, axis=0), 4, axis=1)
            assert repeated.shape == original.shape
            masks[bank][char] = Image.fromarray(pixels)
            for y in range(height*4):
                if char.isascii():
                    assert not repeated[y, 32:].any()
                    words = [sum(LEVELS.index(int(repeated[y, half*16+x])) << (30-2*x)
                                 for x in range(16)) for half in range(2)]
                else:
                    words = [sum(int(repeated[y, half*32+x] != 0) << (31-x)
                                 for x in range(32)) for half in range(2)]
                struct.pack_into('<2I', native, start+i*height*32+y*8, *words)
            metrics.append({'bank': bank, 'character': char, 'native_bounds': masks[bank][char].getbbox(),
                            'native_mask_sha256': digest(pixels.tobytes())})
    assert native[:SMALL_DATA] == hd[:SMALL_DATA]
    return bytes(native), masks, metrics


def compose():
    base = ROOT/'work/output'/PRIOR
    source = (base/'WIN00.AFS').read_bytes()
    _, hd = font_bytes(source)
    native, masks, metrics = native_bank(hd)
    archive, packing = repack(source, {0: hd+native}, first=0x60000)
    packing['validation'] = 'Only font member 0 replaced; all 89 other payloads exact; compact SDK sector order retained'
    old_exe = (base/'1ST_READ.BIN').read_bytes()
    exe, labels, used, edits = make_executable(old_exe,
        wide=True, small_data=SMALL_DATA, medium_data=MEDIUM_DATA, antialias=True,
        font_mode_address=MODE, native_font_offset=len(hd))
    exe = bytearray(exe)
    # The later filtering and album-caption dispatchers occupy part of the
    # original kernel's NOP tail. They are independent, live code.
    assert BASE+START+used <= BASE+0x6b800
    exe[0x6b800:END] = old_exe[0x6b800:END]
    exe[MODE-BASE:MODE-BASE+32] = bytes(32)
    assert BASE+START+used < MODE
    footer,footer_labels=title_hook()
    assert old_exe[TITLE_HOOK-BASE:MODE-BASE]==b'\x09\x00'*((MODE-TITLE_HOOK)//2)
    exe[TITLE_HOOK-BASE:TITLE_HOOK-BASE+len(footer)]=footer
    assert struct.unpack_from('<I',exe,0x10150)[0]==FRAME_CALLEE
    struct.pack_into('<I',exe,0x10150,TITLE_HOOK)
    filtering=filtering_hook();exe[0x6b800:0x6b800+len(filtering)]=filtering
    report = {'version': VERSION, 'source_build': PRIOR, 'native_default': True,
        'mode_address': hex(MODE), 'native_font_offset': len(hd), 'font_member_bytes': len(hd)*2,
        'HD_bank_sha256': digest(hd), 'native_bank_sha256': digest(native),
        'combined_font_sha256': digest(hd+native), 'executable_sha256': digest(exe),
        'archive_sha256': digest(archive), 'kernel_bytes': used, 'labels': labels,
        'maximum_texture_edge': 1024, 'width_tables': 'byte-exact in both banks',
        'native_filter': 'Uniform area integration: 1/3 source scale for small, 1/2 for medium; original four alpha levels',
        'HD_pixels': 'Byte-exact original bank', 'archive_nonfont_members': '89 byte-exact',
        'archive_packing': {k:v for k,v in packing.items() if k != 'members'}, 'metrics': metrics,
        'title_hook':{'address':hex(TITLE_HOOK),'bytes':len(footer),'labels':footer_labels,
            'VM_range':[hex(v) for v in TITLE_RANGE],'named_context':15,'origin':[80,224],
            'buttons':{'X':'Native (1x)','Y':'HD (up to 4x)'},'persistence':'Current session only'},
        'pending': ['Native small-font readability and full runtime checks']}
    return bytes(exe), archive, hd+native, masks, report


def preview(masks, hd):
    im = Image.new('RGB', (640, 300), '#24282e')
    d = ImageDraw.Draw(im)
    d.text((12, 8), 'Native-size font candidate - offline, at 1x', fill='white')
    for small,y,text in ((False,40,'Touya  Zeifon  Move Type Land'),
                         (True,70,'Lv 1 Exp 87  HP 389/420'),
                         (False,110,'Melee 78  Ranged 80  Defense 70')):
        chars, table = (SMALL,0x20) if small else (MEDIUM,0xa0)
        x = 12
        for ch in text:
            mask = masks['small' if small else 'medium'][ch]
            im.paste('white', (x,y,x+mask.width,y+mask.height), mask)
            x += hd[table+chars.index(ch)]
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    exe, archive, font, masks, report = compose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('metrics','labels')}, indent=2))
    if not args.write:
        print('DRY RUN: no files written'); return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'1ST_READ.BIN').write_bytes(exe)
    (OUT/'WIN00.AFS').write_bytes(archive)
    (OUT/'font-mode-component.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    preview(masks,font).save(OUT/'native-preview.png')
    print('Wrote', OUT)


if __name__ == '__main__': main()
