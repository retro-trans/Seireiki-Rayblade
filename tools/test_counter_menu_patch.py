"""Native counter popup/frame/help and full glyph rendering checks. Dry first."""
import argparse,json,re,struct
from collections import Counter
from build_counter_menu_patch import ROOT,OUT,VERSION,PRIOR,compose,digest
from build_antialias_font import font_bytes
from build_font4x_patch import MEDIUM
from test_library_layout import fresh,run,BASE,parse_page
from test_library_headers import setup,call,HeaderCPU
from test_font4x_patch import HDCPU
from test_outline_font import legacy_mask,expected_pixels
from test_ui_layouts import entry,parse_ui
from test_battle_menu_patch import specimen
from check_native_text_components import verify


class RasterCPU(HeaderCPU):
    def execute(self,pc,delay=False):
        if pc==0x8c07b28e:
            small=bool(self.read(0x8c1f36ba,1)&64)
            assert not small
            ch=MEDIUM[self.reg[4]];x=self.read(0x8c1f36b6,2);y=self.read(0x8c1f36b8,2)
            self.glyphs.append((ch,x,y,False))
            tex=self.read(0x8c1f36ac,4)-32;w=self.read(tex+28,2);h=self.read(tex+30,2)
            sx=1<<self.read(tex+12,1);sy=1<<self.read(tex+13,1);flags=self.read(0x8c1f36ba,1)
            if tex not in self.reference:
                block,at=self.area(tex,32+w*h*2);self.reference[tex]=bytearray(block[at:at+32+w*h*2])
            out=self.reference[tex];coverage=legacy_mask(self.font,ch,False)[:,:32]
            color=self.read(0x8c0980aa+(flags&14)*2,2)
            rgb=((color>>11)&15)<<8|((color>>6)&15)<<4|(color>>1)&15
            for yy in range(16*sy):
                py=y*sy+yy
                if py>=h:continue
                for xx in range(8*sx):
                    px=x*sx+xx
                    if px>=w:continue
                    alpha=int(coverage[yy*4//sy,xx*4//sx])//17
                    if flags&128 and px+sx<w:struct.pack_into('<H',out,32+(py*w+px+sx)*2,alpha<<12)
                    if alpha:struct.pack_into('<H',out,32+(py*w+px)*2,(alpha<<12)|rgb)
            self.raster_states.append({'character':ch,'scale':[sx,sy],'texture':hex(tex),'flags':flags})
            return HDCPU.execute(self,pc,delay)
        return super().execute(pc,delay)


def check():
    files,names,recipe,_,component=compose();exe=files['1ST_READ.BIN'];base=ROOT/'work/output'/PRIOR
    for name,raw in files.items():assert (OUT/name).read_bytes()==raw
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1];paper=(base/'text/D_PAPER.en.dec.bin').read_bytes()
    old_names=(base/'text/D_NAMES.en.dec.bin').read_bytes();unchanged=0
    changed={r['id'] for r in component['help_rows']}
    for row in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8')):
        if row['id'] in changed:continue
        assert entry(names,row['id'])==entry(old_names,row['id']),row['id'];unchanged+=1
    metrics=json.loads((base/'skies-font-component-report.json').read_text('utf-8'))['metrics']
    bounds={r['character']:r['packed_mask_bounds'] for r in metrics['medium']}
    steps=Counter();geometry=[];ui=[];previews={}
    # Actual VM text-context constructors and matching frame constructors.
    configs=[('forecast',0xe70b,0xe712,[104,144,128,128],[96,136,128,80],112),
        ('policies',0xfdbf,0xfdc6,[104,64,128,128],[96,56,128,96],112),
        ('help',0xfddf,0xfde6,[32,160,256,128],[24,152,272,80],64),
        ('objectives',0xfeb0,0xfeb7,[112,32,256,32],[104,24,112,32],64)]
    contexts={}
    for label,script,frame_script,expected,rect,tilewidth in configs:
        c=fresh(exe,font);c.write(0x8c1dbe24,BASE+script+1,4);steps['context']+=run(c,0x8c07d978)
        slot=c.read(0x8c1f24cd,1);at=0x8c1f0cf8+slot*92
        actual=[c.read(at+i,2) for i in (0x30,0x32,0x4e,0x50)];assert actual==expected,(label,actual,expected)
        assert c.read(at+10,1)==tilewidth
        ptr=c.read(at+0x44,4);physical=[c.read(ptr+i,2) for i in (28,30)]
        assert max(physical)<=1024
        f=fresh(exe,font);f.write(0x8c1dbe24,BASE+frame_script+1,4)
        steps['frame']+=run(f,0x8c07d7c8,0x8c076588)
        visual=0x8c1f1e38+208*exe[frame_script+2];actual_rect=[f.read(visual+i,2) for i in (24,26,28,30)]
        assert actual_rect==rect,(label,actual_rect,rect)
        assert 0<=rect[0] and rect[0]+rect[2]<=320 and 0<=rect[1] and rect[1]+rect[3]<=240
        geometry.append({'label':label,'text_context':actual,'frame':rect,'physical_surface':physical,
            'visible_tile_width':tilewidth,'surface_exponents':[c.read(ptr+12,1),c.read(ptr+13,1)]})
        contexts[label]=c
    assert geometry[1]['frame'][1]+geometry[1]['frame'][3]<=geometry[2]['frame'][1]
    # Native measured parser output, including original words/control operands.
    for index in range(24,32):
        key=f'names.g01.{index:03d}';gs,n=parse_ui(exe,font,names,entry(names,key),x=0);steps['UI']+=n
        right=max(x+bounds[ch][2]/4+1 for ch,x,y,s in gs if bounds[ch]);bottom=max(y+16 for _,x,y,s in gs)
        assert right<=256 and bottom<=64 and all(not g[3] for g in gs),(key,right,bottom)
        old=next(r for r in component['help_rows'] if r['id']==key)['before']
        assert ''.join(g[0] for g in gs).replace(' ','')==old.replace('<NL>','').replace(' ','')
        # Execute the complete native context selection/render parser for each help.
        rendered,n=parse_page(contexts['help'],entry(names,key));steps['constructed_help_parser']+=n
        assert rendered==gs,(key,rendered[:3],gs[:3])
        ui.append({'id':key,'ink_right':right,'bottom':bottom,'words_and_font_preserved':True})
        if index in (29,30):previews['help-'+str(index)]=gs
    for key,args,limit,label in [('names.g00.124',[('',False)],112,'forecast'),
            ('names.g00.174',[],112,'policies'),('names.g00.171',[],96,'objectives')]:
        gs,n=parse_ui(exe,font,names,entry(names,key),args,x=0);steps['UI']+=n
        right=max(x+bounds[ch][2]/4+1 for ch,x,y,s in gs if bounds[ch]);assert right<=limit
        assert all(not g[3] for g in gs)
        ui.append({'id':key,'ink_right':right,'limit':limit,'same_medium_font_all_rows':True});previews[label]=gs
    # Run the actual font routine for the two reported rows and the remaining
    # policy choice text; verify exact masks, advance, clipped edges and ABI.
    chars=sorted(set('CounterattackSelect WeaponEvadeDefendManualAlways Be AggressivePlay It Safe'))
    for ch in chars:
        c=HDCPU(exe,font,MEDIUM.index(ch),128,128,128,2,2)
        c.write(0x8c1f36b6,12,2);c.write(0x8c1f36b8,4,2)
        expected=expected_pixels(c,legacy_mask(font,ch,False)[:,:32],128,12,4)
        steps['raster']+=c.run_until(limit=300000);assert c.regions[3][1]==expected
    # Entire actual forecast choices: constructor -> real common queue/name
    # lookup -> parser -> native glyph routine -> allocated pixel buffer.
    c=setup(exe,font,paper,names);c.__class__=RasterCPU;c.reference={};c.raster_states=[]
    c.write(0x8c1dbe24,BASE+0xe70c,4);steps['full_forecast']+=call(c,0x8c07d978)
    steps['full_forecast']+=call(c,0x8c03af90)+call(c,0x8c03b030,0)
    c.glyphs=[];c.reg[15]=0x8c701800;c.pr=0xdead0000;c.reg[4:6]=[6,124];c.pc=0x8c076afc
    for count in range(8000000):
        if c.pc==0x8c076bac:break
        c.pc=c.execute(c.pc)
    else:raise AssertionError('Full forecast native instruction limit')
    steps['full_forecast']+=count
    assert ''.join(g[0] for g in c.glyphs)=='CounterattackSelect WeaponEvadeDefend'
    assert all(s['scale']==[4,4] and not s['flags']&64 for s in c.raster_states)
    for tex,expected in c.reference.items():
        block,at=c.area(tex,len(expected));assert block[at:at+len(expected)]==expected
    full={'glyphs':len(c.glyphs),'all_choices_same_Skies_bank':True,'all_choice_scales':[4,4],
        'native_composed_pixels':'exact independent original Skies masks, including alpha/shadow',
        'state_sequence':c.raster_states}
    steps['PRS']=verify(exe,files['D_NAMES.BIN'],names,65536)
    return {'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),
        'font_sha256':digest(font),'font_changed':False,'names_packed_sha256':digest(files['D_NAMES.BIN']),
        'names_decoded_sha256':digest(names),'geometry_cases':geometry,'UI_cases':ui,'native_raster_cases':len(chars),
        'unchanged_other_name_rows':unchanged,'native_composed_forecast':full,'native_instructions':dict(steps),'limits':['Graphics allocation/I/O are bounded fixtures; constructors/queue/parser/raster execute; forecast pixels compared end to end.',
            'Live GPU appearance, cursor/highlight placement, input and simultaneous menu allocation remain pending.']},previews,font


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true');a=ap.parse_args()
    assert not a.write_report or a.verify
    print('Plan: four real frame/context constructions, eight help rows, choice/title bounds, actual Skies glyph rasters and names PRS.',flush=True)
    if not a.verify:print('DRY RUN: no native execution/report.');return
    report,previews,font=check()
    if a.write_report:
        (OUT/'native-test.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
        for name,gs in previews.items():specimen(OUT/(name+'-preview.png'),gs,font)
    print('PASS:',len(report['geometry_cases']),'geometry cases;',len(report['UI_cases']),'UI cases;',report['native_raster_cases'],'native rasters.',flush=True)


if __name__=='__main__':main()
