"""Record verified 0.1.38 packaging and the captured corruption fix. Dry first."""
import argparse
import copy
import json

from afs_layout import require_native_layouts
from build_bitmap_font import ROOT, digest
from build_ordered_archive_patch import OUT, PRIOR, VERSION, compose


NOTE = '''## 0.1.38 — fix archive loading corruption after New Game

- Reproduced the reported 0.1.37 failure from read-only captured game RAM. The original SDK's compact directory uses a first sector followed by cumulative rounded member lengths, rather than every absolute AFS offset. Its entire 777-member ADV00 length list matches the captured native table. The English letter had been moved out of sequence and enlarged, so member 380 was fetched at byte 22,067,200 instead of 22,063,104. Reversing the one native pointer relocation makes all 80 captured bad bytes match that wrong archive location exactly. Pixel data was interpreted as NJTL metadata and the resulting relocation walk added 0x8c82f2e8 at twelve-byte intervals through game memory. Reversing that pattern in an analysis copy restores both scenario hooks, the valid 0x8cd55700 English heap pointer and the 128 KiB allocation literal. No running process memory was changed.
- Audited all eight modified AFS archives and repaired six incompatible layouts: ADV00, ALBUM, EFFECT, WMAP, STAFF and D_SYSTEM. All 1,525 member payloads, member IDs, translations, pictures and compressed streams remain exact 0.1.37. WIN00 and D_SCE already satisfy the native cumulative-sector layout and remain byte-exact, as do the executable, normal font and other eight unaffected game payloads. WMAP/ALBUM use two additional sectors of zero prefix to retain their original file extents; no content was shortened or recompressed.
- Executed actual SDK validation, directory traversal and offset/length calculation for all 2,063 members in eight archives: 2,869,127 SH-4 instructions including the captured failing lookup. Corrected physical offsets, padded read bounds, guards, registers and source buffers pass. Only the 40-byte file-info copy endpoint uses a bounded fixture. D_SYSTEM's SDK slot is a generic fixture; its actual registration/use remains unproved. This is not a live fresh-game, graphics or full-playthrough result.
- Packaged local build 0.1.38 with 28,736 sector substitutions over 0.1.37 and 56,409 locations changed from original. All fourteen payloads re-extract exactly, changed-sector EDC/ECC and the complete 1,188,856,032-byte track comparison pass, ISO allocations remain unchanged, and twenty-six historical native proof identities are retained under their actual tested identities. Added a cumulative-sector compatibility gate for every archive in builds starting with 0.1.38, preventing this packaging error from recurring.
- Test the new GDI from a fresh boot, choose New Game and continue past the memory screen to first dialogue. A save state from the corrupted run contains overwritten code and must not be resumed for this check; VMU save files are unchanged. Computer control was not resumed. Independent meaning, later asset loading/navigation, save/load, font appearance and full-game translation review remain unfinished. No new translation credit, original-dump/prior-build changes or release.

'''


def read(path):
    return json.loads(path.read_text('utf-8'))


def record():
    out = ROOT / 'work/output' / VERSION
    previous = read(ROOT / 'work/output' / PRIOR / 'english-disc-report.json')
    report = read(out / 'english-disc-report.json')
    targets, component = compose()
    proof_bytes = (OUT / 'native-test.json').read_bytes()
    proof = json.loads(proof_bytes)
    assert report['version'] == VERSION and report['source_build'] == PRIOR
    assert report['ordered_archives_component'] == component
    assert report['ordered_archives_native_proof'] == proof
    assert report['ordered_archives_proof_sha256'] == digest(proof_bytes)
    assert report['new_changed_sectors'] == 28736 and report['total_changed_sector_locations_from_original'] == 56409
    assert report['validation']['reextracted_files'] == 'all 14 exact'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['unrelated_ISO_entries'] == 'unchanged'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert proof['native_lookup_cases'] == 2063 and proof['native_instructions'] == 2869127
    all_files = {}
    for name, row in report['files'].items():
        path = out / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
        raw = path.read_bytes()
        assert len(raw) == row['size'] and digest(raw) == row['sha256']
        if name in targets:
            assert raw == targets[name]
        else:
            assert row == previous['files'][name]
        all_files[name] = raw
    assert require_native_layouts(all_files) == report['native_archive_layout_validation']
    assert len(report['historical_native_evidence']) == 26
    for row in report['historical_native_evidence']:
        raw = (out / row['file']).read_bytes()
        assert digest(raw) == row['sha256'] and json.loads(raw)['executable_sha256'] == row['executable_sha256']
    assert (out / 'ordered-archives-native-test.json').read_bytes() == proof_bytes
    assert read(out / 'ordered-archives-component-report.json') == component
    disc_rel = f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi'
    assert (ROOT / disc_rel).is_file()
    repaired = {name: {'current_build': VERSION, 'archive_sha256': report['files'][name]['sha256'],
                       'member_payloads_unchanged_from': PRIOR, 'member_count': row['members'],
                       'native_lookups': 'all offsets/sector lengths match physical layout',
                       'evidence': f'work/output/{VERSION}/ordered-archives-native-test.json'}
                for name, row in component['archives'].items()}
    summary = {'version': VERSION, 'source_build': PRIOR,
               'status': 'Captured wrong read reproduced exactly and cumulative-sector layouts repaired; user fresh New Game test pending',
               'disc': disc_rel, 'archives': repaired,
               'unchanged_compatible_archives': component['unchanged_compatible_archives'],
               'unchanged_member_payloads_in_repacked_archives': 1525,
               'native_lookup_cases': 2063, 'native_instructions': proof['native_instructions'],
               'native_proof': f'work/output/{VERSION}/ordered-archives-native-test.json',
               'native_proof_sha256': digest(proof_bytes),
               'captured_failure': proof['captured_failure_reproduction'],
               'new_sector_substitutions': 28736, 'changed_locations_from_original': 56409,
               'validation': report['validation'], 'live_new_game': 'pending user test; computer control not resumed',
               'normal_text_font_changed': False, 'story_library_draft_credit': 0, 'release': False}
    failure = {'affected_build_observed': PRIOR, 'repair_build': VERSION,
               'trigger': 'New Game, then pass the memory screen',
               'screenshot': 'work/ui/0.1.37/new-game-corruption-01/reported-screen.jpg',
               'runtime_probe': 'work/ui/0.1.37/new-game-corruption-01/runtime.json',
               'raw_game_RAM': 'Ignored local work/source/runtime/0.1.37-new-game-corruption-01.ram',
               'cause': 'Compact cumulative-sector SDK lookup disagreed with the edited AFS physical layout; wrong image bytes were interpreted as pointer-bearing metadata',
               'evidence': proof['captured_failure_reproduction'], 'repair': 'docs/native-archive-layout.json',
               'validation_limits': proof['limits']}
    status_path = ROOT / 'docs/translation-status.json'
    status = read(status_path)
    assert status['version'] in (PRIOR, VERSION)
    status.update(version=VERSION,
                  stage='Native archive loading corruption repaired and local 0.1.38 packaged; user fresh New Game test and full translation review pending',
                  latest_archive_layout_build=summary, latest_runtime_failure=failure)
    status['checks']['native_compact_archive_layouts'] = report['native_archive_layout_validation']
    status['test_disc'].update(version=VERSION, source_build=PRIOR, path=disc_rel,
                              kind=report['kind'], changed_sectors=56409, new_changed_sectors=28736,
                              validation=report['validation'], pending=report['pending'])
    keys = {'WMAP.AFS': 'worldmap_sha256', 'STAFF.AFS': 'credits_sha256',
            'ADV00.AFS': 'ADV00_sha256', 'ALBUM.AFS': 'ALBUM_sha256',
            'EFFECT.AFS': 'EFFECT_sha256', 'D_SYSTEM.AFS': 'D_SYSTEM_sha256'}
    for name, key in keys.items():
        status['test_disc'][key] = report['files'][name]['sha256']
    status['test_disc'].pop('album_caption_readings_delta_sectors', None)
    gate = 'Fresh-boot 0.1.38 New Game past the memory screen and confirm first dialogue'
    if gate not in status['remaining']:
        status['remaining'].insert(0, gate)
    manifest_path = out / 'font4x-patch.json'
    manifest = read(manifest_path)
    assert manifest['version'] == VERSION
    manifest['current_payload_identities'] = report['files']
    manifest['historical_component_reports'] = 'Retain actual tested archive identities; current archive byte identities are listed separately. All member payloads remain exact 0.1.37.'
    updates = [(ROOT / 'docs/native-archive-layout.json', summary),
               (ROOT / 'docs/new-game-corruption.json', failure), (status_path, status), (manifest_path, manifest)]
    docs = {'WMAP.AFS': ['worldmap-labels'], 'STAFF.AFS': ['staff-credits'],
            'ADV00.AFS': ['story-images'], 'ALBUM.AFS': ['album-captions', 'album-pictures'],
            'EFFECT.AFS': ['effect-ui'], 'D_SYSTEM.AFS': ['system-profiles']}
    for name, stems in docs.items():
        for stem in stems:
            path = ROOT / 'docs' / (stem + '.json')
            data = read(path)
            data['current_archive_layout'] = repaired[name]
            data['archive_identity_note'] = 'Earlier archive hashes/proofs remain historical payload-origin evidence; current layout identity above supersedes file placement only.'
            updates.append((path, data))
    return updates, summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    updates, summary = record()
    print('PASS: complete 0.1.38 packaging, 14 payload hashes, eight native-compatible archives, 26 historical proofs.')
    print('Disc:', summary['disc'])
    if not args.write:
        print('DRY RUN:', len(updates), 'metadata updates and change log; no files written.')
        return
    for path, value in updates:
        path.write_text(json.dumps(value, indent=2) + '\n', 'utf-8')
    changes = ROOT / 'CHANGELOG.md'
    old = changes.read_text('utf-8')
    if NOTE.splitlines()[0] not in old:
        changes.write_text(old.replace('# Change log\n\n', '# Change log\n\n' + NOTE, 1), 'utf-8')
    print('Recorded the repair build, current identities and changelog; live user test remains pending.')


if __name__ == '__main__':
    main()
