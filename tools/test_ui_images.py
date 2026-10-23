"""Verify integrated English image sprites, native decoding and texture headers.

Scalar Morton addressing and source-font mask/fit are independent of the
production atlas encoder. Native PRS and Ninja texture-info routines execute.
This does not execute GPU rendering or complete live sprite selection routes.
"""
import argparse,json,struct
import numpy as np
from PIL import Image
from build_ui_atlas_patch import ROOT,VERSION,PRIOR,compose,digest
from prepare_ui_atlas_translation import DEST,prepare
from extract_ui_atlases import analyze
from build_bitmap_font import ATLAS
from check_native_text_components import verify
from rayblade_codec import decompress
from test_font_patch import CPU


def scalar_plane(data,w,h):
    out=np.zeros((h,w),np.uint16);side=min(w,h)
    for y in range(h):
        for x in range(w):
            index=(x//side+y//side)*side*side;xx=x%side;yy=y%side;bit=0
            while (1<<bit)<side:
                index|=((yy>>bit)&1)<<(2*bit);index|=((xx>>bit)&1)<<(2*bit+1);bit+=1
            out[y,x]=int.from_bytes(data[32+index*2:34+index*2],'little')
    return out


def reference_mask(text,d):
    source=np.asarray(Image.open(ATLAS).convert('L'));glyphs=[];total=2
    if d in (3,4):
        # Independent scalar block sampling and explicit integer bearings.
        reduced=[]
        for ch in text:
            if ch==' ':reduced.append(np.zeros((24//d,2),np.uint8));continue
            code=ord(ch)-32;cell=source[code//32*24:code//32*24+24,code%32*12:code%32*12+12]
            columns=np.flatnonzero(cell.any(axis=0));left,right=int(columns[0]),int(columns[-1])+1
            width=(right-left+d-1)//d;glyph=np.zeros((24//d,width),np.uint8)
            for y in range(24//d):
                for x in range(width):glyph[y,x]=cell[y*d:y*d+d,left+x*d:min(right,left+x*d+d)].max(initial=0)
            reduced.append(glyph)
        out=np.zeros((24//d,sum(g.shape[1] for g in reduced)+len(reduced)+1),np.uint8);x=1
        for glyph in reduced:out[:,x:x+glyph.shape[1]]=glyph;x+=glyph.shape[1]+1
        return out
    for ch in text:
        if ch==' ':glyphs.append((None,4));total+=4;continue
        index=ord(ch)-32;cell=source[index//32*24:index//32*24+24,index%32*12:index%32*12+12]
        columns=np.flatnonzero(cell.any(axis=0));g=cell[:,columns[0]:columns[-1]+1];glyphs.append((g,g.shape[1]+1));total+=g.shape[1]+1
    # The source line has a one-pixel side margin and even storage width.
    total=(total+1)//2*2;width=(total+d-1)//d*d
    raw=np.zeros((24,width),np.uint16);x=1
    for g,advance in glyphs:
        if g is not None:raw[:,x:x+g.shape[1]]=g
        x+=advance
    # Integer area sampling independently checks the uniform 1/2 or 1/3 scale.
    horizontal=((2*raw.reshape(24,width//d,d).sum(axis=2)+d)//(2*d))
    return ((2*horizontal.reshape(24//d,d,width//d).sum(axis=1)+d)//(2*d)).astype(np.uint8)


def texture_info(exe,w,h,fmt,expected_pixel_bits=0):
    cpu=CPU(exe,b'',0,0);cpu.regions.insert(-1,(0x8c500000,bytearray(b'\xa5'*128)))
    cpu.reg[4:8]=[0x8c500020,w,h,fmt];cpu.pc=0x8c0e1c4c;saved=cpu.reg[8:]
    for n in range(10000):
        if cpu.pc==0xdead0000:break
        cpu.pc=cpu.execute(cpu.pc)
    else:raise ValueError('Native texture-info instruction limit')
    assert cpu.reg[0]==0 and cpu.reg[8:]==saved
    assert [cpu.read(0x8c500020+i,4) for i in (8,12,16,20)]==[expected_pixel_bits,w,h,w*h*2]
    assert cpu.regions[-2][1][:32]==b'\xa5'*32 and cpu.regions[-2][1][64:]==b'\xa5'*64
    return n


def main():
    global VERSION
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--version',default=VERSION,choices=['0.1.20','0.1.21']);ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    print('Plan: independent pixel addressing/source-mask fit, 35 selected/277 protected sprites, three native PRS decodes/texture-format cases and all archive members.',flush=True)
    if not args.verify:print('DRY RUN: no native execution/report');return
    out=ROOT/'work/output'/VERSION;base=ROOT/'work/output'/PRIOR
    component_compose=compose
    if VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose as component_compose
    files,_,_=component_compose();report=json.loads(files['ui-image-component.json']);archive=(out/'WIN00.AFS').read_bytes();assert archive==files['WIN00.AFS']
    exe=(out/'1ST_READ.BIN').read_bytes();assert exe==files['1ST_READ.BIN']
    if VERSION=='0.1.20':assert exe==(base/'1ST_READ.BIN').read_bytes()
    recipe=json.loads(DEST.read_text('utf-8'));assert recipe==prepare();rows=recipe['rows']
    old=(base/'WIN00.AFS').read_bytes();changed={r['texture_member'] for r in report['resources']};last=0;unrelated=0
    for i in range(90):
        off,size=struct.unpack_from('<II',archive,8+i*8);before,count=struct.unpack_from('<II',old,8+i*8)
        assert off%2048==0 and off>=last and off+size<=len(archive);last=off+size
        if i not in changed:assert archive[off:off+size]==old[before:before+count];unrelated+=1
    assert unrelated==87 and len(archive)==len(old)
    resources=[];prs_steps=0;format_steps=0;protected=0;draws=0;source_font_pixels=0
    sources={info['texture_member']:(info,plain) for info,_,plain,_ in analyze()}
    for record in report['resources']:
        index=record['texture_member'];info,source=sources[index];w,h=info['width'],info['height']
        off,size=struct.unpack_from('<II',archive,8+index*8);raw=archive[off:off+size];target,used=decompress(raw[16:]);assert used==len(raw)-16
        assert digest(raw)==record['packed_sha256'] and digest(target)==record['decoded_sha256'] and len(target)==len(source)==record['decoded_bytes']
        before,count=struct.unpack_from('<II',old,8+index*8);assert raw[:16]==old[before:before+16] and target[:32]==source[:32]
        prs=verify(exe,raw[16:],target,len(source),instruction_limit=25_000_000);prs_steps+=prs
        fmt=struct.unpack_from('<I',target,24)[0];native=texture_info(exe,w,h,fmt);format_steps+=native
        plane=scalar_plane(target,w,h);original=scalar_plane(source,w,h);allowed=np.zeros((h,w),bool)
        selected=[r for r in rows if r['texture_member']==index];ids={r['sprite'] for r in selected}
        for row in selected:
            x0,y0,x1,y1=row['source_box'];allowed[y0:y1,x0:x1]=True
            if row['style'] in ('medium','small_red'):
                expected=np.zeros((y1-y0,x1-x0),bool)
                parts=row.get('parts',[{'text':row['en'],'box':[0,0,x1-x0,y1-y0]}])
                for part in parts:
                    mask=reference_mask(part['text'],4 if row['style']=='small_red' else 2);hh,ww=mask.shape;bx,by,ex,ey=part['box']
                    x=bx+(ex-bx-ww-1)//2;y=by+(ey-by-hh-1)//2
                    assert x>=bx and y>=by and x+ww+1<=ex and y+hh+1<=ey
                    expected[y:y+hh,x:x+ww]|=mask>0;expected[y+1:y+hh+1,x+1:x+ww+1]|=mask>0
                assert np.array_equal(plane[y0:y1,x0:x1]&0x8000!=0,expected),('Source font contour/placement mismatch',row['id'])
            # Independently establish font dimensions and strong foreground
            # coverage for every label, including opaque tab/icon backgrounds.
            parts=row.get('parts',[{'text':row['en'],'box':[8,1,x1-x0-4,y1-y0-1] if row['style']=='tab' else [1,1,x1-x0-1,y1-y0-1] if row['style']=='icon' else [0,0,x1-x0,y1-y0]}])
            for part in parts:
                d=2 if row['style']=='medium' else 4 if row['style']=='small_red' else 3;mask=reference_mask(part['text'],d);hh,ww=mask.shape;bx,by,ex,ey=part['box']
                x=bx+(ex-bx-ww-1)//2;y=by+(ey-by-hh-1)//2;assert x>=bx and y>=by and x+ww+1<=ex and y+hh+1<=ey
                crop=plane[y0+y:y0+y+hh,x0+x:x0+x+ww];ink=mask>0
                assert np.all(crop[ink]&0x8000!=0)
                for shift,channel in zip((10,5,0),(31,10,11) if row['style']=='small_red' else (31,31,31)):
                    assert np.all((crop[ink]>>shift&31)>=((mask[ink].astype(np.uint16)*channel+127)//255))
                source_font_pixels+=int(ink.sum());draws+=1
        assert np.array_equal(plane[~allowed],original[~allowed])
        for r in info['rectangles']:
            if r['index'] in ids:continue
            x0,y0,x1,y1=r['source_box'];assert np.array_equal(plane[y0:y1,x0:x1],original[y0:y1,x0:x1]);protected+=1
        if index==6:
            # Shared sprite must read the exact right half of Ballistic Barrier.
            a=info['rectangles'][94]['source_box'];b=info['rectangles'][107]['source_box'];assert b==[a[0]+48,a[1],a[2],a[3]]
        resources.append({'member':index,'decoded_bytes':len(target),'dimensions':[w,h],'native_format':hex(fmt),'native_PRS_instructions':prs,'native_texture_info_instructions':native,'selected_sprites':len(selected),'changed_pixels':int((plane!=original).sum())})
        print('Texture',index,'native decode, independent font/fit, protected pixels pass',flush=True)
    assert protected==277 and draws==36
    proof={'version':VERSION,'executable_sha256':digest(exe),'archive_sha256':digest(archive),'component_sha256':digest((out/'ui-image-component.json').read_bytes()),'translation_map_sha256':digest(DEST.read_bytes()),'font_source_sha256':digest(ATLAS.read_bytes()),
        'label_sprites':len(rows),'font_draws':draws,'independent_font_mask_pixels':source_font_pixels,'protected_sprites':protected,'unrelated_archive_members':unrelated,'native_PRS_instructions':prs_steps,'native_texture_info_instructions':format_steps,'resources':resources,
        'checks':['Independent scalar Morton decoding and source-font block sampling/fit pass','Every source-font contour and shadow occupancy matches for transparent labels; opaque labels retain all foreground coverage','Every unselected sprite and all pixels outside selected label cells exact','DAT records, resource IDs, dimensions, formats and native texture memory sizes unchanged','Shared Barrier region is identical in both selecting sprites','All 90 archive extents ordered/aligned/non-overlapping; 87 unrelated member payloads exact'],
        'limits':['Native PRS and texture-info execute in an interpreter with guarded buffers','Full resource I/O, actual sprite selection/navigation and GPU drawing are not executed','Tiny image labels use fixed native dimensions; integrated normal-text font is unchanged','Other image/movie text and independent meaning review remain incomplete']}
    print(json.dumps(proof,indent=2),flush=True)
    if args.write_report:
        p=out/'ui-image-native-test.json';p.write_text(json.dumps(proof,indent=2)+'\n','utf-8')
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m['ui_images'].update(native_validation='pass; scope/limits in proof',proof_sha256=digest(p.read_bytes()));(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
