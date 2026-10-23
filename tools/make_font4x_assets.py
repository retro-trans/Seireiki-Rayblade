"""Generate 4x Latin font source atlases and an offline comparison preview.

These assets are NOT yet connected to the Dreamcast texture renderer.
Native glyph bounds and the VWF advance table define their logical layout.
Glyphs are rerasterized from a vector font, not enlarged pixel bitmaps.
Default is a dry run. Requires Pillow.
"""
import argparse
import json
from pathlib import Path
from build_font_patch import ROOT,font_data,metrics,unswap


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/tahoma.ttf'))
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    if not args.font.is_file():raise ValueError('Supply a vector font with --font')
    out=ROOT/'work/ui/font4x'
    print('Vector font: {}'.format(args.font))
    print('Generate small/medium 4x Latin atlases, metrics.json, and offline preview.')
    print('Destination: {}; game integration remains pending.'.format(out))
    if not args.write:
        print('DRY RUN: no files written');return
    from PIL import Image,ImageDraw,ImageFont
    out.mkdir(parents=True,exist_ok=True)
    font=font_data();small,medium=metrics(font)
    vector=ImageFont.truetype(str(args.font),128)
    config=[('small',list(chr(c) for c in range(32,127)),8,0,small),
            ('medium',list(' '+'ABCDEFGHIJKLMNOPQRSTUVWXYZ'+'abcdefghijklmnopqrstuvwxyz'+'0123456789'),16,0x300,medium)]
    data={'scale':4,'status':'source assets only; not integrated in the game',
          'vector_font':args.font.name,'logical_pixels_preserved':True,'fonts':{}}
    glyph_sets={}
    for name,chars,height,start,table in config:
        rows=(len(chars)+15)//16
        atlas_height=1 << ((rows*height*4-1).bit_length())
        atlas=Image.new('RGBA',(512,atlas_height),(255,255,255,0))
        entries=[];glyphs={}
        for idx,ch in enumerate(chars):
            native=Image.new('L',(8,height))
            for y in range(height):
                bits=unswap(font[start+idx*height+y])
                for x in range(8):native.putpixel((x,y),255 if bits&(0x80>>x) else 0)
            bounds=native.getbbox();hd=Image.new('L',(32,height*4))
            advance,bearing=table[idx]
            if bounds:
                left,top,right,bottom=bounds
                canvas=Image.new('L',(256,256));ImageDraw.Draw(canvas).text((16,16),ch,font=vector,fill=255)
                vbox=canvas.getbbox()
                if vbox:
                    ink=canvas.crop(vbox).resize(((right-left)*4,(bottom-top)*4),Image.Resampling.LANCZOS)
                    hd.paste(ink,(0,top*4))
            rgba=Image.new('RGBA',hd.size,'white');rgba.putalpha(hd)
            x,y=(idx%16)*32,(idx//16)*height*4
            atlas.paste(rgba,(x,y))
            entries.append({'character':ch,'glyph_id':idx if name=='medium' else ord(ch),
                'atlas_rect':[x,y,32,height*4],'advance':advance,'bearing_removed':bearing,
                'logical_height':height})
            cropped=Image.new('L',native.size)
            cropped.paste(native,(-bearing,0))
            glyphs[ch]=(native,cropped,hd,advance)
        atlas.save(out/(name+'-4x.png'))
        data['fonts'][name]={'atlas':name+'-4x.png','size':list(atlas.size),'glyphs':entries}
        glyph_sets[name]=glyphs
    preview=Image.new('RGB',(1120,400),'#171d29');draw=ImageDraw.Draw(preview)
    sentence='Illil miWi WWW. Hello, Rayblade!'
    demo=glyph_sets['small']
    for row,label,kind in ((0,'Native fixed width (shown at 4x)','fixed'),
                           (1,'Native variable width (shown at 4x)','variable'),
                           (2,'4x vector font source assets - offline preview; game integration pending','hd')):
        y=row*128+12;draw.text((16,y),label,fill='#d4dbea')
        x=16
        for ch in sentence:
            native,cropped,hd,advance=demo[ch]
            image=hd if kind=='hd' else (native if kind=='fixed' else cropped).resize((32,32),Image.Resampling.NEAREST)
            preview.paste((241,244,251),(x,y+32),image)
            x+=(8 if kind=='fixed' else advance)*4
    preview.save(out/'comparison.png')
    (out/'metrics.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('Wrote {} Latin glyphs; 4x source atlases and comparison are ready.'.format(sum(len(c[1]) for c in config)))


if __name__=='__main__':main()
