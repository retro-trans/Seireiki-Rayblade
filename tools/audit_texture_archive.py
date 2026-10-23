"""Render read-only contact sheets of compressed GBIX/PVRT archive members.

Default dry run. Supports 16-bit rectangular/twiddled/base-mipmap textures and
rectangular YUV422 for locating untranslated image text. YUV preview uses a
BT.601 full-range approximation, not a claim of native GPU color equivalence.
Format reference: https://github.com/nickworonekin/puyotools/wiki/PVR-Texture
"""
import argparse,hashlib,json,math,re,struct
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from build_font_patch import ROOT
from disc_inventory import Disc
from rayblade_codec import decompress


@lru_cache(maxsize=16)
def untwiddle_indices(w,h):
    assert w&(w-1)==0 and h&(h-1)==0
    y,x=np.indices((h,w),dtype=np.uint32);side=min(w,h)
    xx=x%side;yy=y%side;indices=np.zeros_like(x)
    for bit in range(side.bit_length()-1):
        indices|=((yy>>bit)&1)<<(2*bit)
        indices|=((xx>>bit)&1)<<(2*bit+1)
    indices+=(x//side+y//side)*(side*side)
    assert np.array_equal(np.sort(indices.ravel()),np.arange(w*h,dtype=np.uint32))
    return indices


def decode_pvr(data):
    p=16 if data[:4]==b'GBIX' else 0
    assert data[p:p+4]==b'PVRT'
    pixel,layout=data[p+8:p+10];w,h=struct.unpack_from('<HH',data,p+12)
    assert 0<w<=1024 and 0<h<=1024
    assert layout in (1,2,9,13),('Unsupported layout',layout)
    texels=data[p+16:]
    if layout==2:texels=texels[-w*h*2:]
    assert len(texels)==w*h*2,(w,h,len(texels),pixel,layout)
    values=np.frombuffer(texels,dtype='<u2')
    if layout in (1,2,13):values=values[untwiddle_indices(w,h)]
    else:values=values.reshape(h,w)
    if pixel==3:
        assert w%2==0
        pairs=np.frombuffer(values.astype('<u2').tobytes(),dtype=np.uint8).reshape(h,w//2,4).astype(np.float32)
        u=np.repeat(pairs[:,:,0]-128,2,axis=1);v=np.repeat(pairs[:,:,2]-128,2,axis=1)
        y=pairs[:,:,[1,3]].reshape(h,w)
        rgb=np.stack([y+1.402*v,y-.344136*u-.714136*v,y+1.772*u],axis=2)
        im=Image.fromarray(np.clip(np.rint(rgb),0,255).astype(np.uint8))
    else:
        assert pixel in (0,1,2),('Unsupported pixel format',pixel)
        def five(v):return ((v&31)*255//31).astype(np.uint8)
        if pixel==0:
            rgba=np.stack([five(values>>10),five(values>>5),five(values),((values>>15)*255).astype(np.uint8)],axis=2)
        elif pixel==1:
            rgba=np.stack([five(values>>11),((values>>5&63)*255//63).astype(np.uint8),five(values),np.full((h,w),255,np.uint8)],axis=2)
        else:
            rgba=np.stack([((values>>s&15)*17).astype(np.uint8) for s in (8,4,0,12)],axis=2)
        im=Image.fromarray(rgba)
    return im,{'pixel_format':pixel,'data_format':layout,'width':w,'height':h}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--archive',required=True)
    ap.add_argument('--write',action='store_true');ap.add_argument('--member',type=int,action='append',default=[])
    args=ap.parse_args();assert re.fullmatch(r'[A-Z0-9_]+\.AFS',args.archive)
    disc=Disc(next(ROOT.glob('*.cue')));files={r['path']:r for r in disc.inventory()};f=files[args.archive]
    header=disc.read(f['lba'],min(65536,f['size']));assert header[:4]==b'AFS\0'
    n=struct.unpack_from('<I',header,4)[0];assert 8+n*8<=len(header)
    print('Plan:',args.archive,n,'members; read/decompress/render GBIX members only; original dump read-only.',flush=True)
    if not args.write:print('DRY RUN: no contact sheets or extraction written');return
    out=ROOT/'work/ui/asset-audit'/args.archive.replace('.AFS','');out.mkdir(parents=True,exist_ok=True)
    rows=[];errors=[];page=None;counter=0;names=[];other_members=[]
    for i in range(n):
        off,size=struct.unpack_from('<II',header,8+i*8);assert off%2048==0 and off+size<=f['size']
        raw=disc.read(f['lba']+off//2048,size)
        if raw[:4]!=b'GBIX':
            other_members.append({'member':i,'bytes':size,'prefix_hex':raw[:8].hex(),
                                  'classification':'texture-list/geometry' if raw[:4]==b'NJTL' else 'not decoded by this GBIX-only audit'})
        if raw[:4]==b'NJTL':
            names=[v.decode('ascii') for v in re.findall(rb'[A-Za-z_][A-Za-z_0-9]{3,}',raw[:128]) if v not in (b'NJTL',b'POF0') and not v.startswith(b'CCCC')]
            continue
        if raw[:4]!=b'GBIX':continue
        try:
            decoded,used=decompress(raw[16:]);assert used==len(raw)-16
            assert decoded[:4]==b'GBIX','Decoded texture has no GBIX header'
            im,details=decode_pvr(decoded)
        except Exception as e:
            errors.append({'member':i,'error':repr(e)});continue
        row={'member':i,'archive_offset':off,'packed_bytes':size,'decoded_bytes':len(decoded),
            'name_hints':names,'outer_GBIX_index':struct.unpack_from('<I',raw,8)[0],
            'decoded_GBIX_index':struct.unpack_from('<I',decoded,8)[0],'packed_sha256':hashlib.sha256(raw).hexdigest(),
            'decoded_sha256':hashlib.sha256(decoded).hexdigest(),**details}
        rows.append(row)
        if counter%96==0:
            if page is not None:page.save(out/f'contact-{counter//96-1:02d}.png')
            page=Image.new('RGB',(1280,1200),'#30333a')
        thumb=im.copy();thumb.thumbnail((156,80),Image.Resampling.LANCZOS)
        cellx=(counter%8)*160;celly=(counter%96//8)*100
        if thumb.mode=='RGBA':page.paste(thumb,(cellx,celly),thumb)
        else:page.paste(thumb,(cellx,celly))
        ImageDraw.Draw(page).text((cellx,celly+81),f'{i}: '+('/'.join(names))[:20],fill='white')
        row.update(contact_page=counter//96,contact_cell=counter%96)
        if i in args.member:
            im.save(out/f'member-{i:03d}.png')
            (out/f'member-{i:03d}.pvr').write_bytes(decoded)
        counter+=1
        if counter%50==0:print('Decoded textures:',counter,flush=True)
    if page is not None:page.save(out/f'contact-{(counter-1)//96:02d}.png')
    report={'archive':args.archive,'archive_members':n,'texture_count':len(rows),'unsupported_or_failed':errors,'textures':rows,
        'non_GBIX_members':other_members,
        'coverage_limit':'Only members beginning with GBIX are decoded. Other members, including raw compressed PVM containers, require separate inspection; zero GBIX textures does not mean no textures or image text.',
        'scope':'Read-only image-text discovery; does not insert translations or prove native color equivalence',
        'reference':'https://github.com/nickworonekin/puyotools/wiki/PVR-Texture'}
    (out/'texture-index.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote',len(rows),'texture previews;',len(errors),'unsupported/failed GBIX members;',len(other_members),'non-GBIX members outside this decoder:',out,flush=True)


if __name__=='__main__':main()
