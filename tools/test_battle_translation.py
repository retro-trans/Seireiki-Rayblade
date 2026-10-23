"""Execute relocated English battle paths, PRS loading and workspace geometry.

Workspace tests execute native allocation/root lookup/copy/call plumbing with
selection stubs; the selection loop itself is tested independently on every
source path. Neither test claims the preceding combat-state setup is proved.
"""
import argparse,json,struct
from build_font_patch import ROOT,BASE
from build_battle_translation import VERSION,build,digest
from build_battle_patch import candidate_executable,DATA_CAPACITY,RECORD_COPY,OUTPUT_CAPACITY,WORKSPACE_SIZE
from test_battle_text import cases_for,native_select,root_lookup
from test_font_patch import CPU
from check_native_text_components import verify as native_decompress


class WorkspaceCPU(CPU):
    def execute(self,pc,delay=False):
        if pc==0x8c03f748:
            assert self.reg[4]==WORKSPACE_SIZE
            self.reg[0]=self.heap;self.allocations+=1;return self.pr
        if pc==0x8c02f414:
            self.reg[0]=self.slots[self.reg[4]]|0x80;return self.pr
        if pc==0x8c093dc0:
            dest,source,size=self.reg[4:7];assert size==RECORD_COPY
            b,o=self.area(source,size);raw=bytes(b[o:o+size]);a,p=self.area(dest,size);a[p:p+size]=raw
            self.copies.append((dest,source,size));self.reg[0]=dest;return self.pr
        if pc==0x8c079ff8:
            category,record,dest=self.reg[4:7]
            assert category==len(self.select_calls)
            assert record==self.heap+(RECORD_COPY if category in (1,2) else 0)
            expected_dest=self.heap+2*RECORD_COPY+sum(len(m) for m in self.messages[:category])
            assert dest==expected_dest
            raw=self.messages[category];a,p=self.area(dest,len(raw));a[p:p+len(raw)]=raw
            self.select_calls.append((category,record,dest));self.reg[0]=dest+len(raw);return self.pr
        return super().execute(pc,delay)


def workspace(exe,data,slots,flag,messages):
    source=0x8c500000;target=0x8c600000;guard=32
    cpu=WorkspaceCPU(exe,b'',0,0);stack=cpu.regions[-1]
    padded=data+b'\0'*(DATA_CAPACITY-len(data))
    cpu.regions=[(BASE,bytearray(exe)),(source,bytearray(padded)),
        (target-guard,bytearray(b'\xa5'*(WORKSPACE_SIZE+2*guard))),
        (0x8c1db000,bytearray(0x5000)),(0x8c17fba4,bytearray(4)),stack]
    cpu.heap=target;cpu.slots=slots;cpu.messages=messages
    cpu.allocations=0;cpu.copies=[];cpu.select_calls=[]
    cpu.write(0x8c1dbee8,source,4);cpu.write(0x8c1dbfcd,flag,1)
    cpu.write(0x8c1dfc64,0,1);cpu.write(0x8c1dfc65,1,1)
    sp=cpu.reg[15];steps=0
    # These are separate phases of the game's battle state machine, not
    # straight-line adjacent code. Preserve the same globals between them.
    for begin,end in [(0x1ba48,0x1bad2),(0x1bb6c,0x1bbc6)]:
        cpu.pc=BASE+begin
        for count in range(10000):
            if cpu.pc==BASE+end:break
            cpu.pc=cpu.execute(cpu.pc);steps+=1
        else:raise ValueError('Workspace phase instruction limit')
    assert cpu.reg[15]==sp and cpu.allocations==1 and len(cpu.copies)==2 and len(cpu.select_calls)==4
    ids=[slots[1],slots[0]] if flag&64 else [slots[0],slots[1]]
    for side,index in enumerate(ids):
        location=index*4+struct.unpack_from('<I',data,index*4)[0]
        a,o=cpu.area(target+side*RECORD_COPY,RECORD_COPY)
        assert bytes(a[o:o+RECORD_COPY])==padded[location:location+RECORD_COPY]
    output=b''.join(messages);assert len(output)<=OUTPUT_CAPACITY
    a,o=cpu.area(target+2*RECORD_COPY,OUTPUT_CAPACITY)
    assert bytes(a[o:o+len(output)])==output
    assert a[:guard]==b'\xa5'*guard and a[o+len(output):]==b'\xa5'*(OUTPUT_CAPACITY-len(output)+guard)
    assert cpu.read(0x8c1dbff0,4)==target+2*RECORD_COPY
    for i,ptr in enumerate([0x8c1dbff4,0x8c1dbff8,0x8c1dbffc]):
        assert cpu.read(ptr,4)==target+2*RECORD_COPY+sum(len(m) for m in messages[:i+1])
    assert cpu.reg[0]==target+2*RECORD_COPY+len(output)
    return steps


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.6','0.1.7','0.1.11','0.1.12','0.1.17','0.1.19','0.1.21'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    if args.write_report and not args.verify:raise ValueError('Report requires verification')
    plain,packed,old,_,mapping,encoded,component=build();exe,_,_=candidate_executable()
    if args.version=='0.1.7':
        from build_scenario_patch import candidate_executable as scenario_executable
        exe,_=scenario_executable()
        assert (ROOT/'work/output/0.1.7/1ST_READ.BIN').read_bytes()==exe
    elif args.version=='0.1.11':
        from build_genei_font import compose
        files,_,_,_=compose();exe=files['1ST_READ.BIN']
        assert (ROOT/'work/output/0.1.11/1ST_READ.BIN').read_bytes()==exe
    elif args.version=='0.1.12':
        from build_word_wrap_story import candidate_executable as wrap_executable
        exe,_=wrap_executable()
        assert (ROOT/'work/output/0.1.12/1ST_READ.BIN').read_bytes()==exe
    elif args.version=='0.1.17':
        from build_antialias_font import compose
        files,_,_,_=compose();exe=files['1ST_READ.BIN']
        assert (ROOT/'work/output/0.1.17/1ST_READ.BIN').read_bytes()==exe
    elif args.version=='0.1.19':
        from build_library_header_patch import compose
        files,_,_=compose();exe=files['1ST_READ.BIN']
        assert (ROOT/'work/output/0.1.19/1ST_READ.BIN').read_bytes()==exe
    elif args.version=='0.1.21':
        from build_embedded_dialogue_patch import compose
        files,_,_=compose();exe=files['1ST_READ.BIN']
        assert (ROOT/'work/output/0.1.21/1ST_READ.BIN').read_bytes()==exe
    cases=list(cases_for(old));expected=lambda c:b''.join(encoded[s] for s in c['spans'])+b'\xff'
    largest=max((expected(c) for _,_,_,c in cases),key=len)
    print('Plan:',len(cases),'native English selection cases;128roots;256workspace cases; native PRS decode.',flush=True)
    print('Largest record',component['maximum_record_bytes'],'of',RECORD_COPY,'; largest output',len(largest),'; four-output bound',4*len(largest),'of',OUTPUT_CAPACITY,flush=True)
    assert len(plain)<=DATA_CAPACITY and 4*len(largest)<=OUTPUT_CAPACITY
    if not args.verify:print('DRY RUN: native verification not executed; no report written');return
    selection_steps=0;seen=set();edges=set()
    for record,start,pointer,case in cases:
        base=mapping[record['offset']];piece=plain[base:base+RECORD_COPY]
        p=None if pointer is None else pointer-record['offset']
        selection_steps+=native_select(exe,piece,mapping[start]-base,p,case['flags'],case['rng'],expected(case))
        seen.update(case['spans']);edges.update(case['edges'])
    assert len(seen)==5516 and len(edges)==412
    roots=json.loads((ROOT/'work/source/battle/summary.json').read_text('utf-8'))['root_records']
    for root in roots:selection_steps+=root_lookup(exe,plain,root['index'],mapping[root['target']])
    print('Native English selection/root paths passed.',flush=True)
    workspace_steps=0
    for index in range(128):
        for flag in (0,64):workspace_steps+=workspace(exe,plain,[index,(index+1)%128],flag,[largest]*4)
    print('Native workspace allocation, record copies and four-output plumbing passed.',flush=True)
    decode_steps=native_decompress(exe,packed,plain,DATA_CAPACITY,instruction_limit=20_000_000)
    print('Native PRS decoder passed.',flush=True)
    report={'version':args.version,'component_sha256':digest(plain),'compressed_sha256':digest(packed),
        'executable_sha256':digest(exe),'native_selection_cases':len(cases),'native_root_cases':128,
        'workspace_cases':256,'text_spans_witnessed':len(seen),'condition_outcomes_witnessed':len(edges),
        'SH4_selection_instructions':selection_steps,'SH4_workspace_instructions':workspace_steps,
        'SH4_decompression_instructions':decode_steps,'maximum_single_output_bytes':len(largest),
        'maximum_four_output_bound':4*len(largest),'selected_output_capacity':OUTPUT_CAPACITY,
        'decoded_bytes':len(plain),'decoded_capacity':DATA_CAPACITY,
        'maximum_record_bytes':component['maximum_record_bytes'],'record_copy_bytes':RECORD_COPY,
        'raw_outputs_return_pointers_and_guards':'exact','last_record_copy_tail':'explicitly zero-padded in component',
        'limits':['Workspace tests execute allocation/copy and four-call phases separately, stubbing selection to force maximum-length messages; selection is independently checked on all source paths',
            'Preceding combat-state category/weapon mapping and actual RNG implementation remain unverified',
            'Display layout, independent meaning review and gameplay remain pending']}
    print(json.dumps(report,indent=2),flush=True)
    if args.write_report:
        out=ROOT/'work/output'/args.version/'battle-english-native-test.json';out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2),'utf-8');print('Wrote',out)


if __name__=='__main__':main()
