"""Locate/decode the chapter-card PVM atlases without altering the game.

Exports 69 English title links and original sprite rectangles for subsequent
asset rebuilding. Default dry run. Header effects/palette banks stay original.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
from PIL import Image
from build_font_patch import ROOT
from rayblade_codec import decompress
from audit_texture_archive import untwiddle_indices


def analyze():
    afs=(ROOT/'work/source/disc/WIN00.AFS').read_bytes()
    translations={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    result=[];links=[]
    for index,start in [(32,None),(36,0),(40,20),(44,40),(48,60)]:
        off,size=struct.unpack_from('<II',afs,8+8*index);packed=afs[off:off+size]
        decoded,used=decompress(packed);assert used==len(packed) and decoded[:4]==b'PVMH'
        palette=decoded.index(b'PVPL');count=struct.unpack_from('<H',decoded,palette+14)[0]
        assert decoded[palette+8]==0
        colors=np.frombuffer(decoded[palette+16:palette+16+2*count],dtype='<u2')
        texture=palette
        while True:
            texture=decoded.index(b'PVRT',texture+4)
            w,h=struct.unpack_from('<HH',decoded,texture+12)
            if w and h:break
        assert decoded[texture+8:texture+10]==bytes([0,5])
        texels=decoded[texture+16:texture+16+w*h//2]
        assert len(texels)==w*h//2
        data=np.frombuffer(texels,dtype=np.uint8)
        indices=np.column_stack((data&15,data>>4)).ravel()[untwiddle_indices(w,h)]
        values=colors[indices]
        rgba=np.stack([((values>>s&31)*255//31).astype(np.uint8) for s in (10,5,0)]+
            [((values>>15)*255).astype(np.uint8)],axis=2)
        image=Image.fromarray(rgba)
        pof=decoded.index(b'POF0');rect_start=pof+8+struct.unpack_from('<I',decoded,pof+4)[0]
        rects=[];pos=rect_start
        while True:
            width,height,cx,cy,u0,v0,u1,v1,tex_id,flags=struct.unpack_from('<HHhh6H',decoded,pos)
            if width==0:break
            assert 0<width<=512 and 0<height<=64 and u0<=256 and u1<=256 and v0<=256 and v1<=256
            rects.append({'offset':pos,'draw_size':[width,height],'anchor':[cx,cy],
                'UV_fixed_256':[u0,v0,u1,v1],'texture_id':tex_id,'flags':flags})
            pos+=20
        item={'archive':'WIN00.AFS','member':index,'resource_name':f'S_TITLE{(index-32)//4}.PVM',
            'source_archive_offset':off,'packed_bytes':size,'decoded_bytes':len(decoded),
            'packed_sha256':hashlib.sha256(packed).hexdigest(),'decoded_sha256':hashlib.sha256(decoded).hexdigest(),
            'palette_offset':palette,'palette_entries':count,'texture_offset':texture,'texture_size':[w,h],
            'pixel_format':0,'data_format':5,'rect_start':rect_start,'rectangles':rects}
        if start is not None:
            expected=20 if start<60 else 9
            assert len(rects)==(40 if start<60 else 17)
            item.update(first_chapter_index=start,title_slots=expected)
            for i in range(expected):
                key=f'names.g10.{start+i:03d}';row=translations[key]
                links.append({'id':key,'en':row['en'],'source_sha256':row['source_sha256'],
                    'member':index,'main_rectangle':2*i,'reading_rectangle':2*i+1 if 2*i+1<len(rects) else None})
        result.append((item,decoded,image))
    assert len(links)==69
    return result,{'source':'D_NAMES group 10 English chapter drafts','status':'Mapped to original image slots; English pixels not inserted yet','titles':links}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    resources,links=analyze()
    print(json.dumps([{'member':r['member'],'name':r['resource_name'],'size':r['texture_size'],
        'palette_entries':r['palette_entries'],'rectangles':len(r['rectangles']),'title_slots':r.get('title_slots')} for r,_,_ in resources],indent=2))
    if not args.write:print('DRY RUN: no decoded assets, previews or English slot map written');return
    dest=ROOT/'work/source/chapter-cards';ui=ROOT/'work/ui/asset-audit/chapter-cards'
    dest.mkdir(parents=True,exist_ok=True);ui.mkdir(parents=True,exist_ok=True)
    for info,decoded,im in resources:
        (dest/(info['resource_name']+'.dec.bin')).write_bytes(decoded)
        im.save(ui/(info['resource_name']+'.png'))
    report={'resources':[r for r,_,_ in resources],
        'observations':['Chapter-title images and optional reading overlays use 20-byte sprite records; the last title has no reading record',
            'Four title atlases cover source indices 0..68, including original unused Subtitle TBD slots',
            'UV coordinates use 256-based fractions; source pixel dimensions differ between atlases',
            'S_TITLE0 also contains bubble effects, Japanese episode-label graphics and digits; its multiple palette banks require separate handling'],
        'limits':['In-game resource selection and sprite-anchor semantics must be verified before replacement',
            'All original game resources remain unchanged; this is discovery/extraction only']}
    (dest/'resources.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    path=ROOT/'work/translation/en/ui/chapter-cards.en.json'
    path.write_text(json.dumps(links,indent=2)+'\n','utf-8')
    print('Wrote five decoded resources/previews and 69 English chapter-title links. Original game files unchanged.')


if __name__=='__main__':main()
