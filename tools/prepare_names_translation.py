"""Prepare D_NAMES menu/name drafts with exact glossary names. Dry run by default.

Manual drafts live in an ignored source-fingerprinted map. No phrase-level
machine substitution is used: a source row is either explicitly translated,
an exact glossary entry, an indexed character/mech name, or unchanged ASCII.
"""
import argparse
import hashlib
import json
import re
from build_font_patch import ROOT


def fingerprint(row):
    return hashlib.sha256(json.dumps([row['id'],row['text'],row['raw_hex'],row.get('record_kind')],ensure_ascii=False).encode('utf-8')).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    source=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    glossary=json.loads((ROOT/'work/glossary/glossary.json').read_text(encoding='utf-8'))['entries']
    indexed={(e['category'],e.get('source_index')):e for e in glossary if e['category'] in ('character','mech')}
    exact={e['ja']:e['en'] for e in glossary if e.get('en') and e['category'] not in ('character','mech')}
    directory=ROOT/'work/translation/en/ui';out=directory/'names.json';manual_path=directory/'names-drafts.json'
    manual=json.loads(manual_path.read_text(encoding='utf-8')) if manual_path.exists() else {}
    old={r['id']:r for r in json.loads(out.read_text(encoding='utf-8'))} if out.exists() else {};rows=[];revisions=[]
    for r in source:
        digest=fingerprint(r);ja=r['text'];en=None;status='untranslated';basis=None;entry=None
        if r.get('record_kind')=='unused_table_root_sentinel':en='';status='unused_sentinel';basis='binary sentinel retained; no prose'
        elif not ja:en='';status='structural_empty';basis='empty source'
        elif r['group'] in (2,3,11):
            kind='mech' if r['group']==3 else 'character';entry=indexed.get((kind,r['index']))
            if entry:en=entry.get('full_en') if r['group']==11 else entry.get('en');basis='indexed glossary '+entry['id']
        if en is None and ja in exact:en=exact[ja];basis='exact glossary label'
        if en is None:
            normalized=ja.replace('\u3000','  ').replace('\u30fc','-').replace('\u2025','..').replace('\u201c','"').replace('\u201d','"').replace('\uff08','(').replace('\uff09',')')
            if normalized.isascii():en=normalized;basis='existing Latin/control/placeholder text preserved'
        if en is not None and status=='untranslated':status='draft'
        prior=old.get(r['id'])
        if prior:
            if prior['source_sha256']!=digest and prior.get('en') is not None:raise ValueError('Stale name/UI translation '+r['id'])
            if prior.get('en') is not None and en is None:en=prior['en'];status=prior['status'];basis=prior['decisions']
        if r['id'] in manual:
            m=manual[r['id']]
            if m['source_sha256']!=digest:raise ValueError('Stale manual UI draft '+r['id'])
            en=m['en'];basis=m['decisions'];status='draft'
        if en is not None:
            if not isinstance(en,str) or bool(en)!=bool(ja):raise ValueError('Content/empty mismatch '+r['id'])
            if re.findall(r'<[^>]+>',en)!=re.findall(r'<[^>]+>',ja):raise ValueError('UI control tokens changed '+r['id'])
            if not en.isascii():raise ValueError('UI draft outside implemented ASCII repertoire '+r['id'])
        row={'id':r['id'],'group':r['group'],'index':r['index'],'ja':ja,'en':en,'status':status,
             'source_sha256':digest,'source_record_kind':r.get('record_kind'),'decisions':basis}
        row['translation_method']=('unused_sentinel' if status=='unused_sentinel' else 'structural_empty' if not ja
            else 'authored' if r['id'] in manual else 'untranslated' if en is None
            else 'glossary' if basis and ('glossary' in basis) else 'existing_ascii_or_placeholder')
        if prior and prior.get('en') not in (None,en):
            if prior['status'] not in ('draft','untranslated'):raise ValueError('Would replace reviewed translation '+r['id'])
            revisions.append({'id':r['id'],'before':prior['en'],'after':en})
        rows.append(row)
    if set(manual)-{r['id'] for r in source}:raise ValueError('Manual draft contains unknown source IDs')
    count=sum(bool(r['en']) for r in rows);total=sum(bool(r['ja']) for r in rows)
    print('D_NAMES: {} / {} nonempty rows drafted; {} total records; {} unused sentinels.'.format(count,total,len(rows),sum(r['status']=='unused_sentinel' for r in rows)))
    print('New/changed sample:',json.dumps([{'id':r['id'],'en':r['en']} for r in rows if r['en'] is not None and r['ja']!=r['en']][:10]))
    if revisions:print('Revisions:',json.dumps(revisions))
    if not args.write:print('DRY RUN: no name/UI work written');return
    directory.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)


if __name__=='__main__':main()
