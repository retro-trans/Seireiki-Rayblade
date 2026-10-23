"""Apply reviewed source-indexed drafts, with stale-source and row-count checks. Dry run by default."""
import argparse
import json
import re
from pathlib import Path
from build_font_patch import ROOT
from prepare_library_translation import fingerprint


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('batch',type=Path);ap.add_argument('--write',action='store_true')
    ap.add_argument('--revise-draft',action='store_true',help='Allow changes to draft rows only; never overwrite reviewed rows')
    args=ap.parse_args()
    batch=json.loads(args.batch.read_text(encoding='utf-8'))
    path=ROOT/'work/translation/en/library/library.json';rows=json.loads(path.read_text(encoding='utf-8'))
    start=batch['start'];texts=batch['translations'];slice_rows=rows[start:start+len(texts)]
    if len(slice_rows)!=len(texts):raise ValueError('Batch extends beyond source')
    if batch['first_id']!=slice_rows[0]['id'] or batch['last_id']!=slice_rows[-1]['id']:
        raise ValueError('Batch boundaries differ from source ordering')
    if batch['source_fingerprints']!=[r['source_sha256'] for r in slice_rows]:
        raise ValueError('Batch source fingerprints differ')
    for row,en in zip(slice_rows,texts):
        if row['source_sha256']!=fingerprint(row):raise ValueError('Stale source: '+row['id'])
        if row['en'] not in (None,'',en):
            if not (args.revise_draft and row['status']=='draft'):raise ValueError('Would replace existing draft: '+row['id'])
            print('REVISION',row['id'],repr(row['en']),'->',repr(en))
        if not isinstance(en,str):raise ValueError('Every submitted row needs English text')
        if bool(row['ja'])!=bool(en):raise ValueError('Empty/content row mismatch: '+row['id'])
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]',en):raise ValueError('Japanese in English draft')
        tags=lambda s:re.findall(r'<[^>]+>',s)
        if tags(row['ja'])!=tags(en):raise ValueError('Control tokens differ: '+row['id'])
        row.update(en=en,status='draft' if en else 'structural_empty',context=batch['context'],
                   decisions=batch.get('row_decisions',{}).get(row['id'],batch['decisions']))
    print('Draft batch: rows {}..{} ({} rows); examined {} rows.'.format(start,start+len(texts)-1,len(texts),batch['rows_examined']))
    for row in slice_rows[:4]:print(row['id'],repr(row['en']))
    if not args.write:print('DRY RUN: no translations changed');return
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Applied draft; meaning review and in-game layout review remain pending')


if __name__=='__main__':main()
