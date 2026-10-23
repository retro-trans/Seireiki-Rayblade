"""Integrate the user-supplied Latin bitmap into build 0.1.13. Default dry run.

Retains the executable, every translation and the existing conservative story
breaks. Verification remeasures those breaks with the new variable advances.
The supplied bitmap is sampled faithfully, not traced into invented outlines.
"""
import argparse,copy,json,math,struct
from pathlib import Path
from PIL import Image,ImageDraw
from build_genei_font import ROOT,SMALL_DATA,MEDIUM_DATA,MAGIC,digest
from build_font4x_patch import SMALL,MEDIUM

VERSION='0.1.14'
PRIOR='0.1.13'
ATLAS=ROOT/'incoming/fonts/user-bitmap/dialogue-atlas.png'


def prior_font():
    raw=(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()
    off,size=struct.unpack_from('<II',raw,8)
    return raw,off,size,raw[off:off+size]


def source_cell(char):
    assert ' '<=char<='~'
    index=ord(char)-32
    return (index%32*12,index//32*24,12,24)


def make_font():
    source=Image.open(ATLAS).convert('L');assert source.size==(384,168)
    _,_,size,old=prior_font();assert size==99072 and old[:8]==MAGIC
    blob=bytearray(old);metrics={};previews={}
    for name,chars,height,scale,table,start in (
        ('small',SMALL,8,1,0x20,SMALL_DATA),
        ('medium',MEDIUM,16,2,0xa0,MEDIUM_DATA)):
        preview=Image.new('RGBA',(1024,height*4*8),(0,0,0,0));rows=[]
        for i in range(128):
            char=chars[i] if i<len(chars) else '?'
            if char in SMALL[95:]:
                # Protected story marks stay byte-exact; no missing glyphs
                # are silently replaced with Latin punctuation.
                mask=Image.new('L',(64,height*4))
                for y in range(height*4):
                    left,right=struct.unpack_from('<2I',old,start+i*height*32+y*8)
                    for x in range(64):
                        bits=left if x<32 else right
                        if bits & (1<<(31-x%32)):mask.putpixel((x,y),255)
                advance=old[table+i];bounds=None;origin='prior protected non-ASCII mark'
            else:
                x,y,w,h=source_cell(char)
                cell=source.crop((x,y,x+w,y+h)).point(lambda v:255 if v>=128 else 0)
                bounds=cell.getbbox();mask=Image.new('L',(64,height*4))
                if char==' ':
                    assert bounds is None;advance=2 if name=='small' else 3
                else:
                    assert bounds is not None,('Blank supplied glyph',char)
                    left,_,right,_=bounds
                    # Trim blank columns for variable spacing, while all
                    # glyphs share one scale, y origin and source baseline.
                    ink=cell.crop((left,0,right,24))
                    ink=ink.resize((ink.width*scale,24*scale),Image.Resampling.NEAREST)
                    mask.paste(ink,(4,4))
                    advance=math.ceil(ink.width/4)+1
                origin='user bitmap ASCII cell'
            assert 1<=advance<=16
            blob[table+i]=advance
            for y in range(height*4):
                words=[sum(1<<(31-x) for x in range(32) if mask.getpixel((half*32+x,y))) for half in range(2)]
                struct.pack_into('<2I',blob,start+i*height*32+y*8,*words)
            if i<len(chars):
                rgba=Image.new('RGBA',mask.size,'white');rgba.putalpha(mask)
                preview.alpha_composite(rgba,((i%16)*64,(i//16)*height*4))
                rows.append({'character':char,'glyph_id':i,'advance':advance,'source_cell':source_cell(char) if origin.startswith('user') else None,
                    'source_ink_bounds':bounds,'packed_mask_bounds':mask.getbbox(),
                    'mask_sha256':digest(mask.tobytes()),'origin':origin})
        previews[name]=preview
        metrics[name]={'uniform_bitmap_scale':scale,'uniform_left_padding_at_4x':4,
            'uniform_top_padding_at_4x':4,'cell':[64,height*4],'glyphs':rows}
    assert blob[:8]==MAGIC
    return bytes(blob),previews,metrics


def compose():
    base=ROOT/'work/output'/PRIOR
    raw,off,size,old=prior_font();font,previews,metrics=make_font()
    afs=raw[:off]+font+raw[off+size:]
    manifest=copy.deepcopy(json.loads((base/'font4x-patch.json').read_text('utf-8')))
    assert digest(raw)==manifest['files']['WIN00.AFS']['target_sha256']
    exe=(base/'1ST_READ.BIN').read_bytes()
    assert digest(exe)==manifest['files']['1ST_READ.BIN']['target_sha256']
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower() not in ('.png',)}
    for p in (base/'text').iterdir():
        if p.is_file():files['text/'+p.name]=p.read_bytes()
    for name in ('english-disc-report.json','genei-font-native-test.json','inline-control-native-test.json','word-wrap-native-test.json','READ-ME.txt'):
        files.pop(name,None)
    files['WIN00.AFS']=afs
    manifest.update(version=VERSION,previous_build=PRIOR,status='User bitmap font candidate; fresh raster/layout verification pending')
    manifest['files']['WIN00.AFS']['target_sha256']=digest(afs)
    manifest['vector_font']={'source_family':'User-supplied dialogue bitmap','type':'bitmap; no vector font claimed',
        'source_filename':'dialogue-atlas.png','source_sha256':digest(ATLAS.read_bytes()),
        'source_dimensions':[384,168],'ASCII_grid':[32,12,24],'game_bitmap_name':'Rayblade Supplied Latin',
        'glyphs':'All 95 printable ASCII glyphs use the supplied atlas; five protected non-ASCII marks retain the prior GenEi contours',
        'spacing':'Ink widths plus one logical pixel; blank side columns trimmed; no individual-letter stretching',
        'sampling':'Source luma >=128; uniform 2x bitmap enlargement for medium, 1x for small; no invented outline detail',
        'license':'Supplied atlas provenance/license not supplied; GenEi OFL applies only to the five retained marks'}
    report={'version':VERSION,'base_version':PRIOR,'executable_sha256':digest(exe),'font_sha256':digest(font),
        'archive_sha256':digest(afs),'source':manifest['vector_font'],'metrics':metrics,
        'unchanged':['Executable','D_SCE archive and all story breaks','All translations','89 non-font WIN00 members','Original dump and prior builds'],
        'pending':['Native raster checks and remeasurement of all existing story lines','Live appearance','Reported menu alignment/help wrapping and chapter-title image']}
    # Fresh checks use the new font; historical reports retain their identity.
    component=json.loads(files['text/scenario-component-report.json'])
    wrap=component['word_wrap'];wrap['boundary_generation_font_sha256']=wrap['font_sha256']
    wrap.update(font_sha256=digest(font),current_font_validation='pending; boundaries unchanged from 0.1.13',
        native_verification='Historical executable/archive proofs retained; current-font line measurement pending',live_verification='pending for 0.1.14')
    component['presentation_font_update_build']=VERSION
    manifest['scenario']['word_wrap']=copy.deepcopy(wrap)
    manifest['native_proof_reuse']={'source_build':PRIOR,'executable_sha256':digest(exe),
        'D_SCE_archive_sha256':digest(files['D_SCE.AFS']),
        'scope':'Executable and text-component proofs reused by exact hashes; raster/width/inline cursor checks must be fresh for the new font'}
    files['text/scenario-component-report.json']=json.dumps(component,indent=2).encode()
    files['FONT-LICENSE.txt']=(b'Rayblade Supplied Latin: printable ASCII contours from the user-supplied bitmap.\n'
        b'Atlas provenance/license was not provided. No public release is authorized.\n'
        b'The five protected non-ASCII marks remain from GenEi; their notices follow.\n\n'+(base/'FONT-LICENSE.txt').read_bytes())
    return files,previews,manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,previews,manifest,report=compose()
    print(json.dumps({k:v for k,v in report.items() if k!='metrics'},indent=2))
    if not args.write:print('DRY RUN: no files written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    for name,im in previews.items():im.save(out/(name+'-bitmap.png'))
    specimen=Image.new('RGBA',(1024,260),'#171b24');draw=ImageDraw.Draw(specimen)
    draw.text((12,8),'Supplied bitmap font - offline asset preview (not an in-game screenshot)',fill='white')
    for y,line in [(34,'r O o R 0  -  Morning, Touya!'),(104,'Mighty Sword Zeulear / Divine Sword Daifozon'),(174,'Attack  Wait  Counterattack Orders')]:
        x=12
        for c in line:
            i=MEDIUM.index(c);glyph=previews['medium'].crop((i%16*64,i//16*64,i%16*64+64,i//16*64+64))
            if x+64>1024:raise ValueError('Specimen overflow')
            specimen.alpha_composite(glyph,(x,y));x+=report['metrics']['medium']['glyphs'][i]['advance']*4
    specimen.save(out/'specimen-bitmap.png')
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
    (out/'bitmap-font-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('Wrote candidate:',out)


if __name__=='__main__':main()
