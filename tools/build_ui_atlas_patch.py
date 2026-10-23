"""Integrate translated battle/trust atlas labels. Default dry run.

Retains source dimensions, formats, outer resource IDs and all DAT geometry.
Only approved label pixels in three compressed PVR members change.
"""
import argparse,json,struct
from collections import Counter
import numpy as np
from PIL import Image,ImageDraw
from extract_ui_atlases import ROOT,analyze,digest
from prepare_ui_atlas_translation import DEST,prepare
from build_chapter_cards import strip,repack
from audit_texture_archive import untwiddle_indices,decode_pvr
from rayblade_codec import compress,decompress

VERSION='0.1.20'
PRIOR='0.1.19'


def pixels(plain,w,h):
    return np.frombuffer(plain[32:],dtype='<u2')[untwiddle_indices(w,h)].copy()


def mask(text,denominator):
    if denominator in (3,4):
        # At six/eight pixels high, preserve thin source strokes and round
        # bearings to an explicit one-pixel gap. Padding keeps a common scale.
        from build_bitmap_font import ATLAS
        atlas=Image.open(ATLAS).convert('L');glyphs=[]
        for ch in text:
            if ch==' ':glyphs.append(np.zeros((24//denominator,2),np.uint8));continue
            code=ord(ch)-32;cell=atlas.crop((code%32*12,code//32*24,code%32*12+12,code//32*24+24));box=cell.getbbox();assert box
            crop=cell.crop((box[0],0,box[2],24));width=(crop.width+denominator-1)//denominator*denominator
            padded=Image.new('L',(width,24));padded.paste(crop,(0,0))
            raw=np.asarray(padded).reshape(24//denominator,denominator,width//denominator,denominator)
            glyphs.append(raw.max(axis=(1,3)))
        width=sum(g.shape[1] for g in glyphs)+len(glyphs)+1;result=np.zeros((24//denominator,width),np.uint8);x=1
        for glyph in glyphs:result[:,x:x+glyph.shape[1]]=glyph;x+=glyph.shape[1]+1
        return result
    source=strip(text);width=(source.width+denominator-1)//denominator*denominator
    padded=Image.new('L',(width,24));padded.paste(source,(0,0))
    return np.asarray(padded.resize((width//denominator,24//denominator),Image.Resampling.BOX))


def stamp(plane,text,box,denominator,color=(31,31,31)):
    x0,y0,x1,y1=box;ink=mask(text,denominator)
    h,w=ink.shape;assert w+1<=x1-x0 and h+1<=y1-y0,(text,box,ink.shape)
    x=x0+(x1-x0-w-1)//2;y=y0+(y1-y0-h-1)//2
    # ARGB1555 has binary alpha. Blend coverage into opaque tab backgrounds;
    # on transparent labels gray RGB and a dark shadow preserve the edge tone.
    def blend(xx,yy,a,target):
        old=int(plane[yy,xx]);vals=[]
        for shift,channel in zip((10,5,0),target):
            value=((old>>shift)&31) if old&0x8000 else 0
            vals.append((value*(255-a)+channel*a+127)//255)
        plane[yy,xx]=0x8000|(vals[0]<<10)|(vals[1]<<5)|vals[2]
    for yy,xx in zip(*np.nonzero(ink)):blend(x+xx+1,y+yy+1,int(ink[yy,xx]),(2,2,2))
    for yy,xx in zip(*np.nonzero(ink)):blend(x+xx,y+yy,int(ink[yy,xx]),color)
    return {'text':text,'mask_size':[w,h],'ink_box':[x,y,x+w+1,y+h+1]}


def render(info,plain,rows):
    w,h=info['width'],info['height'];before=pixels(plain,w,h);target=before.copy();allowed=np.zeros((h,w),bool);draws=[]
    for row in rows:
        x0,y0,x1,y1=row['source_box'];allowed[y0:y1,x0:x1]=True
        cell=target[y0:y1,x0:x1];original=before[y0:y1,x0:x1];cw,ch=x1-x0,y1-y0
        if row['style']=='tab':
            # Source text is white with a neutral gray shadow. Preserve the
            # colored metallic frame/background exactly while erasing letters.
            region=cell[3:13,6:cw-2];orig=original[3:13,6:cw-2]
            r=(orig>>10)&31;g=(orig>>5)&31;b=orig&31
            neutral=(orig&0x8000!=0)&(r==g)&(g==b)
            colors=orig[(orig&0x8000!=0)&~((r==g)&(g==b))]
            fill=Counter(map(int,colors)).most_common(1)[0][0]
            if row['sprite']==0:
                # Gauge heading has a heavier tinted text outline, unlike the
                # short tabs. Rebuild its label interior, keeping outer bevels.
                heading=cell[2:14,6:cw-3];old_heading=original[2:14,6:cw-3]
                heading[old_heading&0x8000!=0]=fill
            else:region[neutral]=fill
            draws.append({'id':row['id'],**stamp(cell,row['en'],[8,1,cw-4,ch-1],3)})
        elif row['style']=='icon':
            # Keep the one-pixel border. Replace the complete old kanji interior.
            fill=Counter(map(int,original[1:-1,1:-1].ravel())).most_common(1)[0][0]
            cell[1:-1,1:-1]=fill
            draws.append({'id':row['id'],**stamp(cell,row['en'],[1,1,cw-1,ch-1],3)})
        elif row['style']=='small_red':
            cell[:]=0
            draws.append({'id':row['id'],**stamp(cell,row['en'],[0,0,cw,ch],4,color=(31,10,11))})
        else:
            cell[:]=0
            for part in row.get('parts',[{'text':row['en'],'box':[0,0,cw,ch]}]):
                draws.append({'id':row['id'],**stamp(cell,part['text'],part['box'],2)})
    assert np.array_equal(before[~allowed],target[~allowed])
    selected={r['sprite'] for r in rows}
    for r in info['rectangles']:
        if r['index'] in selected:continue
        x0,y0,x1,y1=r['source_box'];assert np.array_equal(before[y0:y1,x0:x1],target[y0:y1,x0:x1]),r['id']
    linear=np.empty(w*h,dtype='<u2');linear[untwiddle_indices(w,h).ravel()]=target.ravel()
    result=plain[:32]+linear.tobytes();assert len(result)==len(plain) and result[:32]==plain[:32]
    return result,{'changed_pixels':int((before!=target).sum()),'target_sprite_count':len(rows),'draws':draws}


def make_resources(recipe):
    resources=[];replacements={};previews={}
    archive=(ROOT/'work/source/disc/WIN00.AFS').read_bytes()
    for info,data,plain,im in analyze():
        rows=[r for r in recipe['rows'] if r['texture_member']==info['texture_member']]
        for r in rows:assert digest(im.crop(r['source_box']).tobytes())==r['source_pixels_sha256']
        result,rendering=render(info,plain,rows)
        off,size=struct.unpack_from('<II',archive,8+info['texture_member']*8);raw=archive[off:off+size]
        encoded=compress(result);packed=raw[:16]+encoded
        assert decompress(packed[16:])==(result,len(encoded))
        replacements[info['texture_member']]=packed
        resources.append({k:v for k,v in info.items() if k!='rectangles'}|rendering|{'packed_bytes':len(packed),'packed_sha256':digest(packed),'decoded_sha256':digest(result),'source_packed_sha256':digest(raw),'source_decoded_sha256':digest(plain),'sprite_records':len(info['rectangles'])})
        previews[info['texture_member']]=(im,decode_pvr(result)[0],rows)
    return replacements,resources,previews


def compose():
    recipe=json.loads(DEST.read_text('utf-8'));assert recipe==prepare()
    base=ROOT/'work/output'/PRIOR;replacements,resources,previews=make_resources(recipe)
    source=(base/'WIN00.AFS').read_bytes()
    for r in resources:
        off,size=struct.unpack_from('<II',source,8+r['texture_member']*8);assert digest(source[off:off+size])==r['source_packed_sha256']
    archive,packing=repack(source,replacements)
    packing['validation']='Three UI texture resources changed; other 87 member payloads exact; metadata/dimensions and archive order retained'
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    files.update({'text/'+p.name:p.read_bytes() for p in (base/'text').iterdir() if p.is_file()})
    for name in ('english-disc-report.json','READ-ME.txt','chapter-card-native-test.json'):files.pop(name,None)
    files['WIN00.AFS']=archive;files['archive-repack-report.json']=json.dumps(packing,indent=2).encode()
    manifest=json.loads(files['font4x-patch.json']);manifest.update(version=VERSION,previous_build=PRIOR,status='English UI image candidate; native texture/PRS/archive checks and packaging pending')
    manifest['files']['WIN00.AFS']['target_sha256']=digest(archive)
    member=packing['members'][52]
    manifest['library'].update(archive_member_offset=member['target_offset'],archive_member_bytes=member['bytes'])
    files['library-patch-report.json']=json.dumps(manifest['library'],indent=2).encode()
    report={'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(files['1ST_READ.BIN']),'archive_sha256':digest(archive),'translation_map_sha256':digest(DEST.read_bytes()),'label_sprites':len(recipe['rows']),'resources':resources,'archive_spare_bytes':packing['spare_bytes'],
        'pending':['Native PRS/texture header and independent pixel/fit verification','Fresh chapter checks for repacked archive','Disc packaging','Live image appearance and actual selection routes']}
    manifest['ui_images']={k:v for k,v in report.items() if k!='resources'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Executable/font and all text payloads exact; prior native reports retain their tested hashes; fresh changed-PVR and repacked-archive checks required'}
    chapter=json.loads(files['chapter-card-component.json']);chapter.update(version=VERSION,source_build=PRIOR,archive_sha256=digest(archive));files['chapter-card-component.json']=json.dumps(chapter,indent=2).encode()
    files['ui-image-component.json']=json.dumps(report,indent=2).encode();files['font4x-patch.json']=json.dumps(manifest,indent=2).encode()
    return files,report,previews


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args();files,report,previews=compose()
    print(json.dumps({k:v for k,v in report.items() if k!='resources'},indent=2));print('Changed texture sizes:',[(r['texture_member'],r['packed_bytes'],r['decoded_bytes']) for r in report['resources']])
    if not args.write:print('DRY RUN: no candidate written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    selected=[(member,source,target,row) for member,(source,target,rows) in previews.items() for row in rows]
    sheet=Image.new('RGB',(1200,32+((len(selected)+2)//3)*132),'#30333a');draw=ImageDraw.Draw(sheet)
    draw.text((8,8),'Original above / English below. Asset preview; live appearance unverified.',fill='white')
    for n,(member,source,target,row) in enumerate(selected):
        x=n%3*400;y=32+n//3*132
        for dy,im in [(0,source),(52,target)]:
            crop=im.crop(row['source_box']);crop=crop.resize((crop.width*3,crop.height*3),Image.Resampling.NEAREST);sheet.paste(crop,(x,y+dy),crop)
        draw.text((x,y+110),row['id']+' '+row['en'],fill='white')
    sheet.save(out/'ui-image-labels-preview.png')
    print('Wrote UI image candidate:',out)


if __name__=='__main__':main()
