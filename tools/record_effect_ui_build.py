"""Record checked local effect UI build 0.1.32. Dry run first."""
import argparse
import json

from build_bitmap_font import ROOT,digest
from build_effect_ui_disc import VERSION,PRIOR
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def relative(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    out=ROOT/'work/output'/VERSION
    report=read(out/'english-disc-report.json')
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    assert report['version']==VERSION and report['source_build']==PRIOR
    assert report['new_changed_sectors']==6 and report['total_changed_sector_locations_from_original']==28396
    assert report['validation']['reextracted_files']=='all 12 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    assert len(report['historical_native_evidence'])==20
    disc=Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries={r['path']:r for r in disc.inventory()}
    for name,info in report['files'].items():
        row=entries[name]
        raw=disc.read(row['lba'],row['size'])
        assert len(raw)==info['size'] and digest(raw)==info['sha256']
        if name!='EFFECT.AFS':
            assert info==previous['files'][name]
    for item in report['historical_native_evidence']:
        raw=(out/item['file']).read_bytes()
        assert digest(raw)==item['sha256']
        assert json.loads(raw)['executable_sha256']==item['executable_sha256']
    proof_raw=(out/'effect-ui-native-test.json').read_bytes()
    proof=json.loads(proof_raw)
    component=read(out/'effect-ui-component-report.json')
    assert proof==report['effect_ui_native_proof'] and component==report['effect_ui_component']
    assert digest(proof_raw)==report['effect_ui_proof_sha256']
    assert proof['archive_sha256']==report['files']['EFFECT.AFS']['sha256']
    assert proof['label_count']==9 and proof['protected_sprites']==116
    assert proof['native_PRS_instructions']==812606 and proof['native_texture_info_instructions']==175
    assert proof['native_guard_and_ABI']=='pass' and proof['archive_bytes_outside_declared_edits']=='exact'
    previews=[out/'effect-ui-labels-before-after.png',out/'effect-ui-atlas-bank-04-4x.png']
    assert all(p.is_file() for p in previews)
    doc={'version':VERSION,'source_build':PRIOR,
         'status':'Nine English effect/UI image label drafts packaged; four status icons and attack calligraphy remain untranslated, live/meaning/full-game review incomplete',
         'disc':relative(out/'disc'/f'Rayblade English Test {VERSION}.gdi'),
         'archive':'EFFECT.AFS','archive_sha256':proof['archive_sha256'],
         'changed_member':250,'label_count':9,
         'labels':[{'id':r['id'],'en':r['en'],'glossary_id':r['glossary_id']} for r in component['draws']],
         'translation_map':'work/translation/en/ui/effect-ui.en.json',
         'recipe_status_scope':'The source-linked draft recipe retains its pre-insertion preparation status/hash; this build record is the current insertion status',
         'previews':[{'path':relative(p),'sha256':digest(p.read_bytes())} for p in previews],
         'artwork_review':'All nine before/after native-index text witnesses reviewed using explicit bank 4 and Prana bank 0; live palette selection is unverified',
         'texture_dimensions':[256,256],'packed_bytes':10156,'original_slot_capacity':12288,
         'shared_suffix_resolution':'Standalone Barrier stays centered in its original cell; full Ballistic Barrier moves to unused atlas rectangle [0,208,96,224] with original screen size/center/raw parameter',
         'preservation':['All 16 stored palettes, NJTL declarations and packed texture parameters exact original',
                         'All 125 screen sizes/anchors, 124 complete sprite records, 116 other source sprites and 459 other archive members exact',
                         'Only sprite 094 UV coordinates and declared label indices change inside the decoded resource',
                         'All eleven preceding game payloads, including the normal font and both selected-logo subtitle movies, exact 0.1.31'],
         'native_proof':proof,'validation':report['validation'],
         'new_changed_sectors':6,'changed_sector_locations_from_original':28396,
         'normal_text_font_changed':False,'story_library_draft_credit':0,
         'pending':report['pending'],'release':False}
    # Japanese names/UI terms are permitted in the glossary. This supplement
    # is separate from the existing 851-entry story/library glossary.
    supplement={'project':'Seireiki Rayblade Dreamcast','status':'Source-linked UI editorial drafts',
                'source_archive_sha256':component['source_archive_sha256'],'entries':[]}
    for sprite,ja,en,id in [(89,'クリティカル','Critical','ui.effect.critical'),(107,'バリア','Barrier','ui.effect.barrier')]:
        row=next(r for r in component['draws'] if r['sprite']==sprite)
        supplement['entries'].append({'id':id,'category':'ui','ja':ja,'en':en,
                                       'source_ids':[row['id']],'source_box':row['source_box'],
                                       'source_index_sha256':row['source_index_sha256'],
                                       'status':'editorial_draft','inserted_build':VERSION})
    palette_path=ROOT/'docs/effect-palettes.json'
    palette=read(palette_path)
    palette.update(current_game_build=VERSION,status='All 459 source paletted atlases decoded; nine UI label drafts now inserted, remaining icons/calligraphy and full image/native/live review incomplete',
                   latest_UI_build=doc,English_drafts_not_inserted=0,English_drafts_inserted=9)
    expanded_path=ROOT/'docs/expanded-image-audit.json'
    expanded=read(expanded_path)
    effect=next(r for r in expanded['audits'] if r['archive']=='EFFECT.AFS')
    effect.update(latest_UI_build=VERSION,English_image_labels_inserted=9,icon_context_holds=4,
                  visual_review='Ten original palette/index contacts, selected full atlases, 125 source UI records and nine inserted English label witnesses reviewed; full-resolution/live review incomplete')
    audit_path=ROOT/'docs/non-movie-image-text-audit.json'
    audit=read(audit_path)
    audit.update(last_packaged_build=VERSION,effect_ui=doc,effect_palette_discovery=palette,
                 expanded_archive_audits=expanded['audits'],
                 status='Partial image-text audit: nine EFFECT UI labels inserted; remaining icons/calligraphy, image discovery and meaning/live review incomplete')
    audit['completed_image_work']=[r for r in audit.get('completed_image_work',[]) if (r.get('build'),r.get('archive'))!=(VERSION,'EFFECT.AFS')]
    audit['completed_image_work'].append({'build':VERSION,'archive':'EFFECT.AFS','label_count':9,'scope':doc['status']})
    status_path=ROOT/'docs/translation-status.json'
    status=read(status_path)
    status.update(version=VERSION,stage='Nine English native effect/UI labels inserted over unchanged 0.1.31 font/text/movies; four status icons, calligraphy, other images/held text, meaning/live and full-game review incomplete',
                  latest_effect_UI_build=doc,effect_palette_discovery=palette,non_movie_image_text_audit=audit)
    status['glossary']['effect_UI_supplement']={'path':'work/glossary/effect-ui.json','entries':2,
                                               'scope':'Additional UI terms; the existing 851-entry main glossary is unchanged'}
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=doc['disc'],kind=report['kind'],
                               changed_sectors=28396,validation=report['validation'],effect_UI_delta_sectors=6,
                               EFFECT_sha256=proof['archive_sha256'],pending=report['pending'])
    status['test_disc'].pop('font_delta_sectors',None)
    return [(ROOT/'docs/effect-ui.json',doc),(palette_path,palette),(expanded_path,expanded),
            (audit_path,audit),(status_path,status),(ROOT/'work/glossary/effect-ui.json',supplement)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    edits=record()
    print('PASS: 0.1.32, nine labels, twelve exact payloads, 20 historical identities; six sectors and native decoder/format/preservation checks pass.')
    if not args.write:
        print('DRY RUN: no documentation or glossary written')
        return
    for path,data in edits:
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    heading='## 0.1.32 — nine English native effect/UI image labels'
    entry='''## 0.1.32 — nine English native effect/UI image labels

- Inserted source-linked English drafts for Prana, Critical, Evade, Guard, Plasma Coating, Plasma Barrier, Ballistic Barrier, Special Field and Barrier in EFFECT member 250. Battle results use action wording Evade/Guard while glossary stat nouns remain Evasion/Defense. Added two source-linked UI glossary terms as a separate supplement; the main 851-entry story/library glossary and its draft counts are unchanged. Four single-kanji status icons and attack calligraphy retain explicit context/reading holds.
- Retained every original external palette and raw texture parameter. English uses the existing light-stroke/edge/shadow index roles. The full Ballistic Barrier moves into unused [0,208,96,224] atlas space to preserve naturally centered full text and the independently centered shared Barrier suffix. All screen sizes/anchors, 124 complete sprite records, 116 protected source sprites and 459 other archive member payloads/offsets stay exact. Texture remains 256x256 PAL4; 10,156 compressed bytes fit the original 12,288-byte slot. No normal-font change, per-letter stretch or emulator texture replacement.
- Reviewed all nine before/after native-index witnesses using explicit bank 4 and Prana bank 0. Independent checks verify all 65,536 index pixels, 256 palette entries, 3,544 source-font mask samples, 125 geometry records, archive bounds/nonoverlap and exact bytes/pixels outside declared edits. Actual native PRS executes 812,606 SH-4 instructions for 36,288 exact bytes; the PAL4 texture-info routine executes 175 instructions and returns exact format/dimensions/storage size, with guards/ABI preserved. Native archive I/O, runtime palette selection, sprite submission and GPU appearance remain untested.
- Packaged local build 0.1.32: six effect/UI sector substitutions, 28,396 locations changed from original. All twelve game payloads re-extract exactly; changed-sector EDC/ECC, unchanged ISO inventory and comparison of all 1,188,856,032 track bytes pass. Eleven prior game payloads and twenty historical native proof identities remain exact, including the inferred Latin font and selected-logo subtitle movies. Shared historical-proof wording now covers the real component scope without calling the font proof an archive-decoding test. Original dump and prior builds untouched; no release.
- Full effect/image discovery, four icon contexts, calligraphy readings, two album captions, held passages, independent meaning/artwork/font review and live/full-game validation remain incomplete. This build does not establish full translation completion.

'''
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded build, glossary supplement and change log; full goal remains incomplete.')


if __name__=='__main__':
    main()
