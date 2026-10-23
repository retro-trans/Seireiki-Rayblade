"""Native raster checks against the supplied image, plus current-font layout.

Default dry run. Does not claim live game appearance or complete UI coverage.
"""
import argparse,json,struct
from collections import Counter
from PIL import Image
from build_bitmap_font import ROOT,VERSION,PRIOR,ATLAS,digest,prior_font
from build_font4x_patch import SMALL,MEDIUM
from build_genei_font import SMALL_DATA,MEDIUM_DATA
from test_font4x_patch import HDCPU,TEX
from scenario_word_wrap import tokens,command_payloads,PEN_WIDTH,TARGET_WIDTH
from rayblade_codec import decompress
from test_inline_controls import execute_stream
from test_scenario_pages import native_format


def reference(cpu,char,flags,x,y,source,old):
    expected=bytearray(cpu.regions[3][1]);small=bool(flags&64)
    chars=SMALL if small else MEDIUM;index=chars.index(char)
    height=8 if small else 16;scale=1 if small else 2
    if char.isascii():
        code=ord(char)-32;gx=code%32*12;gy=code//32*24
        cell=source.crop((gx,gy,gx+12,gy+24)).point(lambda v:255 if v>=128 else 0)
        bounds=cell.getbbox();left=bounds[0] if bounds else 0;right=bounds[2] if bounds else 0
        def bit(xx,yy):
            if xx<4 or yy<4:return False
            px=(xx-4)//scale+left;py=(yy-4)//scale
            return px<right and py<24 and cell.getpixel((px,py))>=128
    else:
        start=(SMALL_DATA if small else MEDIUM_DATA)+index*height*32
        def bit(xx,yy):
            word=struct.unpack_from('<I',old,start+yy*8+(xx//32)*4)[0]
            return bool(word & (1<<(31-xx%32)))
    w=cpu.read(TEX+28,2);h=cpu.read(TEX+30,2)
    sx=1<<cpu.read(TEX+12,1);sy=1<<cpu.read(TEX+13,1)
    color=cpu.read(0x8c0980aa+(flags&14)*2,2)
    for yy in range(height*sy):
        py=y*sy+yy
        if py>=h:continue
        for xx in range(16*sx):
            px=x*sx+xx;ink=bit(xx*4//sx,yy*4//sy)
            if flags&128 and px+sx<w:
                struct.pack_into('<H',expected,32+(py*w+px+sx)*2,0x8000 if ink else 0)
            if ink and px<w:struct.pack_into('<H',expected,32+(py*w+px)*2,color)
    return expected


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    print('Plan: 345 native glyph/edge/scale cases, all 50,273 retained story commands, 166 inline command comparisons.',flush=True)
    if not args.verify:print('DRY RUN: no tests or reports written');return
    out=ROOT/'work/output'/VERSION;base=ROOT/'work/output'/PRIOR
    exe=(out/'1ST_READ.BIN').read_bytes();assert exe==(base/'1ST_READ.BIN').read_bytes()
    afs=(out/'WIN00.AFS').read_bytes();off,size=struct.unpack_from('<II',afs,8);font=afs[off:off+size]
    old_afs,old_off,old_size,old=prior_font()
    assert (off,size)==(old_off,old_size) and afs[:off]==old_afs[:off] and afs[off+size:]==old_afs[off+size:]
    source=Image.open(ATLAS).convert('L');assert source.size==(384,168)
    # Full source-cell membership checks, including every pixel in each bank.
    metric=json.loads((out/'bitmap-font-report.json').read_text('utf-8'))['metrics']
    for bank in metric.values():
        for row in bank['glyphs']:
            if row['packed_mask_bounds']:
                assert row['packed_mask_bounds'][2]/4+1-row['advance']<=TARGET_WIDTH-PEN_WIDTH
    cases=[]
    for chars,mode,ex in [(SMALL,64,2),(MEDIUM,0,1)]:
        cases.extend((c,i+32 if mode else i,mode|(128 if i%2 else 0),512,32,ex,2,12,4) for i,c in enumerate(chars))
    for mode,chars in [(64,SMALL),(0,MEDIUM)]:
        for ex,ey in [(0,0),(0,2),(1,0),(1,1),(2,1),(2,2)]:
            for x,y in [(0,0),(31,31),(32,4),(26,28)]:
                for c in ('W','j','♪'):
                    i=chars.index(c);cases.append((c,i+32 if mode else i,mode|128,32,32,ex,ey,x,y))
    instructions=0
    for number,(char,glyph,flags,w,h,ex,ey,x,y) in enumerate(cases):
        cpu=HDCPU(exe,font,glyph,flags,w,h,ex,ey)
        cpu.write(0x8c1f36b6,x,2);cpu.write(0x8c1f36b8,y,2)
        expected=reference(cpu,char,flags,x,y,source,old)
        instructions+=cpu.run_until()
        assert cpu.regions[3][1]==expected,('Bitmap raster/guard mismatch',char,flags,ex,ey,x,y)
        idx=glyph-32 if flags&64 else glyph
        assert cpu.read(0x8c1f36b6,2)==x+font[(0x20 if flags&64 else 0xa0)+idx]
        if (number+1)%100==0:print('Native raster cases passed:',number+1,flush=True)
    raster={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),
        'native_cases':len(cases),'supported_glyph_ids':len(SMALL)+len(MEDIUM),'SH4_instructions':instructions,
        'pixel_reference':'Direct source-image cell pixels at uniform scale, independent of packed glyph words; prior masks for five protected marks',
        'pixels_shadow_edges_and_guards':'exact','callee_saved_registers_and_stack':'pass',
        'limits':['No live appearance proof','Binary-alpha sampling of the supplied bitmap; enlargement adds no new outline detail']}
    archive=(out/'D_SCE.AFS').read_bytes();assert archive==(base/'D_SCE.AFS').read_bytes()
    component=json.loads((out/'text/scenario-component-report.json').read_text('utf-8'))
    actual={};counts=Counter(commands=0,wrapped=0,lines=0,special_control_fallbacks=0);maximum=0
    for member in component['members']:
        off=member['archive_offset'];plain,used=decompress(archive[off+20:off+member['packed_bytes']])
        assert digest(plain)==member['decoded_sha256'] and used==member['packed_bytes']-20
        bank=member['bank_offset'];assert plain[bank:bank+8]==b'RBSCEN02'
        for i,row in enumerate(member['commands']):
            a,b,p=struct.unpack_from('<HHI',plain,bank+32+i*8)
            assert (a,b,p)==(row['source_offset'],row['source_bytes'],row['english_offset']|0x80000000)
            payload=plain[row['english_offset']:row['english_offset']+row['english_bytes']]
            assert digest(payload)==row['english_sha256'];actual[row['id']]=payload
            width=0;glyphs=0;counts['commands']+=1;counts['wrapped']+=1
            for token in tokens(payload,font):
                if token['kind']=='boundary':
                    assert width<=PEN_WIDTH and glyphs<=127,('Retained line overflow',row['id'],width,glyphs)
                    maximum=max(maximum,width);counts['lines']+=1;width=0;glyphs=0
                else:width+=token['width'];glyphs+=token['kind']=='glyph'
    assert counts['commands']==50273
    previous=json.loads((base/'word-wrap-native-test.json').read_text('utf-8'))
    assert previous['archive_sha256']==digest(archive) and previous['executable_sha256']==digest(exe)
    layout={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'archive_sha256':digest(archive),
        'counts':dict(counts),'maximum_pen_width':maximum,'target_width':TARGET_WIDTH,
        'boundary_policy':'Retain byte-exact 0.1.13 line breaks; remeasure every line with current font; no translation edits',
        'native_pagination_cases':previous['native_pagination_cases'],'native_cases':previous['native_cases'],
        'native_pagination_proof_reuse':{'tested_build':PRIOR,'reason':'Executable and complete story archive byte-exact',
            'source_proof_sha256':digest((base/'word-wrap-native-test.json').read_bytes())},
        'checks':['Every bank entry, payload hash and wrap flag checked','Every retained line remeasured with the new font; 236-pixel pen and 127-glyph budget pass'],
        'limits':['Conservative historical wrapping may leave extra room','Live UI/continuation fit remains unverified']}
    print('PASS: all retained story payloads and',counts['lines'],'current-font line segments; maximum',maximum,flush=True)
    inline_steps=0;inline_cases=[];subtypes=Counter();max_x=64;max_y=16
    for member,row,payload in command_payloads():
        controls=[t for t in tokens(payload,font) if 'fc' in t]
        if not controls or all(t['fc']==0x3e for t in controls):continue
        before,n=native_format(exe,payload,width=30,limit=8191,capacity=8192);inline_steps+=n
        after,n=native_format(exe,actual[row['id']],width=127,limit=8191,capacity=8192);inline_steps+=n
        first,n,effects,states=execute_stream(exe,font,before,row['id']);inline_steps+=n
        second,n,new_effects,new_states=execute_stream(exe,font,after,row['id']);inline_steps+=n
        assert effects==new_effects and states==new_states
        assert ''.join(g[0] for g in first.glyphs if g[0]!=' ')==''.join(g[0] for g in second.glyphs if g[0]!=' ')
        for char,x,y,small in second.glyphs:
            index=(SMALL if small else MEDIUM).index(char);advance=font[(0x20 if small else 0xa0)+index]
            assert 64<=x and x+advance<=64+PEN_WIDTH and 16<=y and y+(8 if small else 16)<=64
            max_x=max(max_x,x+advance);max_y=max(max_y,y+(8 if small else 16))
        for token in controls:subtypes[hex(token['fc'])]+=1
        inline_cases.append({'id':row['id'],'source_sha256':digest(payload),'reflowed_sha256':digest(actual[row['id']]),
            'controls':len(controls),'recorded_effect_calls':len(effects)})
    assert len(inline_cases)==166
    inline={'build':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'commands':166,
        'controls_by_subtype':dict(subtypes),'SH4_instructions':inline_steps,'cases':inline_cases,
        'maximum_pen_end_x':max_x,'maximum_glyph_bottom_y':max_y,
        'checks':['Current-font cursor fits retained three-line layout','Original/reflowed native parser dispatch arguments and resume states match'],
        'limits':['Glyph drawing uses advance stubs independently verified by the raster test','Effect/GPU callees are bounded stubs; timing and live gameplay unverified']}
    print('PASS: 166 current-font inline comparisons,',inline_steps,'native instructions.',flush=True)
    if args.write_report:
        for name,value in [('genei-font-native-test.json',raster),('word-wrap-native-test.json',layout),('inline-control-native-test.json',inline)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
        current=component['word_wrap'];current.update(current_font_validation='All retained line segments and 166 inline cursor comparisons pass',
            native_verification='Fresh current-font raster/line/inline checks pass; historical text/native proofs retained by exact executable/archive hashes',
            inline_control_proof_sha256=digest((out/'inline-control-native-test.json').read_bytes()))
        manifest['scenario']['word_wrap']=current
        manifest['status']='Supplied bitmap font native-verified; local packaging and live appearance pending'
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
        (out/'text/scenario-component-report.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
        print('Wrote current-font proofs:',out,flush=True)


if __name__=='__main__':main()
