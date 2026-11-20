"""0.7.40: loading position and movie-edge sampling on reported working 0.7.39."""
import argparse
import copy
import json
import struct
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save
from build_loading_position_fix import OFFSET, check_candidate as check_loading
from build_movie_edge_fix import START, END, geometry_code, check_candidate as check_movie

VERSION, PRIOR = '0.7.40', '0.7.39'
SOURCE_SHA = 'f71a9bd77b7fb2f6028a4e327ad7414f02ef0c796b21cfd1f4cdc7b91ee1ce9c'


def compose():
    old = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    assert digest(old) == SOURCE_SHA
    assert struct.unpack_from('<f', old, OFFSET)[0] == 8.
    assert old[START:END] == (ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()[START:END]
    exe = bytearray(old)
    struct.pack_into('<f', exe, OFFSET, 16.)
    exe[START:END] = geometry_code()
    changes = [i for i, (a, b) in enumerate(zip(old, exe)) if a != b]
    assert len(changes) == 259 and set(changes) <= set(range(START, END)) | {OFFSET+2}
    donor = (ROOT/'work/output/0.7.32/1ST_READ.BIN').read_bytes()
    assert exe[START:END] == donor[START:END] and exe[OFFSET:OFFSET+4] == donor[OFFSET:OFFSET+4]
    return bytes(exe), {
        'version': VERSION, 'date': '2026-11-11', 'source_build': PRIOR,
        'source_executable_sha256': SOURCE_SHA, 'executable_sha256': digest(exe),
        'kind': 'Loading position and movie-edge corrections on hardware-reported working 0.7.39',
        'changed_executable_bytes': len(changes), 'allowed_spans': [hex(OFFSET+2), [hex(START), hex(END)]],
        'loading': {'SDK_print_default_cell_pixels': {'before': 8, 'after': 16},
                    'physical_origin_before': [216,208], 'physical_origin_after': [432,416],
                    'change': 'Restore original proportional size/position at 640x480; keep cells, colors and animation.'},
        'movie_edge': {'patch_range': [hex(START),hex(END)],
                       'change': 'Inset sampling half a texel on each edge; screen rectangle, movie streams and audio unchanged.'},
        'evidence': 'docs/hardware-0739-follow-up.json',
        'retained': 'All assets exact 0.7.39, including cropped window atlas and Native Skies 1x font; RGB565, original graphics reservation and all other code bytes exact.',
        'excluded': 'No custom map hook, font kernel, runtime compression, grid/target/clipping or unrelated UI feature restored.',
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'public_release': False, 'upgrade_patch': False,
        'limits': ['Physical loading placement/movie-edge and regressions need confirmation.',
                   'User reports 0.7.39 working on hardware; no full-route coverage inferred.',
                   'This adds only the two requested cosmetics, not full emulator feature parity.'],
    }


def check(exe, report):
    old = (ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    loading = check_loading(exe, old, {**report, **report['loading']})
    loading['pre_640_reference'] = '0.7.2 loading routine, SDK print code and character/color data are byte-exact in 0.7.39.'
    loading['checks'][-1] = 'Only the default-size byte and separately checked movie-quad span change in this combined build.'
    movie = check_movie(exe, old, {**report, **report['movie_edge']})
    for proof in (loading, movie):
        proof['limits'] = ['Native routine fixtures do not validate physical GPU output or full-game compatibility.']
    assert loading['animation_frame_cases']==121 and loading['native_glyph_quads']==2420
    assert movie['geometry_cases']==20
    return loading, movie


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    loading, movie = check(exe, report)
    print('PASS: 121 loading-animation frames and 20 movie-edge cases.', flush=True)
    base = ROOT/'work/output'/PRIOR
    archive = (base/'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(base/'font-mode-details.json'))
    assert mode['native_only'] and mode['HD_bank_removed'] and not mode['title_selector']
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    p,_ = plan(compose_fn=lambda:(exe,archive,b'',{},mode), prior=PRIOR, version=VERSION)
    assert [n for n in p[3] if p[3][n]!=p[2][n]] == ['1ST_READ.BIN']
    p[7].update(kind=report['kind'], component_manifest_name='hardware-display-polish-component.json',
        proof_scope='Actual loading/SDK print geometry and old/new Sofdec sampling; all assets and other executable bytes unchanged.',
        readme_component_text='Only loading geometry and movie-edge sampling change from reported working 0.7.39.\n',
        current_native_evidence={'loading':'loading-position-native-test.json','movie_edge':'movie-edge-native-test.json'},
        current_live_evidence={}, inherited_proof_note='Earlier evidence retains its tested identities; no new live or physical run claimed.', pending=report['limits'])
    write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN':exe})
    out = ROOT/'work/output'/VERSION
    for name, data in [('hardware-display-polish-details.json',report),('loading-position-native-test.json',loading),
                       ('movie-edge-native-test.json',movie),('font-mode-details.json',mode)]:save(out/name,data)
    m = read(out/'font4x-patch.json')
    m.update(version=VERSION,previous_build=PRIOR,status='Loading/movie-edge diagnostic; hardware pending',current_payload_identities=p[7]['files'],hardware_display_polish=report)
    m['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    m['font_modes']={k:v for k,v in mode.items() if k not in ('metrics','labels','archive_packing')}
    save(out/'font4x-patch.json',m)
    save(ROOT/'docs/hardware-display-polish.json',dict(report,loading_validation=loading,movie_edge_validation=movie))
    return report


def audit():
    exe, report = compose()
    evidence=ROOT/'docs/hardware-0740-follow-up.json'
    if evidence.exists():
        report.update(hardware_result=read(evidence)['status'],hardware_evidence=evidence.relative_to(ROOT).as_posix())
    folder = ROOT/f'work/output/dcp-{VERSION}-diagnostic'
    target,old = read(folder/'target-tree.json'),read(ROOT/f'work/output/dcp-{PRIOR}-diagnostic/target-tree.json')
    assert len(target['files'])==141 and set(target['files'])==set(old['files'])
    assert [n for n in target['files'] if target['files'][n]!=old['files'][n]]==['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256']==digest(exe)
    bundle,proof=read(folder/'bundle-validation.json'),read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes())==bundle['sha256']
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256']==bundle['game_tree_sha256']
    assert proof['bootsector_invariant_sha256']==bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag']=='1' and not bundle['public_release']
    out=ROOT/'work/output'/VERSION
    loading,movie=read(out/'loading-position-native-test.json'),read(out/'movie-edge-native-test.json')
    assert loading['executable_sha256']==movie['executable_sha256']==digest(exe)
    assert loading['animation_frame_cases']==121 and movie['geometry_cases']==20
    report.update(all_140_game_files_and_boot_checked=True,all_assets_exact_0_7_39=True,
        loading_validation=loading,movie_edge_validation=movie,disc_validation=read(out/'english-disc-report.json')['validation'],
        DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    save(ROOT/'docs/hardware-display-polish.json',report)
    current=read(ROOT/'docs/hardware-chapter-transition.json')
    current['display_polish_candidate']={'version':VERSION,'documentation':'docs/hardware-display-polish.json',
        'DCP':report['DCP']['path'],'status':report['hardware_result'],'public_release':False,'upgrade_patch':False}
    if current.get('consolidated_candidate'):
        current['next_compatibility_candidate']=current['consolidated_candidate']
    else:
        current['next_compatibility_candidate']=current['display_polish_candidate']
    current['last_updated']=max(current.get('last_updated',''),'2026-11-11')
    save(ROOT/'docs/hardware-chapter-transition.json',current)
    if current.get('consolidated_candidate'):
        return report
    current=read(ROOT/'docs/hardware-entry-hang-results.json')
    current['interpretation'].update(new_build_created='0.7.40: only loading geometry and movie-edge sampling on reported working 0.7.39; original-input DCP verified',
        working_baseline_next_test='0.7.40: loading bottom-right size/position and green movie edge; regression check Office/mountain, chapter transitions and New Game/Hallway')
    save(ROOT/'docs/hardware-entry-hang-results.json',current)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true');parser.add_argument('--audit-package',action='store_true')
    a=parser.parse_args()
    if a.write:result=audit() if a.audit_package else build()
    else:
        exe,result=compose()
        if a.check:result['loading_validation'],result['movie_edge_validation']=check(exe,result)
    print(json.dumps(result,indent=2),flush=True)
