"""Record bounded movie discovery and timed draft coverage. Dry first."""
import argparse
import json
from collections import Counter

from build_bitmap_font import ROOT, digest
from prepare_movie_translation import prepare as captions
from prepare_movie_ui import prepare as ui_labels
from prepare_movie_ui_layout import prepare as timed_ui
from prepare_movie_title import prepare as ending_title


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    folder = ROOT / 'work/ui/asset-audit/movies'
    index = json.loads((folder / 'movie-index.json').read_text('utf-8'))
    assert index['movies'] == 116 and index['decoded_video_frames'] == 36123
    streams = Counter()
    for row in index['entries']:
        assert row['probe_exit'] == 0 and not row['decode_diagnostics']
        assert digest((ROOT / row['source']).read_bytes()) == row['sha256']
        assert len(row['sample_indices']) == 8
        for s in row['streams']:
            streams[(s['codec_type'], s['codec_name'])] += 1
    assert {kind for kind, _ in streams} == {'video', 'audio'}
    recipe, _, _ = captions()
    movie_ui = ui_labels()
    output = ROOT / 'work/translation/en/movies'
    # Assert the current saved draft matches its reproducible source-linked form.
    assert recipe == json.loads((output / 'MOV072.en.json').read_text('utf-8'))
    assert movie_ui == json.loads((output / 'MOV072-ui.en.json').read_text('utf-8'))
    dense72 = json.loads((folder / 'MOV072/dense/index.json').read_text('utf-8'))
    dense55 = json.loads((folder / 'MOV055/dense/index.json').read_text('utf-8'))
    consecutive = json.loads((folder / 'MOV072/frames-1530-1935_2630-2700/index.json').read_text('utf-8'))
    assert dense72['selected_frames'] == 462 and dense55['selected_frames'] == 471
    assert len(dense72['interval_contact_pages']) == 18
    assert consecutive['selected_frames'] == 477 and len(consecutive['caption_contact_pages']) == 10
    assert len(recipe['cues']) == 13 and len(movie_ui['rows']) == 25
    for a, b in zip(recipe['cues'], recipe['cues'][1:]):
        assert a['start_frame'] < a['end_frame_exclusive'] <= b['start_frame']
    contacts = [{'path': f'work/ui/asset-audit/movies/contact-{i:02d}.png',
                 'sha256': digest((folder / f'contact-{i:02d}.png').read_bytes())} for i in range(15)]
    draft_folder = ROOT / 'work/output/movie-drafts/MOV072/attempt-02'
    render = json.loads((draft_folder / 'render-report.json').read_text('utf-8'))
    candidate = json.loads((draft_folder / 'sfd-candidate-report.json').read_text('utf-8'))
    decoded = json.loads((draft_folder / 'decoded-comparison.json').read_text('utf-8'))
    assert candidate['source_sha256'] == render['source_sha256'] == dense72['source_sha256']
    assert digest((ROOT / candidate['candidate']).read_bytes()) == candidate['candidate_sha256'] == decoded['candidate_sha256']
    assert digest((ROOT / render['native_video']['path']).read_bytes()) == candidate['video_sha256']
    assert digest((ROOT / render['original_audio']['path']).read_bytes()) == candidate['audio_sha256']
    assert decoded['exact_decoded_video_frames'] == 3084 and decoded['decoded_pcm_identical_to_original_adx']
    assert render['captioned_frames'] == 405 and len(render['exact_preview_witnesses']) == 13
    encoded_contacts = [{'path': p, 'sha256': digest((ROOT / p).read_bytes())} for p in decoded['contact_sheets']]
    assert len(encoded_contacts) == 4
    timed = timed_ui()
    timed_path = ROOT / 'work/translation/en/movies/MOV072-ui-layout.en.json'
    assert timed == json.loads(timed_path.read_text('utf-8'))
    assert timed == json.loads((ROOT / 'work/ui/movies/MOV072/timed-layout.json').read_text('utf-8'))
    ui_folder = ROOT / 'work/output/movie-drafts/MOV072/captions-ui-02'
    ui_render = json.loads((ui_folder / 'render-report.json').read_text('utf-8'))
    ui_candidate = json.loads((ui_folder / 'sfd-candidate-report.json').read_text('utf-8'))
    ui_decoded = json.loads((ui_folder / 'decoded-comparison.json').read_text('utf-8'))
    assert ui_render['captured_ui']['recipe_sha256'] == digest(timed_path.read_bytes())
    assert ui_render['captured_ui']['label_count'] == 25 and ui_render['captured_ui']['label_frame_edits'] == 964
    assert ui_render['captured_ui']['UI_present_frames'] == ui_render['captured_ui']['source_index_matches'] == 134
    assert ui_decoded['exact_decoded_video_frames'] == 3084 and ui_decoded['decoded_pcm_identical_to_original_adx']
    assert digest((ROOT / ui_candidate['candidate']).read_bytes()) == ui_candidate['candidate_sha256'] == ui_decoded['candidate_sha256']
    assert digest((ROOT / ui_render['native_video']['path']).read_bytes()) == ui_candidate['video_sha256']
    assert digest((ROOT / ui_render['original_audio']['path']).read_bytes()) == ui_candidate['audio_sha256']
    assert ui_candidate['source_sha256'] == dense72['source_sha256']
    assert len(ui_decoded['contact_sheets']) == 5 and len(ui_decoded['witness_frames']) == 17
    ui_contacts = []
    for p in ui_decoded['contact_sheets']:
        data = (ROOT / p).read_bytes()
        previous = ROOT / p.replace('/captions-ui-02/', '/captions-ui-01/')
        assert data == previous.read_bytes(), 'Encoded contacts changed since visual review'
        ui_contacts.append({'path': p, 'sha256': digest(data), 'reviewed_identical_contact': str(previous.relative_to(ROOT)).replace('\\', '/')})
    title = ending_title()
    title_path = ROOT / 'work/translation/en/movies/MOV072-ending-title.en.json'
    assert title == json.loads(title_path.read_text('utf-8'))
    title_folder = ROOT / 'work/output/movie-drafts/MOV072/captions-ui-endtitle-01'
    title_render = json.loads((title_folder / 'render-report.json').read_text('utf-8'))
    title_candidate = json.loads((title_folder / 'sfd-candidate-report.json').read_text('utf-8'))
    title_decoded = json.loads((title_folder / 'decoded-comparison.json').read_text('utf-8'))
    assert title_render['ending_title']['recipe_sha256'] == digest(title_path.read_bytes())
    assert title_render['ending_title']['frames'] == title_render['ending_title']['source_index_matches'] == 123
    assert title_render['ending_title']['exact_static_witnesses'] == title['witness_frames']
    assert title_render['captured_ui']['recipe_sha256'] == digest(timed_path.read_bytes())
    assert digest((ROOT / title_candidate['candidate']).read_bytes()) == title_candidate['candidate_sha256'] == title_decoded['candidate_sha256']
    assert digest((ROOT / title_render['native_video']['path']).read_bytes()) == title_candidate['video_sha256']
    assert digest((ROOT / title_render['original_audio']['path']).read_bytes()) == title_candidate['audio_sha256']
    assert title_decoded['exact_decoded_video_frames'] == 3084 and title_decoded['decoded_pcm_identical_to_original_adx']
    assert len(title_decoded['contact_sheets']) == 7 and len(title_decoded['witness_frames']) == 25
    title_contacts = [{'path': p, 'sha256': digest((ROOT / p).read_bytes())} for p in title_decoded['contact_sheets']]
    sources = json.loads((ROOT / 'docs/movie-title-sources.json').read_text('utf-8'))
    assert sources['opening_frames_indexed'] == 181 and sources['demo_title_source_frames_indexed'] == 361
    for key in ('opening_index', 'demo_index'):
        assert digest((ROOT / sources[key]).read_bytes()) == sources[key + '_sha256']
    opening_contacts = [{'path': p, 'sha256': digest((ROOT / p).read_bytes())} for p in dense55['interval_contact_pages']]
    assert len(opening_contacts) == 11
    document = {
        'status': 'MOV072 English captions, captured UI and ending title encoded; initial/moving-art title and opening MOV055 title, game insertion/timing/live checks remain incomplete',
        'last_packaged_build': '0.1.22',
        'movies': 116, 'source_bytes': index['source_bytes'],
        'decoded_video_frames': 36123, 'initial_discovery_samples': 928,
        'initial_visual_review': 'All 15 eight-sample contact sheets reviewed across this thread. MOV072 contains visible Japanese; absence of text in other sampled frames does not establish absence throughout those streams.',
        'initial_contacts': contacts,
        'streams': [{'kind': k, 'codec': c, 'movies': count} for (k, c), count in sorted(streams.items())],
        'movie_index': 'work/ui/asset-audit/movies/movie-index.json',
        'MOV072': {
            'source_sha256': dense72['source_sha256'], 'frames': dense72['total_video_frames'],
            'denser_discovery_frames': 462,
            'interval_samples_reviewed': len([r for r in dense72['frames'] if r['index'] % 15 == 0]),
            'interval_contact_pages_reviewed': dense72['interval_contact_pages'],
            'consecutive_caption_frames_reviewed': 477,
            'consecutive_ranges': [[1530, 1935], [2630, 2700]],
            'consecutive_caption_contacts': consecutive['caption_contact_pages'],
            'caption_drafts': 13, 'movie_specific_wording_variants': 2,
            'timing': 'Each caption start/end checked against consecutive decoded frames and exact input PTS',
            'caption_recipe': 'work/translation/en/movies/MOV072.en.json',
            'subtitle_review_copy': 'work/translation/en/movies/MOV072.en.srt',
            'captured_UI_label_occurrences': 25,
            'initial_UI_terms_needing_width_review': sum(not r['width_fit_candidate'] for r in movie_ui['rows']),
            'UI_terms_needing_width_review': 0,
            'UI_recipe': 'work/translation/en/movies/MOV072-ui.en.json',
            'initial_UI_geometry': 'work/ui/movies/MOV072/layout.json',
            'UI_geometry': 'work/ui/movies/MOV072/timed-layout.json',
            'previews': [f'work/ui/movies/MOV072/english-caption-drafts/comparison-{i:02d}.png' for i in range(4)],
            'preview_scope': 'Static offline drafts using supplied bitmap at uniform 1/2 scale; wrapping preserves every English word, and pixels outside the declared caption rectangle are unchanged. All four comparison sheets visually inspected.',
            'title_logo_sequences': 2,
            'reading_speed': 'Original demo cuts are very fast, including captions under one second. English timing/presentation remains a review requirement.',
            'remaining': ['Initial 3D/moving-art title sequence; the plain-background ending title has an English candidate',
                          'Corresponding title sequence found in MOV055 also requires replacement',
                          'Independent meaning, full-motion and English caption reading-speed review',
                          'Frame-complete movie/content/audio audit',
                          'Game insertion and native playback/buffering/A-V synchronization verification'],
            'native_movie_translation_inserted': False,
            'captioned_movie_candidate': {
                'candidate': candidate['candidate'], 'sha256': candidate['candidate_sha256'],
                'software_decoded_frames': 3084, 'captioned_frames': 405, 'cues': 13,
                'original_audio': 'All 2531 audio packs and complete ADX payload remain exact; decoded PCM also matches',
                'preservation': candidate['preservation'],
                'scheduling': candidate['source_deadline_scheduling'],
                'encoded_contacts_reviewed': encoded_contacts,
                'visual_review_scope': 'All four encoded comparison sheets inspected: thirteen witness frames, not a full-motion review',
                'watchable_preview': render['watchable_preview'],
                'render_proof': str((draft_folder / 'render-report.json').relative_to(ROOT)).replace('\\', '/'),
                'container_proof': str((draft_folder / 'sfd-candidate-report.json').relative_to(ROOT)).replace('\\', '/'),
                'decoded_comparison': str((draft_folder / 'decoded-comparison.json').relative_to(ROOT)).replace('\\', '/'),
                'limitations': candidate['limitations'],
                'timing_note': 'Source contains nonmonotonic mux timestamps. Frame-index rendering resets output timestamps while preserving decoded frame order; native candidate approximates original 3006-tick frame timing.',
                'not_in_game_build': True,
            },
            'latest_captions_UI_candidate': {
                'candidate': ui_candidate['candidate'], 'sha256': ui_candidate['candidate_sha256'],
                'recipe': str(timed_path.relative_to(ROOT)).replace('\\', '/'),
                'recipe_sha256': digest(timed_path.read_bytes()),
                'source_frames_indexed': 326, 'source_UI_frames_present': 134,
                'timed_intervals': timed['intervals'], 'labels': 25, 'label_frame_edits': 964,
                'compact_labels': ['Acc.', 'Spirit Req.', 'Ht. Diff.'],
                'layout': 'One uniform half-source font scale; all fields fit. Full terms retained in en. Signed/numeric values and ON remain source pixels; small P marker moves right of the English weapon name.',
                'repairs': ['Expanded Cut-In erase bound after a remaining Japanese character was found in the first preview',
                            'Consecutive extraction now records source PTS before resetting output timestamps; no VFR frame loss'],
                'software_decoded_video_frames': 3084,
                'original_ADX_and_decoded_PCM': 'exact',
                'source_schedule_peak_compressed_bytes': ui_candidate['source_deadline_scheduling']['peak_compressed_bytes'],
                'encoded_contacts_reviewed': ui_contacts,
                'review_scope': 'Five contact sheets / 17 witness frames reviewed; final contacts byte-exact those reviewed in the preceding metadata-identical rendering',
                'watchable_preview': ui_render['watchable_preview'],
                'render_proof': str((ui_folder / 'render-report.json').relative_to(ROOT)).replace('\\', '/'),
                'container_proof': str((ui_folder / 'sfd-candidate-report.json').relative_to(ROOT)).replace('\\', '/'),
                'decoded_comparison': str((ui_folder / 'decoded-comparison.json').relative_to(ROOT)).replace('\\', '/'),
                'not_in_game_build': True, 'live_playback': 'pending',
            },
            'latest_caption_UI_ending_title_candidate': {
                'candidate': title_candidate['candidate'], 'sha256': title_candidate['candidate_sha256'],
                'ending_title_recipe': str(title_path.relative_to(ROOT)).replace('\\', '/'),
                'title': title['en'], 'ending_interval': [2961, 3084], 'ending_frames': 123,
                'source_index_matches': 123, 'design': 'Rebuilt English bitmap wordmark with uniform zoom and source-derived flash/fade; not original 3D mesh translation',
                'moving_mech_art': 'unchanged; its Japanese title remains pending',
                'software_decoded_video_frames': 3084, 'original_ADX_and_decoded_PCM': 'exact',
                'encoded_contacts_reviewed': title_contacts, 'review_scope': 'Seven contact sheets, 25 witness frames; complete movie motion/audio/design review remains pending',
                'watchable_preview': title_render['watchable_preview'],
                'render_proof': str((title_folder / 'render-report.json').relative_to(ROOT)).replace('\\', '/'),
                'container_proof': str((title_folder / 'sfd-candidate-report.json').relative_to(ROOT)).replace('\\', '/'),
                'decoded_comparison': str((title_folder / 'decoded-comparison.json').relative_to(ROOT)).replace('\\', '/'),
                'not_in_game_build': True, 'live_playback': 'pending',
            },
        },
        'MOV055': {
            'source_sha256': dense55['source_sha256'],
            'denser_discovery_frames': 471,
            'review': 'All eleven regular-interval sheets reviewed; Japanese title sequence found. Dense frame-complete and audio review remain pending.',
            'regular_interval_samples_reviewed': len([r for r in dense55['frames'] if r['index'] % 15 == 0]),
            'regular_interval_contacts_reviewed': opening_contacts,
            'Japanese_title_found': True,
            'title_witnesses': [285, 300, 360, 375, 390, 405],
            'consecutive_title_frames_indexed': 181,
            'consecutive_title_index': sources['opening_index'],
            'shared_footage_comparison': 'docs/movie-title-sources.json',
            'comparison_scope': sources['matching_scope'],
            'translation_inserted': False,
            'index': 'work/ui/asset-audit/movies/MOV055/dense/index.json',
        },
        'limits': ['Sampled discovery does not prove frame-complete caption coverage',
                   'Only the specified MOV072 caption intervals have consecutive-frame review',
                   'Software MPEG-1/SFD encoding and exact original audio pass; audio content, movie selection, timing and native playback remain unverified',
                   'The English SRT and static previews do not change the game or establish reinsertion',
                   'Japanese transcription remains local in ignored work/source; English export contains no Japanese prose'],
        'story_library_draft_credit': 0,
    }
    inserted_path = ROOT / 'docs/movie-insertion.json'
    if inserted_path.exists():
        inserted = json.loads(inserted_path.read_text('utf-8'))
        assert inserted['version'] in ('0.1.23', '0.1.24')
        if inserted['version'] == '0.1.23':
            assert inserted['movie_sha256'] == title_candidate['candidate_sha256']
            assert inserted['packaging']['reextracted_files'] == 'all 6 exact'
        else:
            current_intro = json.loads((ROOT / 'docs/movie-intro-title.json').read_text('utf-8'))
            demo_intro = next(r for r in current_intro['movies'] if r['movie'] == 'MOV072.SFD')
            assert inserted['movie_sha256'] == demo_intro['sha256']
            assert inserted['packaging']['reextracted_files'] == 'all 7 exact'
        document['last_packaged_build'] = inserted['version']
        document['local_movie_insertion'] = {'version': inserted['version'], 'disc': inserted['disc'],
                                               'scope': inserted['status'], 'live_playback': 'pending'}
        document['status'] = inserted['status']
        document['MOV072']['native_movie_translation_inserted'] = True
        document['MOV072']['native_movie_playback_verified'] = False
        document['MOV072']['remaining'] = [r.replace('Game insertion and native playback/buffering/A-V synchronization verification',
                                                     'Native playback/buffering/A-V synchronization verification') for r in document['MOV072']['remaining']]
        document['MOV072']['latest_caption_UI_ending_title_candidate'].update(not_in_game_build=False,
                                                                              packaged_build='0.1.23', disc='work/output/0.1.23/disc/Rayblade English Test 0.1.23.gdi')
        if inserted['version'] == '0.1.24':
            document['MOV055'].update(translation_inserted=True, native_movie_playback_verified=False)
            document['MOV072']['remaining'][0] = 'Title over moving mech remains Japanese; English intro and ending inserted into 0.1.24'
    intro_path = ROOT / 'docs/movie-intro-title.json'
    if intro_path.exists():
        intro_doc = json.loads(intro_path.read_text('utf-8'))
        assert intro_doc['English_intro_frames_total'] == 64 and intro_doc['complete_decoded_video_frames'] == 4924
        for row in intro_doc['movies']:
            assert digest((ROOT / row['candidate']).read_bytes()) == row['sha256']
            document[row['movie'][:6]]['latest_intro_title_candidate'] = row
        document['movie_intro_title_candidates'] = intro_doc
    background_path = ROOT / 'docs/movie-title-background.json'
    if background_path.exists():
        background = json.loads(background_path.read_text('utf-8'))
        assert digest((ROOT / background['analysis']).read_bytes()) == background['analysis_sha256']
        document['moving_title_artwork'] = background
    print('Verified: 13 captions, 25 captured UI labels and 123 English ending-title frames in a 3084-frame SFD candidate; original ADX/PCM exact. MOV055 title also found; initial/moving titles, insertion and live timing remain pending.')
    if not args.write:
        print('DRY RUN: no documentation changed')
        return
    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    save(ROOT / 'docs/movie-text-audit.json', document)
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status['movie_text_audit'] = document
    save(status_path, status)


if __name__ == '__main__':
    main()
