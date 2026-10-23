"""Record packaged credit translations and exact remaining scope. Dry run first."""
import argparse
import json

from build_bitmap_font import ROOT, digest
from build_staff_test_disc import VERSION
from disc_inventory import Disc
from prepare_staff_credits import prepare, DEST, GLOSSARY


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'work/output' / VERSION
    report = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
    assert report['version'] == VERSION and report['source_build'] == '0.1.25'
    assert report['validation']['reextracted_files'] == 'all 9 exact'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['new_changed_sectors'] == 31 and report['total_changed_sector_locations_from_original'] == 27815
    prior = json.loads((ROOT / 'work/output/0.1.25/english-disc-report.json').read_text('utf-8'))
    assert {n: report['files'][n] for n in prior['files']} == prior['files']
    disc_relative = f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi'
    disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']: r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        data = disc.read(row['lba'], row['size'])
        assert len(data) == info['size'] and digest(data) == info['sha256']
    assert len(report['historical_native_evidence']) == 15
    for item in report['historical_native_evidence']:
        raw = (out / item['file']).read_bytes()
        assert digest(raw) == item['sha256'] and json.loads(raw)['executable_sha256'] == item['executable_sha256']
    proof_bytes = (out / 'credits-native-test.json').read_bytes()
    proof = json.loads(proof_bytes)
    assert proof == report['credits_native_proof']
    assert digest(proof_bytes) == report['credits_proof_sha256']
    assert proof['archive_sha256'] == report['files']['STAFF.AFS']['sha256']
    recipe, glossary = prepare()
    assert json.loads(DEST.read_text('utf-8')) == recipe
    assert json.loads(GLOSSARY.read_text('utf-8')) == glossary
    component = json.loads((out / 'credits-component-report.json').read_text('utf-8'))
    assert component == report['credits_component']
    assert component['translation_map_sha256'] == digest(DEST.read_bytes())
    assert all((out / f'credits-preview-{i:02d}.png').is_file() for i in range(4))
    unresolved = [r for r in glossary['people'] if r['en'] is None]
    assert len(unresolved) == 7 and len(glossary['people']) == 42
    doc = {'version': VERSION, 'source_build': '0.1.25',
           'status': '21 translated credit roles/company labels and 35 supported name readings inserted; seven name readings and live credit playback unresolved',
           'disc': disc_relative, 'translation_map': str(DEST.relative_to(ROOT)).replace('\\', '/'),
           'staff_name_glossary': str(GLOSSARY.relative_to(ROOT)).replace('\\', '/'),
           'source_geometry': 'work/ui/asset-audit/STAFF/rectangles.json',
           'previews': [f'work/output/{VERSION}/credits-preview-{i:02d}.png' for i in range(4)],
           'archive_sha256': report['files']['STAFF.AFS']['sha256'],
           'translated_role_company_sprites': 21, 'supported_name_reading_sprites': 35,
           'source_credit_sprites': 84, 'source_personal_name_sprites': 42,
           'protected_original_English_text_sprites': 20, 'protected_blank_sprite': 1,
           'unresolved_names': unresolved,
           'name_sources': glossary['sources'],
           'native_proof': proof, 'validation': report['validation'],
           'archive_preservation': '20 other member payloads and every original member offset exact; only DAT 19 and texture 20 change. Texture remains 1024x256 ARGB1555; original archive/file extent retained.',
           'previous_components': 'Eight game payloads exact 0.1.25; fifteen historical proof identities retained',
           'new_changed_sectors': 31, 'changed_sector_locations_from_original': 27815,
           'meaning_notes': ['Roles authored against the original Japanese image; existing English title counterparts inform role terminology.',
                             'Name readings use a secondary credits reference and are not claimed official self-romanizations.',
                             'ASCII long-vowel forms are used for the native Latin repertoire; no names abbreviated to initials.',
                             'All seven unresolved Japanese name images stay readable; no guessed substitutions.',
                             'Name sprite 52 exists in the atlas but is absent from the consulted Rayblade credit transcript; actual use is unverified.'],
           'pending': report['pending'], 'release': False, 'story_library_draft_credit': 0}
    audit_path = ROOT / 'docs/non-movie-image-text-audit.json'
    audit = json.loads(audit_path.read_text('utf-8'))
    audit.update(last_packaged_build=VERSION, staff_credits=doc)
    for finding in audit['remaining_findings']:
        if finding.get('archive') == 'STAFF.AFS':
            finding.update(finding='Seven unresolved personal-name images remain Japanese; secondary-reference readings need independent confirmation.',
                           status='56 image-label updates packaged in 0.1.26; live credit playback and all-name translation incomplete',
                           unresolved_sprite_ids=recipe['unresolved_name_ids'])
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status.update(version=VERSION,
                  stage='21 credit role/company labels and 35 supported name readings inserted over unchanged 0.1.25; seven credit names, remaining image/movie text, held passages, font/live review and full-game validation incomplete',
                  latest_credits_build=doc, non_movie_image_text_audit=audit,
                  staff_credits_glossary={'path': doc['staff_name_glossary'], 'people': 42, 'supported_readings': 35,
                                          'unresolved_readings': 7, 'scope': 'Separate staff roster; fictional glossary remains 851 entries'})
    status['test_disc'].update(version=VERSION, source_build='0.1.25', path=disc_relative,
                               kind=report['kind'], changed_sectors=27815, validation=report['validation'],
                               credits_delta_sectors=31, credits_sha256=doc['archive_sha256'],
                               worldmap_component_origin_build='0.1.25')
    status['test_disc'].pop('worldmap_delta_sectors', None)
    status['test_disc']['pending'] = list(dict.fromkeys([*status['test_disc']['pending'], *report['pending']]))
    print('PASS: 0.1.26; nine exact payloads; 56 credit updates; seven preserved unresolved names; native proof identity; 31 new sectors.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path, data in [(ROOT / 'docs/staff-credits.json', doc), (audit_path, audit), (status_path, status)]:
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
