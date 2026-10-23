"""Assemble story loader/formatter hooks atop 0.1.6. Dry run by default.

Candidate components require native verification before test-disc packaging.
Original VM bytes retain their original fixed addresses; English banks live
in a separate expanded heap. Saved-game behavior still needs gameplay checks.
"""
import argparse
import json
import struct
from build_font_patch import ROOT,BASE
from build_scenario_translation import (VERSION,SCRIPT_CAPACITY,SCRATCH_CAPACITY,
    DIALOGUE_CAPACITY,BANK_POINTER_OFFSET,BANK_MAGIC,PACK_MAGIC,digest)
from sh4_asm import Assembler

SOURCE=BASE+0x80
HEAP_POINTER=BASE+0x83f0
ORIGINAL_PREFIX_CAPACITY=HEAP_POINTER-SOURCE
INIT=BASE+0x8400
LOADER=BASE+0x8800
FORMATTER=BASE+0x8c00
CAVE_END=0x9000
HEAP_BYTES=SCRIPT_CAPACITY+SCRATCH_CAPACITY


def call(a,address):
    a.lit(address,3);a.emit(0x430b);a.emit(0x0009)


def prologue(a,registers):
    a.emit(0x4f22)
    for reg in registers:a.push(reg)


def epilogue(a,registers):
    for reg in reversed(registers):a.pop(reg)
    a.emit(0x4f26);a.emit(0x000b);a.emit(0x0009)


def init_code():
    a=Assembler(INIT);prologue(a,[])
    a.lit(HEAP_BYTES,4);a.imm(0,5);call(a,0x8c03f748)
    a.lit(HEAP_POINTER,1);a.store('l',0,1)
    a.lit(SOURCE,2);a.lit(0x8c1dbf50,1);a.store('l',2,1)
    epilogue(a,[])
    return a.pool_and_finish()


def loader_code(*,pack_magic=PACK_MAGIC):
    a=Assembler(LOADER);regs=list(range(8,13));prologue(a,regs)
    a.rr('mov',4,8);a.rr('mov',5,9)
    a.lit(HEAP_POINTER,1);a.load('l',1,10)
    a.lit(BANK_POINTER_OFFSET,2);a.rr('add',10,2);a.imm(0,0);a.store('l',0,2)
    # The raw ALS list and invalid IDs keep the original reader behavior.
    a.lit(447,1);a.rr('cmp/hs',1,8);a.branch('bt','raw')
    a.lit(SCRIPT_CAPACITY,1);a.rr('add',1,10)
    a.rr('mov',10,6);a.rr('mov',8,5);a.imm(2,4);a.imm(0,7);call(a,0x8c021d9e)
    a.rr('tst',0,0);a.branch('bt','fail')
    a.load('l',10,0);a.lit(int.from_bytes(pack_magic,'little'),1)
    a.rr('cmp/eq',1,0);a.branch('bf','fail')
    a.rr('mov',10,2);a.addi(4,2);a.load('l',2,11)
    a.lit(BANK_POINTER_OFFSET,1);a.rr('cmp/hs',11,1);a.branch('bf','fail')
    a.addi(4,2);a.load('l',2,0);a.lit(SCRATCH_CAPACITY-20,1)
    a.rr('cmp/hs',0,1);a.branch('bf','fail')
    a.addi(4,2);a.load('l',2,0);a.rr('cmp/eq',8,0);a.branch('bf','fail')
    a.addi(4,2);a.load('l',2,12)
    a.rr('mov',12,0);a.addi(32,0);a.rr('cmp/hs',0,11);a.branch('bf','fail')
    a.rr('mov',10,4);a.addi(20,4);a.lit(HEAP_POINTER,1);a.load('l',1,5);call(a,0x8c0221a4)
    a.rr('cmp/eq',11,0);a.branch('bf','fail')
    a.lit(HEAP_POINTER,1);a.load('l',1,2);a.rr('add',2,12)
    a.lit(BANK_POINTER_OFFSET,1);a.rr('add',1,2);a.store('l',12,2)
    a.addi(8,12);a.load('l',12,11);a.lit(ORIGINAL_PREFIX_CAPACITY,1)
    a.rr('cmp/hs',11,1);a.branch('bf','fail')
    a.rr('mov',9,4);a.lit(HEAP_POINTER,1);a.load('l',1,5);a.rr('mov',11,6);call(a,0x8c093dc0)
    a.rr('mov',9,4);a.rr('mov',11,5);call(a,0x8c0a437a)
    a.imm(1,0);a.branch('bra','return');a.emit(0x0009)
    a.label('raw');a.rr('mov',9,6);a.rr('mov',8,5);a.imm(2,4);a.imm(0,7)
    call(a,0x8c021d9e);a.rr('tst',0,0);a.branch('bt','fail')
    a.imm(1,0);a.branch('bra','return');a.emit(0x0009)
    a.label('fail');a.imm(0,0)
    a.label('return');epilogue(a,regs)
    return a.pool_and_finish()


def formatter_code(*,bank_magic=BANK_MAGIC,word_wrap=False):
    a=Assembler(FORMATTER);regs=list(range(8,15));prologue(a,regs)
    for src,dst in [(4,8),(5,9),(6,10),(7,11)]:a.rr('mov',src,dst)
    a.lit(0x8c1dbf50,1);a.load('l',1,2);a.rr('tst',2,2);a.branch('bt','fallback')
    a.rr('mov',9,12);a.rr('sub',2,12);a.lit(ORIGINAL_PREFIX_CAPACITY,1)
    a.rr('cmp/hs',1,12);a.branch('bt','fallback')
    a.lit(HEAP_POINTER,1);a.load('l',1,2);a.rr('tst',2,2);a.branch('bt','fallback')
    a.lit(BANK_POINTER_OFFSET,1);a.rr('add',2,1);a.load('l',1,13)
    a.rr('tst',13,13);a.branch('bt','fallback')
    a.load('l',13,0);a.lit(int.from_bytes(bank_magic[:4],'little'),1)
    a.rr('cmp/eq',1,0);a.branch('bf','fallback')
    a.addi(4,13);a.load('l',13,0);a.lit(int.from_bytes(bank_magic[4:],'little'),1)
    a.rr('cmp/eq',1,0);a.branch('bf','fallback')
    a.addi(4,13);a.load('l',13,0);a.rr('cmp/hs',0,12);a.branch('bt','fallback')
    a.addi(4,13);a.load('l',13,14);a.addi(20,13)
    # Binary search sorted u16 source offsets; r12 then becomes the original
    # source consumption count, independently of English length.
    a.label('search');a.rr('tst',14,14);a.branch('bt','fallback')
    a.rr('mov',14,0);a.unary('shlr',0);a.rr('mov',0,1)
    a.unary('shll2',1);a.unary('shll',1);a.rr('mov',13,2);a.rr('add',1,2)
    a.load('w',2,3);a.rr('extu.w',3,3);a.rr('cmp/eq',12,3);a.branch('bt','found')
    a.rr('cmp/hs',12,3);a.branch('bf','lower')
    a.rr('mov',0,14);a.branch('bra','search');a.emit(0x0009)
    a.label('lower');a.rr('mov',2,13);a.addi(8,13);a.rr('sub',0,14);a.addi(-1,14)
    a.branch('bra','search');a.emit(0x0009)
    a.label('found');a.addi(2,2);a.load('w',2,12);a.rr('extu.w',12,12)
    a.addi(2,2);a.load('l',2,5)
    if word_wrap:
        # MSB marks a prewrapped stream. Clear it before pointer arithmetic;
        # widen only those streams so the legacy formatter still paginates
        # explicit newlines but no longer inserts character-count breaks.
        a.unary('shll',5);a.unary('movt',0);a.unary('shlr',5)
        a.rr('tst',0,0);a.branch('bt','keep_legacy_width');a.imm(127,10)
        a.label('keep_legacy_width')
    a.lit(HEAP_POINTER,1);a.load('l',1,2);a.rr('add',2,5)
    a.branch('bra','format');a.emit(0x0009)
    a.label('fallback');a.imm(0,12);a.rr('mov',9,5)
    a.label('format');a.rr('mov',8,4);a.rr('mov',10,6);a.rr('mov',11,7)
    # Incoming fifth argument lies above saved PR and seven registers.
    a.rr('mov',15,1);a.addi(32,1);a.load('l',1,1);a.push(1)
    call(a,0x8c07bc00);a.addi(4,15);a.rr('tst',12,12);a.branch('bt','return')
    a.rr('mov',12,0)
    a.label('return');epilogue(a,regs)
    return a.pool_and_finish()


def candidate_executable():
    directory=ROOT/'work/output/0.1.6';manifest=json.loads((directory/'font4x-patch.json').read_text('utf-8'))
    original=(directory/'1ST_READ.BIN').read_bytes()
    assert digest(original)==manifest['files']['1ST_READ.BIN']['target_sha256']
    source=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();target=bytearray(original)
    assert not any(target[HEAP_POINTER-BASE:CAVE_END])
    members=json.loads((ROOT/'work/source/scenario/manifest.json').read_text('utf-8'))['members']
    assert max(m['size'] for m in members)<=ORIGINAL_PREFIX_CAPACITY
    functions=[('scenario heap initialization',INIT,init_code()),('compressed scenario loader',LOADER,loader_code()),
               ('English formatter lookup',FORMATTER,formatter_code())]
    edits=[]
    def patch(offset,before,after,purpose):
        assert target[offset:offset+len(before)]==before,(hex(offset),purpose)
        assert len(before)==len(after)
        target[offset:offset+len(after)]=after
        edits.append({'offset':hex(offset),'bytes':len(after),'before_sha256':digest(before),
                      'after_sha256':digest(after),'purpose':purpose})
    for name,address,raw in functions:
        offset=address-BASE;assert offset+len(raw)<min(offset+0x400,CAVE_END)
        patch(offset,b'\0'*len(raw),raw,name)
    assert original[0x10352:0x10358]==source[0x10352:0x10358]
    patch(0x10354,original[0x10354:0x10358],bytes.fromhex('0b420900'),'call scenario heap initializer')
    patch(0x104c0,struct.pack('<I',0x8c010080),struct.pack('<I',INIT),'scenario heap initializer pointer')
    trampoline=struct.pack('<4HI',0xd001,0x402b,0x0009,0x0009,LOADER)
    patch(0x78270,source[0x78270:0x78270+12],trampoline,'scenario loader entry trampoline')
    patch(0x6d0a8,struct.pack('<I',0x8c07bc00),struct.pack('<I',FORMATTER),'scenario-only formatter pointer')
    patch(0x6d086,struct.pack('<H',0x400),struct.pack('<H',DIALOGUE_CAPACITY),'dialogue heap allocation')
    patch(0x6d088,struct.pack('<H',0x3ff),struct.pack('<H',DIALOGUE_CAPACITY-1),'dialogue formatter limit')
    assert DIALOGUE_CAPACITY<0x8000
    report={'version':VERSION,'kind':'scenario executable candidate; native/gameplay verification pending',
        'base_version':'0.1.6','base_executable_sha256':digest(original),'executable_sha256':digest(target),
        'script_capacity':SCRIPT_CAPACITY,'scratch_capacity':SCRATCH_CAPACITY,'combined_heap_bytes':HEAP_BYTES,
        'original_script_base':hex(SOURCE),'original_script_prefix_capacity':ORIGINAL_PREFIX_CAPACITY,
        'english_heap_pointer_storage':hex(HEAP_POINTER),
        'dialogue_capacity':DIALOGUE_CAPACITY,'bank_pointer_offset':BANK_POINTER_OFFSET,
        'functions':[{'name':name,'address':hex(address),'bytes':len(raw),'sha256':digest(raw)} for name,address,raw in functions],
        'edits':edits,'limits':['No test disc built by this tool','Native verification and gameplay still required',
            'Held commands retain their original untranslated payloads; Latin font cannot display original Japanese']}
    return bytes(target),report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    exe,report=candidate_executable();print(json.dumps(report,indent=2))
    if not args.write:print('DRY RUN: no executable candidate written.');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    (out/'1ST_READ.BIN').write_bytes(exe)
    (out/'scenario-patch-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote candidate for native testing; not a test disc:',out)


if __name__=='__main__':main()
