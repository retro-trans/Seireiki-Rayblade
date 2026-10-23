"""Package verified Skies font and measured layouts as 0.1.39. Dry first."""
import argparse
import json

from build_skies_font_patch import VERSION, PRIOR, OUT, ROOT, compose, digest
from package_archive_test_disc import plan_archive_patch, substitute_payload_sector
from build_movie_test_disc import write_plan
from disc_inventory import Disc, SECTOR


def plan():
    p = plan_archive_patch(
        version=VERSION, prior_version=PRIOR, archive_name='WIN00.AFS', draft_dir=OUT, candidate=compose,
        slug='skies-font', proof_count_key='glyph_cases', proof_count=397, replace_existing=True,
        prior_proof=('ordered-archives-native-test.json', 'ordered_archives_proof_sha256', None),
        description='Original Skies Latin font integrated with variable advances and measured library/UI layouts',
        pending=['Fresh boot and live original-Skies font appearance across dialogue, battles, library and menus'],
        proof_scope='397 source-exact native glyph cases; all 50273 story commands/123041 boundaries measured; affected UI, library and PRS execution. Original Skies pixels retained. GPU appearance and whole-game testing pending.',
        readme='Ports the original Skies of Arcadia USA Dreamcast Latin font into normal Rayblade text.\n'
               'Preserves its four coverage shades and original pixel shapes; variable spacing, small and medium text.\n'
               'Library/help text rewrapped; narrow labels use Counters, SP, PR, Hit and Ht Dif.\n'
               'Completed-chapter strips use Clear and keep every complete title.\n'
               'The original font pixels replace inferred outlines. No emulator texture replacement; textures remain <=1024.\n'
               'TEST: boot this GDI afresh, choose New Game and compare r/O and normal dialogue, then menus/library.\n'
               'Existing emulator save states retain old game memory; use a fresh boot for the new font.\n')
    disc, cue, inherited, targets, changes, names, historical, report = p
    archive, component, _, _, extras = compose()
    proof = json.loads((OUT / 'native-test.json').read_text('utf-8'))
    inline_raw = (OUT / 'inline-native-test.json').read_bytes()
    inline = json.loads(inline_raw)
    assert inline['commands'] == 166 and inline['cursor_bounds'] == 'pass'
    assert inline['font_sha256'] == proof['font_sha256'] and inline['executable_sha256'] == proof['executable_sha256']
    assert inline['archive_sha256'] == digest(inherited['D_SCE.AFS'])
    report['skies_font_inline_proof'] = inline
    report['skies_font_inline_proof_sha256'] = digest(inline_raw)
    assert proof['native_UI_cases'] == 145 and proof['native_WIN00_lookup_cases'] == 90
    assert proof['library_native_line_occurrences'] == 3534
    target = extras['text/D_NAMES.BIN']
    assert target == (OUT / 'text/D_NAMES.BIN').read_bytes()
    assert proof['names_packed_sha256'] == digest(target) == component['names_packed_sha256']
    row = next(r for r in disc.inventory() if r['path'] == 'D_NAMES.BIN')
    source = inherited['D_NAMES.BIN']
    assert len(source) == len(target) == row['size']
    original_disc = Disc(next(ROOT.glob('*.cue')))
    original = original_disc.read(row['lba'], row['size'])
    old_locations = sum(source[i:i+2048] != original[i:i+2048] for i in range(0, len(source), 2048))
    new_locations = sum(target[i:i+2048] != original[i:i+2048] for i in range(0, len(target), 2048))
    extra_changes = []
    for i in range((len(target) + 2047) // 2048):
        a, b = source[i*2048:(i+1)*2048], target[i*2048:(i+1)*2048]
        if a == b:
            continue
        lba = row['lba'] + i
        track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
        offset = (track['index'] + lba - track['start_lba']) * SECTOR
        with track['path'].open('rb') as fh:
            fh.seek(offset)
            raw = fh.read(SECTOR)
        extra_changes.append((track['path'].name, offset, substitute_payload_sector(raw, a, b)))
    assert not ({(n, off) for n, off, _ in changes} & {(n, off) for n, off, _ in extra_changes})
    changes.extend(extra_changes)
    targets['D_NAMES.BIN'] = target
    report['files']['D_NAMES.BIN'] = {'size': len(target), 'sha256': digest(target)}
    report['new_changed_sectors'] = len(changes)
    report['total_changed_sector_locations_from_original'] += new_locations - old_locations
    report['inherited_components'] = 'Twelve game payloads exact 0.1.38; WIN00 font/library and D_NAMES layouts updated'
    report['names_layout_sector_substitutions'] = len(extra_changes)
    report['proof_scope'] = ('397 source-exact native glyph cases, all retained story boundaries measured, '
        f"{proof['native_UI_cases']} native UI cases, both PRS decodes, "
        f"{proof['library_parser_pages']} library parser pages and {proof['library_filter_cases']} filter cases, "
        '90 actual WIN00 SDK lookups. Bounded external fixtures and GPU/live limits retained in native report.')
    return p


def finalize(planned):
    out = ROOT / 'work/output' / VERSION
    _, component, _, font, extras = compose()
    for name, raw in extras.items():
        (out / name).write_bytes(raw)
    for name in ('component-report.json', 'native-test.json', 'inline-native-test.json', 'font-preview.png', 'settings-preview.png'):
        (out / ('skies-font-' + name)).write_bytes((OUT / name).read_bytes())
    manifest_path = out / 'font4x-patch.json'
    manifest = json.loads(manifest_path.read_text('utf-8'))
    manifest.update(version=VERSION, previous_build=PRIOR, status='Original Skies Latin port verified offline; local playable build, live font appearance pending')
    manifest['files']['WIN00.AFS']['target_sha256'] = component['target_archive_sha256']
    manifest['files']['D_NAMES.BIN'] = {'source_sha256': digest(planned[2]['D_NAMES.BIN']),
                                      'target_sha256': component['names_packed_sha256']}
    manifest['skies_font'] = {'version': VERSION, 'font_sha256': digest(font), 'method': component['method'],
                            'native_proof': 'skies-font-native-test.json', 'live_appearance': 'pending'}
    manifest.setdefault('antialias_font_before_skies_port', manifest.get('antialias_font'))
    manifest['antialias_font'] = {'version': VERSION, 'font_sha256': digest(font),
        'source': 'Original Skies of Arcadia USA Dreamcast Latin VQ glyphs',
        'texture_format': 'Existing ARGB4444 surfaces, two-bit coverage; cap <=1024',
        'advances': 'Measured original contours, one shared rule per bank',
        'native_validation': 'skies-font-native-test.json', 'live_validation': 'pending'}
    manifest['font_outline']['superseded_by'] = VERSION
    manifest['vector_font'].update(type='Original Skies bitmap; no reconstructed or vector contours',
                                   sampling='Exact original coverage, uniform repeats', coverage='0,85,187,255')
    manifest['ui_layout'].update(version=VERSION, names_sha256=component['names_sha256'],
        names_packed_sha256=component['names_packed_sha256'], native_validation='145 native cases, actual PRS decode')
    library = manifest['library']
    import struct
    offset, size = struct.unpack_from('<II', planned[3]['WIN00.AFS'], 8 + 52 * 8)
    library.update(version=VERSION, archive_member_offset=offset, archive_member_bytes=size,
                   library_payload_sha256=component['library_sha256'], archive_repack_build=VERSION)
    manifest['library_layout'] = {**component['library'], 'native_validation': 'all 1767 lines parsed in both viewers; 1028 none/all flag filter cases over 257 physical records'}
    scenario_path = out / 'text/scenario-component-report.json'
    scenario = json.loads(scenario_path.read_text('utf-8'))
    scenario['presentation_font_update_build'] = VERSION
    scenario['word_wrap'].update(font_sha256=digest(font),
        current_font_validation='All 50273 commands / 123041 retained boundaries measured, maximum 197 of 236 pen pixels',
        live_verification='pending for original Skies font')
    scenario_path.write_text(json.dumps(scenario, indent=2) + '\n', 'utf-8')
    manifest['scenario']['word_wrap'] = scenario['word_wrap']
    manifest['current_payload_identities'] = planned[7]['files']
    manifest['native_proof_reuse'] = {'source_build': PRIOR, 'executable_sha256': component['executable_sha256'],
        'fresh_proof': 'skies-font-native-test.json', 'scope': 'Original font, spacing, affected library/UI and loaders freshly tested; other archive proofs historical'}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', 'utf-8')
    for name in ('library-patch-report.json', 'chapter-card-component.json'):
        path = out / name
        value = json.loads(path.read_text('utf-8'))
        value['current_font_port_build'] = VERSION
        value['current_archive_sha256'] = component['target_archive_sha256']
        if name == 'library-patch-report.json':
            value.update(archive_member_offset=offset, archive_member_bytes=size,
                         library_payload_sha256=component['library_sha256'])
        path.write_text(json.dumps(value, indent=2) + '\n', 'utf-8')
    license_text = ('Rayblade 0.1.39 Latin pixels: decoded from the local Skies of Arcadia USA Dreamcast disc.\n'
                    'Original game font data; no new font license is granted. Local test build.\n'
                    'The five protected non-ASCII marks retain their previous GenEi masks and notices.\n\n'
                    + (ROOT / 'work/output' / PRIOR / 'FONT-LICENSE.txt').read_text('utf-8'))
    (out / 'FONT-LICENSE.txt').write_text(license_text, 'utf-8')
    (out / 'disc/FONT-LICENSE.txt').write_text(license_text, 'utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--finalize-existing', action='store_true', help='Resume metadata after verifying an already completed disc package')
    args = ap.parse_args()
    planned = plan()
    print('PASS:', len(planned[4]), 'sector substitutions;', len(planned[7]['files']), 'payloads;',
          len(planned[6]), 'historical proof identities.', flush=True)
    if args.finalize_existing:
        out = ROOT / 'work/output' / VERSION
        saved = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
        assert saved['files'] == planned[7]['files'] and saved['skies_font_proof_sha256'] == planned[7]['skies_font_proof_sha256']
        assert saved['validation']['reextracted_files'] == 'all 14 exact'
        assert saved['validation']['changed_sector_EDC_ECC'] == 'pass'
        assert saved['validation']['unrelated_track_bytes'] == 'all unchanged'
        assert saved['validation']['track_bytes_compared'] == 1188856032
        disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
        entries = {r['path']: r for r in disc.inventory()}
        for name, raw in planned[3].items():
            row = entries[name]
            assert disc.read(row['lba'], row['size']) == raw
        print('Existing disc re-extraction and completed track validation record verified.', flush=True)
    if not args.write:
        print('DRY RUN: no game build or metadata written')
        return
    if not args.finalize_existing:
        write_plan(planned, VERSION, PRIOR, {name: planned[3][name] for name in ('WIN00.AFS', 'D_NAMES.BIN')})
    finalize(planned)
    print('Build records complete:', ROOT / 'work/output' / VERSION, flush=True)


if __name__ == '__main__':
    main()
