"""Independently check all ten newly decoded MAP mip levels. Dry run first.

Runs native PRS against the unchanged original resource. No asset edits.
"""
import argparse
import json
import struct

import numpy as np

from audit_map_formats import OUT,original,decode
from audit_texture_archive import decode_pvr
from build_bitmap_font import ROOT,digest
from check_native_text_components import verify


def check():
    archive,members=original()
    packed=members[124]
    plain,image,fmt,extra=decode(packed)
    assert plain==(OUT/'member-124-decoded.pvr').read_bytes()
    raw=plain[16:]
    assert raw[16:22]==bytes(6) and raw[8:12]==b'\1\x12\0\0'
    offset=22
    levels=[]
    for exponent in range(10):
        side=1<<exponent
        size=side*side*2
        payload=raw[offset:offset+size]
        assert len(payload)==size
        expected=np.zeros((side,side,4),np.uint8)
        for y in range(side):
            for x in range(side):
                address=0
                for bit in range(exponent):
                    address+=((x>>bit)&1)<<(2*bit+1)
                    address+=((y>>bit)&1)<<(2*bit)
                value=int.from_bytes(payload[2*address:2*address+2],'little')
                expected[y,x]=[(value>>11)*255//31,((value>>5)&63)*255//63,(value&31)*255//31,255]
        header=bytearray(raw[:16])
        header[9]=1
        struct.pack_into('<I',header,4,size+8)
        struct.pack_into('<HH',header,12,side,side)
        rendered,_=decode_pvr(bytes(header)+payload)
        assert np.array_equal(expected,np.asarray(rendered))
        if side==512:
            assert rendered.tobytes()==image.tobytes()
        source_level=extra['mipmap_levels'][exponent]
        assert source_level=={'side':side,'offset_in_chunk':offset,'bytes':size,'sha256':digest(payload)}
        levels.append({'side':side,'pixels':side*side,'offset_in_chunk':offset,
                       'stored_bytes':size,'source_sha256':digest(payload),'scalar_RGBA':'exact'})
        offset+=size
    assert offset==len(raw)
    exe=(ROOT/'work/output/0.1.32/1ST_READ.BIN').read_bytes()
    steps=verify(exe,packed[16:],plain,len(plain),instruction_limit=50_000_000)
    return {'source_build':'0.1.32','source_archive_sha256':digest(archive),
            'member':124,'packed_sha256':digest(packed),'decoded_sha256':digest(plain),
            'executable_sha256':digest(exe),'mip_levels':levels,
            'independent_pixels_checked':sum(r['pixels'] for r in levels),
            'all_declared_texture_bytes_accounted_for':True,
            'native_PRS_instructions':steps,'native_decoded_bytes':len(plain),
            'native_guard_and_ABI':'pass','game_build_changed':False,
            'scope':'Original source decoding/format discovery only; no native palette/texture load/submission or GPU/live proof'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: scalar RGB565/Morton verification of all ten mip levels (349525 pixels), exact original PRS native output and guards.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    result=check()
    print('PASS:',result['independent_pixels_checked'],'mip pixels;',result['native_PRS_instructions'],
          'native instructions;',result['native_decoded_bytes'],'exact source bytes.',flush=True)
    if args.write_report:
        (OUT/'native-source-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
