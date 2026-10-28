"""Correct the 0.7.16 startup transition. Dry first; local candidate only."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from sh4_asm import Assembler
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.17','0.7.16'
OUT=ROOT/'work/output/startup-memory-candidate'
ENTRY=0x8c07b900
ORIGINAL=0x8c0d2356


@lru_cache(maxsize=1)
def window_atlas():
    import numpy as np
    from build_map_font_patch import member,packed_pvr
    from rayblade_codec import decompress
    from audit_texture_archive import untwiddle_indices
    from build_chapter_cards import repack
    source=(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes();old=member(source,1);dat=bytearray(old)
    packed=member(source,2);raw=decompress(packed[16:])[0]
    assert struct.unpack_from('<IHH',raw,24)==(0xd00,512,512)
    plane=np.frombuffer(raw[32:],dtype='<u2')[untwiddle_indices(512,512)]
    assert not plane[224:].any()
    start=4+struct.unpack_from('<I',dat,4)[0];assert start==48 and len(dat)==start+125*20+12
    for i in range(125):
        at=start+i*20;w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',old,at)
        assert tex==0 and max(v0,v1)<=112
        struct.pack_into('<H',dat,at+10,v0*2);struct.pack_into('<H',dat,at+14,v1*2)
    target,decoded=packed_pvr(plane[:256],0xd00,struct.unpack_from('<I',raw,8)[0])
    # Preserve both the runtime GBIX prefix and the decoded GBIX identity.
    target=packed[:16]+target[16:]
    archive,packing=repack(source,{1:bytes(dat),2:target},first=struct.unpack_from('<I',source,8)[0])
    assert all(member(source,i)==member(archive,i) for i in range(90) if i not in (1,2))
    return archive,bytes(dat),decoded,{'old_dimensions':[512,512],'new_dimensions':[512,256],
        'sprites':125,'saved_VRAM_bytes':262144,'original_upper_half_pixels_sha256':digest(plane[:256].tobytes()),
        'archive_sha256':digest(archive),'other_members_exact':88,'font_member_exact':True,
        'preservation':'Entire upper half and all 125 sprite sizes/anchors/IDs unchanged; only normalized V coordinates doubled; discarded rows entirely zero'}


def startup():
    a=Assembler(ENTRY)
    # Preserve the actual 0.7.15 TA reservation. The inherited buffer-size
    # calculation wraps unsigned subtraction at 24 bpp, then caps at 2 MiB allocator units (4 MiB VRAM).
    # At 16 bpp it no longer wraps and yields only 176 bytes, below the minimum:
    # system initialization returns 3 before creating either framebuffer.
    # The SDK allocator doubles this value for interleaved VRAM addressing.
    a.lit(0x200000,11);a.imm(88,0);a.emit(0x0db6)
    a.imm(100,0);a.emit(0x03de)
    a.lit(ORIGINAL,0);a.emit(0x402b);a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=0x1d0
    return raw


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(old)
    assert exe[0x10cb0:0x10cb4]==bytes.fromhex('01e531e4')
    # Katana display enum 0 is RGB565. Enum 1 is RGB555: verified against the
    # SDK's bit-depth table and native read/write format selection, not PVR enums.
    exe[0x10cb0:0x10cb2]=bytes.fromhex('00e5')
    assert exe[0xc234e:0xc2356]==bytes.fromhex('58e0de0b64e0de03')
    assert exe[0xc24b4:0xc24b8]==bytes.fromhex('09000900')
    # SDK padding literal, reached only by the new PC-relative load.
    struct.pack_into('<I',exe,0xc24b4,ENTRY)
    disp=(0x8c0d24b4-((0x8c0d234e+4)&~3))//4
    exe[0xc234e:0xc2356]=struct.pack('<4H',0xd000|disp,0x402b,9,9)
    raw=startup();assert exe[ENTRY-0x8c010000:ENTRY-0x8c010000+len(raw)]==bytes.fromhex('0900')*(len(raw)//2)
    exe[ENTRY-0x8c010000:ENTRY-0x8c010000+len(raw)]=raw
    changes=[i for i,(x,y) in enumerate(zip(old,exe)) if x!=y]
    assert all(i==0x10cb0 or 0xc234e<=i<0xc2356 or 0xc24b4<=i<0xc24b8 or 0x6b900<=i<0x6b900+len(raw) for i in changes)
    # No glyph, allocator, filtering or marker hook is changed.
    assert exe[0x6b28e:0x6b900]==old[0x6b28e:0x6b900] and exe[0x6bad0:0x6bc00]==old[0x6bad0:0x6bc00]
    archive,_,_,window=window_atlas()
    report={'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),'window_atlas':window,
        'startup_hook':{'entry':hex(ENTRY),'original_tail':hex(ORIGINAL),'bytes':len(raw),
            'TA_allocator_units':0x200000,'TA_reservation_bytes':0x400000,'matches_0715_reservation':True,
            'cause':'Inherited unsigned geometry-budget subtraction wraps at 24 bpp but yields only 176 allocator units at 16 bpp; initialization fails before framebuffer creation',
            'scope':'Explicitly retain existing 4 MiB geometry reservation; original SDK framebuffer creation/clearing and remaining initialization execute normally'},
        'display':{'SDK_enum':0,'format':'RGB565','resolution':[640,480],'buffers':2,'framebuffer_bytes':1228800,
            'corrected_prior_claim':'0.7.16 enum 1 selects RGB555, not RGB565'},
        'combined_VRAM_saving_from_0715':1335296,
        'preserved':'Native-only font pixels, widths, alpha, dynamic surface allocation, all window sprite pixels/anchors, WMAP lossless marker repack, all wording and original movies',
        'release':False,'live_validation':'pending'}
    return bytes(exe),report


def check():
    from test_native_movie_font import DrawCPU,STOP,bits,run
    exe,report=compose();budget=[]
    # Actual SDK arithmetic, cap, replacement and minimum check. Only the
    # configuration-query endpoint is bounded to the live default value 0.
    class BudgetCPU(DrawCPU):
        def execute(self,pc,delay=False):
            if pc==0x8c0e77e0:self.reg[0]=0;return self.pr
            return super().execute(pc,delay)
    for name,image,fb,expected,ok in [('0715',(ROOT/'work/output/0.7.15/1ST_READ.BIN').read_bytes(),0xe1000,0x200000,True),
        ('0716',(ROOT/'work/output/0.7.16/1ST_READ.BIN').read_bytes(),0x96000,0xb0,False),
        ('0717',exe,0x96000,0x200000,True)]:
        c=BudgetCPU(image,b'',0,0);c.regions=[(0x8c000000,bytearray(0x1000000))]
        c.regions[0][1][0x10000:0x10000+len(image)]=image;c.reg[15]=0x8cffe000;c.pr=STOP
        c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set();c.reg[13]=0x8c46214c;c.reg[14]=0x8c419b38
        for at,v in [(0x8c461bd0,0x800000),(0x8c46214c+92,0x1b4fa8),(0x8c46214c+96,fb),(0x8c46214c+100,0xfd20)]:c.write(at,v,4)
        c.pc=0x8c0d230c;n=0
        while c.pc not in (0x8c0d2368,0x8c0d241a):
            assert n<1000;c.pc=c.execute(c.pc);n+=1
        actual=c.read(0x8c46214c+88,4)
        assert actual==expected and (c.pc==0x8c0d2368)==ok
        if ok:assert c.reg[4]==0x200000
        budget.append({'build':name,'TA_allocator_units':actual,'TA_VRAM_bytes':actual*2,'reaches_native_allocator':ok,'instructions':n})
    # Run actual SDK configuration selection. Stop before the unrelated
    # division/geometry/timing tail, after both read/write format fields exist.
    formats=[]
    for fmt,depth,wr,rd in [(0,16,1,1),(1,16,0,0),(4,24,4,2)]:
        d=DrawCPU(exe,b'',0,0);d.regions=[(0x8c000000,bytearray(0x1000000))]
        d.regions[0][1][0x10000:0x10000+len(exe)]=exe
        d.reg[15]=0x8cffe000;d.pr=STOP;d.fr=[bits(0.)]*16;d.fpul=0;d.visited=set()
        d.reg[4:8]=[640,480,fmt,1];d.write(0x8c461bdc,0x31,4)
        d.pc=0x8c0e9ce0;n=0
        while d.pc!=0x8c0e9e68:
            assert n<2000
            d.pc=d.execute(d.pc);n+=1
        p=d.reg[14]
        assert d.reg[11]==depth and d.read(p+48,4)==wr and d.read(p+60,4)==rd
        formats.append({'enum':fmt,'bits_per_pixel':depth,'write_format':wr,'read_format':rd,'instructions':n})
    import numpy as np
    from build_map_font_patch import member
    from test_ui_images import scalar_plane,texture_info
    from test_map_font_patch import GeometryCPU
    from check_attack_variant_selection import run as geometry_run
    from check_native_text_components import verify
    from test_ordered_archive_layouts import directory_bytes,lookup
    from afs_layout import compact_positions,require_native_layouts
    archive,dat,raw,window=window_atlas();steps=texture_info(exe,512,256,0xd00)
    require_native_layouts({'WIN00.AFS':archive});directory=directory_bytes('WIN00.AFS',archive)
    for row in compact_positions(archive):
        off,count,n=lookup(exe,'WIN00.AFS',directory,row['member']);steps+=n
        assert off==row['declared_offset'] and count==row['sectors']
    steps+=verify(exe,member(archive,2)[16:],raw,len(raw),instruction_limit=40000000)
    from rayblade_codec import decompress
    source=(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()
    original=scalar_plane(decompress(member(source,2)[16:])[0],512,512);cropped=scalar_plane(raw,512,256)
    assert np.array_equal(original[:256],cropped)
    old=member(source,1)
    for i in range(125):
        w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',dat,48+i*20)
        prior=struct.unpack_from('<HHhh6H',old,48+i*20)
        assert (w,h,cx,cy,u0,v0//2,u1,v1//2,tex,flags)==prior
        # Includes filtering neighborhoods and wrapped top-edge samples.
        ox,oy,ex,ey=prior[4]*2,prior[5]*2,prior[6]*2,prior[7]*2
        xs=np.arange(min(ox,ex)-1,max(ox,ex)+2)%512;ys=np.arange(min(oy,ey)-1,max(oy,ey)+2)
        assert np.array_equal(original[np.ix_(ys%512,xs)],cropped[np.ix_(ys%256,xs)])
        c=GeometryCPU(exe,b'',0,0);c.regions=[(0x8c010000,bytearray(exe)),(0x8c500000,bytearray(dat)),(0x8c510000,bytearray(32)),(0x8c700000,bytearray(0x2000))]
        c.reg[4:7]=[0x8c510000,i,0];c.reg[8]=0x8c701000;c.reg[15]=0x8c700fc0
        c.write(0x8c51001c,0x8c500030,4);c.write(0x8c51000c,bits(1.),4);c.write(0x8c510010,bits(1.),4)
        c.fr=[0]*16;c.fpul=0;c.visited=set();steps+=geometry_run(c,0x8c0ac310,0x8c0ac39c,1000)
        f=lambda x:struct.unpack('<f',struct.pack('<I',x))[0]
        assert [f(x) for x in c.fr[:4]]==[-float(cx),-float(cy),float(w-cx),float(h-cy)]
        assert [f(c.read(0x8c700fe0+j*4,4)) for j in range(8)]==[v1/256,u1/256,v0/256,u1/256,v1/256,u0/256,v0/256,u0/256]
    return {**report,'actual_SDK_geometry_budget_cases':budget,'actual_SDK_format_cases':formats,
        'window_native_instructions':steps,'window_native_geometry_cases':125,'window_native_archive_lookups':90,
        'window_pixel_and_filtering_neighborhoods':'all 125 exact; all 131072 upper-half texels exact',
        'limits':['Actual display/GPU and early startup require live cold-boot review','Physical Dreamcast pending','Stage 6 issue #1 unresolved']}


def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive,_,_,window=window_atlas()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    mode['archive_sha256']=digest(archive)
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Startup geometry reservation and correct RGB565 mode',component_manifest_name='startup-memory-component.json',
        current_native_evidence={'startup_memory':'startup-memory-native-test.json'},
        readme_component_text='Native 1x font only, 640x480 RGB565. Startup explicitly retains the existing 4 MiB geometry reservation.\n'
            'Retains the lossless map marker atlas repack from 0.7.16 and removes unused window-atlas rows.\n',
        proof_scope='Actual SDK geometry budget/minimum check and pixel format selection, complete disc preservation; live display/map validation recorded separately.',
        pending=['Live boot/movie/map validation','Physical hardware/full-game review','Stage 6 issue #1'])
    return p,mode


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');args=ap.parse_args()
    exe,r=compose()
    if not args.write:print(json.dumps(r,indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True);(OUT/'1ST_READ.BIN').write_bytes(exe)
    archive,_,_,_=window_atlas();(OUT/'WIN00.AFS').write_bytes(archive)
    records={'startup-memory-component.json':r,'startup-memory-native-test.json':proof}
    for n,v in records.items():(OUT/n).write_text(json.dumps(v,indent=2)+'\n','utf-8')
    print('PASS: actual SDK geometry budget and pixel format selection.',flush=True)
    if not args.disc:return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':archive});out=ROOT/'work/output'/VERSION
    for n,v in records.items():(out/n).write_text(json.dumps(v,indent=2)+'\n','utf-8')
    for n in ('font-mode-details.json','font-mode-component.json'):(out/n).write_text(json.dumps(mode,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    m['files']['WIN00.AFS']['target_sha256']=digest(archive)
    off,size=struct.unpack_from('<II',archive,8+52*8);m['library'].update(archive_member_offset=off,archive_member_bytes=size)
    (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
    lib=json.loads((out/'library-patch-report.json').read_text('utf-8'));lib.update(archive_member_offset=off,archive_member_bytes=size)
    (out/'library-patch-report.json').write_text(json.dumps(lib,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
