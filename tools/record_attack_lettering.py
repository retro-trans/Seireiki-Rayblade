"""Record source attack lettering and bounded native variant evidence.

Dry run first. English wording is a draft; no game/artwork bytes change.
"""
import argparse
import json

from build_bitmap_font import ROOT,digest
from check_attack_variant_selection import OUT


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def witness(path):
    return {'path':rel(path),'sha256':digest(path.read_bytes())}


def record():
    source=read(OUT/'source-map.json')
    native=read(OUT/'native-variant-selection.json')
    assert source['sprite_records_mapped']==110 and source['lettering_sprite_candidates']==8
    assert native['native_cases']==16 and native['native_instructions']==4160
    assert native['native_dispatch_bit_query_branch_join_and_ABI']=='pass'
    assert native['graphic_variant_pairs']==[[142,455],[143,456]]
    rows=[]
    for resource in source['resources']:
        member=resource['member']
        if member not in (142,143,455,456):
            continue
        for sprite in (8,9):
            row=dict(resource['rectangles'][sprite])
            row.update(source_member=member,English_target='BREAK',status='editorial_draft_not_inserted',
                       source_decoded_sha256=resource['decoded_sha256'],
                       source_glyph='破' if sprite==8 else None,
                       reading_basis='Clear primary glyph or its visually reversed variant' if sprite==8
                       else 'Proposed same-word motion/glow treatment; separate character/phrase reading is not established')
            rows.append(row)
    recipe={'source_archive':'EFFECT.AFS','source_archive_sha256':source['source_archive_sha256'],
            'native_graphic_selection_proof':witness(OUT/'native-variant-selection.json'),
            'rows':rows,'wording':'BREAK',
            'wording_basis':'破 is an emphatic breaking/shattering glyph. Existing weapon.020 naming ends in Rift Breaker; no claim that this image alone prints the full weapon name.',
            'motion_frame_reading':'Do not invent a second character or a two-character phrase from the smeared frame. Same-word effect treatment remains a draft pending frame/submission inspection.',
            'pending':['Coordinated English artwork for all eight frame images, including the visually reversed and smeared variants',
                       'Actual sprite transform and palette/timing selection; native variant-load tests do not cover these',
                       'Texture/archive preservation and fresh native checks before insertion',
                       'Independent wording/artwork and live attack review'],
            'game_build_changed':False,'story_library_draft_credit':0}
    doc={'status':'Primary attack glyph read as 破 with BREAK draft; source sprite maps and native graphic-variant selection verified, English artwork not inserted',
         'current_game_build':'0.1.32','source_map':witness(OUT/'source-map.json'),
         'native_variant_selection':witness(OUT/'native-variant-selection.json'),
         'source_records_mapped':110,'English_frame_targets':8,
         'trimmed_primary_glyph_relationship':source['exact_relationships'],
         'native_cases':16,'native_instructions':4160,
         'native_variant_pairs':native['graphic_variant_pairs'],
         'native_scope':'Real main/subcommand dispatch, SDK bit extraction, conditional VM advancement, parsed file-load arguments, native completion-phase advance and branch join. File I/O and pending poll are explicit fixtures.',
         'native_limits':native['limits'],
         'test_correction':'The interpreter initially lacked SWAP.B used by the actual SDK bit query. Added its instruction semantics locally, then all sixteen cases pass; no game defect attributed to that interpreter gap.',
         'previews':[witness(OUT/f'lettering-{page:02d}.png') for page in (0,1)],
         'visual_review':'Both labeled full-size lettering sheets reviewed: clear/red primary glyphs, reversed variants and yellow smeared effect frames. Explicit preview banks 5/6; runtime palette binding still untested.',
         'resolved_non_text_candidates':source['resolved_non_text_candidates'],
         'translation_recipe':'work/translation/en/ui/attack-lettering.en.json',
         'glossary':'work/glossary/attack-lettering.json',
         'pending':recipe['pending'],'game_build_changed':False,'story_library_draft_credit':0}
    glossary={'project':'Seireiki Rayblade Dreamcast','status':'Source-linked effect artwork wording draft',
              'entries':[{'id':'ui.attack.break','category':'ui_effect','ja':'破','en':'BREAK',
                          'status':'editorial_draft','source_ids':[r['id'] for r in rows if r['sprite']==8],
                          'source_archive_sha256':source['source_archive_sha256'],
                          'notes':['Single emphatic artwork glyph; does not replace the full attack name',
                                   'All frame artwork, transforms and final presentation remain under review']}],
              'main_glossary_changed':False}
    palette=read(ROOT/'docs/effect-palettes.json')
    palette['attack_lettering_discovery']=doc
    for finding in palette['findings']:
        if finding.get('members')==[142,143,455,456]:
            finding.update(classification='Primary 破 glyph plus reversed/smeared variants; eight BREAK frame targets drafted',
                           details='110 source records mapped across six resources. ANIME 172/173 native branch/load/join cases establish pairs 142/455 and 143/456. Whole attack, frame transforms, motion/glow treatment and English insertion remain pending.')
        if finding.get('members')==[438,439]:
            finding.update(classification='Full-size candidates resolved as impact-ring/mech effect artwork',
                           details='No kanji reading assigned; source images retained unchanged.')
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    audit.update(attack_lettering_discovery=doc,effect_palette_discovery=palette)
    status=read(ROOT/'docs/translation-status.json')
    status.update(attack_lettering_discovery=doc,effect_palette_discovery=palette,
                  non_movie_image_text_audit=audit)
    status['glossary']['attack_artwork_supplement']={'path':'work/glossary/attack-lettering.json','entries':1,
                                                   'scope':'Additional artwork wording draft; main 851-entry glossary and two effect-UI terms unchanged'}
    return [(ROOT/'work/translation/en/ui/attack-lettering.en.json',recipe),
            (ROOT/'work/glossary/attack-lettering.json',glossary),(ROOT/'docs/attack-lettering.json',doc),
            (ROOT/'docs/effect-palettes.json',palette),(ROOT/'docs/non-movie-image-text-audit.json',audit),
            (ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('Plan: record eight BREAK artwork targets, 110 source records, two exact primary-glyph copies and sixteen native selection cases. No game edit.')
    if not args.write:
        print('DRY RUN: no translation, glossary or documentation written')
        return
    for path,data in outputs:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    heading='## Working translation — attack lettering and native graphic variants'
    entry='''## Working translation — attack lettering and native graphic variants

- Inspected full sources for EFFECT 143/438/439/455/456 and mapped 110 sprite records across 142/143/438/439/455/456, preserving exact source geometry/index/palette fingerprints and observed terminators. The 438/439 candidates are mech poses/impact rings, not confirmed kanji. Four Hongshenguang resources contain a clear 破 primary glyph and reversed/smeared artwork variants. Trimmed primary glyph 8 in members 142/143 is a byte-exact 167x155 index image, placed 40 source pixels lower in the latter cell.
- Prepared BREAK as an editorial artwork-wording draft and eight coordinated frame targets, with a separate one-entry UI-effect glossary supplement. The smeared frames must not be read as an invented second character or two-character phrase; their same-word motion/glow treatment still needs frame/submission inspection. Both labeled source sheets reviewed using explicit preview banks 5/6. No English image inserted and no story/library draft credit.
- Linked real ANIME 172/173 source branch/load regions to EFFECT pairs 142/455 and 143/456. Sixteen actor/state-bit cases execute native main/subcommand dispatch, the actual SDK bit-field query, VM conditional advance, AFS argument parsing, completed-phase advance and the unconditional branch join: 4,160 SH-4 instructions, exactly one selected load per case, preserved guards/ABI. File I/O and pending poll are bounded fixtures; phases 1/2 resource loading, whole-attack reachability, frame transforms, palette/timing and GPU appearance are not executed. The interpreter initially lacked SWAP.B; implemented that instruction locally and reran all sixteen cases successfully, without attributing the gap to the game.
- The primary glyph wording, reversed/smeared English art, palette/transform/timing behavior, native insertion and independent/live review remain unfinished. Other status icons, remaining text/meaning/font/full-game checks remain open. Latest playable build stays 0.1.32; original game bytes and previous builds unchanged; no release.

'''
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded source-linked wording/variant evidence and change log; build remains 0.1.32.')


if __name__=='__main__':
    main()
