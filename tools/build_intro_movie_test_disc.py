"""Package build 0.1.24 with the two checked English intro-title candidates.

Dry run by default. The moving-art title choice is intentionally not selected.
Existing native code/font/text/archive files retain their actual proof scope.
"""
import argparse
import json
import re

from audit_sfd_container import inspect
from build_bitmap_font import ROOT, digest
from build_movie_test_disc import write_plan
from build_test_disc import regenerate
from disc_inventory import Disc, SECTOR


VERSION, PRIOR = '0.1.24', '0.1.23'
SOURCES = {'MOV055.SFD': 'work/output/movie-drafts/MOV055/intro-title-01',
           'MOV072.SFD': 'work/output/movie-drafts/MOV072/captions-ui-titles-01'}


def plan():
    base = ROOT / 'work/output' / PRIOR
    previous = json.loads((base / 'english-disc-report.json').read_text('utf-8'))
    assert previous['version'] == PRIOR and previous['validation']['reextracted_files'] == 'all 6 exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    prior_data = {}
    for name, info in previous['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'], row['size'])
        assert digest(raw) == info['sha256'] and len(raw) == info['size']
        prior_data[name] = raw
    native = {n: raw for n, raw in prior_data.items() if not n.endswith('.SFD')}
    assert len(native) == 5
    historical = previous['historical_native_evidence']
    assert len(historical) == 14
    for item in historical:
        data = (base / item['file']).read_bytes()
        assert digest(data) == item['sha256']
        assert json.loads(data)['executable_sha256'] == item['executable_sha256']
    original_disc = Disc(next(ROOT.glob('*.cue')))
    original_entries = {r['path']: r for r in original_disc.inventory()}
    assert original_entries.keys() == entries.keys()
    changes = []
    movies = []
    targets = dict(native)
    total_movie_locations = 0
    audio_sectors = 0
    for name, relative in SOURCES.items():
        folder = ROOT / relative
        mux = json.loads((folder / 'sfd-candidate-report.json').read_text('utf-8'))
        render = json.loads((folder / 'render-report.json').read_text('utf-8'))
        decoded = json.loads((folder / 'decoded-comparison.json').read_text('utf-8'))
        raw = (ROOT / mux['candidate']).read_bytes()
        assert digest(raw) == mux['candidate_sha256'] == decoded['candidate_sha256']
        expected = 1840 if name == 'MOV055.SFD' else 3084
        assert decoded['exact_decoded_video_frames'] == render['frame_count'] == expected
        assert decoded['decoded_pcm_identical_to_original_adx'] and decoded['software_decode_errors'] == 0
        assert render['intro_title']['frames'] == render['intro_title']['source_index_matches'] == 32
        recipe = ROOT / render['intro_title']['recipe']
        assert digest(recipe.read_bytes()) == render['intro_title']['recipe_sha256']
        row = entries[name]
        assert row == original_entries[name], 'Movie extent changed from original'
        original = original_disc.read(row['lba'], row['size'])
        assert digest(original) == mux['source_sha256']
        original_info, packs, streams = inspect(original)
        target_info, _, target_streams = inspect(raw)
        assert len(raw) == len(original) == row['size']
        assert original_info['metadata'] == target_info['metadata']
        assert target_streams[0xc0] == streams[0xc0]
        assert digest(target_streams[0xe0]) == mux['video_sha256']
        slots = {p['sector'] for p in packs if any(q['id'] == '0xe0' for q in p.get('packets', []))}
        for n in range(len(raw) // 2048):
            a, b = original[n * 2048:(n + 1) * 2048], raw[n * 2048:(n + 1) * 2048]
            if a != b:
                assert n in slots
                total_movie_locations += 1
            assert a[:12] == b[:12]
        audio_sectors += original_info['packet_counts']['0xc0']
        prior = disc.read(row['lba'], row['size'])
        if name in prior_data:
            assert prior == prior_data[name]
        else:
            assert prior == original
        changed = [n for n in range(len(raw) // 2048) if prior[n * 2048:(n + 1) * 2048] != raw[n * 2048:(n + 1) * 2048]]
        assert set(changed) <= slots
        handles = {}
        try:
            for n in changed:
                lba = row['lba'] + n
                track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
                filename = track['path'].name
                if filename not in handles:
                    handles[filename] = track['path'].open('rb')
                handle = handles[filename]
                offset = (track['index'] + lba - track['start_lba']) * SECTOR
                handle.seek(offset)
                sector = handle.read(SECTOR)
                assert regenerate(sector) == sector
                assert sector[16:2064] == prior[n * 2048:(n + 1) * 2048]
                edited = bytearray(sector)
                edited[16:2064] = raw[n * 2048:(n + 1) * 2048]
                changes.append((filename, offset, regenerate(edited)))
        finally:
            for handle in handles.values():
                handle.close()
        targets[name] = raw
        movies.append({'movie': name, 'extent': row, 'candidate_sha256': mux['candidate_sha256'],
                       'new_changed_sectors': len(changed), 'software_frames': expected,
                       'intro_title_frames': 32, 'original_audio': 'exact ADX and decoded PCM',
                       'candidate_report': str((folder / 'sfd-candidate-report.json').relative_to(ROOT)).replace('\\', '/'),
                       'decoded_report': str((folder / 'decoded-comparison.json').relative_to(ROOT)).replace('\\', '/'),
                       'source_schedule': mux['source_deadline_scheduling']})
    assert total_movie_locations == 25099 and audio_sectors == 4041
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5
    native_locations = previous['total_changed_sector_locations_from_original'] - previous['new_changed_sectors']
    assert native_locations == 2671
    report = {'version': VERSION, 'source_build': PRIOR,
              'kind': 'Local opening/demo English intro-title insertion test; unfinished translation/review',
              'movie_extent': entries['MOV072.SFD'], 'movie_extents': [m['extent'] for m in movies],
              'new_changed_sectors': len(changes), 'total_changed_sector_locations_from_original': native_locations + total_movie_locations,
              'original_audio_sector_count': audio_sectors,
              'files': {n: {'size': len(raw), 'sha256': digest(raw)} for n, raw in targets.items()},
              'movies': movies, 'inherited_components': 'All five executable/font/text/archive files exact 0.1.23/0.1.22',
              'historical_native_evidence': historical,
              'proof_scope': 'Software movie/frame/audio and disc preservation checks only; all native reports retain their actual 0.1.21/0.1.22 executable identities',
              'readme_movie_text': 'MOV055 opening and MOV072 demo include rebuilt English intro-title stages.\n'
                                  'The demo also retains 13 English captions, 25 UI labels and the English ending title.\n'
                                  'The later title over moving mech art remains Japanese in both movies; treatment preference is pending.\n',
              'pending': ['Moving-art title treatment selection and implementation',
                          'Native boot/movie startup/completion/A-V sync/skip/loop/return tests for both movies',
                          'Full-motion/design/content/audio and independent translation review',
                          'Held passages, live font/UI/library/battle/save/load and full-game validation'],
              'release': False}
    return disc, cue, native, targets, changes, names, historical, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print(f'PASS: {len(planned[4])} sector deltas over 0.1.23; seven payloads; 4041 exact original audio sectors; native components unchanged.', flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned, VERSION, PRIOR)


if __name__ == '__main__':
    main()
