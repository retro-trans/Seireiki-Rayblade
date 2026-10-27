"""Align status labels with their original square markers. Local 0.7.8."""
import argparse, copy, json, re, struct
from functools import lru_cache
from build_bitmap_font import ROOT, digest
from build_names_translation import compose as names_compose
from build_map_font_patch import member
from english_text_codec import decode
from test_ui_layouts import entry, parse_ui
from test_library_layout import fresh, run, BASE
from test_outline_font import legacy_mask
from check_native_text_components import verify
from sh4_asm import Assembler
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan
from disc_inventory import Disc, SECTOR
from package_archive_test_disc import substitute_payload_sector

VERSION, PRIOR = '0.7.8', '0.7.7'
OUT=ROOT/'work/output/status-marker-candidate'
RECIPE=ROOT/'work/translation/en/ui/status-marker-alignment.en.json'
HOOK=BASE+0x6bad0
FACTORY_POINTER=0x8b1d4
STATUS_CONTEXTS=(0xef01,0xef29)


def hook_code():
    a=Assembler(HOOK)
    for reg in (8,9,10,11):a.push(reg)
    a.emit(0x4f22);a.addi(-96,15)
    a.lit(0x8c1dbe24,1);a.load('l',1,8)
    a.lit(0x8c07d978,3);a.emit(0x430b);a.emit(0x0009);a.rr('mov',0,9)
    a.lit(BASE+STATUS_CONTEXTS[0]+1,0);a.rr('cmp/eq',0,8);a.branch('bt','adjust')
    a.lit(BASE+STATUS_CONTEXTS[1]+1,0);a.rr('cmp/eq',0,8);a.branch('bf','done')
    a.label('adjust');a.lit(0x8c1f24cd,1);a.load('b',1,0);a.rr('extu.b',0,0)
    a.imm(48,1);a.rr('cmp/hs',1,0);a.branch('bt','done')
    a.imm(92,2);a.rr('mul.l',2,0);a.unary('sts.macl',0)
    a.lit(0x8c1f0cf8+0x4c,1);a.rr('add',0,1)
    a.load('w',1,2);a.addi(2,2);a.store('w',2,1)
    # The FC coordinate parser subtracts the cached draw origin from the
    # logical tile origins. Move every linked tile too, preventing unsigned
    # -2 header coordinates after a refresh. Use the original link enumerator
    # rather than assuming the four allocated tiles are contiguous.
    a.lit(0x8c1f24cd,1);a.load('b',1,4);a.rr('extu.b',4,4)
    a.rr('mov',15,5);a.imm(48,6);a.lit(0x8c0787d0,3);a.emit(0x430b);a.emit(0x0009)
    a.imm(48,10);a.rr('mov',15,11)
    a.label('tiles');a.rr('tst',10,10);a.branch('bt','done')
    a.load('w',11,0);a.rr('extu.w',0,0);a.imm(48,1);a.rr('cmp/hs',1,0);a.branch('bt','next')
    a.imm(92,2);a.rr('mul.l',2,0);a.unary('sts.macl',0)
    a.lit(0x8c1f0cf8+0x32,1);a.rr('add',0,1);a.load('w',1,2);a.addi(2,2);a.store('w',2,1)
    a.label('next');a.addi(2,11);a.unary('dt',10);a.branch('bra','tiles');a.emit(0x0009)
    a.label('done');a.rr('mov',9,0);a.addi(96,15);a.emit(0x4f26)
    for reg in (11,10,9,8):a.pop(reg)
    a.emit(0x000b);a.emit(0x0009)
    return a.pool_and_finish()


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;source=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(source)
    code=hook_code();off=HOOK-BASE
    assert off+len(code)<=0x6bbe0 and exe[off:off+len(code)]==bytes.fromhex('0900')*(len(code)//2)
    assert struct.unpack_from('<I',exe,FACTORY_POINTER)[0]==0x8c07d978
    exe[off:off+len(code)]=code;struct.pack_into('<I',exe,FACTORY_POINTER,HOOK)
    names=(base/'text/D_NAMES.en.dec.bin').read_bytes();recipe=json.loads((base/'ui-layouts.en.json').read_text('utf-8'))
    key='names.g00.006';before=decode(entry(names,key))[0];assert before.startswith(' Skills<NL> ')
    after='<FC:81:80>Skills<FC:80:82>'+before.split('<NL>',1)[1]
    row=next(r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8')) if r['id']==key)
    recipe['rows'][key]={'en':after,'source_sha256':row['source_sha256'],'prior_en_sha256':digest(row['en'].encode()),
        'reason':'Set Skills header at x8 rather than a three-pixel variable-width space; restore original x0/y16 before ability rows.'}
    plain,packed,names_report=names_compose(overrides=recipe['rows'],version=VERSION)
    capacity=len((base/'text/D_NAMES.BIN').read_bytes());stream=len(packed);assert stream<=capacity
    packed+=bytes(capacity-stream);recipe.update(version=VERSION,previous_build=PRIOR)
    files={'1ST_READ.BIN':bytes(exe),'D_NAMES.BIN':packed}
    report={'version':VERSION,'source_build':PRIOR,'files':{n:{'sha256':digest(v),'size':len(v)} for n,v in files.items()},
        'names_decoded_sha256':digest(plain),'compressed_stream_bytes':stream,
        'heading':{'id':key,'before':before,'after':after,'horizontal_shift_logical_pixels':5,
                   'ability_entry_coordinates':'unchanged relative to the panel'},
        'panels':{'scripts':[hex(p) for p in STATUS_CONTEXTS],'text_draw_y_shift_logical_pixels':2,
                  'square_marker_coordinates':'unchanged','font_pixels':'unchanged'},
        'hook':{'address':hex(HOOK),'bytes':len(code),'VM_factory_pointer':hex(FACTORY_POINTER),
                'scope':'Only the two status panels; other contexts delegate unchanged to the original constructor'},
        'release':False,'live_validation':'pending'}
    return files,plain,recipe,names_report,report


def check():
    files,plain,recipe,names_report,component=compose();base=ROOT/'work/output'/PRIOR
    exe=files['1ST_READ.BIN'];old_exe=(base/'1ST_READ.BIN').read_bytes()
    font=member((base/'WIN00.AFS').read_bytes(),0)[:99072];old_names=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'));unchanged=0
    for row in rows:
        if row['source_record_kind']=='unused_table_root_sentinel':continue
        if row['id']=='names.g00.006':continue
        assert entry(old_names,row['id'])==entry(plain,row['id']);unchanged+=1
    contexts=[];steps=0
    # Actual constructor/template/surface selection for both affected contexts
    # and their adjacent portrait/upper-right contexts, in Native and HD modes.
    for mode in (0,1):
        for script in (0xeee6,0xef01,0xef15,0xef29,0xe70b,0xfdbf):
            before=fresh(old_exe,font);after=fresh(exe,font)
            for cpu in (before,after):
                cpu.write(0x8c07bbe0,mode,1);cpu.write(0x8c1dbe24,BASE+script+1,4)
            steps+=run(before,0x8c07d978)
            saved=after.reg[8:];steps+=run(after,HOOK);assert after.reg[8:]==saved
            assert before.reg[0]==after.reg[0] and before.pr==after.pr
            slot=after.read(0x8c1f24cd,1);assert slot==before.read(0x8c1f24cd,1)
            ctx=0x8c1f0cf8+slot*92
            a=bytes(before.read(ctx+i,1) for i in range(92));b=bytes(after.read(ctx+i,1) for i in range(92))
            expected=bytearray(a)
            if script in STATUS_CONTEXTS:
                for pos in (0x32,0x4c):struct.pack_into('<H',expected,pos,struct.unpack_from('<H',a,pos)[0]+2)
            assert b==expected,(hex(script),a.hex(),b.hex())
            assert before.read(0x8c1dbe24,4)==after.read(0x8c1dbe24,4)
            contexts.append({'script':hex(script),'mode':mode,'text_draw_y_before':struct.unpack_from('<H',a,0x4c)[0],
                'text_draw_y_after':struct.unpack_from('<H',b,0x4c)[0],'other_context_fields':'exact'})
            for linked in range(1,4):
                p=ctx+linked*92
                child_a=bytes(before.read(p+i,1) for i in range(92));child_b=bytes(after.read(p+i,1) for i in range(92));child_expected=bytearray(child_a)
                if script in STATUS_CONTEXTS:struct.pack_into('<H',child_expected,0x32,struct.unpack_from('<H',child_a,0x32)[0]+2)
                assert child_b==child_expected
    key='names.g00.006';args=[('Anti-Field',False),('Second Skill',False),('',False),('',False),('',False)]
    old,n=parse_ui(old_exe,font,old_names,entry(old_names,key),args,x=0);steps+=n
    new,n=parse_ui(exe,font,plain,entry(plain,key),args,x=0);steps+=n
    old_header=[g for g in old if g[2]==0 and g[0]!=' '];new_header=[g for g in new if g[2]==0]
    assert ''.join(g[0] for g in new_header)=='Skills'
    assert [(ch,x+5,y,s) for ch,x,y,s in old_header]==new_header
    assert [g for g in old if g[2]>0]==[g for g in new if g[2]>0]
    from test_library_layout import LibraryCPU, parse_page
    from english_text_codec import encode
    class RenderCPU(LibraryCPU):
        def execute(self,pc,delay=False):
            if pc==0x8c0344da: # Existing GPU-object validity endpoint only.
                self.reg[0]=1;return self.pr
            return super().execute(pc,delay)
    redraw=[]
    for mode in (0,1):
        for script,text,expected_x in [(0xef01,'<FC:88:80>Trust',120),(0xef29,'<FC:81:80>Skills',200)]:
            cpu=fresh(exe,font);cpu.__class__=RenderCPU
            cpu.write(0x8c07bbe0,mode,1);cpu.write(0x8c1dbe24,BASE+script+1,4);steps+=run(cpu,HOOK)
            ctx=0x8c1f0cf8
            for _ in range(2):
                glyphs,n=parse_page(cpu,encode(text));steps+=n
                assert all(y==0 for ch,x,y,s in glyphs) # No -2/65534 clipping.
                assert cpu.read(ctx+0x4a,2)+glyphs[0][1]==expected_x
                assert cpu.read(ctx+0x4c,2)==114
            cpu.write(0x8c1dbf63,2,1);cpu.write(0x8c1dbf67,0,1);cpu.write(ctx+0x48,2,2)
            cpu.reg[15]=0x8c701800;cpu.pr=0xdead0000
            steps+=run(cpu,0x8c078b0c,0x8c078c1a)
            calls=[r for r in cpu.calls if r[0]=='0x8c02fb6c']
            assert len(calls)==1 and calls[0][1][1:3]==(cpu.read(ctx+0x4a,2),114)
            redraw.append({'script':hex(script),'mode':mode,'glyph_y':0,'screen_pen_x':expected_x,
                           'text_object_position':list(calls[0][1][1:3]),'repeated_clear_and_parse':'pass'})
    # Trust is byte-exact: only its panel's draw Y changes. Original marker
    # bounds from the supplied native screenshot: x112..118 and x192..198,
    # y117..125. Skies ink shifts down two logical pixels to share center121.
    marker_checks=[]
    for text,pen_x,marker_x in [('Trust',120,112),('Skills',200,192)]:
        ys=[];xs=[];x=pen_x
        from build_font4x_patch import MEDIUM
        for ch in text:
            a=legacy_mask(font,ch,False);yy,xx=a.nonzero()
            if len(xx):xs.extend(x+xx/4);ys.extend(114+yy/4)
            x+=font[0xa0+MEDIUM.index(ch)]
        bounds=[float(min(xs)),float(min(ys)),float(max(xs)+.25),float(max(ys)+.25)]
        assert bounds[0]>marker_x+6 and abs((bounds[1]+bounds[3])/2-121)<=1
        marker_checks.append({'label':text,'marker_box_from_user_image':[marker_x,117,marker_x+6,125],
                              'new_ink_bounds_logical':bounds,'scope':'Marker bounds measured from supplied 640x480 image; glyph bounds from original masks'})
    prs=verify(exe,files['D_NAMES.BIN'],plain,65536)
    return {'version':VERSION,'files':component['files'],'unchanged_other_name_rows':unchanged,
        'context_cases':contexts,'Skills_header_x_shift':5,'Skills_ability_rows':'exact original coordinates',
        'marker_alignment':marker_checks,'native_redraw_cases':redraw,'native_context_and_parser_instructions':steps,'native_PRS_instructions':prs,
        'names_builder_validation':names_report['validation'],
        'limits':['Marker geometry measured from supplied screenshot; native constructors/parser and bounds execute, GPU/input not executed',
                  'The two full text panels move down two logical pixels; font and square art unchanged']}


def plan():
    files,plain,recipe,names_report,component=compose();base=ROOT/'work/output'/PRIOR
    font_component=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    def candidate():return files['1ST_READ.BIN'],(base/'WIN00.AFS').read_bytes(),b'',{},font_component
    p,_=font_plan(compose_fn=candidate,prior=PRIOR,version=VERSION)
    disc,cue,inherited,targets,changes,names,historical,report=p
    source=inherited['D_NAMES.BIN'];target=files['D_NAMES.BIN'];targets['D_NAMES.BIN']=target
    ent=next(r for r in disc.inventory() if r['path']=='D_NAMES.BIN');orig=Disc(next(ROOT.glob('*.cue'))).read(ent['lba'],len(source));delta=0
    for off in range(0,len(source),2048):
        a,b=source[off:off+2048],target[off:off+2048]
        if a==b:continue
        lba=ent['lba']+off//2048;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
        position=(track['index']+lba-track['start_lba'])*SECTOR
        with track['path'].open('rb') as f:f.seek(position);raw=f.read(SECTOR)
        changes.append((track['path'].name,position,substitute_payload_sector(raw,a,b)))
        delta+=int(b!=orig[off:off+2048])-int(a!=orig[off:off+2048])
    report.update(kind='Local Trust/Skills square-marker alignment',files={n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        new_changed_sectors=len(changes),total_changed_sector_locations_from_original=report['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='status-marker-component.json',
        readme_component_text='Aligned Trust and Skills vertically with the original square markers.\n'
            'Skills now starts to the right of its marker; its ability rows keep their original horizontal coordinates.\n'
            'Only the two lower status text panels move down two logical pixels. Font and marker art are unchanged.\n'
            'All 0.7.7 compact weapon/movie names and 0.7.6 choice/map fixes are retained.\n'
            'Cold-boot and load a normal in-game save; emulator states retain old code/text.\n',
        current_native_evidence={'status_marker':'status-marker-native-test.json'},
        proof_scope='Actual status/adjacent native context constructors in Native/HD, Skills parser/control coordinates, screenshot-derived icon versus glyph bounds and PRS. Full disc preservation.',
        pending=['Live status-marker alignment in Native/HD on Flycast and Dreamcast','Full-game/translation review'])
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    files,plain,recipe,names_report,component=compose()
    if not a.write:print(json.dumps(component,indent=2));return
    OUT.mkdir(parents=True,exist_ok=True);proof=check()
    for name,raw in files.items():(OUT/name).write_bytes(raw)
    for name,value in [('component-report.json',component),('native-test.json',proof)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    RECIPE.write_text(json.dumps({'version':VERSION,'heading':component['heading'],'panels':component['panels']},indent=2)+'\n','utf-8')
    print('PASS: 12 Native/HD context cases; Skills indentation/entry coordinates; marker alignment and native PRS.',flush=True)
    if a.disc:
        p=plan();write_plan(p,VERSION,PRIOR,files);out=ROOT/'work/output'/VERSION
        (out/'text/D_NAMES.en.dec.bin').write_bytes(plain)
        for name,value in [('text/names-component-report.json',names_report),('ui-layouts.en.json',recipe),('status-marker-component.json',component),('status-marker-native-test.json',proof)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'));manifest.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        for name,raw in files.items():manifest['files'][name]['target_sha256']=digest(raw)
        manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Current status context/parser proof is separate. Historical records keep actual tested identities; font, other 12 payloads and boot area exact.'}
        manifest['status_marker_alignment']={'recipe':str(RECIPE.relative_to(ROOT)).replace('\\','/'),'proof':'status-marker-native-test.json'}
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
