"""Execute embedded English lookup, native pagination/VM advance and fallback.

Native lookup/formatter/VM phases execute. Glyph advance and effect/GPU callees
are bounded fixtures for layout checks. No live gameplay claim.
"""
import argparse,json
from build_embedded_dialogue_patch import ROOT,VERSION,PRIOR,ENTRY,BASE,compose,digest
from prepare_embedded_dialogue import DEST,extract
from build_scenario_patch import HEAP_POINTER
from build_scenario_translation import BANK_POINTER_OFFSET
from test_scenario_integration import StoryCPU,fresh,reset,run,guarded,HEAP,DEST as OUTPUT
from test_scenario_pages import native_format,meaningful_tokens
from english_text_codec import encode
from scenario_word_wrap import wrap,INLINE_FC,font_bytes
from test_inline_controls import execute_stream
from test_ui_layouts import specimen


class EmbeddedCPU(StoryCPU):
    def execute(self,pc,delay=False):
        if pc==0x8c07bc00:self.formatter_calls.append(tuple(self.reg[4:8]))
        return super().execute(pc,delay)


def output_bytes(cpu):
    b,o=cpu.area(OUTPUT,8192);n=0
    while True:
        v=b[o+n];n+=1
        if v==255:break
        if v==252:n+=4 if b[o+n+1]==0x3c else 2
        elif 0xf0<=v<=0xfa:n+=1
        assert n<8192
    assert b[o+n:o+8192]==b'\xa5'*(8192-n)
    return bytes(b[o:o+n])


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    print('Plan: all 13 embedded commands before/after story heap setup, direct and native VM-phase calls, all parsed layouts and nonmatching-pointer fallbacks.',flush=True)
    if not args.verify:print('DRY RUN: no native execution/report');return
    out=ROOT/'work/output'/VERSION;files,_,component=compose();exe=(out/'1ST_READ.BIN').read_bytes();assert exe==files['1ST_READ.BIN']
    recipe=json.loads(DEST.read_text('utf-8'));assert recipe==extract()[0]
    font=font_bytes(VERSION);by_id={r['id']:r for r in recipe['rows']};cases=[];steps={'formatter_VM':0,'reference':0,'parser_effect':0,'fallback':0};maximum=0;glyphs=0;preview=None
    for record in component['records']:
        row=by_id[record['id']];raw=exe[record['english_offset']:record['english_offset']+record['english_bytes']]
        expected,stats=wrap(encode(row['en']),font,safe_fc=INLINE_FC);assert raw==expected and stats['forced_word_breaks']==0
        reference,n=native_format(exe,raw,width=127,limit=8191,capacity=8192);steps['reference']+=n
        for warm in (False,True):
            for phases in (False,True):
                cpu=fresh(exe,b'');cpu.__class__=EmbeddedCPU;cpu.formatter_calls=[];cpu.write(HEAP_POINTER,HEAP if warm else 0,4)
                reset(cpu);saved=cpu.reg[8:];cpu.reg[4:8]=[OUTPUT,BASE+row['source_offset'],30,3];cpu.write(cpu.reg[15],8191,4)
                if phases:
                    cpu.write(0x8c1dbe24,BASE+row['command_offset']+1,4)
                    n=run(cpu,BASE+0x6cfb2,BASE+0x6cfe6)
                    assert cpu.read(BASE+0x8b1ec,4)==row['source_bytes']+1
                    n+=run(cpu,BASE+0x6d4b8,BASE+0x6d4c2);assert cpu.reg[0]==0x6000|(row['source_bytes']+2)
                    cpu.write(cpu.reg[15],cpu.reg[0],4);n+=run(cpu,BASE+0x2f35c,BASE+0x2f382)
                    assert cpu.read(0x8c1dbe24,4)==BASE+row['command_end']+1
                    assert cpu.read(0x8c1dbe70,4)==exe[row['command_end']]
                else:
                    n=run(cpu,ENTRY);assert cpu.reg[0]==row['source_bytes']
                steps['formatter_VM']+=n;assert cpu.reg[8:]==saved
                assert cpu.formatter_calls==[(OUTPUT,BASE+record['english_offset'],127,3)]
                actual=output_bytes(cpu);assert actual==reference and meaningful_tokens(actual)==meaningful_tokens(raw);guarded(cpu)
                maximum=max(maximum,len(actual));cases.append({'id':row['id'],'story_heap_initialized':warm,'native_VM_phases':phases,'native_instructions':n,'formatted_bytes':len(actual)})
        parsed,n,effects,states=execute_stream(exe,font,reference,row['id']);steps['parser_effect']+=n;glyphs+=len(parsed.glyphs)
        for ch,x,y,small in parsed.glyphs:
            from build_font4x_patch import SMALL,MEDIUM
            index=(SMALL if small else MEDIUM).index(ch)
            assert 64<=x and x+font[(0x20 if small else 0xa0)+index]<=300 and 16<=y and y+(8 if small else 16)<=64
        if preview is None:
            first=reference.split(b'\xfe')[0]
            if not first.endswith(b'\xff'):first+=b'\xff'
            page,n,_,_=execute_stream(exe,font,first,row['id']);steps['parser_effect']+=n
            preview=[(ch,x-64,y-16,small) for ch,x,y,small in page.glyphs]
    # Synthetic valid text at the original scenario source address exercises
    # the unmatched-pointer tail path without depending on any loaded bank.
    for warm in (False,True):
        cpu=fresh(exe,b'');cpu.__class__=EmbeddedCPU;cpu.formatter_calls=[];cpu.write(HEAP_POINTER,HEAP if warm else 0,4);reset(cpu)
        cpu.write(HEAP+BANK_POINTER_OFFSET,0,4)
        payload=encode('Fallback path.');source=BASE+0x80;b,o=cpu.area(source,len(payload));b[o:o+len(payload)]=payload
        cpu.reg[4:8]=[OUTPUT,source,30,3];cpu.write(cpu.reg[15],8191,4);saved=cpu.reg[8:]
        steps['fallback']+=run(cpu,ENTRY);assert cpu.reg[0]==len(payload) and cpu.reg[8:]==saved
        assert cpu.formatter_calls==[(OUTPUT,source,30,3)] and output_bytes(cpu)==payload;guarded(cpu)
    assert len(cases)==52
    proof={'version':VERSION,'executable_sha256':digest(exe),'component_sha256':digest((out/'embedded-dialogue-component.json').read_bytes()),'font_sha256':digest(font),'recipe_sha256':digest(DEST.read_bytes()),'commands':13,'native_formatter_VM_cases':len(cases),'cold_and_warm_heap_cases':'pass','native_parser_commands':13,'native_fallback_cases':2,'parsed_glyphs':glyphs,'maximum_formatted_bytes':maximum,'capacity':8192,'native_instructions':steps,'cases':cases,
        'checks':['All 13 exact pointers select the correct static English payload before/after story heap initialization','Native formatter output exactly matches independent direct formatting; wrapper returns original source consumption','Native handler count and VM next-opcode arithmetic preserve every original command boundary','Callee-saved registers/stack, full output buffers and guards pass','All English words/FC operands retained; parsed cursor fits three-line 236-pixel pen area','Unmatched pointers retain original source/width and existing story-lookup path'],
        'limits':['Parser glyph advance and scene/effect callees are bounded fixtures','The handler formatting/count/advance phases execute separately; UI construction, callbacks/timing, GPU and live appearance remain unverified','Embedded region scan plus two marker resolutions do not prove full VM/native text coverage','These commands reuse existing drafts; independent meaning review is still pending']}
    print(json.dumps({k:v for k,v in proof.items() if k!='cases'},indent=2),flush=True)
    if args.write_report:
        p=out/'embedded-dialogue-native-test.json';p.write_text(json.dumps(proof,indent=2)+'\n','utf-8');specimen(out/'embedded-dialogue-preview.png',preview,font)
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m['embedded_dialogue'].update(native_validation='pass; scope/limits in proof',proof_sha256=digest(p.read_bytes()));(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
