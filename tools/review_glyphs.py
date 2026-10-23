"""Render unresolved glyphs beside tentative matches. Default is a dry run."""
import argparse
import json
from PIL import Image, ImageDraw, ImageFont
from build_font_patch import ROOT, font_data, unswap


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    mapping=json.loads((ROOT/'work/source/font/original-charmap.json').read_text(encoding='utf-8'))
    rows=mapping['unresolved']
    print('Review {} unresolved glyphs in pages of 40. Candidates are NOT accepted automatically.'.format(len(rows)))
    if not args.write:print('DRY RUN: no files written');return
    data=font_data();font=ImageFont.truetype('C:/Windows/Fonts/msmincho.ttc',22)
    for page in range((len(rows)+39)//40):
        image=Image.new('RGB',(1000,1000),'white');draw=ImageDraw.Draw(image)
        for n,row in enumerate(rows[page*40:page*40+40]):
            x=(n%5)*200;y=(n//5)*125;gid=row['glyph_id']
            draw.text((x+3,y+2),row['hex'],fill='black')
            start=0x2300+(gid-512)*32
            for r in range(16):
                bits=unswap(data[start+r*2])<<8|unswap(data[start+r*2+1])
                for c in range(12):
                    if bits&(0x8000>>c):draw.rectangle((x+3+c*4,y+20+r*4,x+6+c*4,y+23+r*4),fill='black')
            for j,candidate in enumerate(row['nearest']):
                label=''.join(candidate['characters'])[:4]+' '+str(candidate['pixel_difference'])
                draw.text((x+60,y+20+j*25),label,font=font,fill='#334466')
        image.save(ROOT/'work/source/font'/('unresolved-{:02d}.png'.format(page)))
    print('Wrote review sheets under work/source/font')


if __name__=='__main__':main()
