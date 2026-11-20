"""Feature-complete 0.7.23 catch-up with safe map filename reads. Dry first.

0.7.33's isolated memory/grid/loading/movie fixes already match final 0.7.23.
Preserve every final 0.7.23 asset and repair only the shared map-label guard.
"""
import argparse,copy,json
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from sh4_asm import Assembler
from build_font4x_patch import START

VERSION,PRIOR='0.7.34','0.7.23'
HELPER=0x8c07b69c
HOOK=0x8c018d00
SOURCE_SHA='6899e263653b1a29de45ee7bf04778e1ad240c40a99763511bd2da7ce9abbffe'
MANUAL='https://www.renesas.com/en/document/mas/sh-4-software-manual'


def filename_helper(*, entry=HELPER, name_address=None, capacity=0x44):
    a=Assembler(entry)
    a.rr('tst',1,1);a.branch('bt','fail')
    a.lit('name' if name_address is None else name_address,2)
    a.label('compare');a.emit(0x6014);a.emit(0x6324) # MOV.B @R1+,R0 / @R2+,R3
    a.rr('cmp/eq',3,0);a.branch('bf','fail')
    a.rr('tst',3,3);a.branch('bf','compare')
    a.emit(0x000b);a.emit(0x0009)  # T is set by matching the terminating zero
    a.label('fail');a.imm(1,0);a.rr('tst',0,0);a.emit(0x000b);a.emit(0x0009)
    if name_address is None:
        a.label('name');a.data.extend(b'wmap_en\0')
    code=a.pool_and_finish();assert len(code)<=capacity
    return code


def map_guard(*, helper=HELPER):
    a=Assembler(HOOK)
    a.imm(17,0);a.rr('cmp/hs',0,5);a.branch('bf','tail')
    a.imm(27,0);a.rr('cmp/hs',0,5);a.branch('bt','tail')
    a.emit(0x5146);a.rr('tst',1,1);a.branch('bt','tail')
    a.emit(0x5211);a.imm(2,0);a.rr('cmp/eq',0,2);a.branch('bf','tail')
    a.load('l',1,1);a.rr('tst',1,1);a.branch('bt','tail')
    a.addi(12,1);a.load('l',1,1)
    a.emit(0x4f22);a.lit(helper,3);a.emit(0x430b);a.emit(0x0009);a.emit(0x4f26)
    a.branch('bf','tail')
    a.rr('mov',4,1);a.imm(2,2)
    a.label('snap');a.emit(0xf019);a.emit(0xf03d);a.emit(0xf02d)
    a.addi(-4,1);a.emit(0xf10a);a.addi(4,1);a.unary('dt',2);a.branch('bf','snap')
    a.label('tail');a.lit(0x8c0ab970,3);a.emit(0x432b);a.emit(0x0009)
    code=a.pool_and_finish();assert HOOK+len(code)<=0x8c018d60,len(code)
    return code+bytes.fromhex('0900')*((0x60-len(code))//2)


FEATURES=[
    {'versions':'0.7.6','features':'All 961 story-choice boundaries; native-density map lettering/markers, with repaired shared filename guard.'},
    {'versions':'0.7.7-0.7.11','features':'Compact weapon/movie names; status marker alignment; complete Trust help and popup aliases; signed SP; compact notices; room tags; fitted location banners.'},
    {'versions':'0.7.12-0.7.15','features':'Loading placement and movie-edge correction; final Native-only font/kernel. HD bank and selector remain removed; superseded HD-only helpers are excluded.'},
    {'versions':'0.7.16-0.7.19','features':'Final lossless marker/window atlas compaction, corrected RGB565 startup and original stock graphics reservation. Superseded broken startup/temporary reserve values are excluded.'},
    {'versions':'0.7.20-0.7.23','features':'Movement grid, animation targeting/lines, Stage 6 lossless generated-text compression, split-battle clipping and full-width selectors.'},
    {'versions':'0.7.24-0.7.33','features':'Diagnostic rollbacks are not cumulative features. Final loading/movie/grid/stock-reservation spans already match 0.7.33; its RGB888 and padded legacy font runtime are superseded by the final emulator implementation.'}]


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old=(base/'1ST_READ.BIN').read_bytes()
    assert digest(old)==SOURCE_SHA
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    assert mode['native_only'] and mode['font_banks']==1
    assert START+mode['kernel_bytes']==HELPER-0x8c010000
    helper,guard=filename_helper(),map_guard()
    at=HELPER-0x8c010000
    assert old[at:at+len(helper)]==bytes.fromhex('0900')*(len(helper)//2)
    # The map guard abuts the Stage 6 encoder. Never extend into its code.
    from build_choice_map_fix import map_hook
    legacy,details=map_hook((ROOT/'work/output/0.7.5/1ST_READ.BIN').read_bytes())
    assert old[0x8d00:0x8d60]==legacy[0x8d00:0x8d60]
    exe=bytearray(old);exe[at:at+len(helper)]=helper;exe[0x8d00:0x8d60]=guard
    spans=[(at,at+len(helper)),(0x8d00,0x8d60)]
    changes=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]
    assert set(changes)<={i for a,b in spans for i in range(a,b)}
    assert exe[0x8d60:0x9000]==old[0x8d60:0x9000]
    # Explicitly retain the previous diagnostic's proven repair spans.
    reference=(ROOT/'work/output/0.7.33/1ST_READ.BIN').read_bytes()
    shared=[(0x6b900,0x6b918),(0x6b940,0x6b998),(0xc234e,0xc2356),(0xc24b4,0xc24b8),
            (0x360c8,0x360cc),(0xac2e4,0xac3f4),(0x9c690,0x9c694),(0x2a150,0x2a158)]
    for lo,hi in shared:assert exe[lo:hi]==reference[lo:hi]
    report={'version':VERSION,'date':'2026-11-04','source_build':PRIOR,
        'kind':'Full emulator-feature catch-up plus alignment-safe map filename guard',
        'source_executable_sha256':digest(old),'executable_sha256':digest(exe),
        'changed_executable_bytes_from_latest':len(changes),'allowed_spans':[[hex(a),hex(b)] for a,b in spans],
        'helper':hex(HELPER),'helper_bytes':len(helper),'map_guard':hex(HOOK),'map_guard_bytes':len(guard),
        'features':FEATURES,'all_assets':'Every game asset exact final local 0.7.23; no authored translation changes.',
        'repair':'Compare texture filenames byte by byte, including null; guard missing name arrays/filenames and preserve caller PR, stack and descriptor.',
        'defect_reference':{'manual':MANUAL,'PDF_page':39,'printed_page':17,
            'rule':'SH-4 word/longword reads require 2/4-byte alignment; byte reads accept any address.',
            'claim_limit':'Old guard can fault on valid unaligned filename pointers. Whether this exact condition occurred on the reporting Dreamcast remains unproven.'},
        'hardware_changes_vs_0_7_33':['Final RGB565 framebuffer setup replaces RGB888, matching emulator build.',
            'Final single Native bank/kernel, compact atlases, later UI/animation paths and Stage 6 text upload codec restored together at explicit user request.'],
        'known_limits':['Catch-up restores the full final feature set at once; this is a combined hardware candidate, not a confirmed hardware fix.',
            'No full-game pass is claimed; retest original conversation transitions, map/grid, battles, Stage 6 issue #1, saves and movies.',
            'Unidentified room tag and previously recorded long save-label/full-translation limitations remain.'],
        'font':'Original Skies Native 1x only; no HD bank or selector',
        'public_release':False,'upgrade_patch':False,'hardware_result':'pending'}
    return bytes(exe),report


def check(exe,report):
    from test_hardware_catchup import check_candidate
    return check_candidate(exe,report)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--check',action='store_true');args=p.parse_args()
    exe,report=compose();print(json.dumps(report,indent=2),flush=True)
    if not(args.write or args.check):print('DRY RUN: no files written.');return
    proof=check(exe,report)
    if not args.write:print(json.dumps(proof,indent=2));return
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(json.loads((base/'font-mode-details.json').read_text('utf-8')))
    mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    planned,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in planned[3] if planned[3][n]!=planned[2][n]]==['1ST_READ.BIN']
    planned[7].update(kind=report['kind'],component_manifest_name='hardware-catchup-component.json',
        proof_scope=proof['scope'],readme_component_text='Full final emulator features restored; only unsafe map filename reads repaired. Hardware testing pending.\n',pending=report['known_limits'])
    write_plan(planned,VERSION,PRIOR,{'1ST_READ.BIN':exe})
    out=ROOT/'work/output'/VERSION
    for name,data in [('hardware-catchup-component.json',report),('hardware-catchup-native-test.json',proof),('font-mode-details.json',mode)]:
        (out/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    path=out/'font4x-patch.json';m=json.loads(path.read_text('utf-8'))
    m.update(version=VERSION,previous_build=PRIOR,status='Full final feature catch-up; hardware result pending',current_payload_identities=planned[7]['files'],hardware_catchup=report)
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe);m['font_modes']={k:v for k,v in mode.items() if k not in ('metrics','labels','archive_packing')}
    path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    (out/'READ-ME.txt').write_text(f'Rayblade {VERSION}: full final emulator-feature catch-up, alignment-safe map filename guard.\n'
        'Apply full DCP to original Japanese image, output GDI, cold boot GDEMU/VGA.\n'
        'Combined hardware candidate, not a confirmed fix. No upgrade or public release.\n',encoding='utf-8')
    print('PASS: full feature catch-up checks and complete disc preservation.',flush=True)


if __name__=='__main__':main()
