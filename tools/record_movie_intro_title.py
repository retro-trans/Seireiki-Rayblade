"""Record bounded English intro-title candidates for two movies. Dry first.

These movie work products are not yet part of a new disc build. Keep 0.1.23's
packaged coverage and pending native-playback checks separate.
"""
import argparse
import json

from audit_sfd_container import inspect
from build_bitmap_font import ROOT, digest
from prepare_movie_intro_title import prepare, recipe_path


CANDIDATES = {
    'MOV055.SFD': ('work/output/movie-drafts/MOV055/intro-title-01', 1840, 2, 8),
    'MOV072.SFD': ('work/output/movie-drafts/MOV072/captions-ui-titles-01', 3084, 9, 33),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    movies = []
    for movie, (folder, count, pages, witnesses) in CANDIDATES.items():
        recipe = prepare(movie)
        path = recipe_path(movie)
        assert recipe == json.loads(path.read_text('utf-8'))
        folder = ROOT / folder
        render = json.loads((folder / 'render-report.json').read_text('utf-8'))
        mux = json.loads((folder / 'sfd-candidate-report.json').read_text('utf-8'))
        decoded = json.loads((folder / 'decoded-comparison.json').read_text('utf-8'))
        assert render['intro_title']['recipe_sha256'] == digest(path.read_bytes())
        assert render['intro_title']['frames'] == render['intro_title']['source_index_matches'] == 32
        assert render['intro_title']['exact_static_witnesses'] == [r['frame'] for r in recipe['witnesses']]
        assert render['frame_count'] == decoded['exact_decoded_video_frames'] == mux['coded_frames'] == count
        assert decoded['decoded_pcm_identical_to_original_adx'] and decoded['software_decode_errors'] == 0
        assert len(decoded['contact_sheets']) == pages and len(decoded['witness_frames']) == witnesses
        candidate = ROOT / mux['candidate']
        raw = candidate.read_bytes()
        assert digest(raw) == mux['candidate_sha256'] == decoded['candidate_sha256']
        assert digest((ROOT / render['native_video']['path']).read_bytes()) == mux['video_sha256']
        assert digest((ROOT / render['original_audio']['path']).read_bytes()) == mux['audio_sha256']
        original = (ROOT / 'work/source/movies' / movie).read_bytes()
        assert digest(original) == recipe['source_sha256'] == mux['source_sha256']
        _, _, source_streams = inspect(original)
        _, _, target_streams = inspect(raw)
        assert source_streams[0xc0] == target_streams[0xc0]
        assert digest(target_streams[0xe0]) == mux['video_sha256']
        contacts = [{'path': p, 'sha256': digest((ROOT / p).read_bytes())} for p in decoded['contact_sheets']]
        movies.append({'movie': movie, 'candidate': mux['candidate'], 'sha256': mux['candidate_sha256'],
                       'bytes': len(raw), 'source_sha256': mux['source_sha256'],
                       'recipe': str(path.relative_to(ROOT)).replace('\\', '/'), 'recipe_sha256': digest(path.read_bytes()),
                       'English_intro_interval': [recipe['start_frame'], recipe['end_frame_exclusive']],
                       'English_intro_frames': 32, 'matched_indexed_source_frames': 32,
                       'source_boundary_witnesses': recipe['boundary_evidence'],
                       'software_decoded_frames': count, 'original_ADX_and_decoded_PCM': 'exact',
                       'source_schedule_occupancy': mux['source_deadline_scheduling'],
                       'watchable_preview': render['watchable_preview'],
                       'encoded_contacts_reviewed': contacts, 'encoded_witness_frames': witnesses,
                       'render_proof': str((folder / 'render-report.json').relative_to(ROOT)).replace('\\', '/'),
                       'mux_proof': str((folder / 'sfd-candidate-report.json').relative_to(ROOT)).replace('\\', '/'),
                       'decoded_proof': str((folder / 'decoded-comparison.json').relative_to(ROOT)).replace('\\', '/'),
                       'moving_art_title': 'Original Japanese remains; surrounding moving artwork retained before encoding',
                       'in_game_build': False, 'native_playback': 'pending'})
    doc = {'status': 'Two English intro-title movie candidates encoded and software-verified; not yet in a new disc build',
           'last_packaged_build': '0.1.23', 'movies': movies,
           'English_intro_frames_total': 64, 'complete_decoded_video_frames': 4924,
           'encoded_contacts_reviewed': 11, 'encoded_witness_frames': 41,
           'animation': 'Shared rebuilt 2D English zoom/white-blue logo/rays/bloom, not the original 3D mesh',
           'texture_dimensions': '320x192 output; largest intermediate 960x576; one uniform scale for complete wordmark',
           'preservation_scope': 'Pre-encoding source RGB is retained outside each intro interval; re-encoding the complete video is lossy',
           'remaining': ['Title over moving mech artwork remains Japanese in both movies',
                         'Whole-motion/design and source-content/audio review',
                         'New disc insertion and native startup/completion/sync/skipping/looping checks',
                         'Existing whole-game translation/review and held passages remain incomplete'],
           'story_library_draft_credit': 0, 'release': False}
    insertion_path = ROOT / 'docs/movie-insertion.json'
    if insertion_path.exists():
        insertion = json.loads(insertion_path.read_text('utf-8'))
        if insertion['version'] == '0.1.24':
            packaged = {r['movie']: r for r in insertion['movies']}
            for row in movies:
                assert row['sha256'] == packaged[row['movie']]['candidate_sha256']
                row.update(in_game_build=True, packaged_build='0.1.24', disc=insertion['disc'])
            doc.update(status='Two English intro-title candidates inserted into local test disc 0.1.24; native playback and moving-art treatment pending',
                       last_packaged_build='0.1.24')
    print('Verified: two full movie candidates, 4924 decoded frames, 64 English intro-title frames, exact original ADX/PCM; 41 encoded witnesses reviewed. No new game build.')
    if not args.write:
        print('DRY RUN: no documentation changed')
        return
    def save(path, data):
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')
    save(ROOT / 'docs/movie-intro-title.json', doc)
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status['movie_intro_title_candidates'] = doc
    movie_path = ROOT / 'docs/movie-text-audit.json'
    audit = json.loads(movie_path.read_text('utf-8'))
    audit['movie_intro_title_candidates'] = doc
    for row in movies:
        audit[row['movie'][:6]]['latest_intro_title_candidate'] = row
    save(movie_path, audit)
    status['movie_text_audit'] = audit
    save(status_path, status)


if __name__ == '__main__':
    main()
