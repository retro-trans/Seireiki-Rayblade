"""0.7.49: restore signed numeric fields only, on passing 0.7.48."""
import argparse
import copy
import json
from build_bitmap_font import ROOT, digest
from build_hardware_asset_split import read, save

VERSION, PRIOR = '0.7.49', '0.7.48'
BASE_SHA = '6de79055e4edabd428cf778385719086ee21db312c3bd9a48101897e326c0be6'
START, END = 0x2c1ae, 0x2c1ca


def compose():
    from build_numeric_room_fix import sign_patch
    root = ROOT / 'work/output'
    old = (root / PRIOR / '1ST_READ.BIN').read_bytes()
    before = (root / '0.7.9/1ST_READ.BIN').read_bytes()
    after = (root / '0.7.10/1ST_READ.BIN').read_bytes()
    assert digest(old) == BASE_SHA and len(old) == len(before) == len(after)
    assert old[START:END] == before[START:END]
    assert after[START:END] == sign_patch()
    delta = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    assert len(delta) == 21 and all(START <= i < END for i in delta)
    exe = old[:START] + sign_patch() + old[END:]
    assert {i for i, (a, b) in enumerate(zip(old, exe)) if a != b} == delta
    assert exe[0x66d38:0x66e4e] == old[0x66d38:0x66e4e]
    return exe, {
        'version': VERSION, 'date': '2026-11-19', 'source_build': PRIOR,
        'source_executable_sha256': BASE_SHA, 'executable_sha256': digest(exe),
        'kind': 'Signed numeric fields only on working 0.7.48',
        'scope': 'Exactly 21 historical 0.7.9-to-0.7.10 sign-writer bytes restored. All other executable bytes and every asset remain exact 0.7.48, including the bytewise name-offset alignment fix.',
        'patch_range': [hex(START), hex(END)], 'changed_executable_bytes': len(delta),
        'visible_change': 'Native Latin plus/minus for signed SP and other callers of the shared signed-number formatter; zero displayed as +0. Magnitudes, field padding and gameplay values unchanged.',
        'excluded': ['Status wrapper/gate and vertical alignment', 'Stage 6 runtime text compression', 'Custom map filename/snapping hook'],
        'hardware_result': 'pending', 'public_release': False, 'upgrade_patch': False,
        'limits': ['Hardware retest pending; no full-route claim.', 'Status adjustments and Stage 6 compression remain absent.'],
        'next_test': 'Cold-boot New Game and the previously failing mission dialogues. Inspect positive, negative and zero SP values in battle preview where available. Keep 0.7.48 as the working fallback.'}


def check(exe, report, *, check_constructors=True):
    from build_map_font_patch import member
    from build_font4x_patch import MEDIUM
    from test_library_headers import setup, call
    from test_ui_layouts import parse_ui
    from english_text_codec import decode
    from test_hardware_header_alignment import check as alignment_check
    from build_hardware_status_bypass import check as constructor_check
    base = ROOT / 'work/output' / PRIOR
    old = (base / '1ST_READ.BIN').read_bytes()
    names = (base / 'text/D_NAMES.en.dec.bin').read_bytes()
    font = member((base / 'WIN00.AFS').read_bytes(), 0)[99072:]
    old_cpu, cpu = setup(old, font, b'', names), setup(exe, font, b'', names)
    old_cpu.strict_alignment = cpu.strict_alignment = True
    cases = steps = 0
    samples = []
    for field_width in (0, 2, 3, 4):
        for value in range(-128, 128):
            streams = []
            for c in (old_cpu, cpu):
                saved = c.reg[8:]
                steps += call(c, 0x8c03af90)
                steps += call(c, 0x8c03c010, value, field_width)
                assert c.reg[8:] == saved
                at = c.read(0x8c1db4ec, 4) + 0x600
                raw = bytearray()
                for i in range(16):
                    raw.append(c.read(at+i, 1))
                    if raw[-1] == 255: break
                assert raw[-1] == 255
                streams.append(bytes(raw))
            prior, result = streams
            sign = b'\xf0' + bytes([6 if value < 0 else 5 if value > 0 else 7])
            assert prior.count(sign) == 1
            wanted = prior.replace(sign, bytes([MEDIUM.index('-' if value < 0 else '+')]))
            assert result == wanted, (value, field_width)
            if value != -128:
                expected = (('-' if value < 0 else '+') + str(abs(value)))
                expected = expected.rjust(max(len(expected), field_width))
                text = decode(result)[0]
                assert text == expected, (value, field_width, text, expected)
                glyphs, n = parse_ui(exe, font, names, result, x=0)
                steps += n
                assert ''.join(g[0] for g in glyphs) == expected
                if value in (-20, 0, 20) and field_width == 3:
                    samples.append({'input': value, 'output': text})
            cases += 1
    return {'version': report['version'], 'executable_sha256': digest(exe),
            'signed_formatter_cases': cases, 'native_rendered_cases': 1020,
            'samples': samples, 'SH4_signed_instructions': steps,
            'legacy_minus_128': 'Four boundary cases preserve original magnitude bytes; this patch changes only the sign encoding.',
            'alignment': alignment_check(exe),
            'constructors': dict(constructor_check(exe), version=report['version']) if check_constructors else 'Checked separately by the combined-build status tests',
            'scope': 'Strict-alignment signed-number execution against 0.7.48; exact original magnitude/padding bytes, Native sign rendering and retained alignment regression checks. Constructor checks are identified separately. No fresh emulator or hardware pass claimed.'}


def build():
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    exe, report = compose()
    proof = check(exe, report)
    print('PASS: signed numeric fields and preserved alignment/constructor behavior.', flush=True)
    root = ROOT / 'work/output'
    archive = (root / PRIOR / 'WIN00.AFS').read_bytes()
    mode = copy.deepcopy(read(root / PRIOR / 'font-mode-details.json'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe))
    p, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    assert [n for n in p[3] if p[3][n] != p[2][n]] == ['1ST_READ.BIN']
    p[7].update(kind=report['kind'], component_manifest_name='hardware-signed-fields-component.json',
        proof_scope=proof['scope'], current_native_evidence={'signed_fields': 'hardware-signed-fields-native-test.json'},
        current_live_evidence={}, inherited_proof_note='Historical checks retain their tested build identity.',
        readme_component_text=report['scope']+'\n', pending=report['limits'])
    write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = root / VERSION
    for name, obj in [('hardware-signed-fields-details.json', report), ('hardware-signed-fields-native-test.json', proof),
                      ('font-mode-details.json', mode), ('font-mode-component.json', mode)]: save(out / name, obj)
    m = read(out / 'font4x-patch.json')
    m.update(version=VERSION, previous_build=PRIOR, status='Signed-field diagnostic; hardware pending',
             current_payload_identities=p[7]['files'], hardware_signed_fields=report)
    m['files']['1ST_READ.BIN']['target_sha256'] = digest(exe)
    m['font_modes'] = {k: v for k, v in mode.items() if k not in ('labels', 'metrics', 'archive_packing')}
    m['hardware_consolidation']['current_build_exception'] = report['scope']
    save(out / 'font4x-patch.json', m)
    save(ROOT / 'docs/hardware-signed-fields.json', dict(report, native_validation=proof))
    return report


def audit():
    exe, report = compose()
    root = ROOT / 'work/output'
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
    report.update(native_validation=read(root / VERSION / 'hardware-signed-fields-native-test.json'),
        all_140_game_files_and_boot_checked=True, disc_validation=read(root / VERSION / 'english-disc-report.json')['validation'],
        DCP=dict(bundle, path=(folder / bundle['asset']).relative_to(ROOT).as_posix()))
    evidence = ROOT / 'docs/hardware-0749-follow-up.json'
    follow_up = read(evidence) if evidence.exists() else None
    if follow_up:
        report.update(hardware_result=follow_up['status'], hardware_evidence=evidence.relative_to(ROOT).as_posix())
        report['DCP']['hardware_result'] = follow_up['status']
    save(ROOT / 'docs/hardware-signed-fields.json', report)
    path = ROOT / 'docs/hardware-chapter-transition.json'
    d = read(path)
    d['signed_fields_candidate'] = {'version': VERSION, 'documentation': 'docs/hardware-signed-fields.json',
        'DCP': report['DCP']['path'], 'status': report['hardware_result'], 'public_release': False, 'upgrade_patch': False}
    d['next_compatibility_candidate'] = dict(d['signed_fields_candidate'])
    d['last_updated'] = follow_up['date'] if follow_up else '2026-11-19'
    save(path, d)
    path = ROOT / 'docs/hardware-entry-hang-results.json'
    d = read(path)
    d['interpretation'].update(new_build_created='0.7.49: only 21 signed-number formatting bytes restored on passing 0.7.48',
        working_baseline_next_test=report['next_test'])
    if follow_up: d['interpretation'].update(latest_report=VERSION+': '+follow_up['status'], working_baseline_next_test=follow_up['next_test'])
    d['last_updated'] = follow_up['date'] if follow_up else '2026-11-19'
    save(path, d)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true'); p.add_argument('--check', action='store_true')
    p.add_argument('--audit-package', action='store_true'); a = p.parse_args()
    if a.write: r = audit() if a.audit_package else build()
    else:
        exe, r = compose()
        if a.check: r['native_validation'] = check(exe, r)
    print(json.dumps(r, indent=2))
