"""Compile explicitly authored UI translations into a source-checked draft map.

Each entry is full English text or an explicit list of exact phrase edits for
control-heavy labels. These are human-authored edits, not inferred translation.
Source fingerprints are mandatory. Default is a dry run.
"""
import argparse
import json
import re
from pathlib import Path
from build_font_patch import ROOT
from prepare_names_translation import fingerprint


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('authored',type=Path)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    authored=json.loads(args.authored.read_text(encoding='utf-8'))
    source={r['id']:r for r in json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))}
    path=ROOT/'work/translation/en/ui/names-drafts.json'
    manual=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    prepared={}
    for key,entry in authored['rows'].items():
        row=source[key];digest=fingerprint(row)
        if authored['source_fingerprints'][key]!=digest:raise ValueError('Authoring source changed '+key)
        if 'en' in entry:en=entry['en']
        else:
            en=row['text']
            for old,new in entry['replace']:
                if old not in en:raise ValueError('Phrase not found '+key+' '+repr(old))
                en=en.replace(old,new)
            en=en.replace('\u3000','  ')
        if not en.isascii():raise ValueError('UI row retains non-ASCII source text '+key)
        if re.findall(r'<[^>]+>',en)!=re.findall(r'<[^>]+>',row['text']):raise ValueError('UI control sequence changed '+key)
        prepared[key]={'en':en,'source_sha256':digest,'decisions':entry.get('decisions',authored['decisions'])}
    print('Authored {} UI rows.'.format(len(prepared)))
    print('Sample:',json.dumps(list(prepared.items())[:8]))
    if not args.write:print('DRY RUN: no compiled UI draft map written');return
    manual.update(prepared);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(manual,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',path)


if __name__=='__main__':main()
