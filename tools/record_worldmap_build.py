"""Record verified local map build and remaining image-audit scope. Dry run first."""
import argparse
from collections import Counter
import json

from build_bitmap_font import ROOT, digest
from build_worldmap_test_disc import VERSION
from disc_inventory import Disc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'work/output' / VERSION
    report = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
    assert report['version'] == VERSION and report['source_build'] == '0.1.24'
    assert report['validation']['reextracted_files'] == 'all 8 exact'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['new_changed_sectors'] == 14 and report['total_changed_sector_locations_from_original'] == 27784
    prior = json.loads((ROOT / 'work/output/0.1.24/english-disc-report.json').read_text('utf-8'))
    assert {n: report['files'][n] for n in prior['files']} == prior['files']
    disc_relative = f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi'
    disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']: r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        data = disc.read(row['lba'], row['size'])
        assert len(data) == info['size'] and digest(data) == info['sha256']
    for item in report['historical_native_evidence']:
        assert digest((out / item['file']).read_bytes()) == item['sha256']
    proof = json.loads((out / 'worldmap-native-test.json').read_text('utf-8'))
    assert proof == report['worldmap_native_proof']
    assert digest((out / 'worldmap-native-test.json').read_bytes()) == report['worldmap_proof_sha256']
    assert proof['archive_sha256'] == report['files']['WMAP.AFS']['sha256']
    doc = {'version': VERSION, 'source_build': '0.1.24',
           'status': 'Ten English world-map image labels inserted; local native/structural checks pass, live loading/layout/navigation pending',
           'disc': disc_relative, 'translation_map': 'work/translation/en/ui/worldmap-labels.en.json',
           'source_geometry': 'work/ui/asset-audit/WMAP/rectangles.json',
           'preview': f'work/output/{VERSION}/worldmap-worldmap-labels-preview.png',
           'archive_sha256': report['files']['WMAP.AFS']['sha256'],
           'label_count': 10, 'glossary_entries': 851,
           'native_proof': proof, 'validation': report['validation'],
           'archive_preservation': '18 other member payloads/offsets exact; only DAT 17 and texture 18 change. Texture 18 relocated to verified zero padding at 0x78000; 512x512 dimensions and original file extent retained.',
           'previous_components': 'Seven existing game payloads and fourteen historical proof identities exact 0.1.24',
           'new_changed_sectors': 14, 'changed_sector_locations_from_original': 27784,
           'meaning_notes': ['Nine labels use existing glossary entries; Belta is a new provisional phonetic spelling.',
                             'Research Institute Ruins retains the full place descriptor; no text omitted to fit.',
                             'Two widened cells preserve original horizontal centers and vertical anchors.'],
           'pending': report['pending'], 'release': False, 'story_library_draft_credit': 0}
    archives = []
    for name in ('STAFF', 'WMAP', 'ITM00', 'ADV01'):
        path = ROOT / 'work/ui/asset-audit' / name / 'texture-index.json'
        index = json.loads(path.read_text('utf-8'))
        archives.append({'archive': name + '.AFS', 'index': str(path.relative_to(ROOT)).replace('\\', '/'),
                         'index_sha256': digest(path.read_bytes()), 'GBIX_textures_decoded': index['texture_count'],
                         'GBIX_failures': len(index['unsupported_or_failed']),
                         'non_GBIX_members_outside_decoder': len(index.get('non_GBIX_members', [])),
                         'visual_review': 'full contact sheet and text atlas' if name in ('STAFF', 'WMAP') else
                                          ('contact sheet only' if name == 'ITM00' else 'No rendered textures; compressed PVM containers remain uninspected')})
    audit = {'status': 'Partial non-movie image-text audit; additional untranslated image text remains',
             'last_packaged_build': VERSION, 'new_archive_audits': archives,
             'worldmap_labels': doc,
             'remaining_findings': [
                 {'archive': 'STAFF.AFS', 'member': 20, 'size': [1024, 256],
                  'finding': 'Japanese credit roles and personal names mixed with existing English roles.',
                  'status': 'Needs exact sprite mapping, role translation and name-reading research; not inserted'},
                 {'archive': 'ADV00.AFS', 'members': [303, 307, 321, 333, 335, 337, 379, 481, 483],
                  'finding': 'Contact-sheet candidates include development placeholder text, a document and event-cut placeholders.',
                  'status': 'Needs full-resolution reading and reachable/debug classification; no claim that this candidate list is exhaustive'},
                 {'archive': 'ADV01.AFS', 'finding': 'GBIX-only decoder does not inspect the compressed PVM containers.',
                  'status': 'Requires a separate PVM-capable audit'}],
             'other_archives_not_covered_in_this_pass': ['ALBUM.AFS', 'ANIME.AFS', 'BTT_FACE.AFS', 'CUTIN.AFS', 'EFFECT.AFS', 'MAP.AFS'],
             'limits': ['Contact sheets may hide small text; no full-image absence claim.',
                        'This pass does not establish source art contains no other Japanese.',
                        'No current live map/GPU test and no full-game completion claim.']}
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    glossary = json.loads((ROOT / 'work/glossary/glossary.json').read_text('utf-8'))
    assert len(glossary['entries']) == 851
    status['glossary'].update(entries=851, categories=dict(Counter(r['category'] for r in glossary['entries'])))
    status.update(version=VERSION,
                  stage='Ten English world-map labels inserted over unchanged 0.1.24 components; remaining image/movie text, held passages, font/live review and full-game validation incomplete',
                  latest_worldmap_build=doc, non_movie_image_text_audit=audit)
    status['test_disc'].update(version=VERSION, source_build='0.1.24', path=disc_relative,
                               kind=report['kind'], changed_sectors=27784, validation=report['validation'],
                               worldmap_delta_sectors=14, worldmap_sha256=doc['archive_sha256'],
                               movie_component_origin_build='0.1.24')
    status['test_disc'].pop('movie_delta_sectors', None)
    status['test_disc']['pending'] = list(dict.fromkeys([*status['test_disc']['pending'], *report['pending']]))
    print('PASS: build 0.1.25, eight exact payloads, ten labels, 851 glossary entries, native proof identity, 14 sector changes; remaining images explicitly incomplete.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path, data in [(ROOT / 'docs/worldmap-labels.json', doc),
                       (ROOT / 'docs/non-movie-image-text-audit.json', audit), (status_path, status)]:
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
