"""Prepare source-linked battle rows for contextual English drafting.

Displayed speaker labels are read from the text, never guessed from battle
root-slot indices. Branch and random-table operands remain outside the prose.
Dry run by default. Bilingual working rows remain ignored by version control.
"""
import argparse
import json
import re
from build_font_patch import ROOT
from prepare_scenario_translation import fingerprint


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    directory=ROOT/'work/source/battle'
    source=json.loads((directory/'rows.json').read_text(encoding='utf-8'))
    records=json.loads((directory/'records.json').read_text(encoding='utf-8'))
    spans={s['id']:s for r in records for s in r['spans']}
    glossary=json.loads((ROOT/'work/glossary/glossary.json').read_text(encoding='utf-8'))['entries']
    labels={}
    for e in glossary:
        if e['category']!='character':continue
        for name in (e.get('ja'),e.get('full_ja')):
            if name:labels.setdefault(name,(e.get('canonical_entity_id',e['id']),e.get('en')))
    speakers={}
    for span in spans.values():
        label=None
        for page in span['pages']:
            text=re.sub(r'^(?:<[^>]+>)*','',page['ja']).lstrip()
            match=re.match(r'^([^「『（<]{1,30})[「『（]',text)
            if match:label=match.group(1)
            speakers[(span['id'],page['page_index'])]=label
    out=ROOT/'work/translation/en/battle/battle.json'
    old={r['id']:r for r in json.loads(out.read_text(encoding='utf-8'))} if out.exists() else {}
    result=[]
    for original in source:
        row=dict(original);span=spans[row['span_id']];label=speakers[(span['id'],row['page_index'])]
        entity,english=labels.get(label,(None,None))
        row.update(block_source_sha256=span['source_sha256'],
                   source_sha256=fingerprint(row,span['source_sha256']),
                   source_speaker_label=label,speaker_entity_id=entity,speaker_label_en=english,
                   source_review_needed=any(p['unknown_glyphs'] for p in span['pages']))
        previous=old.get(row['id'])
        if previous and previous['source_sha256']!=row['source_sha256'] and previous['en'] is not None:
            raise ValueError('Stale battle draft: '+row['id'])
        if previous:
            for field in ('en','status','context','decisions','review_notes'):
                if field in previous:row[field]=previous[field]
        elif not row['ja']:row.update(en='',status='structural_empty')
        result.append(row)
    if set(old)-{r['id'] for r in result}:raise ValueError('Battle source IDs removed')
    print('Battle: {} rows, {} nonempty; {} drafted.'.format(len(result),sum(bool(r['ja']) for r in result),sum(bool(r['en']) for r in result)))
    print('Samples:',json.dumps([{k:r[k] for k in ('id','speaker_entity_id','speaker_label_en','en')} for r in result[:4]]))
    if not args.write:print('DRY RUN: no working battle translation written');return
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote local battle working rows; meaning, branch context and layout review remain separate.')


if __name__=='__main__':main()
