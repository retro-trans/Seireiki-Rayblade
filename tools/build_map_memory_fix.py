"""Historical 0.7.16 candidate, superseded: startup initialization fails.

Use build_startup_memory_fix.py for the corrected 0.7.17 build. This recipe
is retained only to reproduce the exact failed input for upgrade verification.
"""
import argparse,json,struct
from functools import lru_cache
import numpy as np
from build_bitmap_font import ROOT,digest
from build_font4x_patch import BASE
from build_map_font_patch import member,packed_pvr
from build_scenario_translation import align
from rayblade_codec import decompress
from audit_texture_archive import untwiddle_indices
from afs_layout import require_native_layouts
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from disc_inventory import Disc,SECTOR
from package_archive_test_disc import substitute_payload_sector

VERSION,PRIOR='0.7.16','0.7.15'
OUT=ROOT/'work/output/map-memory-candidate'
IDS=list(range(17))+[27]


def pack_boxes(rects):
    free=[(0,0,256,128)];placed={}
    for i,w,h in sorted(rects,key=lambda r:(-max(r[1:]),-r[1]*r[2])):
        W,H=w+2,h+2
        opts=[(min(fw-W,fh-H),max(fw-W,fh-H),x,y) for x,y,fw,fh in free if W<=fw and H<=fh]
        assert opts,('Marker atlas overflow',i,w,h)
        _,_,x,y=min(opts);placed[i]=(x+1,y+1,w,h);new=[]
        for fx,fy,fw,fh in free:
            if x>=fx+fw or x+W<=fx or y>=fy+fh or y+H<=fy:new.append((fx,fy,fw,fh));continue
            if x>fx:new.append((fx,fy,x-fx,fh))
            if x+W<fx+fw:new.append((x+W,fy,fx+fw-x-W,fh))
            if y>fy:new.append((fx,fy,fw,y-fy))
            if y+H<fy+fh:new.append((fx,y+H,fw,fy+fh-y-H))
        free=[a for a in new if not any(a!=b and a[0]>=b[0] and a[1]>=b[1] and a[0]+a[2]<=b[0]+b[2] and a[1]+a[3]<=b[1]+b[3] for b in new)]
    return placed


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old_exe=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(old_exe)
    assert exe[0x10cb0:0x10cb4]==bytes.fromhex('04e531e4')
    exe[0x10cb0:0x10cb2]=bytes.fromhex('01e5') # RGB565 display format, same 640x480 request.
    assert [i for i,(a,b) in enumerate(zip(old_exe,exe)) if a!=b]==[0x10cb0]
    source=(base/'WMAP.AFS').read_bytes();dat=bytearray(member(source,17));start=4+struct.unpack_from('<I',dat,4)[0]
    packed=member(source,18);raw=decompress(packed[16:])[0]
    assert struct.unpack_from('<IHH',raw,24)==(0x100,512,512)
    plane=np.frombuffer(raw[32:],dtype='<u2')[untwiddle_indices(512,512)]
    rects=[(i,*struct.unpack_from('<HH',dat,start+i*20)) for i in IDS]
    placements=pack_boxes(rects);atlas=np.zeros((128,256),dtype='<u2');used=np.zeros_like(atlas,dtype=bool);rows=[]
    for i in IDS:
        at=start+i*20;before=struct.unpack_from('<HHhh6H',dat,at);w,h,cx,cy,u0,v0,u1,v1,tex,flags=before
        assert tex==0 and (u1-u0)*2==w and (v1-v0)*2==h
        x,y,_,_=placements[i];ox,oy=u0*2,v0*2
        # Preserve the original source neighborhood, including wrapped edge
        # samples. A one-pixel gutter reproduces bilinear boundary sampling.
        tile=plane[np.ix_(np.arange(oy-1,oy+h+1)%512,np.arange(ox-1,ox+w+1)%512)]
        assert not used[y-1:y+h+1,x-1:x+w+1].any()
        used[y-1:y+h+1,x-1:x+w+1]=True;atlas[y-1:y+h+1,x-1:x+w+1]=tile
        struct.pack_into('<4H',dat,at+8,x,y*2,x+w,(y+h)*2)
        after=struct.unpack_from('<HHhh6H',dat,at);assert after[:4]==before[:4] and after[8:]==before[8:]
        assert np.array_equal(atlas[y:y+h,x:x+w],plane[oy:oy+h,ox:ox+w])
        rows.append({'sprite':i,'source_xywh':[ox,oy,w,h],'target_xywh':[x,y,w,h],
            'source_record':list(before),'target_record':list(after),'pixels_and_gutter_sha256':digest(tile.tobytes())})
    marker,marker_raw=packed_pvr(atlas,0xd00,struct.unpack_from('<I',packed,8)[0])
    members=[member(source,i) for i in range(21)];members[17]=bytes(dat);members[18]=marker
    target=bytearray(source[:struct.unpack_from('<I',source,8)[0]])
    for i,p in enumerate(members):
        off=align(len(target));target.extend(bytes(off-len(target)));target.extend(p);struct.pack_into('<II',target,8+i*8,off,len(p))
    assert len(target)<=len(source);target.extend(bytes(len(source)-len(target)))
    assert all(member(target,i)==member(source,i) for i in range(21) if i not in (17,18))
    require_native_layouts({'WMAP.AFS':target})
    report={'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),'archive_sha256':digest(target),
        'display':{'resolution':[640,480],'old_format':'RGB888 / 24 bit','new_format':'RGB565 / 16 bit',
            'framebuffers':2,'old_bytes':640*480*3*2,'new_bytes':640*480*2*2,'saved_bytes':640*480*2,
            'tradeoff':'Framebuffer color precision is reduced; original texture pixels, font alpha and source movie bytes are retained.'},
        'marker_atlas':{'old_dimensions':[512,512],'new_dimensions':[256,128],'pixel_format':'ARGB1555, rectangular twiddled',
            'old_VRAM_bytes':512*512*2,'new_VRAM_bytes':256*128*2,'saved_bytes':(512*512-256*128)*2,
            'sprites':rows,'preservation':'All 18 marker sprites, source pixels, one-pixel filtering neighborhoods, sizes, anchors and texture ID exact'},
        'combined_VRAM_saving':640*480*2+(512*512-256*128)*2,
        'unchanged':'Native-only font/kernel, all 16 terrain textures, English map label atlas, wording, geometry, movie bytes and all other payloads',
        'release':False,'live_validation':'pending'}
    return bytes(exe),bytes(target),bytes(dat),marker_raw,report


def check():
    from test_map_font_patch import registration,geometry
    from test_ui_images import texture_info,scalar_plane
    from test_ordered_archive_layouts import directory_bytes,lookup
    from afs_layout import compact_positions
    exe,archive,dat,raw,report=compose();base=ROOT/'work/output'/PRIOR
    # Actual SDK archive lookups, PRS, map registration and sprite geometry.
    count=steps=0;directory=directory_bytes('WMAP.AFS',archive)
    for row in compact_positions(archive):
        off,n,used=lookup(exe,'WMAP.AFS',directory,row['member']);steps+=used
        assert off==row['declared_offset'] and n==row['sectors'];count+=1
    steps+=texture_info(exe,256,128,0xd00)
    info={'width':256,'height':128,'format':'0xd00','VRAM_bytes':65536,'native_validation':'pass'}
    from check_native_text_components import verify
    prs=verify(exe,member(archive,18)[16:],raw,len(raw),instruction_limit=40000000)
    reg=registration(exe,dat);geo=geometry(exe,dat)
    decoded=scalar_plane(raw,256,128)
    old=decompress(member((base/'WMAP.AFS').read_bytes(),18)[16:])[0];original=scalar_plane(old,512,512)
    pixels=0
    for r in report['marker_atlas']['sprites']:
        ox,oy,w,h=r['source_xywh'];x,y,_,_=r['target_xywh']
        a=original[np.ix_(np.arange(oy-1,oy+h+1)%512,np.arange(ox-1,ox+w+1)%512)]
        b=decoded[y-1:y+h+1,x-1:x+w+1]
        assert np.array_equal(a,b);pixels+=a.size
    assert exe[0x6b28e:0x6bc00]==(base/'1ST_READ.BIN').read_bytes()[0x6b28e:0x6bc00]
    return {**report,'SDK_archive_cases':count,'SDK_texture_info':info,'map_registration':reg,
        'sprite_geometry':geo,'native_PRS':prs,'exact_marker_and_gutter_pixels':pixels,
        'native_instructions':steps+reg['native_instructions']+geo['native_instructions'],
        'limits':['Framebuffer allocation/color-format and complete texture residency require live cold-boot verification',
            'Physical hardware/full-route review pending','Stage 6 issue #1 unresolved']}


def plan():
    exe,archive,dat,raw,report=compose();base=ROOT/'work/output'/PRIOR
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,(base/'WIN00.AFS').read_bytes(),b'',{},mode),prior=PRIOR,version=VERSION)
    disc,cue,inherited,targets,changes,names,historical,r=p;source=inherited['WMAP.AFS'];targets['WMAP.AFS']=archive
    entry=next(x for x in disc.inventory() if x['path']=='WMAP.AFS');assert len(source)==len(archive)==entry['size']
    original=Disc(next(ROOT.glob('*.cue'))).read(entry['lba'],len(source));delta=0
    for at in range(0,len(source),2048):
        a,b=source[at:at+2048],archive[at:at+2048]
        if a==b:continue
        lba=entry['lba']+at//2048;t=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba']);pos=(t['index']+lba-t['start_lba'])*SECTOR
        with t['path'].open('rb') as f:f.seek(pos);sector=f.read(SECTOR)
        changes.append((t['path'].name,pos,substitute_payload_sector(sector,a,b)));delta+=int(b!=original[at:at+2048])-int(a!=original[at:at+2048])
    r.update(kind='Native 640x480 map video-memory fix',files={n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        new_changed_sectors=len(changes),total_changed_sector_locations_from_original=r['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='map-memory-component.json',current_native_evidence={'map_memory':'map-memory-native-test.json'},
        readme_component_text='Native 1x font only. VGA stays 640x480 with two RGB565 16-bit framebuffers.\n'
            'Map marker sprites are losslessly repacked into a smaller atlas to save video memory.\n',
        proof_scope='Native archive/texture registration/geometry, lossless marker repack and complete disc preservation; live framebuffer/VRAM confirmation separate.',
        inherited_proof_note='Native font and other historical records retain tested identities; current map proof is map-memory-native-test.json.',
        pending=['Live map/framebuffer verification','Physical hardware/full-game review','Stage 6 issue #1'])
    return p,mode


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');args=ap.parse_args()
    exe,archive,dat,raw,component=compose()
    if not args.write:print(json.dumps({k:v for k,v in component.items() if k!='marker_atlas'},indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True)
    for n,b in [('1ST_READ.BIN',exe),('WMAP.AFS',archive),('markers.pvr',raw)]:(OUT/n).write_bytes(b)
    records={'map-memory-component.json':component,'map-memory-native-test.json':proof}
    for n,v in records.items():(OUT/n).write_text(json.dumps(v,indent=2)+'\n','utf-8')
    print('PASS: map registration, all 28 sprite geometry cases and exact 18 marker/filtering neighborhoods.',flush=True)
    if not args.disc:return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WMAP.AFS':archive});out=ROOT/'work/output'/VERSION
    for n,v in records.items():(out/n).write_text(json.dumps(v,indent=2)+'\n','utf-8')
    for n in ('font-mode-details.json','font-mode-component.json'):(out/n).write_text(json.dumps(mode,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
    for n,b in [('1ST_READ.BIN',exe),('WMAP.AFS',archive)]:m['files'].setdefault(n,{})['target_sha256']=digest(b)
    m['native_proof_reuse']={'source_build':PRIOR,'scope':'Native-only font/kernel exact; current framebuffer/map changes have separate native/live evidence.'}
    (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
