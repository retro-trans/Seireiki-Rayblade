"""Remeasure retained English story and execute pagination/inline regressions."""
import argparse,json,struct
from collections import Counter
from build_antialias_font import ROOT,VERSION,PRIOR,digest,font_bytes
from build_font4x_patch import SMALL,MEDIUM
from scenario_word_wrap import tokens,command_payloads,PEN_WIDTH,TARGET_WIDTH
from rayblade_codec import decompress
from english_text_codec import encode
from test_scenario_pages import native_format,meaningful_tokens
from test_inline_controls import execute_stream


def main():
    global VERSION,PRIOR
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--version',default=VERSION,choices=['0.1.17','0.1.19','0.1.21']);ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    if VERSION=='0.1.19':PRIOR='0.1.18'
    elif VERSION=='0.1.21':PRIOR='0.1.20'
    print('Plan: every retained story line, 15 native pagination witnesses and all 166 inline parser/dispatch comparisons.',flush=True)
    if not args.verify:print('DRY RUN: no native execution/report written');return
    out=ROOT/'work/output'/VERSION;prior=ROOT/'work/output'/PRIOR
    exe=(out/'1ST_READ.BIN').read_bytes();_,font=font_bytes((out/'WIN00.AFS').read_bytes())
    archive=(out/'D_SCE.AFS').read_bytes();assert archive==(prior/'D_SCE.AFS').read_bytes()
    component=json.loads((out/'text/scenario-component-report.json').read_text('utf-8'))
    actual={};counts=Counter(commands=0,wrapped=0,lines=0,special_control_fallbacks=0);maximum=0
    for m in component['members']:
        off=m['archive_offset'];plain,used=decompress(archive[off+20:off+m['packed_bytes']]);assert used==m['packed_bytes']-20 and digest(plain)==m['decoded_sha256']
        bank=m['bank_offset'];assert plain[bank:bank+8]==b'RBSCEN02'
        for i,row in enumerate(m['commands']):
            a,b,p=struct.unpack_from('<HHI',plain,bank+32+i*8)
            assert (a,b,p)==(row['source_offset'],row['source_bytes'],row['english_offset']|0x80000000)
            payload=plain[row['english_offset']:row['english_offset']+row['english_bytes']];assert digest(payload)==row['english_sha256'];actual[row['id']]=payload
            width=0;glyphs=0;counts['commands']+=1;counts['wrapped']+=1
            for t in tokens(payload,font):
                if t['kind']=='boundary':
                    assert width<=PEN_WIDTH and glyphs<=127,(row['id'],width,glyphs)
                    maximum=max(maximum,width);counts['lines']+=1;width=0;glyphs=0
                else:width+=t['width'];glyphs+=t['kind']=='glyph'
    assert counts['commands']==50273
    metrics=json.loads((out/'antialias-font-report.json').read_text('utf-8'))['metrics']
    for bank in metrics.values():
        for g in bank['glyphs']:
            b=g['packed_mask_bounds']
            if b:assert b[2]/4+1-g['advance']<=TARGET_WIDTH-PEN_WIDTH
    oldproof=json.loads((prior/'word-wrap-native-test.json').read_text('utf-8'));native=[];steps=0
    for old in oldproof['native_cases']:
        identity=old['id']
        payload=actual.get(identity)
        if payload is None:
            assert identity in ('golden.greeting','golden.pagination','golden.mode')
            payload=encode('Ayaka: "Good morning, Touya Kazami."') if identity=='golden.greeting' else encode('<NL>'.join(['One two three four five six seven eight nine ten.']*12)) if identity=='golden.pagination' else encode('<ASCII:ON>'+('<NL>'.join(['narrow letters and words']*14))+'<ASCII:OFF>Medium text.')
        output,n=native_format(exe,payload,width=127,limit=8191,capacity=8192);steps+=n
        assert meaningful_tokens(output)==meaningful_tokens(payload)
        if identity=='golden.pagination':assert output.count(b'\xfe')>0
        native.append({'id':identity,'input_bytes':len(payload),'output_bytes':len(output),'SH4_instructions':n})
    layout={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'archive_sha256':digest(archive),'counts':dict(counts),'maximum_pen_width':maximum,'target_width':TARGET_WIDTH,'native_pagination_cases':len(native),'native_cases':native,'SH4_instructions':steps,'checks':['Every compiled payload and high-bit wrap flag checked','All current-font line widths and complete faint-edge bounds fit the retained pen/ink budgets','Fresh native pagination output retains meaningful glyph/control bytes'],'limits':['Conservative historical wrapping leaves extra room','Live dialogue/continuation appearance remains unverified']}
    print('PASS:',counts['lines'],'story line segments;',len(native),'native pagination witnesses.',flush=True)
    steps=0;cases=[];subtypes=Counter();max_x=64;max_y=16
    for member,row,payload in command_payloads():
        controls=[t for t in tokens(payload,font) if 'fc' in t]
        if not controls or all(t['fc']==0x3e for t in controls):continue
        before,n=native_format(exe,payload,width=30,limit=8191,capacity=8192);steps+=n
        after,n=native_format(exe,actual[row['id']],width=127,limit=8191,capacity=8192);steps+=n
        first,n,effects,states=execute_stream(exe,font,before,row['id']);steps+=n
        second,n,new_effects,new_states=execute_stream(exe,font,after,row['id']);steps+=n
        assert effects==new_effects and states==new_states
        assert ''.join(g[0] for g in first.glyphs if g[0]!=' ')==''.join(g[0] for g in second.glyphs if g[0]!=' ')
        for ch,x,y,small in second.glyphs:
            i=(SMALL if small else MEDIUM).index(ch);advance=font[(0x20 if small else 0xa0)+i]
            assert 64<=x and x+advance<=64+PEN_WIDTH and 16<=y and y+(8 if small else 16)<=64
            max_x=max(max_x,x+advance);max_y=max(max_y,y+(8 if small else 16))
        for t in controls:subtypes[hex(t['fc'])]+=1
        cases.append({'id':row['id'],'source_sha256':digest(payload),'reflowed_sha256':digest(actual[row['id']]),'controls':len(controls),'recorded_effect_calls':len(effects)})
    assert len(cases)==166
    inline={'build':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),'commands':166,'controls_by_subtype':dict(subtypes),'SH4_instructions':steps,'cases':cases,'maximum_pen_end_x':max_x,'maximum_glyph_bottom_y':max_y,'checks':['Current-font cursor fits retained three-line layout','Fresh original/reflowed native parser dispatch arguments and resume states match'],'limits':['Glyph drawing uses advance fixtures; raster checked independently','Effect/GPU endpoints are bounded fixtures; timing and live gameplay unverified']}
    print('PASS: 166 inline comparisons,',steps,'native instructions.',flush=True)
    if args.write_report:
        for name,proof in [('word-wrap-native-test.json',layout),('inline-control-native-test.json',inline)]:(out/name).write_text(json.dumps(proof,indent=2)+'\n','utf-8')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
        wrap=component['word_wrap'];wrap.update(font_sha256=digest(font),current_font_validation='All retained line segments, faint-edge ink budgets, native pagination and 166 inline comparisons pass',inline_control_proof_sha256=digest((out/'inline-control-native-test.json').read_bytes()))
        manifest['scenario']['word_wrap']=wrap
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8');(out/'text/scenario-component-report.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
