"""Record checked album captions and the expanded structural image audit.

Default dry run. Checks actual packaged payloads and proof identities before
updating status; no completion, live-appearance or all-images absence claim.
"""
import argparse
import json

from build_album_test_disc import VERSION, PRIOR
from build_bitmap_font import ROOT, digest
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def relative(path):
    return str(path.relative_to(ROOT)).replace('\\', '/')


def record():
    out = ROOT / 'work/output' / VERSION
    report = read(out / 'english-disc-report.json')
    prior = read(ROOT / 'work/output' / PRIOR / 'english-disc-report.json')
    assert report['version'] == VERSION and report['source_build'] == PRIOR
    assert report['validation']['reextracted_files'] == 'all 11 exact'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    assert report['total_changed_sector_locations_from_original'] == prior['total_changed_sector_locations_from_original'] + report['new_changed_sectors']
    assert {name: report['files'][name] for name in prior['files']} == prior['files']
    disc_path = out / 'disc' / f'Rayblade English Test {VERSION}.gdi'
    disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']: r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'], row['size'])
        assert len(raw) == info['size'] and digest(raw) == info['sha256']
    assert len(report['historical_native_evidence']) == 17
    for item in report['historical_native_evidence']:
        raw = (out / item['file']).read_bytes()
        assert digest(raw) == item['sha256']
        assert json.loads(raw)['executable_sha256'] == item['executable_sha256']
    raw = (out / 'album-captions-native-test.json').read_bytes()
    proof = json.loads(raw)
    component = read(out / 'album-captions-component-report.json')
    assert proof == report['album_captions_native_proof']
    assert component == report['album_captions_component']
    assert digest(raw) == report['album_captions_proof_sha256']
    assert proof['archive_sha256'] == report['files']['ALBUM.AFS']['sha256']
    assert proof['caption_count'] == 201 and len(proof['native_PRS_streams']) == 28
    assert proof['protected_photo_areas'] == 224 and proof['protected_whole_cells'] == 23
    assert proof['native_guard_and_ABI'] == 'pass'
    assert proof['archive_bytes_outside_declared_edits'] == 'exact'
    previews = [out / 'album-captions-gallery-before-after.png',
                *[out / f'English-captions-{page:02d}.png' for page in range(7)]]
    assert all(p.is_file() for p in previews)
    doc = {'version': VERSION, 'source_build': PRIOR,
           'status': '201 English album caption drafts packaged; two source readings, pictured text, independent meaning review and live album checks remain incomplete',
           'disc': relative(disc_path), 'archive': 'ALBUM.AFS',
           'archive_sha256': proof['archive_sha256'], 'translation_map': 'work/translation/en/ui/album-captions.en.json',
           'geometry_map': 'work/ui/asset-audit/ALBUM/captions/rectangles.json',
           'caption_count': 201, 'source_caption_count': 203,
           'unresolved_caption_ids': proof['unresolved_caption_ids'],
           'protected_photograph_regions': 224, 'protected_Coming_Soon_cells': 21,
           'protected_unreadable_caption_cells': 2,
           'font_sampling': 'Uniform 1/3 source scale, independently area-averaged 3x3 coverage; no individual glyph stretching',
           'font_review': 'Rejected max-pool caption sample as heavy; reviewed averaged gallery comparison and all seven English sheets. This does not change normal-text font smoothing.',
           'previews': [{'path': relative(p), 'sha256': digest(p.read_bytes())} for p in previews],
           'native_proof': proof, 'validation': report['validation'],
           'preservation': '216 other member payloads and both DAT geometry members exact; all 224 thumbnail photographs exact. Six atlases move into checked zero prefix padding, with all other member offsets and the archive extent retained.',
           'changed_members': component['changed_members'], 'relocated_members': component['relocated_members'],
           'meaning_notes': ['Full caption wording/sequence numbers retained; project glossary spellings reused.',
                             'IDs 174/175 retain a provisional becoming-Debish interpretation requiring story-context review.',
                             'Unclear caption source readings remain original rather than guessed.'],
           'new_changed_sectors': report['new_changed_sectors'],
           'changed_sector_locations_from_original': report['total_changed_sector_locations_from_original'],
           'normal_text_font_changed': False, 'story_library_draft_credit': 0,
           'pending': report['pending'], 'release': False}
    audits = []
    for name, visual in [('ALBUM', 'Three original contact sheets, full pictured note/card, all seven source/English caption sheets and context witnesses reviewed; full live artwork review pending'),
                         ('ANIME', 'No previews from these prefix decoders; archive format/unclassified members pending'),
                         ('BTT_FACE', 'Contact sheets generated; visual inspection pending'),
                         ('CUTIN', 'Contact sheets generated; visual inspection pending'),
                         ('EFFECT', '459 PVM texture errors explicit; palette/format decoding pending'),
                         ('MAP', 'Contact sheets generated; visual inspection and two decoder errors pending')]:
        path = ROOT / 'work/ui/asset-audit' / name / 'texture-index.json'
        a = read(path)
        pvm_path = path.parent / 'pvm/texture-index.json'
        b = read(pvm_path)
        audits.append({'archive': name + '.AFS', 'GBIX_index': relative(path), 'GBIX_index_sha256': digest(path.read_bytes()),
                       'archive_members': a['archive_members'], 'GBIX_textures_decoded': a['texture_count'],
                       'GBIX_errors': a['unsupported_or_failed'], 'outside_GBIX_decoder': len(a['non_GBIX_members']),
                       'PVM_index': relative(pvm_path), 'PVM_index_sha256': digest(pvm_path.read_bytes()),
                       'source_archive_sha256': b['source_archive_sha256'], 'PVM_containers': b['PVM_containers'],
                       'PVM_textures_decoded': b['texture_count'], 'PVM_error_count': len(b['unsupported_or_failed']),
                       'outside_PVM_decoder': len(b['skipped_members']), 'visual_review': visual,
                       'limit': 'Structural coverage of these formats only; zero previews does not mean no images/text'})
    pvm_path = ROOT / 'work/ui/asset-audit/ADV01/pvm-mipmaps-01/texture-index.json'
    index = read(pvm_path)
    assert index['texture_count'] == 476 and index['PVM_containers'] == 251
    assert not index['unsupported_or_failed'] and len(index['skipped_members']) == 5
    mipmaps = [r for r in index['textures'] if r.get('data_format') == 18]
    assert len(mipmaps) == 3 and sorted(r['member'] for r in mipmaps) == [9, 85, 209]
    pvm = {'status': '476 textures decoded; three previously unsupported mipmap base images inspected. Full-resolution absence/reachability coverage incomplete',
           'archive': 'ADV01.AFS', 'index': relative(pvm_path), 'index_sha256': digest(pvm_path.read_bytes()),
           'source_archive_sha256': index['source_archive_sha256'], 'PVM_containers': 251, 'textures_decoded': 476,
           'unsupported': [], 'other_members': index['skipped_members'],
           'mipmap_cases': mipmaps,
           'mipmap_method': 'Verified six zero prefix bytes and every smallest-to-largest 16-bit level span/hash; preview base only',
           'visual_review': 'The previous 473-texture contact-sheet audit is retained; the three additional full base images show portrait/expression banks with no added text candidate observed. New combined contact sheets not rereviewed.',
           'format_reference': 'https://github.com/nickworonekin/puyotools/wiki/PVR-Texture',
           'limits': ['No GPU mip selection test', 'Contact-sheet inspection is not a no-text proof'],
           'previous_audit': read(ROOT / 'docs/pvm-image-audit.json')}
    if 'previous_audit' in pvm['previous_audit']:
        pvm['previous_audit'] = pvm['previous_audit']['previous_audit']
    audit_path = ROOT / 'docs/non-movie-image-text-audit.json'
    audit = read(audit_path)
    audit.update(last_packaged_build=VERSION, album_captions=doc, expanded_archive_audits=audits, PVM_discovery=pvm)
    audit['other_archives_not_covered_in_this_pass'] = []
    audit['expanded_audit_limits'] = ['ANIME remains outside these decoders', 'EFFECT paletted/other formats remain unsupported',
                                     'MAP has two explicit errors; MAP/BTT_FACE/CUTIN visual review pending',
                                     'Album note/New Year pictured artwork and two source-caption readings remain untranslated']
    for finding in audit['remaining_findings']:
        if finding.get('archive') == 'ADV01.AFS':
            finding.update(finding='All 476 discovered PVM textures decode, including three alternate mipmap base levels; five other members remain outside this decoder.',
                           status='Prior contact review plus three added full base images; full-resolution absence/reachability not established')
    audit['remaining_findings'] = [r for r in audit['remaining_findings'] if r.get('archive') != 'ALBUM.AFS']
    audit['remaining_findings'].append({'archive': 'ALBUM.AFS', 'status': doc['status'],
                                       'unresolved_caption_ids': doc['unresolved_caption_ids'],
                                       'pictured_text_members': [15, 81], 'matching_thumbnail_artwork_pending': True})
    for row in audit['new_archive_audits']:
        if row['archive'] == 'ADV01.AFS':
            row['visual_review'] = 'GBIX audit has no previews; separate PVM audit now decodes 476 textures. See PVM_discovery.'
    audit['completed_image_work'] = [r for r in audit.get('completed_image_work', [])
                                     if (r.get('build'), r.get('archive')) != (VERSION, 'ALBUM.AFS')]
    audit['completed_image_work'].append({'build': VERSION, 'archive': 'ALBUM.AFS', 'caption_count': 201, 'scope': doc['status']})
    status_path = ROOT / 'docs/translation-status.json'
    status = read(status_path)
    status.update(version=VERSION,
                  stage='201 English album caption drafts inserted over unchanged 0.1.27; two caption readings, pictured text, other images/movies, held passages, independent meaning review, font/live and full-game validation remain incomplete',
                  latest_album_caption_build=doc, non_movie_image_text_audit=audit, PVM_image_discovery=pvm,
                  latest_font_smoothing_investigation='docs/font-smoothing-investigation.json')
    status['test_disc'].update(version=VERSION, source_build=PRIOR, path=relative(disc_path), kind=report['kind'],
                               changed_sectors=report['total_changed_sector_locations_from_original'], validation=report['validation'],
                               album_caption_delta_sectors=report['new_changed_sectors'], ALBUM_sha256=proof['archive_sha256'])
    status['test_disc'].pop('story_images_delta_sectors', None)
    status['test_disc']['pending'] = report['pending']
    return [(ROOT / 'docs/album-captions.json', doc), (ROOT / 'docs/pvm-image-audit.json', pvm),
            (ROOT / 'docs/expanded-image-audit.json', {'audits': audits, 'limits': audit['expanded_audit_limits']}),
            (audit_path, audit), (status_path, status)], report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    changes, report = record()
    print('PASS: 0.1.28, eleven exact payloads, 201 captions, 28 native streams, 17 historical reports;',
          report['new_changed_sectors'], 'new sectors;', report['total_changed_sector_locations_from_original'], 'total.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path, data in changes:
        path.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
