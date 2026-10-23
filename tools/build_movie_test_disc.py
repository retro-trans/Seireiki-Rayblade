"""Package movie-only build 0.1.23 over the verified 0.1.22 disc. Dry first.

All existing executable/font/text/archive bytes and their historical proof
identities remain unchanged. Only MOV072's original video sectors change.
No release, ISO allocation change or claim of live native playback.
"""
import argparse
import json
import re
import shutil

from audit_sfd_container import inspect
from build_bitmap_font import ROOT, digest
from build_test_disc import regenerate
from build_text_filter_disc import plan as previous_plan
from disc_inventory import Disc, SECTOR


VERSION = '0.1.23'
PRIOR = '0.1.22'
MOVIE = 'MOV072.SFD'
DRAFT = ROOT / 'work/output/movie-drafts/MOV072/captions-ui-endtitle-01'


def plan():
    base = ROOT / 'work/output' / PRIOR
    prior = json.loads((base / 'english-disc-report.json').read_text('utf-8'))
    assert prior['version'] == PRIOR and prior['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert prior['validation']['unrelated_track_bytes'] == 'all unchanged'
    # Re-evaluate the existing incremental packager's proof/capacity gates.
    # This only reads files and retains actual tested executable identities.
    _, _, inherited, old_changes, _, checked_prior = previous_plan()
    assert checked_prior['files'] == prior['files']
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    inventory = {r['path']: r for r in disc.inventory()}
    for name, raw in inherited.items():
        row = inventory[name]
        assert disc.read(row['lba'], row['size']) == raw, ('Prior disc component mismatch', name)
        component_path = base / (name if name in ('1ST_READ.BIN', 'WIN00.AFS', 'D_SCE.AFS') else 'text/' + name)
        assert component_path.read_bytes() == raw
    render = json.loads((DRAFT / 'render-report.json').read_text('utf-8'))
    candidate = json.loads((DRAFT / 'sfd-candidate-report.json').read_text('utf-8'))
    decoded = json.loads((DRAFT / 'decoded-comparison.json').read_text('utf-8'))
    movie = (ROOT / candidate['candidate']).read_bytes()
    assert digest(movie) == candidate['candidate_sha256'] == decoded['candidate_sha256']
    assert decoded['exact_decoded_video_frames'] == 3084 and decoded['decoded_pcm_identical_to_original_adx']
    assert len(decoded['witness_frames']) == 25 and decoded['software_decode_errors'] == 0
    assert render['captioned_frames'] == 405 and len(render['per_cue_frames']) == 13
    assert render['captured_ui']['label_count'] == 25 and render['ending_title']['frames'] == 123
    for key in ('captured_ui', 'ending_title'):
        assert digest((ROOT / render[key]['recipe']).read_bytes()) == render[key]['recipe_sha256']
    row = inventory[MOVIE]
    original = disc.read(row['lba'], row['size'])
    assert digest(original) == candidate['source_sha256'] == render['source_sha256']
    assert len(original) == len(movie) == row['size'] == 37392384
    old_container, old_packs, old_streams = inspect(original)
    new_container, new_packs, new_streams = inspect(movie)
    assert new_streams[0xc0] == old_streams[0xc0]
    assert digest(new_streams[0xe0]) == candidate['video_sha256']
    assert new_container['metadata'] == old_container['metadata']
    video_slots = {p['sector'] for p in old_packs if any(s['id'] == '0xe0' for s in p.get('packets', []))}
    changed = [n for n in range(len(movie) // 2048) if original[n * 2048:(n + 1) * 2048] != movie[n * 2048:(n + 1) * 2048]]
    assert set(changed) <= video_slots and len(changed) == 15723
    changes = []
    handles = {}
    try:
        for n in changed:
            lba = row['lba'] + n
            track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
            name = track['path'].name
            fh = handles.setdefault(name, track['path'].open('rb')) if name not in handles else handles[name]
            offset = (track['index'] + lba - track['start_lba']) * SECTOR
            fh.seek(offset)
            source_sector = fh.read(SECTOR)
            assert len(source_sector) == SECTOR and regenerate(source_sector) == source_sector
            assert source_sector[16:2064] == original[n * 2048:(n + 1) * 2048]
            target_sector = bytearray(source_sector)
            target_sector[16:2064] = movie[n * 2048:(n + 1) * 2048]
            changes.append((name, offset, regenerate(target_sector)))
    finally:
        for fh in handles.values():
            fh.close()
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5
    historical = []
    for path in sorted(base.glob('*test.json')):
        proof = json.loads(path.read_text('utf-8'))
        tested = '0.1.22' if path.name == 'text-filter-native-test.json' else '0.1.21'
        historical.append({'file': path.name, 'actual_tested_build': tested,
                           'executable_sha256': proof['executable_sha256'], 'sha256': digest(path.read_bytes())})
    assert len(historical) == 14
    all_targets = dict(inherited, **{MOVIE: movie})
    prior_locations = prior['total_changed_sector_locations_from_original']
    # Original MOV072 is exact in prior disc, so its new deltas cannot overlap
    # any pre-existing English delta. Verify using original disc payload too.
    original_disc = Disc(next(ROOT.glob('*.cue')))
    original_inventory = {r['path']: r for r in original_disc.inventory()}
    old_movie = original_inventory[MOVIE]
    assert old_movie == row
    assert original_disc.read(row['lba'], row['size']) == original
    report = {'version': VERSION, 'source_build': PRIOR,
              'kind': 'Local movie-insertion test: English demo captions/UI/ending title; unfinished full translation',
              'movie_extent': row, 'new_changed_sectors': len(changes),
              'total_changed_sector_locations_from_original': prior_locations + len(changes),
              'files': {name: {'size': len(raw), 'sha256': digest(raw)} for name, raw in all_targets.items()},
              'inherited_components': 'All five executable/font/text/archive files exact 0.1.22',
              'historical_native_evidence': historical,
              'movie_candidate': candidate, 'movie_render': render, 'movie_decoded_comparison': decoded,
              'proof_scope': 'Software movie decoding and preservation only. Native component reports retain their actual tested versions/hashes; no new SH-4/GPU/movie-runtime proof claimed.',
              'pending': ['Movie startup, complete playback, looping/skipping and A/V synchronization in Flycast',
                          'Initial 3D/moving-art titles in MOV072 and MOV055',
                          'English reading speed, independent meaning/content review and full-game validation',
                          'Held passages, live current-font/UI/library/battle and save/load/navigation checks'],
              'release': False}
    return disc, cue, inherited, all_targets, changes, names, historical, report


def write_plan(planned, version, prior_version, additional_components=None):
    disc, cue, inherited, targets, changes, names, historical, report = planned
    additional_components = additional_components or {}
    assert all(name in targets and targets[name] == raw for name, raw in additional_components.items())
    assert all(re.fullmatch(r'[A-Z0-9_]+\.(?:AFS|PVR)', name) or name in ('1ST_READ.BIN', 'D_NAMES.BIN', 'D_BMESS.BIN')
               for name in additional_components)
    # Preserve reproducibility of historical builds. Starting with the repair
    # build, every new package must satisfy the actual SDK sector lookup.
    if tuple(map(int,version.split('.'))) >= (0,1,38):
        from afs_layout import require_native_layouts
        report['native_archive_layout_validation'] = require_native_layouts(targets)
    out = ROOT / 'work/output' / version
    assert not out.exists(), 'Refuse to overwrite an existing build'
    out.mkdir(parents=True)
    base = cue.parent.parent
    for path in base.iterdir():
        if path.is_file() and path.name not in ('english-disc-report.json', 'READ-ME.txt'):
            shutil.copyfile(path, out / path.name)
    shutil.copytree(base / 'text', out / 'text')
    for name, raw in targets.items():
        if name.endswith('.SFD') or name in additional_components:
            destination = out / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
            destination.write_bytes(raw)
        component_path = out / (name if name == '1ST_READ.BIN' or name.endswith(('.SFD', '.AFS', '.PVR')) else 'text/' + name)
        assert component_path.read_bytes() == raw, ('Copied build component mismatch', name)
    folder = out / 'disc'
    folder.mkdir()
    for name in names:
        shutil.copyfile(cue.parent / name, folder / name)
    track_edits = {}
    for name, offset, raw in changes:
        track_edits.setdefault(name, []).append((offset, raw))
    for name, edits in track_edits.items():
        with (folder / name).open('r+b') as fh:
            for offset, raw in edits:
                fh.seek(offset)
                fh.write(raw)
    title = f'Rayblade English Test {version}'
    target_cue = folder / (title + '.cue')
    target_cue.write_bytes(cue.read_bytes())
    (folder / (title + '.gdi')).write_bytes((cue.parent / f'Rayblade English Test {prior_version}.gdi').read_bytes())
    shutil.copyfile(out / 'FONT-LICENSE.txt', folder / 'FONT-LICENSE.txt')
    finished = Disc(target_cue)
    assert finished.inventory() == disc.inventory()
    entries = {r['path']: r for r in finished.inventory()}
    for name, raw in targets.items():
        row = entries[name]
        assert finished.read(row['lba'], row['size']) == raw, name
    verified_bytes = 0
    for name in names:
        edits = sorted(track_edits.get(name, []))
        cursor = 0
        with (cue.parent / name).open('rb') as a, (folder / name).open('rb') as b:
            position = 0
            while True:
                expected = bytearray(a.read(4 * 1024 * 1024))
                actual = b.read(len(expected))
                if not expected:
                    assert not b.read(1)
                    break
                while cursor < len(edits) and edits[cursor][0] + SECTOR <= position:
                    cursor += 1
                j = cursor
                while j < len(edits) and edits[j][0] < position + len(expected):
                    offset, raw = edits[j]
                    lo, hi = max(position, offset), min(position + len(expected), offset + SECTOR)
                    if lo < hi:
                        expected[lo - position:hi - position] = raw[lo - offset:hi - offset]
                    j += 1
                assert actual == expected, (name, position)
                position += len(expected)
                verified_bytes += len(expected)
    for name, edits in track_edits.items():
        with (folder / name).open('rb') as fh:
            for offset, raw in edits:
                fh.seek(offset)
                actual = fh.read(SECTOR)
                assert actual == raw and regenerate(actual) == actual
    for previous in historical:
        assert digest((out / previous['file']).read_bytes()) == previous['sha256']
    report['validation'] = {'reextracted_files': f'all {len(targets)} exact', 'changed_sector_EDC_ECC': 'pass',
                            'unrelated_ISO_entries': 'unchanged', 'unrelated_track_bytes': 'all unchanged',
                            'track_bytes_compared': verified_bytes, 'audio_movie_sectors': f'all {report.get("original_audio_sector_count", 2531)} original sectors exact',
                            'in_game': 'pending'}
    (out / 'english-disc-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    component = {k: report[k] for k in ('version', 'source_build', 'movie_extent', 'files', 'proof_scope', 'pending', 'validation')}
    if 'movie_extents' in report:
        component['movie_extents'] = report['movie_extents']
    component_name = report.get('component_manifest_name', 'movie-component.json')
    assert re.fullmatch(r'[a-z-]+-component\.json', component_name)
    (out / component_name).write_text(json.dumps(component, indent=2) + '\n', 'utf-8')
    movie_readme = report.get('readme_movie_text',
        'MOV072 demo movie now contains 13 English dialogue captions, 25 captured UI labels and a rebuilt English ending title.\n'
        'The earlier title and opening MOV055 title still contain Japanese. Held text and full translation review remain incomplete.\n')
    (out / 'READ-ME.txt').write_text(title + '\n\nOpen disc/' + title + '.gdi in Flycast.\n'
        + report.get('readme_component_text', 'Includes the 0.1.22 integrated Latin font and English text components unchanged.\n')
        + movie_readme +
        'Software decoding/audio/preservation checks pass; native movie playback, timing and full-game behavior are unverified.\n'
        'Previous native reports keep their actual tested builds and executable hashes.\nLocal test only; no release.\n', 'utf-8')
    print(f'PASS: {len(targets)} exact extracted files, valid changed sectors and all unrelated track bytes preserved.', flush=True)
    print(folder / (title + '.gdi'), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print(f'PASS: {len(planned[4])} movie-sector deltas; exact original audio; all five inherited components and 14 historical proof identities retained.', flush=True)
    if not args.write:
        print('DRY RUN: no components or disc written')
        return
    write_plan(planned, VERSION, PRIOR)


if __name__ == '__main__':
    main()
