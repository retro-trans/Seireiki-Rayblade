"""Record all 203 album caption drafts and the 0.1.37 two-caption insertion."""
import argparse
import copy
import json

from build_album_caption_readings_disc import VERSION,PRIOR,plan
from build_bitmap_font import ROOT,digest
from disc_inventory import Disc
from prepare_album_caption_readings import DEST,OUT as READING_OUT


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    out=ROOT/'work/output'/VERSION
    report=read(out/'english-disc-report.json')
    assert {k:v for k,v in report.items() if k!='validation'}==plan()[-1]
    assert report['new_changed_sectors']==15 and report['total_changed_sector_locations_from_original']==28450
    assert report['source_archive_changed_locations_from_original']==report['target_archive_changed_locations_from_original']
    assert report['validation']['reextracted_files']=='all 14 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    disc_path=out/'disc'/f'Rayblade English Test {VERSION}.gdi'
    disc=Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries={r['path']:r for r in disc.inventory()}
    for name,info in report['files'].items():
        row=entries[name]
        raw=disc.read(row['lba'],row['size'])
        assert len(raw)==info['size'] and digest(raw)==info['sha256']
        if name!='ALBUM.AFS':
            assert info==previous['files'][name]
    assert len(report['historical_native_evidence'])==25
    for item in report['historical_native_evidence']:
        raw=(out/item['file']).read_bytes()
        assert digest(raw)==item['sha256'] and json.loads(raw)['executable_sha256']==item['executable_sha256']
    proof_raw=(out/'album-caption-readings-native-test.json').read_bytes()
    proof=json.loads(proof_raw)
    component=read(out/'album-caption-readings-component-report.json')
    assert proof==report['album_caption_readings_native_proof'] and component==report['album_caption_readings_component']
    assert digest(proof_raw)==report['album_caption_readings_proof_sha256']
    assert proof['archive_sha256']==report['files']['ALBUM.AFS']['sha256']
    assert proof['native_PRS_instructions']==5936625 and proof['source_font_mask_samples']==936
    assert proof['combined_caption_count']==203 and proof['unresolved_caption_ids']==[]
    assert proof['native_guard_and_ABI']=='pass' and proof['archive_bytes_outside_declared_edits']=='exact'
    override=read(DEST)
    old_path=ROOT/'work/translation/en/ui/album-captions.en.json'
    old_recipe=read(old_path)
    override_rows={r['id']:r for r in override['rows']}
    combined_rows=[]
    for row in old_recipe['rows']:
        item=copy.deepcopy(row)
        if row['id'] in override_rows:
            revised=override_rows[row['id']]
            assert not row['en'] and row['source_caption_sha256']==revised['source_caption_sha256']
            item.update(en=revised['en'],wrapped_lines=revised['wrapped_lines'],
                        status='Draft inserted in 0.1.37; independent reading/meaning and live review pending',
                        decision=revised['decision'],reading_evidence=rel(DEST))
        combined_rows.append(item)
    # The recipe excludes the 21 source Coming Soon tiles from its row list.
    assert len(combined_rows)==203 and all(r['en'] for r in combined_rows)
    current_map={'version':VERSION,'status':'All 203 nonblank source captions drafted and inserted; independent meaning/readings and live review pending',
                 'source':old_recipe['source'],'source_archive_sha256':old_recipe['source_archive_sha256'],
                 'base_recipe':rel(old_path),'base_recipe_sha256':digest(old_path.read_bytes()),
                 'override_recipe':rel(DEST),'override_recipe_sha256':digest(DEST.read_bytes()),
                 'font_sampling':old_recipe['font_sampling'],'caption_count':203,
                 'source_gallery_sprite_count':224,'preserved_Coming_Soon_cells':21,'unresolved_caption_ids':[],
                 'rows':combined_rows,'story_library_draft_credit':0}
    map_path=ROOT/'work/translation/en/ui/album-captions-current.en.json'
    preview=out/'album-caption-readings-before-after.png'
    glyph_preview=READING_OUT/'source-glyph-references.png'
    assert preview.is_file() and glyph_preview.is_file()
    summary={'version':VERSION,'source_build':PRIOR,'archive':'ALBUM.AFS',
             'status':'All 203 nonblank source album captions have inserted English drafts; independent reading/meaning and live review incomplete',
             'disc':rel(disc_path),'archive_sha256':proof['archive_sha256'],
             'caption_count':203,'source_caption_count':203,'new_caption_count':2,'unresolved_caption_ids':[],
             'new_captions':[{'id':r['id'],'en':r['en']} for r in override['rows']],
             'translation_map':rel(map_path),'override_recipe':rel(DEST),
             'caption_preview':rel(preview),'caption_preview_sha256':digest(preview.read_bytes()),
             'glyph_reading_reference':rel(glyph_preview),'glyph_reading_reference_sha256':digest(glyph_preview.read_bytes()),
             'reading_scope':'Manual shape reading with original-game and local Japanese-font reference forms, not an exact-pixel OCR/font identity proof',
             'native_report':rel(out/'album-caption-readings-native-test.json'),'native_report_sha256':digest(proof_raw),
             'native_PRS_instructions':5936625,'native_scalar_texture_pixels':131072,
             'preservation':'Other 201 English captions, 21 Coming Soon cells, all 224 photos, all geometry and other 242 members exact previous build',
             'normal_text_font_changed':False,'new_changed_sectors':15,'changed_locations_from_original':28450,
             'validation':report['validation'],'pending':report['pending'],'story_library_draft_credit':0,'release':False}
    prior=read(ROOT/'docs/album-captions.json')
    historical=prior.get('historical_201_caption_build',prior)
    doc={**summary,'source_readings':[{'id':r['id'],'ja_ui':r['ja_ui'],'en':r['en'],
                                     'source_caption_sha256':r['source_caption_sha256'],
                                     'first_glyph_reference':r['first_glyph_reference'],'decision':r['decision']} for r in override['rows']],
         'native_proof':proof,'resources':component['resources'],
         'historical_201_caption_build':historical,
         'history_scope':'Original 0.1.28 recipe/proof retained under its actual tested identity; two fresh changed-stream/pixel checks cover this build. No full native album loading/reachability proof is claimed.'}
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    audit.update(last_packaged_build=VERSION,album_captions=doc,
                 status='Partial image-text audit: all 203 album caption drafts inserted; remaining image/encoded-text discovery and independent/live/full-game review incomplete')
    for finding in audit['remaining_findings']:
        if finding.get('archive')=='ALBUM.AFS':
            finding.update(status='All 203 source captions drafted and inserted; original reading holds closed, independent meaning/readings and live artwork/album behavior remain pending',
                           unresolved_caption_ids=[],latest_caption_build=VERSION)
    audit['completed_image_work']=[r for r in audit.get('completed_image_work',[]) if r.get('build')!=VERSION]
    audit['completed_image_work'].append({'build':VERSION,'archive':'ALBUM.AFS','new_caption_count':2,
                                         'combined_caption_count':203,'scope':summary['status']})
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,stage='All 203 album captions now have inserted English drafts; remaining text/images, independent meaning/artwork/font and live/full-game validation incomplete',
                  latest_album_caption_build=summary,non_movie_image_text_audit=audit)
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(disc_path),kind=report['kind'],
                               changed_sectors=28450,album_caption_readings_delta_sectors=15,
                               ALBUM_sha256=proof['archive_sha256'],validation=report['validation'],pending=report['pending'])
    status['test_disc'].pop('disc_icon_delta_sectors',None)
    glossary={'scope':'Two short album UI caption readings, no story/library draft credit',
              'inserted_build':VERSION,'entries':[{'id':r['id'],'ja_ui':r['ja_ui'],'en':r['en'],
                                                'source_sha256':r['source_caption_sha256'],
                                                'status':'Manual source reading/draft; independent review pending'} for r in override['rows']]}
    return [(map_path,current_map),(ROOT/'docs/album-captions.json',doc),
            (ROOT/'work/glossary/album-caption-readings.json',glossary),
            (ROOT/'docs/non-movie-image-text-audit.json',audit),(ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: 203 combined caption drafts, fourteen exact disc payloads, 25 historical proofs; fifteen substitutions, no new original-disc locations.')
    if not args.write:
        print('DRY RUN: no combined recipe/records/change log written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    text=log.read_text('utf-8')
    heading='## 0.1.37 — resolve and insert the last two album caption drafts'
    entry='''## 0.1.37 — resolve and insert the last two album caption drafts

- Resolved caption 082 as 裸のトウヤ (Naked Touya) and 102 as 弱々しい目のアルフォリナ (Alforina's Feeble Gaze). Manual glyph-shape inspection compares the clothing-plus-fruit structure of 裸 and paired bow shapes of 弱 with original-game glyph references 2075/1332 and local Japanese-font forms. Earlier 裏/影/素 and other adjective guesses did not fit those shapes. This is editorial reading evidence, not an exact font match or automatic OCR proof. The first caption is literal and non-graphic; no erotic/anatomical or invented scene detail added. Independent readings/wording review remains pending.
- Inserted both full captions in their original 64x24 cells using the same uniform 1/3 bitmap area coverage as the preceding 201 captions. Alforina's / Feeble Gaze uses two balanced lines. Native resources 225/227 shrink to 30,018/31,742 bytes and stay in their original slots. Source pictures, the 201 existing English caption cells, 21 Coming Soon cells, all 224 photograph regions, all geometry, normal font and other 242 archive member payloads/offsets remain exact previous build.
- Independent scalar checks verify 131,072 texture pixels, 936 source-font mask samples, backgrounds/full cell replacement and archive/pixel bounds. Two actual original PRS decodes execute 5,936,625 SH-4 instructions for 262,208 exact bytes; native texture-header helpers execute 372. Guards/ABI pass. Actual album loading, selection/unlocks/navigation and GPU/live appearance remain unverified; byte tests do not prove Japanese meaning.
- Packaged local build 0.1.37: fifteen sector substitutions, all within already changed locations, leaving 28,450 locations changed from original. All fourteen payloads re-extract exactly; changed-sector EDC/ECC, ISO inventory and comparison of all 1,188,856,032 track bytes pass. Thirteen unaffected game payloads and twenty-five historical native proof identities remain exact. Original dumps/earlier builds untouched; no release.
- Published a combined current 203-caption draft map while preserving the historical 201-caption recipe and native proof under their actual tested identities. All nonblank source album captions now have English drafts; source reading holds are closed. This is not independent meaning/artwork review or live/full-game completion. Other image/encoded-text discovery, held passages and remaining reviews/tests continue; no story/library draft credit.

'''
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded all 203 caption drafts and exact historical evidence; full translation remains incomplete.')


if __name__=='__main__':
    main()
