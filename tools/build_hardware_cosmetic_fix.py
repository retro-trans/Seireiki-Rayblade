"""Backport only loading geometry and movie-edge sampling onto working 0.7.31.

Dry by default. No 0.7.6 or later unrelated feature is restored.
"""
import argparse
import copy
import json
import struct
from functools import lru_cache

from build_bitmap_font import ROOT,digest
from build_loading_position_fix import OFFSET,check_candidate as check_loading
from build_movie_edge_fix import START,END,geometry_code,check_candidate as check_movie

VERSION,PRIOR='0.7.32','0.7.31'


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR
    old=(base/'1ST_READ.BIN').read_bytes()
    assert digest(old)=='054d99fbd8a29d981d4ba478b05a3817181c8dfd77267e30208bdbb0b15de020'
    assert struct.unpack_from('<f',old,OFFSET)[0]==8.
    assert old[START:END]==(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()[START:END]
    exe=bytearray(old)
    struct.pack_into('<f',exe,OFFSET,16.)
    exe[START:END]=geometry_code()
    changes=[i for i,(a,b) in enumerate(zip(old,exe)) if a!=b]
    assert set(changes)<=set(range(START,END))|{OFFSET+2}
    # The 0.7.5 movie-size setters and every font/video/map span stay exact.
    assert exe[0x2a150:0x2a158]==old[0x2a150:0x2a158]
    assert exe[0x6b200:0x6bbe0]==old[0x6b200:0x6bbe0]
    report={
        'date':'2026-11-04','version':VERSION,'source_build':PRIOR,
        'source_executable_sha256':digest(old),'executable_sha256':digest(exe),
        'kind':'Loading position and movie-edge corrections on reported working 0.7.31',
        'changed_executable_bytes':len(changes),
        'allowed_spans':[hex(OFFSET+2),[hex(START),hex(END)]],
        'loading':{'SDK_print_default_cell_pixels':{'before':8,'after':16},
                   'physical_origin_before':[216,208],'physical_origin_after':[432,416],
                   'change':'Restore original proportional size/position in the existing 640x480 output; retain character cells, colors and animation.'},
        'movie_edge':{'change':'Inset four-corner sampling by half a texel to avoid unused padding; retain movie screen size, position, streams and audio.',
                      'patch_range':[hex(START),hex(END)]},
        'retained':'Every other executable byte and all 13 non-executable modified game payloads stay exact 0.7.31. Native 1x only; no HD font/selector.',
        'excluded':'Historical 0.7.6 story-choice/map changes and every other later feature remain absent.',
        'hardware_result':'pending','cause_of_original_freeze_confirmed':False,
        'test':'Full original-input DCP -> GDI; cold boot GDEMU/VGA. Check NOW LOADING location, bottom movie edge and full-size playback, New Game first dialogue and Koichiro/Kasumi Hallway, then normal Clear 2 VMU save -> Next.',
        'public_release':False,'upgrade_patch':False}
    return bytes(exe),report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    exe,report=compose()
    print(json.dumps(report,indent=2),flush=True)
    if not args.write:
        print('DRY RUN: no files written.');return
    base=ROOT/'work/output'/PRIOR
    old=(base/'1ST_READ.BIN').read_bytes()
    loading=check_loading(exe,old,{**report,**report['loading']})
    loading['pre_640_reference']='0.7.2 loading routine, SDK print code and character/color data are byte-exact in baseline 0.7.31.'
    loading['checks'][-1]='Loading geometry uses one default-size byte; the combined candidate also changes only the separately tested movie-quad span.'
    edge=check_movie(exe,old,{**report,**report['movie_edge']})
    # Earlier limits mention later Stage 6 repairs absent from this baseline;
    # record current proof scope rather than importing a later build identity.
    for proof in (loading,edge):
        proof['limits']=['GPU output and physical hardware confirmation pending. Historical baseline bugs remain; no full-game compatibility claim.']
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    archive=(base/'WIN00.AFS').read_bytes()
    mode=copy.deepcopy(json.loads((base/'font-mode-details.json').read_text('utf-8')))
    assert mode['native_only'] and not mode['title_selector'] and mode['HD_bank_removed']
    mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    planned,_=plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    assert [n for n in planned[3] if planned[3][n]!=planned[2][n]]==['1ST_READ.BIN']
    planned[7].update(kind=report['kind'],component_manifest_name='hardware-cosmetic-component.json',
        proof_scope='Actual loading animation/SDK print packets and old/new Sofdec quad generation; unchanged assets and other executable bytes.',
        readme_component_text='Only NOW LOADING geometry and movie-edge sampling change from reported working 0.7.31.\n',
        pending=['Physical GDEMU/VGA loading/movie checks and regression test of the reported working scenario paths.'])
    write_plan(planned,VERSION,PRIOR,{'1ST_READ.BIN':exe})
    out=ROOT/'work/output'/VERSION
    for name,data in (('hardware-cosmetic-component.json',report),('loading-position-native-test.json',loading),
                      ('movie-edge-native-test.json',edge),('font-mode-details.json',mode)):
        (out/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    path=out/'font4x-patch.json';manifest=json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,status='Only loading and movie-edge cosmetic fixes; hardware test pending',
                    current_payload_identities=planned[7]['files'],hardware_cosmetic_fixes=report)
    manifest['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    manifest['font_modes']={k:v for k,v in mode.items() if k not in ('metrics','labels','archive_packing')}
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (out/'READ-ME.txt').write_text(f'Rayblade {VERSION}: only loading position and movie-edge fixes from {PRIOR}.\n'
        +report['test']+'\nNative 1x only. No upgrade or public release. Hardware confirmation pending.\n',encoding='utf-8')
    print(f'PASS: {loading["animation_frame_cases"]} loading frames; {edge["geometry_cases"]} movie-edge cases; complete disc preservation.',flush=True)


if __name__=='__main__':main()
