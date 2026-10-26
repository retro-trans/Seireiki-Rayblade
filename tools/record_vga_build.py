"""Record verified local VGA build and read-only emulator telemetry. Dry first."""
import argparse
import csv
import json
import shutil
from build_vga_patch import ROOT, OUT, VERSION, PRIOR, compose, digest, read


def prepare():
    exe, boot, component = compose()
    build = ROOT / 'work/output' / VERSION
    report = read(build / 'english-disc-report.json')
    proof = read(build / 'vga-native-test.json')
    assert digest((build / '1ST_READ.BIN').read_bytes()) == digest(exe) == proof['executable_sha256']
    assert digest((build / 'IP.BIN').read_bytes()) == digest(boot) == proof['boot_sha256']
    assert report['vga_proof_sha256'] == digest((build / 'vga-native-test.json').read_bytes())
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['new_changed_sectors'] == 5
    telemetry = []
    for name, cable in (('vga', 0), ('composite', 3)):
        path = ROOT / 'work/output/vga-runtime' / name / 'video-probe.csv'
        rows = list(csv.DictReader(path.read_text('utf-8').splitlines()))
        assert len(rows) == 20 and rows[-1]['frame'] == '1200'
        assert all(int(r['cable']) == cable for r in rows)
        loaded = [r for r in rows if r['vga_code_word'] == 'bda1e400']
        assert loaded and loaded[-1] == rows[-1]
        if cable == 0:
            assert all((r['width'], r['height'], r['spg_control'], r['spg_load']) ==
                       ('640', '480', '00000100', '020c0359') for r in loaded)
            assert all(int(r['fb_r_ctrl'], 16) & (1 << 23) for r in loaded)
        else:
            assert any(r['spg_control'] != '00000100' and not int(r['fb_r_ctrl'], 16) & (1 << 23)
                       for r in loaded)
        telemetry.append({'case': name, 'sha256': digest(path.read_bytes()),
                          'path': f'work/output/{VERSION}/vga-live-{name}.csv',
                          'samples': len(rows), 'last_vblank': 1200,
                          'loaded_patched_code_samples': len(loaded), 'last_sample': rows[-1]})
    summary = dict(component)
    summary.update(disc=f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        equivalent_public_base='0.7.0', status='VGA merge built; native, disc and cold-boot telemetry checks pass; visual/hardware testing pending',
        native_proof={'path': f'work/output/{VERSION}/vga-native-test.json',
                      'sha256': report['vga_proof_sha256'], 'cases': proof['case_count'],
                      'instructions': sum(r['instructions'] for r in proof['cases']), 'limits': proof['limits']},
        validation=report['validation'], sector_substitutions=5, unchanged_other_payloads=13,
        emulator={'executable_sha256': digest((ROOT / 'work/output/vga-runtime/vga/flycast.exe').read_bytes()),
                  'cold_boot': True, 'save_states': False, 'custom_textures': False,
                  'selected_region': 'Japan', 'selected_broadcast': 'NTSC',
                  'telemetry_api': 'Flycast Lua read32/state/display/VBlank; guest memory read only',
                  'telemetry': telemetry,
                  'limits': 'Hidden isolated emulator instances; no screenshot/visual inspection, button input or route progression. NTSC-configured boot only; not physical PAL-console proof.'})
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    summary = prepare()
    print('PASS: local', VERSION, 'VGA/composite cold boot; 96 native cases; five sector substitutions.')
    print('Would record docs/vga-support.json and copy the exact live telemetry into the test build.')
    if not args.write:
        print('DRY RUN: no files written.')
        return
    build = ROOT / 'work/output' / VERSION
    for name in ('vga', 'composite'):
        shutil.copyfile(ROOT / f'work/output/vga-runtime/{name}/video-probe.csv', build / f'vga-live-{name}.csv')
    for path in (ROOT / 'docs/vga-support.json', build / 'vga-validation-summary.json'):
        path.write_text(json.dumps(summary, indent=2) + '\n', 'utf-8')
    report = read(build / 'english-disc-report.json')
    report['vga_emulator_telemetry'] = summary['emulator']
    report['validation']['vga_cold_boot'] = 'pass: 640x480 progressive timing, VGA pixel clock, patched code loaded; read-only emulator telemetry'
    report['validation']['composite_cold_boot'] = 'pass: patched code loaded, original TV video path selected; read-only emulator telemetry'
    report['validation']['in_game'] = 'visual/gameplay confirmation pending; cold-boot telemetry only'
    (build / 'english-disc-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    shutil.copyfile(ROOT / 'THIRD_PARTY_NOTICES.txt', build / 'THIRD_PARTY_NOTICES.txt')
    with (build / 'READ-ME.txt').open('a', encoding='utf-8') as fh:
        fh.write('\nCold-boot telemetry: Flycast VGA at 640x480 progressive and composite TV fallback both pass.\n'
                 'No visual inspection or physical VGA hardware/PAL-console validation claimed.\n')


if __name__ == '__main__':
    main()
