"""Resolve two short album UI captions using source glyph-shape references.

Default dry run. Manual readings are not an exact font/OCR identity claim.
Retains the historical 201-caption recipe for old proof reproducibility.
"""
import argparse
import json

from PIL import Image,ImageDraw,ImageFont

from build_bitmap_font import ROOT,digest
from extract_album_captions import analyze
from font_match_probe import bitmap
from prepare_album_translations import wrap,caption_mask

DEST=ROOT/'work/translation/en/ui/album-caption-readings.en.json'
OUT=ROOT/'work/ui/asset-audit/ALBUM/captions/readings-01'
READINGS=[
    (82,'裸のトウヤ','Naked Touya','裸',2075,
     'The first character has the clothing radical and fruit-shaped right component: 裸. The earlier 裏/影/素 guesses do not match that structure. Literal non-graphic caption only; no erotic or anatomical detail added.'),
    (102,'弱々しい目のアルフォリナ',"Alforina's Feeble Gaze",'弱',1332,
     'The first character is the repeated bow-shaped structure 弱, followed by 々しい目の. Feeble Gaze retains the weakened eyes/gaze detail without adding a cause or new scene event.'),
]


def prepare():
    info,_,_,textures=analyze()
    charmap=json.loads((ROOT/'work/source/font/original-charmap.json').read_text('utf-8'))['glyphs']
    rows=[]
    for index,ja,en,char,gid,note in READINGS:
        source=info['rectangles'][index]
        caption=textures[source['texture_member']][1].crop(source['caption_box'])
        assert charmap[str(gid)]['text']==char
        assert digest(caption.tobytes())==source['source_caption_sha256']
        lines=wrap(en)
        if index==102:
            lines=["Alforina's",'Feeble Gaze']
        assert len(lines)<=3 and ' '.join(lines)==en
        assert all(caption_mask(line).shape[1]<=62 for line in lines)
        rows.append({**source,'ja_ui':ja,'en':en,'wrapped_lines':lines,
                     'status':'Manual glyph-shape reading; editorial draft, independent review pending',
                     'first_glyph_reference':{'character':char,'original_game_glyph_id':gid,
                                              'bitmap_sha256':digest(bitmap(gid).tobytes()),
                                              'source_caption_local_box':[4,1,14,10]},
                     'decision':note})
    return {'source':'Original ALBUM.AFS DAT214 caption cells; exact source hashes retained',
            'source_archive_sha256':info['source_archive_sha256'],'caption_count':2,
            'rows':rows,'source_font_reference':'Original WIN00 member 0 and reviewed original-charmap.json',
            'scope':'Manual source shape reading supported by original-game and local Japanese-font reference forms; no exact pixel font match or automatic OCR proof',
            'historical_recipe':'work/translation/en/ui/album-captions.en.json remains unchanged (201 captions and two original reading holds)',
            'normal_font_changed':False,'story_library_draft_credit':0,
            'pending':['Independent caption readings/wording review','Native insertion and actual album appearance/navigation']}


def make_reference():
    info,_,_,textures=analyze()
    page=Image.new('RGB',(1080,590),'#ececec')
    draw=ImageDraw.Draw(page)
    reference=ImageFont.truetype('C:/Windows/Fonts/msgothic.ttc',40)
    charmap=json.loads((ROOT/'work/source/font/original-charmap.json').read_text('utf-8'))['glyphs']
    gids={v['text']:int(k) for k,v in charmap.items()}
    for index,candidates,y in [(82,'裸裏影素襟黒霧',0),(102,'弱毒寂険',290)]:
        row=info['rectangles'][index]
        crop=textures[row['texture_member']][1].crop(row['caption_box'])
        page.paste(crop.resize((512,192),Image.Resampling.NEAREST),(8,y+30))
        draw.text((8,y+8),'Original caption '+str(index)+' (8x inspection)',fill='black')
        for i,char in enumerate(candidates):
            x,yy=540+i%4*130,y+18+i//4*125
            draw.text((x,yy),char,font=reference,fill='black')
            glyph=bitmap(gids[char])
            glyph=glyph.resize((glyph.width*4,glyph.height*4),Image.Resampling.NEAREST)
            page.paste('black',(x+55,yy,x+55+glyph.width,yy+glyph.height),glyph)
            draw.text((x,yy+70),'Reference / game',fill='black')
    return page


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    recipe=prepare()
    print('Plan: two source-linked UI caption readings and manual shape reference; no exact OCR/font match claimed.')
    for row in recipe['rows']:
        print(row['id'],row['ja_ui'],'->',row['en'],row['wrapped_lines'])
    if not args.write:
        print('DRY RUN: no recipe/reference written')
        return
    DEST.write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n','utf-8')
    OUT.mkdir(parents=True,exist_ok=True)
    make_reference().save(OUT/'source-glyph-references.png')
    print('Wrote two caption drafts and source/reference sheet; no game bytes changed.')


if __name__=='__main__':
    main()
