"""Build integrated English chapter-card atlases 0.1.16. Default dry run.

Uses the supplied bitmap at a common 1x source scale, variable spacing and
one-pixel outlines. Retains all PVM decoded sizes, texture dimensions,
palettes, original effects/digits, resource IDs and executable bytes.
"""
import argparse,copy,json,math,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter,ImageDraw
from build_bitmap_font import ROOT,ATLAS,digest
from extract_chapter_cards import analyze
from audit_texture_archive import untwiddle_indices
from rayblade_codec import compress,decompress

VERSION='0.1.16'
PRIOR='0.1.15'


def strip(text):
    atlas=Image.open(ATLAS).convert('L');glyphs=[];width=2
    for char in text:
        assert ' '<=char<='~'
        if char==' ':glyphs.append((None,4));width+=4;continue
        code=ord(char)-32;x=code%32*12;y=code//32*24
        cell=atlas.crop((x,y,x+12,y+24));box=cell.getbbox();assert box
        glyph=cell.crop((box[0],0,box[2],24));advance=glyph.width+1
        glyphs.append((glyph,advance));width+=advance
    width=(width+1)//2*2
    mask=Image.new('L',(width,24));x=1
    for glyph,advance in glyphs:
        if glyph is not None:mask.paste(glyph,(x,0))
        x+=advance
    return mask


def indexed(mask,decoded,info,bank=0):
    start=info['palette_offset']+16+bank*32
    values=np.frombuffer(decoded[start:start+32],dtype='<u2')
    rgb=np.stack([((values>>s&31)*255//31).astype(np.int32) for s in (10,5,0)],axis=1)
    opaque=values>>15
    candidates=np.flatnonzero(opaque);assert len(candidates)
    choices=np.array([candidates[np.argmin(np.sum((rgb[candidates]-v)**2,axis=1))] for v in range(256)],dtype=np.uint8)
    assert values[0]==0,'Index zero must be transparent'
    ink=np.asarray(mask);outline=np.asarray(mask.filter(ImageFilter.MaxFilter(3)))
    result=np.zeros(ink.shape,dtype=np.uint8)
    result[outline>0]=choices[0]
    result[ink>0]=choices[ink[ink>0]]
    return result


def unpack_indices(decoded,info):
    w,h=info['texture_size'];p=info['texture_offset']+16
    data=np.frombuffer(decoded[p:p+w*h//2],dtype=np.uint8)
    return np.column_stack((data&15,data>>4)).ravel()[untwiddle_indices(w,h)].copy()


def put_indices(decoded,info,plane):
    w,h=info['texture_size'];assert plane.shape==(h,w) and plane.max()<16
    raw=np.empty(w*h,dtype=np.uint8);raw[untwiddle_indices(w,h).ravel()]=plane.ravel()
    packed=(raw[0::2]|raw[1::2]<<4).tobytes();p=info['texture_offset']+16
    result=bytearray(decoded);result[p:p+len(packed)]=packed
    assert len(result)==len(decoded)
    return result


def rect(result,offset,width,height,cx,cy,x,y,texture_size,tex_id=0):
    w,h=texture_size
    assert x*256%w==0 and (x+width)*256%w==0
    assert y*256%h==0 and (y+height)*256%h==0
    struct.pack_into('<HHhh6H',result,offset,width,height,cx,cy,
        x*256//w,y*256//h,(x+width)*256//w,(y+height)*256//h,tex_id,0)


def make_resources():
    resources,original_links=analyze()
    path=ROOT/'work/translation/en/ui/chapter-cards.en.json'
    links=json.loads(path.read_text('utf-8'));assert links==original_links
    result={};report=[];previews={}
    for info,source,_ in resources:
        index=info['member'];w,h=info['texture_size'];base=info['rect_start']
        rows=[r for r in links['titles'] if r['member']==index]
        target=bytearray(source);entries=[]
        if index==32:
            plane=unpack_indices(source,info)
            # Exactly the two Japanese episode-label cells; digits and all
            # six effect sprites retain their original texel indices.
            plane[56:80,0:48]=0
            mask=strip('Chapter');pixels=indexed(mask,source,info,bank=4)
            plane[88:112,0:mask.width]=pixels
            assert not plane[254:256,254:256].any()
            shift=(mask.width+4)//2
            rect(target,base+6*20,mask.width,24,mask.width-20-shift,0,0,88,[w,h],tex_id=4)
            rect(target,base+7*20,1,1,0,0,255,255,[w,h],tex_id=4)
            for i in range(8,18):struct.pack_into('<h',target,base+i*20+4,-shift)
            assert target[base:base+6*20]==source[base:base+6*20]
            target=put_indices(target,info,plane)
            assert np.array_equal(plane[56:80,48:208],unpack_indices(source,info)[56:80,48:208])
            entries=[{'id':'episode-label','en':'Chapter','width':mask.width,'common_number_shift':shift,
                'blanked_source_suffix':'Original episode suffix sprite now selects a transparent texel'}]
        else:
            plane=np.zeros((h,w),dtype=np.uint8);shelves=[]
            shapes=[(row,strip('"'+row['en']+'"')) for row in rows]
            for row,mask in sorted(shapes,key=lambda p:(-p[1].width,p[0]['id'])):
                assert mask.width<=w
                for shelf in shelves:
                    if shelf['used']+mask.width+2<=w:break
                else:
                    shelf={'y':len(shelves)*26,'used':0};shelves.append(shelf)
                x=shelf['used'];y=shelf['y'];shelf['used']+=mask.width+2
                assert y+24<=h
                plane[y:y+24,x:x+mask.width]=indexed(mask,source,info)
                main=row['main_rectangle'];reading=row['reading_rectangle']
                rect(target,base+main*20,mask.width,24,mask.width//2-40,12,x,y,[w,h])
                # The last development-only title originally ended at a
                # sentinel instead of having a reading sprite. Its 28-byte
                # terminator/padding tail fits a blank record + new sentinel.
                if reading is None:
                    reading=main+1;terminal=base+reading*20
                    next_chunk=source.index(b'PVRT',0xa0)
                    assert terminal+28==next_chunk
                    assert struct.unpack_from('<4H',source,terminal)==(0,65535,65535,65535)
                    struct.pack_into('<4H',target,terminal+20,0,65535,65535,65535)
                rect(target,base+reading*20,2 if w==512 else 1,1,0,0,w-2 if w==512 else w-1,h-1,[w,h])
                entries.append({'id':row['id'],'en':row['en'],'display_text':'"'+row['en']+'"',
                    'main_rectangle':main,'reading_rectangle':reading,'width':mask.width,'atlas_xy':[x,y],
                    'native_call_xy':[120,132],'calculated_left':160-mask.width//2,'calculated_center':160})
            assert not plane[h-1,w-2:].any()
            target=put_indices(target,info,plane)
        target=bytes(target);assert len(target)==len(source)
        # All source palettes, container/texture headers and relocation
        # metadata remain exact; only sprite records and texel arrays change.
        palette_end=info['palette_offset']+16+info['palette_entries']*2
        assert target[info['palette_offset']:palette_end]==source[info['palette_offset']:palette_end]
        assert target[:base]==source[:base]
        p=info['texture_offset'];assert target[p:p+16]==source[p:p+16]
        packed=compress(target);assert decompress(packed)==(target,len(packed))
        result[index]=packed
        report.append({**{k:info[k] for k in ('member','resource_name','texture_size','rect_start','texture_offset','palette_offset','palette_entries')},
            'source_packed_sha256':info['packed_sha256'],'source_decoded_sha256':info['decoded_sha256'],
            'packed_sha256':digest(packed),'decoded_sha256':digest(target),'packed_bytes':len(packed),
            'decoded_bytes':len(target),'entries':entries})
        # White-bank rendering for audit; S_TITLE0 uses bank four for its
        # letters and other banks for effects, so this is a text preview only.
        start=info['palette_offset']+16+(128 if index==32 else 0)
        colors=np.frombuffer(source[start:start+32],dtype='<u2');values=colors[plane]
        rgba=np.stack([((values>>s&31)*255//31).astype(np.uint8) for s in (10,5,0)]+
            [((values>>15)*255).astype(np.uint8)],axis=2)
        previews[index]=Image.fromarray(rgba)
    assert sum(len(r['entries']) for r in report if r['member']!=32)==69
    return result,report,previews


def repack(source,replacements,*,first=0x70000):
    count=struct.unpack_from('<I',source,4)[0]
    assert first%2048==0 and first>=8+count*8+8
    assert count==90 and source[8+count*8:8+count*8+8]==bytes(8)
    out=bytearray(source[:8+count*8+8]);out.extend(bytes(first-len(out)));records=[]
    for i in range(count):
        old,size=struct.unpack_from('<II',source,8+8*i);original=source[old:old+size]
        raw=replacements.get(i,original);offset=(len(out)+2047)//2048*2048
        out.extend(bytes(offset-len(out)));out.extend(raw);struct.pack_into('<II',out,8+8*i,offset,len(raw))
        records.append({'index':i,'source_offset':old,'target_offset':offset,'bytes':len(raw),
            'sha256':digest(raw),'source_sha256':digest(original),'changed':i in replacements})
    used=len(out);assert used<=len(source),(used,len(source));out.extend(bytes(len(source)-used))
    for r in records:
        assert digest(out[r['target_offset']:r['target_offset']+r['bytes']])==r['sha256']
    assert all(a['target_offset']+a['bytes']<=b['target_offset'] for a,b in zip(records,records[1:]))
    return bytes(out),{'source_sha256':digest(source),'target_sha256':digest(out),'archive_bytes':len(out),
        'first_data_offset':first,'used_bytes':used,'spare_bytes':len(source)-used,'members':records,
        'validation':'Five chapter resources changed; all other 85 member payloads exact; index order, non-overlap and sector alignment retained'}


def compose():
    base=ROOT/'work/output'/PRIOR;replacements,resources,previews=make_resources()
    source=(base/'WIN00.AFS').read_bytes()
    for r in resources:
        off,size=struct.unpack_from('<II',source,8+8*r['member'])
        assert digest(source[off:off+size])==r['source_packed_sha256']
    archive,repacked=repack(source,replacements)
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    for p in (base/'text').iterdir():
        if p.is_file():files['text/'+p.name]=p.read_bytes()
    files.pop('english-disc-report.json',None);files.pop('READ-ME.txt',None)
    files['WIN00.AFS']=archive
    manifest=json.loads(files['font4x-patch.json']);assert manifest['files']['WIN00.AFS']['target_sha256']==digest(source)
    manifest.update(version=VERSION,previous_build=PRIOR,status='English chapter-card candidate; fresh resource/native/geometry checks pending')
    manifest['files']['WIN00.AFS']['target_sha256']=digest(archive)
    off,size=struct.unpack_from('<II',archive,8+8*52)
    manifest['library'].update(archive_member_offset=off,archive_member_bytes=size)
    library=json.loads(files['library-patch-report.json']);library.update(archive_member_offset=off,archive_member_bytes=size)
    files['library-patch-report.json']=json.dumps(library,indent=2).encode()
    files['archive-repack-report.json']=json.dumps(repacked,indent=2).encode()
    report={'version':VERSION,'source_build':PRIOR,'archive_sha256':digest(archive),
        'executable_sha256':digest(files['1ST_READ.BIN']),'bitmap_source_sha256':digest(ATLAS.read_bytes()),
        'English_map_sha256':digest((ROOT/'work/translation/en/ui/chapter-cards.en.json').read_bytes()),
        'title_slots':69,'episode_label':'Chapter','resources':resources,'archive_spare_bytes':repacked['spare_bytes'],
        'pending':['Native resource selection/PVM walker/PRS checks','Sprite geometry and chapter-preview verification','Disc packaging and live chapter appearance']}
    manifest['chapter_cards']={k:v for k,v in report.items() if k!='resources'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'reason':'Executable/font/name/story/library/battle payloads unchanged; only chapter PVMs and archive offsets changed',
        'executable_sha256':digest(files['1ST_READ.BIN'])}
    files['chapter-card-component.json']=json.dumps(report,indent=2).encode()
    files['font4x-patch.json']=json.dumps(manifest,indent=2).encode()
    for r in resources:
        member=r['member'];files[f'text/chapter-{member}.pvm.bin']=decompress(replacements[member])[0]
    return files,report,previews


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,report,previews=compose()
    print(json.dumps({k:v for k,v in report.items() if k!='resources'},indent=2))
    print('Resource packed/decoded bytes:',[(r['member'],r['packed_bytes'],r['decoded_bytes']) for r in report['resources']])
    if not args.write:print('DRY RUN: no components or previews written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    for index,im in previews.items():im.save(out/f'chapter-atlas-{index}.png')
    print('Wrote chapter-card candidate:',out)


if __name__=='__main__':main()
