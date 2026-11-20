"""Restore texture capacity and battle range coordinates on 0.7.32. Dry first."""
import argparse,copy,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_battle_grid_fix import adapter_code,ENTRY,POINTER,DRAW
from build_battle_memory_fix import UNITS
from build_startup_memory_fix import startup

VERSION,PRIOR='0.7.33','0.7.32'


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR
    old=(base/'1ST_READ.BIN').read_bytes()
    assert digest(old)=='1df8579f57db1300848c41c8f9b3fda0c8122a20d7994c239af26888cb4bcec6'
    exe=bytearray(old)
    # Reuse only the checked SDK allocation redirect and stock reservation;
    # leave the hardware-tested RGB888 display and every asset unchanged.
    code=bytearray(startup());assert len(code)==24
    assert struct.unpack_from('<I',code,16)[0]==0x200000
    struct.pack_into('<I',code,16,UNITS)
    assert old[0x6b900:0x6b918]==bytes.fromhex('0900')*12
    assert old[0xc234e:0xc2356]==bytes.fromhex('58e0de0b64e0de03')
    assert old[0xc24b4:0xc24b8]==bytes.fromhex('09000900')
    exe[0x6b900:0x6b918]=code
    struct.pack_into('<I',exe,0xc24b4,0x8c07b900)
    disp=(0x8c0d24b4-((0x8c0d234e+4)&~3))//4
    exe[0xc234e:0xc2356]=struct.pack('<4H',0xd000|disp,0x402b,9,9)
    grid=adapter_code();off=ENTRY-0x8c010000
    assert old[off:off+len(grid)]==bytes.fromhex('0900')*(len(grid)//2)
    assert struct.unpack_from('<I',old,POINTER)[0]==DRAW
    exe[off:off+len(grid)]=grid;struct.pack_into('<I',exe,POINTER,ENTRY)
    spans=[(0x6b900,0x6b918),(0xc234e,0xc2356),(0xc24b4,0xc24b8),(off,off+len(grid)),(POINTER,POINTER+4)]
    changes=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]
    assert set(changes)<={i for lo,hi in spans for i in range(lo,hi)}
    assert exe[0x10cb0:0x10cb4]==old[0x10cb0:0x10cb4]  # RGB888 / 640x480
    report={'version':VERSION,'date':'2026-11-04','source_build':PRIOR,
        'source_executable_sha256':digest(old),'executable_sha256':digest(exe),
        'kind':'Stock texture budget and range-grid coordinates on hardware-tested baseline',
        'changed_executable_bytes':len(changes),'allowed_spans':[[hex(a),hex(b)] for a,b in spans],
        'graphics_reservation':{'before_bytes':0x400000,'after_bytes':UNITS*2,
            'texture_capacity_recovered_bytes':0x400000-UNITS*2,
            'source':'Original Japanese SDK reservation; no framebuffer-format or video-mode change'},
        'range_grid':{'adapter':hex(ENTRY),'adapter_bytes':len(grid),'draw_pointer':hex(POINTER),
            'change':'Double XY once for the range-fill API, retaining masks, tile selection, camera logic, colors, flags and source arrays.'},
        'retained':'All assets, Native 1x font, 0.7.32 loading/movie corrections, RGB888 output, full-size movies and every other executable byte.',
        'excluded':'0.7.6 story-choice/map-label changes, HD/selector, RGB565 conversion, texture repacks and runtime text compression remain absent.',
        'limits':['Photos match earlier texture-allocation failures, but current physical allocation state was not captured; memory cause is a supported hypothesis, not directly proven on this build.',
            'Stock geometry reservation has a smaller list-growth interval at 640x480 than at 320x240; busy-battle/full-route hardware headroom still requires testing.',
            'Captured-RAM grid checks execute game code but are not a physical GPU or screenshot-scene replay.'],
        'hardware_result':'pending','original_conversation_freeze_fixed':False,'public_release':False,'upgrade_patch':False,
        'test':'Original Japanese image -> full DCP -> GDI; cold boot GDEMU/VGA. Revisit blank world-map dialogue/labels and battle unit shadows/dialogue; move the cursor and verify grid/arrow/unit alignment. Also retest New Game Hallway and normal Clear 2 VMU save -> Next.'}
    return bytes(exe),report


def budget_check(exe,old,report):
    from test_native_movie_font import DrawCPU,STOP,bits
    class CPU(DrawCPU):
        def execute(self,pc,delay=False):
            if pc==0x8c0e77e0:self.reg[0]=self.query;return self.pr
            return super().execute(pc,delay)
    rows=[]
    for version,image in ((PRIOR,old),(VERSION,exe)):
      for query in (0,1):
        # Stock RGB888 subtraction wraps in this bounded fixture. The SDK
        # chooses distinct caps for its two query outcomes; only query 0 was
        # observed in the prior live baseline. Do not report query 1 as a
        # measured physical reservation.
        cap=struct.unpack_from('<I',old,0xc2480 if query==1 else 0xc2484)[0]
        calculated=((0x800000-0x1b4fa8*4-0xe1000*2)&0xffffffff)>>1
        expected=min(calculated,cap) if version==PRIOR else UNITS
        c=CPU(image,b'',0,0);c.regions=[(0x8c000000,bytearray(0x1000000))]
        c.regions[0][1][0x10000:0x10000+len(image)]=image;c.query=query
        c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
        c.reg[13]=0x8c46214c;c.reg[14]=0x8c419b38
        for at,v in [(0x8c461bd0,0x800000),(0x8c46214c+92,0x1b4fa8),(0x8c46214c+96,0xe1000),(0x8c46214c+100,0xfd20)]:c.write(at,v,4)
        c.pc=0x8c0d230c;n=0
        while c.pc not in (0x8c0d2368,0x8c0d241a):
            assert n<1000;c.pc=c.execute(c.pc);n+=1
        assert c.pc==0x8c0d2368 and c.reg[11]==expected and c.read(0x8c4621a4,4)==expected,(version,query,c.reg[11])
        c.pc=c.execute(c.pc);n+=1
        assert c.pc==0x8c0e5200 and c.reg[4]==expected and expected>c.read(0x8c4621b0,4)
        rows.append({'version':version,'query':query,'geometry_units':expected,'geometry_VRAM_bytes':expected*2,
            'framebuffer_bytes_each':0xe1000,'SDK_minimum_units':c.read(0x8c4621b0,4),'reaches_allocator':True,'instructions':n})
    return {'executable_sha256':report['executable_sha256'],'actual_SDK_budget_cases':rows,
        'fixture_note':'Query 0 matches the prior observed default; query 1 exercises the alternate cap with the same bounded RAM fields, not a measured physical reservation.',
        'scope':'Actual SDK arithmetic, cap/redirect, minimum check and allocator entry; no physical residency/headroom claim.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');args=p.parse_args()
    exe,report=compose();print(json.dumps(report,indent=2),flush=True)
    if not(args.write or args.check):print('DRY RUN: no files written.');return
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    budget=budget_check(exe,old,report)
    from test_battle_grid import check_candidate
    grid=check_candidate(exe,old,report)
    if not args.write:print(json.dumps({'budget':budget,'grid':grid},indent=2));return
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(json.loads((base/'font-mode-details.json').read_text('utf-8')))
    mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    planned,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in planned[3] if planned[3][n]!=planned[2][n]]==['1ST_READ.BIN']
    planned[7].update(kind=report['kind'],component_manifest_name='hardware-map-grid-component.json',
        readme_component_text='Only stock geometry reservation and battle range-fill XY conversion change from 0.7.32.\n',
        proof_scope='Actual SDK budget/minimum checks and battle range construction across camera offsets; complete disc preservation.',pending=report['limits'])
    write_plan(planned,VERSION,PRIOR,{'1ST_READ.BIN':exe})
    out=ROOT/'work/output'/VERSION
    for name,data in (('hardware-map-grid-component.json',report),('hardware-budget-test.json',budget),('hardware-grid-test.json',grid),('font-mode-details.json',mode)):
        (out/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    path=out/'font4x-patch.json';m=json.loads(path.read_text('utf-8'))
    m.update(version=VERSION,previous_build=PRIOR,status='Map texture budget and movement grid candidate; hardware confirmation pending',current_payload_identities=planned[7]['files'],hardware_map_grid=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe);m['font_modes']={k:v for k,v in mode.items() if k not in ('metrics','labels','archive_packing')}
    path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    (out/'READ-ME.txt').write_text(f'Rayblade {VERSION}: map/battle texture capacity and range-grid test.\n'+report['test']+'\nNo upgrade or public release. Hardware confirmation pending.\n',encoding='utf-8')
    print('PASS: SDK budget, range-grid construction and complete disc preservation.',flush=True)


if __name__=='__main__':main()
