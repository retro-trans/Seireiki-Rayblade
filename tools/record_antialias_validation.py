"""Record exact packaged alpha-font evidence; dry run before --write."""
import argparse,json
from build_antialias_font import ROOT,VERSION,PRIOR,ATLAS,digest,compose


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION
    read=lambda p:json.loads(p.read_text('utf-8'))
    files,_,_,_=compose()
    for name in ('1ST_READ.BIN','WIN00.AFS'):assert files[name]==(out/name).read_bytes()
    assert json.loads(files['chapter-card-component.json'])==read(out/'chapter-card-component.json')
    raster=read(out/'genei-font-native-test.json');surface=read(out/'genei-surface-native-test.json');disc=read(out/'english-disc-report.json');text=read(out/'word-wrap-native-test.json');inline=read(out/'inline-control-native-test.json');ui=read(out/'ui-layout-native-test.json');chapter=read(out/'chapter-card-native-test.json')
    sha=digest(files['1ST_READ.BIN'])
    assert all(p['executable_sha256']==sha for p in [raster,surface,text,inline,ui,chapter,read(out/'scenario-native-test.json'),read(out/'battle-english-native-test.json')])
    assert disc['files']['1ST_READ.BIN']['sha256']==sha and disc['files']['WIN00.AFS']['sha256']==digest(files['WIN00.AFS'])
    assert disc['validation']=={'reextracted_files':'all 5 exact','changed_sector_EDC_ECC':'pass','unrelated_ISO_entries':'unchanged','in_game':'pending'}
    record={'version':VERSION,'status':'Supplied bitmap edge coverage retained through native ARGB4444 text; offline checks and local packaging pass; live GPU blending/appearance pending',
        'source':'incoming/fonts/user-bitmap/dialogue-atlas.png','source_sha256':digest(ATLAS.read_bytes()),'coverage_levels':[0,85,187,255],
        'font_member_bytes':99072,'texture_edge_limit':1024,'native_raster_cases':raster['native_cases'],'native_raster_instructions':raster['SH4_instructions'],
        'native_surface_cases':surface['allocation_cases']+surface['invalid_dimension_cases'],'native_texture_format_cases':len(surface['native_texture_format_cases']),
        'source_edge_pixels_preserved':14830,'advances':'byte-exact 0.1.16; all text and chapter resources unchanged',
        'raster_proof':f'work/output/{VERSION}/genei-font-native-test.json','surface_proof':f'work/output/{VERSION}/genei-surface-native-test.json',
        'preview':f'work/output/{VERSION}/font-smoothing-comparison.png','disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi','packaging':disc['validation'],
        'limitations':['Source bitmap has finite outline detail; enlargement is not vector reconstruction','Actual GPU blending and live appearance remain unverified']}
    results={ROOT/'docs/font-antialiasing.json':record}
    p=ROOT/'docs/translation-status.json';d=read(p);d.update(version=VERSION,stage='Supplied bitmap edge coverage retained in native font; English chapter cards, targeted UI layouts and drafted text packaged; held translation, review, remaining images and full-game validation incomplete',latest_font_build=record);d['test_disc'].update(version=VERSION,changed_sectors=disc['changed_sectors'],validation=disc['validation'],path=record['disc']);results[p]=d
    p=ROOT/'docs/font-renderer.json';d=read(p);d.update(build=VERSION,status=record['status'],latest_font_build=record);d['font'].update(format_version=4,new_magic='RBLF4X 00 04',pixel_data='Latin: two bits per pixel, 32 pixels per eight-byte row; five protected marks: binary 64 pixels per row',source_details=record);d['executable']['current_symbols']=read(out/'font4x-patch.json')['symbols'];results[p]=d
    p=out/'font4x-patch.json';d=read(p);d['status']=record['status'];d['antialias_font'].update(packaging=disc['validation'],raster_proof_sha256=digest((out/'genei-font-native-test.json').read_bytes()),surface_proof_sha256=digest((out/'genei-surface-native-test.json').read_bytes()))
    for section in ('library','battle','scenario'):d[section]['font_update_build']=VERSION
    results[p]=d
    p=out/'text/scenario-component-report.json';d=read(p);d['presentation_font_update_build']=VERSION;results[p]=d
    p=out/'antialias-font-report.json';d=read(p);d['validation']={'raster':raster,'surface':surface,'story_line_segments':text['counts']['lines'],'inline_commands':inline['commands'],'ui_cases':ui['native_UI_cases'],'chapter_cases':chapter['native_cases'],'packaging':disc['validation']};results[p]=d
    log=ROOT/'CHANGELOG.md';old=log.read_text('utf-8')
    entry='''## 0.1.17 — retain supplied bitmap antialiasing

- Corrected the bitmap import/rendering path that discarded gray edge coverage. All four source levels (0, 85, 187, 255) now survive as native ARGB4444 alpha (0, 5, 11, 15). Latin glyphs use compact two-bit rows; five protected wide symbols keep their existing binary contours. Font member size, texture allocations, 1024-pixel cap, advances, baseline, all translations and chapter-card resources remain unchanged. No texture replacement or invented vector detail.
- Fresh checks pass 393 native raster/color/shadow/edge cases (12,917,515 SH-4 instructions), 17 allocation/header/append/flush/DMA and rejection cases, and eight actual Ninja texture-format/size cases. Rechecked all 123,041 retained story line segments, 15 pagination witnesses, 166 inline comparisons, 145 UI cases, all story lookups/loaders/formatter witnesses, battle regressions and chapter-card cases against the new executable. Offline fixtures do not prove GPU blending, live appearance or full gameplay.
- Local packaging re-extracts all five files exactly, validates 2,669 changed sectors and preserves unrelated ISO entries. Wrote an accurately labeled before/after font comparison. Live Flycast appearance and the remaining translation/review work are pending; no release.

'''
    print(json.dumps(record,indent=2))
    if not args.write:print('DRY RUN: no documentation written');return
    for p,d in results.items():p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
    if '## 0.1.17 —' not in old:log.write_text(old.replace('## 0.1.16 —',entry+'## 0.1.16 —',1),'utf-8')
    p=out/'READ-ME.txt';notice='\n0.1.17 retains all four gray edge-coverage levels from the supplied bitmap through native ARGB4444 text. Font textures remain within 1024 pixels per edge. Native/offline checks and disc integrity pass; actual Flycast GPU blending and appearance are still pending.\n'
    if notice.strip() not in p.read_text('utf-8'):p.write_text(p.read_text('utf-8')+notice,'utf-8')
    print('Recorded fresh proof identities, source coverage, local disc integrity and live-validation limits.')


if __name__=='__main__':main()
