"""Record packaged English attack artwork 0.1.33. Dry run first."""
import argparse
import copy
import json

from build_attack_lettering_disc import VERSION,PRIOR
from build_bitmap_font import ROOT,digest
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    out=ROOT/'work/output'/VERSION
    report=read(out/'english-disc-report.json')
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    assert report['version']==VERSION and report['source_build']==PRIOR
    assert report['new_changed_sectors']==46 and report['total_changed_sector_locations_from_original']==28441
    assert report['source_archive_changed_locations_from_original']==6
    assert report['target_archive_changed_locations_from_original']==51
    assert report['total_changed_sector_locations_from_original']==previous['total_changed_sector_locations_from_original']-6+51
    assert report['validation']['reextracted_files']=='all 12 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    assert len(report['historical_native_evidence'])==21
    disc_path=out/'disc'/f'Rayblade English Test {VERSION}.gdi'
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
        assert digest(raw)==item['sha256'] and json.loads(raw)['executable_sha256']==item['executable_sha256']
    native_raw=(out/'attack-lettering-native-test.json').read_bytes()
    proof=json.loads(native_raw)
    component=read(out/'attack-lettering-component-report.json')
    assert proof==report['attack_lettering_native_proof'] and component==report['attack_lettering_component']
    assert digest(native_raw)==report['attack_lettering_proof_sha256']
    assert proof['archive_sha256']==report['files']['EFFECT.AFS']['sha256']
    assert proof['native_PRS_instructions']==10392893 and len(proof['native_PRS_streams'])==4
    assert proof['independent_scalar_index_pixels']==1048576 and proof['independent_palette_entries']==1088
    assert len(proof['native_PVM_wrapper_cases'])==12 and proof['native_variant_selector']['native_cases']==16
    assert proof['native_guard_and_ABI']=='pass' and proof['archive_bytes_outside_declared_edits']=='exact'
    assert all(r['target_offset']==r['source_offset'] and r['packed_bytes']<=r['source_slot_capacity'] for r in component['resources'])
    previews=[out/f'attack-lettering-before-after-{member:03d}.png' for member in (142,143,455,456)]
    assert all(p.is_file() for p in previews)
    prior_doc=read(ROOT/'docs/attack-lettering.json')
    # Retain source-discovery evidence without recursively nesting repeated
    # records if this recorder is run again after completion.
    discovery=prior_doc.get('source_discovery',prior_doc)
    doc={'version':VERSION,'source_build':PRIOR,
         'status':'Eight coordinated English BREAK artwork frames packaged; glow/trail fidelity, independent meaning and whole-attack/live review pending',
         'disc':rel(disc_path),'archive':'EFFECT.AFS','archive_sha256':proof['archive_sha256'],
         'artwork_frame_count':8,'changed_texture_members':[142,143,455,456],
         'translation_recipe':'work/translation/en/ui/attack-lettering.en.json',
         'recipe_status_scope':'Source-linked wording recipe preserves its pre-insertion preparation status/hash; this build record gives current insertion status',
         'previews':[{'path':rel(p),'sha256':digest(p.read_bytes())} for p in previews],
         'visual_review':'All eight before/after English/source frame witnesses reviewed; primary optical placement, reversed variants and reauthored yellow trails inspected offline in explicit banks 5/6',
         'font':component['font'],'normal_font_changed':False,
         'artwork_method':component['artwork_method'],'artwork_fidelity_limit':component['fidelity_limit'],
         'resources':[{'member':r['member'],'packed_bytes':r['packed_bytes'],'source_slot_capacity':r['source_slot_capacity'],
                       'offset':r['target_offset'],'dimensions':r['texture_dimensions']} for r in component['resources']],
         'preservation':['All four original 512x512 texture dimensions, 104 complete sprite records, anchors/UV/raw parameters and all palettes exact',
                         'Ninety-six non-letter sprite images and 456 unrelated archive member payloads/offsets exact',
                         'Preceding English member-250 UI, animation programs and all eleven other game payloads exact 0.1.32',
                         'All four compressed resources stay in their original slots; original archive extent and bytes outside declared edits exact'],
         'native_proof':proof,'validation':report['validation'],
         'new_changed_sectors':46,'changed_sector_locations_from_original':28441,
         'EFFECT_changed_locations':{'before':6,'after':51,'new_locations':45},
         'source_discovery':copy.deepcopy(discovery),'pending':report['pending'],
         'story_library_draft_credit':0,'release':False}
    palette=read(ROOT/'docs/effect-palettes.json')
    palette.update(current_game_build=VERSION,latest_attack_artwork_build=doc,
                   status='All source paletted atlases decoded; nine UI labels and eight BREAK artwork frames inserted. Four status icons, other image/text discovery and independent/native/live review remain incomplete')
    for finding in palette['findings']:
        if finding.get('members')==[142,143,455,456]:
            finding.update(classification='Eight coordinated English BREAK artwork frames inserted in 0.1.33',
                           details='Original 512x512 dimensions, all geometry/palettes and other sprites retained. Red glow/yellow trails reauthored as approximations; independent wording/fidelity and whole-attack palette/transform/timing/live review pending.')
    expanded=read(ROOT/'docs/expanded-image-audit.json')
    effect=next(r for r in expanded['audits'] if r['archive']=='EFFECT.AFS')
    effect.update(latest_attack_artwork_build=VERSION,English_attack_frames_inserted=8,
                  latest_combined_archive_build=VERSION,
                  visual_review='Original discovery views, nine English UI labels and eight English attack-frame witnesses reviewed; whole-attack/GPU/fine-detail/reachability review incomplete')
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    audit.update(last_packaged_build=VERSION,attack_lettering=doc,effect_palette_discovery=palette,
                 expanded_archive_audits=expanded['audits'],
                 status='Partial image-text audit: nine EFFECT UI labels and eight BREAK artwork frames inserted; four icons, other images/text and independent meaning/live review incomplete')
    audit['completed_image_work']=[r for r in audit.get('completed_image_work',[]) if (r.get('build'),r.get('archive'))!=(VERSION,'EFFECT.AFS')]
    audit['completed_image_work'].append({'build':VERSION,'archive':'EFFECT.AFS','artwork_frames':8,'scope':doc['status']})
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,stage='Eight coordinated English BREAK attack-art frames inserted over unchanged 0.1.32 font/text/UI/movies; four icons, other images/held text, meaning/font/live and full-game review incomplete',
                  latest_attack_artwork_build=doc,effect_palette_discovery=palette,
                  non_movie_image_text_audit=audit)
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(disc_path),kind=report['kind'],
                               changed_sectors=28441,validation=report['validation'],attack_artwork_delta_sectors=46,
                               EFFECT_sha256=proof['archive_sha256'],pending=report['pending'])
    status['test_disc'].pop('effect_UI_delta_sectors',None)
    glossary=read(ROOT/'work/glossary/attack-lettering.json')
    glossary['entries'][0]['inserted_build']=VERSION
    glossary['entries'][0]['notes']=['Single emphatic artwork glyph; full attack name remains unchanged',
                                   'Eight frame images inserted with reauthored glow/trails; independent meaning/fidelity and live review pending']
    return [(ROOT/'docs/attack-lettering.json',doc),(ROOT/'docs/effect-palettes.json',palette),
            (ROOT/'docs/expanded-image-audit.json',expanded),(ROOT/'docs/non-movie-image-text-audit.json',audit),
            (ROOT/'docs/translation-status.json',status),(ROOT/'work/glossary/attack-lettering.json',glossary)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: 0.1.33, eight English frames, twelve exact payloads, 21 historical identities; 46 substitutions, 45 newly changed original-disc locations.')
    if not args.write:
        print('DRY RUN: no documentation/glossary written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    heading='## 0.1.33 — English BREAK attack artwork across all eight variants'
    entry='''## 0.1.33 — English BREAK attack artwork across all eight variants

- Inserted BREAK in eight related primary/reversed/motion artwork cells in EFFECT members 142/143/455/456. Reuses the current inferred Latin font's exact native glyph masks and advances at one common whole-word scale, with no individual stretching. Primary placements retain the source's optical center and 40-pixel vertical variant difference. Reversed source variants remain reversed; other sprite flags and animation programs are unchanged. Red glow and rotated yellow trails are newly authored approximations, not exact reconstruction of original brush contours or motion fields. All eight before/after witnesses reviewed offline; independent wording/fidelity and live appearance remain pending.
- All four native atlases remain 512x512 with every original palette, 104 complete geometry records and 96 other sprite images exact. The four compressed resources fit their original 24,576/26,624-byte slots without relocation. The other 456 archive members, including the preceding nine English UI labels, remain exact 0.1.32. Only eight declared word cells, four compressed payloads and their size descriptors change; source dump and previous builds untouched. Normal text font and source story/library draft counts unchanged.
- Independent scalar checks verify 1,048,576 texture indices, 1,088 palette entries and 10,240 native font samples for B/R/E/A/K, common word layout, exact source placements/reversed forms, complete word-cell replacement, all archive bounds/nonoverlap and bytes/pixels outside edits. Four actual PRS streams execute 10,392,893 SH-4 instructions for 530,304 exact bytes. Twelve native PVM wrapper lookups execute 1,932 instructions, PAL4 header creation 181, and sixteen fresh source graphic-variant branch/load/join cases 4,160. Guards/ABI pass. Existing bounded memcmp and async-I/O fixtures remain explicit; actual loading, complete attack reachability, sprite transforms, runtime palette/timing and GPU/live behavior are not proved.
- Packaged local build 0.1.33: 46 sector substitutions over 0.1.32 and 28,441 locations from original. EFFECT already had six changed locations and now has 51, so 45 locations are newly changed; overlapping archive-header edits are not double-counted. All twelve payloads re-extract exactly; changed-sector EDC/ECC, unchanged ISO inventory and comparison of all 1,188,856,032 track bytes pass. Eleven other game payloads, including current normal font and both selected-logo subtitle movies, and twenty-one historical native proof identities remain exact. No release.
- Four effect status icons, other image/encoded-text discovery, two album captions, held passages, independent meaning/artwork/font review and live/full-game validation remain unfinished. This is a local artwork test build, not full translation completion.

'''
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded build, glossary status and change log; full translation goal remains incomplete.')


if __name__=='__main__':
    main()
