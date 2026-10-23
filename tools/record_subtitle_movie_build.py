"""Record selected moving-title subtitles after checking the packaged build.

Dry run first. Preserve historical intro/recovery evidence and make current
selection, game component identities and remaining live checks explicit.
"""
import argparse
import json

from build_bitmap_font import ROOT, digest
from build_subtitle_movie_test_disc import VERSION, PRIOR, SOURCES
from disc_inventory import Disc
from prepare_movie_moving_title import prepare, recipe_path, preview_dir


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\', '/')


def record():
    out = ROOT / 'work/output' / VERSION
    report = read(out / 'english-disc-report.json')
    previous = read(ROOT / 'work/output' / PRIOR / 'english-disc-report.json')
    assert report['version'] == VERSION and report['source_build'] == PRIOR
    assert report['validation']['reextracted_files'] == 'all 11 exact'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['new_changed_sectors'] == 332 and report['total_changed_sector_locations_from_original'] == 28326
    assert report['original_audio_sector_count'] == 4041
    assert len(report['historical_native_evidence']) == 18
    disc_path = out / 'disc' / f'Rayblade English Test {VERSION}.gdi'
    disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']: r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        data = disc.read(row['lba'], row['size'])
        assert len(data) == info['size'] and digest(data) == info['sha256']
        if not name.endswith('.SFD'):
            assert info == previous['files'][name]
    for item in report['historical_native_evidence']:
        data = (out / item['file']).read_bytes()
        assert digest(data) == item['sha256'] and json.loads(data)['executable_sha256'] == item['executable_sha256']
    movies, contacts = [], []
    for name, relative in SOURCES.items():
        folder = ROOT / relative
        render = read(folder / 'render-report.json')
        decoded = read(folder / 'decoded-comparison.json')
        mux = read(folder / 'sfd-candidate-report.json')
        assert mux['candidate_sha256'] == decoded['candidate_sha256'] == report['files'][name]['sha256']
        assert decoded['exact_decoded_video_frames'] == render['frame_count']
        assert decoded['decoded_pcm_identical_to_original_adx'] and decoded['software_decode_errors'] == 0
        for file in ('render-report.json', 'sfd-candidate-report.json', 'decoded-comparison.json'):
            assert (out / (name[:6] + '-' + file)).read_bytes() == (folder / file).read_bytes()
        recipe = read(recipe_path(name))
        assert recipe == prepare(name)
        assert digest(recipe_path(name).read_bytes()) == render['moving_title']['recipe_sha256']
        assert len(decoded['moving_title_witnesses']) == 9
        witnesses = []
        for page in decoded['contact_sheets']:
            path = ROOT / page
            assert path.is_file()
            witnesses.append({'path': page, 'sha256': digest(path.read_bytes())})
        contacts.extend(witnesses)
        movies.append({'movie': name, 'sha256': mux['candidate_sha256'],
                       'source_interval': [recipe['start_frame'], recipe['end_frame_exclusive']],
                       'subtitle_frames': render['moving_title']['frames'],
                       'recipe': rel(recipe_path(name)), 'recipe_sha256': digest(recipe_path(name).read_bytes()),
                       'prepared_previews': [rel(preview_dir(name) / f'comparison-{n:02d}.png') for n in range(3)],
                       'encoded_contacts_reviewed': witnesses, 'encoded_witness_frames': decoded['witness_frames'],
                       'software_frames': render['frame_count'], 'audio_PCM_exact': True,
                       'source_schedule': mux['source_deadline_scheduling']})
    assert sum(m['subtitle_frames'] for m in movies) == 108
    assert sum(m['software_frames'] for m in movies) == 4924
    assert sum(len(m['encoded_witness_frames']) for m in movies) == 59 and len(contacts) == 16
    doc = {'version': VERSION, 'source_build': PRIOR,
           'status': 'Selected original moving-logo artwork plus English subtitle inserted in both movies; full-motion and native playback/review pending',
           'disc': rel(disc_path), 'treatment': 'A — Original artwork + English subtitle',
           'user_selection': 'Explicit user answer received 2026-10-23', 'movies': movies,
           'Japanese_logo_artwork': 'Intentionally retained by the selected treatment; English title is added below',
           'source_pixels_before_encoding': 'Exact outside English subtitle/shadow strokes during moving-title intervals; prior English intro/caption/UI/ending treatments retained',
           'subtitle_timing': 'Opening [349,409), demo [1489,1537); separate fades/holds, not one fixed frame offset',
           'font': 'Supplied Latin bitmap at one uniform source scale; normal text font unchanged',
           'software_movie_checks': {'all_video_frames_and_order': 4924, 'original_ADX_and_decoded_PCM': 'exact for both movies',
                                     'encoded_witnesses_reviewed': 59, 'encoded_contact_sheets_reviewed': 16,
                                     'new_subtitle_witnesses': 18,
                                     'scope': 'Software decoding/static witnesses and disc preservation; no native movie execution or full-motion review'},
           'packaging': report['validation'], 'inherited_components': report['inherited_components'],
           'historical_native_evidence': report['historical_native_evidence'],
           'new_changed_sectors': 332, 'changed_sector_locations_from_original': 28326,
           'native_playback_checks': {movie: {key: 'pending' for key in
               ('startup', 'complete_video', 'English_title', 'audio_sync', 'skip', 'loop_or_return')} for movie in SOURCES},
           'remaining': report['pending'], 'normal_text_font_changed': False,
           'release': False, 'story_library_draft_credit': 0}
    background_path = ROOT / 'docs/movie-title-background.json'
    background = read(background_path)
    background.update(status='Recovery study retained as historical evidence; user selected original artwork plus English subtitle, now packaged in 0.1.29',
                      user_preference={'choice': 'A', 'treatment': doc['treatment'], 'source': doc['user_selection']},
                      current_treatment=doc,
                      next_work=['Native movie playback/sync/skip/loop/return and full-motion design/content review'])
    background['no_game_movie_edits_scope'] = 'The recovery analysis and original static comparisons made no game edits; the separately recorded selected treatment now does.'
    intro_path = ROOT / 'docs/movie-intro-title.json'
    intro = read(intro_path)
    intro.update(status='English intro stages retained in combined 0.1.29 movies; selected moving-title subtitles inserted, native playback pending',
                 last_packaged_build=VERSION, latest_combined_movie_build=doc)
    intro['remaining'] = ['Whole-motion/design and source-content/audio review',
                           'Native startup/completion/sync/skipping/looping checks',
                           'Whole-game translation/review, held passages and font/live validation remain incomplete']
    for movie in intro['movies']:
        movie['moving_art_title'] = 'Original Japanese logo retained by selected A; English subtitle added in the combined 0.1.29 movie'
    audit_path = ROOT / 'docs/movie-text-audit.json'
    audit = read(audit_path)
    audit.update(status=doc['status'], last_packaged_build=VERSION,
                 local_movie_insertion={'version': VERSION, 'disc': rel(disc_path), 'scope': doc['status'], 'live_playback': 'pending'},
                 movie_intro_title_candidates=intro, moving_title_artwork=background, selected_moving_title_build=doc)
    for movie in movies:
        audit[movie['movie'][:6]].update(latest_moving_title_subtitle=movie, translation_inserted=True,
                                         native_movie_playback_verified=False)
    audit['MOV072']['remaining'] = ['Independent meaning, full-motion and English caption reading-speed review',
                                   'Frame-complete movie/content/audio audit', 'Native playback/buffering/A-V synchronization verification']
    status_path = ROOT / 'docs/translation-status.json'
    status = read(status_path)
    status.update(version=VERSION,
                  stage='Selected original moving-logo artwork plus English subtitles inserted in opening/demo over unchanged 0.1.28 native/text/album components; remaining image/held text/meaning/font/live and full-game validation incomplete',
                  latest_movie_build=doc, movie_intro_title_candidates=intro, movie_text_audit=audit,
                  movie_title_background=background)
    status['test_disc'].update(version=VERSION, source_build=PRIOR, path=rel(disc_path), kind=report['kind'],
                               changed_sectors=28326, validation=report['validation'], movie_delta_sectors=332,
                               movies=report['movies'], movie_sha256=report['files']['MOV072.SFD']['sha256'],
                               pending=report['pending'])
    status['test_disc'].pop('album_caption_delta_sectors', None)
    return [(ROOT / 'docs/movie-moving-title.json', doc), (ROOT / 'docs/movie-insertion.json', doc),
            (background_path, background), (intro_path, intro), (audit_path, audit), (status_path, status)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    edits = record()
    print('PASS: 0.1.29, selected A, 108 subtitle frames, 4924 decoded frames, 59 reviewed witnesses, eleven exact payloads; 332 changed sectors over 0.1.28.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path, data in edits:
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
