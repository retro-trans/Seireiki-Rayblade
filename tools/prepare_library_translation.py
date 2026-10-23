"""Prepare or refresh library work without overwriting translations. Dry run by default."""
import argparse
import hashlib
import json
from build_font_patch import ROOT


def fingerprint(row):
    return hashlib.sha256(json.dumps([row['ja'],row['conditions'],row['ends_with_newline']],ensure_ascii=False).encode('utf-8')).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    source=json.loads((ROOT/'work/source/library/rows.json').read_text(encoding='utf-8'))
    out=ROOT/'work/translation/en/library/library.json'
    old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else []
    previous={r['id']:r for r in old};rows=[]
    for row in source:
        row=dict(row);row['source_sha256']=fingerprint(row)
        prior=previous.get(row['id'])
        if prior and prior.get('source_sha256')!=row['source_sha256'] and prior.get('en') is not None:
            raise ValueError('Source changed under translation: '+row['id'])
        if prior:
            for field in ('en','status','review_notes','context','decisions'): 
                if field in prior:row[field]=prior[field]
        elif row['ja']=='':row.update(en='',status='structural_empty')
        rows.append(row)
    removed=set(previous)-{r['id'] for r in rows}
    if removed:raise ValueError('Source removed rows; manual reconciliation needed: '+str(sorted(removed)))
    print('Library work: {} rows, {} nonempty rows, {} existing translations.'.format(len(rows),sum(bool(r['ja']) for r in rows),sum(bool(r['en']) for r in rows)))
    print('Sample:',json.dumps([{k:r[k] for k in ('id','en','status')} for r in rows[:3]]))
    if not args.write:print('DRY RUN: no translation work written');return
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote',out)


if __name__=='__main__':main()
