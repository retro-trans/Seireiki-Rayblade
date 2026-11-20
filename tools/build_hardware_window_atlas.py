"""0.7.39: remove unused window-atlas rows; executable remains exact 0.7.38."""
import argparse
import copy
import json
import struct
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save
from build_map_font_patch import member

VERSION, PRIOR = '0.7.39', '0.7.38'
EXE_SHA = 'f71a9bd77b7fb2f6028a4e327ad7414f02ef0c796b21cfd1f4cdc7b91ee1ce9c'


def compose():
    from build_chapter_cards import repack
    base = ROOT/'work/output'/PRIOR
    exe, old = (base/'1ST_READ.BIN').read_bytes(), (base/'WIN00.AFS').read_bytes()
    assert digest(exe) == EXE_SHA
    source = (ROOT/'work/output/0.7.16/WIN00.AFS').read_bytes()
    donor = (ROOT/'work/output/0.7.17/WIN00.AFS').read_bytes()
    assert all(member(old, i) == member(source, i) for i in (1, 2))
    assert struct.unpack_from('<I', member(old, 2), 8)[0] == 0x1f40
    archive, packing = repack(old, {i: member(donor, i) for i in (1, 2)}, first=struct.unpack_from('<I', old, 8)[0])
    assert len(archive) == len(old)
    assert struct.unpack_from('<I', archive, 4)[0] == 90
    assert all(member(old, i) == member(archive, i) for i in range(90) if i not in (1, 2))
    return exe, archive, {
        'version': VERSION, 'date': '2026-11-10', 'source_build': PRIOR,
        'kind': 'Lossless window-atlas crop only; unchanged executable',
        'executable_sha256': EXE_SHA, 'changed_executable_bytes': 0,
        'source_archive_sha256': digest(old), 'archive_sha256': digest(archive),
        'changed_archive_members': [1, 2], 'unchanged_archive_members': 88,
        'window_texture': {'old_dimensions': [512, 512], 'new_dimensions': [512, 256],
                           'old_bytes': 524288, 'new_bytes': 262144, 'saved_bytes': 262144,
                           'method': 'Reuse exact historical 0.7.17 crop and matching normalized V coordinates after verifying both source members match 0.7.38.'},
        'packing': packing, 'evidence': 'docs/hardware-0738-follow-up.json',
        'retained': 'Executable exact 0.7.38, including RGB565, stock graphics reservation and no custom map hook. Every other asset and all 88 other WIN00 members, including Native font, unchanged.',
        'reason': 'Office still corrupt after framebuffer change. Historical working emulator Office capture retains battle assets and has only 134784 bytes total free with this smaller atlas already applied. This supports testing window-atlas overhead; it is not a current hardware allocation measurement.',
        'limits': ['No physical RAM/VRAM trace; Office fix remains unconfirmed.',
                   'No full emulator feature catch-up. Other historical UI/grid/movie-edge/loading limitations remain.',
                   'Retest Office, mountain, chapter transition, New Game/Hallway, Clear 2, menus and busy battles.'],
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'public_release': False, 'upgrade_patch': False,
    }


def check(exe, archive):
    import numpy as np
    from rayblade_codec import decompress
    from test_ui_images import scalar_plane, texture_info
    from test_map_font_patch import GeometryCPU
    from test_native_movie_font import bits
    from check_attack_variant_selection import run as geometry_run
    from check_native_text_components import verify
    from test_ordered_archive_layouts import directory_bytes, lookup
    from afs_layout import compact_positions, require_native_layouts
    old = (ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()
    raw = decompress(member(archive, 2)[16:])[0]
    original = scalar_plane(decompress(member(old, 2)[16:])[0], 512, 512)
    cropped = scalar_plane(raw, 512, 256)
    assert not original[224:].any() and np.array_equal(original[:256], cropped)
    assert member(old, 2)[:16] == member(archive, 2)[:16]
    require_native_layouts({'WIN00.AFS': archive})
    directory = directory_bytes('WIN00.AFS', archive)
    steps = texture_info(exe, 512, 256, 0xd00)
    for row in compact_positions(archive):
        off, count, n = lookup(exe, 'WIN00.AFS', directory, row['member'])
        steps += n
        assert (off, count) == (row['declared_offset'], row['sectors'])
    steps += verify(exe, member(archive, 2)[16:], raw, len(raw), instruction_limit=40000000)
    dat, before = member(archive, 1), member(old, 1)
    assert len(dat) == 48+125*20+12 and dat[:48] == before[:48] and dat[-12:] == before[-12:]
    for i in range(125):
        w,h,cx,cy,u0,v0,u1,v1,tex,flags = struct.unpack_from('<HHhh6H', dat, 48+i*20)
        prior = struct.unpack_from('<HHhh6H', before, 48+i*20)
        assert (w,h,cx,cy,u0,v0//2,u1,v1//2,tex,flags) == prior and not v0%2 and not v1%2
        ox,oy,ex,ey = prior[4]*2,prior[5]*2,prior[6]*2,prior[7]*2
        xs,ys = np.arange(min(ox,ex)-1,max(ox,ex)+2)%512, np.arange(min(oy,ey)-1,max(oy,ey)+2)
        assert np.array_equal(original[np.ix_(ys%512,xs)], cropped[np.ix_(ys%256,xs)])
        c = GeometryCPU(exe,b'',0,0)
        c.regions = [(0x8c010000,bytearray(exe)),(0x8c500000,bytearray(dat)),(0x8c510000,bytearray(32)),(0x8c700000,bytearray(0x2000))]
        c.reg[4:7]=[0x8c510000,i,0];c.reg[8]=0x8c701000;c.reg[15]=0x8c700fc0
        c.write(0x8c51001c,0x8c500030,4);c.write(0x8c51000c,bits(1.),4);c.write(0x8c510010,bits(1.),4)
        c.fr=[0]*16;c.fpul=0;c.visited=set()
        steps += geometry_run(c,0x8c0ac310,0x8c0ac39c,1000)
        f=lambda x:struct.unpack('<f',struct.pack('<I',x))[0]
        assert [f(x) for x in c.fr[:4]] == [-float(cx),-float(cy),float(w-cx),float(h-cy)]
        assert [f(c.read(0x8c700fe0+j*4,4)) for j in range(8)] == [v1/256,u1/256,v0/256,u1/256,v1/256,u0/256,v0/256,u0/256]
    return {'version': VERSION, 'executable_sha256': digest(exe), 'archive_sha256': digest(archive),
            'native_instructions': steps, 'native_archive_lookups': 90, 'native_sprite_geometry_cases': 125,
            'pixel_preservation': 'All 131072 upper-half texels exact; all discarded rows zero; all 125 sprite sampling neighborhoods exact, including wrapping/filtering.',
            'native_decode': 'Actual game PRS output exact', 'native_texture_dimensions': '512x256 accepted',
            'font_member_exact': member(old,52)==member(archive,52),
            'scope': 'Actual archive lookup, PRS decode, texture header and sprite geometry in bounded SH-4 fixtures; no live GPU/hardware result.'}


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, archive, report = compose()
    proof = check(exe, archive)
    print('PASS: lossless crop, 90 native archive lookups, PRS and 125 sprite geometry cases.', flush=True)
    base = ROOT/'work/output'/PRIOR
    mode = copy.deepcopy(read(base/'font-mode-details.json'))
    assert mode['native_only'] and mode['HD_bank_removed'] and not mode['title_selector']
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe), archive_sha256=digest(archive))
    p, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in p[3] if p[3][n] != p[2][n]] == ['WIN00.AFS']
    p[7].update(kind=report['kind'], component_manifest_name='hardware-window-atlas-component.json',
        proof_scope=proof['scope'], readme_component_text=report['retained']+'\n',
        current_native_evidence={'window_atlas':'hardware-window-atlas-native-test.json'}, current_live_evidence={},
        inherited_proof_note='Historical evidence retains its tested identities; no new live or physical run claimed.', pending=report['limits'])
    write_plan(p, VERSION, PRIOR, {'WIN00.AFS': archive})
    out = ROOT/'work/output'/VERSION
    save(out/'hardware-window-atlas-details.json', report)
    save(out/'hardware-window-atlas-native-test.json', proof)
    save(out/'font-mode-details.json', mode)
    m = read(out/'font4x-patch.json')
    m.update(version=VERSION, previous_build=PRIOR, status='Window-atlas-only diagnostic; hardware pending', current_payload_identities=p[7]['files'], hardware_window_atlas=report)
    m['files']['WIN00.AFS']['target_sha256'] = digest(archive)
    m['font_modes'] = {k:v for k,v in mode.items() if k not in ('metrics','labels','archive_packing')}
    off,size=struct.unpack_from('<II',archive,8+52*8)
    m['library'].update(archive_member_offset=off,archive_member_bytes=size)
    save(out/'font4x-patch.json',m)
    lib=read(out/'library-patch-report.json');lib.update(archive_member_offset=off,archive_member_bytes=size)
    save(out/'library-patch-report.json',lib)
    save(ROOT/'docs/hardware-window-atlas-diagnostic.json',dict(report,native_validation=proof))
    return report


def audit():
    exe, archive, report = compose()
    folder = ROOT/f'work/output/dcp-{VERSION}-diagnostic'
    target, old = read(folder/'target-tree.json'), read(ROOT/f'work/output/dcp-{PRIOR}-diagnostic/target-tree.json')
    assert len(target['files'])==141 and set(target['files'])==set(old['files'])
    assert [n for n in target['files'] if target['files'][n]!=old['files'][n]]==['WIN00.AFS']
    assert target['files']['WIN00.AFS']['sha256']==digest(archive)
    assert target['files']['1ST_READ.BIN']['sha256']==EXE_SHA
    bundle, proof = read(folder/'bundle-validation.json'),read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes())==bundle['sha256']
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256']==bundle['game_tree_sha256']
    assert proof['bootsector_invariant_sha256']==bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag']=='1' and not bundle['public_release']
    native=read(ROOT/f'work/output/{VERSION}/hardware-window-atlas-native-test.json')
    assert native['executable_sha256']==EXE_SHA and native['archive_sha256']==digest(archive)
    report.update(all_140_game_files_and_boot_checked=True,only_WIN00_changed_from_0_7_38=True,package_verified_date='2026-11-11',
        native_validation=native,disc_validation=read(ROOT/f'work/output/{VERSION}/english-disc-report.json')['validation'],
        DCP=dict(bundle,path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    manual=read(ROOT/'docs/hardware-entry-hang-results.json').get('results',{}).get(VERSION)
    if manual:
        report.update(hardware_result=manual['status'],hardware_report=manual,hardware_follow_up=manual.get('evidence'))
    save(ROOT/'docs/hardware-window-atlas-diagnostic.json',report)
    current=read(ROOT/'docs/hardware-chapter-transition.json')
    current['window_atlas_candidate']={'version':VERSION,'documentation':'docs/hardware-window-atlas-diagnostic.json',
        'DCP':report['DCP']['path'],'status':'Original-input DCP verified locally; Office and regression hardware tests pending','public_release':False,'upgrade_patch':False}
    current['next_compatibility_candidate']=current['window_atlas_candidate']
    if manual:
        current['window_atlas_candidate'].update(status=manual['status'],hardware_report=manual)
    if 'display_polish_candidate' in current:
        current['next_compatibility_candidate']=current['display_polish_candidate']
    current['last_updated']='2026-11-11'
    save(ROOT/'docs/hardware-chapter-transition.json',current)
    current=read(ROOT/'docs/hardware-entry-hang-results.json')
    if not (ROOT/'docs/hardware-display-polish.json').exists():
        current['interpretation'].update(new_build_created='0.7.39: lossless window-atlas crop only; executable exact 0.7.38; original-input DCP verified',
            working_baseline_next_test='0.7.39: same Office cutaway, mountain scene, Chapter 4 transition; New Game/Hallway, Clear 2, menus and busy battles')
    current['last_updated']='2026-11-11'
    save(ROOT/'docs/hardware-entry-hang-results.json',current)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true');parser.add_argument('--audit-package',action='store_true')
    a=parser.parse_args()
    if a.write:result=audit() if a.audit_package else build()
    else:
        exe,archive,result=compose()
        if a.check:result['native_validation']=check(exe,archive)
    print(json.dumps(result,indent=2),flush=True)
