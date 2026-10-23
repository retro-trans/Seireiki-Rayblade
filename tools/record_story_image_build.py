"""Record packaged note/placeholders and expanded PVM discovery. Dry first."""
import argparse
import json

from build_bitmap_font import ROOT, digest
from build_story_image_disc import VERSION
from disc_inventory import Disc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'work/output' / VERSION
    report = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
    assert report['version'] == VERSION and report['source_build'] == '0.1.26'
    assert report['validation']['reextracted_files'] == 'all 10 exact'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['new_changed_sectors'] == 79 and report['total_changed_sector_locations_from_original'] == 27894
    prior = json.loads((ROOT / 'work/output/0.1.26/english-disc-report.json').read_text('utf-8'))
    assert {n: report['files'][n] for n in prior['files']} == prior['files']
    assert report['total_changed_sector_locations_from_original'] == 27815 + report['new_changed_sectors']
    disc_relative = f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi'
    disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']: r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        data = disc.read(row['lba'], row['size'])
        assert len(data) == info['size'] and digest(data) == info['sha256']
    assert len(report['historical_native_evidence']) == 16
    for item in report['historical_native_evidence']:
        raw = (out / item['file']).read_bytes()
        assert digest(raw) == item['sha256'] and json.loads(raw)['executable_sha256'] == item['executable_sha256']
    proof_bytes = (out / 'story-images-native-test.json').read_bytes()
    proof = json.loads(proof_bytes)
    component = json.loads((out / 'story-images-component-report.json').read_text('utf-8'))
    assert proof == report['story_images_native_proof'] and component == report['story_images_component']
    assert digest(proof_bytes) == report['story_images_proof_sha256']
    assert proof['archive_sha256'] == report['files']['ADV00.AFS']['sha256']
    assert proof['image_resource_count'] == 9 and len(proof['unique_PRS_streams']) == 3
    assert proof['letter_original_U_V_and_headers'] == 'exact' and proof['linked_story_rows'] == 10
    for key in ('story-images-preview.png', 'letter-before-after.png'):
        assert (out / key).is_file()
    doc = {'version': VERSION, 'source_build': '0.1.26',
           'status': 'Kasumi note and eight source development-placeholder images translated and packaged; native/structural checks pass, live loading/appearance/reachability pending',
           'disc': disc_relative, 'archive': 'ADV00.AFS', 'archive_sha256': proof['archive_sha256'],
           'changed_texture_members': component['changed_members'],
           'letter_recipe': 'work/translation/en/ui/story-letter.en.json',
           'placeholder_recipe': 'work/translation/en/ui/story-image-labels.en.json',
           'letter_source_command': 'scenario.s_081.o00659', 'linked_story_rows': 10,
           'letter_render': component['letter_render'],
           'previews': [f'work/output/{VERSION}/story-images-preview.png', f'work/output/{VERSION}/letter-before-after.png'],
           'native_proof': proof, 'validation': report['validation'],
           'preservation': '768 other member payloads and 776 original offsets exact. Letter 379 moves to checked zero padding at 0x60000; native texture headers/resource IDs and every original letter U/V color byte remain exact. Archive extent unchanged.',
           'new_changed_sectors': report['new_changed_sectors'],
           'changed_sector_locations_from_original': report['total_changed_sector_locations_from_original'],
           'normal_text_font_changed': False,
           'meaning_notes': ['All ten existing note rows retained, including miso soup, Yamato food, apology, unspecified clothing, punctuality and Kasumi signature.',
                             'Only outer quotation marks and signature spacing become image layout; English wording is reused without new story-row credit.',
                             'Work in Progress and Dummy retain the original development notices; no unfinished illustrations are invented.',
                             'The first paper-removal preview had bright Japanese ghosts; revised local paper values replaced additive brightness correction, and the corrected preview was reviewed.'],
           'pending': report['pending'], 'release': False, 'story_library_draft_credit': 0}
    pvm_path = ROOT / 'work/ui/asset-audit/ADV01/pvm/texture-index.json'
    index = json.loads(pvm_path.read_text('utf-8'))
    assert index['PVM_containers'] == 251 and index['texture_count'] == 473
    assert len(index['unsupported_or_failed']) == 3 and len(index['skipped_members']) == 5
    assert sum(r.get('verified_trailing_zero_bytes', 0) == 16 for r in index['textures']) == 223
    contacts = []
    for i in range(5):
        path = pvm_path.parent / f'contact-{i:02d}.png'
        contacts.append({'path': str(path.relative_to(ROOT)).replace('\\', '/'), 'sha256': digest(path.read_bytes())})
    pvm = {'status': '473 PVM textures decoded and contact-reviewed; three mipmap textures and full-resolution text/reachability review incomplete',
           'archive': index['archive'], 'source_archive_sha256': index['source_archive_sha256'],
           'index': str(pvm_path.relative_to(ROOT)).replace('\\', '/'), 'index_sha256': digest(pvm_path.read_bytes()),
           'PVM_containers': 251, 'textures_decoded': 473,
           'texture_chunks_discovered': sum(r['classification'] == 'texture' for c in index['containers'] for r in c['chunks']),
           'verified_zero_trailing_padding_cases': 223, 'unsupported': index['unsupported_or_failed'],
           'other_members': index['skipped_members'], 'contacts_reviewed': contacts,
           'observation': 'Portraits, expression banks and small scene illustrations; no additional text candidate observed on the five contact sheets. This is not a full-resolution absence proof.',
           'format_reference': 'https://github.com/nickworonekin/puyotools/wiki/PVR-Texture',
           'remaining_format': '0x12 alternate twiddled mipmaps in members 9/85/209; not guessed as rectangular data',
           'scope': 'Read-only discovery; no source PVM files modified and no new story/library draft credit'}
    assert pvm['texture_chunks_discovered'] == 476
    audit_path = ROOT / 'docs/non-movie-image-text-audit.json'
    audit = json.loads(audit_path.read_text('utf-8'))
    audit.update(last_packaged_build=VERSION, story_images=doc, PVM_discovery=pvm)
    audit['remaining_findings'] = [r for r in audit['remaining_findings'] if r.get('archive') != 'ADV00.AFS']
    for finding in audit['remaining_findings']:
        if finding.get('archive') == 'ADV01.AFS':
            finding.update(finding='PVM-capable audit decoded 473 textures from 251 containers; three alternate-mipmap textures remain unsupported.',
                           status='Five contact sheets reviewed; full-resolution absence/reachability review and three mipmaps still pending')
    audit['completed_image_work'] = [r for r in audit.get('completed_image_work', [])
                                     if (r.get('build'), r.get('archive')) != (VERSION, 'ADV00.AFS')]
    audit['completed_image_work'].append({'build': VERSION, 'archive': 'ADV00.AFS',
                                         'members': component['changed_members'], 'scope': doc['status']})
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status.update(version=VERSION,
                  stage='English pictured Kasumi note and eight development-placeholder images inserted over unchanged 0.1.26; remaining names/images/movies, held passages, font/live review and full-game validation incomplete',
                  latest_story_image_build=doc, non_movie_image_text_audit=audit, PVM_image_discovery=pvm)
    status['test_disc'].update(version=VERSION, source_build='0.1.26', path=disc_relative,
                               kind=report['kind'], changed_sectors=report['total_changed_sector_locations_from_original'],
                               validation=report['validation'], story_images_delta_sectors=report['new_changed_sectors'],
                               ADV00_sha256=doc['archive_sha256'], credits_component_origin_build='0.1.26')
    status['test_disc'].pop('credits_delta_sectors', None)
    status['test_disc']['pending'] = list(dict.fromkeys([*status['test_disc']['pending'], *report['pending']]))
    print('PASS: 0.1.27, ten exact payloads, nine images, ten linked note rows, 473 PVM previews with three explicit unsupported mipmaps;', report['new_changed_sectors'], 'new sectors.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path, data in [(ROOT / 'docs/story-images.json', doc), (ROOT / 'docs/pvm-image-audit.json', pvm), (audit_path, audit), (status_path, status)]:
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
