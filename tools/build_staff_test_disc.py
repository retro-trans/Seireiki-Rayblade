"""Package local build 0.1.26 with translated credit labels. Default dry run."""
import argparse
import json
import re

from build_bitmap_font import ROOT, digest
from build_movie_test_disc import write_plan
from build_test_disc import regenerate
from build_staff_credits import OUT, compose
from disc_inventory import Disc, SECTOR

VERSION, PRIOR = '0.1.26', '0.1.25'


def plan():
    base = ROOT / 'work/output' / PRIOR
    previous = json.loads((base / 'english-disc-report.json').read_text('utf-8'))
    assert previous['version'] == PRIOR and previous['validation']['reextracted_files'] == 'all 8 exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    inherited = {}
    for name, record in previous['files'].items():
        entry = entries[name]
        data = disc.read(entry['lba'], entry['size'])
        assert len(data) == record['size'] and digest(data) == record['sha256']
        path = base / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
        assert path.read_bytes() == data
        inherited[name] = data
    historical = list(previous['historical_native_evidence'])
    assert len(historical) == 14
    map_proof_bytes = (base / 'worldmap-native-test.json').read_bytes()
    map_proof = json.loads(map_proof_bytes)
    assert digest(map_proof_bytes) == previous['worldmap_proof_sha256']
    assert map_proof['archive_sha256'] == digest(inherited['WMAP.AFS'])
    historical.append({'file': 'worldmap-native-test.json', 'sha256': digest(map_proof_bytes),
                       'executable_sha256': map_proof['executable_sha256'],
                       'actual_tested_build': map_proof['source_build'],
                       'scope': 'World-map archive PRS/texture and structural checks; no live I/O or GPU proof'})
    for item in historical:
        raw = (base / item['file']).read_bytes()
        assert digest(raw) == item['sha256']
        assert json.loads(raw)['executable_sha256'] == item['executable_sha256']
    target = (OUT / 'STAFF.AFS').read_bytes()
    component = json.loads((OUT / 'component-report.json').read_text('utf-8'))
    proof = json.loads((OUT / 'native-test.json').read_text('utf-8'))
    built = compose()
    assert target == built[0] and component == built[4]
    assert proof['archive_sha256'] == component['target_archive_sha256'] == digest(target)
    assert proof['executable_sha256'] == digest(inherited['1ST_READ.BIN'])
    assert proof['native_guard_and_ABI'] == 'pass' and proof['label_count'] == 56
    assert proof['original_pixels_and_archive_bytes_outside_declared_edits'] == 'exact'
    row = entries['STAFF.AFS']
    source = disc.read(row['lba'], row['size'])
    original_disc = Disc(next(ROOT.glob('*.cue')))
    original_row = next(r for r in original_disc.inventory() if r['path'] == 'STAFF.AFS')
    assert row == original_row and original_disc.read(row['lba'], row['size']) == source
    assert digest(source) == component['source_archive_sha256'] and len(target) == len(source)
    changed = [n for n in range(len(target) // 2048)
               if source[n * 2048:(n + 1) * 2048] != target[n * 2048:(n + 1) * 2048]]
    changes = []
    handles = {}
    try:
        for n in changed:
            lba = row['lba'] + n
            track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
            name = track['path'].name
            if name not in handles:
                handles[name] = track['path'].open('rb')
            fh = handles[name]
            offset = (track['index'] + lba - track['start_lba']) * SECTOR
            fh.seek(offset)
            raw = fh.read(SECTOR)
            assert len(raw) == SECTOR and regenerate(raw) == raw
            assert raw[16:2064] == source[n * 2048:(n + 1) * 2048]
            patch = bytearray(raw)
            patch[16:2064] = target[n * 2048:(n + 1) * 2048]
            changes.append((name, offset, regenerate(patch)))
    finally:
        for handle in handles.values():
            handle.close()
    targets = dict(inherited, **{'STAFF.AFS': target})
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5
    report = {'version': VERSION, 'source_build': PRIOR,
              'kind': 'Local translated credit-label test; seven name readings and full-game translation/review incomplete',
              'movie_extent': previous['movie_extent'], 'movie_extents': previous['movie_extents'],
              'movies': previous['movies'], 'original_audio_sector_count': 4041,
              'new_changed_sectors': len(changes),
              'total_changed_sector_locations_from_original': previous['total_changed_sector_locations_from_original'] + len(changes),
              'files': {n: {'size': len(raw), 'sha256': digest(raw)} for n, raw in targets.items()},
              'historical_native_evidence': historical,
              'credits_component': component, 'credits_native_proof': proof,
              'credits_proof_sha256': digest((OUT / 'native-test.json').read_bytes()),
              'inherited_components': 'All eight preceding game payloads exact 0.1.25',
              'component_manifest_name': 'credits-component.json',
              'readme_component_text': 'Adds 21 translated credit roles/company labels and 35 name readings from a secondary credits reference.\n'
                                       'Seven unresolved names remain as original Japanese images. Credits are not fully translated.\n'
                                       'The native credit atlas remains 1024x256, with every original member offset retained.\n'
                                       'Native decoding/texture and structural checks pass; actual credit playback is unverified.\n'
                                       'All eight preceding game payloads, including the English world map, are unchanged.\n',
              'readme_movie_text': previous['readme_movie_text'],
              'proof_scope': 'New credit-atlas native PRS/texture-info execution plus independent pixel/geometry/preservation checks; no name-reading proof, native I/O, credit playback, sprite pipeline or GPU proof. Fifteen historical reports retain tested identities.',
              'pending': ['Seven credit-name readings and independent confirmation of reference romanizations',
                          'Live credit timing/order, appearance, alignment and overlaps', *previous['pending']],
              'release': False}
    return disc, cue, inherited, targets, changes, names, historical, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print(f'PASS: {len(planned[4])} new credit-archive sectors; nine payloads; eight inherited payloads and fifteen historical reports exact.', flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned, VERSION, PRIOR, additional_components={'STAFF.AFS': planned[3]['STAFF.AFS']})
    out = ROOT / 'work/output' / VERSION
    for name in ('component-report.json', 'native-test.json', *(f'credits-preview-{i:02d}.png' for i in range(4))):
        (out / ('credits-' + name if not name.startswith('credits-') else name)).write_bytes((OUT / name).read_bytes())


if __name__ == '__main__':
    main()
