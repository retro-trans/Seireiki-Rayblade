"""Audit complete English command streams before designing a scenario hook.

Dry run by default. Does not modify game binaries or translation rows. Native
formatter witnesses establish stream/ABI behavior, not pixel fit or VM coverage.
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from build_font_patch import ROOT
from english_text_codec import encode, decode
from prepare_scenario_translation import fingerprint
from test_scenario_pages import native_format


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def command_streams():
    directory=ROOT/'work/source/scenario-text'
    blocks=json.loads((directory/'blocks.json').read_text('utf-8'))
    sources=json.loads((directory/'rows.json').read_text('utf-8'))
    source_by_id={r['id']:r for r in sources}
    working=[];working_hashes={}
    for path in sorted((ROOT/'work/translation/en/scenario').glob('s_*.json')):
        if path.name.endswith('.en.json'):continue
        raw=path.read_bytes();working_hashes[path.name]=digest(raw)
        working.extend(json.loads(raw))
    assert [r['id'] for r in working]==[r['id'] for r in sources]
    by_block=defaultdict(list);groups=defaultdict(list);files={}
    for row in working:by_block[row['block_id']].append(row)
    for block in blocks:groups[block['command_id']].append(block)
    complete=[];held=[]
    for command,pages in groups.items():
        first=pages[0];member=first['member']
        if member not in files:files[member]=(ROOT/'work/source/scenario'/member).read_bytes()
        data=files[member];parts=[];held_ids=[];rows=[];mode=False
        for index,page in enumerate(pages):
            assert page['page_index']==index and page['page_count']==len(pages)
            assert page['ascii_mode_at_start']==mode
            assert data[page['text_offset']:page['end_offset']]==bytes.fromhex(page['raw_hex'])
            assert digest(bytes.fromhex(page['raw_hex']))==page['source_sha256']
            assert page['terminator']==(0xff if index==len(pages)-1 else 0xfe)
            assert page['text_offset']==(first['command_offset']+3 if not index else pages[index-1]['end_offset'])
            selected=by_block[page['id']];rows.extend(selected)
            assert ''.join(r['ja']+('<NL>' if r['ends_with_newline'] else '') for r in selected)==page['ja']
            for row in selected:
                source=source_by_id[row['id']]
                assert row['source_sha256']==fingerprint(source,page['source_sha256'])
                assert row['block_source_sha256']==page['source_sha256']
                assert row['ends_with_newline']==source['ends_with_newline']
                if row['en'] is None:
                    assert row['status']=='held' and row['decisions'].strip()
                    held_ids.append(row['id'])
                else:
                    assert bool(source['ja'])==bool(row['en'])
                    assert '\n' not in row['en'] and '\r' not in row['en']
                    assert re.findall(r'<[^>]+>',source['ja'])==re.findall(r'<[^>]+>',row['en'])
            if not any(r['en'] is None for r in selected):
                text=''.join(r['en']+('<NL>' if r['ends_with_newline'] else '') for r in selected)
                piece=encode(text,page['terminator'],ascii_mode=mode)
                assert decode(piece,ascii_mode=mode)==(text,page['terminator'])
                parts.append(piece)
            # The preserved source controls determine mode even for held pages.
            tags=re.findall(r'<ASCII:(ON|OFF)>',page['ja'])
            if tags:mode=tags[-1]=='ON'
            assert mode==page['ascii_mode_at_end']
        start=first['command_offset'];end=pages[-1]['end_offset']
        assert data[start:start+3]==bytes((0x8a,0x06,first['style']))
        assert end==first['command_end_offset']
        record={'id':command,'member':member,'command_offset':start,
                'source_payload_bytes':end-start-3,'source_command_end':end,
                'source_payload_sha256':digest(data[start+3:end]),
                'style':first['style'],'pages':len(pages),'physical_rows':len(rows)}
        if held_ids:
            held.append({**record,'held_rows':held_ids,
                'drafted_rows_in_same_command':sum(bool(r['en']) for r in rows)})
        else:
            payload=b''.join(parts)
            assert len(parts)==len(pages) and payload[-1]==0xff
            complete.append(({**record,'english_payload_bytes':len(payload),
                'english_payload_sha256':digest(payload)},payload))
    return complete,held,working_hashes,{m:digest(raw) for m,raw in files.items()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify-native',action='store_true')
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    complete,held,working_hashes,source_hashes=command_streams()
    largest=sorted(complete,key=lambda p:(-len(p[1]),p[0]['id']))
    # Longest streams and a longest witness for each style, continuation count,
    # and ASCII/FC control pattern; IDs are stable and samples contain no prose.
    chosen={r['id']:(r,p) for r,p in largest[:24]}
    for record,payload in largest:
        if len(payload)>1023:chosen[record['id']]=(record,payload)
    features={}
    for record,payload in largest:
        tags=[];pos=0
        while pos<len(payload):
            value=payload[pos];pos+=1
            if value==0xfc:
                tags.append('FC:'+payload[pos:pos+2].hex())
                pos+=4 if payload[pos+1]==0x3c else 2
            elif 0xf0<=value<=0xfa:pos+=1
            elif value==0xfb:tags.append('ASCII toggle')
        for feature in [('style',record['style']),('pages',record['pages'])]+[('control',t) for t in tags]:
            features.setdefault(feature,(record,payload))
    for record,payload in features.values():chosen[record['id']]=(record,payload)
    maximum=max(len(p) for _,p in complete)
    # Formatter may insert row/page controls. Use a generous research capacity;
    # actual required output is measured below, never inferred from input size.
    capacity=max(4096,4*maximum+256);native=[]
    exe=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    if args.verify_native:
        for index,(record,payload) in enumerate(chosen.values()):
            output,instructions=native_format(exe,payload,limit=capacity-1,capacity=capacity)
            native.append({'id':record['id'],'input_bytes':len(payload),
                'output_bytes':len(output),'output_sha256':digest(output),
                'SH4_instructions':instructions})
            if (index+1)%25==0:print('Native formatter witnesses:',index+1,'/',len(chosen),flush=True)
    report={'kind':'scenario English stream and native formatter insertion audit; no game patch',
        'candidate_commands':len(complete)+len(held),'complete_commands':len(complete),
        'held_commands':len(held),'held_rows':sum(len(r['held_rows']) for r in held),
        'drafted_rows_sharing_held_commands':sum(r['drafted_rows_in_same_command'] for r in held),
        'english_payload_bytes_total':sum(len(p) for _,p in complete),
        'maximum_english_payload_bytes':maximum,
        'commands_over_original_formatter_limit':sum(len(p)>1023 for _,p in complete),
        'largest_commands':[r for r,_ in largest[:12]],
        'styles':dict(Counter(r['style'] for r,_ in complete)),
        'selected_native_witnesses':len(chosen),'native_cases':native,
        'native_SH4_instructions':sum(r['SH4_instructions'] for r in native),
        'maximum_native_output_bytes':max((r['output_bytes'] for r in native),default=None),
        'native_outputs_over_original_allocation':sum(r['output_bytes']>1024 for r in native),
        'research_destination_capacity':capacity,'research_limit_argument':capacity-1,
        'source_executable_sha256':digest(exe),
        'source_member_sha256':source_hashes,'working_file_sha256':working_hashes,
        'checks':['Source spans, fingerprints, original command boundaries and physical row order exact',
                  'All complete pages encode/decode exactly with original FC controls, FE ends and ASCII state',
                  'Held commands excluded completely; no replacement prose or draft credit'],
        'limits':['Candidate signature extraction is not full VM coverage',
                  'Native witnesses use research destination/limit, not a patched game allocation',
                  'No source-pointer mapping, runtime bank ownership, layout or gameplay proof',
                  'Native tests preserve glyph/control bytes but permit native FD/FE reflow',
                  'Dynamic FC text expansion is handled later by the renderer and is not measured here']}
    preview={k:v for k,v in report.items() if k not in ('source_member_sha256','working_file_sha256','native_cases')}
    print(json.dumps(preview,indent=2),flush=True)
    if args.write:
        out=ROOT/'work/output/0.1.6/scenario-insertion-audit.json'
        out.write_text(json.dumps(report,indent=2)+'\n','utf-8');print('Wrote',out)
    else:print('DRY RUN: no files written.')


if __name__=='__main__':main()
