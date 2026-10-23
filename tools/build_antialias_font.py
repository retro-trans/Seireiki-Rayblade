"""Retain all four supplied bitmap coverage levels in native text. Dry run first.

ASCII uses two-bit, 32-pixel rows in the same eight bytes as the old 64-bit
binary rows. Five protected wide symbols retain their binary storage. Advance
tables, all text archives, chapter images and allocations stay unchanged.
"""
import argparse,json,struct
from PIL import Image,ImageDraw
from build_bitmap_font import ROOT,ATLAS,digest
from build_font4x_patch import SMALL,MEDIUM,make_executable,START,END
from build_genei_font import SMALL_DATA,MEDIUM_DATA

VERSION='0.1.17'
PRIOR='0.1.16'
LEVELS=(0,85,187,255)


def font_bytes(archive):
    off,size=struct.unpack_from('<II',archive,8)
    assert size==99072
    return off,archive[off:off+size]


def make_font(old):
    source=Image.open(ATLAS).convert('L');assert source.size==(384,168)
    assert set(source.get_flattened_data())==set(LEVELS)
    blob=bytearray(old);blob[:8]=b'RBLF4X\0\4'
    previews={};metrics={};edge_pixels=0
    for bank,chars,height,scale,table,start in [('small',SMALL,8,1,0x20,SMALL_DATA),('medium',MEDIUM,16,2,0xa0,MEDIUM_DATA)]:
        preview=Image.new('RGBA',(1024,height*4*8));rows=[]
        for i in range(128):
            ch=chars[i] if i<len(chars) else '?'
            mask=Image.new('L',(64,height*4))
            if ch in chars[-5:]:
                for y in range(height*4):
                    a,b=struct.unpack_from('<2I',old,start+i*height*32+y*8)
                    for x in range(64):
                        if (a if x<32 else b)&(1<<(31-x%32)):mask.putpixel((x,y),255)
                kind='prior protected binary symbol'
            else:
                code=ord(ch)-32;x=code%32*12;y=code//32*24
                cell=source.crop((x,y,x+12,y+24))
                binary=cell.point(lambda v:255 if v>=128 else 0)
                bounds=binary.getbbox()
                # Keep the previous contour's origin and all advances exactly;
                # faint edge pixels outside that contour now remain visible.
                left=bounds[0] if bounds else 0
                for sy in range(24):
                    for sx in range(12):
                        level=cell.getpixel((sx,sy))
                        if not level:continue
                        px=4+(sx-left)*scale;py=4+sy*scale
                        assert 0<=px and px+scale<=32 and py+scale<=height*4,(bank,ch,px,py)
                        for dy in range(scale):
                            for dx in range(scale):mask.putpixel((px+dx,py+dy),level)
                        if level in (85,187) and i<len(chars):edge_pixels+=scale*scale
                for yy in range(height*4):
                    words=[sum(LEVELS.index(mask.getpixel((half*16+xx,yy)))<<(30-xx*2) for xx in range(16)) for half in range(2)]
                    struct.pack_into('<2I',blob,start+i*height*32+yy*8,*words)
                kind='two-bit source coverage, 32 physical pixels per row'
            if i<len(chars):
                rgba=Image.new('RGBA',mask.size,'white');rgba.putalpha(mask)
                preview.alpha_composite(rgba,((i%16)*64,(i//16)*height*4))
                rows.append({'character':ch,'glyph_id':i,'advance':old[table+i],'packed_mask_bounds':mask.getbbox(),'coverage_mask_sha256':digest(mask.tobytes()),'storage':kind})
        previews[bank]=preview
        metrics[bank]={'uniform_bitmap_scale':scale,'uniform_top_padding_at_4x':4,'uniform_left_padding_at_4x':4,'cell':[64,height*4],'glyphs':rows}
    assert blob[0x20:0x120]==old[0x20:0x120]
    return bytes(blob),previews,metrics,edge_pixels


def compose():
    base=ROOT/'work/output'/PRIOR
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    files.update({'text/'+p.name:p.read_bytes() for p in (base/'text').iterdir() if p.is_file()})
    for name in ('english-disc-report.json','READ-ME.txt'):files.pop(name,None)
    archive=files['WIN00.AFS'];off,old=font_bytes(archive)
    font,previews,metrics,edges=make_font(old)
    source=files['1ST_READ.BIN'];exe,labels,used,hooks=make_executable(source,wide=True,small_data=SMALL_DATA,medium_data=MEDIUM_DATA,antialias=True)
    allowed={p for start,raw,_ in hooks for p in range(start,start+len(raw))}
    changed={p for p,(a,b) in enumerate(zip(source,exe)) if a!=b}
    assert changed<=allowed and len(exe)==len(source)
    files['1ST_READ.BIN']=exe;files['WIN00.AFS']=archive[:off]+font+archive[off+len(font):]
    manifest=json.loads(files['font4x-patch.json'])
    manifest.update(version=VERSION,previous_build=PRIOR,font_format=4,status='Four-level bitmap alpha candidate; fresh native checks and packaging pending',
                    kernel_bytes_used=used,symbols={k:hex(labels[k]) for k in ('raster','allocate','initialize','flush')},
                    hooks=[{'offset':p,'length':len(raw),'purpose':why} for p,raw,why in hooks])
    for name in ('1ST_READ.BIN','WIN00.AFS'):manifest['files'][name]['target_sha256']=digest(files[name])
    manifest['vector_font'].update(type='user bitmap with four coverage levels; no vector font claimed',coverage='0,85,187,255 retained as ARGB4444 alpha 0,5,11,15',storage='32-pixel two-bit Latin rows; legacy 64-pixel binary protected symbols')
    manifest['antialias_font']={'version':VERSION,'source_sha256':digest(ATLAS.read_bytes()),'font_sha256':digest(font),'preserved_edge_pixels':edges,'texture_format':'ARGB4444 linear; unchanged 16-bit allocation size','advances':'byte-exact 0.1.16','native_validation':'pending','live_validation':'pending'}
    chapter=json.loads(files['chapter-card-component.json'])
    chapter.update(version=VERSION,source_build=PRIOR,archive_sha256=digest(files['WIN00.AFS']),executable_sha256=digest(exe))
    files['chapter-card-component.json']=json.dumps(chapter,indent=2).encode()+b'\n'
    for section in ('library','battle','scenario'):manifest[section]['font_update_build']=VERSION
    component=json.loads(files['text/scenario-component-report.json']);component['presentation_font_update_build']=VERSION
    files['text/scenario-component-report.json']=json.dumps(component,indent=2).encode()
    manifest['native_proof_reuse']={'source_build':PRIOR,'changed_scope':'Only renderer/helpers, their four existing hooks and font member; fresh proofs required for affected paths','exact_text_archives':'D_NAMES, D_SCE, D_PAPER, D_BMESS and chapter resources unchanged'}
    files['font4x-patch.json']=json.dumps(manifest,indent=2).encode()
    report={'version':VERSION,'source_build':PRIOR,'source_sha256':digest(ATLAS.read_bytes()),'executable_sha256':digest(exe),'font_sha256':digest(font),'archive_sha256':digest(files['WIN00.AFS']),'font_member_bytes':len(font),'kernel_bytes':used,'changed_executable_bytes':len(changed),'coverage_levels':list(LEVELS),'preserved_edge_pixels':edges,'metrics':metrics,'limits':['Bitmap enlargement adds no vector outline detail','Live GPU blending and appearance remain unverified']}
    return files,previews,manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,previews,manifest,report=compose()
    print(json.dumps({k:v for k,v in report.items() if k!='metrics'},indent=2))
    if not args.write:print('DRY RUN: no files written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    for name,im in previews.items():im.save(out/(name+'-coverage.png'))
    sample=Image.new('RGBA',(1024,260),'#171b24');d=ImageDraw.Draw(sample)
    d.text((12,8),'Supplied bitmap coverage retained - offline preview, not an in-game screenshot',fill='white')
    for y,text in [(34,'r O o R 0 - Morning, Touya!'),(104,'Mighty Sword Zeulear / Divine Sword Daifozon'),(174,'Attack  Wait  Counterattack Orders')]:
        x=12
        for ch in text:
            i=MEDIUM.index(ch);glyph=previews['medium'].crop((i%16*64,i//16*64,i%16*64+64,i//16*64+64))
            sample.alpha_composite(glyph,(x,y));x+=report['metrics']['medium']['glyphs'][i]['advance']*4
    sample.save(out/'specimen-coverage.png')
    (out/'antialias-font-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('Wrote alpha candidate:',out)


if __name__=='__main__':main()
