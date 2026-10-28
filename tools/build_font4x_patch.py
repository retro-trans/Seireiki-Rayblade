"""Build the integrated Latin-only HD font candidate. Default: dry run.

No emulator replacements. Glyphs are rasterized at 4x and packed into the
existing MOJI member. Text surfaces use up to 4x per axis, capped at 1024;
512-wide logical surfaces therefore use 2x horizontally. A 2 MiB aggregate
CPU text-surface budget and allocation fallback reduce detail when necessary.
Logical layout and sprite sizes stay unchanged. Experimental, not playtested.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from build_font_patch import ROOT,BASE,START,END,font_data,metrics,unswap
from sh4_asm import Assembler

VERSION='0.1.5'
ASCII_PRINTABLE=''.join(chr(c) for c in range(32,127))
SYMBOLS='≪≫♥♪ー'
SMALL=ASCII_PRINTABLE+SYMBOLS
OLD_MEDIUM=' '+'ABCDEFGHIJKLMNOPQRSTUVWXYZ'+'abcdefghijklmnopqrstuvwxyz'+' '+'0123456789'
LATIN_MEDIUM=OLD_MEDIUM+''.join(c for c in ASCII_PRINTABLE if c not in OLD_MEDIUM)
MEDIUM=LATIN_MEDIUM+SYMBOLS
SMALL_Q=SMALL.index('?');MEDIUM_Q=MEDIUM.index('?')
SURFACE_BUDGET=2*1024*1024
SYMBOL_FONT=Path('C:/Windows/Fonts/seguisym.ttf')
SMALL_DATA=0x200
MEDIUM_DATA=0x4200
# Logical ink boxes within the existing 8-pixel-wide cells. The protected
# model-code mark keeps its own character ID; its contour is an em dash.
SYMBOL_BOXES={8: [(7,5,1,8),(7,5,1,8),(7,6,1,8),(5,7,0,6),(7,1,3,8)],
              16:[(7,9,3,8),(7,9,3,8),(7,10,3,8),(5,12,2,6),(7,2,7,8)]}
assert len(SMALL)<=128 and len(MEDIUM)<=128
assert 32+len(SMALL)-1<0xf0 and len(MEDIUM)<0xf0


def make_font(vector_path,symbol_path=SYMBOL_FONT):
    from PIL import Image,ImageDraw,ImageFont
    original=font_data();sm,md=metrics(original)
    vector=ImageFont.truetype(str(vector_path),128)
    symbol_vector=ImageFont.truetype(str(symbol_path),128)
    blob=bytearray(len(original));blob[:8]=b'RBLF4X\x00\x02'
    previews={};tables={}
    for name,chars,height,table_off,data_off in (
            ('small',SMALL,8,0x20,SMALL_DATA),('medium',MEDIUM,16,0xa0,MEDIUM_DATA)):
        atlas=Image.new('RGBA',(512,256 if height==8 else 512),(255,255,255,0));advances=[]
        for i in range(128):
            real=i if i<len(chars) else (SMALL_Q if name=='small' else MEDIUM_Q)
            ch=chars[real]
            if ch in SYMBOLS:
                width,ink_height,top,advance=SYMBOL_BOXES[height][SYMBOLS.index(ch)]
                # Tahoma lacks the double-angle glyphs; use a local symbol
                # face explicitly instead of silently rasterizing its tofu.
                face=symbol_vector if ch in '≪≫' else vector
                contour='—' if ch=='ー' else ch
                candidate=face.getmask(contour);missing=face.getmask('\U0010ffff')
                if (candidate.size,bytes(candidate))==(missing.size,bytes(missing)):
                    raise ValueError('Vector font lacks required contour '+repr(contour))
                native=None;bounds=(0,top,width,top+ink_height)
            elif name=='small':
                glyph=original[real*8:real*8+8];advance,bearing=sm[real]
                rows=[unswap(v) for v in glyph]
            elif real<64:
                glyph=original[0x300+real*16:0x300+real*16+16]
                advance,bearing=md[real];rows=[unswap(v) for v in glyph]
            else:
                idx=ord(ch)-32;advance,bearing=sm[idx]
                rows=[unswap(v) for v in original[idx*8:idx*8+8] for _ in range(2)]
            if ch not in SYMBOLS:
                native=Image.new('L',(8,height))
                for y,v in enumerate(rows):
                    for x in range(8):
                        if v&(0x80>>x):native.putpixel((x,y),255)
                bounds=native.getbbox();face=vector;contour=ch
            mask=Image.new('L',(32,height*4))
            if bounds:
                left,top,right,bottom=bounds
                canvas=Image.new('L',(256,256))
                ImageDraw.Draw(canvas).text((16,16),contour,font=face,fill=255)
                ink=canvas.crop(canvas.getbbox()).resize(((right-left)*4,(bottom-top)*4),Image.Resampling.LANCZOS)
                mask.paste(ink,(0,top*4))
            # ARGB1555 has binary alpha. Rasterize real 4x contours, not an
            # interpolated copy of the native bitmap.
            mask=mask.point(lambda v:255 if v>=128 else 0)
            base=data_off+i*height*16
            for y in range(height*4):
                bits=sum((1<<(31-x)) for x in range(32) if mask.getpixel((x,y)))
                struct.pack_into('<I',blob,base+y*4,bits)
            blob[table_off+i]=advance;advances.append(advance)
            if i<len(chars):
                glyph_rgba=Image.new('RGBA',mask.size,'white');glyph_rgba.putalpha(mask)
                atlas.paste(glyph_rgba,((i%16)*32,(i//16)*height*4))
        previews[name]=atlas;tables[name]=advances
    return bytes(blob),previews,tables


def prologue(a,regs=range(8,15),locals=0):
    for r in regs:a.push(r)
    a.emit(0x4f22)
    if locals:a.addi(-locals,15)


def epilogue(a,regs=range(8,15),locals=0):
    if locals:a.addi(locals,15)
    a.emit(0x4f26)
    for r in reversed(list(regs)):a.pop(r)
    a.emit(0x000b);a.emit(0x0009)


def section(a):
    a.pool_and_finish();a.fixups=[];a.pool=[]


def mem(a,size,ptr,offset,reg,write=False,scratch=0):
    a.rr('mov',ptr,scratch)
    if offset:a.addi(offset,scratch)
    if write:a.store(size,reg,scratch)
    else:a.load(size,scratch,reg)


def assemble(*,wide=False,small_data=SMALL_DATA,medium_data=MEDIUM_DATA,antialias=False,
             font_mode_address=None, native_font_offset=0, native_surface_exponent=0,
             native_shadow_pixels=None, native_only=False):
    assert not antialias or wide
    assert native_surface_exponent in (0,1)
    assert not native_only or (font_mode_address is None and native_font_offset==0 and native_surface_exponent==1)
    a=Assembler(BASE+START)
    a.label('raster')
    local_bytes=56 if antialias else 40 if wide else 24
    prologue(a,locals=local_bytes)
    a.lit(0x8c1f36ba,0);a.load('b',0,13);a.rr('extu.b',13,13)
    a.lit(0x8c1f36a4,0);a.load('l',0,8)
    if font_mode_address is not None:
        assert antialias and native_font_offset > 0
        a.lit(font_mode_address,0);a.load('b',0,0);a.rr('tst',0,0)
        a.branch('bf','r_selected_font')
        a.lit(native_font_offset,0);a.rr('add',0,8)
        a.label('r_selected_font')
    a.rr('mov',13,0);a.emit(0xc840);a.branch('bt','r_medium')
    a.rr('mov',4,0);a.addi(-32,0);a.emit(0xc97f);a.rr('mov',0,4)
    a.imm(len(SMALL),0);a.rr('cmp/hs',0,4);a.branch('bf','r_small_valid');a.imm(SMALL_Q,4)
    a.label('r_small_valid')
    if antialias:
        a.imm(len(SMALL)-5,0);a.rr('cmp/hs',0,4);a.unary('movt',1);a.emit(0x1f19)
    a.rr('mov',8,1);a.addi(32,1);a.rr('add',4,1);a.load('b',1,7);a.rr('extu.b',7,7)
    a.unary('shll2',4);a.unary('shll2',4);a.unary('shll2',4);a.unary('shll',4)
    if wide:a.unary('shll',4)
    a.lit(small_data,0);a.rr('add',0,8);a.rr('add',4,8);a.imm(8,11)
    a.branch('bra','r_surface');a.emit(0x0009)
    a.label('r_medium')
    a.rr('extu.w',4,4);a.imm(len(MEDIUM),0);a.rr('cmp/hs',0,4);a.branch('bf','r_medium_valid');a.imm(MEDIUM_Q,4)
    a.label('r_medium_valid')
    if antialias:
        a.imm(len(MEDIUM)-5,0);a.rr('cmp/hs',0,4);a.unary('movt',1);a.emit(0x1f19)
    a.lit(0xa0,0);a.rr('add',8,0);a.rr('add',4,0);a.load('b',0,7);a.rr('extu.b',7,7)
    a.unary('shll8',4)
    if wide:a.unary('shll',4)
    a.lit(medium_data,0);a.rr('add',0,8);a.rr('add',4,8);a.imm(16,11)
    a.label('r_surface')
    a.lit(0x8c1f36ac,0);a.load('l',0,9)
    if wide:
        mem(a,'l',9,-12,0);a.rr('add',9,0);a.emit(0x1f08) # payload end
    mem(a,'b',9,-20,1);a.store('l',1,15) # x exponent, metadata at buffer+12
    mem(a,'b',9,-19,2);a.emit(0x1f21) # mov.l r2,@(4,r15)
    mem(a,'w',9,-4,10);a.rr('extu.w',10,10);a.unary('shll',10)
    a.lit(0x8c1f36b6,0);a.load('w',0,3);a.rr('extu.w',3,3);a.rr('shld',1,3);a.unary('shll',3)
    if wide:a.emit(0x1f37) # x offset in bytes
    a.rr('add',3,9)
    a.lit(0x8c1f36b8,0);a.load('w',0,3);a.rr('extu.w',3,3);a.rr('shld',2,3)
    a.rr('mul.l',10,3);a.unary('sts.macl',3);a.rr('add',3,9)
    a.rr('shld',2,11)
    a.imm(2,0);a.rr('sub',2,0);a.imm(8 if wide else 4,4);a.rr('shld',0,4) # source row byte step
    a.imm(8,12);a.rr('shld',1,12)
    a.imm(2,0);a.rr('sub',1,0);a.imm(1,2);a.rr('shld',0,2);a.addi(-1,2);a.emit(0x1f22)
    if antialias:
        # Latin rows contain sixteen two-bit coverage samples per word;
        # protected symbols retain the prior thirty-two one-bit samples.
        a.emit(0x50f9);a.rr('tst',0,0);a.branch('bf','r_aa_counts_done')
        a.unary('shlr',12);a.unary('shll',2);a.emit(0x1f22)
        a.label('r_aa_counts_done')
    a.imm(2,2);a.rr('shld',1,2);a.emit(0x1f23) # physical shadow offset
    if native_shadow_pixels is not None:
        assert (font_mode_address is not None or native_only) and native_shadow_pixels in (1,2)
        if not native_only:
            a.lit(font_mode_address,0);a.load('b',0,0);a.rr('tst',0,0)
            a.branch('bf','r_shadow_selected')
        a.imm(native_shadow_pixels*2,0);a.emit(0x1f03)
        if not native_only:a.label('r_shadow_selected')
    a.lit(0x8c1f36b4,0);a.load('w',0,0);a.addi(-17,0);a.unary('shll',0);a.rr('mov',0,2)
    a.rr('mov',13,0);a.emit(0xc90e);a.rr('add',2,0);a.rr('extu.w',0,0);a.unary('shll',0)
    a.lit(0x8c0980a8,1);a.rr('add',1,0);a.addi(2,0);a.load('w',0,14)
    if antialias:
        # Convert the native color's RGB555 channels to RGB444 once, then
        # retain the atlas's exact alpha levels 0,85,187,255 as 0,5,11,15.
        a.rr('mov',14,1);a.unary('shlr2',1);a.unary('shlr',1);a.lit(0xf00,0);a.rr('and',0,1)
        a.rr('mov',14,2);a.unary('shlr2',2);a.lit(0xf0,0);a.rr('and',0,2);a.rr('or',2,1)
        a.unary('shlr',14);a.imm(15,0);a.rr('and',0,14);a.rr('or',1,14)
        a.imm(0,0);a.emit(0x1f0a)
        for n,alpha in enumerate((0x5000,0xb000,0xf000),11):
            a.lit(alpha,0);a.rr('or',14,0);a.emit(0x1f00|n)
    a.label('r_row')
    if wide:
        a.emit(0x50f7);a.rr('mov',9,3);a.rr('sub',0,3) # start of physical row
        a.emit(0x50f8);a.rr('cmp/hs',0,3);a.branch('bt','r_row_next')
        a.rr('add',10,3);a.emit(0x1f36) # end of physical row
        a.imm(2,0);a.emit(0x1f04) # two 32-bit halves per source row
    a.load('l',8,2);a.rr('mov',9,6);a.rr('mov',12,5);a.lit(0x8000,1)
    a.label('r_pixel')
    if antialias:
        a.emit(0x50f9);a.rr('tst',0,0);a.branch('bf','r_binary_sample')
        a.rr('mov',2,3);a.imm(-30,0);a.rr('shld',0,3);a.unary('shll2',2)
        a.branch('bra','r_coverage_color');a.emit(0x0009)
        a.label('r_binary_sample');a.unary('shll',2);a.unary('movt',3)
        a.rr('tst',3,3);a.branch('bt','r_coverage_color');a.imm(3,3)
        a.label('r_coverage_color');a.unary('shll2',3);a.rr('add',15,3);a.addi(40,3);a.load('l',3,3)
    else:
        a.unary('shll',2);a.unary('movt',3)
    a.emit(0x50f2);a.rr('shld',0,2) # mov.l @(8,r15),r0; skip source subpixels
    if wide:
        a.emit(0x50f6);a.rr('cmp/hs',0,6);a.branch('bt','r_next')
    a.rr('mov',13,0);a.emit(0xc880);a.branch('bt','r_no_bg')
    if antialias:
        a.rr('mov',3,1);a.lit(0xf000,0);a.rr('and',0,1)
        a.push(3);a.emit(0x50f4);a.rr('add',6,0);a.pop(3)
    else:
        a.imm(0,0);a.rr('tst',3,3);a.branch('bt','r_bg_zero');a.rr('mov',1,0)
        a.label('r_bg_zero');a.push(0);a.emit(0x50f4);a.rr('add',6,0);a.pop(3)
    if wide:
        a.push(2);a.emit(0x52f7);a.rr('cmp/hs',2,0);a.pop(2);a.branch('bt','r_bg_clipped')
    a.store('w',1 if antialias else 3,0)
    if wide:a.label('r_bg_clipped')
    # Recreate foreground bit after using r3 to store background color.
    a.rr('tst',3,3);a.branch('bt','r_no_fg');a.store('w',3 if antialias else 14,6)
    a.branch('bra','r_next');a.emit(0x0009)
    a.label('r_no_bg');a.rr('tst',3,3);a.branch('bt','r_no_fg');a.store('w',3 if antialias else 14,6)
    a.label('r_no_fg')
    a.label('r_next');a.addi(2,6);a.unary('dt',5);a.branch('bf','r_pixel')
    if wide:
        a.emit(0x50f4);a.addi(-1,0);a.emit(0x1f04);a.rr('tst',0,0);a.branch('bt','r_row_next')
        a.rr('mov',8,0);a.addi(4,0);a.load('l',0,2);a.rr('mov',12,5)
        a.branch('bra','r_pixel');a.emit(0x0009)
        a.label('r_row_next')
    a.rr('add',4,8);a.rr('add',10,9);a.unary('dt',11);a.branch('bf','r_row')
    a.lit(0x8c1f36b6,0);a.load('w',0,2);a.rr('add',7,2);a.store('w',2,0)
    epilogue(a,locals=local_bytes);section(a)

    a.label('allocate');prologue(a)
    mem(a,'w',8,10,9);a.rr('extu.w',9,9)
    mem(a,'w',8,12,10);a.rr('extu.w',10,10)
    for reg,name in [(9,'width'),(10,'height')]:
        a.rr('tst',reg,reg);a.branch('bf','a_nonzero_'+name)
        a.branch('bra','a_reject');a.emit(0x0009);a.label('a_nonzero_'+name)
        a.lit(1025,0);a.rr('cmp/hs',0,reg);a.branch('bf','a_bounded_'+name)
        a.branch('bra','a_reject');a.emit(0x0009);a.label('a_bounded_'+name)
    a.imm(1 if native_only else 2,11);a.imm(1 if native_only else 2,12);a.lit(257,0)
    a.rr('cmp/hs',0,9);a.branch('bf','a_height');a.imm(1,11)
    a.label('a_height');a.rr('cmp/hs',0,10);a.branch('bf','a_native_width');a.imm(1,12)
    a.label('a_native_width');a.lit(513,0)
    a.rr('cmp/hs',0,9);a.branch('bf','a_native_height');a.imm(0,11)
    a.label('a_native_height');a.rr('cmp/hs',0,10);a.branch('bf','a_scan');a.imm(0,12)
    a.label('a_scan')
    if font_mode_address is not None:
        a.lit(font_mode_address,0);a.load('b',0,0);a.rr('tst',0,0)
        a.branch('bf','a_selected_scale');a.imm(0,11);a.imm(0,12)
        if native_surface_exponent:
            # UI coordinates are 320x240. Two texels per coordinate produce
            # one texel per physical pixel at the game's 640x480 output.
            a.lit(513,0);a.rr('cmp/hs',0,9);a.branch('bt','a_native_x_done');a.imm(1,11)
            a.label('a_native_x_done')
            a.rr('cmp/hs',0,10);a.branch('bt','a_selected_scale');a.imm(1,12)
        a.label('a_selected_scale')
    a.imm(0,13);a.lit(0x8c1f0d3c,1);a.imm(48,2)
    a.label('a_scan_loop');a.load('l',1,3);a.rr('tst',3,3);a.branch('bt','a_scan_next')
    mem(a,'l',3,20,6);a.addi(32,6);a.rr('add',6,13)
    a.label('a_scan_next');a.addi(92,1);a.unary('dt',2);a.branch('bf','a_scan_loop')
    a.label('a_try');a.rr('mov',9,4);a.rr('shld',11,4);a.rr('mov',10,5);a.rr('shld',12,5)
    a.rr('mul.l',5,4);a.unary('sts.macl',14);a.unary('shll',14);a.addi(32,14)
    a.rr('mov',14,0);a.rr('add',13,0);a.lit(SURFACE_BUDGET,1);a.rr('cmp/hs',0,1);a.branch('bt','a_malloc')
    a.rr('mov',11,0);a.rr('or',12,0);a.rr('tst',0,0);a.branch('bf','a_reduce')
    a.label('a_malloc');a.rr('mov',14,4);a.imm(0,5);a.lit(0x8c03f748,0);a.emit(0x400b);a.emit(0x0009)
    a.rr('tst',0,0);a.branch('bf','a_success')
    a.rr('mov',11,1);a.rr('or',12,1);a.rr('tst',1,1);a.branch('bt','a_return')
    a.label('a_reduce');a.rr('cmp/hs',12,11);a.branch('bf','a_reduce_y');a.addi(-1,11)
    a.branch('bra','a_try');a.emit(0x0009)
    a.label('a_reduce_y');a.addi(-1,12);a.branch('bra','a_try');a.emit(0x0009)
    a.label('a_success');a.rr('mov',0,8)
    a.rr('mov',12,1);a.unary('shll8',1);a.rr('or',11,1);mem(a,'l',8,12,1,True)
    a.rr('mov',14,1);a.addi(-32,1);mem(a,'l',8,20,1,True)
    a.rr('shld',11,9);a.rr('shld',12,10)
    mem(a,'w',8,28,9,True);mem(a,'w',8,30,10,True);a.rr('mov',8,0)
    a.branch('bra','a_return');a.emit(0x0009)
    a.label('a_reject');a.imm(0,0)
    a.label('a_return');epilogue(a);section(a)

    a.label('initialize');prologue(a)
    a.rr('mov',4,8);a.rr('mov',5,12)
    mem(a,'l',8,12,9);mem(a,'l',8,20,10);mem(a,'l',8,28,11)
    a.rr('mov',8,4);a.imm(0,5);a.rr('mov',10,6);a.addi(32,6)
    a.lit(0x8c093e80,0);a.emit(0x400b);a.emit(0x0009)
    a.lit(0x58494247,1);a.store('l',1,8)
    a.imm(8,1);mem(a,'l',8,4,1,True)
    a.lit(0x400,1);a.rr('add',12,1);mem(a,'l',8,8,1,True)
    mem(a,'l',8,12,9,True)
    a.lit(0x54525650,1);mem(a,'l',8,16,1,True)
    mem(a,'l',8,20,10,True)
    a.lit(0x902 if antialias else 0x900,1);mem(a,'l',8,24,1,True)
    mem(a,'l',8,28,11,True)
    epilogue(a);section(a)

    a.label('flush');mem(a,'l',4,20,5);a.addi(32,5)
    a.lit(0x8c0a437a,0);a.emit(0x402b);a.emit(0x0009);section(a)
    if len(a.data)>END-START:raise ValueError('HD kernel exceeds reclaimed font routine: '+str(len(a.data)))
    used=len(a.data)
    return bytes(a.data)+b'\x09\x00'*((END-START-used)//2),a.labels,used


def range_code(start,end,code):
    if len(code)>end-start:raise ValueError('Hook exceeds original allocation')
    return code+b'\x09\x00'*((end-start-len(code))//2)


def make_executable(source,**options):
    payload,labels,used=assemble(**options);target=bytearray(source)
    edits=[(START,payload,'HD renderer and helpers'),
           (0x684b0,struct.pack('<I',labels['allocate']),'text surface allocator'),
           (0x22118,struct.pack('<I',labels['flush']),'cache flush size')]
    a=Assembler(BASE+0x6ab98)
    a.load('l',15,4);a.imm(123,0);a.emit(0x05fc);a.rr('extu.b',5,5)
    a.lit(labels['initialize'],3);a.emit(0x430b);a.emit(0x0009)
    a.lit(BASE+0x6abfa,3);a.emit(0x432b);a.emit(0x0009)
    # The script's append-text mode enters the original header block here.
    # Its surface already has a header and must not be cleared or execute a
    # literal pool. Keep this second entry point as an explicit skip branch.
    while a.pc<BASE+0x6abb2:a.emit(0x0009)
    assert a.pc==BASE+0x6abb2
    a.labels['header_done']=BASE+0x6abfa
    a.branch('bra','header_done');a.emit(0x0009)
    while a.pc<BASE+0x6abe0:a.emit(0x0009)
    edits.append((0x6ab98,range_code(0x6ab98,0x6abfa,a.pool_and_finish()),'clear and PVR header'))
    a=Assembler(BASE+0x22d1a)
    mem(a,'l',3,20,3);a.addi(32,3);a.lit(2047,1);a.rr('add',1,3)
    a.unary('shlr8',3);a.unary('shlr2',3);a.unary('shlr',3)
    a.lit(0x8c1716f8,1);a.store('l',3,1)
    a.lit(BASE+0x22d68,0);a.emit(0x402b);a.emit(0x0009)
    edits.append((0x22d1a,range_code(0x22d1a,0x22d68,a.pool_and_finish()),'upload sector count'))
    for off,data,_ in edits:target[off:off+len(data)]=data
    assert len(target)==len(source)
    return bytes(target),labels,used,edits


def build(vector_path,symbol_path=SYMBOL_FONT):
    source=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    target,labels,used,edits=make_executable(source)
    font,previews,tables=make_font(vector_path,symbol_path)
    from PIL import Image,ImageDraw
    preview=Image.new('RGBA',(1040,550),'#151d2a');draw=ImageDraw.Draw(preview)
    draw.text((8,8),'Small Latin font - 4x source atlas (offline asset preview)',fill='white')
    draw.text((528,8),'Medium Latin font - 4x source atlas',fill='white')
    preview.alpha_composite(previews['small'],(0,32))
    preview.alpha_composite(previews['medium'],(528,32))
    previews['atlas-preview']=preview
    afs=(ROOT/'work/source/disc/WIN00.AFS').read_bytes()
    offset,length=struct.unpack_from('<II',afs,8)
    assert len(font)==length
    patched_afs=afs[:offset]+font+afs[offset+length:]
    files={'1ST_READ.BIN':target,'WIN00.AFS':patched_afs}
    originals={'1ST_READ.BIN':source,'WIN00.AFS':afs}
    manifest={'version':VERSION,'status':'experimental; validation coverage recorded separately in work/ui',
        'integration':'native game renderer; no emulator texture replacement',
        'glyph_source_scale':4,'maximum_texture_edge':1024,'surface_budget_bytes':SURFACE_BUDGET,
        'surface_scaling':'up to 4x per axis; 512 logical pixels cap at 2x; budget/allocation fallback may reduce detail',
        'latin_only':True,'japanese_text_glyph_slots':0,'unsupported_glyph':'?',
        'small_charset':SMALL,'medium_charset':MEDIUM,
        'symbols_supported':SYMBOLS,'symbol_vector_font':symbol_path.name,
        'protected_model_dash':'U+30FC retained as a separate ID; em-dash vector contour',
        'font_format':2,'small_bitmaps_offset':SMALL_DATA,'medium_bitmaps_offset':MEDIUM_DATA,
        'kernel_bytes_used':used,'kernel_bytes_available':END-START,
        'symbols':{k:hex(v) for k,v in labels.items() if k in ('raster','allocate','initialize','flush')},
        'hooks':[{'offset':off,'length':len(data),'purpose':purpose} for off,data,purpose in edits],
        'files':{name:{'source_sha256':hashlib.sha256(originals[name]).hexdigest(),
                       'target_sha256':hashlib.sha256(data).hexdigest(),'size':len(data)} for name,data in files.items()}}
    return files,previews,tables,manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/tahoma.ttf'))
    ap.add_argument('--symbol-font',type=Path,default=SYMBOL_FONT)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,previews,tables,manifest=build(args.font,args.symbol_font)
    print('Integrated Latin font {}: {} / {} bytes of kernel space'.format(VERSION,manifest['kernel_bytes_used'],END-START))
    print('95 printable Latin characters plus five source marks; 4x contours; 1024px surface limit; 2MiB aggregate surface budget.')
    print('Logical 256x64 -> at most 1024x256. Logical 512x64 -> at most 1024x256.')
    print('No Japanese slots are retained. Original untranslated Japanese is incompatible with this Latin-only font.')
    for row in manifest['hooks']:print('Hook 0x{:x}+{}: {}'.format(row['offset'],row['length'],row['purpose']))
    if not args.write:print('DRY RUN: no game files written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():(out/name).write_bytes(data)
    for name,im in previews.items():im.save(out/(name+'-latin-4x.png'))
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Wrote experimental native HD font build:',out)


if __name__=='__main__':main()
