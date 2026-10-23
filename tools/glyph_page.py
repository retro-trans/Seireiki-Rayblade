"""Render a labelled original-font glyph page for encoding research. Dry run by default."""
import argparse
from build_font_patch import ROOT,font_data,unswap


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--start',type=lambda v:int(v,0),default=512)
    ap.add_argument('--count',type=int,default=256)
    ap.add_argument('--cols',type=int,default=16)
    ap.add_argument('--scale',type=int,default=3)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    if args.start<0 or args.start+args.count>3328:raise ValueError('Glyph range outside font')
    out=ROOT/'work/source/font'/('glyphs-{:04x}{}.png'.format(args.start,'' if args.scale==3 else '-s'+str(args.scale)))
    print('Render original glyph IDs {}..{} to {}'.format(args.start,args.start+args.count-1,out))
    if not args.write:print('DRY RUN: no files written');return
    from PIL import Image,ImageDraw
    data=font_data();s=args.scale;cw=max(64,12*s+16);ch=16*s+24
    page=Image.new('RGB',(args.cols*cw,((args.count+args.cols-1)//args.cols)*ch),'#151923');draw=ImageDraw.Draw(page)
    for n,gid in enumerate(range(args.start,args.start+args.count)):
        x,y=n%args.cols*cw,n//args.cols*ch;draw.text((x+2,y+2),'{:04x}'.format(gid),fill='#96b6e5')
        width=8 if gid<512 else 12;pitch=1 if gid<512 else 2
        off=0x300+gid*16 if gid<512 else 0x2300+(gid-512)*32
        for row in range(16):
            bits=unswap(data[off+row*pitch])<<8
            if pitch==2:bits|=unswap(data[off+row*pitch+1])
            for col in range(width):
                if bits&(0x8000>>col):draw.rectangle((x+4+col*s,y+18+row*s,x+3+(col+1)*s,y+17+(row+1)*s),fill='white')
    out.parent.mkdir(parents=True,exist_ok=True);page.save(out)
    print('Wrote original glyph page')


if __name__=='__main__':main()
