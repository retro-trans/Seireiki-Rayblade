"""Native library constructor, filtering, rendering-layout and scrolling checks.

Native text contexts, row selection, parser and scroll controller execute.
Glyph rasterization is represented by independently checked advances. Graphics
submission/clear endpoints and allocation/memset are bounded fixtures. Frame
geometry is checked before its FPU rendering phase; live GPU output is separate.
"""
import argparse,itertools,json,struct
from collections import Counter
from build_library_layout_patch import ROOT,VERSION,PRIOR,digest
from prepare_library_layouts import DEST,PEN,prepare
from build_antialias_font import font_bytes
from build_font4x_patch import MEDIUM
from build_library_translation import EnglishSpanDecoder
from extract_library import sections
from rayblade_text import relative_target
from english_text_codec import encode,decode
from test_library_patch import filtered_page,reference_window
from test_font4x_patch import HDCPU
from check_native_text_components import verify
from test_ui_layouts import specimen

BASE=0x8c010000
STOP=0xdead0000
SOURCE=0x8c500000


class LibraryCPU(HDCPU):
    def execute(self,pc,delay=False):
        if pc in (0x8c0316c0,0x8c02fb6c,0x8c0312c4,0x8c078cd0,0x8c034970,0x8c030108,0x8c0320aa):
            self.calls.append((hex(pc),tuple(self.reg[4:8])));self.reg[0]=7;return self.pr
        if pc==0x8c07b28e:
            index=self.reg[4];assert not self.read(0x8c1f36ba,1)&64
            assert 0<=index<len(MEDIUM)
            self.glyphs.append((MEDIUM[index],self.read(0x8c1f36b6,2),self.read(0x8c1f36b8,2),False))
            self.write(0x8c1f36b6,self.read(0x8c1f36b6,2)+self.font[0xa0+index],2)
            return self.pr
        return super().execute(pc,delay)


def run(cpu,start,stop=STOP):
    cpu.pc=start
    for n in range(600000):
        if cpu.pc==stop:return n
        try:cpu.pc=cpu.execute(cpu.pc)
        except Exception as e:raise RuntimeError('Library native phase at '+hex(cpu.pc)) from e
    raise ValueError('Library native instruction limit at '+hex(cpu.pc))


def fresh(exe,font):
    cpu=LibraryCPU(exe,font)
    cpu.regions=[(BASE,bytearray(exe)),(0x8c140000,bytearray(0xc0000)),(0x8c400000,bytearray(0x2000)),(SOURCE,bytearray(8192)),(0x8c600000,bytearray(font)),(0x8c700000,bytearray(0x2000))]
    cpu.reg[15]=0x8c701800;cpu.pr=STOP;cpu.glyphs=[];cpu.font=font
    cpu.write(0x8c1f24e4,48,1);cpu.write(0x8c1f36a4,0x8c600000,4)
    return cpu


def make_viewer(exe,font,height):
    cpu=fresh(exe,font);script=0xf634 if height==6 else 0xf7ae
    assert exe[script:script+7]==bytes([0x8a,0x22,5,0,5,12 if height==6 else 10,0x26 if height==6 else 0x27])
    cpu.write(0x8c1dbe24,BASE+script+1,4);saved=cpu.reg[8:];steps=run(cpu,0x8c07d978)
    assert cpu.reg[0]==0x6006 and cpu.reg[8:]==saved
    slot=cpu.read(0x8c1f24cd,1);assert slot==0
    ctx=0x8c1f0cf8
    assert cpu.read(ctx+0x30,2)==40 and cpu.read(ctx+0x32,2)==(96 if height==6 else 80)
    assert cpu.read(ctx+0x4e,2)==256 and cpu.read(ctx+0x50,2)==128
    assert cpu.read(ctx+0x52,2)==1 and cpu.read(ctx+0x54,2)==height
    for row in range(height):
        for col in range(4):
            at=ctx+row*92+col*12
            assert cpu.read(at+10,1)==64 and cpu.read(at+11,1)==16
        assert cpu.read(ctx+row*92+0x32,2)==(96 if height==6 else 80)+row*16
    # The actual shared visual-frame setup is executed up to allocation of
    # decorative sprites; later FPU rendering is outside this proof.
    frame=fresh(exe,font);frame_script=0xf63b if height==6 else 0xf7b5
    assert exe[frame_script:frame_script+8]==bytes.fromhex('8a20040004042015')
    frame.write(0x8c1dbe24,BASE+frame_script+1,4)
    steps+=run(frame,0x8c07d7c8,0x8c076588)
    visual=0x8c1f1e38+4*208
    assert [frame.read(visual+i,2) for i in (24,26,28,30)]==[32,32,256,168]
    # Right border x = frame x + width - 8, left origin = frame x + 8.
    assert 32+256-8-40==240
    return cpu,{'height':height,'script_offset':hex(script),'context_slot':slot,'text_origin':[40,96 if height==6 else 80],'logical_surface':[256,128],'physical_surface':[cpu.read(0x8cb00000+28,2),cpu.read(0x8cb00000+30,2)],'visible_lines':height,'line_step':16,'frame':[32,32,256,168],'ink_pixels':240,'pen_pixels':PEN,'native_instructions':steps}


def parse_page(cpu,payload):
    # Surface/template/context links are real; only the glyph raster and GPU
    # endpoints are fixtures. Reuse the allocated viewer with a fresh frame.
    cpu.reg[15]=0x8c701800;cpu.pr=STOP;cpu.glyphs=[]
    cpu.reg[4]=cpu.read(0x8c1f24cd,1);steps=run(cpu,0x8c078a30)
    cpu.pr=STOP
    block,at=cpu.area(SOURCE,len(payload));block[at:at+len(payload)]=payload
    cpu.reg[4:8]=[cpu.read(0x8c1f24cd,1),128,0,0];cpu.write(cpu.reg[15],SOURCE,4)
    saved=cpu.reg[8:];steps+=run(cpu,0x8c07a854)
    assert cpu.reg[0]==SOURCE+len(payload) and cpu.reg[8:]==saved
    return list(cpu.glyphs),steps


def expected_glyphs(payload,font):
    text,end=decode(payload);assert end==255
    out=[];y=0
    for line in text.split('<NL>'):
        x=0
        for ch in line:out.append((ch,x,y,False));x+=font[0xa0+MEDIUM.index(ch)]
        y+=16
    return out


def main():
    global VERSION,PRIOR
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--version',default=VERSION,choices=['0.1.18','0.1.19','0.1.21']);ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    if VERSION=='0.1.19':PRIOR='0.1.18'
    elif VERSION=='0.1.21':PRIOR='0.1.20'
    print('Plan: native viewer construction, PRS decode, every unlock outcome/scroll window, complete visible-profile parser coverage and real up/down controller witnesses.',flush=True)
    if not args.verify:print('DRY RUN: no native execution or report written');return
    out=ROOT/'work/output'/VERSION;base=ROOT/'work/output'/PRIOR
    exe=(out/'1ST_READ.BIN').read_bytes()
    if VERSION=='0.1.19':
        from build_library_header_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN']
    elif VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN']
    else:assert exe==(base/'1ST_READ.BIN').read_bytes()
    _,font=font_bytes((out/'WIN00.AFS').read_bytes());_,oldfont=font_bytes((base/'WIN00.AFS').read_bytes());assert font==oldfont
    plain=(out/'text/D_PAPER.en.dec.bin').read_bytes();packed=(out/'text/D_PAPER.BIN').read_bytes()
    prs=verify(exe,packed,plain,0x20000-0x210)
    recipe=json.loads(DEST.read_text('utf-8'));assert recipe==prepare()
    source=json.loads((ROOT/'work/source/library/entries.json').read_text('utf-8'));drafts={r['id']:r for r in json.loads((ROOT/'work/translation/en/library/library.json').read_text('utf-8'))}
    profiles=json.loads((out/'text/library-component-report.json').read_text('utf-8'))['profiles'];entries={r['id']:r for r in source}
    viewers={};geometry=[]
    for height in (6,7):viewers[height],record=make_viewer(exe,font,height);geometry.append(record)
    counts=Counter();steps=Counter();maximum=0;worst=None;page_max=0;page_worst=None;parser_lines=0;widest=0;previews={};scroll_choices={}
    masks=json.loads((out/'antialias-font-report.json').read_text('utf-8'))['metrics']['medium']['glyphs'];bounds={g['character']:g['packed_mask_bounds'] for g in masks}
    for number,profile in enumerate(profiles):
        e=entries[profile['id']];header=len(bytes.fromhex(e['header_hex']));start=profile['new_offset']+header;payload=plain[start:profile['new_offset']+profile['bytes']]
        actual,_=sections(EnglishSpanDecoder(),plain,start)
        translated=[]
        for n,s in enumerate(e['sections']):
            key=e['id']+f'.s{n:02d}';prior='<NL>'.join(drafts[key+f'.l{k:02d}']['en'] for k in range(len(s['text'].split('<NL>'))));text=recipe['sections'].get(key,{}).get('en',prior)
            assert prior.replace('<NL>',' ').split()==text.replace('<NL>',' ').split()
            translated.append((text,s['conditions']))
        assert [(s['text'],s['conditions']) for s in actual]==translated
        gates=sorted({g for s in e['sections'] for g in s['conditions']});assert all(g>>8==0x35 for g in gates)
        all_text=b''
        for values in itertools.product([False,True],repeat=len(gates)):
            enabled={g for g,v in zip(gates,values) if v}
            full=b''.join(encode(text)[:-1] for text,cond in translated if all(g in enabled for g in cond))
            windows=[(0,255)]
            if all(values):
                all_text=full;windows += [(skip,h) for h in (6,7) for skip in range(full.count(b'\xfd')+2)]
            for skip,height in windows:
                expected,code=reference_window(full,skip,height);actual,ret,native=filtered_page(exe,payload,enabled,skip,height)
                assert (actual,ret)==(expected,code),(e['id'],values,skip,height)
                counts['filter_cases']+=1;steps['filter']+=native
                if len(actual)>maximum:maximum=len(actual);worst={'profile':e['id'],'skip':skip,'height':height}
                if height in (6,7) and len(actual)>page_max:page_max=len(actual);page_worst={'profile':e['id'],'skip':skip,'height':height}
            counts['unlock_outcomes']+=1
        if not all_text:continue
        # Parse both real viewer layouts in non-overlapping pages. Every
        # visible English line appears, including every unlocked section.
        line_count=all_text.count(b'\xfd')+1
        for height,cpu in viewers.items():
            for skip in range(0,line_count,height):
                expected,_=reference_window(all_text,skip,height);glyphs,native=parse_page(cpu,expected);steps['parser']+=native;counts['parser_pages']+=1
                assert glyphs==expected_glyphs(expected,font)
                assert all(y<height*16 for ch,x,y,_ in glyphs)
                for ch,x,y,_ in glyphs:
                    assert x+font[0xa0+MEDIUM.index(ch)]<=PEN
                    b=bounds[ch]
                    if b:assert x+b[2]/4+1<=240 and y+b[3]/4+1<=height*16
                parser_lines+=len({g[2] for g in glyphs})
                width=max((x+font[0xa0+MEDIUM.index(ch)] for ch,x,y,_ in glyphs),default=0)
                widest=max(widest,width)
                if height not in previews or width>=previews[height][0]:previews[height]=(width,glyphs,e['id'],skip)
        kind=e['kind'];old=scroll_choices.get(kind)
        if old is None or len(all_text)>len(old[2]):scroll_choices[kind]=(e,payload,all_text,gates)
        if (number+1)%50==0:print('Profiles',number+1,'filter cases',counts['filter_cases'],'native parser pages',counts['parser_pages'],flush=True)
    # Execute the original up/down controller with its native filter and text
    # parser on the longest character and mech profiles, both directions.
    scroll=[]
    for kind,(e,payload,full,gates) in scroll_choices.items():
        height=6 if kind=='character' else 7;cpu=viewers[height];cpu.reg[15]=0x8c701800;cpu.pr=STOP
        block,at=cpu.area(SOURCE,len(payload));block[at:at+len(payload)]=payload
        cpu.write(0x8c1f0cf4,0x8c400000,4);cpu.write(0x8c400004,SOURCE,4);cpu.write(0x8c169bac,0x8c401000,4)
        for flag in gates:
            bit=(flag&0x3ff)+0x400;addr=0x8c1df52c+bit//8;cpu.write(addr,cpu.read(addr,1)|(1<<(7-bit%8)),1)
        last=max(0,full.count(b'\xfd')+1-height);skip=0;cases=0
        for button,target in [(0x10,0)]+[(0x20,i) for i in range(1,last+1)]+[(0x20,last)]+[(0x10,i) for i in range(last-1,-1,-1)]+[(0x10,0)]:
            cpu.write(0x8c400002,skip,2);_,more=reference_window(full,skip,height);cpu.write(0x8c17fba4,more,4);cpu.write(0x8c1dbe74,1,4);cpu.write(0x8c401010,button,4)
            cpu.reg[15]=0x8c701800;cpu.pr=STOP;cpu.glyphs=[];saved=cpu.reg[8:]
            steps['scroll']+=run(cpu,0x8c065b28 if height==6 else 0x8c065d90)
            assert cpu.reg[8:]==saved and cpu.read(0x8c400002,2)==target
            if target!=skip:assert cpu.glyphs==expected_glyphs(reference_window(full,target,height)[0],font)
            skip=target;cases+=1
        scroll.append({'kind':kind,'profile':e['id'],'height':height,'last_skip':last,'native_button_cases':cases,'bounds_and_both_directions':'pass'})
    proof={'version':VERSION,'library_component_sha256':digest(plain),'filter_function_sha256':digest(exe[0x6bf00:0x6c32a]),'executable_sha256':digest(exe),'font_sha256':digest(font),'physical_records':len(profiles),'native_filter_cases':counts['filter_cases'],'native_filter_instructions':steps['filter'],'all_unlock_combinations':'pass','scroll_windows_six_and_seven_lines':'pass','maximum_output_bytes_including_full_profile_test':maximum,'maximum_case':worst,'maximum_six_or_seven_line_page_bytes':page_max,'maximum_page_case':page_worst,'output_capacity':512,'guards':'unchanged','viewer_stack_frames':'unchanged','remaining':'Live appearance, navigation and long-session memory unverified'}
    assert parser_lines==2*recipe['nonempty_line_count']
    layout={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'library_sha256':digest(plain),'geometry':geometry,'counts':dict(counts),'native_instructions':dict(steps),'PRS_instructions':prs,'native_parser_line_occurrences':parser_lines,'maximum_pen_pixels':widest,'native_scroll_witnesses':scroll,'preservation':f"Only word separators change: {recipe['inserted_breaks']} spaces become NL and {recipe['joined_breaks']} soft wraps become spaces; all words, paragraph/unlock boundaries, metadata, condition controls and decoded size are preserved",'limits':['Frame geometry stops before decorative/FPU rendering; graphics submission/callback endpoints are bounded fixtures','Glyph drawing uses independently verified advances; actual context construction/selection, clear-state handling, parser/filter/scroll instructions execute','No live GPU appearance, full navigation or long-session memory claim']}
    print(json.dumps(proof,indent=2));print(json.dumps(layout,indent=2))
    if args.write_report:
        for name,value in [('library-native-test.json',proof),('library-layout-native-test.json',layout)]:(out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        for height,(_,gs,identity,skip) in previews.items():specimen(out/f'library-{height}-line-preview.png',gs,font)
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m['library_layout'].update(native_validation='pass; all native filter windows, full visible-profile parser coverage and bidirectional scroll witnesses',proof_sha256=digest((out/'library-layout-native-test.json').read_bytes()));m['library']['pending']=['Live library navigation, appearance and long-session memory'];(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
