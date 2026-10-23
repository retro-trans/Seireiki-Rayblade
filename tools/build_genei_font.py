"""Compose a natural-proportion GenEi font with full English build 0.1.10.

Default dry run. The glyph bank is Latin only and keeps the original member
extent. Wider glyph storage avoids individual resizing; native raster writes
are clipped at the physical surface edges. No emulator texture replacement.
"""
import argparse
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from build_font4x_patch import ROOT,SMALL,MEDIUM,make_executable

VERSION='0.1.11'
FONT=ROOT/'incoming/fonts/GenEiLatin-v2.1/GenEiLatin-Separate_v2.1/GenEiLateGoN_v2.ttf'
SMALL_DATA=0x200
MEDIUM_DATA=0x8200
MAGIC=b'RBLF4X\x00\x03'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def names_from_font(path):
    raw=path.read_bytes()
    count=struct.unpack_from('>H',raw,4)[0]
    for i in range(count):
        tag,_,offset,size=struct.unpack_from('>4sIII',raw,12+i*16)
        if tag!=b'name':continue
        block=raw[offset:offset+size]
        _,n,start=struct.unpack_from('>3H',block)
        result={}
        for j in range(n):
            platform,encoding,language,name_id,length,pos=struct.unpack_from('>6H',block,6+j*12)
            if name_id not in (0,1,2,5,13,14):continue
            data=block[start+pos:start+pos+length]
            text=data.decode('utf-16-be' if platform in (0,3) else 'mac_roman',errors='replace')
            result.setdefault(str(name_id),[])
            if text not in result[str(name_id)]:result[str(name_id)].append(text)
        return result
    raise ValueError('No font naming table')


def make_font(font_path=FONT):
    base=(ROOT/'work/output/0.1.10/WIN00.AFS').read_bytes()
    _,capacity=struct.unpack_from('<II',base,8)
    assert capacity==99072
    blob=bytearray(capacity);blob[:8]=MAGIC
    previews={};tables={};metrics={}
    for name,chars,height,em,baseline,table,start in (
        ('small',SMALL,8,26,23,0x20,SMALL_DATA),
        ('medium',MEDIUM,16,53,47,0xa0,MEDIUM_DATA)):
        face=ImageFont.truetype(str(font_path),em,layout_engine=ImageFont.Layout.BASIC)
        atlas=Image.new('RGBA',(1024,256 if height==8 else 512),(255,255,255,0))
        advances=[];rows=[]
        for i in range(128):
            real=i if i<len(chars) else chars.index('?');ch=chars[real]
            contour='—' if ch=='ー' else ch
            # Common em size and baseline for the whole size bank; never
            # resize/crop/stretch individual glyph images to legacy bounds.
            bounds=face.getbbox(contour,anchor='ls')
            x0,y0,x1,y1=bounds
            assert 0<=x0+4 and x1+4<=64 and 0<=y0+baseline and y1+baseline<=height*4,(name,ch,bounds)
            if ch!=' ':
                tofu=face.getmask('\U0010ffff')
                mask=face.getmask(contour)
                assert (mask.size,bytes(mask))!=(tofu.size,bytes(tofu)),('Missing contour',ch)
            mask=Image.new('L',(64,height*4))
            ImageDraw.Draw(mask).text((4,baseline),contour,font=face,fill=255,anchor='ls')
            mask=mask.point(lambda p:255 if p>=128 else 0)
            advance=max(1,math.floor(face.getlength(contour)/4+0.5))
            assert advance<=16
            blob[table+i]=advance;advances.append(advance)
            for y in range(height*4):
                words=[sum(1<<(31-x) for x in range(32) if mask.getpixel((half*32+x,y))) for half in range(2)]
                struct.pack_into('<2I',blob,start+i*height*32+y*8,*words)
            if i<len(chars):
                rgba=Image.new('RGBA',mask.size,'white');rgba.putalpha(mask)
                atlas.alpha_composite(rgba,((i%16)*64,(i//16)*height*4))
                rows.append({'character':ch,'glyph_id':i,'advance':advance,
                    'unrounded_advance':face.getlength(contour)/4,'source_bounds':list(bounds),
                    'source_mask_sha256':digest(mask.tobytes())})
        assert start+128*height*32<=capacity
        previews[name]=atlas;tables[name]=advances
        metrics[name]={'em_at_4x':em,'baseline_at_4x':baseline,'uniform_left_padding_at_4x':4,
            'cell':[64,height*4],'glyphs':rows}
    assert SMALL_DATA+128*8*32==MEDIUM_DATA
    return bytes(blob),previews,tables,metrics


def compose():
    base=ROOT/'work/output/0.1.10'
    prior=json.loads((base/'font4x-patch.json').read_text('utf-8'))
    original=(base/'1ST_READ.BIN').read_bytes()
    assert digest(original)==prior['files']['1ST_READ.BIN']['target_sha256']
    font,previews,tables,metrics=make_font()
    exe,labels,used,hooks=make_executable(original,wide=True,small_data=SMALL_DATA,medium_data=MEDIUM_DATA)
    allowed={p for start,raw,_ in hooks for p in range(start,start+len(raw))}
    changed={p for p,(a,b) in enumerate(zip(original,exe)) if a!=b}
    assert changed<=allowed and len(exe)==len(original)
    for lo,hi in [(0x83f0,0x9000),(0x6ac64,0x6b28e),(0x6bc00,0x6c32a),
        (0x6cfb2,0x6d4c2),(0x10e9e,0x10ee4),(0x104b4,0x104b8)]:
        assert exe[lo:hi]==original[lo:hi],('Inherited code changed',hex(lo))
    afs=bytearray((base/'WIN00.AFS').read_bytes())
    assert digest(afs)==prior['files']['WIN00.AFS']['target_sha256']
    offset,capacity=struct.unpack_from('<II',afs,8)
    afs[offset:offset+capacity]=font
    assert capacity==len(font)
    for i in range(1,90):
        off,size=struct.unpack_from('<II',afs,8+i*8)
        assert afs[off:off+size]==(base/'WIN00.AFS').read_bytes()[off:off+size]
    manifest=copy.deepcopy(prior)
    manifest.update(version=VERSION,previous_build='0.1.10',
        status='GenEi natural-metric Latin font candidate; native and live checks pending',
        font_format=3,small_bitmaps_offset=SMALL_DATA,medium_bitmaps_offset=MEDIUM_DATA,
        kernel_bytes_used=used,kernel_bytes_available=0x6bc00-0x6b28e,
        symbol_vector_font=None,
        vector_font={'source_family':'GenEi LateGo v2','source_style':'Medium',
            'distribution_version':'2.1','source_url':'https://okoneya.jp/font/genei-latin.html',
            'download_url':'https://okoneya.jp/font/GenEiLatin-Separate_v2.1.zip',
            'source_filename':FONT.name,'source_sha256':digest(FONT.read_bytes()),
            'game_bitmap_name':'Rayblade Latin HD','license':'SIL Open Font License 1.1',
            'proportions':'uniform em size and baseline per font size; no per-glyph resizing',
            'advances':'natural per-glyph advances rounded to the native integer logical grid',
            'bearing':'uniform 1 logical pixel left inset retains negative j bearing without cropping',
            'kerning':'not implemented; individual advance metrics used'},
        hooks=[{'offset':off,'length':len(raw),'purpose':purpose} for off,raw,purpose in hooks],
        symbols={k:hex(labels[k]) for k in ('raster','allocate','initialize','flush')})
    manifest.pop('native_proof_reuse',None)
    manifest['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    manifest['files']['WIN00.AFS']['target_sha256']=digest(afs)
    for section in ('library','battle','scenario'):
        manifest[section]['font_update_build']=VERSION
    copied={}
    for path in (base/'text').iterdir():
        if path.is_file():copied['text/'+path.name]=path.read_bytes()
    copied['D_SCE.AFS']=(base/'D_SCE.AFS').read_bytes()
    copied['library-native-test.json']=(base/'library-native-test.json').read_bytes()
    copied['library-patch-report.json']=json.dumps(manifest['library'],indent=2).encode()
    copied['archive-repack-report.json']=(base/'archive-repack-report.json').read_bytes()
    license_dir=FONT.parent
    notices=names_from_font(FONT)
    copyright_text='\n\n'.join(notices.get('0',[]))
    license_text=('Rayblade Latin HD bitmap subset\nSource: GenEi LateGo v2 (distribution 2.1), '+
        'https://okoneya.jp/font/genei-latin.html\n\n'+copyright_text+'\n\n'+
        (license_dir/'LICENSE.txt').read_text('utf-8'))
    copied['FONT-LICENSE.txt']=license_text.encode('utf-8')
    sample='Ayaka: "Good morning, Touya Kazami."'
    specimen=Image.new('RGBA',(1024,280),'#141820');draw=ImageDraw.Draw(specimen)
    draw.text((12,8),'GenEi LateGo v2.1 - uniform scale and natural advances - offline preview',fill='white')
    for name,chars,height,y,line in [('small',SMALL,8,44,sample),
        ('medium',MEDIUM,16,120,'Ayaka: "Good morning,'),('medium',MEDIUM,16,192,'Touya Kazami."')]:
        x=12
        for ch in line:
            index=chars.index(ch);gx=index%16*64;gy=index//16*height*4
            glyph=previews[name].crop((gx,gy,gx+64,gy+height*4))
            assert x+64<=specimen.width
            specimen.alpha_composite(glyph,(x,y));x+=tables[name][index]*4
    previews['specimen']=specimen
    report={'version':VERSION,'base_version':'0.1.10','executable_sha256':digest(exe),
        'font_sha256':digest(font),'archive_sha256':digest(afs),'font_member_bytes':len(font),
        'kernel_bytes':used,'changed_executable_bytes':len(changed),
        'other_archive_members':'all 89 byte-exact; all offsets and member IDs retained',
        'font':manifest['vector_font'],'source_names':notices,'metrics':metrics,
        'pending':['Native raster/ABI/edge checks','Scenario and battle regression checks',
            'Disc packaging and live dialogue','Word-aware pixel wrapping and other UI layout']}
    return {'1ST_READ.BIN':exe,'WIN00.AFS':bytes(afs),**copied},previews,manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    files,previews,manifest,report=compose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('metrics','source_names')},indent=2))
    out=ROOT/'work/output'/VERSION
    if not args.write:
        print('DRY RUN: no components or previews written');return
    out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    for name,im in previews.items():im.save(out/(name+'-genei-4x.png'))
    (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
    (out/'genei-font-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8')
    entry='''## 0.1.11 — GenEi Latin font with natural proportions

- Replaced individually stretched Tahoma contours with Latin glyphs from the user-selected GenEi LateGo v2.1. Each font size uses one em size and baseline with natural advances rounded to the native logical grid; no individual-letter resizing. Protected source marks use the same font; model-code U+30FC remains distinct and uses an em-dash contour. The generated bitmap subset is named Rayblade Latin HD, with source copyright and OFL 1.1 notices included.
- Expanded glyph storage to two 32-bit words per row, fitting both size banks inside the original 99,072-byte member. Raster clipping guards physical row/surface boundaries. Integrated game rendering remains up to 4x per axis with every texture dimension capped at 1024. The ordered archive layout and all story/menu/library/battle text bytes are retained.
- Candidate components created for native verification. Disc packaging, live appearance and word-aware wrapping remain pending; the original 30-character wrapper is unchanged in this candidate. Original dump/prior builds unchanged; no release.

'''
    if '## 0.1.11 —' not in old:cp.write_text(old.replace('## 0.1.10 —',entry+'## 0.1.10 —',1),'utf-8')
    print('Wrote candidate components and font previews:',out)


if __name__=='__main__':main()
