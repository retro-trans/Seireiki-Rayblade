"""Native widened action frame/text contexts, compact UI and real status lookup."""
import argparse,json,struct,re
from collections import Counter
from build_battle_menu_patch import ROOT,OUT,VERSION,PRIOR,compose,digest,EDITS
from build_antialias_font import font_bytes
from test_library_layout import fresh,run,BASE
from test_library_headers import setup,call
from test_ui_layouts import parse_ui,entry
from check_native_text_components import verify
from build_font4x_patch import MEDIUM
from test_font4x_patch import HDCPU
from test_outline_font import legacy_mask,expected_pixels
from PIL import Image,ImageDraw


def specimen(path,gs,font):
    width=max(1024,((int(max((x+16 for _,x,_,_ in gs),default=0)*4)+143)//128)*128)
    im=Image.new('RGBA',(width,520),'#24211f');draw=ImageDraw.Draw(im)
    draw.text((12,8),'Offline native-parser layout preview; not an in-game screenshot',fill='white')
    for ch,x,y,small in gs:
        mask=Image.fromarray(legacy_mask(font,ch,small));ink=Image.new('RGBA',mask.size,'white');ink.putalpha(mask)
        im.alpha_composite(ink,(x*4,24+y*4))
    im.convert('RGB').save(path)


def check():
    files,names,recipe,names_report,component=compose();exe=files['1ST_READ.BIN']
    base=ROOT/'work/output'/PRIOR
    for name,raw in files.items():assert (OUT/name).read_bytes()==raw
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1]
    metrics=json.loads((base/'skies-font-component-report.json').read_text('utf-8'))['metrics']
    bounds={b:{r['character']:r['packed_mask_bounds'] for r in rows} for b,rows in metrics.items()}
    steps=Counter();contexts=[];ui=[];previews={}
    # All nine legal action labels fit the new 56-pixel visible text tiles.
    for i in range(9,18):
        gs,n=parse_ui(exe,font,names,entry(names,f'names.g00.{i:03d}'),x=0);steps['UI']+=n
        right=max(x+bounds['medium'][ch][2]/4+1 for ch,x,y,s in gs if bounds['medium'][ch])
        assert right<=56,(i,right)
        ui.append({'id':f'names.g00.{i:03d}','ink_right':right,'limit':56})
    # Native VM constructors consume the real altered scripts and template.
    variables=struct.unpack_from('<I',exe,0x6d9d4)[0]
    for count in range(1,9):
        c=fresh(exe,font);c.write(variables+1,count*2+1,1);c.write(variables+2,10,1);c.write(variables+3,11,1)
        c.write(0x8c1dbe24,BASE+0xf01c,4);steps['context']+=run(c,0x8c07d978)
        slot=c.read(0x8c1f24cd,1);at=0x8c1f0cf8+slot*92
        assert [c.read(at+i,2) for i in (0x30,0x32,0x4e,0x50)]==[240,88,64,128]
        assert c.read(at+10,1)==56
        assert c.read(0x8cb00000+28,2)<=1024 and c.read(0x8cb00000+30,2)<=1024
        # A separate CPU reaches actual visual-frame setup before its graphics allocation.
        frame=fresh(exe,font);frame.write(variables+1,count*2+1,1);frame.write(variables+2,10,1)
        frame.write(0x8c1dbe24,BASE+0xf023,4)
        steps['frame']+=run(frame,0x8c07d7c8,0x8c076588)
        visual=0x8c1f1e38+208
        rect=[frame.read(visual+i,2) for i in (24,26,28,30)]
        assert rect==[232,80,72,(count*2+1)*8],rect
        assert rect[0]+rect[2]==304
        contexts.append({'actions':count,'text_origin':[240,88],'logical_surface':[64,128],
                         'visible_tile_width':56,'frame':rect,'right_screen_margin':16})
    def check_ui(key,args=(),limit=None):
        gs,n=parse_ui(exe,font,names,entry(names,key),args,x=8);steps['UI']+=n
        right=max((x+bounds['small' if small else 'medium'][ch][2]/4+1 for ch,x,y,small in gs if bounds['small' if small else 'medium'][ch]),default=0)
        if limit is not None:assert right<=limit,(key,right,limit)
        ui.append({'id':key,'glyphs':len(gs),'ink_right':right,'limit':limit});return gs
    gs=check_ui('names.g00.004',[('99',False)]*5+[('???? ??',False)]*3+[('',False)])
    assert 'Trust' in ''.join(g[0] for g in gs) and 'Commands' not in ''.join(g[0] for g in gs)
    previews['pilot-status']=gs
    for terrain in ('Land','Air','Water','Space'):
        gs=check_ui('names.g00.005',[('M',False),(terrain,False),('99',False),('999',False)],limit=88)
        previews['unit-status']=gs
    gs=check_ui('names.g00.006',[('',False)]*5,limit=88);previews['skills']=gs
    for values in [('--','--','---','50'),('200','200','999','999'),('-99','200','999','999')]:
        gs=check_ui('names.g00.097',[(v,False) for v in values],limit=128);previews['weapon-cost']=gs
    args=[('',False)]
    for i in range(4):args.extend([('',False),('Mighty Sword Zeulear',False),('999',False),('2~4',False),('+99',False)])
    gs=check_ui('names.g00.096',args,limit=280);previews['weapons']=gs
    for row in component['aliases']:
        before=re.findall(r'<[^>]+>',row['before']);after=re.findall(r'<[^>]+>',row['after'])
        if row['id']=='names.g00.005':before=[s.replace('<FC:88:82>','<FC:87:82>') for s in before]
        assert before==after
    # Real common-parameter queue, actual nested name lookup and actual native
    # text context demonstrate that label and value share one medium font bank.
    status=[];paper=(base/'text/D_PAPER.en.dec.bin').read_bytes()
    for state,index in [('On',251),('Off',252)]:
        c=setup(exe,font,paper,names);c.write(0x8c1dbe24,BASE+0xe6c6,4)
        steps['status_native']+=call(c,0x8c07d978)
        steps['status_native']+=call(c,0x8c03af90)+call(c,0x8c03b030,index)
        assert c.read(0x8c1db4e4,2)==2;c.glyphs=[]
        steps['status_native']+=call(c,0x8c076afc,5,166,stop=0x8c076bac)
        assert ''.join(g[0] for g in c.glyphs)=='Cut-In '+state
        assert all(not g[3] for g in c.glyphs) and c.read(0x8c1db4e4,2)==0
        status.append({'value':state,'glyphs':c.glyphs,'same_medium_Skies_bank':True})
        previews['cut-in-'+state.lower()]=c.glyphs
    # Exact source masks and native raster ABI for the affected letter forms.
    for ch in ('C','u','t','I','n','O','N','f'):
        c=HDCPU(exe,font,MEDIUM.index(ch),128,256,32,2,2)
        c.write(0x8c1f36b6,12,2);c.write(0x8c1f36b8,4,2)
        expected=expected_pixels(c,legacy_mask(font,ch,False)[:,:32],128,12,4)
        steps['raster']+=c.run_until(limit=300000);assert c.regions[3][1]==expected
    steps['names_PRS']=verify(exe,files['D_NAMES.BIN'],names,65536)
    return {'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),'font_sha256':digest(font),
        'names_packed_sha256':digest(files['D_NAMES.BIN']),'names_decoded_sha256':digest(names),
        'menu_geometry_cases':contexts,'UI_cases':ui,'native_status_cases':status,'native_raster_cases':8,
        'native_instructions':dict(steps),'font_changed':False,'executable_instruction_changes':0,
        'translation_check':component['translation_check'],
        'limits':['VM/frame geometry stops before decorative sprite/GPU allocation; input variable values are fixtures',
                  'UI parameter cases use bounded values; status cases execute real common queue and nested names',
                  'Fresh live menu cursor/highlight appearance, interaction and reading review remain pending']},previews,font


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args();assert not args.write_report or args.verify
    print('Plan: all action labels and 1..8-action frames; affected native UI, actual On/Off queue/lookups, eight native glyphs and PRS.',flush=True)
    if not args.verify:print('DRY RUN: no native execution or report.');return
    proof,previews,font=check()
    if args.write_report:
        (OUT/'native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
        for name,gs in previews.items():specimen(OUT/(name+'-preview.png'),gs,font)
    print('PASS:',len(proof['UI_cases']),'UI cases, eight native menu/frame constructors, both status states and font/PRS checks.',flush=True)


if __name__=='__main__':main()
