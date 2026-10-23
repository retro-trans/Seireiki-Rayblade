"""Execute story loader/lookup/formatter and original VM advancement offline.

File I/O, allocation and cache maintenance are bounded stubs. PRS decoding,
lookup hooks, formatting and source-count/VM pointer arithmetic execute SH-4.
"""
import argparse,json,struct
from build_font_patch import ROOT,BASE
from build_scenario_translation import (VERSION,SCRIPT_CAPACITY,SCRATCH_CAPACITY,
    DIALOGUE_CAPACITY,BANK_POINTER_OFFSET,digest,align)
from build_scenario_patch import candidate_executable,FORMATTER,HEAP_BYTES,SOURCE,HEAP_POINTER
from rayblade_codec import decompress
from test_font_patch import CPU
from test_scenario_pages import meaningful_tokens

HEAP=0x8c500000
DEST=0x8c600000
GUARD=32


class StoryCPU(CPU):
    def execute(self,pc,delay=False):
        if pc==0x8c03f748:
            size=self.reg[4];assert self.reg[5]==0
            assert size in (HEAP_BYTES,DIALOGUE_CAPACITY)
            self.allocations.append(size);self.reg[0]=HEAP if size==HEAP_BYTES else DEST
            return self.pr
        if pc==0x8c021d9e:
            file,index,target,extra=self.reg[4:8]
            assert file==2 and extra==0
            if self.file_failure:self.reg[0]=0;return self.pr
            off,size=struct.unpack_from('<II',self.archive,8+index*8)
            raw=self.archive[off:off+align(size)]
            assert len(raw)==align(size)
            a,p=self.area(target,len(raw));a[p:p+len(raw)]=raw
            self.reads.append((index,target,len(raw)));self.reg[0]=target
            return self.pr
        if pc==0x8c0a437a:
            self.flushes.append(tuple(self.reg[4:6]));return self.pr
        if pc==0x8c093dc0:
            dest,source,size=self.reg[4:7]
            a,p=self.area(source,size);raw=bytes(a[p:p+size]);b,q=self.area(dest,size);b[q:q+size]=raw
            self.copies.append((dest,source,size));self.reg[0]=dest;return self.pr
        if pc==0x8c07bc00 and self.fast_format:
            dest,source,width,lines=self.reg[4:8]
            assert (dest,width,lines)==(DEST,self.expected_width,3)
            assert self.read(self.reg[15],4)==DIALOGUE_CAPACITY-1
            a,p=self.area(source,len(self.expected));assert bytes(a[p:p+len(self.expected)])==self.expected
            assert source==self.expected_pointer
            self.format_calls+=1;self.reg[0]=len(self.expected);return self.pr
        return super().execute(pc,delay)


def fresh(exe,archive):
    cpu=StoryCPU(exe,b'',0,0);stack=cpu.regions[-1]
    cpu.regions=[(BASE,bytearray(exe)),(0x8c169af0,bytearray(20)),(0x8c1db000,bytearray(0x5000)),
        (0x8c17fba4,bytearray(16)),(HEAP-GUARD,bytearray(b'\xa5'*(HEAP_BYTES+2*GUARD))),
        (DEST-GUARD,bytearray(b'\xa5'*(DIALOGUE_CAPACITY+2*GUARD))),stack]
    cpu.archive=archive;cpu.allocations=[];cpu.reads=[];cpu.flushes=[];cpu.copies=[]
    cpu.file_failure=False;cpu.fast_format=False;cpu.format_calls=0
    cpu.write(0x8c1dbf50,SOURCE,4);cpu.write(HEAP_POINTER,HEAP,4)
    return cpu


def run(cpu,start,stop=0xdead0000,limit=5_000_000):
    cpu.pc=start
    for steps in range(limit):
        if cpu.pc==stop:return steps
        cpu.pc=cpu.execute(cpu.pc)
    raise ValueError('Story native instruction limit at '+hex(cpu.pc))


def reset(cpu):
    cpu.reg=[0x12340000+i*0x100 for i in range(16)];cpu.reg[15]=0x8c700800
    cpu.pr=0xdead0000;cpu.t=0


def guarded(cpu):
    for base,size in [(HEAP,HEAP_BYTES),(DEST,DIALOGUE_CAPACITY)]:
        a,p=cpu.area(base,size)
        assert a[:GUARD]==b'\xa5'*GUARD and a[p+size:]==b'\xa5'*GUARD


def selected_bytes(plain,record):
    p=record['english_offset'];return plain[p:p+record['english_bytes']]


def install(cpu,plain,member):
    a,p=cpu.area(HEAP,HEAP_BYTES);a[p:p+len(plain)]=plain
    b,q=cpu.area(SOURCE,member['original_bytes']);b[q:q+member['original_bytes']]=plain[:member['original_bytes']]
    cpu.write(HEAP+BANK_POINTER_OFFSET,HEAP+member['bank_offset'],4)


def format_case(cpu,plain,member,record,native=False,phases=False):
    reset(cpu);saved=cpu.reg[8:];cpu.fast_format=not native
    cpu.expected=selected_bytes(plain,record);cpu.expected_pointer=HEAP+record['english_offset']
    cpu.expected_width=127 if record.get('word_wrapped') else 30
    cpu.reg[4:8]=[DEST,SOURCE+record['source_offset'],30,3]
    cpu.write(cpu.reg[15],DIALOGUE_CAPACITY-1,4)
    a,p=cpu.area(DEST,DIALOGUE_CAPACITY);a[p:p+DIALOGUE_CAPACITY]=b'\xa5'*DIALOGUE_CAPACITY
    if phases:
        cpu.write(0x8c1dbe24,SOURCE+record['source_offset']-2,4)
        steps=run(cpu,BASE+0x6cfb2,BASE+0x6cfe6)
        assert cpu.read(BASE+0x8b1ec,4)==record['source_bytes']+1
        steps+=run(cpu,BASE+0x6d4b8,BASE+0x6d4c2)
        assert cpu.reg[0]==0x6000|(record['source_bytes']+2)
        cpu.write(cpu.reg[15],cpu.reg[0],4)
        steps+=run(cpu,BASE+0x2f35c,BASE+0x2f382)
        end=record['source_offset']+record['source_bytes']
        assert end<member['original_bytes']
        assert cpu.read(0x8c1dbe24,4)==SOURCE+end+1
        assert cpu.read(0x8c1dbe70,4)==plain[end]
    else:
        steps=run(cpu,FORMATTER)
        assert cpu.reg[0]==record['source_bytes']
    assert cpu.reg[8:]==saved
    if native:
        end=0
        while True:
            value=a[p+end];end+=1
            if value==0xff:break
            if value==0xfc:end+=4 if a[p+end+1]==0x3c else 2
            elif 0xf0<=value<=0xfa:end+=1
            assert end<DIALOGUE_CAPACITY
        output=bytes(a[p:p+end]);assert meaningful_tokens(output)==meaningful_tokens(cpu.expected)
        assert a[p+end:p+DIALOGUE_CAPACITY]==b'\xa5'*(DIALOGUE_CAPACITY-end)
    else:end=0
    guarded(cpu)
    return steps,end


def fallback_case(cpu,pointer,payload):
    reset(cpu);saved=cpu.reg[8:];cpu.fast_format=True
    cpu.expected=payload;cpu.expected_pointer=pointer
    cpu.expected_width=30
    cpu.reg[4:8]=[DEST,pointer,30,3];cpu.write(cpu.reg[15],DIALOGUE_CAPACITY-1,4)
    steps=run(cpu,FORMATTER)
    assert cpu.reg[0]==len(payload) and cpu.reg[8:]==saved
    guarded(cpu)
    return steps


def main():
    global VERSION,FORMATTER
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.7','0.1.11','0.1.12','0.1.13','0.1.17','0.1.19','0.1.21'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    VERSION=args.version
    assert not args.write_report or args.verify
    out=ROOT/'work/output'/VERSION;report=json.loads((out/'text/scenario-component-report.json').read_text('utf-8'))
    archive=(out/'text/D_SCE.AFS').read_bytes();assert digest(archive)==report['archive_sha256']
    exe,patch=candidate_executable()
    if VERSION=='0.1.11':
        from build_genei_font import compose
        files,_,_,_=compose();exe=files['1ST_READ.BIN']
    elif VERSION in ('0.1.12','0.1.13'):
        from build_word_wrap_story import candidate_executable as wrap_executable
        exe,_=wrap_executable()
    elif VERSION=='0.1.17':
        from build_antialias_font import compose
        files,_,_,_=compose();exe=files['1ST_READ.BIN']
    elif VERSION=='0.1.19':
        from build_library_header_patch import compose
        files,_,_=compose();exe=files['1ST_READ.BIN']
    elif VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose,ENTRY
        files,_,_=compose();exe=files['1ST_READ.BIN'];FORMATTER=ENTRY
    assert (out/'1ST_READ.BIN').read_bytes()==exe
    for name,sha in report['working_file_sha256'].items():assert digest((ROOT/'work/translation/en/scenario'/name).read_bytes())==sha
    print('Plan:',report['english_commands'],'native lookups;353 held-command fallback cases;87 native English formatting/VM-advance witnesses; representative native PRS loads, allocation and stale-bank checks.',flush=True)
    if not args.verify:print('DRY RUN: no native test executed or report written.');return
    cpu=fresh(exe,archive);saved=cpu.reg[8:];instructions=run(cpu,BASE+0x10352,BASE+0x10358)
    assert cpu.allocations==[HEAP_BYTES] and cpu.read(0x8c1dbf50,4)==SOURCE and cpu.reg[8:]==saved
    assert cpu.read(HEAP_POINTER,4)==HEAP
    members=report['members'];by_name={m['name']:m for m in members};plains={}
    for m in members:
        off=m['archive_offset'];wrapped=archive[off:off+m['packed_bytes']]
        plain,used=decompress(wrapped[20:]);assert digest(plain)==m['decoded_sha256'] and used==len(wrapped)-20
        original=(ROOT/'work/source/scenario'/m['name']).read_bytes()
        assert digest(original)==m['original_sha256'] and plain[:len(original)]==original
        plains[m['name']]=plain
    # Native loader witnesses cover maximum packed, decoded, original and
    # sector-read sizes, the five nontext members, and an ordinary opening.
    chosen={m['index']:m for key in ('packed_bytes','decoded_bytes','original_bytes') for m in [max(members,key=lambda m:m[key])]}
    for m in members:
        if not m['english_commands']:chosen[m['index']]=m
        if m.get('dynamic_PRS'):chosen[m['index']]=m
    chosen[1]=members[1];loader_steps=0
    for m in chosen.values():
        cpu=fresh(exe,archive);reset(cpu);saved=cpu.reg[8:];cpu.reg[4:6]=[m['index'],SOURCE]
        loader_steps+=run(cpu,BASE+0x78270)
        assert cpu.reg[0]==1 and cpu.reg[8:]==saved
        plain=plains[m['name']];a,p=cpu.area(HEAP,HEAP_BYTES)
        assert bytes(a[p:p+len(plain)])==plain
        assert a[p+len(plain):p+BANK_POINTER_OFFSET]==b'\xa5'*(BANK_POINTER_OFFSET-len(plain))
        assert cpu.read(HEAP+BANK_POINTER_OFFSET,4)==HEAP+m['bank_offset']
        assert cpu.flushes==[(SOURCE,m['original_bytes'])]
        assert cpu.copies==[(SOURCE,HEAP,m['original_bytes'])]
        b,q=cpu.area(SOURCE,m['original_bytes']);assert bytes(b[q:q+m['original_bytes']])==plain[:m['original_bytes']]
        assert bytes(b[HEAP_POINTER-BASE+4:])==exe[HEAP_POINTER-BASE+4:]
        assert cpu.reads==[(m['index'],HEAP+SCRIPT_CAPACITY,align(m['packed_bytes']))]
        assert a[p+SCRIPT_CAPACITY+align(m['packed_bytes']):p+HEAP_BYTES]==b'\xa5'*(SCRATCH_CAPACITY-align(m['packed_bytes']))
        guarded(cpu)
    print('Native decompression/load witnesses passed:',len(chosen),flush=True)
    cpu=fresh(exe,archive);cpu.file_failure=True;cpu.write(HEAP+BANK_POINTER_OFFSET,HEAP+100,4)
    reset(cpu);saved=cpu.reg[8:];cpu.reg[4:6]=[1,SOURCE];loader_steps+=run(cpu,BASE+0x78270)
    assert cpu.reg[0]==0 and cpu.read(HEAP+BANK_POINTER_OFFSET,4)==0 and cpu.reg[8:]==saved
    guarded(cpu)
    cpu=fresh(exe,archive);reset(cpu);saved=cpu.reg[8:];cpu.reg[4:6]=[447,SOURCE]
    cpu.write(HEAP+BANK_POINTER_OFFSET,HEAP+100,4);loader_steps+=run(cpu,BASE+0x78270)
    off,size=struct.unpack_from('<II',archive,8+447*8);a,p=cpu.area(SOURCE,size)
    assert bytes(a[p:p+size])==archive[off:off+size] and cpu.reg[0]==1 and cpu.reg[8:]==saved
    assert cpu.read(HEAP+BANK_POINTER_OFFSET,4)==0;guarded(cpu)
    cpu=fresh(exe,archive);lookup_steps=0;lookup_count=0;all_records={}
    for m in members:
        plain=plains[m['name']];install(cpu,plain,m)
        for record in m['commands']:
            steps,_=format_case(cpu,plain,m,record);lookup_steps+=steps;lookup_count+=1
            all_records[record['id']]=(m,record)
        if (m['index']+1)%50==0:print('Native lookups:',lookup_count,flush=True)
    assert lookup_count==report['english_commands']
    # Held commands must retain the original stream and get no English credit.
    blocks=json.loads((ROOT/'work/source/scenario-text/blocks.json').read_text('utf-8'))
    by_block={b['id']:b for b in blocks};held_ids=set()
    for path in (ROOT/'work/translation/en/scenario').glob('s_*.json'):
        if path.name.endswith('.en.json'):continue
        for row in json.loads(path.read_text('utf-8')):
            if row['en'] is None:held_ids.add(by_block[row['block_id']]['command_id'])
    first_pages=[b for b in blocks if not b['page_index'] and b['command_id'] in held_ids]
    fallback_steps=0
    for b in first_pages:
        plain=plains[b['member']];m=by_name[b['member']];install(cpu,plain,m)
        payload=plain[b['text_offset']:b['command_end_offset']]
        fallback_steps+=fallback_case(cpu,SOURCE+b['text_offset'],payload)
    assert len(first_pages)==report['held_commands']==353
    external=0x8c400000;cpu.regions.append((external,bytearray(b'\x01\xff')))
    fallback_steps+=fallback_case(cpu,external,b'\x01\xff')
    # A bank not yet loaded also follows the original formatter path.
    sample=members[1]['commands'][0];plain=plains[members[1]['name']];install(cpu,plain,members[1])
    cpu.write(HEAP+BANK_POINTER_OFFSET,0,4)
    original=plain[sample['source_offset']:sample['source_offset']+sample['source_bytes']]
    fallback_steps+=fallback_case(cpu,SOURCE+sample['source_offset'],original)
    prior=json.loads((ROOT/'work/output/0.1.6/scenario-insertion-audit.json').read_text('utf-8'))
    native=[];formatter_steps=0
    for witness in prior['native_cases']:
        m,record=all_records[witness['id']];plain=plains[m['name']]
        install(cpu,plain,m)
        steps,size=format_case(cpu,plain,m,record,native=True,phases=True);formatter_steps+=steps
        native.append({'id':record['id'],'original_consumed_bytes':record['source_bytes'],
                       'english_consumed_bytes':record['english_bytes'],'formatted_bytes':size,'SH4_instructions':steps})
    print('Native formatting, source counts and original next-opcode advancement passed:',len(native),flush=True)
    proof={'version':VERSION,'archive_sha256':digest(archive),'executable_sha256':digest(exe),
        'native_lookup_cases':lookup_count,'native_loader_cases':len(chosen),'failed_read_stale_bank_cases':1,
        'raw_filename_list_cases':1,'held_original_stream_cases':353,'other_fallback_cases':2,
        'native_formatter_VM_advance_cases':native,'maximum_formatted_bytes':max(r['formatted_bytes'] for r in native),
        'SH4_initialization_instructions':instructions,'SH4_loader_instructions':loader_steps,
        'SH4_lookup_instructions':lookup_steps,'SH4_formatter_VM_instructions':formatter_steps,
        'SH4_fallback_instructions':fallback_steps,
        'source_prefixes':'all 447 exact','original_script_base':hex(SOURCE),'guards_and_callee_saved_registers':'pass',
        'limits':['File I/O, malloc, memcpy and cache-maintenance implementations are stubbed',
                  'Lookups all execute native search; 87 formatter cases execute native output and original source-count/VM advance phases',
                  'No full-game memory, rendering, navigation, save/load or layout proof',
                  'Full VM text coverage, held passages and meaning review remain incomplete']}
    print(json.dumps({k:v for k,v in proof.items() if k!='native_formatter_VM_advance_cases'},indent=2))
    if args.write_report:(out/'scenario-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
