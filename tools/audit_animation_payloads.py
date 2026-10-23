"""Decode ANIME members for format discovery, without assuming no text.

Dry run first. Fingerprints every consumed PRS stream and searches decoded
bytes for known image/container signatures. Animation VM semantics remain
unproven; a signature scan is not a complete text/image absence proof.
"""
import argparse
from collections import Counter
import io
import json
import struct

from PIL import Image

from build_bitmap_font import ROOT,digest
from disc_inventory import Disc
from rayblade_codec import decompress

OUT=ROOT/'work/ui/asset-audit/ANIME/decoded-01'
MAGICS={'GBIX':b'GBIX','PVRT':b'PVRT','PVMH':b'PVMH','PVPL':b'PVPL','NJTL':b'NJTL',
        'PNG':b'\x89PNG\r\n\x1a\n','GIF87a':b'GIF87a','GIF89a':b'GIF89a',
        'JPEG_JFIF_start':b'\xff\xd8\xff\xe0','JPEG_EXIF_start':b'\xff\xd8\xff\xe1'}


def original():
    disc=Disc(next(ROOT.glob('*.cue')))
    row=next(r for r in disc.inventory() if r['path']=='ANIME.AFS')
    archive=disc.read(row['lba'],row['size'])
    assert archive[:4]==b'AFS\0' and struct.unpack_from('<I',archive,4)[0]==642
    members=[]
    spans=[]
    for index in range(642):
        offset,size=struct.unpack_from('<II',archive,8+8*index)
        assert offset%2048==0 and size>0 and offset+size<=len(archive)
        spans.append((offset,offset+size))
        members.append(archive[offset:offset+size])
    spans.sort()
    assert all(a[1]<=b[0] for a,b in zip(spans,spans[1:]))
    return archive,members


def inspect(index,raw):
    plain,used=decompress(raw)
    assert used==len(raw), (index,used,len(raw))
    hits=[]
    for name,magic in MAGICS.items():
        position=plain.find(magic)
        while position>=0:
            hit={'signature':name,'offset':position}
            if name.startswith('JPEG_'):
                hit['APP_segment_declared_bytes']=int.from_bytes(plain[position+4:position+6],'big')
                hit['APP_identifier_prefix_hex']=plain[position+6:position+12].hex()
                try:
                    candidate=Image.open(io.BytesIO(plain[position:]))
                    assert candidate.format=='JPEG'
                    candidate.verify()
                    hit['image_probe']={'result':'Recognized JPEG structure','dimensions':list(candidate.size)}
                except (OSError,ValueError,AssertionError) as error:
                    hit['image_probe']={'result':'No JPEG recognized/verified at this byte match','error_type':type(error).__name__}
            hits.append(hit)
            position=plain.find(magic,position+1)
    row={'member':index,'packed_bytes':len(raw),'decoded_bytes':len(plain),
         'packed_sha256':digest(raw),'decoded_sha256':digest(plain),
         'packed_prefix_hex':raw[:8].hex(),'decoded_prefix_hex':plain[:24].hex(),
         'decoded_first_byte':plain[0] if plain else None,
         'decoded_first_u32_le':struct.unpack_from('<I',plain)[0] if len(plain)>=4 else None,
         'PRS_consumption':'exact entire member','known_image_signature_hits':hits}
    return row


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,members=original()
    print('Plan: decode/fingerprint 642 ANIME members and scan full decoded spans for ten known image/container signatures.',flush=True)
    if not args.write:
        for index in (0,1,2,100,641):
            row=inspect(index,members[index])
            print(index,row['packed_bytes'],'->',row['decoded_bytes'],'bytes; exact stream consumption;',len(row['known_image_signature_hits']),'signature hits')
        print('DRY RUN: no structure index written')
        return
    rows=[]
    for index,raw in enumerate(members):
        rows.append(inspect(index,raw))
        if (index+1)%100==0:
            print('Decoded ANIME members:',index+1,flush=True)
    report={'archive':'ANIME.AFS','source_archive_sha256':digest(archive),'archive_members':642,
            'PRS_members_decoded':len(rows),'PRS_full_member_consumption':'all exact',
            'decoded_bytes':sum(r['decoded_bytes'] for r in rows),
            'unsupported_or_failed':[],
            'largest_member':max(rows,key=lambda r:r['decoded_bytes'])['member'],
            'decoded_first_byte_histogram':dict(sorted(Counter(str(r['decoded_first_byte']) for r in rows).items())),
            'decoded_small_u32_prefix_counts':dict(sorted(Counter(str(r['decoded_first_u32_le']) for r in rows
                                                               if r['decoded_first_u32_le'] is not None and r['decoded_first_u32_le']<256).items())),
            'image_signature_matches':sum(len(r['known_image_signature_hits']) for r in rows),
            'recognized_JPEG_structures':sum(h.get('image_probe',{}).get('result')=='Recognized JPEG structure'
                                              for r in rows for h in r['known_image_signature_hits']),
            'scanned_signatures':{k:v.hex() for k,v in MAGICS.items()},'members':rows,
            'classification':'Decoded binary payloads; VM/animation/table formats not semantically classified',
            'limits':['Exact PRS consumption does not classify every decoded payload or establish it is text-free',
                      'Absent known image signatures or rejected JPEG probes cannot exclude raw/signatureless textures or encoded text commands',
                      'No native animation VM execution, control-flow/reachability, image rendering or live proof',
                      'No source or translated game asset changed; latest playable build remains 0.1.32'],
            'game_build_changed':False}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'structure-index.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote',len(rows),'decoded member identities;',report['decoded_bytes'],'decoded bytes;',report['image_signature_matches'],'known signature matches. Semantics remain open.',flush=True)


if __name__=='__main__':
    main()
