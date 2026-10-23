"""Check all prepared D_NAMES drafts against source identities and controls.

Read-only. Does not verify meaning, pixel layout or runtime-assembled grammar.
"""
import json
import re
from collections import Counter
from build_font_patch import ROOT
from prepare_names_translation import fingerprint


def main():
    source=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text(encoding='utf-8'))
    assert [r['id'] for r in rows]==[r['id'] for r in source]
    assert len({r['id'] for r in rows})==len(rows)
    unready=Counter();methods=Counter()
    words={'0':['zero'],'1':['one','single','first'],'2':['two','second'],'3':['three','third'],
           '4':['four','fourth'],'5':['five','fifth'],'6':['six','sixth'],'7':['seven','seventh'],
           '8':['eight','eighth'],'9':['nine','ninth'],'10':['ten'],'100':['century','hundred']}
    for row,original in zip(rows,source):
        assert row['source_sha256']==fingerprint(original),('Stale source',row['id'])
        assert (row['group'],row['index'])==(original['group'],original['index'])
        if row['en'] is not None:
            assert bool(row['en'])==bool(original['text']),('Content mismatch',row['id'])
            assert row['en'].isascii(),('Unsupported UI font character',row['id'])
            assert re.findall(r'<[^>]+>',row['en'])==re.findall(r'<[^>]+>',original['text']),('Lost control token',row['id'])
            assert '\n' not in row['en'] and '\r' not in row['en'],'Extra unencoded line boundary'
            jp_plain=re.sub(r'<[^>]+>','',original['text']);en_plain=re.sub(r'<[^>]+>','',row['en']).lower()
            for number in set(re.findall(r'\d+',jp_plain)):
                visible=number in re.findall(r'\d+',en_plain.replace(',',''))
                spelled=any(re.search(r'\b'+word+r'\b',en_plain) for word in words.get(number,()))
                assert visible or spelled,('Source number missing',row['id'],number)
            if row['en']:methods[row['translation_method']]+=1
        else:unready[row['group']]+=1
    complete=[g for g in range(13) if not unready[g]]
    print('Source IDs, fingerprints, all control tokens, line boundaries and ASCII UI repertoire pass.')
    print('Prepared nonempty rows by method:',dict(methods))
    print('Fully drafted/preserved groups:',complete)
    print('Still untranslated rows by group:',dict(unready))
    print('Meaning review, measured layout and dynamic message assembly remain pending; disc insertion status is tracked separately.')


if __name__=='__main__':main()
