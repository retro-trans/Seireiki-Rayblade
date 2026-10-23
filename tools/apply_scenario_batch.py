"""Apply 80-row scenario/battle drafts with exact source identities. Dry run by default."""
import argparse
import json
import re
from pathlib import Path
from build_font_patch import ROOT
from prepare_scenario_translation import fingerprint
from source_literals import checked_english_prose


def draft_update(row,en,batch):
    if row['source_sha256']!=fingerprint(row,row['block_source_sha256']):raise ValueError('Stale source')
    if row['source_review_needed']:raise ValueError('Resolve inline source ambiguity before translation: '+row['id'])
    reason=batch.get('holds',{}).get(row['id'])
    if en is None:
        if not row['ja'] or not isinstance(reason,str) or not reason.strip():raise ValueError('Unexplained untranslated row')
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',reason):raise ValueError('Japanese in hold reason')
        if row['en'] is not None:raise ValueError('Hold would erase an existing draft')
        return dict(en=None,status='held',context=batch['context'],decisions=reason)
    if reason is not None:raise ValueError('Held row must remain untranslated')
    if row['en'] not in (None,'',en):raise ValueError('Would overwrite existing draft')
    if not isinstance(en,str) or bool(en)!=bool(row['ja']):raise ValueError('Content/empty mismatch '+row['id'])
    checked_english_prose(row['ja'],en)
    if re.findall(r'<[^>]+>',row['ja'])!=re.findall(r'<[^>]+>',en):raise ValueError('Control code mismatch '+row['id'])
    return dict(en=en,status='draft' if en else 'structural_empty',context=batch['context'],
                decisions=batch.get('row_decisions',{}).get(row['id'],batch['decisions']))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('batch',type=Path)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    batch=json.loads(args.batch.read_text(encoding='utf-8'));member=batch['member']
    if not re.fullmatch(r's_[0-9a-f]{3}|battle',member):raise ValueError('Invalid member name')
    directory=ROOT/('work/translation/en/battle' if member=='battle' else 'work/translation/en/scenario')
    path=directory/(member+'.json');rows=json.loads(path.read_text(encoding='utf-8'))
    texts=batch['translations'];start=batch['start'];selected=rows[start:start+len(texts)]
    if len(texts)!=80 and start+len(texts)!=len(rows):raise ValueError('Non-final slice must contain 80 rows')
    if len(selected)!=len(texts) or selected[0]['id']!=batch['first_id'] or selected[-1]['id']!=batch['last_id']:raise ValueError('Wrong source boundaries')
    if [r['source_sha256'] for r in selected]!=batch['source_fingerprints']:raise ValueError('Batch source fingerprints differ')
    if set(batch.get('holds',{}))!={r['id'] for r,en in zip(selected,texts) if en is None}:raise ValueError('Hold IDs must exactly match untranslated rows')
    for row,en in zip(selected,texts):
        row.update(draft_update(row,en,batch))
    print('{}: rows {}..{}; {} examined.'.format(member,start,start+len(texts)-1,batch['rows_examined']))
    for r in selected[:4]:print(r['id'],repr(r['en']))
    if batch.get('holds'):print('{} held rows remain untranslated'.format(len(batch['holds'])))
    if not args.write:print('DRY RUN: no translation changed');return
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote draft; meaning and in-game review remain pending')


if __name__=='__main__':main()
