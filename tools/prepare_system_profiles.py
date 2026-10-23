"""Extract and draft the additional D_SYSTEM profile texts. Dry run first.

Source prose is written only under ignored work/source. The English recipe
retains exact source fingerprints, headers, aliases and existing labels.
This archive's actual runtime use has not been established.
"""
import argparse
from collections import defaultdict
import json
import struct

from build_bitmap_font import ROOT, digest
from disc_inventory import Disc
from extract_library import sections
from rayblade_text import TextCodec, relative_target

SOURCE = ROOT/'work/source/system-profiles'
DEST = ROOT/'work/translation/en/library/system-profiles.en.json'
ENGLISH = [
    [
        'A handsome young man with a slightly brooding air.',
        'At heart, he has a fairly hot-blooded streak.',
        "He doesn't mind it himself, but he is rather blunt and foul-mouthed.",
        'He suddenly gets caught up in a disturbance of causality around him,',
        'and is summoned to Agarthia, a world in another dimension,',
        'where he ends up fighting the Ze=Ode that caused it all.',
        'He pilots the Spirit Mech Zeifon.',
        'He later becomes the pilot of the Spirit Mech Rayblade.',
        'On Rayblade, he handles the weapons and main controls.',
    ],
    [
        'Unearthed in Orthodox Calendar year 5959, it is maintained',
        'and researched in the Holy Land.',
        'It also served as the foundation for the La=Dis Spirit Mechs.',
        'Although some of its workings are understood, much',
        'remains unknown.',
        'Why it will only activate when two pilots are together',
        'also remains unknown.',
    ],
]


def original():
    disc = Disc(next(ROOT.glob('*.cue')))
    row = next(r for r in disc.inventory() if r['path']=='D_SYSTEM.AFS')
    archive = disc.read(row['lba'], row['size'])
    assert digest(archive)=='580b6de26b831dd49d71437d629504ed20c17094cc58f2f7f33dee21a6a2708d'
    assert archive[:8]==b'AFS\0\x02\0\0\0'
    members=[]
    for i in range(2):
        offset,size=struct.unpack_from('<II',archive,8+i*8)
        assert offset%2048==0 and size>0 and offset+size<=len(archive)
        members.append(archive[offset:offset+size])
    return archive,members


def source():
    archive,members=original()
    codec=TextCodec()
    paper,labels=members
    assert struct.unpack_from('<I',paper)[0]==384*4
    aliases=defaultdict(list)
    for i in range(384):
        aliases[relative_target(paper,i*4)].append(i)
    assert list(aliases)==[1536,1794]
    assert list(aliases.values())==[list(range(128)),list(range(128,384))]
    profiles=[]
    rows=[]
    for i,(offset,indices) in enumerate(aliases.items()):
        header_size=6 if i==0 else 5
        parts,end=sections(codec,paper,offset+header_size)
        assert len(parts)==1 and parts[0]['conditions']==[] and not parts[0]['unknown_glyphs']
        assert end==([1794,len(paper)][i])
        lines=parts[0]['text'].split('<NL>')
        assert len(lines)==len(ENGLISH[i])
        profiles.append({'id':f'system.profile.{i:03d}','offset':offset,'end':end,
                         'alias_indices':indices,'header_hex':paper[offset:offset+header_size].hex(),
                         'source_record_sha256':digest(paper[offset:end]),
                         'source_text_sha256':digest(paper[offset+header_size:end]),
                         'ja':parts[0]['text']})
        for j,line in enumerate(lines):
            rows.append({'id':f'system.profile.{i:03d}.l{j:02d}','profile':i,'line':j,
                         'ja':line,'ends_with_newline':j+1<len(lines),
                         'source_sha256':digest(json.dumps([line,j+1<len(lines),profiles[-1]['source_record_sha256']],ensure_ascii=False).encode())})
    assert struct.unpack_from('<I',labels)[0]==128*4
    existing=[]
    end=512
    for i in range(128):
        pos=relative_target(labels,i*4)
        assert pos==end
        decoded=codec.decode(labels,pos)
        assert not decoded['unknown_glyphs'] and decoded['terminator']==255
        assert decoded['text']==f'  {i+1:03d}:Unknown'
        end=pos+decoded['bytes_consumed']
        existing.append({'id':f'system.label.{i:03d}','index':i,'text':decoded['text'],
                         'source_offset':pos,'source_raw_sha256':digest(labels[pos:end])})
    assert end==len(labels)
    report={'archive':'D_SYSTEM.AFS','source_archive_sha256':digest(archive),
            'members':[{'member':i,'size':len(p),'sha256':digest(p)} for i,p in enumerate(members)],
            'profile_references':384,'distinct_profiles':2,'source_rows':16,
            'existing_English_labels':128,'header_sizes':[6,5],
            'reachability':'Not established; no D_SYSTEM.AFS filename literal found in current executable, which alone does not prove absence of runtime use'}
    return archive,members,report,profiles,rows,existing


def prepare():
    _,_,report,profiles,rows,existing=source()
    glossary=json.loads((ROOT/'work/glossary/glossary.json').read_text('utf-8'))
    terms={r['id']:r['en'] for r in glossary['entries']}
    expected={'mech.001':'Rayblade','mech.005':'Zeifon','term.002':'Spirit Mech',
              'term.004':'Agarthia','term.008':'Holy Land','term.009':'Ze=Ode',
              'term.061':'La=Dis','term.072':'Orthodox Calendar'}
    assert all(terms[k]==v for k,v in expected.items())
    translated=[]
    for row in rows:
        translated.append({k:row[k] for k in ('id','profile','line','ends_with_newline','source_sha256')}|
                          {'en':ENGLISH[row['profile']][row['line']],
                           'status':'source-linked editorial draft; independent review pending'})
    return {'source':report,'profiles':[{k:v for k,v in p.items() if k!='ja'} for p in profiles],
            'rows':translated,'existing_labels':existing,'glossary_links':list(expected),
            'context':'An additional older/different pair of shared profiles, not interchangeable with the current WIN00 library. No firm character or mech slot identity is assigned.',
            'decisions':['Preserve year 5959, Zeifon then Rayblade, weapons/main-control duties and the two-pilot activation statement exactly as this source says.',
                         'Do not replace these differences with current library lore or invent a female-pilot restriction absent here.',
                         'He follows the source description of a handsome male lead; no name is assigned from aliased slot indices.',
                         'Existing 001..128:Unknown labels retain every displayed character and leading space; only native glyph encoding may change for the integrated font.',
                         'La=Dis is treated as the Spirit Mech category; original Japanese does not mark number explicitly. Independent terminology review remains pending.'],
            'insertion_status':'Draft; native archive insertion, layout and actual runtime use pending'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    recipe=prepare()
    print('Plan: two shared profiles / 384 aliases, sixteen Japanese rows and 128 existing English labels.')
    for p in range(2):
        print('Profile',p,'sample:',next(r['en'] for r in recipe['rows'] if r['profile']==p))
    if not args.write:
        print('DRY RUN: no source/translation files written')
        return
    archive,members,report,profiles,rows,existing=source()
    SOURCE.mkdir(parents=True,exist_ok=True)
    for i,payload in enumerate(members):
        (SOURCE/f'member-{i:02d}.bin').write_bytes(payload)
    for name,data in [('index.json',report),('profiles.json',profiles),('rows.json',rows)]:
        (SOURCE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    DEST.write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('Wrote ignored local source and English-only draft; game files unchanged.')


if __name__=='__main__':
    main()
