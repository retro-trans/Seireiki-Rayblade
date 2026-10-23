"""Record an actual source-comparison pass over library rows 0..79.

Dry run first. Historical draft/layout recipes remain immutable. Reviewed
wording corrections are explicit pending overrides for the next game build.
"""
import argparse
import json
import re

from build_bitmap_font import ROOT, digest
from prepare_library_translation import fingerprint

OUT = ROOT / 'work/translation/en/library/review'
FIX_ID = 'library.character.004.s00.l02'
BEFORE = 'A childhood friend, glasses, long straight black hair, quiet devotion...'
AFTER = 'A childhood friend, glasses, straight black hair, quiet devotion...'

NOTE = '''## Working translation — first library meaning re-review and current-build boot

- Re-read library rows 0..79 against the Japanese, using rows 80..86 to finish Kasumi's profile context: 80 rows in the slice, 87 examined. The record fingerprints every source and English row separately. Checked all original unlock sections, Touya's childhood/parents/arrival, Ai's uncertain feelings, Ymir's title/family/grief and Kasumi's traits. This is an editorial second pass, not an independent reviewer or verification of all 1,549 content rows.
- Found one unsupported detail: Kasumi's source specifies straight black hair, while the draft adds long. Prepared the exact one-word removal as a pending English override. Other wording remains unchanged. Retained the source's differing descriptions of Touya's parents' deaths rather than silently reconciling the profiles. Explicitly recorded the deliberate profile-heading/catalogue fragments; no new pronoun or family-identity guesses. Historical source/draft/layout recipes and game bytes remain unchanged; the wording fix still needs integration and layout verification.
- Added the 0.1.37 disc folder to the existing Flycast content list and booted its filtered game-list entry. Observed the Winkysoft screen and moving opening footage; saved a runtime witness. Confirmed existing keyboard bindings (Start=Return, A=X, B=C), but automated game-button input did not reliably skip the movie or reach dialogue. No menu-fit, font-smoothness, title-subtitle or library-navigation live pass claimed. Latest playable build remains 0.1.37; no release.

'''


def prepare():
    draft_path = ROOT / 'work/translation/en/library/library.json'
    rows = json.loads(draft_path.read_text('utf-8'))
    source = json.loads((ROOT / 'work/source/library/rows.json').read_text('utf-8'))
    assert len(rows) == len(source) == 1616
    assert all(a['id'] == b['id'] and a['source_sha256'] == fingerprint(b)
               for a, b in zip(rows, source))
    assert rows[72]['id'] == FIX_ID and rows[72]['en'] == BEFORE
    assert rows[0]['id'] == 'library.character.001.s00.l00'
    assert rows[79]['id'] == 'library.character.004.s00.l09'
    assert rows[86]['id'] == 'library.character.004.s02.l01'
    fragments = {0: 'Descriptive profile-opening noun phrase, matching the source form',
                 19: 'Pilot title under the named profile; deliberate heading fragment',
                 21: 'Pilot title under the named profile; deliberate heading fragment',
                 24: 'Appositive character description following an explicit she sentence',
                 70: 'Childhood-friend appositive, followed by an explicit she sentence',
                 72: 'Deliberate list of character tropes, completed by the next row'}
    reviewed = []
    for n, row in enumerate(rows[:80]):
        reviewed.append({'id': row['id'], 'source_sha256': row['source_sha256'],
                         'prior_en_sha256': digest(row['en'].encode('utf-8')),
                         'conditions': row['conditions'],
                         'result': 'wording_correction_pending' if n == 72 else
                                   'structural_empty_retained' if not row['ja'] else 'retained_after_source_comparison',
                         **({'intentional_fragment': fragments[n]} if n in fragments else {})})
    correction = {'id': FIX_ID, 'source_sha256': rows[72]['source_sha256'],
                  'prior_en_sha256': digest(BEFORE.encode('utf-8')), 'prior_en': BEFORE,
                  'en': AFTER, 'reason': 'The source specifies straight black hair without specifying length; remove the unsupported long',
                  'integration': 'pending; not inserted in build 0.1.37'}
    review = {'format': 1, 'review_kind': 'Editorial second pass against original source; not independent review',
              'slice_start': 0, 'rows_in_slice': 80, 'rows_examined': 87,
              'content_rows_in_slice': sum(bool(r['ja']) for r in rows[:80]),
              'first_id': rows[0]['id'], 'last_id': rows[79]['id'],
              'context_last_id': rows[86]['id'],
              'source_corpus_sha256': digest(json.dumps([fingerprint(r) for r in source]).encode()),
              'draft_file_sha256': digest(draft_path.read_bytes()),
              'context': 'Complete Touya, Ai and Ymir profiles, plus Kasumi profile including its continuation after the slice',
              'decisions': ['Retain source section/unlock boundaries and one original row per draft row',
                            'Retain glossary spellings and title terminology; no new name romanization',
                            'Ai recognition of her feelings remains explicitly uncertain',
                            'Preserve different source descriptions of the parents deaths across Touya and Kasumi profiles',
                            'Ymir family revelations are gated source statements; do not harmonize or infer further identities',
                            'Deliberate heading/catalogue fragments are flagged per row; ordinary prose retains explicit subjects',
                            'One unsupported hair-length adjective removed in pending override; other wording retained'],
              'rows': reviewed, 'corrections': [correction],
              'pending': ['Integrate the reviewed correction and recheck affected paragraph layout',
                          'Review remaining library rows and obtain independent meaning/name review',
                          'Actual library loading/navigation, unlocked-section selection and live appearance']}
    overrides = {'format': 1, 'base_game_build': '0.1.37',
                 'status': 'Reviewed English wording; pending game integration', 'rows': {FIX_ID: correction}}
    screenshot = ROOT / 'work/ui/0.1.37/boot-runtime.jpg'
    assert screenshot.read_bytes()[:3] == b'\xff\xd8\xff'
    live = {'build_selected_in_UI': '0.1.37',
            'selection_evidence': 'Added exact work/output/0.1.37/disc content folder; filter 0.1.37 showed its two cue/gdi entries; launched second entry',
            'loaded_memory_identity': 'Not independently inspected; selection is UI evidence only',
            'screenshot': str(screenshot.relative_to(ROOT)).replace('\\', '/'),
            'screenshot_sha256': digest(screenshot.read_bytes()),
            'observed': ['Winkysoft startup screen', 'Moving opening movie footage'],
            'input': {'observed_existing_bindings': {'Start': 'Return', 'A': 'X', 'B': 'C', 'menu': 'Tab'},
                      'result': 'Automated controller-key input unreliable; no successful skip/new-game sequence established'},
            'configuration_change': 'Added latest disc folder to existing Flycast content paths; existing paths/bindings retained',
            'live_validation': {'boot_and_opening_movie_observed': True, 'dialogue': False,
                                'font_smoothing': False, 'menus': False, 'library': False,
                                'title_subtitle': False, 'save_load': False},
            'game_files_changed': False, 'release_created': False}
    summary = {'review': 'work/translation/en/library/review/meaning-0000.en.json',
               'review_kind': review['review_kind'], 'rows_in_slice': 80,
               'source_rows_examined': 87, 'content_rows_reviewed': review['content_rows_in_slice'],
               'total_content_rows': 1549, 'wording_corrections_pending': 1,
               'remaining': review['pending'], 'game_build_changed': False, 'current_game_build': '0.1.37'}
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    assert status['version'] == '0.1.37'
    status['library']['editorial_second_pass'] = summary
    status['checks']['current_build_boot_observation'] = {
        'evidence': 'work/ui/0.1.37/live-validation.json', 'scope': 'UI-selected boot/opening movie only; dialogue/font/menu/library live checks pending'}
    updates = [(OUT / 'meaning-0000.en.json', review),
               (OUT / 'meaning-overrides.en.json', overrides),
               (ROOT / 'docs/library-meaning-review.json', summary),
               (ROOT / 'work/ui/0.1.37/live-validation.json', live), (status_path, status)]
    for _, content in updates[:4]:
        assert not re.search(r'[\u3040-\u30ff\u3400-\u9fff]', json.dumps(content, ensure_ascii=False))
    return updates


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    updates = prepare()
    print('Reviewed: 80 rows in slice; 87 examined;', updates[0][1]['content_rows_in_slice'], 'content rows.')
    print('Pending correction:', BEFORE, '=>', AFTER)
    print('Live: boot/opening footage only; automated input unreliable; no dialogue/menu/font pass.')
    if not args.write:
        print('DRY RUN: five metadata/review updates plus change log; no draft/game files changed.')
        return
    for path, content in updates:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2) + '\n', 'utf-8')
    path = ROOT / 'CHANGELOG.md'
    old = path.read_text('utf-8')
    if NOTE.splitlines()[0] not in old:
        path.write_text(old.replace('# Change log\n\n', '# Change log\n\n' + NOTE, 1), 'utf-8')
    print('Wrote checked review and limited live evidence; current game build unchanged.')


if __name__ == '__main__':
    main()
