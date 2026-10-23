"""Read-only comparison of original bitmap glyphs with local Japanese fonts."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from build_font_patch import font_data,unswap


def bitmap(gid):
    font=font_data();start=0x2300+(gid-512)*32
    im=Image.new('L',(12,16))
    for y in range(16):
        bits=(unswap(font[start+y*2])<<8)|unswap(font[start+y*2+1])
        for x in range(12):
            if bits&(0x8000>>x):im.putpixel((x,y),255)
    return im.crop(im.getbbox())


def score(a,b):
    width=max(a.width,b.width);height=max(a.height,b.height)
    ca=Image.new('1',(width,height));cb=Image.new('1',(width,height))
    ca.paste(a,(0,0));cb.paste(b,(0,0))
    aa=list(ca.getdata());bb=list(cb.getdata())
    return sum(x!=y for x,y in zip(aa,bb))


def main():
    known={0x210:'亜',0x216:'一',0x22b:'機',0x234:'軍',0x24a:'高',0x24d:'国',
           0x270:'人',0x276:'星',0x277:'生',0x278:'聖',0x27b:'戦',0x2c6:'無',0x2c8:'夜'}
    results=[]
    for name in ('msgothic.ttc','msmincho.ttc','meiryo.ttc','BIZ-UDGothicR.ttc','simsun.ttc'):
        path=Path('C:/Windows/Fonts')/name
        for index in (0,1,2):
            for size in (11,12,13,14,15,16):
                try:f=ImageFont.truetype(str(path),size,index=index)
                except OSError:continue
                distances=[]
                for gid,ch in known.items():
                    im=Image.new('L',(40,40));ImageDraw.Draw(im).text((4,4),ch,font=f,fill=255)
                    im=im.point(lambda v:255 if v>=128 else 0);im=im.crop(im.getbbox())
                    distances.append(score(bitmap(gid),im))
                results.append((sum(distances),name,index,size,distances))
    for row in sorted(results)[:12]:print(row)


if __name__=='__main__':main()
