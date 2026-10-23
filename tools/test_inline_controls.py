"""Execute native inline-control parsing/dispatch with bounded effect callees.

Text parser and inline handler instructions are real. Glyph rasterization is
replaced by the already-verified font's cursor advance, and scene/effect
callees are recorded stubs. This verifies operand consumption, call arguments
and cursor continuity, not the actual effects, graphics or timing.
"""
import argparse,json,struct
from collections import Counter
from build_genei_font import ROOT,digest,SMALL,MEDIUM
from scenario_word_wrap import command_payloads,tokens,font_bytes,wrap,INLINE_FC,PEN_WIDTH
from test_font_patch import CPU
from test_scenario_pages import native_format

BASE=0x8c010000
SOURCE=0x8c500000
STOP=0xdead0000
FONT=0x8c600000
CURSOR=0x8c1f36b6
FLAGS=0x8c1f36ba
TEXT=0x8c17fba8


class InlineCPU(CPU):
    def execute(self,pc,delay=False):
        if pc==0x8c07b28e:
            glyph=self.reg[4];small=bool(self.read(FLAGS,1)&64)
            index=(glyph-32)&127 if small else glyph
            chars=SMALL if small else MEDIUM
            assert 0<=index<len(chars),('Invalid Latin glyph',glyph,small)
            advance=self.font[(0x20 if small else 0xa0)+index]
            self.glyphs.append((chars[index],self.read(CURSOR,2),self.read(CURSOR+2,2),small))
            self.write(CURSOR,self.read(CURSOR,2)+advance,2)
            return self.pr
        if pc in self.stub_targets:
            argc={0x8c08351e:4,0x8c083714:2,0x8c07745e:2,0x8c085480:1,0x8c02f4f0:2,0x8c0320aa:1}[pc]
            self.calls.append((hex(pc),tuple(self.reg[4:4+argc])))
            self.reg[0]=0x2345 if pc==0x8c07745e else 0
            return self.pr
        return super().execute(pc,delay)


def fresh(exe,font,payload):
    cpu=InlineCPU(exe,b'',0,0)
    cpu.regions=[(BASE,bytearray(exe)),(0x8c160000,bytearray(0x20000)),
        (0x8c1d0000,bytearray(0x10000)),(0x8c1f0000,bytearray(0x10000)),
        (0x8c400000,bytearray(0x10000)),(SOURCE,bytearray(payload+b'\0'*64)),
        (FONT,bytearray(font)),(0x8c700000,bytearray(0x1000))]
    cpu.font=font;cpu.calls=[];cpu.glyphs=[]
    # Targets decoded from literal pools in the inline parser/handler. Their
    # internals remain outside this test's claim and cannot change text state.
    cpu.stub_targets={0x8c08351e,0x8c083714,0x8c07745e,0x8c085480,0x8c02f4f0,0x8c0320aa}
    cpu.write(CURSOR,64,2);cpu.write(CURSOR+2,16,2);cpu.write(FLAGS,128,1)
    cpu.write(0x8c1f36a4,FONT,4)
    cpu.write(0x8c019088,0x8c400000,4)
    cpu.write(0x8c169c68,0x8c400000,4)
    # Animation-table indirections exercised by FC 3C operands F0..FF.
    cpu.write(0x8c400000+60,0x100,4)
    for i in range(16):cpu.write(0x8c400000+60+0x100+i*2,0x40,2)
    return cpu


def run(cpu,start,limit=500000):
    cpu.pc=start
    for count in range(limit):
        if cpu.pc==STOP:return count
        try:cpu.pc=cpu.execute(cpu.pc)
        except Exception as error:raise RuntimeError('Native inline phase at '+hex(cpu.pc)) from error
    raise ValueError('Inline native instruction limit at '+hex(cpu.pc))


def parse(cpu,pointer):
    # Execute the parser phase with its actual native frame layout. Entry
    # allocation/context selection and the GPU submit call are separate scopes.
    frame=0x8c700500;cpu.reg[15]=frame
    cpu.write(frame+124,STOP,4);cpu.write(frame+128,cpu.reg[8],4)
    cpu.write(frame+132,pointer,4)
    cpu.write(frame+120,64,2);cpu.write(frame+118,16,2)
    cpu.write(frame+123,1,1);cpu.write(frame+115,1,1)
    steps=run(cpu,0x8c07ac64)
    return cpu.reg[0],steps


def handle(cpu,pointer):
    cpu.write(TEXT,pointer,4);cpu.reg[15]=0x8c700800;cpu.pr=STOP
    before=cpu.read(CURSOR,4),cpu.read(FLAGS,1)
    steps=run(cpu,0x8c07c7fc)
    assert (cpu.read(CURSOR,4),cpu.read(FLAGS,1))==before,'Inline handler changed text geometry/mode'
    return cpu.read(TEXT,4),steps,cpu.reg[0]


def execute_stream(exe,font,payload,identity):
    rows=tokens(payload,font);controls=[r for r in rows if 'fc' in r]
    cpu=fresh(exe,font,payload);pointer=SOURCE;seen=[];states=[];steps=0
    for iteration in range(1000):
        pointer,n=parse(cpu,pointer);steps+=n;value=cpu.read(pointer-1,1)
        if value==0xff:break
        if value==0xfe:
            cpu.write(CURSOR,64,2);cpu.write(CURSOR+2,16,2);continue
        assert value==0xfc,('Unexpected parser stop',identity,hex(pointer),value)
        token=next(r for r in controls if SOURCE+r['offset']+1==pointer)
        new_pointer,n,state=handle(cpu,pointer);steps+=n
        assert new_pointer==pointer+len(token['raw'])-1,('Inline operand consumption',identity,token['raw'].hex(),hex(new_pointer-pointer))
        seen.append(token['raw']);states.append(state);pointer=new_pointer
    else:raise ValueError('Inline continuation limit')
    assert seen==[r['raw'] for r in controls]
    assert ''.join(g[0] for g in cpu.glyphs)==''.join(r.get('character','') for r in rows)
    effects=[call for call in cpu.calls if call[0]!='0x8c0320aa']
    return cpu,steps,effects,states


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    print('Plan: native text parser and inline dispatch for all 166 specialized-control-bearing story commands.')
    if not args.verify:print('DRY RUN: no native execution or report written');return
    exe=(ROOT/'work/output/0.1.12/1ST_READ.BIN').read_bytes();font=font_bytes()
    count=0;steps=0;types=Counter();cases=[];breaks=0;maximum_x=64;maximum_y=16
    for member,record,payload in command_payloads():
        rows=tokens(payload,font)
        controls=[r for r in rows if 'fc' in r]
        if not controls or all(r['fc']==0x3e for r in controls):continue
        wrapped,stats=wrap(payload,font,safe_fc=INLINE_FC)
        assert stats['wrapped'] and not stats['forced_word_breaks']
        baseline,n=native_format(exe,payload,width=30,limit=8191,capacity=8192);steps+=n
        reflowed,n=native_format(exe,wrapped,width=127,limit=8191,capacity=8192);steps+=n
        before,n,effects,states=execute_stream(exe,font,baseline,record['id']);steps+=n
        after,n,after_effects,after_states=execute_stream(exe,font,reflowed,record['id']);steps+=n
        assert effects==after_effects and states==after_states,'Effect arguments/order or resume states changed'
        assert ''.join(g[0] for g in before.glyphs if g[0]!=' ')==''.join(g[0] for g in after.glyphs if g[0]!=' ')
        for char,x,y,small in after.glyphs:
            chars=SMALL if small else MEDIUM;advance=font[(0x20 if small else 0xa0)+chars.index(char)]
            assert 64<=x and x+advance<=64+PEN_WIDTH,('Reflow cursor outside dialogue width',record['id'],char,x)
            assert 16<=y and y+(8 if small else 16)<=64,('Reflow cursor outside three lines',record['id'],y)
            maximum_x=max(maximum_x,x+advance);maximum_y=max(maximum_y,y+(8 if small else 16))
        for row in controls:types[hex(row['fc'])]+=1
        breaks+=stats['automatic_breaks'];count+=1
        cases.append({'id':record['id'],'controls':len(controls),'recorded_effect_calls':len(effects),
            'automatic_breaks':stats['automatic_breaks'],'formatted_bytes':len(reflowed),
            'source_sha256':digest(payload),'reflowed_sha256':digest(wrapped),
            'effect_arguments_and_states_sha256':digest(json.dumps([effects,states]).encode())})
    proof={'build':'0.1.12','executable_sha256':digest(exe),'font_sha256':digest(font),
        'commands':count,'controls_by_subtype':dict(types),'SH4_instructions':steps,
        'automatic_breaks':breaks,'maximum_pen_end_x':maximum_x,'maximum_glyph_bottom_y':maximum_y,
        'cases':cases,'checks':['Complete Latin glyph/control sequences retained across native parser stops',
            'Native inline operand lengths and text cursor/mode continuity match',
            'Original and word-reflowed streams dispatch identical effect argument sequences and resume states',
            'Reflowed native cursor positions fit 236 logical pen pixels and the three-line window'],
        'limits':['Parser entry allocation/context selection and GPU submission are outside the phase test',
            'Glyph drawing uses measured advance stubs; scene/effect callees are recorded bounded stubs',
            'Effect behavior, callback side effects, timing and full gameplay remain unverified']}
    print(json.dumps({k:v for k,v in proof.items() if k!='cases'},indent=2))
    if args.write_report:
        path=ROOT/'work/output/0.1.12/inline-control-native-test.json';path.write_text(json.dumps(proof,indent=2)+'\n','utf-8');print('Wrote',path)


if __name__=='__main__':main()
