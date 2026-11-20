"""Execute current combined-build routines; no live hardware claim."""
import struct
from build_bitmap_font import ROOT,digest
from build_map_font_patch import member


def status_checks(exe,font,*,gate=None):
    from test_library_layout import fresh,run,BASE
    from build_hardware_consolidated import STATUS_GATE
    if gate is None:gate=STATUS_GATE
    rows=[];steps=0
    for script in (0xeee6,0xef01,0xef15,0xef29,0xe70b,0xfdbf,0xf634,0xf7ae):
        before,after=fresh(exe,font),fresh(exe,font)
        for c in (before,after):c.write(0x8c1dbe24,BASE+script+1,4)
        saved=after.reg[8:];sp=after.reg[15]
        steps+=run(before,0x8c07d978)
        after.pc=gate;visited=set();min_sp=sp
        for n in range(600000):
            if after.pc==0xdead0000:break
            visited.add(after.pc);min_sp=min(min_sp,after.reg[15]);after.pc=after.execute(after.pc)
        else:raise AssertionError('Constructor did not return')
        steps+=n
        assert after.reg[8:]==saved and after.reg[0]==before.reg[0] and after.pr==before.pr
        status=script in (0xef01,0xef29)
        assert (0x8c07bad0 in visited)==status
        if not status:
            assert bytes(after.regions[1][1])==bytes(before.regions[1][1])
        slot=after.read(0x8c1f24cd,1);assert slot==before.read(0x8c1f24cd,1)
        for linked in range(4):
            ctx=0x8c1f0cf8+(slot+linked)*92
            a=bytes(before.read(ctx+i,1) for i in range(92));b=bytes(after.read(ctx+i,1) for i in range(92));expected=bytearray(a)
            if status:
                for off in ((0x32,0x4c) if linked==0 else (0x32,)):
                    struct.pack_into('<H',expected,off,struct.unpack_from('<H',a,off)[0]+2)
            assert b==expected,(hex(script),linked)
        assert before.read(0x8c1dbe24,4)==after.read(0x8c1dbe24,4)
        rows.append({'script':hex(script),'status_adjustment':status,'extra_status_wrapper_entered':status,'stack_bytes':sp-min_sp})
    # Verify the routing independently for arbitrary dialogue VM addresses.
    # No wrapper body or callee is faked in the constructor cases above.
    for pc in (0,1,0x8c800001,0x8c800400,0x8c01ef01,0x8c01ef03,0xffffffff):
        c=fresh(exe,font);c.write(0x8c1dbe24,pc,4);sp=c.reg[15];pr=c.pr;regs=c.reg[8:]
        steps+=run(c,gate,0x8c07d978)
        assert c.reg[15]==sp and c.pr==pr and c.reg[8:]==regs
    return {'actual_constructor_cases':rows,'non_status_routing_cases':7,'SH4_instructions':steps,
            'status_contexts_and_linked_tiles':'Only intended Y fields shifted by two; VM advance and return ABI match',
            'other_contexts':'Exact native context memory; direct retail constructor without extra frame'}


def check_candidate(exe,archive,mode,report,*,status_gate=None,map_validator=None):
    from test_hardware_catchup import font_check
    from build_hardware_map_bypass import check as map_check
    from test_battle_grid import check_candidate as grid
    from test_battle_target import check_candidate as target
    from test_battle_clip import check_candidate as clip
    from test_stage6_text import check_candidate as codec
    from build_hardware_display_polish import check as polish
    font=member(archive,0)
    proof={'version':report['version'],'executable_sha256':digest(exe),'archive_sha256':digest(archive)}
    proof['status']=status_checks(exe,font,gate=status_gate)
    proof['font']=font_check(exe,font,99072)
    proof['map']=dict((map_validator or map_check)(exe),version=report['version'])
    print('PASS: Native pixels/advances, status-only routing, actual constructors and map drawing.',flush=True)
    proof['grid']=grid(exe,(ROOT/'work/output/0.7.19/1ST_READ.BIN').read_bytes(),report)
    proof['target']=target(exe,report)
    proof['clip']=clip(exe,report,relocated_text_allocator=True)
    print('PASS: grid, targeting, split clipping, line adapters and selectors.',flush=True)
    proof['stage6_text']=codec(exe,report,labels=mode['labels'])
    print('PASS: Stage 6 exact text encoding, relocated allocator, upload/append and SDK admission.',flush=True)
    # Cosmetic routine identities match 0.7.40; exercise them on this EXE too.
    from build_hardware_display_polish import compose as cosmetic
    _,old_cosmetic=cosmetic()
    cosmetic_report={'version':report['version'],'executable_sha256':digest(exe),
        'kind':'Loading/movie regression checks within consolidated build',
        'loading':old_cosmetic['loading'],'movie_edge':old_cosmetic['movie_edge']}
    proof['loading'],proof['movie_edge']=polish(exe,cosmetic_report)
    proof['loading']['checks'][-1]='Loading/movie routines match 0.7.40; other restored features are checked separately.'
    # Confirm imported name stream with the actual game decoder and original
    # final decoded bytes. This covers the complete UI changes, not a sample.
    from check_native_text_components import verify
    base=ROOT/'work/output/0.7.23/text'
    proof['names_PRS_instructions']=verify(exe,(base/'D_NAMES.BIN').read_bytes(),(base/'D_NAMES.en.dec.bin').read_bytes(),65536)
    print('PASS: loading/movie geometry and complete final UI name-stream decode.',flush=True)
    proof['scope']='Current-executable SH-4 checks: status routing/constructors, exact Native pixels, map bypass, grid/target/clip, relocated Stage 6 allocator/encoder/upload/SDK, loading/movie geometry and UI PRS. Bounded heap/cache/GPU endpoints and historical RAM fixtures; no fresh emulator/hardware execution or full-route claim.'
    return proof
