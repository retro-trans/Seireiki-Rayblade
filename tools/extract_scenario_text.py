"""Extract candidate inline text commands, retaining relocation evidence.

Recognizes 8A 06 followed by the five observed immediate style bytes. This is
not a complete VM decoder: unrecognized styles and anomalous inline controls
are explicit review items, and command coverage remains unproven. Dry run by
default. Source and per-glyph tokens are not committed to version control.
FE ends a display page; scan continuation pages through the final FF.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from build_font_patch import ROOT
from rayblade_text import TextCodec
from audit_scenario_markers import reviewed_marker


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--member',help='One filename, e.g. s_001.bin; default all')
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    directory=ROOT/'work/source/scenario';codec=TextCodec();blocks=[];rows=[];issues=[];resolved=[];counts=Counter();styles=Counter()
    paths=sorted(directory.glob(args.member or '*.bin'))
    if not paths:raise ValueError('No scenario members selected')
    for file_number,path in enumerate(paths):
        data=path.read_bytes();text_end=0
        for match in re.finditer(b'\x8a\x06',data):
            offset=match.start()
            if offset<text_end:counts['marker_inside_text']+=1;continue
            resolution=reviewed_marker(path.name,data,offset)
            if resolution:
                resolved.append({k:resolution[k] for k in ('member','marker_offset','command_start','command_end','classification','command_sha256')});continue
            if offset+3>len(data):issues.append({'member':path.name,'offset':offset,'kind':'truncated_command'});continue
            style=data[offset+2]
            if style not in (0,0x40,0x80,0xa0,0xc0):
                issues.append({'member':path.name,'offset':offset,'kind':'unrecognized_style','style':style,
                               'raw_context_hex':data[max(0,offset-8):offset+24].hex()});continue
            # FE finishes a display page, not the enclosing inline text
            # command. Continuation prose immediately follows without 8A 06.
            # Keep legacy first-page IDs/hashes so existing drafts survive.
            pages=[];page_start=offset+3;ascii_mode=False
            try:
                while True:
                    decoded=codec.decode(data,page_start,ascii_mode=ascii_mode)
                    pages.append((page_start,ascii_mode,decoded))
                    page_start+=decoded['bytes_consumed']
                    ascii_mode=decoded['ascii_mode_at_end']
                    if decoded['terminator']==0xff:break
            except ValueError as exc:issues.append({'member':path.name,'offset':offset,'kind':'decode_error','error':str(exc)});continue
            text_end=page_start;styles[style]+=1;counts['commands']+=1
            command_id='scenario.{}.o{:05x}'.format(path.stem,offset)
            for page_index,(page_start,ascii_mode,decoded) in enumerate(pages):
                block_id=command_id+('.p{:02d}'.format(page_index) if page_index else '')
                block={'id':block_id,'member':path.name,'command_id':command_id,'page_index':page_index,
                       'page_count':len(pages),'command_offset':offset,'text_offset':page_start,
                       'end_offset':page_start+decoded['bytes_consumed'],'command_end_offset':text_end,
                       'ascii_mode_at_start':ascii_mode,'ascii_mode_at_end':decoded['ascii_mode_at_end'],
                       'style':style,'terminator':decoded['terminator'],
                       'source_sha256':hashlib.sha256(bytes.fromhex(decoded['raw_hex'])).hexdigest(),
                       'raw_hex':decoded['raw_hex'],'ja':decoded['text'],'unknown_glyphs':decoded['unknown_glyphs'],
                       'controls':[t for t in decoded['tokens'] if t['kind'] in ('control','mode')],
                       'validation':'candidate inline text display page; full VM coverage pending'}
                if decoded['unknown_glyphs']:
                    issues.append({'member':path.name,'offset':offset,'kind':'unresolved_glyph_or_inline_control',
                                   'glyph_ids':decoded['unknown_glyphs'],'block_id':block_id})
                blocks.append(block)
                lines=decoded['text'].split('<NL>')
                for line_number,line in enumerate(lines):
                    rows.append({'id':block_id+'.l{:02d}'.format(line_number),'block_id':block_id,'member':path.name,
                                 'line_index':line_number,'ja':line,'en':None,'status':'untranslated',
                                 'ends_with_newline':line_number<len(lines)-1})
        if (file_number+1)%50==0:print('Read {}/{} members; {} text blocks.'.format(file_number+1,len(paths),len(blocks)),flush=True)
    # Exact repetitions are only reuse candidates; surrounding scene context
    # must be reviewed before a shared translation is accepted.
    groups={}
    for b in blocks:groups.setdefault(b['source_sha256'],[]).append(b['id'])
    repeated=[{'source_sha256':key,'block_ids':ids,'status':'context review required before reuse'} for key,ids in groups.items() if len(ids)>1]
    summary={'format':2,'coverage_status':'candidate command extraction with FE continuation pages; full VM/opcode coverage not established',
             'members_examined':len(paths),'blocks':len(blocks),'physical_rows':len(rows),'unique_text_payloads':len(groups),
             'inline_commands':counts['commands'],'continuation_pages':len(blocks)-counts['commands'],
             'styles':dict(styles),'markers_inside_text':counts['marker_inside_text'],'issues':issues,
             'native_resolved_operand_markers':resolved,
             'repeated_payload_groups':len(repeated)}
    prior_dir=ROOT/'work/source/scenario-text'
    if not args.member and (prior_dir/'summary.json').exists():
        prior_summary=json.loads((prior_dir/'summary.json').read_text(encoding='utf-8'))
        if 'format1_migration' in prior_summary:summary['format1_migration']=prior_summary['format1_migration']
        if prior_summary.get('format')==1:
            prior_blocks=json.loads((prior_dir/'blocks.json').read_text(encoding='utf-8'))
            now={b['id']:b for b in blocks}
            for old in prior_blocks:
                current=now.get(old['id'])
                fields=('raw_hex','ja','source_sha256','command_offset','text_offset','end_offset','terminator')
                if current is None or any(current[k]!=old[k] for k in fields):
                    raise ValueError('First-page identity changed during coverage migration: '+old['id'])
            prior_rows=json.loads((prior_dir/'rows.json').read_text(encoding='utf-8'))
            current_rows={r['id']:r for r in rows}
            for old in prior_rows:
                if current_rows.get(old['id'])!=old:
                    raise ValueError('Existing source row changed during coverage migration: '+old['id'])
            summary['format1_migration']={'unchanged_existing_blocks':len(prior_blocks),
                'unchanged_existing_rows':len(prior_rows),'added_pages':len(blocks)-len(prior_blocks),
                'added_rows':len(rows)-len(prior_rows)}
        current_rows={r['id']:r for r in rows};now={b['id']:b for b in blocks};preserved=0
        for draft_path in (ROOT/'work/translation/en/scenario').glob('s_*.json'):
            if draft_path.name.endswith('.en.json'):continue
            for old in json.loads(draft_path.read_text(encoding='utf-8')):
                if old.get('en') is None:continue
                current=current_rows.get(old['id'])
                if current is None or current['ja']!=old['ja'] or current['ends_with_newline']!=old['ends_with_newline'] or now[current['block_id']]['source_sha256']!=old['block_source_sha256']:
                    raise ValueError('Prepared translation source changed: '+old['id'])
                preserved+=1
        summary['prepared_rows_with_unchanged_source']=preserved
    print(json.dumps(summary),flush=True)
    print('First blocks:',json.dumps([{'id':b['id'],'preview':b['ja'][:100]} for b in blocks[:3]],ensure_ascii=True),flush=True)
    if not args.write:print('DRY RUN: no scenario text written');return
    out=ROOT/'work/source/scenario-text'
    if args.member:out=out/paths[0].stem
    out.mkdir(parents=True,exist_ok=True)
    for name,value in [('blocks.json',blocks),('rows.json',rows),('reuse-candidates.json',repeated),('summary.json',summary)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote local candidate text and review evidence. No script marked translated.')


if __name__=='__main__':main()
