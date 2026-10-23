"""Recover Rayblade's original character map from exact bitmap matches.

Uses the user's local MS Mincho 12-pixel bitmap strikes. No font is copied.
Ambiguous or unmatched glyphs stay unresolved. Default is dry-run.
"""
import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from build_font_patch import ROOT,font_data,unswap


def key(image):
    bounds=image.getbbox()
    if not bounds:return None
    image=image.crop(bounds)
    return image.size,image.tobytes()


def original_key(data,gid):
    start=0x2300+(gid-512)*32;image=Image.new('L',(12,16))
    for y in range(16):
        bits=(unswap(data[start+y*2])<<8)|unswap(data[start+y*2+1])
        for x in range(12):
            if bits&(0x8000>>x):image.putpixel((x,y),255)
    return key(image)


def make_map(path):
    data=font_data();vector=ImageFont.truetype(str(path),12,index=0)
    repertoire=set()
    for hi in range(0x81,0xfd):
        for lo in range(0x40,0xfd):
            try:ch=bytes((hi,lo)).decode('cp932')
            except UnicodeDecodeError:continue
            if len(ch)==1 and not 0xe000<=ord(ch)<=0xf8ff:repertoire.add(ch)
    missing=Image.new('L',(32,32));ImageDraw.Draw(missing).text((4,4),'\U0010ffff',font=vector,fill=255)
    missing_key=key(missing.point(lambda v:255 if v>=128 else 0))
    templates={}
    for ch in repertoire:
        image=Image.new('L',(32,32));ImageDraw.Draw(image).text((4,4),ch,font=vector,fill=255)
        image=image.point(lambda v:255 if v>=128 else 0)
        k=key(image)
        if k and k!=missing_key:templates.setdefault(k,set()).add(ch)
    glyphs={}
    def put(gid,text,basis):glyphs[str(gid)]={'text':text,'basis':basis}
    latin=' '+'ABCDEFGHIJKLMNOPQRSTUVWXYZ'+'abcdefghijklmnopqrstuvwxyz'+' '+'0123456789'
    for gid,ch in enumerate(latin):put(gid,ch,'original Latin bank, visually verified')
    hira=[chr(v) for v in range(0x3041,0x3094) if chr(v) not in 'ゎゐゑ']
    for gid,ch in enumerate(hira,0x40):put(gid,ch,'original kana bank, visually verified')
    kata=[chr(v) for v in range(0x30a1,0x30f4) if chr(v) not in 'ヮヰヱ']
    for gid,ch in enumerate(kata,0x90):put(gid,ch,'original kana bank, visually verified')
    punctuation={0xe1:'ヴ',0xe2:'ヵ',0xe3:'ヶ',0xe4:'々',0xe5:'、',0xe6:'。',0xe7:'.',0xe8:'（',0xe9:'）',0xea:'「',0xeb:'」',
        0xec:'『',0xed:'』',0xee:'・',0xef:'"',0x100:'%',0x101:'～',0x102:'♥',0x103:'/',
        0x104:'=',0x105:'+',0x106:'ー',0x107:'±',0x108:'?',0x109:'!',0x10a:':',0x10b:'‥',
        0x10c:'→',0x10d:'←',0x111:'プ',0x112:'ラ',0x113:'ナ',
        0x200:'　',0x201:'㎜',0x202:'㎞',0x203:'∞',0x204:'≪',0x205:'≫',0x206:'“',0x207:'”',
        0x208:'○',0x209:'×',0x20a:'△',0x20b:'□',0x20c:'!!',0x20d:'!?',0x20e:'?!'}
    for gid,ch in punctuation.items():put(gid,ch,'original symbol bank, visually verified')
    def packed(k):
        canvas=Image.new('1',(16,16));canvas.paste(Image.frombytes('L',k[0],k[1]),(0,0))
        return int.from_bytes(canvas.tobytes(),'little')
    packed_templates=[(packed(k),sorted(v)) for k,v in templates.items() if k[0][0]<=16 and k[0][1]<=16]
    unresolved=[];exact=0;empty=0
    for gid in range(512,3328):
        k=original_key(data,gid)
        if not k:empty+=1;continue
        if str(gid) in glyphs:continue
        candidates=sorted(templates.get(k,()))
        canonical=sorted(set(unicodedata.normalize('NFKC',c) for c in candidates))
        if len(candidates)==1:
            put(gid,candidates[0],'exact MS Mincho 12px bitmap match');exact+=1
        elif len(canonical)==1 and len(canonical[0])==1:
            put(gid,canonical[0],'exact bitmap match; Unicode compatibility aliases collapsed')
            glyphs[str(gid)]['aliases']=candidates;exact+=1
        else:
            bits=packed(k)
            nearest=sorted(((bits^other).bit_count(),chars) for other,chars in packed_templates)[:3]
            unresolved.append({'glyph_id':gid,'hex':'{:04x}'.format(gid),'candidates':candidates,
                               'nearest':[{'pixel_difference':diff,'characters':chars} for diff,chars in nearest]})
    reviewed_path=ROOT/'work/source/font/reviewed-glyphs.json'
    reviewed=json.loads(reviewed_path.read_text(encoding='utf-8')) if reviewed_path.exists() else {}
    for hex_id,review in reviewed.items():
        gid=int(hex_id,16)
        if not original_key(data,gid):raise ValueError('Reviewed glyph is empty: '+hex_id)
        put(gid,review['text'],review['basis'])
    unresolved=[r for r in unresolved if str(r['glyph_id']) not in glyphs]
    result={'format':1,'source_font_sha256':hashlib.sha256(data).hexdigest(),
        'template_font':path.name,'template_font_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'template_size':12,'wide_exact_matches':exact,'wide_empty_slots':empty,
        'manually_reviewed':len(reviewed),'glyphs':glyphs,'unresolved':unresolved}
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/msmincho.ttc'))
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    result=make_map(args.font)
    print('Recovered {} total glyph IDs; {} exact wide-glyph matches; {} unresolved; {} empty wide slots.'.format(
        len(result['glyphs']),result['wide_exact_matches'],len(result['unresolved']),result['wide_empty_slots']))
    print('Unresolved sample:',json.dumps(result['unresolved'][:20],ensure_ascii=True))
    out=ROOT/'work/source/font/original-charmap.json';print('Destination:',out)
    if not args.write:print('DRY RUN: no mapping written');return
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote local character map; no game files changed')


if __name__=='__main__':main()
