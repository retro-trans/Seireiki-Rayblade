"""Prepare source-linked effect UI drafts without changing game bytes.

Historical 0.1.32 recipe, retained for tested identity/reproducibility. Its old
icon holds/misreading of sprite 60 are superseded by counterattack-orders.en.json
and build_order_icons_patch.py. Palette binding remains unproven.
"""
import argparse
import json

from PIL import Image, ImageDraw

from audit_effect_palettes import original, parse
from build_bitmap_font import ROOT, ATLAS, digest
from build_ui_atlas_patch import mask
from extract_effect_ui import analyze, OUT as SOURCE

DEST = ROOT/'work/translation/en/ui/effect-ui.en.json'
PREVIEW = ROOT/'work/ui/asset-audit/EFFECT/ui-250/english-drafts.png'
LINKS = [
    (57, 'プラーナ', 'Prana', 'term.013', 3),
    (89, 'クリティカル', 'Critical', None, 2),
    (90, '回避', 'Evade', 'term.098', 2),
    (91, '防御', 'Guard', 'term.096', 2),
    (92, 'プラズマコート', 'Plasma Coating', 'term.101', 2),
    (93, 'プラズマバリア', 'Plasma Barrier', 'term.099', 2),
    (94, '対実弾バリア', 'Ballistic Barrier', 'term.100', 2),
    (95, '特殊フィールド', 'Special Field', 'term.233', 2),
    (107, 'バリア', 'Barrier', None, 2),
]
HOLDS = [
    (59, '反', 'Counter / retaliation; confirm this icon state and use before assigning English'),
    (60, '潜', 'Submerged / submerge; confirm state versus command and water context'),
    (61, '無', 'None / disabled; determine what this absence marker qualifies'),
    (62, '防', 'Defense / guard; determine status versus command before assigning abbreviation'),
]


def prepare():
    info, *_ = analyze()
    _, members = original()
    _, _, _, indices, colors, _ = parse(members[250])
    glossary = json.loads((ROOT/'work/glossary/glossary.json').read_text('utf-8'))
    terms = {r['id']: r for r in glossary['entries']}
    # Bank four makes these text indices legible, but this offline view does
    # not assert that every sprite uses that bank in the native pipeline.
    source = Image.fromarray(colors[4][indices])
    rows = []
    for sprite, ja, en, term, denominator in LINKS:
        row = dict(info['rectangles'][sprite])
        if term:
            assert terms[term]['ja'] == ja
            assert (en.lower() == terms[term]['en'].lower()
                    or (sprite, en) in [(90, 'Evade'), (91, 'Guard')])
        ink = mask(en, denominator)
        w, h = row['draw_size']
        assert ink.shape[1]+1 <= w and ink.shape[0]+1 <= h, (en, ink.shape, w, h)
        row.update(ja=ja, en=en, glossary_id=term, status='editorial_draft_not_inserted',
                   source_bank_04_pixel_sha256=digest(source.crop(row['source_box']).tobytes()),
                   font_scale_denominator=denominator,
                   draft_mask_size=[ink.shape[1], ink.shape[0]])
        if sprite in (90, 91):
            row['decision'] = 'Battle-result action wording; glossary stat noun is retained separately'
        if sprite == 107:
            row['decision'] = 'Shares the rightmost 48 pixels of sprite 094. Insertion must preserve a common Barrier suffix'
        rows.append(row)
    held = [{**info['rectangles'][i], 'ja':ja, 'en':None, 'status':'context_hold', 'reason':why}
            for i,ja,why in HOLDS]
    return {'source':'Original EFFECT.AFS member 250 map_dc',
            'source_archive_sha256':info['source_archive_sha256'],
            'source_decoded_sha256':info['decoded_sha256'],
            'source_geometry_map':str((SOURCE/'rectangles.json').relative_to(ROOT)).replace('\\','/'),
            'font':str(ATLAS.relative_to(ROOT)).replace('\\','/'),
            'font_sha256':digest(ATLAS.read_bytes()),
            'source_preview_palette_bank':4,
            'rows':rows, 'context_holds':held,
            'pending':['Native texture parameter and palette binding',
                       'Shared 094/107 suffix layout and protected sprite overlap checks',
                       'Source palette/index preservation and native decoding/insertion',
                       'Independent meaning review and live battle UI validation'],
            'other_candidates':['Sprite 088 ornament/glyph remains unclassified; no guessed translation'],
            'story_library_draft_credit':0, 'game_build_changed':False}, source


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    data,source=prepare()
    print('Plan:',len(data['rows']),'English drafts;',len(data['context_holds']),'icon context holds; no game edit.')
    for row in data['rows']:
        print(row['id'],row['en'],row['draft_mask_size'],'within',row['draw_size'])
    if not args.write:
        print('DRY RUN: no translation recipe or preview written')
        return
    sheet=Image.new('RGB',(800,len(data['rows'])*85),'#30333a')
    draw=ImageDraw.Draw(sheet)
    for n,row in enumerate(data['rows']):
        crop=source.crop(row['source_box'])
        factor=min(4,350//crop.width,60//crop.height)
        crop=crop.resize((crop.width*factor,crop.height*factor),Image.Resampling.NEAREST)
        y=n*85
        sheet.paste(crop,(0,y),crop)
        ink=Image.fromarray(mask(row['en'],row['font_scale_denominator']))
        ink=ink.resize((ink.width*factor,ink.height*factor),Image.Resampling.NEAREST)
        sheet.paste('white',(400,y),ink)
        draw.text((2,y+65),row['id']+'  '+row['en'],fill='white')
    draw.text((400, len(data['rows'])*85-20),'Offline draft; palette/native layout pending',fill='#cccccc')
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf-8')
    PREVIEW.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(PREVIEW)
    print('Wrote source-linked English draft and comparison; original game files unchanged.')


if __name__=='__main__':
    main()
