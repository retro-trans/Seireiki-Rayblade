"""Record the locally packaged movie-only build without claiming live playback.

Dry run by default. Preserve the actual versions of inherited native reports.
"""
import argparse
import json

from build_bitmap_font import ROOT, digest
from build_movie_test_disc import VERSION, PRIOR, DRAFT
from disc_inventory import Disc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'work/output' / VERSION
    report = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
    assert report['version'] == VERSION and report['source_build'] == PRIOR
    assert report['validation']['reextracted_files'] == 'all 6 exact'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['new_changed_sectors'] == 15723
    assert report['total_changed_sector_locations_from_original'] == 18394
    cue = out / 'disc' / f'Rayblade English Test {VERSION}.cue'
    disc = Disc(cue)
    entries = {row['path']: row for row in disc.inventory()}
    for name, expected in report['files'].items():
        row = entries[name]
        assert digest(disc.read(row['lba'], row['size'])) == expected['sha256']
        assert row['size'] == expected['size']
    for proof in report['historical_native_evidence']:
        path = out / proof['file']
        assert digest(path.read_bytes()) == proof['sha256']
        assert json.loads(path.read_text('utf-8'))['executable_sha256'] == proof['executable_sha256']
    assert len(report['historical_native_evidence']) == 14
    runtime_path = ROOT / 'work/ui/0.1.23/runtime-font-check.json'
    runtime = json.loads(runtime_path.read_text('utf-8'))
    assert runtime['pid'] == 34448 and runtime['build_compared'] == VERSION
    # An inconclusive read-only probe and a blue window are not a failed game
    # test: the candidate was not successfully loaded by the UI automation.
    assert runtime['kernel_copies_found'] == 0 and not runtime['font_loaded']
    doc = {'version': VERSION, 'source_build': PRIOR,
           'status': 'Movie candidate inserted into local disc; native startup/playback unverified',
           'disc': f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
           'movie': report['movie_extent'], 'movie_sha256': report['files']['MOV072.SFD']['sha256'],
           'movie_coverage': {'English_dialogue_cues': 13, 'dialogue_frames': 405,
                              'captured_UI_labels': 25, 'UI_frames': 134, 'UI_label_frame_edits': 964,
                              'ending_title_frames': 123, 'total_video_frames': 3084},
           'inherited_components': report['inherited_components'],
           'new_changed_sectors': 15723, 'changed_sector_locations_from_original': 18394,
           'packaging': report['validation'],
           'software_movie_checks': {'decoded_video_frames': 3084, 'decoded_frame_order_and_pixels': 'exact encoded draft',
                                     'original_ADX_and_PCM': 'exact', 'encoded_witness_frames_reviewed': 25,
                                     'scope': 'Software decoder, not game-native buffering/timing/GPU proof'},
           'historical_native_evidence': report['historical_native_evidence'],
           'live_attempt': {'window': 'Flycast', 'window_id': 71110524, 'pid': 34448,
                            'observed_window': 'Blue gradient; no identifiable game scene',
                            'input_error': 'failed to activate captured window',
                            'recovery': 'Fresh window enumeration/capture then supported Raise also failed activation',
                            'read_only_font_probe': str(runtime_path.relative_to(ROOT)).replace('\\', '/'),
                            'probe_scope': runtime['scope'], 'build_loaded': 'unproven',
                            'user_assistance': 'Requested opening the completed GDI and idling at title for demo; answer pending'},
           'native_playback_checks': {key: 'pending' for key in
               ('boot', 'demo_start', 'complete_video', 'English_caption_UI_ending_title',
                'audio_sync', 'return_to_title', 'skip', 'second_loop')},
           'remaining': report['pending'], 'release': False, 'story_library_draft_credit': 0}
    print('Record 0.1.23: six exact disc payloads, 15,723 movie-sector changes and 14 unchanged historical proofs. Live playback remains pending.')
    if not args.write:
        print('DRY RUN: no documentation changed')
        return
    def save(path, value):
        path.write_text(json.dumps(value, indent=2) + '\n', 'utf-8')
    save(ROOT / 'docs/movie-insertion.json', doc)
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status.update(version=VERSION, stage='English demo captions/UI/ending title inserted over unchanged 0.1.22 native components; remaining titles, held passages, meaning review and full-game/live verification incomplete')
    status['latest_movie_build'] = doc
    status['test_disc'].update(version=VERSION, source_build=PRIOR, path=doc['disc'], kind=report['kind'],
                               changed_sectors=18394, validation=doc['packaging'], movie_delta_sectors=15723,
                               movie=doc['movie'], movie_sha256=doc['movie_sha256'])
    if 'movie_text_audit' in status:
        status['movie_text_audit']['last_packaged_build'] = VERSION
        status['movie_text_audit']['local_movie_insertion'] = {'version': VERSION, 'disc': doc['disc'],
                                                              'scope': doc['status'], 'live_playback': 'pending'}
    save(status_path, status)
    movie_path = ROOT / 'docs/movie-text-audit.json'
    movie = json.loads(movie_path.read_text('utf-8'))
    movie['last_packaged_build'] = VERSION
    movie['local_movie_insertion'] = {'version': VERSION, 'disc': doc['disc'], 'scope': doc['status'], 'live_playback': 'pending'}
    movie['status'] = 'MOV072 English captions/UI/ending title inserted into local disc 0.1.23; remaining titles, reviews and native playback incomplete'
    movie['MOV072']['native_movie_translation_inserted'] = True
    movie['MOV072']['native_movie_playback_verified'] = False
    movie['MOV072']['remaining'] = [r.replace('Game insertion and native playback/buffering/A-V synchronization verification',
                                              'Native playback/buffering/A-V synchronization verification') for r in movie['MOV072']['remaining']]
    latest = movie['MOV072']['latest_caption_UI_ending_title_candidate']
    latest.update(not_in_game_build=False, packaged_build=VERSION, disc=doc['disc'])
    save(movie_path, movie)
    status['movie_text_audit'] = movie
    save(status_path, status)


if __name__ == '__main__':
    main()
