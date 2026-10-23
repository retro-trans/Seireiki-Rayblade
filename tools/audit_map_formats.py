"""Resolve MAP's alternate mipmap and explicit dummy resource. Dry run first.

Preserves the historical GBIX audit. New discovery views include every real
GBIX texture; non-GBIX members remain separately accounted for.
"""
import argparse
import json
import struct

from PIL import Image,ImageDraw

from audit_pvm_archive import preview_texture
from build_bitmap_font import ROOT,digest
from disc_inventory import Disc
from rayblade_codec import decompress

OUT=ROOT/'work/ui/asset-audit/MAP/formats-01'


def original():
    disc=Disc(next(ROOT.glob('*.cue')))
    row=next(r for r in disc.inventory() if r['path']=='MAP.AFS')
    archive=disc.read(row['lba'],row['size'])
    assert archive[:4]==b'AFS\0' and struct.unpack_from('<I',archive,4)[0]==523
    members=[]
    for index in range(523):
        offset,size=struct.unpack_from('<II',archive,8+8*index)
        assert offset%2048==0 and offset+size<=len(archive)
        members.append(archive[offset:offset+size])
    return archive,members


def decode(packed):
    assert packed[:8]==b'GBIX\x08\0\0\0'
    plain,used=decompress(packed[16:])
    assert used==len(packed)-16 and plain[:4]==b'GBIX' and plain[16:20]==b'PVRT'
    width,height=struct.unpack_from('<HH',plain,28)
    chunk=plain[16:]
    assert struct.unpack_from('<I',chunk,4)[0]+8==len(chunk)
    image,fmt,extra=preview_texture(chunk,{'width':width,'height':height})
    assert fmt['width']==width and fmt['height']==height
    return plain,image,fmt,extra


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    archive,members=original()
    dummy=members[428]
    assert len(dummy)==38 and dummy[:16]==bytes.fromhex('47424958080000008001000000000000')
    assert dummy[16:]==b'This File is Dummy!!\r\n'
    plain,image,fmt,extra=decode(members[124])
    assert fmt=={'pixel_format':1,'data_format':18,'width':512,'height':512}
    assert len(extra['mipmap_levels'])==10 and len(plain)==699088
    print('Plan: 398 real MAP GBIX textures, 124 other members; member 124 has ten bounded RGB565 mip levels; 428 is an explicit dummy.',flush=True)
    if not args.write:
        print('DRY RUN: no previews or index written')
        return
    old=json.loads((ROOT/'work/ui/asset-audit/MAP/texture-index.json').read_text('utf-8'))
    baseline={r['member']:r for r in old['textures']}
    assert len(baseline)==397
    rows,others=[],[]
    page=None
    OUT.mkdir(parents=True,exist_ok=True)
    for index,packed in enumerate(members):
        if packed[:4]!=b'GBIX':
            others.append({'member':index,'bytes':len(packed),'prefix_hex':packed[:8].hex(),
                           'sha256':digest(packed),'classification':'NJTL geometry/texture-list prefix' if packed[:4]==b'NJTL' else 'Outside standalone GBIX decoder'})
            continue
        if index==428:
            continue
        plain,image,fmt,extra=decode(packed)
        if index in baseline:
            prior=baseline[index]
            assert prior['packed_sha256']==digest(packed) and prior['decoded_sha256']==digest(plain)
            assert all(prior[k]==v for k,v in fmt.items())
        else:
            assert index==124
        row={'member':index,'packed_bytes':len(packed),'decoded_bytes':len(plain),
             'packed_sha256':digest(packed),'decoded_sha256':digest(plain),
             'decoded_RGBA_or_RGB_pixels_sha256':digest(image.tobytes()),**fmt,**extra}
        n=len(rows)
        if n%96==0:
            if page is not None:
                page.save(OUT/f'contact-{n//96-1:02d}.png')
            page=Image.new('RGB',(1280,1200),'#30333a')
        thumb=image.copy()
        thumb.thumbnail((156,80),Image.Resampling.LANCZOS)
        x,y=n%8*160,n%96//8*100
        page.paste(thumb,(x,y),thumb if thumb.mode=='RGBA' else None)
        ImageDraw.Draw(page).text((x,y+81),f'{index}: {fmt["width"]}x{fmt["height"]}',fill='white')
        row.update(contact_page=n//96,contact_cell=n%96)
        rows.append(row)
        if index==124:
            image.save(OUT/'member-124-base.png')
            (OUT/'member-124-decoded.pvr').write_bytes(plain)
        if len(rows)%100==0:
            print('Decoded MAP textures:',len(rows),flush=True)
    page.save(OUT/'contact-04.png')
    assert len(rows)==398 and len(others)==124
    report={'archive':'MAP.AFS','source_archive_sha256':digest(archive),'archive_members':523,
            'decoded_textures':398,'historical_397_texture_identities':'all exact',
            'unsupported_or_failed':[],'textures':rows,'non_GBIX_members':others,
            'dummy':{'member':428,'bytes':38,'sha256':digest(dummy),'outer_GBIX_index':384,
                     'classification':'Explicit ASCII dummy marker; not a PRS texture'},
            'historical_index':'work/ui/asset-audit/MAP/texture-index.json',
            'contact_pages':5,'visual_review':'Pending; separate reviewed evidence will record inspection',
            'limits':['124 non-GBIX members remain outside this texture decoder',
                      'Base mip preview; every smaller mip span/hash is accounted for',
                      'Contact sheets do not prove full-resolution absence or live reachability',
                      'YUV previews retain the existing approximate color conversion; no new native GPU proof'],
            'game_build_changed':False}
    (OUT/'texture-index.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote 398 map previews, five contacts and explicit dummy classification; original game unchanged.',flush=True)


if __name__=='__main__':
    main()
