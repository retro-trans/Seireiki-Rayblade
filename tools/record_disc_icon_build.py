"""Record the packaged 0.1.36 disc-icon caption and exact preservation."""
import argparse
import json

from build_bitmap_font import ROOT,digest
from build_disc_icon_subtitle_disc import VERSION,PRIOR,plan
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    out=ROOT/'work/output'/VERSION
    report=read(out/'english-disc-report.json')
    assert {k:v for k,v in report.items() if k!='validation'}==plan()[-1]
    assert report['new_changed_sectors']==4 and report['total_changed_sector_locations_from_original']==28450
    assert report['validation']['reextracted_files']=='all 14 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    path=out/'disc'/f'Rayblade English Test {VERSION}.gdi'
    disc=Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries={r['path']:r for r in disc.inventory()}
    for name,info in report['files'].items():
        row=entries[name]
        raw=disc.read(row['lba'],row['size'])
        assert len(raw)==info['size'] and digest(raw)==info['sha256']
        if name!='0GDTEX.PVR':
            assert info==previous['files'][name]
    assert len(report['historical_native_evidence'])==24
    for item in report['historical_native_evidence']:
        raw=(out/item['file']).read_bytes()
        assert digest(raw)==item['sha256'] and json.loads(raw)['executable_sha256']==item['executable_sha256']
    proof_raw=(out/'disc-icon-native-test.json').read_bytes()
    proof=json.loads(proof_raw)
    component=read(out/'disc-icon-component-report.json')
    assert proof==report['disc_icon_native_proof'] and component==report['disc_icon_component']
    assert digest(proof_raw)==report['disc_icon_proof_sha256']
    assert proof['archive_sha256']==report['files']['0GDTEX.PVR']['sha256']
    assert proof['changed_pixels']==566 and proof['protected_source_alpha_bits']==65536
    assert proof['protected_bright_source_pixels']==12936 and proof['scalar_texture_pixels']==65536
    assert proof['native_guard_and_ABI']=='pass' and proof['archive_bytes_outside_declared_edits']=='exact'
    preview=out/'disc-icon-before-after.png'
    summary={'version':VERSION,'source_build':PRIOR,'file':'0GDTEX.PVR',
             'status':'Original disc artwork with English identification subtitle packaged; actual BIOS/Flycast icon appearance/readability unverified',
             'disc':rel(path),'file_sha256':proof['archive_sha256'],'dimensions':[256,256],
             'subtitle':'SEIREIKI RAYBLADE','treatment':'Original artwork + English subtitle',
             'changed_pixels':566,'protected_alpha_bits':65536,'protected_bright_artwork_pixels':12936,
             'normal_font_changed':False,'recipe':'work/translation/en/ui/disc-icon-subtitle.en.json',
             'preview':rel(preview),'preview_sha256':digest(preview.read_bytes()),
             'native_report':rel(out/'disc-icon-native-test.json'),'native_report_sha256':digest(proof_raw),
             'new_changed_sectors':4,'changed_locations_from_original':28450,
             'validation':report['validation'],'pending':report['pending'],'release':False,
             'story_library_draft_credit':0}
    doc={**summary,'source_file_sha256':component['source_archive_sha256'],
         'layout':component['recipe'],'current_font_sha256':component['font_sha256'],
         'method':'Two words use the same original native cap band, scale and baseline; widened interword space avoids the central blade tip. Native ARGB1555 outline/coverage only.',
         'preservation':'All source alpha bits, source channels above 12/31, complete PVR header, source dimensions, file length and every pixel outside caption strokes stay exact',
         'first_preview_rejected':'One-line caption at y247 crossed the circular alpha silhouette; not packaged',
         'component':component,'native_proof':proof}
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    audit.update(last_packaged_build=VERSION,disc_icon=summary,
                 status='Partial image-text audit: English identification subtitle added to original disc icon; other image/text coverage and independent/live/full-game review incomplete')
    audit['completed_image_work']=[r for r in audit.get('completed_image_work',[]) if r.get('build')!=VERSION]
    audit['completed_image_work'].append({'build':VERSION,'file':'0GDTEX.PVR','subtitle_count':1,'scope':summary['status']})
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,stage='English subtitle added to original disc-selection artwork; remaining text/images and independent/live/full-game validation incomplete',
                  latest_disc_icon_build=summary,non_movie_image_text_audit=audit)
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(path),kind=report['kind'],
                               changed_sectors=28450,disc_icon_delta_sectors=4,
                               disc_icon_sha256=proof['archive_sha256'],validation=report['validation'],pending=report['pending'])
    status['test_disc'].pop('system_profiles_delta_sectors',None)
    coordinates={'build':VERSION,'file':'0GDTEX.PVR','texture_dimensions':[256,256],
                 'source_kind':'Native disc-selection artwork; preview is not a live screenshot',
                 'words':component['word_masks'],'stroke_bounds':component['recipe']['stroke_bounds'],
                 'caption_preview':rel(preview),'alpha_silhouette':'byte-exact source',
                 'actual_BIOS_Flycast_appearance':'pending'}
    return [(ROOT/'docs/disc-icon.json',doc),(ROOT/'work/ui/disc-icon.json',coordinates),
            (ROOT/'docs/non-movie-image-text-audit.json',audit),(ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: original alpha/bright art retained; fourteen exact disc payloads, 24 historical proofs; four icon-sector substitutions.')
    if not args.write:
        print('DRY RUN: no records/change log written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,indent=2)+'\n','utf-8')
    heading='## 0.1.36 — English identification below the original disc icon logo'
    entry='''## 0.1.36 — English identification below the original disc icon logo

- Added SEIREIKI RAYBLADE to the native 0GDTEX.PVR disc-selection image, applying the original-artwork-plus-English-subtitle treatment. Reuses the current inferred Latin masks/advances at a common 1/5 scale and cap band; two words share a baseline and leave space for the logo's central blade tip. The first one-line preview crossed the circular alpha silhouette and was rejected before packaging. Final comparison reviewed offline; actual BIOS/Flycast icon appearance and small-caption readability remain unverified.
- Changes 566 native ARGB1555 pixels while retaining all 65,536 source alpha bits and all 12,936 bright artwork pixels (any source channel above 12/31), the complete source PVR header, 256x256 dimensions, file size and every pixel outside the caption strokes. No normal-font change, per-letter stretching, texture replacement or Japanese-logo removal. Independent scalar texture/font assembly/compositing and native SDK texture-header execution pass. The initial fixture used a pixel-format value in the storage-layout position; corrected to the actual packed 0x100 source format before the successful check. No BIOS renderer/GPU proof or PRS-compression claim applies.
- Extended the shared packager to support native PVR files and partial final file sectors. This 131,104-byte file has a 32-byte final payload portion. Read-only synthetic changes against real source sectors verify full-sector parity with the prior method, preservation of all 2,016 padding bytes for the final tail, unchanged source headers and valid EDC/ECC. The preceding AFS build plan still matches its recorded proof. No original track or previous build changed.
- Packaged local build 0.1.36: four sector substitutions and 28,450 locations changed from original. All fourteen modified game payloads re-extract exactly; changed-sector EDC/ECC, unchanged ISO inventory and comparison of all 1,188,856,032 track bytes pass. Thirteen preceding payloads, current font, all existing text/profiles/icons/artwork/movies and twenty-four historical native proof identities remain exact. No release.
- No new story/library draft credit. Remaining image/encoded-text discovery, unresolved caption/name readings, held passages, independent meaning/artwork/font review and live/full-game validation remain incomplete.

'''
    log=ROOT/'CHANGELOG.md'
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded disc-icon treatment, build status and change log; full translation remains incomplete.')


if __name__=='__main__':
    main()
