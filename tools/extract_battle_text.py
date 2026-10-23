"""Parse the native D_BMESS selection graph, preserving non-text operands.

Root u32 pointers and the twelve u16 category pointers are self-relative.
Two weapon-override lists follow the category table. Conditional and random
selection controls are instructions, not prose. All reachable token boundaries
and original bytes are retained. Dry run by default; source prose stays local.
"""
import argparse
import hashlib
import json
import struct
from collections import Counter,defaultdict
from build_font_patch import ROOT
from rayblade_codec import decompress
from rayblade_text import TextCodec,relative_target


def digest(data):return hashlib.sha256(data).hexdigest()


def parse_record(data,base,end,extra_starts=()):
    def word(pos):
        if not base<=pos<=end-2:raise ValueError('Word outside record at '+hex(pos))
        return struct.unpack_from('<H',data,pos)[0]
    categories=[{'category':i,'pointer_offset':base+i*2,'target':base+i*2+word(base+i*2)} for i in range(12)]
    pos=base+24;overrides=[]
    for side in range(2):
        entries=[];start=pos
        while word(pos)!=0xffff:
            if pos+3>end:raise ValueError('Truncated weapon override')
            entries.append({'pointer_offset':pos,'target':pos+word(pos),'weapon_id':data[pos+2]})
            pos+=3
        pos+=2;overrides.append({'index':side,'offset':start,'end_offset':pos,'entries':entries})
    header_end=pos
    starts={c['target'] for c in categories}
    starts.update(e['target'] for table in overrides for e in table['entries'])
    if any(not header_end<=p<end for p in starts):raise ValueError('Entry target outside record body')
    starts.update(extra_starts)
    nodes={};owner={};pending=list(starts)
    while pending:
        pos=pending.pop()
        if pos in nodes:continue
        if not header_end<=pos<end:raise ValueError('Instruction outside record at '+hex(pos))
        value=data[pos];node={'offset':pos}
        if value==0xff:
            node.update(kind='end',size=1,edges=[])
        elif value==0xfc:
            if pos+3>end:raise ValueError('Truncated FC')
            parameter,op=data[pos+1:pos+3]
            if 0x30<=op<=0x37:
                jump=pos+3+word(pos+3)
                node.update(kind='condition',size=5,flag=((op&3)<<8)|parameter,
                            continue_when_set=op>=0x34,fallthrough=pos+5,jump=jump,edges=[pos+5,jump])
            elif op==0x3f:
                field=pos+3;choices=[]
                while word(field)!=0xffff:
                    choices.append({'pointer_offset':field,'target':field+word(field)})
                    field+=2
                    if len(choices)>64:raise ValueError('Random table exceeds native limit')
                node.update(kind='random',size=field+2-pos,choices=choices,edges=[e['target'] for e in choices])
            else:
                size=5 if op==0x3c else 3
                node.update(kind='copy',size=size,edges=[pos+size],control_opcode=op)
        else:
            size=2 if 0xf0<=value<=0xfa else 1
            node.update(kind='copy',size=size,edges=[pos+size])
        finish=pos+node['size']
        if finish>end:raise ValueError('Instruction crosses record end')
        for byte in range(pos,finish):
            if byte in owner and owner[byte]!=pos:raise ValueError('Jump enters another instruction at '+hex(pos))
            owner[byte]=pos
        node['raw_hex']=data[pos:finish].hex();nodes[pos]=node;pending.extend(node['edges'])
    incoming=Counter(target for n in nodes.values() for target in n['edges'])
    spans=[];copy_owner={}
    for pos,node in sorted(nodes.items()):
        if node['kind']!='copy' or pos in copy_owner:continue
        begin=pos
        while True:
            copy_owner[pos]=begin;following=nodes[pos]['edges'][0]
            if nodes[following]['kind']!='copy' or incoming[following]!=1 or following in starts:break
            pos=following
        finish=pos+nodes[pos]['size'];raw=data[begin:finish]
        spans.append({'id':'battle.o{:05x}'.format(begin),'offset':begin,'end_offset':finish,
                      'source_sha256':digest(raw),'raw_hex':raw.hex(),'next_offset':following})
    uncovered=[];pos=header_end
    while pos<end:
        if pos in owner:pos+=1;continue
        begin=pos
        while pos<end and pos not in owner:pos+=1
        raw=data[begin:pos]
        uncovered.append({'offset':begin,'size':len(raw),'all_zero':not any(raw),'sha256':digest(raw),'raw_hex':raw.hex()})
    return {'offset':base,'end_offset':end,'header_end':header_end,'header_hex':data[base:header_end].hex(),
            'categories':categories,'weapon_overrides':overrides,'entry_targets':sorted(starts),
            'unreferenced_program_starts':list(extra_starts),
            'nodes':[nodes[p] for p in sorted(nodes)],'spans':spans,'uncovered_ranges':uncovered}


def extract():
    packed=(ROOT/'work/source/disc/D_BMESS.BIN').read_bytes();data,used=decompress(packed)
    if used!=len(packed):raise ValueError('Unconsumed compressed battle bytes')
    roots=[relative_target(data,n*4) for n in range(128)]
    if min(roots)!=512:raise ValueError('Unexpected root table boundary')
    ordered=sorted(set(roots));records=[];codec=TextCodec();rows=[];unknown=Counter();controls=Counter()
    for i,base in enumerate(ordered):
        end=ordered[i+1] if i+1<len(ordered) else len(data)
        record=parse_record(data,base,end)
        rooted_offsets={n['offset'] for n in record['nodes']}
        # Retain text that has no reference in the discovered selection graph.
        # FF followed by zero alignment bytes is padding, not an extra line.
        extra=[]
        for attempt in range(64):
            seeds=[]
            for gap in record['uncovered_ranges']:
                positions=[p for p in range(gap['offset'],gap['offset']+gap['size']) if data[p] not in (0,0xff)]
                if not positions:continue
                seed=positions[0]
                if data[seed]!=0xfc:raise ValueError('Unresolved unreferenced data at '+hex(seed))
                seeds.append(seed)
            if not seeds:break
            if set(seeds)&set(extra):raise ValueError('Unreferenced scan made no progress')
            extra.extend(seeds);record=parse_record(data,base,end,extra)
        else:raise ValueError('Unreferenced program discovery limit')
        record['root_indices']=[n for n,target in enumerate(roots) if target==base]
        # State flows through the graph. Different mode states at one span
        # would require an explicit contextual decode, never a guessed string.
        nodes={n['offset']:n for n in record['nodes']};modes=defaultdict(set)
        todo=[(p,False) for p in record['entry_targets']]
        while todo:
            pos,mode=todo.pop()
            if mode in modes[pos]:continue
            modes[pos].add(mode);node=nodes[pos]
            if node['kind']=='copy' and node['raw_hex']=='fb':mode=not mode
            todo.extend((target,mode) for target in node['edges'])
        for span in record['spans']:
            span['referenced_by_selection_graph']=span['offset'] in rooted_offsets
            states=modes[span['offset']]
            if len(states)!=1:raise ValueError('Ambiguous ASCII state at '+span['id'])
            mode=next(iter(states));span['ascii_mode_at_start']=mode
            raw=bytes.fromhex(span['raw_hex']);padded=raw+b'\xff';pos=0;pages=[]
            while pos<len(raw):
                decoded=codec.decode(padded,pos,ascii_mode=mode)
                consumed=decoded['bytes_consumed'];synthetic=pos+consumed>len(raw)
                pages.append({'page_index':len(pages),'text_offset':span['offset']+pos,
                              'ja':decoded['text'],'terminator':None if synthetic else decoded['terminator'],
                              'synthetic_bound_for_decode':synthetic,'unknown_glyphs':decoded['unknown_glyphs']})
                unknown.update(decoded['unknown_glyphs'])
                controls.update(t['text'] for t in decoded['tokens'] if t['kind'] in ('control','mode'))
                mode=decoded['ascii_mode_at_end'];pos+=consumed
            span['pages']=pages;span['ascii_mode_at_end']=mode
            for page in pages:
                lines=page['ja'].split('<NL>')
                for line,text in enumerate(lines):
                    rows.append({'id':span['id']+'.p{:02d}.l{:02d}'.format(page['page_index'],line),
                                 'span_id':span['id'],'record_offset':base,'root_indices':record['root_indices'],
                                 'page_index':page['page_index'],'line_index':line,'ja':text,'en':None,
                                 'status':'untranslated','ends_with_newline':line<len(lines)-1,
                                 'referenced_by_selection_graph':span['referenced_by_selection_graph'],
                                 'source_sha256':span['source_sha256']})
        records.append(record)
    kinds=Counter(n['kind'] for r in records for n in r['nodes'])
    gaps=[g for r in records for g in r['uncovered_ranges']]
    summary={'format':1,'version':'0.1.4','source_file':'D_BMESS.BIN','compressed_bytes':len(packed),
             'decoded_bytes':len(data),'compressed_sha256':digest(packed),'decoded_sha256':digest(data),
             'root_pointers':128,'physical_records':len(records),'category_pointers_per_record':12,
             'weapon_override_lists_per_record':2,'node_counts':dict(kinds),
             'text_spans':sum(len(r['spans']) for r in records),'physical_rows':len(rows),
             'distinct_text_payloads':len({s['source_sha256'] for r in records for s in r['spans']}),
             'nonempty_rows':sum(bool(r['ja']) for r in rows),'unknown_glyph_ids':dict(unknown),
             'copied_controls':dict(controls),'uncovered_ranges':len(gaps),
             'uncovered_nonzero_bytes':sum(b!=0 for g in gaps for b in bytes.fromhex(g['raw_hex'])),
             'uncovered_nonpadding_bytes':sum(b not in (0,0xff) for g in gaps for b in bytes.fromhex(g['raw_hex'])),
             'unreferenced_program_starts':sum(len(r['unreferenced_program_starts']) for r in records),
             'unreferenced_text_rows':sum(not r['referenced_by_selection_graph'] for r in rows),
             'root_records':[{'index':n,'pointer_offset':n*4,'target':target} for n,target in enumerate(roots)],
             'coverage_status':'structural parse of native selection graph; native loop verification tracked separately; combat-state selection and runtime checks pending',
             'identity_caution':'Root slots are battle-message indices. Do not assign D_NAMES character IDs without proving the runtime mapping.'}
    return data,records,rows,summary


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    data,records,rows,summary=extract()
    print('Battle messages: {} physical records, 12 category pointers and two weapon lists per record.'.format(len(records)))
    print('{} spans / {} rows; nodes {}; unknown glyph IDs {}.'.format(summary['text_spans'],len(rows),summary['node_counts'],summary['unknown_glyph_ids']))
    print('Uncovered ranges:',summary['uncovered_ranges'],'nonzero bytes:',summary['uncovered_nonzero_bytes'])
    print('Unreferenced programs/rows:',summary['unreferenced_program_starts'],summary['unreferenced_text_rows'],
          'uncovered bytes beyond FF/zero padding:',summary['uncovered_nonpadding_bytes'])
    print('Samples:',json.dumps([{k:r[k] for k in ('id','root_indices','ja')} for r in rows[:5]],ensure_ascii=True))
    if not args.write:print('DRY RUN: no battle source files written');return
    out=ROOT/'work/source/battle';out.mkdir(parents=True,exist_ok=True)
    (out/'D_BMESS.dec.bin').write_bytes(data)
    for name,value in [('records',records),('rows',rows),('summary',summary)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote ignored battle source and graph; original game files unchanged.')


if __name__=='__main__':main()
