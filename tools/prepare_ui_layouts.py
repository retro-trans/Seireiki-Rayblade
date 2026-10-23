"""Prepare source-checked English UI presentation overrides. Default dry run.

Full terminology stays in the working translation/glossary. Display aliases
and layout controls are explicit; help text changes only its line breaks.
"""
import argparse,json,hashlib
from build_font_patch import ROOT
from scenario_word_wrap import font_bytes
from build_font4x_patch import MEDIUM

DEST=ROOT/'work/translation/en/ui/layouts.en.json'


def prepare():
    rows={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    font=font_bytes('0.1.14')
    width=lambda text:sum(font[0xa0+MEDIUM.index(c)] for c in text)
    entries={}
    def add(key,text,reason):
        before=rows[key]
        entries[key]={'en':text,'source_sha256':before['source_sha256'],
            'prior_en_sha256':hashlib.sha256(before['en'].encode('utf-8')).hexdigest(),'reason':reason}
    add('names.g00.001',rows['names.g00.001']['en'].replace('Counterattack Orders','Counter Orders').replace('Mission Objectives','Objectives'),
        'Explicit compact display labels in the tactical menu; full terminology retained in translation/glossary')
    for key in ('names.g00.003','names.g00.160'):
        en=rows[key]['en'].replace('Fighting Spirit','Spirit')
        if key.endswith('.003'):
            en=en.replace('Spirit    Prana<FC:93:80><FC:FF:FF>',
                'Spirit<FC:93:80><FC:FF:FF><FC:97:80>Prana')
        add(key,en,'Spirit fits the 24-pixel label field; Prana explicitly starts at x184 before its x208 value')
    add('names.g00.162',rows['names.g00.162']['en'].replace('Elevation Difference','Ht Diff'),
        'Height Difference display abbreviation before the unchanged x40 value anchor')
    add('names.g00.166',rows['names.g00.166']['en'].replace('Cut-In<','Cut-In <'),
        'Visible gap before the unchanged dynamic ON/OFF value')
    for key in ('names.g00.212','names.g00.225','names.g00.235'):
        add(key,rows[key]['en'].replace('Cleared through Chapter ','Cleared Ch. '),
            'Compact completed-chapter label retains chapter number and complete title')
    lines=[]
    for i,label in enumerate(('Show Obscured Units','Unit Color Coding','Grid Display','Sound')):
        y=0x80+2*i
        first,second=('Stereo','Mono') if i==3 else ('ON','OFF')
        lines.append(f'<FC:81:{y:02X}>'+label+f'<FC:94:{y:02X}>'+first+f'<FC:9A:{y:02X}>'+second)
    for i,label in enumerate(('Sound Test','Character Profiles','Unit Profiles','Memory Album'),4):
        lines.append(f'<FC:81:{0x80+2*i:02X}>'+label)
    add('names.g01.032','<NL>'.join(lines),
        'Choice columns anchored at local x160/x208; each 16-pixel row explicitly restores x8 because FC positioning also changes the native newline origin')
    for i in range(34,42):
        key=f'names.g01.{i:03d}';before=rows[key]['en']
        words=before.replace('<NL>',' ').split();lines=[];line=''
        for word in words:
            candidate=line+' '+word if line else word
            if width(candidate)>236:
                assert line;lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        assert len(lines)<=3 and max(map(width,lines))<=236
        assert ' '.join(lines).split()==words
        add(key,'<NL>'.join(lines),'Font-measured three-line settings help; every word/punctuation retained')
    assert width('Spirit')<=24 and width('Ht Diff')<=31
    return {'version':'0.1.15','font_build':'0.1.14','rows':entries}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    recipe=prepare();print(json.dumps(recipe,indent=2))
    if not args.write:print('DRY RUN: no layout overrides written');return
    DEST.write_text(json.dumps(recipe,indent=2)+'\n','utf-8');print('Wrote',DEST)


if __name__=='__main__':main()
