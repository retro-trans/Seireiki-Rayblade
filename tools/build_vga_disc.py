"""Package the checked VGA merge over 0.1.44 as local 0.7.1. Dry first."""
import argparse
import json
import re
import shutil
from build_vga_patch import ROOT, OUT, VERSION, PRIOR, compose, digest, read
from build_movie_test_disc import write_plan
from package_archive_test_disc import substitute_payload_sector
from disc_inventory import Disc, SECTOR


def plan():
    exe, boot, component = compose()
    assert (OUT / '1ST_READ.BIN').read_bytes() == exe
    assert (OUT / 'IP.BIN').read_bytes() == boot
    proof = read(OUT / 'native-test.json')
    assert proof['executable_sha256'] == digest(exe) and proof['boot_sha256'] == digest(boot)
    assert proof['component_sha256'] == digest((OUT / 'component-report.json').read_bytes())
    assert proof['case_count'] == 96
    base = ROOT / 'work/output' / PRIOR
    previous = read(base / 'english-disc-report.json')
    assert previous['validation']['reextracted_files'] == 'all 14 exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    inherited = {}
    for name, row in previous['files'].items():
        raw = (base / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)).read_bytes()
        ent = entries[name]
        assert digest(raw) == row['sha256'] and len(raw) == row['size']
        assert disc.read(ent['lba'], ent['size']) == raw
        inherited[name] = raw
    targets = dict(inherited, **{'1ST_READ.BIN': exe})
    historical = list(previous['historical_native_evidence'])
    historical.append({'file': 'map-font-native-test.json', 'actual_tested_build': PRIOR,
                       'executable_sha256': digest(inherited['1ST_READ.BIN']),
                       'sha256': digest((base / 'map-font-native-test.json').read_bytes()),
                       'scope': 'Archive/font/geometry retained; prior executable identity is historical'})
    for row in historical:
        assert digest((base / row['file']).read_bytes()) == row['sha256']
    original = Disc(next(ROOT.glob('*.cue')))
    ent = entries['1ST_READ.BIN']
    chunks = [(ent['lba'], inherited['1ST_READ.BIN'], exe), (45000, disc.read(45000, len(boot)), boot)]
    changes = []
    sector_delta = 0
    for first_lba, source, target in chunks:
        assert len(source) == len(target)
        orig = original.read(first_lba, len(source))
        for off in range(0, len(source), 2048):
            a, b = source[off:off+2048], target[off:off+2048]
            if a == b:
                continue
            lba = first_lba + off // 2048
            track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
            position = (track['index'] + lba - track['start_lba']) * SECTOR
            with track['path'].open('rb') as fh:
                fh.seek(position)
                raw = fh.read(SECTOR)
            changes.append((track['path'].name, position, substitute_payload_sector(raw, a, b)))
            old = orig[off:off+2048]
            sector_delta += int(b != old) - int(a != old)
    report = {
        'version': VERSION, 'source_build': PRIOR, 'equivalent_public_base': '0.7.0',
        'kind': 'Local VGA compatibility test over the public 0.7.0 game payloads',
        'movie_extent': previous['movie_extent'], 'movie_extents': previous['movie_extents'],
        'movies': previous['movies'], 'original_audio_sector_count': previous.get('original_audio_sector_count', 4041),
        'files': {n: {'size': len(v), 'sha256': digest(v)} for n, v in targets.items()},
        'new_changed_sectors': len(changes),
        'total_changed_sector_locations_from_original': previous['total_changed_sector_locations_from_original'] + sector_delta,
        'historical_native_evidence': historical, 'vga_component': component, 'vga_native_proof': proof,
        'vga_proof_sha256': digest((OUT / 'native-test.json').read_bytes()),
        'component_manifest_name': 'vga-component.json',
        'readme_component_text': 'VGA video support merged from Rolly (SEGA-SKY) retail patch v1.0.\n'
            'Includes 0.7.0 / local 0.1.44 English text, original Skies font, word wrapping and high-detail map labels.\n'
            'Only 497 executable bytes and the boot VGA flag changed; no translation or font changes.\n'
            'Cold-boot this GDI with VGA selected. Do not load an emulator save state from an older build.\n'
            'For hardware testing use a VGA cable/box or VGA-based HDMI adapter; native output is 640x480 progressive.\n'
            'Keep the original Japanese region setting (or use your existing region-compatible loader).\n'
            'Credits/source: ' + component['source']['url'] + '\n',
        'readme_movie_text': previous['readme_movie_text'],
        'proof_scope': proof['scope'] + '; exact re-extraction and full-disc preservation checks. ' + proof['limits'],
        'pending': list(dict.fromkeys(component['pending'] + previous['pending'])), 'release': False,
    }
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5 and len(changes) == len({(n, o) for n, o, _ in changes})
    return disc, cue, inherited, targets, changes, names, historical, report


def finalize(planned):
    out = ROOT / 'work/output' / VERSION
    for name in ('component-report.json', 'native-test.json'):
        shutil.copyfile(OUT / name, out / ('vga-' + name))
    shutil.copyfile(OUT / 'IP.BIN', out / 'IP.BIN')
    disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    assert disc.read(45000, 32768) == (OUT / 'IP.BIN').read_bytes()
    manifest = read(out / 'font4x-patch.json')
    manifest.update(version=VERSION, previous_build=PRIOR,
                    status='VGA support merged; native video and disc checks pass; live VGA/hardware pending')
    manifest['current_payload_identities'] = planned[7]['files']
    manifest['files']['1ST_READ.BIN']['target_sha256'] = digest(planned[3]['1ST_READ.BIN'])
    manifest['vga'] = {'proof': 'vga-native-test.json', 'case_count': 96, 'live_validation': 'pending'}
    manifest['native_proof_reuse'] = {'source_build': PRIOR,
        'scope': 'Historical reports keep actual tested hashes. Only VGA code/flag changed; English font/text/archive bytes exact.'}
    (out / 'font4x-patch.json').write_text(json.dumps(manifest, indent=2) + '\n', 'utf-8')
    print('PASS: VGA boot flag re-extracted; all thirteen non-executable payloads retained exactly.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    p = plan()
    print('PASS:', len(p[4]), 'sector substitutions;', len(p[3]), 'game payloads;', len(p[6]), 'historical proofs.')
    if not args.write:
        print('DRY RUN: no disc written.')
        return
    write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN': p[3]['1ST_READ.BIN']})
    finalize(p)


if __name__ == '__main__':
    main()
