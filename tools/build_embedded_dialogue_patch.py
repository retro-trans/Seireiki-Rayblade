"""Add an address-preserving English lookup for embedded VM dialogue. Dry first.

Uses verified zero padding after existing story helpers. Original command
addresses/bytes and the existing story lookup remain intact. No new allocation.
"""
import argparse,json,struct
from prepare_embedded_dialogue import ROOT,DEST,extract,digest
from build_scenario_patch import BASE,INIT,LOADER,FORMATTER,init_code,loader_code,formatter_code,call,prologue,epilogue
from build_word_wrap_story import BANK_MAGIC,PACK_MAGIC
from scenario_word_wrap import wrap,INLINE_FC,font_bytes
from english_text_codec import encode
from sh4_asm import Assembler

VERSION='0.1.21';PRIOR='0.1.20'
ENTRY=BASE+0x8440;TABLE=BASE+0x84c0


def dispatcher():
    a=Assembler(ENTRY);a.lit(TABLE,0);a.imm(13,1)
    a.label('search');a.load('l',0,2);a.rr('cmp/eq',5,2);a.branch('bt','found')
    a.addi(12,0);a.addi(-1,1);a.rr('tst',1,1);a.branch('bf','search')
    # No matching embedded pointer: pass the original call/stack unchanged.
    a.lit(FORMATTER,0);a.emit(0x402b);a.emit(0x0009)
    a.label('found');prologue(a,[8]);a.addi(4,0);a.load('l',0,8);a.addi(4,0);a.load('l',0,5)
    a.imm(127,6);a.rr('mov',15,0);a.addi(8,0);a.load('l',0,0);a.push(0)
    call(a,0x8c07bc00);a.addi(4,15);a.rr('mov',8,0);epilogue(a,[8])
    code=a.pool_and_finish();assert ENTRY+len(code)<=TABLE
    return code


def compose():
    recipe=json.loads(DEST.read_text('utf-8'));expected,_=extract();assert recipe==expected
    base=ROOT/'work/output'/PRIOR;exe=(base/'1ST_READ.BIN').read_bytes();target=bytearray(exe);font=font_bytes(PRIOR)
    originals=[(INIT,init_code()),(LOADER,loader_code(pack_magic=PACK_MAGIC)),(FORMATTER,formatter_code(bank_magic=BANK_MAGIC,word_wrap=True))]
    for address,raw in originals:assert exe[address-BASE:address-BASE+len(raw)]==raw
    code=dispatcher();table_end=TABLE-BASE+13*12
    holes=[(table_end,0x8800),(0x8800+len(originals[1][1]),0x8c00)]
    assert not any(exe[ENTRY-BASE:0x8800]) and not any(exe[holes[1][0]:holes[1][1]])
    target[ENTRY-BASE:ENTRY-BASE+len(code)]=code;hole=0;cursor=holes[0][0];records=[];ranges=[(ENTRY-BASE,ENTRY-BASE+len(code)),(TABLE-BASE,table_end)]
    for i,row in enumerate(recipe['rows']):
        original=encode(row['en']);payload,stats=wrap(original,font,safe_fc=INLINE_FC)
        assert stats['wrapped'] and stats['forced_word_breaks']==0
        cursor=(cursor+3)//4*4
        if cursor+len(payload)>holes[hole][1]:hole+=1;cursor=holes[hole][0]
        assert cursor+len(payload)<=holes[hole][1]
        target[cursor:cursor+len(payload)]=payload;ranges.append((cursor,cursor+len(payload)))
        struct.pack_into('<III',target,TABLE-BASE+i*12,BASE+row['source_offset'],row['source_bytes'],BASE+cursor)
        source=exe[row['source_offset']:row['command_end']];assert digest(source)==row['source_sha256']
        records.append({k:row[k] for k in ('id','command_offset','source_offset','source_bytes','command_end','source_sha256','story_draft_block','draft_sha256')}|{'english_offset':cursor,'english_bytes':len(payload),'english_sha256':digest(payload),'automatic_breaks':stats['automatic_breaks']})
        cursor+=len(payload)
    assert struct.unpack_from('<I',exe,0x6d0a8)[0]==FORMATTER
    struct.pack_into('<I',target,0x6d0a8,ENTRY);ranges.append((0x6d0a8,0x6d0ac))
    for address,raw in originals:assert target[address-BASE:address-BASE+len(raw)]==raw
    for row in recipe['rows']:assert target[row['command_offset']:row['command_end']]==exe[row['command_offset']:row['command_end']]
    allowed=set(i for lo,hi in ranges for i in range(lo,hi));assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(exe,target)))
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    files.update({'text/'+p.name:p.read_bytes() for p in (base/'text').iterdir() if p.is_file()})
    files.pop('english-disc-report.json',None);files.pop('READ-ME.txt',None);files['1ST_READ.BIN']=bytes(target)
    report={'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(exe),'executable_sha256':digest(target),'recipe_sha256':digest(DEST.read_bytes()),'commands':13,'dispatcher_address':hex(ENTRY),'dispatcher_bytes':len(code),'table_address':hex(TABLE),'english_payload_bytes':sum(r['english_bytes'] for r in records),'changed_bytes':sum(a!=b for a,b in zip(exe,target)),'allowed_ranges':[[hex(lo),hex(hi)] for lo,hi in ranges],
        'source_commands_and_branches':'byte-exact at original addresses','story_helpers_and_all_allocations':'unchanged','records':records,'pending':['Native embedded lookup/formatter/VM advance and fallback checks','Fresh native regressions for changed executable','Disc packaging and live embedded dialogue check'],'story_library_draft_credit':0}
    m=json.loads(files['font4x-patch.json']);m.update(version=VERSION,previous_build=PRIOR,status='Embedded-dialogue English candidate; native checks and packaging pending');m['files']['1ST_READ.BIN']['target_sha256']=digest(target)
    m['embedded_dialogue']={k:v for k,v in report.items() if k!='records'};m['scenario']['executable_sha256']=digest(target)
    m['native_proof_reuse']={'source_build':PRIOR,'scope':'All archives/font/text payloads byte-exact; existing story helpers unchanged; fresh native suites required for the new formatter dispatch'}
    files['font4x-patch.json']=json.dumps(m,indent=2).encode();files['embedded-dialogue-component.json']=json.dumps(report,indent=2).encode()
    return files,m,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args();files,_,report=compose();print(json.dumps({k:v for k,v in report.items() if k not in ('records','allowed_ranges')},indent=2))
    if not args.write:print('DRY RUN: no candidate written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    print('Wrote embedded-dialogue candidate:',out)


if __name__=='__main__':main()
