"""Verify battle selection against original SH-4 instructions.

Default is a read-only plan/sample. --verify executes native root lookups and
the selection/copy loop at 8c07a518, with deterministic RNG return values.
This checks branch/operand interpretation, not combat state setup or layout.
"""
import argparse
import hashlib
import json
from collections import Counter
from extract_battle_text import extract,digest
from build_font_patch import ROOT,BASE
from test_font_patch import CPU


def paths(record,start):
    nodes={n['offset']:n for n in record['nodes'] if n['kind']!='copy'}
    for span in record['spans']:
        nodes[span['offset']]={'kind':'copy','raw_hex':span['raw_hex'],'edges':[span['next_offset']]}
    def walk(pos,flags,rng,output,spans,edges,depth=0):
        if depth>256:raise ValueError('Selection path depth limit')
        node=nodes[pos];kind=node['kind']
        if kind=='copy':
            yield from walk(node['edges'][0],flags,rng,output+bytes.fromhex(node['raw_hex']),spans+(pos,),edges,depth+1)
        elif kind=='end':yield {'flags':flags,'rng':rng,'expected':output+b'\xff','spans':spans,'edges':edges}
        elif kind=='condition':
            flag=node['flag']
            for state in (False,True):
                if flag in flags and flags[flag]!=state:continue
                chosen=node['fallthrough'] if state==node['continue_when_set'] else node['jump']
                yield from walk(chosen,{**flags,flag:state},rng,output,spans,edges+((pos,state),),depth+1)
        elif kind=='random':
            count=len(node['choices'])
            if not count:yield {'flags':flags,'rng':rng,'expected':output+b'\xff','spans':spans,'edges':edges}
            for i,choice in enumerate(node['choices']):
                value=(i*32768+count-1)//count
                assert value*count//32768==i
                yield from walk(choice['target'],flags,rng+(value,),output,spans,edges,depth+1)
        else:raise ValueError('Unknown node')
    yield from walk(start,{},(),b'',(),())


def cases_for(records):
    for record in records:
        fields=record['categories']+[e for t in record['weapon_overrides'] for e in t['entries']]
        first={}
        for field in fields:first.setdefault(field['target'],field['pointer_offset'])
        first_paths={}
        for start in record['entry_targets']:
            for case in paths(record,start):
                first_paths.setdefault(start,case)
                yield record,start,first.get(start),case
        # Every alias pointer field is checked, not just each distinct target.
        for field in fields:
            if first[field['target']]==field['pointer_offset']:continue
            yield record,field['target'],field['pointer_offset'],first_paths[field['target']]


class SelectionCPU(CPU):
    def execute(self,pc,delay=False):
        if pc==0x8c093e98:
            if not self.rng:raise ValueError('Unexpected native RNG call')
            self.reg[0]=self.rng.pop(0);return self.pr
        return super().execute(pc,delay)


def native_select(exe,record_bytes,start,pointer,flags,rng,expected):
    source=0x8c500000;target=0x8c600000;guard=32;capacity=max(1024,len(expected)+64)
    cpu=SelectionCPU(exe,b'',0,0)
    cpu.regions=[(BASE,bytearray(exe)),(source,bytearray(record_bytes)),
                 (target-guard,bytearray(b'\xa5'*(capacity+2*guard))),
                 (0x8c1df52c,bytearray(128)),cpu.regions[-1]]
    for bit,state in flags.items():
        if state:cpu.write(0x8c1df52c+bit//8,cpu.read(0x8c1df52c+bit//8,1)|(1<<(7-bit%8)),1)
    original_sp=cpu.reg[15];original_r8=cpu.reg[8];cpu.reg[15]-=36;sp=cpu.reg[15]
    cpu.write(sp+16,target,4);cpu.write(sp+20,source+(start if pointer is None else pointer),4)
    cpu.write(sp+28,0xdead0000,4);cpu.write(sp+32,original_r8,4)
    cpu.pc=0x8c07a530 if pointer is None else 0x8c07a518;cpu.rng=list(rng)
    for count in range(300_000):
        if cpu.pc==0xdead0000:break
        cpu.pc=cpu.execute(cpu.pc)
    else:raise ValueError('Native selection instruction limit')
    if cpu.reg[0]!=target+len(expected) or cpu.reg[15]!=original_sp or cpu.reg[8]!=original_r8 or cpu.rng:
        raise ValueError('Native return pointer/frame/RNG consumption differs')
    memory,offset=cpu.area(target,capacity)
    if bytes(memory[offset:offset+len(expected)])!=expected:raise ValueError('Native output differs')
    if memory[:guard]!=b'\xa5'*guard or memory[offset+len(expected):]!=b'\xa5'*(capacity-len(expected)+guard):
        raise ValueError('Unexpected destination writes')
    return count


def root_lookup(exe,data,index,target):
    source=0x8c500000;cpu=CPU(exe,b'',0,0)
    cpu.regions=[(BASE,bytearray(exe)),(source,bytearray(data)),cpu.regions[-1]]
    cpu.reg[4:6]=[source,index];saved=cpu.reg[8:];cpu.pc=0x8c03f4c4
    for count in range(1000):
        if cpu.pc==0xdead0000:break
        cpu.pc=cpu.execute(cpu.pc)
    else:raise ValueError('Root lookup instruction limit')
    if cpu.reg[0]!=source+target or cpu.reg[8:]!=saved:raise ValueError('Native root lookup differs')
    return count


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    if args.write_report and not args.verify:raise ValueError('Report requires --verify')
    data,records,rows,summary=extract();cases=list(cases_for(records))
    print('Planned native selection cases:',len(cases),'maximum single output bytes:',max(len(c[3]['expected']) for c in cases),flush=True)
    print('Samples:',json.dumps([{'record':hex(r['offset']),'start':hex(s),'pointer':hex(p) if p is not None else None,
          'flags':c['flags'],'rng_calls':len(c['rng']),'output_bytes':len(c['expected'])} for r,s,p,c in cases[:3]]),flush=True)
    if not args.verify:print('DRY RUN: native instructions not executed; no report written');return
    exe=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();instructions=0;golden=0
    def check(payload,flags,rng,expected):
        nonlocal instructions,golden
        instructions+=native_select(exe,bytes.fromhex(payload),2,0,flags,rng,bytes.fromhex(expected));golden+=1
    check('0200fc0530040001ff02ff',{5:False},(),'01ff')
    check('0200fc0530040001ff02ff',{5:True},(),'02ff')
    check('0200fc0534040001ff02ff',{5:True},(),'01ff')
    check('0200fc0534040001ff02ff',{5:False},(),'02ff')
    for value,out in [(0,'01ff'),(16384,'02ff'),(32767,'02ff')]:
        check('0200fc003f06000600ffff01ff02ff',{},(value,),out)
    check('0200fc003fffff',{},(),'ff')
    check('020001fc843cfeff02fe03ff',{},(),'01fc843cfeff02fe03ff')
    check('0200f001fb4142fbff',{},(),'f001fb4142fbff')
    for root in summary['root_records']:instructions+=root_lookup(exe,data,root['index'],root['target'])
    seen=set();edges=set();largest=0;largest_case=None
    for i,(record,start,pointer,case) in enumerate(cases):
        base=record['offset'];piece=data[base:record['end_offset']]
        try:instructions+=native_select(exe,piece,start-base,None if pointer is None else pointer-base,
                                        case['flags'],case['rng'],case['expected'])
        except Exception as exc:raise ValueError('Record {} start {} pointer {}'.format(hex(base),hex(start),pointer)) from exc
        seen.update(case['spans']);edges.update(case['edges'])
        if len(case['expected'])>largest:
            largest=len(case['expected']);largest_case={'record_offset':hex(base),'start_offset':hex(start)}
        if (i+1)%1000==0:print('Verified {}/{} selection cases.'.format(i+1,len(cases)),flush=True)
    expected_spans={s['offset'] for r in records for s in r['spans']}
    if seen!=expected_spans:raise ValueError('Not all parsed text spans have a native witness')
    report={'version':'0.1.4','source_file':'D_BMESS.BIN','compressed_sha256':summary['compressed_sha256'],
            'decoded_sha256':digest(data),'native_selector_sha256':digest(exe[0x6a518:0x6a84a]),
            'native_root_lookup_cases':128,'golden_cases':golden,'selection_cases':len(cases),
            'SH4_instructions':instructions,'physical_records':len(records),'text_spans_witnessed':len(seen),
            'condition_outcomes_witnessed':len(edges),'maximum_single_output_bytes':largest,'largest_case':largest_case,
            'raw_output_and_return_pointer':'exact','destination_guards':'unchanged',
            'unreferenced_programs_forced_for_decode_verification':summary['unreferenced_program_starts'],
            'limits':['Native copy/selection loop and root lookup only; combat-state category/weapon selection remains separate',
                      'Deterministic RNG results are supplied; the RNG implementation is not tested',
                      'Standalone guarded destinations do not prove the game battle buffers fit English',
                      'Root-slot to character mapping, translation meaning, insertion and in-game checks remain pending']}
    print(json.dumps(report,indent=2),flush=True)
    if args.write_report:
        out=ROOT/'work/output/0.1.4/battle-native-test.json'
        out.write_text(json.dumps(report,indent=2),encoding='utf-8');print('Wrote',out)


if __name__=='__main__':main()
