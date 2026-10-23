"""Native map two-texture registration, geometry/UVs, PRS and preservation. Dry first."""
import argparse,json,struct
from collections import Counter
import numpy as np
from build_map_font_patch import ROOT,OUT,VERSION,PRIOR,compose,member,digest
from afs_layout import compact_positions,require_native_layouts
from check_native_text_components import verify
from test_ordered_archive_layouts import directory_bytes,lookup
from test_memory_album_patch import InitCPU,GeometryCPU
from check_attack_variant_selection import run,STOP,BASE
from test_ui_images import texture_info,scalar_plane
from build_antialias_font import font_bytes
from build_font4x_patch import MEDIUM
from analyze_skies_font import read_executable,skies_glyph,EXPECTED_EXE
from PIL import Image


def registration(exe,dat):
    c=InitCPU(exe,b'',0,0);slot=29;resource=0x8c16ed5c+slot*48
    c.regions=[(BASE,bytearray(exe)),(0x8c160000,bytearray(0x20000)),
        (0x8c500000,bytearray(dat)),(0x8c700000,bytearray(b'\xa5'*0x2000))]
    c.reg[15]=0x8c701000;c.write(0x8c171710,slot,1);c.write(0x8c171711,26,1);c.write(0x8c171712,17,2)
    c.visited=set();saved=c.reg[8:];n=run(c,0x8c031b7c,STOP,100000)
    assert c.reg[0]==0xffffffff and c.reg[8:]==saved
    start=4+struct.unpack_from('<I',dat,4)[0]
    assert c.read(resource,4)==0x8c500008 and c.read(resource+4,4)==0x8c500000+start
    assert c.read(resource+8,4)==0x8c500000 and c.read(resource+12,4)==0x12001a
    assert c.read(resource+16,2)==28
    relocated=bytearray(dat)
    for p in (8,16,28):struct.pack_into('<I',relocated,p,struct.unpack_from('<I',dat,p)[0]+0x8c500008)
    assert c.regions[2][1]==relocated
    assert c.regions[-1][1][:0xf00]==b'\xa5'*0xf00 and c.regions[-1][1][0x1000:]==b'\xa5'*0x1000
    return {'textures':2,'sprites':28,'native_instructions':n,'exact_NJTL_relocation_and_sprite_scan':'pass',
        'resource_slot_fixture':slot,'archive_member_identity':'WMAP.AFS 17, consecutive textures 18/19',
        'scope':'I/O/poll allocation are bounded fixtures; actual map slot selection and GPU not executed'}


def geometry(exe,dat):
    start=4+struct.unpack_from('<I',dat,4)[0];cases=[];steps=0
    f=lambda value:struct.unpack('<f',value.to_bytes(4,'little'))[0]
    for i in range(28):
        w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',dat,start+i*20)
        c=GeometryCPU(exe,b'',0,0);c.regions=[(BASE,bytearray(exe)),(0x8c500000,bytearray(dat)),
            (0x8c510000,bytearray(32)),(0x8c700000,bytearray(b'\xa5'*0x2000))]
        c.reg[4:7]=[0x8c510000,i,0];c.reg[8]=0x8c701000;c.reg[15]=0x8c700fc0
        c.write(0x8c51001c,0x8c500000+start,4);c.write(0x8c51000c,0x3f800000,4);c.write(0x8c510010,0x3f800000,4)
        c.fr=[0]*16;c.fpul=0;c.visited=set();steps+=run(c,0x8c0ac310,0x8c0ac39c,1000)
        bounds=[f(v) for v in c.fr[:4]];assert bounds==[-float(cx),-float(cy),float(w-cx),float(h-cy)],(i,bounds)
        uv=[f(c.read(0x8c700fe0+j*4,4)) for j in range(8)]
        assert uv==[v1/256,u1/256,v0/256,u1/256,v1/256,u0/256,v0/256,u0/256],(i,uv)
        cases.append({'sprite':i,'bounds':bounds,'normalized_UV':uv,'texture_id':tex})
    return {'cases':cases,'native_instructions':steps,'bounds_normalized_UV_and_center_anchors':'pass','GPU':False}


def check():
    target,dat,mp,mr,lp,lr,component,oldplane,atlas=compose()
    assert (OUT/'WMAP.AFS').read_bytes()==target
    base=ROOT/'work/output'/PRIOR;source=(base/'WMAP.AFS').read_bytes();exe=(base/'1ST_READ.BIN').read_bytes()
    steps=Counter();layout=require_native_layouts({'WMAP.AFS':target});directory=directory_bytes('WMAP.AFS',target)
    for row in compact_positions(target):
        off,count,n=lookup(exe,'WMAP.AFS',directory,row['member']);steps['SDK']+=n
        assert off==row['declared_offset'] and count==row['sectors']
    for i in range(17):assert member(target,i)==member(source,i)
    assert member(target,20)==member(source,19)
    before=member(source,17);oldstart=component['old_DAT_sprite_start'];start=component['new_DAT_sprite_start']
    clean=scalar_plane(mr,512,512);plane=scalar_plane(lr,1024,256);assert np.array_equal(plane,atlas)
    allowed=np.zeros((512,512),bool)
    sky,_=read_executable();assert digest(sky)==EXPECTED_EXE
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1];reference_pixels=0
    for row in component['draws']:
        i=row['sprite'];x0,y0,x1,y1=row['old_box'];allowed[y0:y1,x0:x1]=True;assert not clean[y0:y1,x0:x1].any()
        w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',dat,start+i*20)
        ow,oh,ox,oy,*_=row['old_record'];assert h==oh and cy==oy and w-2*cx==ow-2*ox and tex==1
        ax,ay,bx,by=row['atlas_box'];assert [u0*4,v0,u1*4,v1]==[ax,ay,bx,by]
        assert (bx-ax,by-ay)==(w*4,h*4)
        # Independent source VQ glyph extraction, using only recorded advances.
        masks=[];right=0
        for ch in row['en']:
            g=skies_glyph(sky,ord(ch),(0,85,187,255));box=g.getbbox();left=box[0] if box else 0
            im=Image.new('L',(32,64));im.paste(g.resize((24,48),Image.Resampling.NEAREST),(4-left*2,4))
            masks.append((right,np.asarray(im)));right+=font[0xa0+MEDIUM.index(ch)]*4
        reference=np.zeros((64,right+32),np.uint8)
        for x,mask in masks:reference[:,x:x+32]=mask
        inkbox=Image.fromarray(reference).getbbox();width=inkbox[2]+4;reference=reference[:,:width]
        canvas=np.zeros((64,w*4),np.uint8);pad=(w*4-width)//2;canvas[:,pad:pad+width]=reference
        assert digest(canvas.tobytes())==row['font_coverage_sha256']
        cell=plane[ay:by,ax:bx];fg=canvas>0
        assert np.array_equal((cell[fg]>>12)*17,canvas[fg]) and np.all(cell[fg]&0xfff==0xffe)
        assert set(map(int,np.unique(cell>>12)))<={0,5,11,15}
        reference_pixels+=int(fg.sum())
    assert np.array_equal(oldplane[~allowed],clean[~allowed])
    for i in component['protected_marker_sprite_ids']:
        assert dat[start+i*20:start+(i+1)*20]==before[oldstart+i*20:oldstart+(i+1)*20]
        w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',before,oldstart+i*20)
        assert np.array_equal(clean[v0*2:v1*2,u0*2:u1*2],oldplane[v0*2:v1*2,u0*2:u1*2])
    print('PASS: all ten independent original Skies masks; 18 marker sprites and 17 map artwork members exact.',flush=True)
    reg=registration(exe,dat);geom=geometry(exe,dat)
    steps['texture_info']=texture_info(exe,1024,256,0xd02,expected_pixel_bits=2<<27)
    for label,packed,raw in [('markers',mp,mr),('labels',lp,lr)]:
        steps['PRS_'+label]=verify(exe,packed[16:],raw,len(raw),instruction_limit=40000000)
        print('PASS native PRS:',label,len(raw),'bytes',flush=True)
    return {'version':VERSION,'source_build':PRIOR,'archive_sha256':digest(target),'executable_sha256':digest(exe),
        'component_sha256':digest((OUT/'component-report.json').read_bytes()),'font_sha256':digest(font),
        'label_count':10,'independent_original_Skies_foreground_pixels':reference_pixels,
        'original_glyph_shape_scale_and_four_alpha_levels':'pass','texture_dimensions':[1024,256],
        'protected_marker_sprites':18,'unchanged_map_artwork_members':17,'original_metadata_payload':'retained at member20',
        'archive_layout':layout,'registration':reg,'geometry':geom,'native_instructions':dict(steps),
        'limits':['Archive lookup, NJTL registration, sprite bounds/UV, PRS and texture format execute; I/O/allocation fixtures are bounded.',
            'Actual map selection, texture upload/VRAM, GPU filtering/blending, screen overlaps and dialogue fade remain pending.']}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true');a=ap.parse_args()
    assert not a.write_report or a.verify
    print('Plan: ten source Skies masks; protected markers/art; 21 SDK lookups; native two-texture registration, 28 geometries, ARGB4444/PRS.',flush=True)
    if not a.verify:print('DRY RUN: no native execution/report.');return
    r=check()
    if a.write_report:(OUT/'native-test.json').write_text(json.dumps(r,indent=2)+'\n','utf-8')
    print('PASS: map labels/native registration, geometry, PRS and preservation.',flush=True)


if __name__=='__main__':main()
