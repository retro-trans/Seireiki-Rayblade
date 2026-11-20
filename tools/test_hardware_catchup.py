"""Strict SH-4 filename alignment plus integrated final-feature checks."""
import json,math,struct
from build_bitmap_font import ROOT,digest
from test_choice_map_fix import SnapCPU,map_draw
from test_native_movie_font import fresh,run,OBJ,BASE,bits


class AddressError(Exception):pass


class StrictCPU(SnapCPU):
    def read(self,address,count):
        if count in (2,4) and address%count:
            raise AddressError(f'{hex(self.pc)}: unaligned {count}-byte read at {hex(address)}')
        return super().read(address,count)


def map_case(exe,name,alignment=0,sprite=21,count=2,null_array=False,null_filename=False):
    c=fresh(exe,StrictCPU)
    c.write(OBJ+0x2000,0 if null_array else OBJ+0x2020,4)
    c.write(OBJ+0x2004,count,4)
    pointer=OBJ+0x2040+alignment
    c.write(OBJ+0x202c,0 if null_filename else pointer,4)
    for i,b in enumerate(name):c.write(pointer+i,b,1)
    raw=struct.pack('<5f3I',160.25,24.75,-.5,1.,1.,0x1234,OBJ+0x2000,OBJ+0x2100)
    c.regions[3][1][0x1000:0x1020]=raw
    c.reg[4:7]=[OBJ+0x1000,sprite,0x20]
    before=bytes(c.regions[3][1]);stack=c.reg[15];pr=c.pr;preserved=c.reg[8:15];depth=c.fr[4]
    n=run(c,0x8c07b6e0)
    expected=bytearray(raw)
    for at in (0,4,12,16):struct.pack_into('<f',expected,at,struct.unpack_from('<f',raw,at)[0]*2)
    match=name==b'wmap_en\0' and count==2 and 17<=sprite<27 and not(null_array or null_filename)
    if match:
        for at in (0,4):struct.pack_into('<f',expected,at,float(math.trunc(struct.unpack_from('<f',expected,at)[0])))
    assert c.observed==(bytes(expected),[sprite,0x20],depth),(name,alignment,sprite,count,c.observed)
    assert bytes(c.regions[3][1])==before and c.reg[15]==stack and c.pr==pr and c.reg[8:15]==preserved
    assert c.reg[0]==0x12345678 and c.reg[2]==0x8c5f0040
    return n


def alignment_check(exe):
    old=(ROOT/'work/output/0.7.23/1ST_READ.BIN').read_bytes();faults=[];steps=0;cases=0
    for alignment in (1,2,3):
        try:map_case(old,b'other\0',alignment)
        except AddressError as exc:faults.append({'filename_alignment':alignment,'error':str(exc)})
        else:raise AssertionError('Legacy unaligned MOV.L must fault under documented SH-4 alignment rules')
    for name in (b'wmap_en\0',b'other\0',b'wmap_x\0',b'\0',b'wmap_en_extra\0',b'wmap\0'):
      for alignment in range(4):
       for sprite in (0,16,17,21,26,27,129):
        for count in (0,1,2,3):
            steps+=map_case(exe,name,alignment,sprite,count);cases+=1
    for null_array,null_filename in ((True,False),(False,True)):
        steps+=map_case(exe,b'wmap_en\0',null_array=null_array,null_filename=null_filename);cases+=1
    return {'strict_alignment_cases':cases,'legacy_fault_witnesses':faults,'SH4_instructions':steps,
        'manual':'https://www.renesas.com/en/document/mas/sh-4-software-manual',
        'scope':'SH-4 integer/FPU execution with documented aligned-read checks and an SDK draw endpoint. No actual reporter filename address or fault register was captured.'}


def font_check(exe,resource=None,native_offset=0):
    from build_map_font_patch import member
    from build_font4x_patch import SMALL,MEDIUM
    from test_font4x_patch import HDCPU
    from test_outline_font import legacy_mask,expected_pixels
    if resource is None:resource=member((ROOT/'work/output/0.7.23/WIN00.AFS').read_bytes(),0)
    font=resource[native_offset:]
    assert len(font)==99072 and digest(font)=='1b909b7fc3e2755a74f2d2da5dbc0b9b67dad90d31eb808ad5ed016adb71820e'
    cases=steps=0
    for small,chars in ((True,SMALL),(False,MEDIUM)):
      for i,ch in enumerate(chars):
       for bg in (0,128):
        flags=(64 if small else 0)|bg
        c=HDCPU(exe,resource,i+32 if small else i,flags,w=64,h=32,ex=1,ey=1)
        mask=legacy_mask(font,ch,small)
        if ch.isascii():mask=mask[:,:32]
        expected=expected_pixels(c,mask,flags,12,4,shadow_pixels=1)
        steps+=c.run_until(limit=300000)
        assert c.regions[3][1]==expected,(small,ch,bg)
        assert c.read(0x8c1f36b6,2)==12+font[(0x20 if small else 0xa0)+i]
        cases+=1
    return {'Native_glyph_cases':cases,'Native_bank_sha256':digest(font),'SH4_instructions':steps,'pixels_advances_and_guards':'pass'}


def check_candidate(exe,report):
    proof={'version':report['version'],'executable_sha256':digest(exe)}
    proof['alignment']=alignment_check(exe)
    proof['original_map_contexts']=map_draw(exe)
    print('PASS: strict map filename alignment and original map contexts.',flush=True)
    proof['font']=font_check(exe)
    print('PASS: exact Native glyph pixels, advances and guards.',flush=True)
    from test_battle_target import check_candidate as target
    from test_battle_clip import check_candidate as clip
    from test_battle_grid import check_candidate as grid
    proof['target']=target(exe,report)
    proof['clip']=clip(exe,report)
    proof['grid']=grid(exe,(ROOT/'work/output/0.7.19/1ST_READ.BIN').read_bytes(),report)
    print('PASS: current target, clipping, menu selectors and movement-grid code.',flush=True)
    from test_stage6_text import check_candidate as codec
    proof['stage6_text']=codec(exe,report)
    print('PASS: Stage 6 lossless text encoding, upload worker and SDK allocation/admission.',flush=True)
    proof['scope']='Integrated current-executable SH-4 checks for safe map matching, exact Native glyphs, target/clip/grid and Stage 6 codec/SDK allocation. Heap/cache/draw endpoints and captured RAM remain bounded fixtures; physical hardware and full-game replay pending.'
    return proof


if __name__=='__main__':
    from build_hardware_catchup import compose
    exe,report=compose();print(json.dumps(alignment_check(exe),indent=2))
