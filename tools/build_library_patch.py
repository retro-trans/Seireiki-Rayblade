"""Integrate the English library with the existing native HD font components.

Expand shared resource memory. Keep original page stack buffers after proving
all current English scrolling windows fit. Store
compressed D_PAPER in verified unused AFS prefix padding without moving other
members. Defaults to dry run; never modifies the original dump or 0.1.3 build.
"""
import argparse
import hashlib
import json
import struct
from build_font_patch import ROOT
from rayblade_codec import decompress

VERSION='0.1.4'
SHARED_CAPACITY=0x20000
LIBRARY_OFFSET=0x210
DISPLAY_CAPACITY=0x200
MEMORY_EDITS=[
    (0x104b4,4,0x10000,SHARED_CAPACITY,'shared resource allocation')
]


def build():
    base=ROOT/'work/output/0.1.3'
    manifest=json.loads((base/'font4x-patch.json').read_text())
    files={}
    for name,info in manifest['files'].items():
        data=(base/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=info['target_sha256']:
            raise ValueError('Base font component changed: '+name)
        files[name]=bytearray(data)
    original=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    if struct.unpack_from('<H',original,0x8743c+14*2)[0]!=52:
        raise ValueError('Native library resource mapping changed')
    # Validate the exact loader path: lookup category 3/index 14, then load
    # into shared-base+0x210. These are separate from D_NAMES allocation.
    for off,expected in [(0x5590a,'0ee503e4'),(0x55902,'3392'),(0x55926,'16d2')]:
        if original[off:off+len(bytes.fromhex(expected))]!=bytes.fromhex(expected):
            raise ValueError('Native library loader instruction changed at '+hex(off))
    changes=[]
    for offset,size,before,after,purpose in MEMORY_EDITS:
        if int.from_bytes(files['1ST_READ.BIN'][offset:offset+size],'little')!=before:
            raise ValueError('Unexpected executable byte at '+hex(offset))
        files['1ST_READ.BIN'][offset:offset+size]=after.to_bytes(size,'little')
        changes.append({'offset':hex(offset),'bytes':size,'before':hex(before),'after':hex(after),'purpose':purpose})
    packed=(base/'text/D_PAPER.BIN').read_bytes()
    plain,used=decompress(packed)
    library=json.loads((base/'text/library-component-report.json').read_text())
    if used!=len(packed) or hashlib.sha256(packed).hexdigest()!=library['compressed_sha256'] or hashlib.sha256(plain).hexdigest()!=library['output_sha256']:
        raise ValueError('Library component hashes changed')
    if LIBRARY_OFFSET+len(plain)>SHARED_CAPACITY:
        raise ValueError('Library exceeds expanded shared allocation')
    afs=files['WIN00.AFS'];count=struct.unpack_from('<I',afs,4)[0]
    members=[struct.unpack_from('<II',afs,8+n*8) for n in range(count)]
    destination=0x800;end=destination+len(packed)
    if 8+count*8+8>destination or end>min(off for off,size in members if size):
        raise ValueError('Library overlaps AFS metadata or existing members')
    if any(afs[destination:end]):raise ValueError('AFS destination is not unused zero padding')
    afs[destination:end]=packed
    struct.pack_into('<II',afs,8+52*8,destination,len(packed))
    base_afs=(base/'WIN00.AFS').read_bytes()
    for n,(off,size) in enumerate(members):
        if n==52:continue
        if struct.unpack_from('<II',afs,8+n*8)!=(off,size) or afs[off:off+size]!=base_afs[off:off+size]:
            raise ValueError('Unrelated archive member changed: '+str(n))
    off,size=struct.unpack_from('<II',afs,8+52*8)
    if decompress(afs[off:off+size])!=(plain,len(packed)):
        raise ValueError('Re-extracted library differs')
    report={'version':VERSION,'kind':'local English library integration; gameplay/layout validation pending',
            'base_font_build':'0.1.3','memory_edits':changes,
            'shared_allocation_bytes':SHARED_CAPACITY,'library_destination_offset':LIBRARY_OFFSET,
            'decoded_library_bytes':len(plain),'spare_shared_bytes':SHARED_CAPACITY-LIBRARY_OFFSET-len(plain),
            'display_page_buffer_bytes':DISPLAY_CAPACITY,'viewer_stack_frames':'unchanged',
            'archive_member':52,'archive_member_offset':destination,'archive_member_bytes':len(packed),
            'archive_size_unchanged':len(afs)==len(base_afs),'unrelated_archive_members':'all 89 unchanged',
            'library_payload_sha256':hashlib.sha256(plain).hexdigest(),
            'pending':['In-game library navigation/layout and memory checks']}
    manifest.update(version=VERSION,status='English library integration; gameplay/layout validation pending',
                    library=report)
    for name,data in files.items():
        manifest['files'][name]['target_sha256']=hashlib.sha256(data).hexdigest()
    return {name:bytes(data) for name,data in files.items()},manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,manifest,report=build()
    print('Library {} decoded bytes at shared+0x210; shared capacity {}, {} spare bytes.'.format(
        report['decoded_library_bytes'],report['shared_allocation_bytes'],report['spare_shared_bytes']))
    print('Library display page buffers: original 512 bytes; one shared-allocation literal edit.')
    print('WIN00 member 52 relocated to 0x800 ({} bytes); archive size and other 89 members unchanged.'.format(report['archive_member_bytes']))
    print('Memory edits:',json.dumps(report['memory_edits'][:3]))
    if not args.write:print('DRY RUN: no components written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():(out/name).write_bytes(data)
    text=out/'text';text.mkdir(exist_ok=True)
    base=ROOT/'work/output/0.1.3/text'
    for name in ['D_NAMES.BIN','D_NAMES.en.dec.bin','names-component-report.json','D_PAPER.BIN','D_PAPER.en.dec.bin','library-component-report.json']:
        (text/name).write_bytes((base/name).read_bytes())
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'library-patch-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Wrote 0.1.4 integration components; original dump and earlier builds unchanged.')


if __name__=='__main__':main()
