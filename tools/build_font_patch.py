"""Build a local VWF renderer candidate; default is a dry run.

Replaces only the original glyph rasterizer, reusing its existing code space.
The executable stays the same size, and no BSS or new memory is claimed.
This native-resolution candidate is separate from the 4x-texture investigation.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from sh4_asm import Assembler

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x8c010000
START, END = 0x6b28e, 0x6bc00
VERSION = '0.1.1'


def font_data():
    raw = (ROOT / 'work/source/disc/WIN00.AFS').read_bytes()
    offset, length = struct.unpack_from('<II', raw, 8)
    assert length == 99072
    return raw[offset:offset + length]


def unswap(v):
    return ((v & 0x55) << 1) | ((v & 0xaa) >> 1)


def metric_for(glyph, default):
    rows = [unswap(b) for b in glyph]
    right = max((x for x in range(8) if any(v & (0x80 >> x) for v in rows)), default=-1)
    left = min((x for x in range(8) if any(v & (0x80 >> x) for v in rows)), default=0)
    return (min(default, right-left+2), left) if right >= 0 else (4,0)


def metrics(font):
    small = [metric_for(font[i*8:i*8+8],8) if i<96 else (8,0) for i in range(128)]
    medium = [metric_for(font[0x300+i*16:0x300+i*16+16],8) for i in range(64)]
    return small,medium


def widths(font):
    small,medium=metrics(font)
    return bytes(v[0] for v in small),bytes(v[0] for v in medium)


def assemble(font, variable=True):
    a = Assembler(BASE + START)
    for reg in range(8, 15):
        a.push(reg)
    a.emit(0x4f22)  # sts.l pr,@-r15
    a.addi(-4,15)
    a.lit(0x8c1f36ba, 0); a.load('b',0,13); a.rr('extu.b',13,13)
    a.rr('mov',13,5); a.branch('bsr','advance'); a.emit(0x0009); a.rr('mov',0,7)
    a.store('l',2,15)
    a.lit(0x8c1f36b0,0); a.load('w',0,10); a.rr('extu.w',10,10); a.unary('shll',10)
    a.lit(0x8c1f36ac,0); a.load('l',0,9)
    a.lit(0x8c1f36b6,0); a.load('w',0,2); a.rr('extu.w',2,2); a.unary('shll',2); a.rr('add',2,9)
    a.lit(0x8c1f36b8,0); a.load('w',0,2); a.rr('extu.w',2,2)
    a.rr('mul.l',10,2); a.unary('sts.macl',2); a.rr('add',2,9)
    a.lit(0x8c1f36b4,0); a.load('w',0,0); a.addi(-17,0); a.unary('shll',0); a.rr('mov',0,2)
    a.rr('mov',13,0); a.emit(0xc90e); a.rr('add',2,0); a.rr('extu.w',0,0); a.unary('shll',0)
    a.lit(0x8c0980a8,1); a.rr('add',1,0); a.addi(2,0); a.load('w',0,14)
    a.rr('mov',13,0); a.emit(0xc840); a.branch('bt','medium')
    a.rr('mov',4,0); a.addi(-32,0); a.emit(0xc97f); a.unary('shll2',0); a.unary('shll',0)
    a.lit(0x8c1f36a4,8); a.load('l',8,8); a.rr('add',0,8)
    a.imm(8,11); a.imm(8,12); a.imm(1,4); a.branch('bra','row'); a.emit(0x0009)
    a.label('medium')
    a.rr('extu.w',4,4); a.lit(512,0); a.rr('cmp/hs',0,4); a.branch('bt','wide')
    a.unary('shll2',4); a.unary('shll2',4)
    a.lit(0x8c1f36a0,8); a.load('l',8,8); a.rr('add',4,8)
    a.imm(16,11); a.imm(8,12); a.imm(1,4); a.branch('bra','row'); a.emit(0x0009)
    a.label('wide')
    a.rr('sub',0,4); a.unary('shll2',4); a.unary('shll2',4); a.unary('shll',4)
    a.lit(0x8c1f36a0,8); a.load('l',8,8); a.rr('add',4,8); a.lit(8192,0); a.rr('add',0,8)
    a.imm(16,11); a.imm(12,12); a.imm(2,4)
    a.label('row')
    a.load('b',8,2); a.rr('extu.b',2,2)
    a.rr('mov',2,0); a.emit(0xc955); a.unary('shll',0); a.rr('mov',0,3)
    a.rr('mov',2,0); a.emit(0xc9aa); a.unary('shlr',0); a.rr('or',3,0); a.rr('mov',0,2)
    a.unary('shll16',2); a.unary('shll8',2)
    a.imm(2,0); a.rr('cmp/eq',0,4); a.branch('bf','pixels')
    a.rr('mov',8,0); a.addi(1,0); a.load('b',0,3); a.rr('extu.b',3,3)
    a.rr('mov',3,0); a.emit(0xc955); a.unary('shll',0); a.rr('mov',0,6)
    a.rr('mov',3,0); a.emit(0xc9aa); a.unary('shlr',0); a.rr('or',6,0)
    a.unary('shll16',0); a.rr('or',0,2)
    a.label('pixels')
    a.load('l',15,0);a.rr('shld',0,2)
    a.rr('mov',9,6); a.rr('mov',12,5); a.lit(0x8000,1)
    a.label('pixel')
    a.unary('shll',2); a.unary('movt',3)
    a.rr('mov',13,0); a.emit(0xc880); a.branch('bt','no_background')
    a.imm(0,0); a.rr('tst',3,3); a.branch('bt','background_zero'); a.rr('mov',1,0)
    a.label('background_zero'); a.emit(0x8161)  # mov.w r0,@(2,r6)
    a.label('no_background'); a.rr('tst',3,3); a.branch('bt','no_foreground'); a.store('w',14,6)
    a.label('no_foreground'); a.addi(2,6); a.unary('dt',5); a.branch('bf','pixel')
    a.rr('add',4,8); a.rr('add',10,9); a.unary('dt',11); a.branch('bf','row')
    a.lit(0x8c1f36b6,3); a.load('w',3,2); a.rr('add',7,2); a.store('w',2,3)
    a.addi(4,15)
    a.emit(0x4f26)  # lds.l @r15+,pr
    for reg in reversed(range(8,15)):
        a.pop(reg)
    a.emit(0x000b); a.emit(0x0009)
    a.label('advance')
    a.imm(0,2)
    a.rr('mov',5,0); a.emit(0xc840); a.branch('bt','advance_medium')
    if variable:
        a.rr('mov',4,0); a.addi(-32,0); a.emit(0xc97f); a.unary('shll',0)
        a.lit('small_widths',1); a.rr('add',0,1); a.load('b',1,0); a.rr('extu.b',0,0)
        a.addi(1,1);a.load('b',1,2);a.emit(0x000b);a.rr('extu.b',2,2)
    else:
        a.emit(0x000b); a.imm(8,0)
    a.label('advance_medium')
    a.rr('extu.w',4,0); a.lit(512,1); a.rr('cmp/hs',1,0); a.branch('bf','advance_narrow')
    a.emit(0x000b); a.imm(12,0)
    a.label('advance_narrow')
    if variable:
        a.imm(63,1); a.rr('cmp/hs',1,0); a.branch('bf','advance_latin')
        a.emit(0x000b); a.imm(8,0)
        a.label('advance_latin'); a.unary('shll',0);a.lit('medium_widths',1);a.rr('add',0,1)
        a.load('b',1,0);a.rr('extu.b',0,0);a.addi(1,1);a.load('b',1,2)
        a.emit(0x000b);a.rr('extu.b',2,2)
    else:
        a.emit(0x000b); a.imm(8,0)
    a.align()
    small_metrics,medium_metrics=metrics(font)
    small=bytes(x for pair in small_metrics for x in pair)
    medium=bytes(x for pair in medium_metrics for x in pair)
    pool_end = a.pc + len(a.pool)*4
    a.labels['small_widths'] = pool_end
    a.labels['medium_widths'] = pool_end + len(small)
    code = a.pool_and_finish() + small + medium
    if len(code) % 2:
        code += b'\x00'
    if len(code) > END - START:
        raise ValueError('Font payload exceeds original code allocation')
    return code + b'\x09\x00' * ((END - START - len(code))//2), a.labels


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    source=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    font=font_data(); payload,labels=assemble(font)
    assert len(payload)==END-START
    small,medium=widths(font)
    print('VWF {}: replace file offsets 0x{:x}..0x{:x}, {} bytes'.format(VERSION,START,END,len(payload)))
    print('Uses existing code space; executable and font asset sizes stay unchanged.')
    print('Small advances I/i/l/W/m/space:',[small[ord(c)-32] for c in 'IilWm '])
    print('Medium advances A/I/W/a/i/l/m/space:',[medium[i] for i in (1,9,23,27,35,38,39,0)])
    print('Japanese non-Latin advances are preserved (8 or 12 pixels).')
    if not args.write:
        print('DRY RUN: no patch or executable written')
        return
    out=ROOT/'work/output'/VERSION
    out.mkdir(parents=True,exist_ok=True)
    target=source[:START]+payload+source[END:]
    (out/'1ST_READ.VWF.BIN').write_bytes(target)
    patch=dict(version=VERSION,status='experimental; offline validation and emulator testing required',
               source_sha256=hashlib.sha256(source).hexdigest(),
               target_sha256=hashlib.sha256(target).hexdigest(),
               file='1ST_READ.BIN',offset=START,length=END-START,new_hex=payload.hex(),
               symbols={k:hex(v) for k,v in labels.items()},
               small_widths=list(small),medium_latin_widths=list(medium),
               small_bearings=[v[1] for v in metrics(font)[0]],
               medium_latin_bearings=[v[1] for v in metrics(font)[1]],
               texture_scale=1)
    (out/'font-patch.json').write_text(json.dumps(patch,indent=2),encoding='utf-8')
    print('Wrote experimental renderer and patch manifest to {}'.format(out))


if __name__=='__main__':
    main()
