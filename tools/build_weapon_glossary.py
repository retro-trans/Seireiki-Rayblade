"""Build a glossary of distinct authored weapon labels. Dry run by default."""
import argparse
import json
from build_font_patch import ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    source=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    authored=json.loads((ROOT/'work/translation/en/ui/weapon-label-drafts.json').read_text(encoding='utf-8'))
    groups={}
    for row in source:
        if row['group']!=4 or not row['text'] or set(row['text'])=={'\u30fc'}:continue
        label=row['text'].strip()
        if label not in authored['labels']:raise ValueError('Unauthored source weapon '+row['id'])
        groups.setdefault(label,[]).append(row)
    entries=[]
    for ja,rows in groups.items():
        index=min(r['index'] for r in rows);source_ids=[r['id'] for r in rows]
        aliases=[key for key,value in authored['gallery_aliases'].items() if value==ja]
        for row in source:
            if row['group']==12 and ':' in row['text'] and row['text'].split(':',1)[1] in [ja]+aliases:source_ids.append(row['id'])
        entries.append({'id':'weapon.{:03d}'.format(index),'category':'weapon','ja':ja,'en':authored['labels'][ja],
            'status':'editorial_draft','source_ids':source_ids,'source_indices':[r['index'] for r in rows],
            'alternate_ja':aliases,'notes':[authored['decisions']]+([authored['notes'][ja]] if ja in authored['notes'] else [])})
    result={'format':1,'version':'0.1.3','source':'D_NAMES.BIN group 4 and group 12 captions','entries':entries}
    print('Weapons: {} distinct labels; {} indexed source rows; {} linked gallery captions.'.format(len(entries),sum(len(e['source_indices']) for e in entries),sum(sum(i.startswith('names.g12.') for i in e['source_ids']) for e in entries)))
    print('Sample:',[(e['id'],e['en']) for e in entries[:6]])
    if not args.write:print('DRY RUN: no weapon glossary written');return
    out=ROOT/'work/glossary/weapons.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)


if __name__=='__main__':main()
