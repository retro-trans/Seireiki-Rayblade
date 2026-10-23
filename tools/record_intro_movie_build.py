"""Record packaged 0.1.24; preserve pending native/artwork review boundaries."""
import argparse
import json

from build_bitmap_font import ROOT, digest
from disc_inventory import Disc


VERSION = '0.1.24'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'work/output' / VERSION
    report = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
    assert report['version'] == VERSION and report['source_build'] == '0.1.23'
    assert report['validation']['reextracted_files'] == 'all 7 exact'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['new_changed_sectors'] == 9540 and report['total_changed_sector_locations_from_original'] == 27770
    assert report['original_audio_sector_count'] == 4041
    disc_path = f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi'
    cue = out / 'disc' / f'Rayblade English Test {VERSION}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        assert len(disc.read(row['lba'], row['size'])) == info['size']
        assert digest(disc.read(row['lba'], row['size'])) == info['sha256']
    intro_path = ROOT / 'docs/movie-intro-title.json'
    intro = json.loads(intro_path.read_text('utf-8'))
    assert len(intro['movies']) == 2 and intro['English_intro_frames_total'] == 64
    for movie in intro['movies']:
        assert movie['sha256'] == report['files'][movie['movie']]['sha256']
    for item in report['historical_native_evidence']:
        assert digest((out / item['file']).read_bytes()) == item['sha256']
    assert len(report['historical_native_evidence']) == 14
    previous_path = ROOT / 'docs/movie-insertion.json'
    previous = json.loads(previous_path.read_text('utf-8'))
    doc = {'version': VERSION, 'source_build': '0.1.23',
           'status': 'English opening/demo intro-title candidates inserted into local disc; moving-title choice and native playback pending',
           'disc': disc_path, 'movie': entries['MOV072.SFD'], 'movie_sha256': report['files']['MOV072.SFD']['sha256'],
           'movies': report['movies'], 'movie_coverage': {'English_intro_frames': 64, 'complete_video_frames': 4924,
                                                        'English_demo_dialogue_cues': 13, 'captured_UI_labels': 25,
                                                        'English_ending_title_frames': 123},
           'inherited_components': report['inherited_components'],
           'new_changed_sectors': 9540, 'changed_sector_locations_from_original': 27770,
           'packaging': report['validation'], 'historical_native_evidence': report['historical_native_evidence'],
           'software_movie_checks': {'complete_frames_and_order': 4924, 'original_ADX_and_PCM': 'exact for both movies',
                                     'encoded_witnesses_reviewed': 41,
                                     'scope': 'Software decoder and packaging only; no new SH-4/GPU/native-movie proof'},
           'prior_build_live_attempt': previous.get('live_attempt', previous.get('prior_build_live_attempt')),
           'live_attempt': {'build': VERSION, 'status': 'not verified; earlier window-control failure does not prove a boot/playback outcome for this build'},
           'native_playback_checks': {movie: {key: 'pending' for key in
               ('startup', 'complete_video', 'English_title', 'audio_sync', 'skip', 'loop_or_return')} for movie in ('MOV055.SFD', 'MOV072.SFD')},
           'remaining': report['pending'], 'moving_title_treatment': 'user preference pending; unchanged in disc',
           'release': False, 'story_library_draft_credit': 0}
    print('Record 0.1.24: seven exact payloads, 9540 sector deltas, 4041 original audio sectors exact. Moving-art choice/native playback remain pending.')
    if not args.write:
        print('DRY RUN: no documentation changed')
        return
    def save(path, data):
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')
    save(previous_path, doc)
    intro.update(status='Two English intro-title movie candidates inserted into local test disc 0.1.24; native playback and moving-art treatment pending',
                 last_packaged_build=VERSION)
    for movie in intro['movies']:
        movie.update(in_game_build=True, packaged_build=VERSION, disc=disc_path)
    save(intro_path, intro)
    movie_path = ROOT / 'docs/movie-text-audit.json'
    audit = json.loads(movie_path.read_text('utf-8'))
    audit.update(status=doc['status'], last_packaged_build=VERSION,
                 local_movie_insertion={'version': VERSION, 'disc': disc_path, 'scope': doc['status'], 'live_playback': 'pending'},
                 movie_intro_title_candidates=intro)
    for movie in intro['movies']:
        audit[movie['movie'][:6]]['latest_intro_title_candidate'] = movie
        audit[movie['movie'][:6]]['translation_inserted'] = True
        audit[movie['movie'][:6]]['native_movie_playback_verified'] = False
    audit['MOV072']['remaining'][0] = 'Title over moving mech remains Japanese; the English intro and ending are inserted in 0.1.24'
    save(movie_path, audit)
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status.update(version=VERSION, stage='English opening/demo intro titles inserted over existing English demo captions/UI/ending and unchanged native font/text; moving-title preference, held passages, review and full-game/live verification incomplete')
    status['latest_movie_build'] = doc
    status['movie_intro_title_candidates'] = intro
    status['movie_text_audit'] = audit
    status['test_disc'].update(version=VERSION, source_build='0.1.23', path=disc_path, kind=report['kind'],
                               changed_sectors=27770, validation=report['validation'], movie_delta_sectors=9540,
                               movies=report['movies'], movie_sha256=doc['movie_sha256'])
    save(status_path, status)


if __name__ == '__main__':
    main()
