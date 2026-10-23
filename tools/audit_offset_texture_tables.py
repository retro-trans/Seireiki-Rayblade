"""Audit textures in D_FACE/D_UNIT relative-offset tables missed by AFS scans.

Default dry run. Accounts for terminal/aliased pointers and compressed-stream
alignment padding. Source palette-bank-zero views are not runtime proof.
"""
import argparse
from collections import defaultdict
import json
import struct

import numpy as np
from PIL import Image,ImageDraw

from audit_effect_palettes import scalar_verify
from audit_pvm_archive import chunks,preview_texture
from audit_texture_archive import decode_pvr,untwiddle_indices
from build_bitmap_font import ROOT,digest
from disc_inventory import Disc
from rayblade_codec import decompress

FILES=('D_FACE.BIN','D_UNIT.BIN')


def original(name):
    assert name in FILES
    disc=Disc(next(ROOT.glob('*.cue')))
    record=next(r for r in disc.inventory() if r['path']==name)
    raw=disc.read(record['lba'],record['size'])
    table_bytes=struct.unpack_from('<I',raw)[0]
    assert table_bytes%4==0 and 0<table_bytes<len(raw)
    count=table_bytes//4
    groups=defaultdict(list)
    targets=[]
    for i in range(count):
        offset=i*4+struct.unpack_from('<I',raw,i*4)[0]
        assert table_bytes<=offset<=len(raw) and offset%4==0
        groups[offset].append(i)
        targets.append(offset)
    assert targets==sorted(targets) and targets[0]==table_bytes and targets[-1]==len(raw)
    starts=sorted(groups)
    spans=[{'index':groups[a][0],'aliases':groups[a],'offset':a,'bytes':b-a}
           for a,b in zip(starts,starts[1:])]
    assert all(r['bytes']>0 for r in spans)
    return raw,{'file':name,'source_sha256':digest(raw),'file_bytes':len(raw),
                'table_bytes':table_bytes,'pointer_entries':count,
                'unique_nonempty_resources':len(spans),
                'nonempty_pointer_references':count-len(groups[len(raw)]),
                'terminal_empty_indices':groups[len(raw)],'resources':spans}


def decode_record(raw,name,row,independent=False):
    blob=raw[row['offset']:row['offset']+row['bytes']]
    outer=16 if blob[:4]==b'GBIX' else 0
    plain,used=decompress(blob[outer:])
    end=outer+used
    assert end<=len(blob) and len(blob)-end<=3 and blob[end:]==bytes(len(blob)-end)
    info={**row,'source_span_sha256':digest(blob),'PRS_bytes':used,'outer_header_bytes':outer,
          'verified_zero_alignment_bytes':len(blob)-end,'decoded_bytes':len(plain),'decoded_sha256':digest(plain)}
    textures=[]
    if name=='D_FACE.BIN':
        assert outer==16 and plain[:4]==b'GBIX'
        image,fmt=decode_pvr(plain)
        textures.append((image,{'texture':0,**fmt,'texture_sha256':digest(plain)}))
    else:
        assert not outer and plain[:4]==b'PVMH'
        items=chunks(plain)
        palettes=[]
        for meta,chunk in items:
            if meta['classification']=='geometry/metadata' and chunk[16:20]==b'PVPL':
                pal=chunk[16:]
                assert struct.unpack_from('<I',pal,4)[0]+8==len(pal)
                assert pal[8:14]==bytes.fromhex('000500000000')
                count=struct.unpack_from('<H',pal,14)[0]
                assert count>0 and count%16==0 and len(pal)==16+count*2
                values=np.frombuffer(pal[16:],'<u2').reshape(-1,16)
                rgba=np.stack([((values>>s&31)*255//31).astype(np.uint8) for s in (10,5,0)]
                              +[((values>>15)*255).astype(np.uint8)],axis=2)
                palettes.append((pal,rgba))
        info['wrapped_palette_chunks']=len(palettes)
        info['palette_entries']=sum(c.shape[0]*16 for _,c in palettes)
        info['chunks']=[r for r,_ in items]
        for meta,chunk in items:
            if meta['classification']!='texture':
                continue
            w,h=meta['width'],meta['height']
            if chunk[8:12]==bytes.fromhex('00050000'):
                assert len(palettes)==1
                pal,colors=palettes[0]
                size=16+w*h//2
                assert len(chunk)-size in (0,16) and chunk[size:]==bytes(len(chunk)-size)
                trimmed=chunk[:size]
                ids=untwiddle_indices(w,h)
                data=np.frombuffer(trimmed[16:],np.uint8)
                indices=((data[ids//2]>>((ids&1)*4))&15).astype(np.uint8)
                if independent:
                    scalar_verify(trimmed,pal,indices,colors)
                image=Image.fromarray(colors[0][indices])
                details={'pixel_format':0,'data_format':5,'width':w,'height':h,
                         'palette_banks':len(colors),'preview_bank':0,'palette_sha256':digest(pal),
                         'index_plane_sha256':digest(indices.tobytes()),'trailing_zero_bytes':len(chunk)-size,
                         'independent_scalar_checked':independent}
            else:
                image,fmt,extra=preview_texture(chunk,meta)
                details={**fmt,**extra}
            textures.append((image,{'texture':meta['texture_index_in_container'],**details,
                                    'texture_sha256':digest(chunk)}))
    info['textures']=len(textures)
    return info,textures


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--file',choices=FILES,required=True)
    ap.add_argument('--write',action='store_true')
    ap.add_argument('--index',type=int,action='append',default=[])
    args=ap.parse_args()
    raw,table=original(args.file)
    print('Plan:',args.file,table['pointer_entries'],'pointers;',table['unique_nonempty_resources'],
          'distinct resources;',len(table['terminal_empty_indices']),'terminal/empty references.',flush=True)
    if not args.write:
        for row in [table['resources'][0],table['resources'][len(table['resources'])//2],table['resources'][-1]]:
            info,images=decode_record(raw,args.file,row)
            print('Resource',row['index'],'->',info['decoded_bytes'],'bytes;',len(images),'textures;',info['verified_zero_alignment_bytes'],'alignment bytes')
        print('DRY RUN: no source/image/index files written')
        return
    out=ROOT/'work/ui/asset-audit'/args.file.replace('.BIN','')/'offset-table-01'
    out.mkdir(parents=True,exist_ok=True)
    rows,textures,errors=[],[],[]
    page=None
    for k,row in enumerate(table['resources']):
        try:
            info,images=decode_record(raw,args.file,row,independent=args.file=='D_UNIT.BIN' and k in (0,len(table['resources'])-1))
            rows.append(info)
        except Exception as error:
            errors.append({**row,'error':repr(error)})
            continue
        for image,details in images:
            n=len(textures)
            if n%96==0:
                if page is not None:
                    page.save(out/f'contact-{n//96-1:02d}.png')
                page=Image.new('RGB',(1280,1200),'#30333a')
            thumb=image.copy()
            thumb.thumbnail((156,80),Image.Resampling.LANCZOS)
            x,y=(n%8)*160,(n%96//8)*100
            page.paste(thumb,(x,y),thumb if thumb.mode=='RGBA' else None)
            ImageDraw.Draw(page).text((x,y+81),f'{row["index"]}:{details["texture"]} {image.width}x{image.height}',fill='white')
            item={'resource':row['index'],'aliases':row['aliases'],**details,
                  'contact_page':n//96,'contact_cell':n%96}
            if set(row['aliases'])&set(args.index):
                name=f'resource-{row["index"]:03d}-texture-{details["texture"]:02d}.png'
                image.save(out/name)
                item['full_image']=name
            textures.append(item)
        if (k+1)%100==0:
            print('Decoded resources:',k+1,'textures:',len(textures),flush=True)
    if page is not None:
        page.save(out/f'contact-{(len(textures)-1)//96:02d}.png')
    report={**table,'decoded_resources':len(rows),'decoded_texture_count':len(textures),
            'decoded_total_bytes':sum(r['decoded_bytes'] for r in rows),
            'decoded_resources_info':rows,'textures':textures,'unsupported_or_failed':errors,
            'limits':['Source structural/pixel discovery only; actual table/resource loading and native GPU not executed',
                      'D_UNIT previews use bank zero; native palette bindings and alternate states remain unverified',
                      'Contact sheets do not establish absence of fine image text or complete runtime reachability'],
            'game_bytes_changed':False}
    (out/'texture-index.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote',len(rows),'resources,',len(textures),'textures;',len(errors),'explicit errors.',flush=True)


if __name__=='__main__':
    main()
