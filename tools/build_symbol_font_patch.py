"""Compose the symbol-capable native font with the existing 0.1.4 translation.

Preserves menu/name/library components and shared-memory changes. The original
dump and prior builds are read only. Default is a dry run; no release upload.
"""
import argparse,copy,hashlib,json,struct
from pathlib import Path
from build_font4x_patch import ROOT,VERSION,SYMBOL_FONT,SMALL,MEDIUM,build,make_executable


def digest(data):return hashlib.sha256(data).hexdigest()


def compose(vector,symbol_vector):
    fresh,previews,tables,font_manifest=build(vector,symbol_vector)
    base=ROOT/'work/output/0.1.4'
    prior=json.loads((base/'font4x-patch.json').read_text('utf-8'))
    old={name:(base/name).read_bytes() for name in prior['files']}
    for name,raw in old.items():
        if digest(raw)!=prior['files'][name]['target_sha256']:raise ValueError('Prior component hash mismatch: '+name)
    exe,_,_,_=make_executable(old['1ST_READ.BIN'])
    allowed={i for h in font_manifest['hooks'] for i in range(h['offset'],h['offset']+h['length'])}
    changed=[i for i,(a,b) in enumerate(zip(exe,old['1ST_READ.BIN'])) if a!=b]
    assert len(exe)==len(old['1ST_READ.BIN']) and set(changed)<=allowed
    for hook in font_manifest['hooks']:
        start=hook['offset'];end=start+hook['length']
        assert exe[start:end]==fresh['1ST_READ.BIN'][start:end]
    assert exe[0x6ac64:0x6b28e]==fresh['1ST_READ.BIN'][0x6ac64:0x6b28e]
    off,size=struct.unpack_from('<II',fresh['WIN00.AFS'],8)
    font=fresh['WIN00.AFS'][off:off+size]
    afs=bytearray(old['WIN00.AFS']);dest,capacity=struct.unpack_from('<II',afs,8)
    assert len(font)==capacity==99072
    afs[dest:dest+capacity]=font
    count=struct.unpack_from('<I',afs,4)[0]
    for index in range(1,count):
        location,length=struct.unpack_from('<II',afs,8+index*8)
        assert afs[location:location+length]==old['WIN00.AFS'][location:location+length]
    assert afs[:dest]==old['WIN00.AFS'][:dest] and afs[dest+capacity:]==old['WIN00.AFS'][dest+capacity:]
    files={'1ST_READ.BIN':exe,'WIN00.AFS':bytes(afs)}
    manifest=copy.deepcopy(font_manifest)
    manifest['status']='local symbol-font update with existing menu/name/library translation; gameplay validation pending'
    manifest['previous_build']='0.1.4';manifest['library']=copy.deepcopy(prior['library'])
    manifest['library']['font_update_build']=VERSION
    for name,raw in files.items():manifest['files'][name]['target_sha256']=digest(raw)
    copied={}
    for name in ['D_NAMES.BIN','D_NAMES.en.dec.bin','names-component-report.json',
                 'D_PAPER.BIN','D_PAPER.en.dec.bin','library-component-report.json']:
        copied['text/'+name]=(base/'text'/name).read_bytes()
    proof=(base/'library-native-test.json').read_bytes();validation=json.loads(proof)
    assert validation['filter_function_sha256']==digest(exe[0x6bf00:0x6c32a])
    assert validation['library_component_sha256']==digest(copied['text/D_PAPER.en.dec.bin'])
    copied['library-native-test.json']=proof
    from PIL import Image,ImageDraw
    specimen=Image.new('RGBA',(960,260),'#151d2a');draw=ImageDraw.Draw(specimen)
    draw.text((16,8),'Native font 0.1.5 - 4x source contours, offline specimen',fill='white')
    sample='Test: ≪Ze=Ode≫  HP 42 ♥ ♪ AーB'
    for name,chars,height,y in [('small',SMALL,8,52),('medium',MEDIUM,16,150)]:
        draw.text((16,y-22),name.title()+' - Latin spacing retained; five protected source marks',fill='#c6d8ef')
        x=16
        for char in sample:
            i=chars.index(char);gx=(i%16)*32;gy=(i//16)*height*4
            glyph=previews[name].crop((gx,gy,gx+32,gy+height*4))
            specimen.alpha_composite(glyph,(x,y));x+=tables[name][i]*4
    previews['symbol-specimen']=specimen
    report={'version':VERSION,'base_translation':'0.1.4','font_format':2,
            'original_and_prior_builds':'unchanged','executable_changed_bytes_vs_0_1_4':len(changed),
            'archive_members_other_than_font':'all89 unchanged','font_member_bytes':len(font),
            'atlas_dimensions':{name:list(previews[name].size) for name in ['small','medium']},
            'old_latin_shapes_preserved':190,'old_latin_advances_preserved':191,
            'small_space':'fixed legacy advance-table/bitmap overlap; now blank',
            'text_components_unchanged':{name:digest(raw) for name,raw in copied.items()},
            'pending':['Live symbol/font checks','Long-session memory/layout checks',
                       'Story/battle insertion, full VM coverage and meaning review']}
    return files,copied,previews,manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/tahoma.ttf'))
    ap.add_argument('--symbol-font',type=Path,default=SYMBOL_FONT)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,copied,previews,manifest,report=compose(args.font,args.symbol_font)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not args.write:print('DRY RUN: no component files written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,data in {**files,**copied}.items():
        path=out/name;path.parent.mkdir(exist_ok=True);path.write_bytes(data)
    for name,preview in previews.items():preview.save(out/(name+'-latin-4x.png'))
    (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    (out/'symbol-font-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    print('Wrote local symbol-font components:',out)


if __name__=='__main__':main()
