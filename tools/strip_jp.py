"""Export English-only library/scenario rows for version control. Dry run by default.

Does not silently delete Japanese characters: rejects Japanese prose in selected
English fields. Scenario exports preserve exact source-verified opaque model
labels. Source prose, source names, and raw source bytes are excluded.
"""
import argparse
import hashlib
import json
import re
from build_font_patch import ROOT
from prepare_library_translation import fingerprint
from source_literals import checked_english_prose

EXPORT_VERSION=(ROOT/'VERSION').read_text('utf-8').strip() if (ROOT/'VERSION').exists() else '0.1.4'
EXPORT_STATUS='English draft export; current insertion and review status tracked separately in docs/translation-status.json'


def library_export(write):
    path=ROOT/'work/translation/en/library/library.json'
    rows=json.loads(path.read_text(encoding='utf-8'))
    source=json.loads((ROOT/'work/source/library/rows.json').read_text(encoding='utf-8'))
    if [r['id'] for r in rows]!=[r['id'] for r in source]:raise ValueError('Translation/source ID mismatch')
    allowed=('id','entry_id','conditions','en','status','ends_with_newline','source_sha256','review_notes')
    output=[]
    for row,original in zip(rows,source):
        if row['source_sha256']!=fingerprint(original):raise ValueError('Stale translation: '+row['id'])
        item={k:row[k] for k in allowed if k in row}
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',json.dumps(item,ensure_ascii=False)):
            raise ValueError('Japanese found in English export: '+row['id'])
        output.append(item)
    result={'format':1,'version':EXPORT_VERSION,'translation_status':EXPORT_STATUS,
            'source_corpus_sha256':hashlib.sha256(json.dumps([fingerprint(r) for r in source]).encode()).hexdigest(),
            'rows':output}
    result['review_batches']=[]
    for batch_path in sorted(path.parent.glob('batch-*.json')):
        batch=json.loads(batch_path.read_text(encoding='utf-8'))
        item={k:batch[k] for k in ('start','first_id','last_id','rows_examined','context','decisions','row_decisions') if k in batch}
        item['row_count']=len(batch['translations'])
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',json.dumps(item,ensure_ascii=False)):
            raise ValueError('Japanese in review notes: '+batch_path.name)
        result['review_batches'].append(item)
    count=sum(bool(r['en']) for r in rows);total=sum(bool(r['ja']) for r in rows)
    print('English-only export: {} / {} nonempty library rows drafted; {} structural empty rows.'.format(count,total,len(rows)-total))
    out=path.with_name('library.en.json')
    print('Sample:',json.dumps(output[:2]));print('Destination:',out)
    if not write:print('DRY RUN: no library export written');return
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote English-only export')


def scenario_exports(write):
    from prepare_scenario_translation import fingerprint as scenario_fingerprint
    directory=ROOT/'work/translation/en/scenario'
    if not directory.exists():return
    source_dir=ROOT/'work/source/scenario-text'
    source={r['id']:r for r in json.loads((source_dir/'rows.json').read_text(encoding='utf-8'))}
    blocks={r['id']:r for r in json.loads((source_dir/'blocks.json').read_text(encoding='utf-8'))}
    allowed=('id','block_id','member','line_index','en','status','ends_with_newline','source_sha256',
             'block_source_sha256','source_command_id','source_page_index',
             'speaker_entity_id','speaker_label_en','source_review_needed','review_notes')
    for path in sorted(directory.glob('s_*.json')):
        if path.name.endswith('.en.json'):continue
        rows=json.loads(path.read_text(encoding='utf-8'));output=[]
        expected=[r['id'] for r in source.values() if r['member']==path.stem+'.bin']
        if [r['id'] for r in rows]!=expected:raise ValueError('Scenario/source IDs differ '+path.name)
        for row in rows:
            original=source[row['id']];block=blocks[row['block_id']]
            if row['source_sha256']!=scenario_fingerprint(original,block['source_sha256']):raise ValueError('Stale scenario row '+row['id'])
            if row['en'] is not None and re.findall(r'<[^>]+>',original['ja'])!=re.findall(r'<[^>]+>',row['en']):raise ValueError('Scenario control tokens changed')
            output.append({k:row[k] for k in allowed if k in row})
        batches=[]
        for bp in sorted((directory/'batches').glob(path.stem+'-*.json')):
            b=json.loads(bp.read_text(encoding='utf-8'))
            item={k:b[k] for k in ('start','first_id','last_id','rows_examined','context','decisions','row_decisions','holds') if k in b}
            item['row_count']=len(b['translations']);batches.append(item)
        result={'format':1,'version':EXPORT_VERSION,'member':path.stem+'.bin',
                'translation_status':EXPORT_STATUS,
                'rows':output,'review_batches':batches}
        # Audit a separate checking copy. Preserve each exact opaque model code
        # in the actual export, and keep every metadata field under the strict
        # Japanese-prose check. An exception cannot leak into review notes.
        audit=dict(result)
        audit['rows']=[dict(r,en=checked_english_prose(source[r['id']]['ja'],r['en']))
                       if r['en'] is not None else r for r in output]
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',json.dumps(audit,ensure_ascii=False)):raise ValueError('Japanese in scenario export '+path.name)
        out=path.with_name(path.stem+'.en.json')
        print('Scenario {}: {}/{} content rows drafted.'.format(path.stem,sum(bool(r['en']) for r in rows),sum(bool(source[r['id']]['ja']) for r in rows)))
        if write:out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)
        else:print('DRY RUN: no scenario export written')


def ui_export(write):
    from prepare_names_translation import fingerprint as ui_fingerprint
    path=ROOT/'work/translation/en/ui/names.json'
    if not path.exists():return
    rows=json.loads(path.read_text(encoding='utf-8'))
    source=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    if [r['id'] for r in rows]!=[r['id'] for r in source]:raise ValueError('UI/source IDs differ')
    allowed=('id','group','index','en','status','source_sha256','source_record_kind','translation_method','decisions')
    output=[]
    for row,original in zip(rows,source):
        if row['source_sha256']!=ui_fingerprint(original):raise ValueError('Stale UI row '+row['id'])
        if row['en'] is not None:
            if re.findall(r'<[^>]+>',row['en'])!=re.findall(r'<[^>]+>',original['text']):raise ValueError('UI control codes changed')
        output.append({k:row[k] for k in allowed if k in row})
    result={'format':1,'version':EXPORT_VERSION,'source_file':'D_NAMES.BIN',
            'translation_status':EXPORT_STATUS,'rows':output}
    if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',json.dumps(result,ensure_ascii=False)):raise ValueError('Japanese in UI export')
    out=path.with_name('names.en.json')
    print('UI/name export: {}/{} nonempty source rows prepared in English.'.format(sum(bool(r['en']) for r in rows),sum(bool(r['text']) for r in source)))
    if write:out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)
    else:print('DRY RUN: no UI export written')


def battle_export(write):
    from prepare_scenario_translation import fingerprint as row_fingerprint
    path=ROOT/'work/translation/en/battle/battle.json'
    if not path.exists():return
    rows=json.loads(path.read_text(encoding='utf-8'))
    source=json.loads((ROOT/'work/source/battle/rows.json').read_text(encoding='utf-8'))
    if [r['id'] for r in rows]!=[r['id'] for r in source]:raise ValueError('Battle/source IDs differ')
    allowed=('id','span_id','record_offset','root_indices','page_index','line_index','en','status',
             'ends_with_newline','source_sha256','block_source_sha256','speaker_entity_id',
             'speaker_label_en','referenced_by_selection_graph','source_review_needed','review_notes')
    output=[]
    for row,original in zip(rows,source):
        if row['source_sha256']!=row_fingerprint(original,original['source_sha256']):raise ValueError('Stale battle source '+row['id'])
        if row['en'] is not None and re.findall(r'<[^>]+>',row['en'])!=re.findall(r'<[^>]+>',original['ja']):
            raise ValueError('Battle controls changed '+row['id'])
        output.append({k:row[k] for k in allowed if k in row})
    batches=[]
    for bp in sorted((path.parent/'batches').glob('battle-*.json')):
        batch=json.loads(bp.read_text(encoding='utf-8'))
        item={k:batch[k] for k in ('start','first_id','last_id','rows_examined','context','decisions','row_decisions') if k in batch}
        item['row_count']=len(batch['translations']);batches.append(item)
    complete=all(r['en'] is not None and bool(r['en'])==bool(s['ja']) for r,s in zip(rows,source))
    result={'format':1,'version':EXPORT_VERSION,'source_file':'D_BMESS.BIN','first_draft_complete':complete,
            'translation_status':EXPORT_STATUS,
            'rows':output,'review_batches':batches}
    if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',json.dumps(result,ensure_ascii=False)):
        raise ValueError('Japanese in battle English export')
    out=path.with_name('battle.en.json')
    print('Battle export: {}/{} nonempty source rows drafted; {} structural empty rows.'.format(
        sum(bool(r['en']) for r in rows),sum(bool(r['ja']) for r in source),sum(not r['ja'] for r in source)))
    print('Sample:',json.dumps(output[:2]))
    if write:out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)
    else:print('DRY RUN: no battle export written')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus',choices=('all','library','scenario','ui','battle'),default='all')
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    if args.corpus in ('all','library'):library_export(args.write)
    if args.corpus in ('all','scenario'):scenario_exports(args.write)
    if args.corpus in ('all','battle'):battle_export(args.write)
    if args.corpus in ('all','ui'):ui_export(args.write)


if __name__=='__main__':main()
