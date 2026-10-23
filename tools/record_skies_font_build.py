"""Record the verified 0.1.39 font port, preference and changelog. Dry first."""
import argparse
import json

from build_skies_font_patch import ROOT, VERSION, PRIOR, digest
from afs_layout import require_native_layouts
from build_antialias_font import font_bytes

NOTE = '''## 0.1.39 — port the original Skies of Arcadia Latin font

- Replaced both normal Latin font banks with the original Skies of Arcadia USA Dreamcast pixels, decoded from the user's local disc. Preserved every original coverage value (0/85/187/255), using uniform 1x small and 2x medium repeats, a consistent baseline and measured variable advances. Removed inferred outlines from normal Latin text; no individual letter stretching. Five protected non-ASCII marks retain their preceding masks. The existing renderer, bilinear filtering, allocation budget and <=1024 texture cap remain unchanged; no emulator texture replacement.
- Rewrapped library paragraphs for the wider font, changing only 2,426 space/newline separator bytes while retaining all wording, conditions, metadata and decoded size. Rewrapped eight settings help paragraphs without dropping words. Narrow display fields use Counters, SP, PR, Hit and Ht Dif; completed-chapter strips use Clear and omit decorative title quotes while keeping every complete chapter title. Full terms remain in translation/glossary records. The names stream has twelve zero tail bytes to retain its existing 33,944-byte ISO extent.
- Passed 397 source-pixel native raster cases, all 50,273 story commands/123,041 retained boundaries (maximum 197 of 236 pen pixels), 166 native inline-control comparisons, 145 native UI cases, both actual PRS decodes, 90 SDK archive lookups, and 853 library parser pages/1,028 none-or-all unlock filter cases across 257 physical records. All 1,767 nonempty library lines are parsed in both viewer layouts. Guard/ABI checks pass. Intermediate unlock combinations, actual GPU appearance and full-game testing remain separate; external fixtures retain their documented scope.
- Packaged a local 0.1.39 test disc with 75 sector substitutions over 0.1.38. All fourteen game payloads re-extract exactly; changed-sector EDC/ECC, unchanged ISO allocations and complete 1,188,856,032-byte track comparison pass. Twelve other game payloads, including the executable and story archive, remain exact 0.1.38; all 88 other WIN00 members and 27 historical proof identities are preserved. The cumulative-sector archive compatibility gate passes.
- Fresh-boot the new GDI for testing; emulator save states can retain the old font in RAM. Live font appearance across dialogue/battles/library/menus remains pending. No new story/library translation or independent meaning-review credit, public release, original-disc changes or prior-build replacement.

'''


def read(path):
    return json.loads(path.read_text('utf-8'))


def record():
    out = ROOT / 'work/output' / VERSION
    report = read(out / 'english-disc-report.json')
    previous = read(ROOT / 'work/output' / PRIOR / 'english-disc-report.json')
    proof_raw = (out / 'skies-font-native-test.json').read_bytes()
    proof = json.loads(proof_raw)
    inline_raw = (out / 'skies-font-inline-native-test.json').read_bytes()
    inline = json.loads(inline_raw)
    component = read(out / 'skies-font-component-report.json')
    assert report['skies_font_proof_sha256'] == digest(proof_raw)
    assert report['skies_font_inline_proof_sha256'] == digest(inline_raw)
    assert report['skies_font_component'] == component and report['skies_font_native_proof'] == proof
    assert report['validation']['reextracted_files'] == 'all 14 exact'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['new_changed_sectors'] == 75 and len(report['historical_native_evidence']) == 27
    files = {}
    for name, row in report['files'].items():
        path = out / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
        raw = path.read_bytes()
        assert len(raw) == row['size'] and digest(raw) == row['sha256']
        if name not in ('WIN00.AFS', 'D_NAMES.BIN'):
            assert row == previous['files'][name]
        files[name] = raw
    assert require_native_layouts(files) == report['native_archive_layout_validation']
    _, font = font_bytes(files['WIN00.AFS'])
    assert digest(font) == component['target_font_sha256'] == proof['font_sha256'] == inline['font_sha256']
    assert proof['executable_sha256'] == digest(files['1ST_READ.BIN']) == inline['executable_sha256']
    assert inline['archive_sha256'] == digest(files['D_SCE.AFS'])
    assert proof['names_packed_sha256'] == digest(files['D_NAMES.BIN'])
    for row in report['historical_native_evidence']:
        raw = (out / row['file']).read_bytes()
        assert digest(raw) == row['sha256'] and json.loads(raw)['executable_sha256'] == row['executable_sha256']
    manifest = read(out / 'font4x-patch.json')
    assert manifest['version'] == VERSION and manifest['current_payload_identities'] == report['files']
    assert manifest['skies_font']['font_sha256'] == digest(font)
    disc = f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi'
    assert (ROOT / disc).is_file()
    summary = {'version': VERSION, 'source_build': PRIOR,
        'status': 'Original Skies Latin pixels integrated; native raster/layout/loader checks pass; live appearance pending',
        'disc': disc, 'font_sha256': digest(font), 'archive_sha256': digest(files['WIN00.AFS']),
        'executable_sha256': digest(files['1ST_READ.BIN']),
        'font_source': 'Original embedded Latin VQ font in E:/Games/Skies of Arcadia (USA) (Disc 1).cue',
        'source_skies_executable_sha256': component['source_skies_executable_sha256'],
        'method': component['method'], 'coverage_levels': component['coverage_levels'],
        'glyphs_per_bank': 95, 'protected_symbols': 5, 'variable_width': True,
        'emulator_texture_replacement': False, 'maximum_font_texture_dimension': 1024,
        'native_proof': f'work/output/{VERSION}/skies-font-native-test.json',
        'native_proof_sha256': digest(proof_raw), 'native_results': proof,
        'inline_proof': f'work/output/{VERSION}/skies-font-inline-native-test.json', 'inline_results': inline,
        'preview': f'work/output/{VERSION}/skies-font-font-preview.png',
        'settings_preview': f'work/output/{VERSION}/skies-font-settings-preview.png',
        'UI_recipe': f'work/output/{VERSION}/ui-layouts.en.json',
        'library_recipe': f'work/output/{VERSION}/library-layouts.en.json',
        'sector_substitutions': report['new_changed_sectors'],
        'changed_locations_from_original': report['total_changed_sector_locations_from_original'],
        'validation': report['validation'], 'translation_credit': 0, 'release': False}
    status = read(ROOT / 'docs/translation-status.json')
    status.update(version=VERSION, stage='Original Skies Latin font port packaged locally; live font testing and full translation review pending')
    status['latest_font_build'] = summary
    status['latest_skies_font_build'] = summary
    status['latest_font_outline_build']['superseded_by'] = VERSION
    test = status['test_disc']
    test.update(version=VERSION, kind=report['kind'], changed_sectors=report['total_changed_sector_locations_from_original'],
                validation=report['validation'], pending=report['pending'])
    test['disc'] = disc
    test['names'].update(decoded_size=len((out / 'text/D_NAMES.en.dec.bin').read_bytes()),
                         compressed_stream_bytes=component['names_compressed_stream_bytes'],
                         zero_tail_bytes=component['names_file_zero_tail_bytes'])
    status['latest_ui_build'] = {'version': VERSION, 'native_cases': proof['native_UI_cases'],
        'font_sha256': digest(font), 'native_proof': summary['native_proof'],
        'status': 'Compact labels and all eight help paragraphs verified with original Skies font; live pending'}
    status['latest_library_build'] = {'version': VERSION, 'content_source_build': '0.1.18',
        'meaning_changes': 0, 'font_sha256': digest(font), 'library_sha256': proof['library_sha256'],
        'nonempty_lines': 1767, 'native_line_occurrences': 3534, 'native_proof': summary['native_proof'],
        'status': 'Wording unchanged; paragraphs rewrapped and native parsing checked in both viewers; live pending'}
    # Keep preceding asset proofs under their true identities and add a current pointer.
    archive_doc = read(ROOT / 'docs/native-archive-layout.json')
    archive_doc['current_font_port'] = {'version': VERSION, 'WIN00_sha256': digest(files['WIN00.AFS']),
        'native_lookup_cases': 90, 'native_proof': summary['native_proof'],
        'all_current_archives_compatible': report['native_archive_layout_validation']}
    outline_doc = read(ROOT / 'docs/font-outline.json')
    outline_doc['superseded_by'] = {'version': VERSION, 'source': 'Original Skies pixels', 'document': 'docs/skies-font-port.json'}
    return [(ROOT / 'docs/skies-font-port.json', summary),
            (ROOT / 'docs/translation-status.json', status),
            (ROOT / 'docs/native-archive-layout.json', archive_doc),
            (ROOT / 'docs/font-outline.json', outline_doc)], summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    updates, summary = record()
    print('PASS: 0.1.39, fourteen verified game payloads, original-Skies font and all new native proofs.', flush=True)
    print('Disc:', summary['disc'], flush=True)
    print('Metadata updates:', [str(p.relative_to(ROOT)) for p, _ in updates], flush=True)
    old_pref = '- Font selection: the user replaced GenEi Latin with the supplied bitmap atlas on 2026-10-23. Source: incoming/fonts/user-bitmap/dialogue-atlas.png (384 x 168, 32 columns of 12 x 24 cells). Use its Latin contours with variable advances and consistent scale/baseline; do not stretch individual letters. GenEi remains a historical build dependency and the source of five protected non-ASCII marks until replacements are available.'
    new_pref = '- Font selection: on 2026-10-23 the user explicitly superseded the supplied bitmap with the original Skies of Arcadia USA Dreamcast Latin font from E:\\Games. Decode its 12 x 24 VQ glyphs using tools/analyze_skies_font.py; preserve original pixel shapes and four alpha levels, with variable advances and a consistent scale/baseline. Do not stretch individual letters or reconstruct outlines. Build integration: tools/build_skies_font_patch.py; source/proof record: docs/skies-font-port.json. The supplied atlas at incoming/fonts/user-bitmap/dialogue-atlas.png and GenEi remain historical dependencies; five protected non-ASCII marks still use GenEi.'
    agents = ROOT / 'AGENTS.md'
    original = agents.read_text('utf-8')
    assert old_pref in original or new_pref in original
    if not args.write:
        print('DRY RUN: metadata, changelog and explicit font-preference replacement only; no writes.')
        return
    for path, value in updates:
        path.write_text(json.dumps(value, indent=2) + '\n', 'utf-8')
    agents.write_text(original.replace(old_pref, new_pref), 'utf-8')
    changes = ROOT / 'CHANGELOG.md'
    content = changes.read_text('utf-8')
    if NOTE.splitlines()[0] not in content:
        changes.write_text(content.replace('# Change log\n\n', '# Change log\n\n' + NOTE, 1), 'utf-8')
    print('Recorded current build, explicit font selection, proofs and changelog.', flush=True)


if __name__ == '__main__':
    main()
