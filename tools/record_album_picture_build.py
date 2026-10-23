"""Record checked 0.1.30 album picture translations. Dry run first."""
import argparse
import json
import struct

from build_album_picture_test_disc import VERSION, PRIOR
from build_bitmap_font import ROOT, digest
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\', '/')


def record():
    out = ROOT/'work/output'/VERSION
    report = read(out/'english-disc-report.json')
    previous = read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    assert report['version'] == VERSION and report['source_build'] == PRIOR
    assert report['validation']['reextracted_files'] == 'all 11 exact'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    assert report['validation']['track_bytes_compared'] == 1188856032
    assert report['new_changed_sectors'] == 84 and report['total_changed_sector_locations_from_original'] == 28390
    assert report['source_archive_changed_locations_from_original'] == 432
    assert report['target_archive_changed_locations_from_original'] == 496
    assert report['total_changed_sector_locations_from_original'] == previous['total_changed_sector_locations_from_original'] - 432 + 496
    assert report['archive_replaces_existing_component'] is True
    assert len(report['historical_native_evidence']) == 18
    disc_path = out/'disc'/f'Rayblade English Test {VERSION}.gdi'
    disc = Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']:r for r in disc.inventory()}
    for name, info in report['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'],row['size'])
        assert len(raw) == info['size'] and digest(raw) == info['sha256']
        if name != 'ALBUM.AFS':
            assert info == previous['files'][name]
    for item in report['historical_native_evidence']:
        raw = (out/item['file']).read_bytes()
        assert digest(raw) == item['sha256'] and json.loads(raw)['executable_sha256'] == item['executable_sha256']
    raw = (out/'album-pictures-native-test.json').read_bytes()
    proof = json.loads(raw)
    component = read(out/'album-pictures-component-report.json')
    assert proof == report['album_pictures_native_proof'] and component == report['album_pictures_component']
    assert digest(raw) == report['album_pictures_proof_sha256']
    assert proof['archive_sha256'] == report['files']['ALBUM.AFS']['sha256']
    assert proof['image_resource_count'] == 5 and len(proof['native_PRS_streams']) == 5
    assert sum(r['instructions'] for r in proof['native_PRS_streams']) == 19058581
    assert proof['all_224_caption_areas'] == proof['other_221_thumbnail_photographs'] == 'exact'
    assert proof['native_guard_and_ABI'] == 'pass' and proof['archive_bytes_outside_declared_edits'] == 'exact'
    preview_names = ['album-pictures-picture-015-before-after.png','album-pictures-picture-081-before-after.png',
                     'album-pictures-thumbnail-before-after.png']
    assert all((out/n).is_file() for n in preview_names)
    old_album = (ROOT/'work/output'/PRIOR/'ALBUM.AFS').read_bytes()
    old_positions = [struct.unpack_from('<II',old_album,8+i*8) for i in range(244)]
    note_offset = old_positions[81][0]
    note_capacity = min(o for o,_ in old_positions if o > note_offset) - note_offset
    assert note_capacity < 75958
    doc = {'version':VERSION,'source_build':PRIOR,
           'status':'English New Year greeting, Kasumi album note and three matching thumbnails packaged; source-estimated cleanup, independent review and live album behavior remain unverified',
           'disc':rel(disc_path),'archive':'ALBUM.AFS','archive_sha256':proof['archive_sha256'],
           'translation_map':'work/translation/en/ui/album-picture-text.en.json',
           'full_picture_members':[15,81],'thumbnail_ids':['album.214.014','album.214.025','album.214.086'],
           'changed_texture_members':[r['member'] for r in component['resources']],
           'previews':[{'path':rel(out/n),'sha256':digest((out/n).read_bytes())} for n in preview_names],
           'meaning':['The greeting is Happy New Year!, year 2000, with the original heart.',
                      'All ten existing source-fingerprinted story note rows are reused; only outer quotes/signature spacing become image layout.',
                      'The album note is rescaled independently from the story image. No new story/library row credit.'],
           'artwork_review':['Reviewed both full pictures and the three thumbnail witnesses.',
                             'The first note cleanup left faint old-letter fragments. Enlarged bounded ink regions and removed faint fragments without requiring a nearby dark core.',
                             'The independently authored thumbnail needs its own paper estimate; mapped text regions plus a one-pixel phase margin are cleaned against that source.',
                             'Revised full note and thumbnail previews reviewed. Estimated hidden paper and tiny thumbnail text still require independent/live review.'],
           'preservation':['239 unrelated member payloads and original DAT geometry exact.',
                           'All 224 caption areas, including 201 English captions and two original reading holds, exact.',
                           'Other 221 thumbnail photographs exact; only three matching photo regions change.',
                           'Greeting portrait/outside-header bytes and the original heart pairs exact.',
                           'All original note chroma/headers exact, luma edits limited to the visible 320x224 picture.'],
           'relocated_note':{'member':81,'offset':next(r['target_offset'] for r in component['resources'] if r['member']==81),
                             'packed_bytes':75958,'source_slot_bytes':note_capacity,'prefix_source_bytes':'verified zero'},
           'native_proof':proof,'validation':report['validation'],
           'new_changed_sectors':84,'changed_sector_locations_from_original':28390,
           'changed_album_sector_locations':{'before':432,'after':496,'new_locations':64},
           'normal_text_font_changed':False,'pending':report['pending'],'release':False,'story_library_draft_credit':0}
    caption_path = ROOT/'docs/album-captions.json'
    captions = read(caption_path)
    captions.update(status='201 English caption drafts retained unchanged in 0.1.30; two readings, independent meaning review and live album checks remain incomplete',
                    latest_combined_album_picture_build=doc)
    captions['pending'] = ['Two unresolved source caption readings','Independent caption meaning/context review',
                           'Native album loading/unlocks/selection/navigation and live caption appearance']
    audit_path = ROOT/'docs/non-movie-image-text-audit.json'
    audit = read(audit_path)
    audit.update(last_packaged_build=VERSION,album_captions=captions,album_pictures=doc)
    for finding in audit['remaining_findings']:
        if finding.get('archive') == 'ALBUM.AFS':
            finding.update(status='Caption IDs 082/102 remain original pending readings; English pictured text inserted with cleanup/artwork/live review pending',
                           translated_picture_members=[15,81],matching_thumbnail_artwork_pending=False)
            finding.pop('pictured_text_members',None)
    for item in audit['expanded_archive_audits']:
        if item['archive'] == 'ALBUM.AFS':
            item['visual_review'] = 'Original contacts/captions/context and English captions/picture/thumbnail witnesses reviewed; full-resolution absence and live review incomplete'
    old_limit = 'Album note/New Year pictured artwork and two source-caption readings remain untranslated'
    audit['expanded_audit_limits'] = [
        'Two album caption readings remain untranslated; pictured-text cleanup, meaning/artwork and live review pending'
        if p == old_limit else p for p in audit['expanded_audit_limits']]
    audit['completed_image_work'] = [r for r in audit.get('completed_image_work',[]) if (r.get('build'),r.get('archive')) != (VERSION,'ALBUM.AFS')]
    audit['completed_image_work'].append({'build':VERSION,'archive':'ALBUM.AFS','full_picture_count':2,
                                         'thumbnail_count':3,'scope':doc['status']})
    expanded_path = ROOT/'docs/expanded-image-audit.json'
    expanded = read(expanded_path)
    expanded.update(audits=audit['expanded_archive_audits'],limits=audit['expanded_audit_limits'])
    status_path = ROOT/'docs/translation-status.json'
    status = read(status_path)
    status.update(version=VERSION,
                  stage='English album greeting/note and matching thumbnails inserted over unchanged 0.1.29 game text/font/movies; two caption readings, other image formats/text, held passages, meaning/font/live and full-game review incomplete',
                  latest_album_picture_build=doc,latest_album_caption_build=captions,non_movie_image_text_audit=audit)
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(disc_path),kind=report['kind'],
                               changed_sectors=28390,validation=report['validation'],album_picture_delta_sectors=84,
                               ALBUM_sha256=proof['archive_sha256'],movie_component_origin_build=PRIOR,pending=report['pending'])
    status['test_disc'].pop('movie_delta_sectors',None)
    return [(ROOT/'docs/album-pictures.json',doc),(caption_path,captions),(audit_path,audit),
            (expanded_path,expanded),(status_path,status)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args = ap.parse_args()
    edits = record()
    print('PASS: 0.1.30, two pictures/three thumbnails, 201 English captions unchanged, five native streams, eleven exact payloads; 84 changed sectors, 64 newly changed original-disc locations.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path,data in edits:
        path.write_text(json.dumps(data,indent=2)+'\n','utf-8')


if __name__ == '__main__':
    main()
