"""Record packaged English image-label evidence. Default dry run."""
import argparse,json
from build_ui_atlas_patch import ROOT,VERSION,PRIOR,compose,digest
from prepare_ui_atlas_translation import DEST


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION;read=lambda p:json.loads(p.read_text('utf-8'))
    files,component,_=compose()
    for name in ('1ST_READ.BIN','WIN00.AFS','D_SCE.AFS','text/D_NAMES.BIN','text/D_PAPER.en.dec.bin'):
        assert files[name]==(out/name).read_bytes()
    proof=read(out/'ui-image-native-test.json');chapter=read(out/'chapter-card-native-test.json');disc=read(out/'english-disc-report.json');manifest=read(out/'font4x-patch.json');recipe=read(DEST)
    assert proof['archive_sha256']==chapter['archive_sha256']==digest(files['WIN00.AFS'])
    assert proof['executable_sha256']==chapter['executable_sha256']==digest(files['1ST_READ.BIN'])
    assert proof['label_sprites']==35 and proof['protected_sprites']==277 and proof['unrelated_archive_members']==87
    assert disc['files']['WIN00.AFS']['sha256']==proof['archive_sha256'] and disc['validation']=={'reextracted_files':'all 5 exact','changed_sector_EDC_ECC':'pass','unrelated_ISO_entries':'unchanged','in_game':'pending'}
    record={'version':VERSION,'source_build':PRIOR,'status':'35 English image-label sprites integrated and locally packaged; native PRS/texture checks and protected-pixel checks pass; live appearance/selection pending',
        'label_sprites':proof['label_sprites'],'distinct_display_strings':len({r['en'] for r in recipe['rows']}),'texture_members':[r['member'] for r in proof['resources']],
        'translation_map':'work/translation/en/ui/image-labels.en.json','source_sprite_map':'work/ui/asset-audit/ui-sprites/rectangles.json','resources':proof['resources'],
        'protected_sprite_count':proof['protected_sprites'],'unrelated_archive_members':proof['unrelated_archive_members'],'native_PRS_instructions':proof['native_PRS_instructions'],'native_texture_info_instructions':proof['native_texture_info_instructions'],
        'independent_font_mask_pixels':proof['independent_font_mask_pixels'],'archive_spare_bytes':component['archive_spare_bytes'],'unchanged':'Executable, integrated normal-text font, sprite DAT records and every text component exact 0.1.19',
        'proof':f'work/output/{VERSION}/ui-image-native-test.json','chapter_proof':f'work/output/{VERSION}/chapter-card-native-test.json','preview':f'work/output/{VERSION}/ui-image-labels-preview.png',
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi','packaging':disc['validation'],'limits':proof['limits'],'story_library_draft_credit':0}
    results={ROOT/'docs/ui-image-labels.json':record}
    manifest.update(status=record['status']);manifest['ui_images'].update(packaging=disc['validation'],pending=['Live image appearance and actual selection routes'])
    results[out/'font4x-patch.json']=manifest
    p=ROOT/'docs/translation-status.json';d=read(p);d.update(version=VERSION,stage='Battle/trust image labels now English; drafted text, wrapped library and corrected native headers packaged; held passages, independent review, other image/movie audit and full-game validation incomplete',latest_ui_image_build=record)
    d['test_disc'].update(version=VERSION,path=record['disc'],changed_sectors=disc['changed_sectors'],validation=disc['validation'])
    d['image_text_audit'].update(battle_and_trust_atlases=record,English_image_insertion='69 chapter-title slots and Chapter label remain inserted; 35 battle/trust/event/name image-label sprites added in 0.1.20; live image validation pending',remaining='Other title/logo images, complete ADV/background and movie-caption audit, actual display routes and live appearance remain pending')
    d['library']['disc_integration']=manifest['library'];results[p]=d
    p=ROOT/'docs/ui-layout.json';d=read(p);d['ui_image_build']=record;results[p]=d
    # Keep historical font/chapter/native reports at their actually tested
    # versions. Only the changed archive has fresh 0.1.20 witnesses.
    p=ROOT/'CHANGELOG.md';log=p.read_text('utf-8')
    before='Native resource checks and packaging are pending.'
    after=f"Native checks pass three PRS decodes ({proof['native_PRS_instructions']:,} instructions) and three actual texture-info/size cases. Independent pixel addressing/source-font fit, 277 protected sprites, pixels outside selected cells and 87 unrelated archive members pass. Fresh chapter checks pass against the repacked archive. Local packaging re-extracts all five files exactly, validates {disc['changed_sectors']:,} changed sectors and preserves unrelated ISO entries."
    assert before in log or after in log
    print(json.dumps(record,indent=2))
    if not args.write:print('DRY RUN: no documentation written');return
    for p,d in results.items():p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
    (ROOT/'CHANGELOG.md').write_text(log.replace(before,after,1),'utf-8')
    p=out/'READ-ME.txt';note='\n0.1.20 translates 35 battle/trust image-label sprites, including the red Event marker and 15 short name tabs. Texture dimensions/resource IDs and all text/font code stay unchanged. Native resource and local disc checks pass; actual Flycast image appearance/selection and full translation validation remain pending.\n'
    if note.strip() not in p.read_text('utf-8'):p.write_text(p.read_text('utf-8')+note,'utf-8')
    print('Recorded English image labels, native resource checks, local disc and explicit live-validation limits.')


if __name__=='__main__':main()
