"""Compile authored scenario/battle rows into source-checked 80-row batches.

Captures the currently prepared source fingerprints for apply_scenario_batch.
Does not infer, reuse, or generate any translation. Default is read-only.
"""
import argparse
import json
import re
from pathlib import Path
from build_font_patch import ROOT
from prepare_scenario_translation import fingerprint
from source_literals import checked_english_prose


def authored_text(value, source):
    """Expand an explicitly authored punctuation-only timing row, never prose."""
    if isinstance(value, dict):
        if value != {'timed_ellipsis': '..'}:
            raise ValueError('Unknown authored text object')
        punctuation = source.replace('<FC:02:3E>', '')
        if not punctuation or set(punctuation) != {'\u2025'}:
            raise ValueError('Timed ellipsis object requires only two-dot leaders and exact wait controls')
        return source.replace('\u2025', '..')
    return value


def authored_entry(value, source):
    """An explicit hold records an untranslated row, never replacement prose."""
    if isinstance(value,dict) and set(value)=={'hold'}:
        reason=value['hold']
        if not source or not isinstance(reason,str) or not reason.strip():
            raise ValueError('A hold requires content and a nonempty reason')
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',reason):
            raise ValueError('Hold reasons must be English-only')
        return None,reason
    return authored_text(value,source),None


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('authored',type=Path);ap.add_argument('--write',action='store_true')
    args=ap.parse_args();authored=json.loads(args.authored.read_text(encoding='utf-8'))
    review_metadata={key:authored.get(key,{}) for key in ('batches','row_decisions')}
    if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',json.dumps(review_metadata,ensure_ascii=False)):
        raise ValueError('Review metadata must be English-only: '+args.authored.name)
    member=authored['member']
    if not re.fullmatch(r's_[0-9a-f]{3}|battle',member):raise ValueError('Invalid scenario/battle member')
    directory=ROOT/('work/translation/en/battle' if member=='battle' else 'work/translation/en/scenario')
    rows=json.loads((directory/(member+'.json')).read_text(encoding='utf-8'))
    covered=set();batches=[]
    for start_text,metadata in sorted(authored['batches'].items(),key=lambda kv:int(kv[0])):
        start=int(start_text);selected=rows[start:start+80]
        if start<0 or start%80 or not selected:raise ValueError('Invalid batch start')
        indices=range(start,start+len(selected));texts=[];holds={}
        for i,row in zip(indices,selected):
            if row['source_sha256']!=fingerprint(row,row['block_source_sha256']):raise ValueError('Stale prepared source')
            en,reason=authored_entry(authored['rows'][str(i)],row['ja'])
            if row['source_review_needed']:raise ValueError('Resolve source ambiguity first')
            if reason is not None:holds[row['id']]=reason
            else:
                if not isinstance(en,str) or bool(en)!=bool(row['ja']):raise ValueError('Content/empty mismatch at '+str(i))
                if re.findall(r'<[^>]+>',en)!=re.findall(r'<[^>]+>',row['ja']):raise ValueError('Controls changed at '+str(i))
                checked_english_prose(row['ja'],en)
            texts.append(en);covered.add(str(i))
        batch={'member':member,'start':start,'first_id':selected[0]['id'],'last_id':selected[-1]['id'],
               'source_fingerprints':[r['source_sha256'] for r in selected],
               'rows_examined':metadata['rows_examined'],'context':metadata['context'],
               'decisions':metadata['decisions'],
               'row_decisions':{rows[int(i)]['id']:decision for i,decision in authored.get('row_decisions',{}).items()
                                if start<=int(i)<start+len(selected)},'translations':texts}
        if holds:batch['holds']=holds
        path=directory/'batches'/(member+'-{:04d}.json'.format(start))
        if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=batch:raise ValueError('Existing batch differs: '+str(path))
        batches.append((path,batch))
        print('{} rows {}..{}: {} examined; sample {}'.format(member,start,start+len(selected)-1,
              batch['rows_examined'],json.dumps(texts[:2])))
        if holds:print('  {} explicitly held rows remain untranslated'.format(len(holds)))
    if covered!=set(authored['rows']):raise ValueError('Authored rows not covered exactly by declared batches')
    if not args.write:print('DRY RUN: no batch files written');return
    for path,batch in batches:
        path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote {} source-checked batches; apply_scenario_batch still required.'.format(len(batches)))


if __name__=='__main__':main()
