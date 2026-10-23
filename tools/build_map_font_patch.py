"""Original Skies map names in a separate 1024x256 alpha atlas. Dry first."""
import argparse,json,struct,math
from functools import lru_cache
import numpy as np
from PIL import Image,ImageFilter,ImageDraw
from build_bitmap_font import ROOT,digest
from build_antialias_font import font_bytes
from build_font4x_patch import MEDIUM
from test_outline_font import legacy_mask
from audit_texture_archive import untwiddle_indices,decode_pvr
from build_ui_atlas_patch import pixels
from rayblade_codec import compress,decompress
from afs_layout import require_native_layouts

VERSION='0.1.44';PRIOR='0.1.43';OUT=ROOT/'work/output/map-font-draft-01'
RECIPE=ROOT/'work/translation/en/ui/worldmap-labels.en.json'


def member(b,i):
    o,n=struct.unpack_from('<II',b,8+i*8);return b[o:o+n]


def label(text,font):
    end=sum(font[0xa0+MEDIUM.index(c)]*4 for c in text)
    coverage=Image.new('L',(end+32,64));x=0
    for ch in text:
        glyph=Image.fromarray(legacy_mask(font,ch,False)[:,:32]);coverage.paste(glyph,(x,0))
        x+=font[0xa0+MEDIUM.index(ch)]*4
    box=coverage.getbbox();assert box and box[1]>=2 and box[3]+2<64
    return np.asarray(coverage)[:,:box[2]+4].copy()


def rgba4444(coverage):
    # A thin dark edge sits behind the unmodified Skies coverage. Preserve
    # source glyph alpha levels, rather than baking dim edges into opaque RGB.
    mask=Image.fromarray(coverage);edge=np.asarray(mask.filter(ImageFilter.MaxFilter(5)))
    out=(edge.astype(np.uint16)//17)<<12
    ink=coverage>0;out[ink]=(coverage[ink].astype(np.uint16)//17)<<12|0xffe
    return out


def packed_pvr(plane,fmt,gbix):
    h,w=plane.shape;linear=np.empty(w*h,dtype='<u2')
    linear[untwiddle_indices(w,h).ravel()]=plane.ravel()
    tag=b'GBIX'+struct.pack('<III',8,gbix,0)
    raw=tag+b'PVRT'+struct.pack('<IIHH',8+w*h*2,fmt,w,h)+linear.tobytes()
    packed=tag+compress(raw);assert decompress(packed[16:])==(raw,len(packed)-16)
    return packed,raw


def dat_with_two_textures(old):
    start=struct.unpack_from('<I',old,4)[0]+4;assert start==48
    assert struct.unpack_from('<I',old,12)[0]==1
    payload=bytearray(struct.pack('<II',8,2)+bytes(24))
    for i,name in enumerate((b'wmap_dc',b'wmap_en')):
        struct.pack_into('<I',payload,8+12*i,len(payload));payload.extend(name+b'\0')
    while len(payload)%4:payload.append(0)
    relocs=bytes([0x40,0x42,0x43,0]);payload.extend(b'POF0'+struct.pack('<I',len(relocs))+relocs)
    dat=b'NJTL'+struct.pack('<I',len(payload)+4)+payload+old[start:]
    return bytearray(dat),len(payload)+8,start


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;source=(base/'WMAP.AFS').read_bytes();assert struct.unpack_from('<I',source,4)[0]==20
    olddat=member(source,17);oldpacked=member(source,18);plain,used=decompress(oldpacked[16:]);assert used==len(oldpacked)-16
    assert plain[24:32]==struct.pack('<IHH',0x100,512,512)
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1]
    rows=json.loads(RECIPE.read_text('utf-8'))['rows'];assert len(rows)==10
    oldplane=pixels(plain,512,512);clean=oldplane.copy();allowed=np.zeros((512,512),bool)
    dat,start,oldstart=dat_with_two_textures(olddat)
    atlas=np.zeros((256,1024),np.uint16);draws=[];shelf_x=shelf_y=0
    for row in rows:
        i=row['sprite'];p=oldstart+i*20
        w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',olddat,p)
        assert tex==0 and h==16
        box=[u0*2,v0*2,u1*2,v1*2];x0,y0,x1,y1=box
        allowed[y0:y1,x0:x1]=True;clean[y0:y1,x0:x1]=0
        coverage=label(row['en'],font)
        width=max(w,math.ceil(coverage.shape[1]/8)*2);physical=width*4
        assert physical<=1024
        if shelf_x+physical>1024:shelf_x=0;shelf_y+=64
        assert shelf_y+64<=256
        canvas=np.zeros((64,physical),np.uint8);offset=(physical-coverage.shape[1])//2
        canvas[:,offset:offset+coverage.shape[1]]=coverage
        tile=rgba4444(canvas);atlas[shelf_y:shelf_y+64,shelf_x:shelf_x+physical]=tile
        anchor=cx+(width-w)//2;assert width-2*anchor==w-2*cx
        uv=[shelf_x//4,shelf_y,(shelf_x+physical)//4,shelf_y+64]
        struct.pack_into('<HHhh6H',dat,start+i*20,width,h,anchor,cy,*uv,1,flags)
        draws.append({'id':row['id'],'sprite':i,'en':row['en'],'old_record':list(struct.unpack_from('<HHhh6H',olddat,p)),
            'old_box':box,'draw_size':[width,h],'anchor':[anchor,cy],'atlas_box':[shelf_x,shelf_y,shelf_x+physical,shelf_y+64],
            'UV':uv,'font_coverage_sha256':digest(canvas.tobytes()),'ink_pixels':int((canvas>0).sum())})
        shelf_x+=physical
    assert np.array_equal(oldplane[~allowed],clean[~allowed])
    cleanpacked,cleanraw=packed_pvr(clean,0x100,struct.unpack_from('<I',oldpacked,8)[0])
    # The protected marker atlas retains its exact old GBIX/PVRT header.
    cleanraw=plain[:32]+cleanraw[32:];cleanpacked=oldpacked[:16]+compress(cleanraw)
    labelpacked,labelraw=packed_pvr(atlas,0xd02,0x00ed0044)
    # Keep the original authoring filename list as the new final member. The
    # second label texture is contiguous after the first, as the native loader expects.
    members=[member(source,i) for i in range(17)]+[bytes(dat),cleanpacked,labelpacked,member(source,19)]
    first=0x70000;assert not any(source[8+20*8:first])
    target=bytearray(first);target[:8]=b'AFS\0'+struct.pack('<I',21);records=[]
    for i,raw in enumerate(members):
        off=(len(target)+2047)//2048*2048;target.extend(bytes(off-len(target)));target.extend(raw)
        struct.pack_into('<II',target,8+i*8,off,len(raw));records.append({'member':i,'offset':off,'bytes':len(raw),'sha256':digest(raw)})
    used=len(target);assert used<=len(source),(used,len(source));target.extend(bytes(len(source)-len(target)))
    require_native_layouts({'WMAP.AFS':target})
    report={'version':VERSION,'source_build':PRIOR,'source_archive_sha256':digest(source),'archive_sha256':digest(target),
        'executable_sha256':digest((base/'1ST_READ.BIN').read_bytes()),'font_sha256':digest(font),
        'font':'Original Skies Latin medium masks and variable advances, exact same glyph coverage as dialogue',
        'method':'Four-times-detail image labels; unmodified four-level foreground alpha, cream fill and two-physical-pixel dark edge',
        'texture_dimensions':[1024,256],'pixel_format':'ARGB4444 rectangular twiddled','added_VRAM_bytes':1024*256*2,
        'texture_members':[18,19],'dat_member':17,'new_DAT_sprite_start':start,'old_DAT_sprite_start':oldstart,
        'label_count':10,'draws':draws,'members':records,'used_bytes':used,'spare_bytes':len(source)-used,
        'protected_marker_sprite_ids':list(range(17))+[27],'unmodified_map_artwork_members':17,
        'original_filename_list_relocated_to_member':20,'font_glyph_shapes_changed':False,
        'marker_atlas_decoded_sha256':digest(cleanraw),'label_atlas_decoded_sha256':digest(labelraw),
        'label_atlas_packed_sha256':digest(labelpacked),'release':False,
        'pending':['Native two-texture registration, UV/anchor/PRS/archive checks','Disc packaging','Live map readability, overlaps, dialogue fade and VRAM behavior']}
    return bytes(target),bytes(dat),cleanpacked,cleanraw,labelpacked,labelraw,report,oldplane,atlas


def preview(result):
    _,_,_,_,_,raw,report,before,_=result
    atlas=decode_pvr(raw)[0];sheet=Image.new('RGB',(1400,1000),'#45543d');draw=ImageDraw.Draw(sheet)
    draw.text((12,10),'Original Skies map labels, 4x texture detail. Offline asset preview, not live gameplay.',fill='white')
    for i,row in enumerate(report['draws']):
        x,y=12+(i%2)*700,42+(i//2)*190
        cell=atlas.crop(row['atlas_box']);sheet.paste(cell,(x,y),cell)
        draw.text((x,y+92),row['en']+' / '+str(row['draw_size']),fill='white')
    return sheet


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args();r=compose()
    print(json.dumps({k:v for k,v in r[6].items() if k not in ('members','draws')},indent=2),flush=True)
    print('Labels:',[(v['en'],v['draw_size'],v['atlas_box']) for v in r[6]['draws']])
    if not a.write:print('DRY RUN: no components written.');return
    OUT.mkdir(parents=True,exist_ok=True)
    for name,raw in zip(('WMAP.AFS','map-labels.dat','markers.packed.bin','markers.pvr','labels.packed.bin','labels.pvr'),r[:6]):(OUT/name).write_bytes(raw)
    (OUT/'component-report.json').write_text(json.dumps(r[6],indent=2)+'\n','utf-8');preview(r).save(OUT/'map-labels-preview.png')


if __name__=='__main__':main()
