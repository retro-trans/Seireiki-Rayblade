"""Relocate English battle text and every selection-graph pointer. Dry first.

Retains root aliases, category/weapon ordering, flags, random choices and
unreferenced programs. No dialogue is shortened to fit a source slot.
"""
import argparse,hashlib,json,re,struct
from collections import defaultdict
from build_font_patch import ROOT
from english_text_codec import encode,decode
from rayblade_codec import compress,decompress
from prepare_scenario_translation import fingerprint
from extract_battle_text import parse_record
from source_literals import checked_english_prose

VERSION='0.1.6'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def build(*, presentation_transform=None):
    directory=ROOT/'work/source/battle'
    summary=json.loads((directory/'summary.json').read_text('utf-8'))
    original=(directory/'D_BMESS.dec.bin').read_bytes()
    assert digest(original)==summary['decoded_sha256']
    source=json.loads((directory/'rows.json').read_text('utf-8'))
    working=json.loads((ROOT/'work/translation/en/battle/battle.json').read_text('utf-8'))
    assert [r['id'] for r in source]==[r['id'] for r in working]
    records=json.loads((directory/'records.json').read_text('utf-8'))
    by_span=defaultdict(list)
    for row,src in zip(working,source):
        assert row['ja']==src['ja'] and row['ends_with_newline']==src['ends_with_newline']
        assert row['source_sha256']==fingerprint(src,row['block_source_sha256'])
        assert not row['source_review_needed'] and row['en'] is not None
        assert bool(row['en'])==bool(src['ja'])
        checked_english_prose(src['ja'],row['en'])
        assert re.findall('<[^>]+>',src['ja'])==re.findall('<[^>]+>',row['en'])
        by_span[row['span_id']].append(row)
    encoded={};row_count=0
    for record in records:
        for span in record['spans']:
            assert digest(bytes.fromhex(span['raw_hex']))==span['source_sha256']
            assert original[span['offset']:span['end_offset']]==bytes.fromhex(span['raw_hex'])
            mode=span['ascii_mode_at_start'];parts=[]
            for page in span['pages']:
                selected=[r for r in by_span[span['id']] if r['page_index']==page['page_index']]
                assert ''.join(r['ja']+('<NL>' if r['ends_with_newline'] else '') for r in selected)==page['ja']
                text=''.join(r['en']+('<NL>' if r['ends_with_newline'] else '') for r in selected)
                end=page['terminator'] if page['terminator'] is not None else 0xff
                piece=encode(text,end,ascii_mode=mode)
                assert decode(piece,ascii_mode=mode)==(text,end)
                if page['terminator'] is None:piece=piece[:-1]
                parts.append(piece);row_count+=len(selected)
                tags=re.findall(r'<ASCII:(ON|OFF)>',text)
                if tags:mode=tags[-1]=='ON'
            assert mode==span['ascii_mode_at_end']
            encoded[span['offset']]=b''.join(parts)
            if presentation_transform is not None:
                encoded[span['offset']]=presentation_transform(encoded[span['offset']],span)
            assert encoded[span['offset']],'Empty replacement would remove a graph unit'
    assert row_count==len(working) and len(encoded)==5516
    output=bytearray(512);mapping={};relocations=[];span_report=[]
    for record in records:
        base=record['offset'];target=len(output);assert target%4==0
        header_end=record['header_end'];blob=bytearray(original[base:header_end])
        mapping[base]=target
        units=[(s['offset'],s['end_offset'],encoded[s['offset']],s) for s in record['spans']]
        units += [(n['offset'],n['offset']+n['size'],bytes.fromhex(n['raw_hex']),None)
                  for n in record['nodes'] if n['kind']!='copy']
        cursor=header_end
        for start,end,raw,span in sorted(units):
            assert cursor<=start
            gap=original[cursor:start];assert all(b in (0,0xff) for b in gap)
            blob.extend(gap);mapping[start]=target+len(blob);blob.extend(raw);cursor=end
            if span:span_report.append({'source_id':span['id'],'source_offset':start,
                'target_offset':mapping[start],'source_bytes':span['end_offset']-start,
                'target_bytes':len(raw),'target_sha256':digest(raw)})
        tail=original[cursor:record['end_offset']];assert all(b in (0,0xff) for b in tail)
        blob.extend(tail)
        while len(blob)%4:blob.append(0)
        output.extend(blob)
        relocations.append({'source_offset':base,'source_end':record['end_offset'],
            'target_offset':target,'target_end':len(output),'header_bytes':header_end-base,
            'root_indices':record['root_indices']})
    fixups=[]
    def pointer(old_field,new_field,target,bits,sentinel=False):
        value=mapping[target]-new_field
        limit=(1<<bits)-1
        if not 0<=value<=limit or (sentinel and value==limit):
            raise ValueError('Relocated pointer exceeds native range at '+hex(old_field))
        struct.pack_into('<H' if bits==16 else '<I',output,new_field,value)
        fixups.append({'source_field':old_field,'target_field':new_field,
                       'source_target':target,'target':mapping[target],'bits':bits})
    for root in summary['root_records']:
        pointer(root['index']*4,root['index']*4,root['target'],32)
    rebuilt=[]
    for old,location in zip(records,relocations):
        base=old['offset'];target=location['target_offset']
        fields=old['categories']+[e for t in old['weapon_overrides'] for e in t['entries']]
        for entry in fields:pointer(entry['pointer_offset'],target+entry['pointer_offset']-base,entry['target'],16,True)
        for node in old['nodes']:
            if node['kind']=='condition':pointer(node['offset']+3,mapping[node['offset']]+3,node['jump'],16)
            elif node['kind']=='random':
                for entry in node['choices']:
                    pointer(entry['pointer_offset'],mapping[node['offset']]+entry['pointer_offset']-node['offset'],entry['target'],16,True)
        extra=[mapping[p] for p in old['unreferenced_program_starts']]
        new=parse_record(output,target,location['target_end'],extra)
        assert len(new['spans'])==len(old['spans'])
        for a,b in zip(old['categories'],new['categories']):assert b['target']==mapping[a['target']]
        for a,b in zip(old['weapon_overrides'],new['weapon_overrides']):
            assert [e['weapon_id'] for e in a['entries']]==[e['weapon_id'] for e in b['entries']]
            assert [mapping[e['target']] for e in a['entries']]==[e['target'] for e in b['entries']]
        nodes={n['offset']:n for n in new['nodes'] if n['kind']!='copy'}
        for node in old['nodes']:
            if node['kind']=='copy':continue
            after=nodes[mapping[node['offset']]];assert after['kind']==node['kind']
            assert [mapping[p] for p in node['edges']]==after['edges']
            if node['kind'] in ('condition','random'):assert node['raw_hex'][:6]==after['raw_hex'][:6]
        spans={s['offset']:s for s in new['spans']}
        for span in old['spans']:
            after=spans[mapping[span['offset']]]
            assert bytes.fromhex(after['raw_hex'])==encoded[span['offset']]
            assert after['next_offset']==mapping[span['next_offset']]
        rebuilt.append(new)
    for root in summary['root_records']:
        field=root['index']*4;assert field+struct.unpack_from('<I',output,field)[0]==mapping[root['target']]
    # The game memcpy's a fixed 0x3000 bytes even for the final short record.
    # Serialize zero tail padding so that copy never reads undecompressed heap.
    serialized_size=len(output)
    readable_end=max(r['target_offset'] for r in relocations)+0x3000
    if len(output)<readable_end:output.extend(b'\0'*(readable_end-len(output)))
    packed=compress(output);assert decompress(packed)==(bytes(output),len(packed))
    sizes=[r['target_end']-r['target_offset'] for r in relocations]
    report={'version':VERSION,'source_file':'D_BMESS.BIN','stage':'relocated English component; game insertion pending',
        'source_decoded_sha256':digest(original),'output_sha256':digest(output),'compressed_sha256':digest(packed),
        'source_decoded_bytes':len(original),'output_decoded_bytes':len(output),'output_compressed_bytes':len(packed),
        'serialized_records_bytes':serialized_size,'copy_tail_padding_bytes':len(output)-serialized_size,
        'physical_records':len(records),'root_alias_slots':128,'translated_spans':len(encoded),
        'translated_physical_rows':len(working),'translated_nonempty_rows':sum(bool(r['en']) for r in working),
        'pointer_fixups':len(fixups),'maximum_record_bytes':max(sizes),
        'records_exceeding_native_0x3000_copy':[r for r,n in zip(relocations,sizes) if n>0x3000],
        'original_component_allocation_bytes':0x38000,'original_record_copy_bytes':0x3000,
        'selection_semantics':'categories, weapon IDs/order, flags, random choices, aliases and unreferenced programs retained',
        'validation':{'source_fingerprints':'pass','text_codec_roundtrip':'pass','PRS_roundtrip':'pass',
            'rebuilt_graph_edges':'pass','u16_u32_ranges':'pass','raw_nonpointer_controls':'unchanged'},
        'pending':['Native selection against all English paths','Component and per-side buffer capacity',
                   'Preceding combat-state selection and display layout','Game integration and gameplay',
                   'Independent meaning review'],
        'record_relocations':relocations,'span_relocations':span_report,'pointer_relocations':fixups}
    return bytes(output),packed,records,rebuilt,mapping,encoded,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    plain,packed,_,_,_,_,report=build()
    print(json.dumps({k:v for k,v in report.items() if k not in ['record_relocations','span_relocations','pointer_relocations']},indent=2))
    print('Sample span relocations:',json.dumps(report['span_relocations'][:3]))
    if not args.write:print('DRY RUN: no battle component written');return
    out=ROOT/'work/output'/VERSION/'text';out.mkdir(parents=True,exist_ok=True)
    (out/'D_BMESS.en.dec.bin').write_bytes(plain);(out/'D_BMESS.BIN').write_bytes(packed)
    (out/'battle-component-report.json').write_text(json.dumps(report,indent=2),'utf-8')
    print('Wrote relocated English battle component:',out)


if __name__=='__main__':main()
