"""Extract source UI sprite rectangles and labeled contact sheets. Dry run first."""
import argparse,hashlib,json,struct
from pathlib import Path
from PIL import Image,ImageDraw
from build_font_patch import ROOT
from rayblade_codec import decompress
from audit_texture_archive import decode_pvr

SOURCES=[(1,2),(5,6),(87,88)]
digest=lambda b:hashlib.sha256(b).hexdigest()


def analyze():
    archive=(ROOT/'work/source/disc/WIN00.AFS').read_bytes();result=[]
    for dat_member,texture_member in SOURCES:
        off,size=struct.unpack_from('<II',archive,8+dat_member*8);data=archive[off:off+size]
        off,size=struct.unpack_from('<II',archive,8+texture_member*8);raw=archive[off:off+size]
        plain,used=decompress(raw[16:]);assert used==len(raw)-16 and raw[:4]==plain[:4]==b'GBIX'
        image,details=decode_pvr(plain);w,h=image.size
        pof=data.index(b'POF0');start=pof+8+struct.unpack_from('<I',data,pof+4)[0]
        rows=[];pos=start
        while True:
            if struct.unpack_from('<H',data,pos)[0]==0:break
            width,height,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',data,pos)
            assert 0<=u0<=u1<=256 and 0<=v0<=v1<=256
            box=[u0*w//256,v0*h//256,u1*w//256,v1*h//256]
            assert box[2]-box[0]==width and box[3]-box[1]==height
            rows.append({'id':f'win00.{dat_member:02d}.{len(rows):03d}','index':len(rows),'record_offset':pos,'draw_size':[width,height],
                'anchor':[cx,cy],'UV_fixed_256':[u0,v0,u1,v1],'source_box':box,'texture_id':tex,'flags':flags})
            pos+=20
        result.append(({'dat_member':dat_member,'texture_member':texture_member,'dat_sha256':digest(data),'packed_sha256':digest(raw),'decoded_sha256':digest(plain),
            'decoded_bytes':len(plain),'outer_GBIX_index':struct.unpack_from('<I',raw,8)[0],**details,'rectangle_start':start,'rectangles':rows},data,plain,image))
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    resources=analyze();print(json.dumps([{'dat':r['dat_member'],'texture':r['texture_member'],'size':[r['width'],r['height']],'sprites':len(r['rectangles'])} for r,*_ in resources],indent=2))
    if not args.write:print('DRY RUN: no files written');return
    dest=ROOT/'work/ui/asset-audit/ui-sprites';dest.mkdir(parents=True,exist_ok=True)
    for info,data,plain,im in resources:
        # Integer magnification is inspection only; source dimensions stay exact.
        page=Image.new('RGB',(1200,((len(info['rectangles'])+5)//6)*105),'#30333a');draw=ImageDraw.Draw(page)
        for n,r in enumerate(info['rectangles']):
            crop=im.crop(r['source_box']);scale=min(4,180//max(crop.width,1),76//max(crop.height,1));scale=max(scale,1)
            crop=crop.resize((crop.width*scale,crop.height*scale),Image.Resampling.NEAREST);x=n%6*200;y=n//6*105
            page.paste(crop,(x,y),crop);draw.text((x,y+79),f'{n}: '+str(r['source_box']),fill='white')
        page.save(dest/f"member-{info['dat_member']:02d}-sprites.png")
    (dest/'rectangles.json').write_text(json.dumps({'resources':[r for r,*_ in resources],'scope':'Source sprite audit only; English pixels not inserted'},indent=2)+'\n','utf-8')
    print('Wrote source sprite contact sheets and exact rectangle coordinates.')


if __name__=='__main__':main()
