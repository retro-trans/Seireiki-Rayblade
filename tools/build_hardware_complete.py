"""0.7.50: combine final emulator fixes with the passing 0.7.48 hardware repair."""
import argparse
import copy
import json
import struct
from pathlib import Path
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save

VERSION, PRIOR = '0.7.50', '0.7.48'
BASE_SHA = '6de79055e4edabd428cf778385719086ee21db312c3bd9a48101897e326c0be6'
COMBINED_SHA = '1632f331219b96ffa982b4a647cd29987060847fc5042800debafaadf23b5b84'
BASE = 0x8c010000
STATUS_GATE = BASE + 0x6b7c8
MAP_HELPER = BASE + 0x6baa8
MAP_NAME = BASE + 0x6b828


def compose():
    from build_hardware_consolidated import compose as combined, status_gate
    from build_hardware_catchup import map_guard, filename_helper
    root = ROOT / 'work/output'
    old = (root / PRIOR / '1ST_READ.BIN').read_bytes()
    donor, archive, _, _ = combined()
    assert digest(old) == BASE_SHA and digest(donor) == COMBINED_SHA
    assert donor == (root / '0.7.41/1ST_READ.BIN').read_bytes()
    assert archive == (root / PRIOR / 'WIN00.AFS').read_bytes()
    exe = bytearray(donor)
    # Preserve the hardware-passing routine, including bytewise relative
    # offsets and immutable Native advances. Never re-import the 0.7.11 MOV.L.
    exe[0x66d38:0x66e4e] = old[0x66d38:0x66e4e]
    # These are explicit NOP tails in the already-reclaimed font region:
    # movie setters end at 6b7c8; filter returns before 6b828; target/line
    # adapters end at 6baa8 and the status wrapper begins at 6bad0.
    placements = [(0x6b7c8, 0x38, status_gate(entry=STATUS_GATE, capacity=0x38)),
                  (0x6baa8, 0x28, filename_helper(entry=MAP_HELPER, name_address=MAP_NAME, capacity=0x28)),
                  (0x6b828, 8, b'wmap_en\0')]
    for pos, capacity, raw in placements:
        assert len(raw) <= capacity and donor[pos:pos+capacity] == b'\x09\x00' * (capacity//2)
        exe[pos:pos+len(raw)] = raw
    # Reclaim the old gate for the alignment-safe map guard. Its second
    # texture filename is compared bytewise at every possible alignment.
    exe[0x8d00:0x8d60] = map_guard(helper=MAP_HELPER)
    struct.pack_into('<I', exe, 0x8b1d4, STATUS_GATE)
    struct.pack_into('<I', exe, 0x6b724, BASE+0x8d00)
    assert exe[0x8d60:0x9000] == donor[0x8d60:0x9000]
    allowed = set(range(0x66d38, 0x66e4e)) | set(range(0x8d00, 0x8d60))
    for pos, capacity, _ in placements: allowed.update(range(pos, pos+capacity))
    for pos in (0x8b1d4, 0x6b724): allowed.update(range(pos, pos+4))
    assert len(exe) == len(old) == len(donor)
    assert all(i in allowed for i, (a, b) in enumerate(zip(exe, donor)) if a != b)
    # Retain the proven renderer, except its explicitly adapted extra text
    # allocation. This is not a replacement with the later emulator kernel.
    from build_font4x_patch import START
    mode = read(root / PRIOR / 'font-mode-details.json')
    hook = mode['labels']['a_malloc'] - BASE
    assert all(hook <= i < hook+4 for i in range(START, START+mode['kernel_bytes']) if exe[i] != old[i])
    assert exe[0x66d38:0x66e4e] == old[0x66d38:0x66e4e]
    assert mode['native_only'] and mode['HD_bank_removed'] and not mode['title_selector']
    return bytes(exe), {
        'version': VERSION, 'date': '2026-11-19', 'source_build': PRIOR,
        'source_executable_sha256': BASE_SHA, 'executable_sha256': digest(exe),
        'kind': 'Combined final emulator fixes on the passing hardware runtime',
        'scope': 'Restore signed numeric fields, status-only vertical alignment, Stage 6 lossless text compression and bytewise map-label snapping. Retain the complete passing 0.7.48 name-offset routine, renderer, graphics repairs, battle fixes and every asset.',
        'restored': ['Signed SP/numeric plus and minus', 'Status marker/text vertical alignment',
                     'Lossless runtime text compression and allocation for Stage 6',
                     'Whole-pixel translated map labels while scrolling, with bytewise filename reads'],
        'retained': ['Bytewise name offsets and static Native advances from hardware-passing 0.7.48',
                     'Original Skies Native 1x; no HD font bank or selector',
                     'Graphics reservation, RGB565 and compact window/marker atlases',
                     'Loading placement, fullscreen movies and movie bottom-edge repair',
                     'Movement grid, animation targeting/lines, split clipping and selection bars',
                     'Final 0.7.23 translated assets, choice boundaries, names and Trust help'],
        'layout': {'status_gate': hex(STATUS_GATE), 'map_guard': hex(BASE+0x8d00),
                   'map_filename_helper': hex(MAP_HELPER), 'map_filename_literal': hex(MAP_NAME),
                   'allocated_NOP_tails': [[hex(p), n, len(raw)] for p, n, raw in placements]},
        'changed_executable_bytes': sum(a != b for a, b in zip(old, exe)),
        'hardware_result': 'pending', 'full_feature_catchup': True,
        'public_release': False, 'upgrade_patch': False,
        'limits': ['Combined build requires hardware confirmation; no full-route or live-GPU claim.',
                   'Separate issue #5 Stage 9 CG investigation remains unresolved; no new fix is claimed for it.',
                   'Existing incomplete-translation limitations remain outside this consolidation.'],
        'next_test': 'Cold-boot New Game and Clear 2 -> Next; continue past dialogue into the next scene. Check status Skills/Trust, signed SP, scrolling map labels, movement/targeting/split battles, Stage 6 dialogue, loading and movies. Keep 0.7.48 as the working fallback.'}


def check(exe, report):
    from test_font_patch import CPU
    from test_hardware_consolidated import check_candidate
    from test_hardware_catchup import alignment_check
    from test_choice_map_fix import map_draw
    from build_hardware_signed_fields import check as signed
    from build_map_font_patch import member
    from build_location_header_fix import check_candidate as widths
    base = ROOT / 'work/output' / PRIOR
    archive = (base / 'WIN00.AFS').read_bytes()
    mode = read(base / 'font-mode-details.json')
    def map_checks(image):
        return {'alignment': alignment_check(image), 'map_draw': map_draw(image)}
    # Every CPU subclass used by this suite inherits these checks. Existing
    # historical suites remain unchanged outside this scoped run.
    sentinel = object()
    prior = CPU.__dict__.get('strict_alignment', sentinel)
    CPU.strict_alignment = True
    try:
        proof = check_candidate(exe, archive, mode, report,
                                status_gate=STATUS_GATE, map_validator=map_checks)
        print('PASS: combined features under strict SH-4 alignment.', flush=True)
        proof['signed_fields'] = signed(exe, report, check_constructors=False)
        names = (base / 'text/D_NAMES.en.dec.bin').read_bytes()
        paper = (base / 'text/D_PAPER.en.dec.bin').read_bytes()
        proof['location_widths'] = widths(exe, (base/'1ST_READ.BIN').read_bytes(), names, paper,
            member(archive, 0), report, modes=(1,), strict_alignment=True)
        proof['location_widths']['checks'][-1] = 'Measurement routine is exact passing 0.7.48; current header placement, caps, body sizing and animation execute with the expected geometry.'
    finally:
        if prior is sentinel: del CPU.strict_alignment
        else: CPU.strict_alignment = prior
    proof['scope'] = 'Current combined executable with strict SH-4 read/write alignment: dialogue offset regression and real caller, location widths, signed numbers, status constructors/routing, bytewise map guard, exact Native pixels, grid/target/clip, Stage 6 allocation/encoding/upload/SDK, loading/movies and complete UI PRS. Historical RAM fixtures and bounded heap/cache/GPU endpoints; no fresh emulator/hardware pass claimed.'
    return proof


def build(proof_path=None):
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    proof = read(proof_path) if proof_path else check(exe, report)
    assert proof['version'] == VERSION and proof['executable_sha256'] == digest(exe)
    root = ROOT / 'work/output'
    archive = (root / PRIOR / 'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(root / PRIOR / 'font-mode-details.json'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    p, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in p[3] if p[3][n] != p[2][n]] == ['1ST_READ.BIN']
    p[7].update(kind=report['kind'], component_manifest_name='hardware-complete-component.json',
        proof_scope=proof['scope'], current_native_evidence={'combined': 'hardware-complete-native-test.json'},
        current_live_evidence={}, inherited_proof_note='Historical evidence retains its tested build identity.',
        readme_component_text=report['scope']+'\n', pending=report['limits'])
    write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = root / VERSION
    for name, obj in [('hardware-complete-details.json', report), ('hardware-complete-native-test.json', proof),
                      ('font-mode-details.json', mode), ('font-mode-component.json', mode)]: save(out / name, obj)
    m = read(out / 'font4x-patch.json')
    m.update(version=VERSION, previous_build=PRIOR, status='Combined candidate; hardware pending',
             current_payload_identities=p[7]['files'], hardware_consolidation=report)
    m['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    m['font_modes'] = {k: v for k, v in mode.items() if k not in ('labels', 'metrics', 'archive_packing')}
    save(out / 'font4x-patch.json', m)
    save(ROOT / 'docs/hardware-complete-fixes.json', dict(report, native_validation=proof))
    return report


def audit():
    exe, report = compose()
    root = ROOT / 'work/output'; folder = root / f'dcp-{VERSION}-diagnostic'
    target, base = [read(root / f'dcp-{v}-diagnostic/target-tree.json') for v in (VERSION, PRIOR)]
    final = read(root / 'dcp-0.7.23/target-tree.json')
    assert len(target['files']) == 141 and set(target['files']) == set(base['files']) == set(final['files'])
    assert [n for n in target['files'] if target['files'][n] != base['files'][n]] == ['1ST_READ.BIN']
    assert {n for n in target['files'] if target['files'][n] != final['files'][n]} == {'1ST_READ.BIN', 'WIN00.AFS'}
    assert target['files']['1ST_READ.BIN']['sha256'] == digest(exe)
    bundle, applied = read(folder/'bundle-validation.json'), read(folder/'original-apply-validation.json')
    assert digest((folder/bundle['asset']).read_bytes()) == bundle['sha256']
    assert applied['release_metadata_verified'] and applied['audio_tracks_preserved']
    assert applied['verified_game_tree_sha256'] == bundle['game_tree_sha256']
    assert applied['bootsector_invariant_sha256'] == bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    report.update(native_validation=read(root/VERSION/'hardware-complete-native-test.json'),
        all_140_game_files_and_boot_checked=True, disc_validation=read(root/VERSION/'english-disc-report.json')['validation'],
        DCP=dict(bundle, path=(folder/bundle['asset']).relative_to(ROOT).as_posix()))
    evidence = ROOT / 'docs/hardware-0750-follow-up.json'
    follow_up = read(evidence) if evidence.exists() else None
    if follow_up:
        report.update(hardware_result=follow_up['status'], hardware_evidence=evidence.relative_to(ROOT).as_posix())
        report['DCP']['hardware_result'] = follow_up['status']
    save(ROOT / 'docs/hardware-complete-fixes.json', report)
    path = ROOT / 'docs/hardware-chapter-transition.json'; d = read(path)
    d['complete_candidate'] = {'version': VERSION, 'documentation': 'docs/hardware-complete-fixes.json',
        'DCP': report['DCP']['path'], 'status': report['hardware_result'], 'public_release': False, 'upgrade_patch': False}
    d['next_compatibility_candidate'] = dict(d['complete_candidate'])
    if follow_up and follow_up['status'] == 'Reported passing on tested hardware paths':
        d['working_hardware_baseline'] = dict(d['complete_candidate'], hardware_evidence=evidence.relative_to(ROOT).as_posix())
        d['latest_hardware_follow_up'] = evidence.relative_to(ROOT).as_posix()
        d['next_step'] = follow_up['next_test']
    d['last_updated'] = follow_up['date'] if follow_up else '2026-11-19'; save(path, d)
    path = ROOT / 'docs/hardware-entry-hang-results.json'; d = read(path)
    d['interpretation'].update(new_build_created='0.7.50: all remaining emulator fixes with passing 0.7.48 name-offset repair; separate status/map hooks',
        working_baseline_next_test=report['next_test'])
    if follow_up: d['interpretation'].update(latest_report=VERSION+': '+follow_up['status'], working_baseline_next_test=follow_up['next_test'])
    d['last_updated'] = follow_up['date'] if follow_up else '2026-11-19'; save(path, d)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true'); p.add_argument('--check', action='store_true')
    p.add_argument('--proof-file', type=Path)
    p.add_argument('--audit-package', action='store_true'); a = p.parse_args()
    if a.write: r = audit() if a.audit_package else build(a.proof_file)
    else:
        exe, r = compose()
        if a.check: r['native_validation'] = check(exe, r)
    print(json.dumps(r, indent=2))
