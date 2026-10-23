"""Record bounded palette discovery and UI drafts. Default dry run.

This is documentation only: no build increment, game asset edit or release.
"""
import argparse
import json

from build_bitmap_font import ROOT, digest
from prepare_effect_ui_translation import DEST, prepare

DOC = ROOT/'docs/effect-palettes.json'


def load(path):
    return json.loads((ROOT/path).read_text('utf-8'))


def witness(path):
    source=ROOT/path
    assert source.is_file()
    return {'path':path, 'sha256':digest(source.read_bytes())}


def plan():
    index_path='work/ui/asset-audit/EFFECT/palette-01/texture-index.json'
    index=load(index_path)
    assert (index['decoded_atlases'],index['palette_banks'],index['palette_entries'])==(459,4230,67680)
    assert index['unsupported_or_failed']==[]
    recipe,_=prepare()
    assert load(str(DEST.relative_to(ROOT)))==recipe
    contacts=[witness(f'work/ui/asset-audit/EFFECT/palette-01/{kind}-contact-{page:02d}.png')
              for kind in ('bank-zero','indices') for page in range(5)]
    ui=[witness(f'work/ui/asset-audit/EFFECT/ui-250/sprites-{page:02d}.png') for page in range(4)]
    ui += [witness('work/ui/asset-audit/EFFECT/ui-250/'+name)
           for name in ['atlas-4x.png','text-candidates-bank-04.png','english-drafts.png']]
    checks=index['independent_scalar_checks']
    doc={'status':'All wrapped 4-bit atlas sources decoded; further untranslated image text discovered; no game edit',
         'current_game_build':'0.1.31',
         'archive':'EFFECT.AFS','source_archive_sha256':index['source_archive_sha256'],
         'archive_members':460,'decoded_atlases':459,'palette_banks':4230,'palette_entries':67680,
         'resources_with_extra_palette_banks':75,
         'last_member':index['last_member'],
         'index':witness(index_path),
         'independent_scalar_checks':checks,
         'independently_checked_index_pixels':sum(r['pixels'] for r in checks),
         'independently_checked_palette_entries':sum(r['palette_entries'] for r in checks),
         'source_contact_sheets_reviewed':contacts,
         'UI_source_and_draft_sheets_reviewed':ui,
         'source_geometry':witness('work/ui/asset-audit/EFFECT/ui-250/rectangles.json'),
         'UI_sprite_count':125,
         'translation_map':witness(str(DEST.relative_to(ROOT)).replace('\\','/')),
         'English_drafts_not_inserted':9,'icon_context_holds':4,
         'findings':[
             {'member':250,'name':'map_dc','classification':'Confirmed Japanese battle/UI image text',
              'details':'Nine readable full text sprites drafted; four single-kanji state icons on context hold; sprite 088 ornament/glyph still unclassified. Sprite 107 shares the Barrier suffix region of sprite 094.'},
             {'members':[142,143,455,456],'classification':'Calligraphic kanji artwork candidates',
              'details':'Member 142 full source viewed: upper glyph appears to be 破; lower reading and combined phrase remain unresolved. Other listed members identified on contacts; no guessed translation.'},
             {'members':[289,292],'classification':'Initial text-like contact candidates resolved as mech/effect silhouettes in full source views'},
             {'member':312,'classification':'Tiny console/display artwork remains unclassified',
              'details':'English-looking Missile/Shell headings; smaller marks need enlarged source/context review. No definite Japanese claim.'},
             {'members':[251,288,353,354],'classification':'Existing English headings observed',
              'details':'LEVEL UP!! / GAME OVER / Big Bang. Not a full-resolution absence claim for the rest of those atlases.'},
             {'members':[438,439],'classification':'Large spiral/glyph candidates need full-resolution/context inspection'}],
         'corrected_discovery_assumptions':[
             'Initial NJTL declaration count does not equal all stored palette banks: 75 resources contain extra banks. All stored banks are now accounted for without invented runtime bindings.',
             'Filename list includes EFFECT.ALS self-reference and DOS EOF; Windows directory components are normalized for all 459 PVM name checks.',
             'UI geometry ends in zero width plus ten 0xff bytes, not all-zero padding. Exact terminator is now checked.'],
         'format_references':index['format_references'],
         'limits':[
             'Bank-zero and false-color source-index sheets are discovery aids; all 4230 runtime palette/blend states were not visually checked.',
             'Palette selector/texture parameter interpretation, native loading/submission and live GPU appearance remain unproven.',
             'Nine English comparisons are preliminary source-bitmap masks, not a normal-font update or native inserted layout.',
             'Four kanji icons require gameplay context; attack calligraphy and other formats/images still need investigation.',
             'No story/library draft credit, no build/game-byte change and no full-game translation completion.']}
    expanded=load('docs/expanded-image-audit.json')
    row=next(r for r in expanded['audits'] if r['archive']=='EFFECT.AFS')
    row.update(paletted_PVM_index=index_path,paletted_PVM_index_sha256=doc['index']['sha256'],
               paletted_PVM_atlases_decoded=459,palette_banks=4230,paletted_PVM_failures=0,
               visual_review='All ten bank-zero/index-color contacts reviewed; selected full atlases and 125 mapped UI sprites reviewed; nine English drafts not inserted',
               palette_details='docs/effect-palettes.json')
    expanded['limits']=[
        'ANIME remains outside these decoders',
        'EFFECT 459 wrapped paletted atlases now decoded; native palette binding and complete full-resolution text/reachability review pending',
        'MAP has two explicit errors; MAP/BTT_FACE/CUTIN visual review pending',
        'Two album caption readings remain untranslated; independent meaning/artwork and live review pending']
    nonmovie=load('docs/non-movie-image-text-audit.json')
    nonmovie['effect_palette_discovery']=doc
    nonmovie['expanded_archive_audits']=expanded['audits']
    nonmovie['expanded_audit_limits']=expanded['limits']
    nonmovie['status']='Partial image-text audit: EFFECT palettes decoded and additional untranslated battle/UI text mapped; full discovery/review incomplete'
    status=load('docs/translation-status.json')
    status['effect_palette_discovery']={
        'document':'docs/effect-palettes.json','decoded_atlases':459,'palette_banks':4230,
        'source_UI_sprites_mapped':125,'English_drafts_not_inserted':9,'icon_context_holds':4,
        'native_palette_binding':'unproven','game_build_changed':False}
    outputs={DOC:doc, ROOT/'docs/expanded-image-audit.json':expanded,
             ROOT/'docs/non-movie-image-text-audit.json':nonmovie,
             ROOT/'docs/translation-status.json':status}
    return outputs


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=plan()
    print('Plan: record 459 decoded palette atlases, ten reviewed contacts, 125 mapped sprites, nine English drafts and four context holds.')
    print('Current build remains 0.1.31; game bytes unchanged.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path,data in outputs.items():
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    heading='## Working translation — EFFECT palette discovery and battle/UI drafts'
    entry='''## Working translation — EFFECT palette discovery and battle/UI drafts

- Decoded all 459 EFFECT wrapped 4-bit twiddled atlases and accounted for 4,230 external ARGB1555 palette banks (67,680 entries). Member 459 is the internal ASCII filename list, including its self-reference and DOS EOF. Initial NJTL count equality was incorrect for 75 resources with additional stored banks; all banks are now counted without invented runtime bindings. Windows filename components and list terminators are checked explicitly. Historical unsupported generic-PVM audit retained.
- Independently checked every index pixel and palette color of members 0/1/36/100/458: 720,896 pixels and 1,200 entries exact. Reviewed ten bank-zero/index-color contact sheets and selected full source atlases. These discovery views do not reproduce all runtime palette/blend states or prove no other image text exists.
- Mapped all 125 map_dc UI sprite records with raw parameter words and source pixel/index fingerprints. Corrected the initial all-zero-tail assumption: the exact table terminator is a zero width followed by ten 0xff bytes. Reviewed four labeled source sheets and legible bank-four text witnesses. Prepared nine source-linked English battle/result/ability label drafts and reviewed their preliminary comparison; four single-kanji state icons remain on context hold. The Barrier suffix is shared by sprites 094/107 and needs coordinated insertion. No font/build/game-byte change or story/library draft credit.
- Found attack calligraphy still needing readings/context. Full views resolve members 289/292 as mech/effect silhouettes, not confirmed Japanese text. Tiny console marks and other glyph candidates remain unclassified. Native palette binding/loading/submission, live appearance and complete image/meaning review remain pending. Latest playable build stays 0.1.31; no release.

'''
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded discovery and change log without creating a build.')


if __name__=='__main__':
    main()
