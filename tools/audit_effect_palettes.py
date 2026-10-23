"""Preview original effect atlases with their wrapped external palettes.

Dry run first. Check every PRS/chunk/palette/index span, show bank zero plus
an index-color discovery view, and independently verify selected real planes.
No game files changed; palette binding and native rendering are unproven.
"""
import argparse
import json
import struct
from pathlib import PureWindowsPath

import numpy as np
from PIL import Image, ImageDraw

from audit_pvm_archive import chunks
from audit_texture_archive import untwiddle_indices
from build_bitmap_font import ROOT, digest
from disc_inventory import Disc
from rayblade_codec import decompress

OUT = ROOT/'work/ui/asset-audit/EFFECT/palette-01'
REFERENCE = 'https://github.com/nickworonekin/puyotools/blob/master/src/PuyoTools.Core/Textures/Pvr/DataCodecs/Index4DataCodec.cs'
PALETTE_REFERENCE = 'https://github.com/nickworonekin/puyotools/blob/master/src/PuyoTools.Core/Textures/Pvr/PvrPalette.cs'


def original():
    disc = Disc(next(ROOT.glob('*.cue')))
    row = next(r for r in disc.inventory() if r['path']=='EFFECT.AFS')
    raw = disc.read(row['lba'],row['size'])
    assert raw[:4] == b'AFS\0' and struct.unpack_from('<I',raw,4)[0] == 460
    positions = [struct.unpack_from('<II',raw,8+i*8) for i in range(460)]
    assert all(o%2048==0 and o+n<=len(raw) for o,n in positions)
    return raw,[raw[o:o+n] for o,n in positions]


def parse(packed):
    data,used = decompress(packed)
    assert used == len(packed) and data[:4] == b'PVMH'
    items = chunks(data)
    assert len(items)==3
    geometry,palette,texture = [raw for _,raw in items]
    assert geometry[:4] == palette[:4] == texture[:4] == b'PVRT'
    assert geometry[12:16] == palette[12:16] == bytes(4)
    meta,pal = geometry[16:],palette[16:]
    assert meta[:4] == b'NJTL' and pal[:4] == b'PVPL'
    assert struct.unpack_from('<I',pal,4)[0]+8 == len(pal)
    assert pal[8:14] == b'\0\5\0\0\0\0'
    entries = struct.unpack_from('<H',pal,14)[0]
    assert entries%16==0 and entries>0 and len(pal)==16+entries*2
    bank_count = entries//16
    list_offset,count = struct.unpack_from('<II',meta,8)
    # Some resources retain additional palette banks beyond their initial
    # NJTL declarations. Account for all colors without inventing bindings.
    assert 1<=count<=bank_count and list_offset==8
    names,selectors = [],[]
    for i in range(count):
        name_offset,flags,selector = struct.unpack_from('<III',meta,8+list_offset+i*12)
        start = 8+name_offset
        assert 0<=start<len(meta)
        end = meta.index(b'\0',start)
        names.append(meta[start:end].decode('ascii'))
        assert flags==0x01000000 and selector==i<<26
        selectors.append(hex(selector))
    assert texture[8:12] == b'\0\5\0\0'
    w,h = struct.unpack_from('<HH',texture,12)
    assert w&(w-1)==h&(h-1)==0 and 8<=min(w,h) and max(w,h)<=1024
    assert len(texture)==16+w*h//2
    morton = untwiddle_indices(w,h)
    raw = np.frombuffer(texture[16:],np.uint8)
    indices = ((raw[morton//2]>>((morton&1)*4))&15).astype(np.uint8)
    colors = np.frombuffer(pal[16:],'<u2').reshape(bank_count,16)
    rgba = np.stack([((colors>>10&31)*255//31).astype(np.uint8),
                     ((colors>>5&31)*255//31).astype(np.uint8),((colors&31)*255//31).astype(np.uint8),
                     ((colors>>15)*255).astype(np.uint8)],axis=2)
    return data,texture,pal,indices,rgba,{'width':w,'height':h,'palette_banks':bank_count,
           'palette_entries':entries,'declared_texture_bindings':count,
           'palette_banks_beyond_initial_declarations':bank_count-count,
           'names':names,'observed_selector_words':selectors,
           'pixel_format':0,'data_format':5,'palette_pixel_format':0,
           'index_plane_sha256':digest(indices.tobytes()),'palette_sha256':digest(pal),
           'texture_sha256':digest(texture),'decoded_container_sha256':digest(data)}


def scalar_verify(texture,pal,indices,rgba):
    w,h = struct.unpack_from('<HH',texture,12)
    side = min(w,h)
    for y in range(h):
        for x in range(w):
            xx,yy = x%side,y%side
            index = (x//side+y//side)*side*side
            for bit in range(side.bit_length()-1):
                index |= ((yy>>bit)&1)<<(2*bit)
                index |= ((xx>>bit)&1)<<(2*bit+1)
            value = texture[16+index//2] >> ((y&1)*4) & 15
            assert value == indices[y,x]
    for bank in range(rgba.shape[0]):
        for index in range(16):
            value = struct.unpack_from('<H',pal,16+(bank*16+index)*2)[0]
            expected = [(value>>10&31)*255//31,(value>>5&31)*255//31,(value&31)*255//31,(value>>15)*255]
            assert rgba[bank,index].tolist() == expected


def false_color(indices):
    # All sixteen source indices remain distinguishable. This is an audit
    # view, not a claim about any runtime palette or blending state.
    colors = np.array([(0,0,0)]+[(40+(i*97)%216,40+(i*53)%216,40+(i*137)%216) for i in range(1,16)],np.uint8)
    return Image.fromarray(colors[indices])


def asset_list(raw):
    assert raw.endswith(b'\x1a'), 'Expected explicit DOS end-of-file marker'
    names = raw[:-1].decode('ascii').splitlines()
    assert len(names)==460 and names[-1]=='EFFECT.ALS'
    assert all(n.lower().endswith('.pvm') for n in names[:459])
    return names[:459]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    ap.add_argument('--member',type=int,action='append',default=[])
    ap.add_argument('--extract-only',action='store_true',help='Extract selected full images against the completed existing index')
    args = ap.parse_args()
    original_archive,members = original()
    names = asset_list(members[459])
    if args.extract_only:
        assert args.member and all(0<=i<459 for i in args.member)
        index = json.loads((OUT/'texture-index.json').read_text('utf-8'))
        assert index['source_archive_sha256'] == digest(original_archive)
        for i in args.member:
            _,_,_,indices,rgba,info = parse(members[i])
            assert info['index_plane_sha256'] == index['textures'][i]['index_plane_sha256']
            print('Extract full source:',i,info['palette_banks'],'banks',flush=True)
            if args.write:
                for bank in range(info['palette_banks']):
                    Image.fromarray(rgba[bank][indices]).save(OUT/f'member-{i:03d}-bank-{bank:02d}.png')
                false_color(indices).save(OUT/f'member-{i:03d}-indices.png')
        if not args.write:
            print('DRY RUN: no selected images written')
        return
    print('Plan: 459 original palette atlases, every stored bank, bank-zero/index-color contacts; independent scalar addressing for 0/1/36/100/458.',flush=True)
    if not args.write:
        # Validate representative sources before creating extraction files.
        for i in (0,1,36,100,458):
            _,_,_,indices,rgba,info = parse(members[i])
            print(i,info['width'],info['height'],info['palette_banks'],'banks',flush=True)
        print('DRY RUN: no previews or audit written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    rows,pages,independent = [],{},[]
    for i,packed in enumerate(members[:459]):
        try:
            data,texture,pal,indices,rgba,info = parse(packed)
        except Exception as error:
            raise ValueError(f'Effect member {i} failed bounded parsing: {error}') from error
        if i in (0,1,36,100,458):
            scalar_verify(texture,pal,indices,rgba)
            independent.append({'member':i,'all_index_pixels_and_bank_colors':'exact','pixels':indices.size,
                                'palette_entries':info['palette_entries']})
        image = Image.fromarray(rgba[0][indices])
        index_view = false_color(indices)
        for name,view in (('bank-zero',image),('indices',index_view)):
            if i%96==0:
                if name in pages:
                    pages[name].save(OUT/f'{name}-contact-{i//96-1:02d}.png')
                pages[name] = Image.new('RGB',(1280,1200),'#30333a')
            thumb = view.copy()
            thumb.thumbnail((156,80),Image.Resampling.LANCZOS)
            x,y=i%8*160,i%96//8*100
            pages[name].paste(thumb,(x,y),thumb if thumb.mode=='RGBA' else None)
            ImageDraw.Draw(pages[name]).text((x,y+81),f'{i}: '+('/'.join(info['names']))[:18],fill='white')
        if i in args.member:
            for bank in range(info['palette_banks']):
                Image.fromarray(rgba[bank][indices]).save(OUT/f'member-{i:03d}-bank-{bank:02d}.png')
            index_view.save(OUT/f'member-{i:03d}-indices.png')
        rows.append({'member':i,'packed_bytes':len(packed),'packed_sha256':digest(packed),
                     'decoded_bytes':len(data),**info,'contact_page':i//96,'contact_cell':i%96})
        if (i+1)%100==0:
            print('Palette atlases decoded:',i+1,flush=True)
    for name,page in pages.items():
        page.save(OUT/f'{name}-contact-04.png')
    for i,row in enumerate(rows):
        assert PureWindowsPath(names[i]).stem.lower()==row['names'][0].lower(),(i,names[i],row['names'][0])
    report = {'archive':'EFFECT.AFS','source_archive_sha256':digest(original_archive),'archive_members':460,
              'decoded_atlases':459,'palette_banks':sum(r['palette_banks'] for r in rows),
              'palette_entries':sum(r['palette_entries'] for r in rows),
              'resources_with_extra_palette_banks':sum(r['palette_banks_beyond_initial_declarations']>0 for r in rows),
              'unsupported_or_failed':[],
              'textures':rows,'independent_scalar_checks':independent,
              'last_member':{'member':459,'classification':'ASCII internal PVM filename list with self-reference and DOS EOF',
                             'PVM_entries':459,'self_reference':'EFFECT.ALS','DOS_EOF':'0x1a','sha256':digest(members[459])},
              'contact_pages_per_view':5,'views':['bank-zero original palette','false-color source indices'],
              'format_references':[REFERENCE,PALETTE_REFERENCE],
              'palette_binding':'Initial NJTL selector sequences are bounded by each palette table; extra stored banks are accounted for without assumed runtime bindings. Native binding/rendering not executed',
              'visual_review':'pending','native_rendering':False,'game_build_changed':False,
              'limits':['Contact sheets are discovery aids, not full-resolution no-text or reachability proof',
                        'Bank zero and index-color views do not reproduce every runtime palette/blend state',
                        'All selected full-image banks are extracted, but palette animation/live appearance remain unverified']}
    (OUT/'texture-index.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote 459 decoded atlases;',report['palette_banks'],'banks; ten contact sheets; original archive unchanged.',flush=True)


if __name__ == '__main__':
    main()
