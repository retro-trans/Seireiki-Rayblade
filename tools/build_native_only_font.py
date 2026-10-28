"""Remove the selectable HD font; retain only the exact 640x480 Native bank. Dry first."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_font4x_patch import BASE,START,END,SMALL,MEDIUM,assemble,make_executable
from build_genei_font import SMALL_DATA,MEDIUM_DATA
from build_native_font_mode import FRAME_CALLEE,MODE,TITLE_HOOK
from build_text_filter_patch import ENTRY as FILTER,SETTER
from build_chapter_cards import repack
from build_map_font_patch import member
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from afs_layout import require_native_layouts
from sh4_asm import Assembler

VERSION,PRIOR='0.7.15','0.7.14'
OUT=ROOT/'work/output/native-only-candidate'
NATIVE_SHA='1b909b7fc3e2755a74f2d2da5dbc0b9b67dad90d31eb808ad5ed016adb71820e'


def filtering():
    a=Assembler(FILTER)
    a.lit(0x8c17fba0,0);a.load('l',0,0);a.rr('tst',0,0);a.branch('bt','tail')
    a.addi(38,0);a.load('w',0,0);a.rr('extu.w',0,0);a.emit(0x883f);a.branch('bf','tail')
    a.imm(0,4)  # Native text uses nearest filtering, independent of all old mode state.
    a.label('tail');a.lit(SETTER,0);a.emit(0x402b);a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=0x40
    return raw


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old=(base/'1ST_READ.BIN').read_bytes();source=(base/'WIN00.AFS').read_bytes()
    prior=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    combined=member(source,0);assert len(combined)==198144
    native=combined[99072:];assert digest(native)==NATIVE_SHA
    archive,packing=repack(source,{0:native},first=struct.unpack_from('<I',source,8)[0])
    packing['validation']='One Native font bank; all 89 other members byte-exact; SDK compact-sector offsets and sector read extents pass'
    assert member(archive,0)==native
    assert all(member(source,i)==member(archive,i) for i in range(1,90))
    require_native_layouts({'WIN00.AFS':archive})
    exe,labels,used,_=make_executable(old,wide=True,small_data=SMALL_DATA,medium_data=MEDIUM_DATA,
        antialias=True,native_only=True,native_surface_exponent=1,native_shadow_pixels=1)
    assert START+used<=0x6b6e0
    exe=bytearray(exe)
    # Preserve later 640x480 sprite/polygon/movie adapters and status-marker hook.
    exe[0x6b6e0:END]=old[0x6b6e0:END]
    assert struct.unpack_from('<I',old,0x10150)[0]==TITLE_HOOK
    assert prior['title_hook']['bytes']==0x1d0
    struct.pack_into('<I',exe,0x10150,FRAME_CALLEE)
    exe[0x6b900:0x6bad0]=bytes.fromhex('0900')*(0x1d0//2)
    # Retire the HD memory helper and all old selector state.
    exe[0x6bb7c:0x6bbe0]=bytes.fromhex('0900')*(0x64//2)
    exe[0x6bbe0:0x6bc00]=bytes(32)
    raw=filtering();exe[0x6b800:0x6b840]=raw+bytes.fromhex('0900')*((0x40-len(raw))//2)
    assert struct.pack('<I',MODE) not in exe[START:END]
    assert not any(name in labels for name in ('r_selected_font','r_shadow_selected','a_selected_scale'))
    assert exe[0x6b6e0:0x6b800]==old[0x6b6e0:0x6b800]
    assert exe[0x6b840:0x6b900]==old[0x6b840:0x6b900]
    assert exe[0x6bad0:0x6bb7c]==old[0x6bad0:0x6bb7c]
    allowed=[(START,END),(0x10150,0x10154),(0x684b0,0x684b4),(0x22118,0x2211c),
             (0x6ab98,0x6abfa),(0x22d1a,0x22d68)]
    changes=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]
    assert all(any(lo<=i<hi for lo,hi in allowed) for i in changes)
    report={'version':VERSION,'source_build':PRIOR,'native_only':True,'native_surface_scale':2,
        'output_resolution':[640,480],'logical_UI_grid':[320,240],
        'font':'Original Skies of Arcadia USA Dreamcast Native bank; exact 0.7.14 pixels, widths and four alpha levels',
        'font_member_bytes':len(native),'native_bank_sha256':digest(native),'font_banks':1,
        'removed':['HD font bank','Title X/Y font selector, labels and state','HD-dependent raster, shadow and allocation branches','0.7.14 HD surface fallback helper'],
        'native_filter':'Nearest; fixed for dynamic text resource only',
        'surface_policy':'Preferred one texel per 640x480 output pixel (two per 320x240 logical coordinate); legacy 1024-edge and CPU allocation-failure guards retained',
        'source_executable_sha256':digest(old),'executable_sha256':digest(exe),'archive_sha256':digest(archive),
        'kernel_bytes':used,'labels':labels,'archive_other_members_exact':89,
        'archive_layout':{k:v for k,v in packing.items() if k!='members'},
        'preserved':'VGA/640x480 output, original movies and movie-edge fix, loading placement, dialogue wrapping, menu layout and all other payloads',
        'release':False,'live_validation':'pending'}
    return bytes(exe),archive,native,{},report


def check():
    from test_font4x_patch import HDCPU
    from test_outline_font import legacy_mask,expected_pixels
    from test_native_movie_font import DrawCPU,run as execute,STOP,bits
    exe,archive,font,_,report=compose();steps=cases=0
    # Historical assembler modes must stay byte-exact for earlier build recipes.
    common=dict(wide=True,small_data=SMALL_DATA,medium_data=MEDIUM_DATA,antialias=True)
    assert digest(assemble(**common)[0])=='bfddd0917b10d56fc2281fd49bd0924434c67b70498a4636cc8fe3ffec7e432c'
    assert digest(assemble(**common,font_mode_address=MODE,native_font_offset=99072,
        native_surface_exponent=1,native_shadow_pixels=1)[0])=='0623fbf2d769722de47f3cc8a3c7db0ecc033a4f2207dcfeac3db79b5ceedb87'
    for small,chars in ((True,SMALL),(False,MEDIUM)):
      for i,ch in enumerate(chars):
       for bg in (0,128):
        flags=(64 if small else 0)|bg
        c=HDCPU(exe,font,i+32 if small else i,flags,w=64,h=32,ex=1,ey=1)
        mask=legacy_mask(font,ch,small)
        if ch.isascii():mask=mask[:,:32]
        expected=expected_pixels(c,mask,flags,12,4,shadow_pixels=1)
        steps+=c.run_until(limit=300000)
        assert c.regions[3][1]==expected,(small,ch,bg)
        assert c.read(0x8c1f36b6,2)==12+font[(0x20 if small else 0xa0)+i]
        cases+=1
    allocations=[]
    # Same allocation order and backing sizes as the four status panels.
    c=HDCPU(exe,font)
    for slot,(w,h) in enumerate(((256,128),(256,128),(128,128),(128,128))):
        ctx=0x8c1f0d3c+slot*92;c.reg[8]=ctx;c.write(ctx+10,w,2);c.write(ctx+12,h,2)
        c.pc=report['labels']['allocate'];steps+=c.run_until();p=c.reg[0];c.write(ctx,p,4)
        assert c.read(p+12,1)==c.read(p+13,1)==1
        allocations.append({'status_panel':slot,'logical':[w,h],'physical':[c.read(p+28,2),c.read(p+30,2)],'pixel_bytes':c.read(p+20,4)})
    # The formerly white Load File and Status surfaces now fit both captured pools.
    gpu=[]
    for ram_name,capacity in [('hd-white-load.ram',903168),('hd-fixed-status-white.ram',641024)]:
      ram=(ROOT/'work/source/runtime'/ram_name).read_bytes()
      for w,h in ((256,128),(256,256)):
        c=DrawCPU(exe,b'',0,0);c.regions=[(0x8c000000,bytearray(ram))]
        c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
        c.reg[4:6]=[0x8cffd000,0x8cffd004];steps+=execute(c,0x8c0e59e6)
        assert c.read(0x8cffd004,4)==capacity
        p=0x8cffd100;c.pr=STOP;c.reg[4:8]=[p,w*2,h*2,0x902]
        steps+=execute(c,0x8c0e1c4c);assert c.reg[0]==0
        c.pr=STOP;c.reg[4:6]=[c.read(p+20,4),p];steps+=execute(c,0x8c0e52a0);assert c.reg[0]==0
        gpu.append({'capture':ram_name,'pool_capacity':capacity,'logical':[w,h],'physical':[w*2,h*2],'native_allocation_status':0})
    filters=[]
    for resource in (None,62,63):
      for requested in (0,1,3):
        c=DrawCPU(exe,b'',0,0);data=bytearray(ram)
        data[0x7b800:0x7b840]=exe[0x6b800:0x6b840]
        c.regions=[(0x8c000000,data)];c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
        obj=0x8cffd200;c.write(0x8c17fba0,obj if resource is not None else 0,4)
        if resource is not None:c.write(obj+38,resource,2)
        c.reg[4]=requested;c.pc=FILTER;saved=c.reg[8:]
        for n in range(100):
            if c.pc==SETTER:break
            c.pc=c.execute(c.pc)
        else:raise AssertionError('Filter dispatcher did not tail-call original setter')
        steps+=n;expected=0 if resource==63 else requested
        assert c.reg[4]==expected and c.reg[8:]==saved and c.pr==STOP
        filters.append({'resource':resource,'requested':requested,'actual':c.reg[4]})
    return {**report,'glyph_cases':cases,'status_allocations':allocations,'native_gpu_cases':gpu,
        'filter_cases':filters,'title_callback':'Original frame callback restored; selector code and labels erased',
        'SH4_instructions':steps,'pixels_advances_ABI_guard_bytes':'pass',
        'historical_assembler_modes_byte_exact':True,'archive_native_layout':'pass',
        'limits':['Heap/clear endpoints are bounded fixtures; GPU allocation executes on copied native free lists',
                  'Live title/load/status confirmation required','Physical Dreamcast/full-game coverage pending','Stage 6 issue #1 unresolved']}


def plan():
    p,report=font_plan(compose_fn=compose,prior=PRIOR,version=VERSION)
    p[7].update(kind='Native 1x font only',component_manifest_name='native-only-component.json',
        readme_component_text='Only the Native (1x) Skies font is included. The HD bank and title font switch are removed.\n'
            'Cold-boot this GDI; use a normal VMU save, not an older emulator save state.\n',
        current_native_evidence={'native_only':'native-only-native-test.json'},
        inherited_proof_note='Historical reports retain tested build identities; current font/kernel proof is native-only-native-test.json.',
        proof_scope='Single Native bank, native raster/allocation, original title callback, SDK-compatible archive repack and complete disc preservation.',
        pending=['Live title/load/status font confirmation','Physical hardware and full-game/route review','Stage 6 issue #1'])
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');args=ap.parse_args()
    exe,archive,font,_,report=compose()
    if not args.write:print(json.dumps({k:v for k,v in report.items() if k!='labels'},indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True)
    for name,raw in [('1ST_READ.BIN',exe),('WIN00.AFS',archive)]: (OUT/name).write_bytes(raw)
    records={'native-only-component.json':report,'native-only-native-test.json':proof}
    for name,data in records.items():(OUT/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    print('PASS:',proof['glyph_cases'],'native glyph cases, four status panels and four native GPU allocations.',flush=True)
    if not args.disc:return
    p=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':archive});out=ROOT/'work/output'/VERSION
    for name,data in records.items():(out/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    # Both common metadata names now describe the one-bank configuration.
    for name in ('font-mode-details.json','font-mode-component.json'):(out/name).write_text(json.dumps(report,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'))
    m.update(version=VERSION,previous_build=PRIOR,status='Native 1x only; HD removed',current_payload_identities=p[7]['files'],
        kernel_bytes_used=report['kernel_bytes'],font_modes={k:v for k,v in report.items() if k!='labels'},
        surface_scaling=report['surface_policy'],historical_component_reports='Historical identities retained; current member 0 contains only the Native bank, other 89 members exact.')
    m.pop('hd_surface',None)
    m.pop('glyph_source_scale',None)
    m['native_proof_reuse']={'source_build':PRIOR,'scope':'Current single-bank font/kernel/filter checks are native-only-native-test.json; other executable regions and 89 archive payloads retain historical identities.'}
    m['symbols']={k:hex(report['labels'][k]) for k in ('raster','allocate','initialize','flush')}
    for name,raw in [('1ST_READ.BIN',exe),('WIN00.AFS',archive)]:m['files'][name]['target_sha256']=digest(raw)
    off,size=struct.unpack_from('<II',archive,8+52*8);m['library'].update(archive_member_offset=off,archive_member_bytes=size)
    (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
    lib=json.loads((out/'library-patch-report.json').read_text('utf-8'));lib.update(archive_member_offset=off,archive_member_bytes=size)
    (out/'library-patch-report.json').write_text(json.dumps(lib,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
