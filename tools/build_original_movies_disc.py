"""Restore both modified opening/demo movies to retail bytes; dry first."""
import argparse
import json
import re
import shutil
from build_vga_patch import ROOT, digest, read
from disc_inventory import Disc, SECTOR
from package_archive_test_disc import substitute_payload_sector
from build_movie_test_disc import write_plan

VERSION, PRIOR = '0.7.2', '0.7.1'
MOVIES = ('MOV055.SFD', 'MOV072.SFD')


def plan():
    base = ROOT / 'work/output' / PRIOR
    previous = read(base / 'english-disc-report.json')
    assert previous['validation']['reextracted_files'] == 'all 14 exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc, original = Disc(cue), Disc(next(ROOT.glob('*.cue')))
    entries = {r['path']: r for r in disc.inventory()}
    original_entries = {r['path']: r for r in original.inventory()}
    assert all(original_entries[n] == entries[n] for n in MOVIES)
    inherited = {}
    for name, row in previous['files'].items():
        raw = (base / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)).read_bytes()
        ent = entries[name]
        assert digest(raw) == row['sha256'] and len(raw) == row['size']
        assert disc.read(ent['lba'], ent['size']) == raw
        inherited[name] = raw
    assert {n for n in inherited if n.endswith('.SFD')} == set(MOVIES)
    targets, changes, movies = dict(inherited), [], []
    for name in MOVIES:
        ent = entries[name]
        source = inherited[name]
        target = original.read(ent['lba'], ent['size'])
        assert len(source) == len(target) == ent['size']
        targets[name] = target
        count = 0
        for off in range(0, len(target), 2048):
            a, b = source[off:off+2048], target[off:off+2048]
            if a == b:
                continue
            lba = ent['lba'] + off // 2048
            track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
            position = (track['index'] + lba - track['start_lba']) * SECTOR
            with track['path'].open('rb') as fh:
                fh.seek(position)
                raw = fh.read(SECTOR)
            changes.append((track['path'].name, position, substitute_payload_sector(raw, a, b)))
            count += 1
        movies.append({'movie': name, 'extent': ent, 'target_sha256': digest(target),
                       'previous_sha256': digest(source), 'restored_sectors': count,
                       'treatment': 'Original Japanese retail movie, byte-exact; no English overlays',
                       'audio_video_timing_container': 'Original bytes restored together; no re-encoding'})
    assert disc.read(45000, 32768) == (base / 'IP.BIN').read_bytes()
    assert disc.read(45000, 32768)[0x3d] == ord('1')
    historical = list(previous['historical_native_evidence'])
    historical.append({'file': 'vga-native-test.json', 'actual_tested_build': PRIOR,
                       'executable_sha256': digest(inherited['1ST_READ.BIN']),
                       'sha256': digest((base / 'vga-native-test.json').read_bytes()),
                       'scope': 'Exact executable/boot and all font/text/archive payloads retained in 0.7.2'})
    for row in historical:
        assert digest((base / row['file']).read_bytes()) == row['sha256']
    report = {
        'version': VERSION, 'source_build': PRIOR,
        'kind': 'VGA English build with original opening/demo movies restored; release candidate',
        'movie_extent': previous['movie_extent'], 'movie_extents': previous['movie_extents'],
        'movies': movies, 'original_audio_sector_count': previous.get('original_audio_sector_count', 4041),
        'files': {n: {'size': len(v), 'sha256': digest(v)} for n, v in targets.items()},
        'new_changed_sectors': len(changes),
        'total_changed_sector_locations_from_original': previous['total_changed_sector_locations_from_original'] - len(changes),
        'historical_native_evidence': historical,
        'vga_component': previous['vga_component'], 'vga_native_proof': previous['vga_native_proof'],
        'vga_proof_sha256': previous['vga_proof_sha256'],
        'vga_emulator_telemetry': previous['vga_emulator_telemetry'],
        'component_manifest_name': 'original-movies-component.json',
        'readme_component_text': 'Includes the 0.7.1 integrated VGA code/boot flag, Skies Latin font, English text and UI/map fixes unchanged.\n'
            'Cold-boot this GDI. Existing emulator save states can retain old code or assets.\n',
        'readme_movie_text': 'MOV055 opening and MOV072 demo restored byte-for-byte from the original Japanese retail disc.\n'
            'All added English movie subtitles, captions, title/UI edits and ending-title edits are removed.\n'
            'Original movie video, audio, container, timing and file extents are preserved without re-encoding.\n',
        'proof_scope': 'Both original movie payload hashes and all fourteen file re-extractions; unchanged VGA/English executable and twelve non-movie payloads; complete track preservation. Prior native/boot telemetry retains actual tested identities.',
        'pending': ['Physical Dreamcast VGA/NTSC/PAL and non-VGA testing',
                    'Live full playback/skipping/return of restored opening/demo movies',
                    'Independent meaning review, held story rows and complete route/long-session testing',
                    'Live newest map/menu/VRAM/fade and overlap checks'],
        'release': False,
    }
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5 and len(changes) == len({(n, o) for n, o, _ in changes})
    return disc, cue, inherited, targets, changes, names, historical, report


def finalize(p):
    out = ROOT / 'work/output' / VERSION
    finished = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    assert finished.read(45000, 32768) == (out / 'IP.BIN').read_bytes()
    for row in p[7]['movies']:
        ent = row['extent']
        assert digest(finished.read(ent['lba'], ent['size'])) == row['target_sha256']
    manifest = read(out / 'font4x-patch.json')
    manifest.update(version=VERSION, previous_build=PRIOR,
                    status='Original Japanese opening/demo movies restored; VGA/English font/text retained')
    manifest['current_payload_identities'] = p[7]['files']
    manifest['movie_presentation'] = p[7]['movies']
    manifest['native_proof_reuse'] = {'source_build': PRIOR, 'scope': 'Only original movie bytes restored; executable/boot/font/text/archive exact.'}
    (out / 'font4x-patch.json').write_text(json.dumps(manifest, indent=2) + '\n', 'utf-8')
    record = {k: p[7][k] for k in ('version', 'source_build', 'movies', 'files', 'proof_scope', 'pending')}
    record['validation'] = read(out / 'english-disc-report.json')['validation']
    record['unchanged_non_movie_payloads'] = 12
    record['restored_movie_sectors'] = len(p[4])
    (out / 'original-movies-validation.json').write_text(json.dumps(record, indent=2) + '\n', 'utf-8')
    print('PASS: both retail movie hashes exact; VGA boot and twelve non-movie payloads unchanged.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    p = plan()
    print('Plan:', VERSION, 'restore', len(p[4]), 'movie sectors; retain twelve non-movie payloads and VGA boot flag.')
    for m in p[7]['movies']:
        print(m['movie'], m['target_sha256'], m['restored_sectors'], 'sectors')
    if not args.write:
        print('DRY RUN: no disc written.')
        return
    write_plan(p, VERSION, PRIOR)
    finalize(p)


if __name__ == '__main__':
    main()
