"""Build the source-linked working glossary. Dry run by default.

Names/UI terms may contain Japanese, as allowed by AGENTS.md. No dialogue or
complete biography prose is copied into the glossary. Existing research fields
are preserved unless --refresh is explicitly supplied.
"""
import argparse
import json
import re
from build_font_patch import ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');ap.add_argument('--refresh',action='store_true');args=ap.parse_args()
    directory=ROOT/'work/glossary'
    decisions=json.loads((directory/'decisions.json').read_text(encoding='utf-8'))
    metadata_path=directory/'profile-metadata.json'
    metadata=json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    rows=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    names={(r['group'],r['index']):r for r in rows}
    library=json.loads((ROOT/'work/source/library/entries.json').read_text(encoding='utf-8'))
    profiles={e['id']:e for e in library}
    profile_rows=json.loads((ROOT/'work/source/library/rows.json').read_text(encoding='utf-8'))
    entries=[]
    for kind,group in (('character',2),('mech',3)):
        for (g,index),source in names.items():
            ja=source['text']
            if g!=group or not ja or set(ja).issubset({'ー','?'}):continue
            decision_key=str(index)
            if kind=='character':
                canonical=decisions['character_aliases'].get(decision_key,index)
                values=decisions['characters'].get(str(canonical))
                english=values[0] if values else None
                full_ja=names.get((11,index),{}).get('text') or None
                full_en=values[1] if values and full_ja else None
            else:
                canonical=index;english=decisions['mechs'].get(decision_key);full_ja=ja;full_en=english
            profile=profiles.get('library.{}.{:03d}'.format(kind,index))
            if profile and profile.get('entity_id')!='{}.{:03d}'.format(kind,canonical):profile=None
            row={'id':'{}.{}'.format(kind,str(index).zfill(3)), 'category':kind,
                 'source_index':index,'canonical_entity_id':'{}.{:03d}'.format(kind,canonical),
                 'ja':ja,'en':english,'full_ja':full_ja,'full_en':full_en,
                 'status':'editorial_draft' if english else 'needs_name_research',
                 'source_ids':[source['id']]+([names[(11,index)]['id']] if kind=='character' and (11,index) in names else []),
                 'library_entry_id':profile['canonical_id'] if profile and profile['sections'] else None,
                 'source_name_decoded':not bool(re.search(r'<G[0-9A-F]+>',ja+(full_ja or ''))),
                 'notes':[]}
            note=decisions.get('notes' if kind=='character' else 'mech_notes',{}).get(decision_key)
            if note:row['notes'].append(note)
            if kind=='character':
                row.update(gender=None,personality=None,position=None,metadata_status='awaiting profile/context review')
            entries.append(row)
    for number,(category,ja,en,note) in enumerate(decisions['terms'],1):
        # Units and explicitly selected homonyms need curated evidence.
        # A substring/name match can point to a distinct mech or person.
        occurrences=[]
        if category!='time_unit' and en not in decisions.get('curated_source_terms',[]):
            occurrences=[r['id'] for r in rows if ja in r['text']]
            occurrences += [r['id'] for r in profile_rows if ja in r['ja']]
        occurrences += decisions.get('term_sources',{}).get(en,[])
        entries.append({'id':'term.{:03d}'.format(number),'category':category,'ja':ja,'en':en,
            'status':'editorial_draft','source_ids':occurrences,'notes':[note]})
    entries.extend(decisions.get('extra_entries',[]))
    weapons=directory/'weapons.json'
    if weapons.exists():entries.extend(json.loads(weapons.read_text(encoding='utf-8'))['entries'])
    out=directory/'glossary.json'
    if out.exists() and not args.refresh:
        old={e['id']:e for e in json.loads(out.read_text(encoding='utf-8'))['entries']}
        for row in entries:
            previous=old.get(row['id'],{})
            for field in ('gender','personality','position','metadata_status','research','review'):
                if field in previous:row[field]=previous[field]
    for row in entries:
        forms=decisions.get('accepted_english_forms',{}).get(row.get('en',''))
        if forms:row['accepted_english_forms']=forms
        entity=row.get('canonical_entity_id',row['id'])
        if entity in metadata:
            row.update(metadata[entity])
    result={'project':'Seireiki Rayblade Dreamcast','revision':decisions['revision'],
            'status':'source-linked working glossary; English spellings are drafts, not claimed official',
            'sources':decisions['sources'],'entries':entries}
    print('Glossary: {} entries; {} character labels, {} mech labels, {} weapon labels, {} terminology entries.'.format(len(entries),
        sum(e['category']=='character' for e in entries),sum(e['category']=='mech' for e in entries),
        sum(e['category']=='weapon' for e in entries),len(decisions['terms'])))
    print('Entries linked to library:',sum(bool(e.get('library_entry_id')) for e in entries))
    print('Unresolved source names:',[e['id'] for e in entries if e.get('source_name_decoded') is False])
    print('English sample:',[(e['id'],e.get('en'),e.get('full_en')) for e in entries[:6]])
    if not args.write:print('DRY RUN: no glossary written');return
    directory.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Wrote',out)


if __name__=='__main__':main()
