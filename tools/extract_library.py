"""Extract the character/mech library from WIN00.AFS/D_PAPER.BIN.

Preserves profile metadata, conditional unlock IDs, raw bytes, and hard line
boundaries. Conditional skip lengths include their own two-byte length field.
Default is dry run; original archives are never modified.
"""
import argparse
import json
import struct
from collections import Counter
from build_font_patch import ROOT
from rayblade_codec import decompress
from rayblade_text import TextCodec,relative_target


def paper_source():
    archive=(ROOT/'work/source/disc/WIN00.AFS').read_bytes()
    off,size=struct.unpack_from('<II',archive,8+52*8)
    return decompress(archive[off:off+size])[0]


def text_span(codec,data,start,end):
    result=codec.decode(data[start:end]+b'\xff')
    if result['bytes_consumed']!=end-start+1:raise ValueError('Unexpected terminator inside library span')
    result['raw_hex']=data[start:end].hex();result['bytes_consumed']=end-start;result['terminator']=None
    result['tokens']=result['tokens'][:-1]
    return result


def sections(codec,data,start):
    output=[]
    def scan(pos,end=None,conditions=()):
        begin=pos
        while pos<len(data) and (end is None or pos<end):
            b=data[pos]
            if b in (0xfc,0xff):
                if begin<pos:
                    row=text_span(codec,data,begin,pos)
                    row.update(text_offset=begin,conditions=list(conditions));output.append(row)
                if b==0xff:
                    if end is not None:raise ValueError('Terminator inside conditional payload')
                    return pos+1
                flag,skip=struct.unpack_from('<HH',data,pos+1)
                finish=pos+3+skip
                if skip<2 or finish>len(data) or (end is not None and finish>end):raise ValueError('Invalid conditional span')
                scan(pos+5,finish,conditions+(flag,))
                pos=finish;begin=pos;continue
            pos+=2 if 0xf0<=b<=0xfa else 1
        if end is None:raise ValueError('Unterminated library record')
        if begin<pos:
            row=text_span(codec,data,begin,pos);row.update(text_offset=begin,conditions=list(conditions));output.append(row)
        return pos
    end=scan(start)
    return output,end


def extract():
    data=paper_source();codec=TextCodec();entries=[];lines=[]
    names=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    name_map={(r['group'],r['index']):r for r in names}
    assert struct.unpack_from('<I',data)[0]==416*4
    for index in range(416):
        kind='character' if index<160 else 'mech';number=index if index<160 else index-160
        pointer=index*4;target=relative_target(data,pointer);header_size=6 if kind=='character' else 5
        parts,end=sections(codec,data,target+header_size)
        name=name_map.get((11 if kind=='character' else 3,number),{}).get('text')
        entity_id='{}.{:03d}'.format(kind,number)
        name_note=None;raw_name=name
        if kind=='character' and number==94:
            name='イーファ・ラニアード・メスティナ';entity_id='character.ipha'
            name_note='Profile identifies deceased queen, mother of Lodis/Celica/Tix; raw name index labels Growster. See profile 93 for her name.'
        elif kind=='character' and number in (101,102):
            name=name_map[(11,102)]['text'];entity_id='character.102'
            name_note='Shared record describes Lenis, younger twin of Lyle; pointer 101 is not a Grauzer biography.'
        elif kind=='character' and number==135:
            name=name_map[(11,91)]['text'];entity_id='character.091'
            name_note='Raw record is byte-identical to profile 91, Garna; name slot 135 is blank.'
        entry={'id':'library.{}.{:03d}'.format(kind,number),'kind':kind,'index':number,
            'source_member':'WIN00.AFS:52:D_PAPER.BIN','pointer_offset':pointer,'record_offset':target,
            'header_hex':data[target:target+header_size].hex(),'source_name':name,
            'raw_name_table_label':raw_name,'entity_id':entity_id,'identity_note':name_note,
            'raw_hex':data[target:end].hex(),'sections':parts}
        if kind=='character':entry['header_bytes']=list(data[target:target+6])
        else:entry['header_fields_raw']=list(struct.unpack_from('<HHB',data,target))
        entries.append(entry)
    groups={}
    for entry in entries:groups.setdefault((entry['kind'],entry['record_offset']),[]).append(entry)
    for variants in groups.values():
        def preferred(e):
            name=e['source_name'] or ''
            return (not (name and set(name)!={'ー'} and e['index']>0),e['index'])
        canonical=min(variants,key=preferred)
        for entry in variants:entry['canonical_id']=canonical['id']
        canonical['aliases']=[e['id'] for e in variants if e is not canonical]
        for section_number,section in enumerate(canonical['sections']):
            for line_number,text in enumerate(section['text'].split('<NL>')):
                lines.append({'id':canonical['id']+'.s{:02d}.l{:02d}'.format(section_number,line_number),
                    'entry_id':canonical['id'],'source_name':canonical['source_name'],'conditions':section['conditions'],
                    'ja':text,'en':None,'status':'untranslated',
                    'ends_with_newline':line_number<len(section['text'].split('<NL>'))-1})
    return data,entries,lines


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    data,entries,lines=extract()
    nonempty=[v for v in entries if v['sections']]
    unique={(e['kind'],e['record_offset']) for e in nonempty}
    print('Library: {} pointers; {} nonempty references; {} unique nonempty records; {} physical text rows.'.format(len(entries),len(nonempty),len(unique),len(lines)))
    print('Kinds:',dict(Counter(k for k,_ in unique)))
    print('First profile sample:',json.dumps(entries[1]['sections'][0]['text'][:230],ensure_ascii=True))
    print('First profile condition flags:',[s['conditions'] for s in entries[1]['sections']])
    if not args.write:print('DRY RUN: no source or translation files written');return
    out=ROOT/'work/source/library';out.mkdir(parents=True,exist_ok=True)
    (out/'D_PAPER.dec.bin').write_bytes(data)
    (out/'entries.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'rows.json').write_text(json.dumps(lines,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote local library source; no translation rows marked complete')


if __name__=='__main__':main()
