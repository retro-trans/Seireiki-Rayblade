"""Prepare one scenario's source-linked rows. Dry run by default."""
import argparse
import hashlib
import json
import re
from build_font_patch import ROOT


def fingerprint(row,block_sha):
    return hashlib.sha256(json.dumps([row['ja'],row['ends_with_newline'],block_sha],ensure_ascii=False).encode('utf-8')).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('member');ap.add_argument('--write',action='store_true');args=ap.parse_args()
    if not re.fullmatch(r's_[0-9a-f]{3}\.bin',args.member):raise ValueError('Expected scenario member filename')
    src=ROOT/'work/source/scenario-text'
    blocks={b['id']:b for b in json.loads((src/'blocks.json').read_text(encoding='utf-8')) if b['member']==args.member}
    if not blocks:raise ValueError('No source blocks for member')
    source=[r for r in json.loads((src/'rows.json').read_text(encoding='utf-8')) if r['member']==args.member]
    glossary=json.loads((ROOT/'work/glossary/glossary.json').read_text(encoding='utf-8'))['entries']
    labels={}
    for e in glossary:
        if e['category']!='character':continue
        for name in (e.get('ja'),e.get('full_ja'),*e.get('source_label_forms',[])):
            if name:labels.setdefault(name,(e.get('canonical_entity_id',e['id']),e.get('en')))
    out=ROOT/'work/translation/en/scenario'/args.member.replace('.bin','.json')
    old={r['id']:r for r in json.loads(out.read_text(encoding='utf-8'))} if out.exists() else {}
    rows=[]
    for row in source:
        row=dict(row);block=blocks[row['block_id']]
        parent=blocks.get(block.get('command_id'),block)
        match=re.match(r'^([^「『（<]{1,30})[「『（]',parent['ja'])
        label=match.group(1) if match else None
        entity,english=labels.get(label,(None,None))
        # These scripts use the generic printed label for waking companions,
        # an unidentified rescuer or a guessing-game voice, not the library's
        # separately catalogued nonhuman character named Voice.
        if label=='声' and args.member in {'s_01b.bin','s_04a.bin','s_0cb.bin','s_0d1.bin'}:
            entity,english=None,'Voice'
        row.update(source_sha256=fingerprint(row,block['source_sha256']),block_source_sha256=block['source_sha256'],
                   source_command_id=block.get('command_id',block['id']),source_page_index=block.get('page_index',0),
                   source_speaker_label=label,speaker_entity_id=entity,speaker_label_en=english,
                   source_review_needed=bool(block['unknown_glyphs']))
        prior=old.get(row['id'])
        if prior and prior['source_sha256']!=row['source_sha256'] and prior['en'] is not None:raise ValueError('Stale translation '+row['id'])
        if prior:
            for field in ('en','status','review_notes','context','decisions'):
                if field in prior:row[field]=prior[field]
        elif not row['ja']:row.update(en='',status='structural_empty')
        rows.append(row)
    if set(old)-{r['id'] for r in rows}:raise ValueError('Source IDs removed')
    print('{}: {} rows, {} content rows, {} drafted.'.format(args.member,len(rows),sum(bool(r['ja']) for r in rows),sum(bool(r['en']) for r in rows)))
    print('Sample:',json.dumps([{k:r[k] for k in ('id','speaker_entity_id','speaker_label_en','en')} for r in rows[:3]]))
    newly_resolved=[{k:r[k] for k in ('id','source_speaker_label','speaker_entity_id','speaker_label_en')}
                    for r in rows if r['speaker_entity_id'] and r['id'] in old
                    and old[r['id']].get('speaker_entity_id') is None]
    if newly_resolved:print('New speaker mappings:',len(newly_resolved),json.dumps(newly_resolved[:4],ensure_ascii=False))
    changed_speakers=[{k:r[k] for k in ('id','speaker_entity_id','speaker_label_en')}
                      for r in rows if r['id'] in old
                      and (r['speaker_entity_id'],r['speaker_label_en'])!=
                          (old[r['id']].get('speaker_entity_id'),old[r['id']].get('speaker_label_en'))]
    if changed_speakers:print('Changed speaker mappings:',len(changed_speakers),json.dumps(changed_speakers[:6]))
    if not args.write:print('DRY RUN: no working translation written');return
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)


if __name__=='__main__':main()
