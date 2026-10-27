"""Repair native signed fields, compact notices and translate room-map tags."""
import argparse,copy,json,re,struct
from functools import lru_cache
import numpy as np
from PIL import Image,ImageDraw
from build_bitmap_font import ROOT,digest
from build_names_translation import compose as names_compose
from build_map_font_patch import member
from build_font4x_patch import MEDIUM,BASE
from sh4_asm import Assembler
from english_text_codec import encode,decode
from test_ui_layouts import entry,parse_ui
from test_outline_font import legacy_mask
from test_library_headers import setup,call,SHARED,SCRATCH
from check_native_text_components import verify
from analyze_skies_font import read_executable,skies_glyph,EXPECTED_EXE
from audit_texture_archive import untwiddle_indices,decode_pvr
from rayblade_codec import compress,decompress
from disc_inventory import Disc,SECTOR
from package_archive_test_disc import substitute_payload_sector
from build_movie_test_disc import write_plan
from build_native_font_mode_disc import plan as font_plan
from afs_layout import require_native_layouts

VERSION,PRIOR='0.7.10','0.7.9'
OUT=ROOT/'work/output/ui-fixes-candidate'
RECIPE=ROOT/'work/translation/en/ui/numeric-room-fix.en.json'
# Sprite 35 + portrait index; visually read against the retail atlas, then
# linked to the existing character glossary. The last unidentified tag (66)
# is excluded rather than assigning an unproved character.
ROOM_IDS=(17,89,3,2,4,6,5,7,11,15,16,9,14,12,138,84,87,53,86,88,8,100,13,23,32,19,10,90,20,21,23,None,47,42)


def sign_patch():
    # Original emits F0 05/06/07 (+, minus, plus/minus) before the decimal.
    # Emit one Latin glyph, retaining the native magnitude, padding and ring.
    a=Assembler(BASE+0x2c1ae)
    a.emit(0x52f2);a.emit(0x84f3);a.emit(0x8806)
    a.imm(MEDIUM.index('+'),3);a.branch('bf','selected');a.imm(MEDIUM.index('-'),3)
    a.label('selected');a.store('b',3,2);a.addi(1,2);a.emit(0x1f22)
    a.labels['digits']=BASE+0x2c1e8;a.branch('bra','digits');a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=0x1c
    return raw+bytes.fromhex('0900')*((0x1c-len(raw))//2)


def room_mask(source,text):
    glyphs=[]
    for ch in text:
        cell=skies_glyph(source,ord(ch),(0,85,187,255));box=cell.getbbox();assert box
        crop=cell.crop((box[0],0,box[2],24));width=(crop.width+2)//3*3
        pad=Image.new('L',(width,24));pad.paste(crop,(0,0))
        # Uniform 1/3 reduction of original pixels, with common baseline.
        glyphs.append(pad.resize((width//3,8),Image.Resampling.BOX))
    mask=Image.new('L',(sum(g.width+1 for g in glyphs)-1,8));x=0
    for g in glyphs:mask.paste(g,(x,0));x+=g.width+1
    assert mask.width+1<=32,(text,mask.size)
    return np.asarray(mask)


def room_archive(source,names):
    raw=member(source,23);plain,used=decompress(raw[16:]);assert used==len(raw)-16
    image,info=decode_pvr(plain);assert (info['pixel_format'],info['data_format'],image.size)==(0,13,(1024,256))
    dat=member(source,22);pof=dat.index(b'POF0');start=pof+8+struct.unpack_from('<I',dat,pof+4)[0]
    indices=untwiddle_indices(1024,256);before=np.frombuffer(plain[32:],dtype='<u2')[indices].copy();after=before.copy();allowed=np.zeros_like(before,dtype=bool)
    skies,_=read_executable();assert digest(skies)==EXPECTED_EXE;records=[]
    preview=Image.new('RGB',(520,18*33+24),'#26323a');draw=ImageDraw.Draw(preview);draw.text((4,4),'Retail room tags / English (4x inspection)',fill='white')
    for n,index in enumerate(ROOM_IDS):
        if index is None:continue
        sprite=35+n;w,h,cx,cy,u0,v0,u1,v1,tex,flags=struct.unpack_from('<HHhh6H',dat,start+sprite*20)
        box=[u0*4,v0,u1*4,v1];assert (w,h,cx,cy,tex,flags)==(32,16,16,-8,0,0)
        row=names[f'names.g02.{index:03d}'];text=row['en'];mask=room_mask(skies,text);x0,y0,x1,y1=box
        allowed[y0:y1,x0:x1]=True;after[y0:y1,x0:x1]=0
        x=x0+(32-mask.shape[1]-1)//2;y=y0+4
        for yy,xx in zip(*np.nonzero(mask)):
            after[y+yy+1,x+xx+1]=0x8000
        for yy,xx in zip(*np.nonzero(mask)):
            # Binary alpha asset: antialias original coverage into grayscale.
            c=(int(mask[yy,xx])*31+127)//255;after[y+yy,x+xx]=0x8000|(c<<10)|(c<<5)|c
        records.append({'sprite':sprite,'en':text,'name_id':row['id'],'name_source_sha256':row['source_sha256'],
            'box':box,'mask_size':[mask.shape[1],8],'source_pixels_sha256':digest(before[y0:y1,x0:x1].tobytes())})
        # Contact sheet rows are eighteen pixels high; source crop below uses
        # 1x plus text, while separate full texture supports close inspection.
        row_y=24+(len(records)-1)*18;preview.paste(image.crop(box),(4,row_y));draw.text((44,row_y+2),f'{sprite}: {text}',fill='white')
    assert np.array_equal(before[~allowed],after[~allowed])
    linear=np.empty(1024*256,dtype='<u2');linear[indices.ravel()]=after.ravel()
    target=plain[:32]+linear.tobytes();packed=raw[:16]+compress(target)
    assert decompress(packed[16:])==(target,len(packed)-16)
    count=struct.unpack_from('<I',source,4)[0];first=struct.unpack_from('<I',source,8)[0]
    def rebuild(first):
        result=bytearray(source[:8+8*count+8]);result.extend(bytes(first-len(result)))
        for i in range(count):
            payload=packed if i==23 else member(source,i);at=(len(result)+2047)//2048*2048
            result.extend(bytes(at-len(result)));result.extend(payload);struct.pack_into('<II',result,8+i*8,at,len(payload))
        return result
    archive=rebuild(first)
    while len(archive)>len(source):first-=2048;archive=rebuild(first)
    archive.extend(bytes(len(source)-len(archive)));archive=bytes(archive);require_native_layouts({'ITM00.AFS':archive})
    for i in range(count):
        if i!=23:assert member(archive,i)==member(source,i)
    return archive,target,packed[16:],records,preview,decode_pvr(target)[0]


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;before=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(before)
    # Pin the original native sign writer byte-for-byte, independent of assets.
    original=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    assert before[0x2c1ae:0x2c1ca]==original[0x2c1ae:0x2c1ca]
    exe[0x2c1ae:0x2c1ca]=sign_patch()
    rows={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    recipe=json.loads((base/'ui-layouts.en.json').read_text('utf-8'));changes=[]
    for key,text in [('names.g00.107','Topic Log'),('names.g00.199','Not enough free blocks.<NL>Saving requires at least<NL>8 free blocks.')]:
        row=rows[key];old=decode(entry((base/'text/D_NAMES.en.dec.bin').read_bytes(),key))[0]
        recipe['rows'][key]={'en':text,'source_sha256':row['source_sha256'],'prior_en_sha256':digest(row['en'].encode()),'reason':'Compact complete notice/heading for its existing frame.'}
        changes.append({'id':key,'before':old,'after':text})
    plain,packed,names_report=names_compose(overrides=recipe['rows'],version=VERSION);stream=len(packed);capacity=len((base/'text/D_NAMES.BIN').read_bytes());assert stream<=capacity;packed+=bytes(capacity-stream)
    disc=Disc(next(ROOT.glob('*.cue')));ent=next(e for e in disc.inventory() if e['path']=='ITM00.AFS');source=disc.read(ent['lba'],ent['size'])
    archive,texture,prs,tags,preview,image=room_archive(source,rows)
    recipe.update(version=VERSION,previous_build=PRIOR)
    files={'1ST_READ.BIN':bytes(exe),'D_NAMES.BIN':packed,'ITM00.AFS':archive}
    report={'version':VERSION,'source_build':PRIOR,'files':{n:{'size':len(v),'sha256':digest(v)} for n,v in files.items()},
        'signed_number_change':{'range':['0x2c1ae','0x2c1ca'],'positive':'+','negative':'-','neutral':'+0 instead of the unavailable original plus/minus symbol','magnitude_and_gameplay':'unchanged'},
        'text_changes':changes,'room_tags':tags,'source_ITM00_sha256':digest(source),'texture_sha256':digest(texture),
        'name_tag_scope':'33 source-read tags, including Clovis and Arthur; unidentified sprite 66 remains exact.',
        'font':'Uniform 1/3 reduction of original Skies USA Dreamcast 12x24 VQ pixels; no individual letter stretching',
        'unrelated_ITM00_members':'All 25 other payloads and sprite geometry exact','names_decoded_sha256':digest(plain),
        'live_validation':'pending','release':False}
    return files,plain,recipe,names_report,report,texture,prs,preview,image


def check():
    files,plain,recipe,names_report,component,texture,prs,_,_=compose();base=ROOT/'work/output'/PRIOR;exe=files['1ST_READ.BIN'];fonts=member((base/'WIN00.AFS').read_bytes(),0)
    old=(base/'text/D_NAMES.en.dec.bin').read_bytes();rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'));changed={r['id'] for r in component['text_changes']};unchanged=0;cases=[];steps=0
    for row in rows:
        if row['source_record_kind']=='unused_table_root_sentinel':continue
        if row['id'] not in changed:assert entry(old,row['id'])==entry(plain,row['id']);unchanged+=1
    for mode,font in [('HD',fonts[:99072]),('Native',fonts[99072:])]:
        c=setup(exe,font,b'',plain)
        for field_width in (0,2,3,4):
            for value in range(-127,128):
                steps+=call(c,0x8c03af90);steps+=call(c,0x8c03c010,value,field_width)
                start=c.read(0x8c1db4ec,4)+0x600;raw=bytearray()
                for j in range(12):
                    raw.append(c.read(start+j,1))
                    if raw[-1]==255:break
                text=decode(bytes(raw))[0];value_text=('-' if value<0 else '+')+str(abs(value))
                # The original field-width calculation reserves a sign cell.
                expected=value_text.rjust(max(len(value_text),field_width))
                assert text==expected,(value,field_width,text,expected)
                gs,n=parse_ui(exe,font,plain,bytes(raw),x=0);steps+=n;assert ''.join(g[0] for g in gs)==expected
        for key,limit in [('names.g00.107',48),('names.g00.199',192)]:
            gs,n=parse_ui(exe,font,plain,entry(plain,key),x=0);steps+=n;right=bottom=0
            for ch,x,y,small in gs:
                yy,xx=legacy_mask(font,ch,small).nonzero()
                if len(xx):right=max(right,x+(max(xx)+1)/4+1);bottom=max(bottom,y+(max(yy)+1)/4)
            assert right<=limit and bottom<=48,(key,right,bottom)
            cases.append({'mode':mode,'id':key,'ink_right':right,'ink_bottom':bottom,'limit':limit})
    return {'version':VERSION,'files':component['files'],'signed_values':2040,'signed_domain':'Every signed byte -127..127, field widths 0/2/3/4, both fonts; neutral normalized to +0; legacy -128 magnitude edge outside gameplay proof',
        'native_instructions':steps,'text_cases':cases,'other_names_byte_exact':unchanged,'room_tags':len(component['room_tags']),
        'names_native_PRS_instructions':verify(exe,files['D_NAMES.BIN'],plain,65536),
        'room_texture_native_PRS_instructions':verify(exe,prs,texture,len(texture),instruction_limit=20_000_000),
        'limits':['Native numeric generator and parser execute; graphics and live gameplay are not executed.','Room texture source geometry and all non-label pixels/members preserved; visual inspection is offline.','Unidentified sprite 66 is preserved, not guessed.','Stage 6 issue #1 remains unresolved.']}


def plan():
    files,plain,recipe,names_report,component,*_=compose();base=ROOT/'work/output'/PRIOR
    font_component=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    p,_=font_plan(compose_fn=lambda:(files['1ST_READ.BIN'],(base/'WIN00.AFS').read_bytes(),b'',{},font_component),prior=PRIOR,version=VERSION)
    disc,cue,inherited,targets,changes,names,historical,report=p;original=Disc(next(ROOT.glob('*.cue')));entries={e['path']:e for e in disc.inventory()};delta=0
    for name in ('D_NAMES.BIN','ITM00.AFS'):
        ent=entries[name]
        if name not in inherited:inherited[name]=disc.read(ent['lba'],ent['size'])
        source=inherited[name];target=files[name];targets[name]=target;orig=original.read(ent['lba'],len(source));assert len(source)==len(target)
        for off in range(0,len(source),2048):
            a,b=source[off:off+2048],target[off:off+2048]
            if a==b:continue
            lba=ent['lba']+off//2048;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba']);position=(track['index']+lba-track['start_lba'])*SECTOR
            with track['path'].open('rb') as f:f.seek(position);raw=f.read(SECTOR)
            changes.append((track['path'].name,position,substitute_payload_sector(raw,a,b)));delta+=int(b!=orig[off:off+2048])-int(a!=orig[off:off+2048])
    report.update(kind='Local signed numeric fields, compact notices and English room tags',files={n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        new_changed_sectors=len(changes),total_changed_sector_locations_from_original=report['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='numeric-room-component.json',current_native_evidence={'numeric_room':'numeric-room-native-test.json'},
        readme_component_text='Fixes original signed numeric glyphs: +0 / +10 / -10 now use Latin signs.\n'
            'Fits the VMU free-block notice and Topic Log heading in their existing frames.\n'
            'Translates 33 room-map tags, including Clovis/Arthur, from original Skies pixels.\n'
            'One unidentified tag stays unchanged. All 0.7.9 fixes retained.\n'
            'Cold-boot and use a normal memory-card save. Issue #1 is still unresolved.\n',
        proof_scope='510 native signed-number generation/parser cases, both font layout cases, original Skies mask/source geometry preservation, native names/texture PRS and full disc preservation.',
        pending=['Live signed numeric fields, notices and room-map appearance','Unidentified room tag sprite 66','Separate Stage 6 issue #1','Full-game and translation review'])
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');args=ap.parse_args()
    files,plain,recipe,names_report,component,_,_,preview,image=compose()
    if not args.write:print(json.dumps(component,indent=2));return
    OUT.mkdir(parents=True,exist_ok=True);proof=check()
    for name,raw in files.items():(OUT/name).write_bytes(raw)
    for name,value in [('numeric-room-component.json',component),('numeric-room-native-test.json',proof)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    image.save(OUT/'room-tags-English.png');preview.save(OUT/'room-tags-contact.png')
    RECIPE.write_text(json.dumps(component,indent=2)+'\n','utf-8')
    print('PASS: signed fields, compact notices, 33 room tags and native PRS.',flush=True)
    if args.disc:
        p=plan();write_plan(p,VERSION,PRIOR,files);out=ROOT/'work/output'/VERSION;(out/'text/D_NAMES.en.dec.bin').write_bytes(plain)
        for name,value in [('text/names-component-report.json',names_report),('ui-layouts.en.json',recipe),('numeric-room-component.json',component),('numeric-room-native-test.json',proof)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        image.save(out/'room-tags-English.png');preview.save(out/'room-tags-contact.png')
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        for n,raw in files.items():m['files'].setdefault(n,{}).update(target_sha256=digest(raw),size=len(raw))
        m['files']['ITM00.AFS']['source_sha256']=component['source_ITM00_sha256']
        m['numeric_room']={'native_proof':'numeric-room-native-test.json','recipe':str(RECIPE.relative_to(ROOT)).replace('\\','/')}
        m['native_proof_reuse']={'source_build':PRIOR,'scope':'The numeric sign writer is separately tested. Font kernel, banks, other executable bytes and the twelve other prior payloads remain exact.'}
        (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
        mode=json.loads((out/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(files['1ST_READ.BIN']));(out/'font-mode-details.json').write_text(json.dumps(mode,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
