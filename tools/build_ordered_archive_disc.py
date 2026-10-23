"""Package 0.1.38 six-archive native loading fix. Dry run before --write."""
import argparse
import json
import re

from afs_layout import require_native_layouts
from build_bitmap_font import ROOT, digest
from build_movie_test_disc import write_plan
from build_ordered_archive_patch import OUT, PRIOR, VERSION, compose
from disc_inventory import Disc, SECTOR
from package_archive_test_disc import substitute_payload_sector


def plan():
    base = ROOT / 'work/output' / PRIOR
    previous = json.loads((base / 'english-disc-report.json').read_text('utf-8'))
    assert previous['version'] == PRIOR and previous['validation']['reextracted_files'] == 'all 14 exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    inherited = {}
    for name, record in previous['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'], row['size'])
        path = base / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
        assert raw == path.read_bytes() and len(raw) == record['size'] and digest(raw) == record['sha256']
        inherited[name] = raw
    replacements, component = compose()
    assert component == json.loads((OUT / 'component-report.json').read_text('utf-8'))
    proof_raw = (OUT / 'native-test.json').read_bytes()
    proof = json.loads(proof_raw)
    assert proof['native_lookup_cases'] == 2063 and proof['native_guard_and_ABI'] == 'pass'
    assert proof['captured_failure_reproduction']['wrong_payload_matches_captured_RAM_after_pointer_unrelocation']
    assert proof['executable_sha256'] == digest(inherited['1ST_READ.BIN'])
    for name, raw in replacements.items():
        assert (OUT / name).read_bytes() == raw
        assert proof['archives'][name] == component['archives'][name]['target_archive_sha256'] == digest(raw)
        assert component['archives'][name]['source_archive_sha256'] == digest(inherited[name])
    historical = list(previous['historical_native_evidence'])
    last = (base / 'album-caption-readings-native-test.json').read_bytes()
    last_proof = json.loads(last)
    assert digest(last) == previous['album_caption_readings_proof_sha256']
    assert last_proof['archive_sha256'] == digest(inherited['ALBUM.AFS'])
    assert not any(r['file'] == 'album-caption-readings-native-test.json' for r in historical)
    historical.append({'file': 'album-caption-readings-native-test.json', 'sha256': digest(last),
                       'actual_tested_build': last_proof['source_build'],
                       'executable_sha256': last_proof['executable_sha256'],
                       'scope': 'Historical payload/native report; original tested archive identity and limits retained'})
    assert len(historical) == 26
    for row in historical:
        raw = (base / row['file']).read_bytes()
        assert digest(raw) == row['sha256'] and json.loads(raw)['executable_sha256'] == row['executable_sha256']
    targets = dict(inherited, **replacements)
    layout = require_native_layouts(targets)
    original_disc = Disc(next(ROOT.glob('*.cue')))
    originals = {r['path']: r for r in original_disc.inventory()}
    changes, handles, by_archive = [], {}, {}
    old_total = new_total = 0
    try:
        for name, target in replacements.items():
            row = entries[name]
            assert row == originals[name]
            source = inherited[name]
            original = original_disc.read(row['lba'], row['size'])
            assert len(source) == len(target) == len(original)
            old_locations = sum(source[p:p+2048] != original[p:p+2048] for p in range(0, len(source), 2048))
            new_locations = sum(target[p:p+2048] != original[p:p+2048] for p in range(0, len(target), 2048))
            old_total += old_locations
            new_total += new_locations
            changed = [n for n in range((len(target)+2047)//2048)
                       if source[n*2048:(n+1)*2048] != target[n*2048:(n+1)*2048]]
            for n in changed:
                lba = row['lba'] + n
                track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
                track_name = track['path'].name
                if track_name not in handles:
                    handles[track_name] = track['path'].open('rb')
                offset = (track['index'] + lba - track['start_lba']) * SECTOR
                handles[track_name].seek(offset)
                raw = handles[track_name].read(SECTOR)
                patched = substitute_payload_sector(raw, source[n*2048:(n+1)*2048], target[n*2048:(n+1)*2048])
                changes.append((track_name, offset, patched))
            by_archive[name] = {'sector_substitutions': len(changed), 'source_locations_from_original': old_locations,
                                'target_locations_from_original': new_locations}
            print('Planned', name, len(changed), 'sector substitutions', flush=True)
    finally:
        for handle in handles.values():
            handle.close()
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5 and len(targets) == 14
    report = {'version': VERSION, 'source_build': PRIOR,
              'kind': 'Fix cumulative-sector archive loading corruption after New Game; six archive layouts repaired',
              'movie_extent': previous['movie_extent'], 'movie_extents': previous['movie_extents'],
              'movies': previous['movies'], 'original_audio_sector_count': 4041,
              'new_changed_sectors': len(changes),
              'total_changed_sector_locations_from_original': previous['total_changed_sector_locations_from_original'] - old_total + new_total,
              'files': {name: {'size': len(raw), 'sha256': digest(raw)} for name, raw in targets.items()},
              'historical_native_evidence': historical, 'ordered_archives_component': component,
              'ordered_archives_native_proof': proof, 'ordered_archives_proof_sha256': digest(proof_raw),
              'archive_sector_changes': by_archive, 'native_archive_layout_validation': layout,
              'inherited_components': 'Eight unaffected preceding game payloads exact 0.1.37; all 1525 member payloads in six repacked archives unchanged',
              'component_manifest_name': 'ordered-archives-component.json',
              'readme_component_text':
                  'Fixes the archive layout that caused the corrupted screen after New Game and the memory screen.\n'
                  'The game uses cumulative rounded sector lengths, not every AFS offset. Six archives now match that native lookup.\n'
                  'Every translated member payload, font and executable remains unchanged.\n'
                  'Captured wrong loading is reproduced exactly; all 2063 native SDK lookups pass.\n'
                  'TEST: start this new disc from a fresh boot, choose New Game, and pass the memory screen. Check for the first dialogue.\n'
                  'Do not resume a save state captured during the corruption: it contains overwritten game code. Existing VMU save files are not changed.\n',
              'readme_movie_text': previous['readme_movie_text'],
              'proof_scope': 'Captured wrong ADV00 read reproduced byte-for-byte; native SDK validation, directory traversal and cumulative-sector lookup for all 2063 members. Six archive layouts repaired with 1525 exact member payloads, no font/executable/translation change. Full track, EDC/ECC and re-extraction checks are separate. Live fresh New Game remains a user test gate.',
              'pending': list(dict.fromkeys(['Fresh-boot New Game past the memory screen; first dialogue and continued asset loading',
                                           'Later world-map, album, credits, effects and additional-profile loading/navigation',
                                           *previous['pending']])), 'release': False}
    return disc, cue, inherited, targets, changes, names, historical, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print('PASS:', len(planned[4]), 'sector substitutions;', planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; fourteen payloads and 26 historical proofs.', flush=True)
    if not args.write:
        print('DRY RUN: no new game build written.')
        return
    replacements, _ = compose()
    write_plan(planned, VERSION, PRIOR, replacements)
    out = ROOT / 'work/output' / VERSION
    for name in ('component-report.json', 'native-test.json'):
        (out / ('ordered-archives-' + name)).write_bytes((OUT / name).read_bytes())
    path = out / 'font4x-patch.json'
    manifest = json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION, previous_build=PRIOR,
                    status='Native archive loading layout corrected; fresh New Game testing pending')
    manifest['ordered_archives'] = {'version': VERSION, 'archives': list(replacements),
                                    'native_lookup_cases': 2063, 'payloads_unchanged': 1525,
                                    'live_validation': 'pending user fresh-boot New Game test'}
    for name, raw in replacements.items():
        if name in manifest.get('files', {}):
            manifest['files'][name]['target_sha256'] = digest(raw)
    path.write_text(json.dumps(manifest, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
