"""0.7.47: measure location banners without reading a loaded font resource."""
import argparse
import copy
import json
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save
from build_location_header_fix import START, END, BASE, measure_code, MEDIUM
from build_map_font_patch import member

VERSION, PRIOR = '0.7.47', '0.7.45'
BASE_SHA = 'd13d6cf267e5ce6ec07a70439205901596174912042e41feed39fbc885bf107f'
FAILED_SHA = '5bb81a7b491295d510780ed1dd152985e1d28456032d110c2df3c0812b005e38'


def compose():
    root = ROOT / 'work/output'
    old = (root / PRIOR / '1ST_READ.BIN').read_bytes()
    failed = (root / '0.7.46/1ST_READ.BIN').read_bytes()
    assert digest(old) == BASE_SHA and digest(failed) == FAILED_SHA
    assert failed[START:END] == measure_code()  # Historical emitter is unchanged.
    assert old[:START] == failed[:START] and old[END:] == failed[END:]
    banks = member((root / PRIOR / 'WIN00.AFS').read_bytes(), 0)
    assert len(banks) == 198144 and not any(banks[0x200:99072])
    widths = banks[99072+0xa0:99072+0xa0+len(MEDIUM)]
    exe = old[:START] + measure_code(static_widths=widths) + old[END:]
    return exe, {
        'version': VERSION, 'date': '2026-11-17', 'source_build': PRIOR,
        'failed_comparison': '0.7.46', 'source_executable_sha256': BASE_SHA,
        'executable_sha256': digest(exe), 'kind': 'Self-contained Native location measurement',
        'patch_range': [hex(START), hex(END)],
        'changed_bytes_from_working': sum(a != b for a, b in zip(old, exe)),
        'changed_bytes_from_failed': sum(a != b for a, b in zip(failed, exe)),
        'width_table_source': 'Exact 101 Native advances from 0.7.45 WIN00.AFS member 0, bank offset 99072 + 0xa0',
        'width_table_sha256': digest(widths),
        'scope': 'Only the location measurement routine differs from 0.7.45. Same widths as 0.7.46, now embedded in executable as nibbles; no loaded-font pointer read. All assets and other code remain exact 0.7.45.',
        'hypothesis': 'The loaded-font pointer may be unavailable or stale at a measurement call during a scene transition. No runtime pointer value has been captured on hardware.',
        'on_pass': 'Supports removing the loaded-font dependency on tested paths; does not prove the historical fault address or full-route stability.',
        'on_fail': 'Keep 0.7.45; inspect shared measurement call contexts and differences from the original routine. Do not restore unrelated code.',
        'excluded': ['Status hooks', 'Signed SP formatting', 'Stage 6 runtime text compression', 'Custom map filename/snapping hook'],
        'hardware_result': 'pending', 'hardware_root_cause_confirmed': False,
        'limits': ['Hardware confirmation pending; no live GPU/timing claim.', 'Not full feature parity; excluded code remains absent.'],
        'public_release': False, 'upgrade_patch': False,
    }


def check(exe, report):
    from build_hardware_header_split import check as common_check
    from test_library_headers import setup, call, HeaderCPU, GLOBALS
    from test_ui_layouts import entry
    base = ROOT / 'work/output' / PRIOR
    proof = common_check(exe, report)
    names = (base / 'text/D_NAMES.en.dec.bin').read_bytes()
    paper = (base / 'text/D_PAPER.en.dec.bin').read_bytes()
    font = member((base / 'WIN00.AFS').read_bytes(), 0)[99072:]
    rows = [r for r in read(ROOT / 'work/translation/en/ui/names.json')
            if r['id'].startswith('names.g06.') and r['source_record_kind'] != 'unused_table_root_sentinel']

    class NoFontCPU(HeaderCPU):
        def read(self, address, count):
            assert not (address < 0x8c1f36a8 and address + count > 0x8c1f36a4), 'Font pointer read'
            assert not (address < 0x8c600000 + len(font) and address + count > 0x8c600000), 'Font resource read'
            return super().read(address, count)

    checks = 0
    for pointer in (0, 0xdead0000, 0x8c600000):
        c = setup(exe, font, paper, names)
        c.write(0x8c1f36a4, pointer, 4)
        c.__class__ = NoFontCPU
        for row in rows:
            before = c.reg[8:]
            call(c, BASE + START, 0x600 + int(row['id'].split('.')[-1]))
            assert c.reg[0] == sum(font[0xa0+b] for b in entry(names, row['id'])[:-1])
            assert c.reg[8:] == before
            checks += 1
        # Exercise every packed nibble, not only characters in current names.
        address = 0x8c920000
        c.regions.append((address, bytearray(b'\x04\x00\x00\x00\x00\xff')))
        c.write(GLOBALS[6], address, 4)
        for glyph in range(0xf0):
            c.write(address+4, glyph, 1)
            call(c, BASE + START, 0x600)
            assert c.reg[0] == font[0xa0 + (glyph if glyph < len(MEDIUM) else MEDIUM.index('?'))]
            checks += 1
    # Demonstrate the dependency in the failed code under the same bounded setup.
    c = setup((ROOT / 'work/output/0.7.46/1ST_READ.BIN').read_bytes(), font, paper, names)
    c.__class__ = NoFontCPU
    detected = False
    try:
        call(c, BASE + START, 0x601)
    except RuntimeError as error:
        detected = isinstance(error.__cause__, AssertionError) and str(error.__cause__) == 'Font pointer read'
    assert detected, 'Failed routine must expose the dependency in this fixture'
    proof['font_independent_cases'] = checks
    proof['failed_build_font_dependency_detected'] = detected
    proof['scope'] += ' Additional poisoned-pointer checks forbid both font-global and font-resource reads, cover all location names and all Latin/fallback byte values. These are bounded instruction tests, not a captured hardware fault.'
    return proof


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    proof = check(exe, report)
    print('PASS: Native widths/geometry, all packed advances, poisoned pointers and constructors.', flush=True)
    root = ROOT / 'work/output'
    archive = (root / PRIOR / 'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(root / PRIOR / 'font-mode-details.json'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    p, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in p[3] if p[3][n] != p[2][n]] == ['1ST_READ.BIN']
    p[7].update(kind=report['kind'], component_manifest_name='hardware-static-header-component.json',
                proof_scope=proof['scope'], current_native_evidence={'static_header': 'hardware-static-header-native-test.json'},
                current_live_evidence={}, inherited_proof_note='Historical evidence retains its tested identity; current routine tests do not establish hardware compatibility.',
                readme_component_text=report['scope']+'\n', pending=report['limits'])
    write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = root / VERSION
    for name, obj in [('hardware-static-header-details.json', report), ('hardware-static-header-native-test.json', proof),
                      ('font-mode-details.json', mode), ('font-mode-component.json', mode)]:
        save(out / name, obj)
    m = read(out / 'font4x-patch.json')
    m.update(version=VERSION, previous_build=PRIOR, status='Self-contained location width diagnostic; hardware pending',
             current_payload_identities=p[7]['files'], hardware_static_header=report)
    m['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    m['font_modes'] = {k: v for k, v in mode.items() if k not in ('labels', 'metrics', 'archive_packing')}
    m['hardware_consolidation']['current_build_exception'] = report['scope']
    save(out / 'font4x-patch.json', m)
    save(ROOT / 'docs/hardware-static-header.json', dict(report, native_validation=proof))
    return report


def audit():
    exe, report = compose()
    root = ROOT / 'work/output'
    evidence = ROOT / 'docs/hardware-0747-follow-up.json'
    follow_up = read(evidence) if evidence.exists() else None
    if follow_up:
        report.update(hardware_result=follow_up['status'], hardware_evidence=evidence.relative_to(ROOT).as_posix())
        report['limits'][0] = 'Reported failed on hardware; retain the result when regenerating package audits.'
    folder = root / f'dcp-{VERSION}-diagnostic'
    target, base = [read(root / f'dcp-{v}-diagnostic/target-tree.json') for v in (VERSION, PRIOR)]
    assert len(target['files']) == 141 and set(target['files']) == set(base['files'])
    assert [n for n in target['files'] if target['files'][n] != base['files'][n]] == ['1ST_READ.BIN']
    assert target['files']['1ST_READ.BIN']['sha256'] == digest(exe)
    bundle, applied = read(folder / 'bundle-validation.json'), read(folder / 'original-apply-validation.json')
    assert digest((folder / bundle['asset']).read_bytes()) == bundle['sha256']
    assert applied['release_metadata_verified'] and applied['audio_tracks_preserved']
    assert applied['verified_game_tree_sha256'] == bundle['game_tree_sha256']
    assert applied['bootsector_invariant_sha256'] == bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    report.update(native_validation=read(root / VERSION / 'hardware-static-header-native-test.json'),
                  all_140_game_files_and_boot_checked=True,
                  disc_validation=read(root / VERSION / 'english-disc-report.json')['validation'],
                  DCP=dict(bundle, path=(folder / bundle['asset']).relative_to(ROOT).as_posix()))
    if follow_up: report['DCP']['hardware_result'] = follow_up['status']
    save(ROOT / 'docs/hardware-static-header.json', report)
    path = ROOT / 'docs/hardware-chapter-transition.json'
    d = read(path)
    d['next_compatibility_candidate'] = {'version': VERSION, 'documentation': 'docs/hardware-static-header.json',
        'DCP': report['DCP']['path'], 'status': 'Original-input DCP verified; hardware pending', 'public_release': False, 'upgrade_patch': False}
    d['last_updated'] = '2026-11-17'
    if follow_up:
        d['next_compatibility_candidate'].update(status=follow_up['status'], hardware_evidence=evidence.relative_to(ROOT).as_posix())
        d['last_updated'] = follow_up['date']
    save(path, d)
    path = ROOT / 'docs/hardware-entry-hang-results.json'
    d = read(path)
    d['interpretation'].update(new_build_created='0.7.47: location measurement uses immutable Native advances; all other code/assets exact passing 0.7.45',
        working_baseline_next_test='Cold-boot 0.7.47 from original input; repeat New Game and failing mission dialogues. Compare 0.7.45 if failure persists. Inspect location banner widths. No font-lifetime fault has been captured on hardware.')
    d['last_updated'] = '2026-11-17'
    if follow_up:
        d['interpretation'].update(latest_report=VERSION+': '+follow_up['status'], static_header_result=follow_up['interpretation'], working_baseline_next_test=follow_up['next_test'])
        d['last_updated'] = follow_up['date']
    save(path, d)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true')
    p.add_argument('--check', action='store_true')
    p.add_argument('--audit-package', action='store_true')
    a = p.parse_args()
    if a.write:
        r = audit() if a.audit_package else build()
    else:
        exe, r = compose()
        if a.check:
            r['native_validation'] = check(exe, r)
    print(json.dumps(r, indent=2))
