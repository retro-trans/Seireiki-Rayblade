"""Record verified 0.1.34 icon correction, source links and change log.

Default dry run. Historical recipe/proof payload identities stay unchanged.
"""
import argparse
import json

from build_bitmap_font import ROOT, digest
from build_order_icons_disc import VERSION, PRIOR, plan
from build_order_icons_patch import DEST
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    out=ROOT/'work/output'/VERSION
    report=read(out/'english-disc-report.json')
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    planned=plan()[-1]
    # Drop the resolved historical hold from current packaging metadata only.
    # Keep all native reports and their original hashes unchanged.
    normalized={**report,'pending':planned['pending']}
    assert {k:v for k,v in normalized.items() if k!='validation'}==planned
    assert report['new_changed_sectors']==24 and report['total_changed_sector_locations_from_original']==28441
    assert report['validation']['reextracted_files']=='all 12 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    assert len(report['historical_native_evidence'])==22
    disc_path=out/'disc'/f'Rayblade English Test {VERSION}.gdi'
    disc=Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries={r['path']:r for r in disc.inventory()}
    for name,info in report['files'].items():
        row=entries[name]
        raw=disc.read(row['lba'],row['size'])
        assert len(raw)==info['size'] and digest(raw)==info['sha256']
        if name not in ('WIN00.AFS','EFFECT.AFS'):
            assert info==previous['files'][name]
    for item in report['historical_native_evidence']:
        raw=(out/item['file']).read_bytes()
        assert digest(raw)==item['sha256'] and read(out/item['file'])['executable_sha256']==item['executable_sha256']
    proof_raw=(out/'order-icons-native-test.json').read_bytes()
    proof=json.loads(proof_raw)
    component=read(out/'order-icons-component-report.json')
    assert proof==report['order_icons_native_proof'] and component==report['order_icons_component']
    assert digest(proof_raw)==report['order_icons_proof_sha256']
    assert proof['archives']=={n:report['files'][n]['sha256'] for n in ('WIN00.AFS','EFFECT.AFS')}
    assert proof['icon_cells']==15 and proof['protected_sprite_records_and_pixels']==360
    assert proof['native_order_selector']['case_count']==80 and proof['native_order_selector']['native_instructions']==3120
    assert proof['native_PRS_instructions']==12332869 and proof['independent_scalar_texture_pixels']==393216
    assert proof['native_guard_and_ABI']=='pass' and proof['archive_bytes_outside_declared_edits']=='exact'
    preview=out/'order-icons-before-after.png'
    assert preview.is_file()
    recipe=read(DEST)
    assert recipe==component['recipe']
    summary={'version':VERSION,'source_build':PRIOR,
             'status':'Five counterattack-order icons corrected in all three atlas copies; independent wording/initial discoverability and live review pending',
             'disc':rel(disc_path),'archives':proof['archives'],'icon_cells':15,
             'orders':recipe['rows'],'historical_correction':recipe['historical_correction'],
             'recipe':rel(DEST),'recipe_sha256':digest(DEST.read_bytes()),
             'preview':rel(preview),'preview_sha256':digest(preview.read_bytes()),
             'native_report':rel(out/'order-icons-native-test.json'),'native_report_sha256':digest(proof_raw),
             'native_selector_cases':80,'native_selector_instructions':3120,
             'native_PRS_instructions':12332869,'scalar_texture_pixels':393216,
             'normal_font_changed':False,'story_library_draft_credit':0,
             'new_changed_sectors':24,'changed_locations_from_original':28441,
             'validation':report['validation'],'pending':planned['pending'],'release':False}
    doc={**summary,'source_evidence':{'context_id':recipe['context_id'],
         'context_source_sha256':recipe['context_source_sha256'],'full_menu':recipe['full_menu'],
         'native_selection':recipe['native_selection'],
         'native_selector_report':'work/ui/asset-audit/EFFECT/counterattack-icons/native-selection.json'},
         'corrections':['Source sprite 60 is 積, not 潜. Its menu policy is Be Aggressive.',
                        'Source sprite 61 無 means Play It Safe in this policy menu, not a generic None label.',
                        'Added sprite 58 Manual, previously mistaken for a nontext checkmark.',
                        'Old WIN00 icon editing erased bevels. Source Manual frame is restored; texture 2 artwork is one pixel left of the other copies.'],
         'native_proof':proof,'resources':component['resources'],
         'archive_placements':component['archives'],
         'historical_recipe_policy':'0.1.20 image-labels.en.json and 0.1.32 effect-ui.en.json remain byte-exact for proof/build reproducibility. This source-linked five-order map supersedes their wrong/held order-icon entries. Historical reports keep their tested archive identities.'}
    coordinates={'build':VERSION,'sprite_dimensions':[16,16],
                 'source_context':doc['source_evidence'],
                 'resources':[{'archive':r['archive'],'member':r['member'],'texture_dimensions':r['dimensions'],
                               'rows':r['draws']} for r in component['resources']],
                 'native_geometry':'Unchanged; all original 375 complete sprite records retained',
                 'preview':rel(preview),'live_capture':False,
                 'limits':recipe['limits']}
    palette=read(ROOT/'docs/effect-palettes.json')
    palette.update(current_game_build=VERSION,latest_order_icons_build=summary,icon_context_holds=0,
                   English_order_icons_inserted=5,
                   status='All source paletted atlases decoded; nine UI labels, five order icons and eight BREAK artwork frames inserted. Other image/text discovery, independent meaning/artwork and live/native review remain incomplete')
    palette['findings'][0].update(classification='Nine English UI labels and five English order initials inserted',
                                 details='Five order icons 58..62 now M/C/A/S/D; native policy selector confirms ordered WIN00 mapping. EFFECT runtime palette/selection remains unverified. Sprite 088 ornament/glyph remains unclassified. Barrier shared region handled in 0.1.32.')
    expanded=read(ROOT/'docs/expanded-image-audit.json')
    effect=next(r for r in expanded['audits'] if r['archive']=='EFFECT.AFS')
    effect.update(latest_order_icons_build=VERSION,English_order_icons_inserted=5,latest_combined_archive_build=VERSION,
                  visual_review='Original discovery views, nine UI labels, eight attack frames and five order-initial witnesses reviewed; whole-attack/GPU/fine-detail/reachability review incomplete')
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    audit.update(last_packaged_build=VERSION,counterattack_orders=summary,effect_palette_discovery=palette,
                 expanded_archive_audits=expanded['audits'],
                 status='Partial image-text audit: five order icons corrected in all copies; other image/text discovery, independent meaning/artwork and live/full-game review incomplete')
    audit['completed_image_work']=[r for r in audit.get('completed_image_work',[]) if r.get('build')!=VERSION]
    audit['completed_image_work'].append({'build':VERSION,'archives':['WIN00.AFS','EFFECT.AFS'],'icon_cells':15,'scope':summary['status']})
    status=read(ROOT/'docs/translation-status.json')
    oldcontext=status.get('effect_icon_context',{})
    context={'status':'Five order icons source-linked and inserted in all three atlas copies; live review pending',
             'icon_ids':[f'effect.250.{i:03d}' for i in range(58,63)],
             'orders':recipe['rows'],'source_evidence':doc['source_evidence'],
             'EFFECT_runtime_binding':'Unverified; source-art duplicate corrected consistently',
             'historical_search_limits':oldcontext.get('native_search_limits',oldcontext.get('historical_search_limits',[]))}
    status.update(version=VERSION,stage='Five order icons corrected across three atlases; remaining text/images, independent meaning/artwork/font/live and full-game validation incomplete',
                  latest_order_icons_build=summary,effect_icon_context=context,effect_palette_discovery=palette,
                  non_movie_image_text_audit=audit)
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(disc_path),kind=report['kind'],
                               changed_sectors=28441,order_icons_delta_sectors=24,
                               WIN00_sha256=proof['archives']['WIN00.AFS'],EFFECT_sha256=proof['archives']['EFFECT.AFS'],
                               validation=report['validation'],pending=planned['pending'])
    status['test_disc'].pop('attack_artwork_delta_sectors',None)
    glossary={'kind':'Counterattack-order UI mapping supplement; no story/library draft credit',
              'source_context_id':recipe['context_id'],'source_sha256':recipe['context_source_sha256'],
              'entries':[{**r,'id':f'order.{r["order"]}','inserted_build':VERSION,
                          'status':'Source/native-policy linked; independent meaning/live review pending'} for r in recipe['rows']]}
    metadata=read(out/'order-icons-component.json')
    metadata['pending']=planned['pending']
    return [(out/'english-disc-report.json',normalized),(out/'order-icons-component.json',metadata),
            (ROOT/'docs/counterattack-orders.json',doc),(ROOT/'work/ui/counterattack-orders.json',coordinates),
            (ROOT/'work/glossary/counterattack-orders.json',glossary),
            (ROOT/'docs/effect-palettes.json',palette),(ROOT/'docs/expanded-image-audit.json',expanded),
            (ROOT/'docs/non-movie-image-text-audit.json',audit),(ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: fifteen corrected cells, twelve exact disc payloads, 22 historical proofs; 24 substitutions, 28441 changed original locations.')
    if not args.write:
        print('DRY RUN: no records/change log written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    heading='## 0.1.34 — correct all five counterattack-order icons'
    entry='''## 0.1.34 — correct all five counterattack-order icons

- Corrected the previously misread order sequence to Manual, Always Counterattack, Be Aggressive, Play It Safe and Always Defend. Source sprite 60 is 積, not 潜; the old WIN00 Sup/Resupply and Nil/None labels were wrong. Added Manual sprite 58, previously mistaken for a nontext mark. All fifteen 16x16 cells across WIN00 textures 2/6 and EFFECT member 250 now use M/C/A/S/D. Full menu descriptions are unchanged. Historical recipes/proofs remain byte-exact and explicitly superseded for these icons.
- Reuses the current inferred Latin masks at one common 1/4 scale and four coverage levels, without per-letter stretching. Restores the source Manual bevel template where the older patch erased it; texture 2's source artwork is one pixel left of the other copies. Fifteen final before/after witnesses reviewed offline. The first candidate exceeded texture 2's packed slot by 22 bytes; native four-level coverage and correct frame reuse fit all resources without relocation. Palette/initial discoverability and live appearance remain unverified.
- All 375 complete sprite records, palettes, 360 other sprite images, 88 other WIN00 members and 459 other EFFECT members stay exact. Current normal font bytes and every non-icon atlas pixel remain exact 0.1.33. Independent checks verify 393,216 scalar texture pixels, 256 palette entries and 10,240 native font samples. Three actual PRS streams execute 12,332,869 SH-4 instructions with exact output and guards/ABI preserved; native texture headers and three PVM wrapper lookups pass. Eighty real unit-list selector/SDK byte-query cases execute 3,120 instructions and confirm resource 3, sprite 58 + policy for unit+8 bits 5:3. Sprite constructor and PVM memcmp are bounded fixtures; no actual file loading, allocation/submission, EFFECT live binding or GPU proof claimed.
- Local build 0.1.34 contains 24 sector substitutions (19 WIN00, 5 EFFECT); all fall within already changed locations, so the total remains 28,441 locations from original. All twelve game payloads re-extract exactly; changed-sector EDC/ECC, ISO inventory and comparison of all 1,188,856,032 track bytes pass. Ten unaffected payloads and twenty-two historical native proof identities remain exact. Original-logo artwork with English subtitle is retained in both selected movies. Original dump and earlier builds untouched; no release.
- Remaining image/encoded-text discovery, two album captions, held passages, independent meaning/artwork/font review and live/full-game validation remain unfinished. No story/library draft credit and no full-translation completion claim.

'''
    log=ROOT/'CHANGELOG.md'
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded source-linked UI/glossary/build status and change log. Full translation remains incomplete.')


if __name__=='__main__':
    main()
