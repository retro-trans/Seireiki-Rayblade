"""Reflow English library paragraphs within their original unlock sections.

The native 256-pixel window has eight-pixel side borders. Its text origin is
eight pixels inside the left border, leaving 240 pixels of ink space. Reserve
four pixels for current-font ink/shadow overhang: 236 pixels of pen advance.
Native constructor and profile-viewer evidence is recorded by the test tool.
"""
import argparse,json,hashlib
from build_antialias_font import ROOT,font_bytes
from build_font4x_patch import MEDIUM
from english_text_codec import encode

VERSION='0.1.18'
PRIOR='0.1.17'
PEN=236
DEST=ROOT/'work/translation/en/library/layouts.en.json'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def wrap_line(line,font):
    assert line==line.strip() and '  ' not in line and '\t' not in line
    if not line:return line
    width=lambda s:sum(font[0xa0+MEDIUM.index(c)] for c in s)
    parts=[];current=''
    for word in line.split(' '):
        if width(word)>PEN:raise ValueError('Library word needs a reviewed layout: '+word)
        candidate=current+' '+word if current else word
        if width(candidate)>PEN:parts.append(current);current=word
        else:current=candidate
    parts.append(current)
    assert ' '.join(parts)==line
    return '<NL>'.join(parts)


def prepare(*,font=None):
    if font is None:
        _,font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())
    entries=json.loads((ROOT/'work/source/library/entries.json').read_text('utf-8'))
    drafted={r['id']:r for r in json.loads((ROOT/'work/translation/en/library/library.json').read_text('utf-8'))}
    result={};rows=0;joined=0;maximum=0;before_max=0;sections=0;line_count=0
    width=lambda s:sum(font[0xa0+MEDIUM.index(c)] for c in s)
    for entry in entries:
        if entry['id']!=entry['canonical_id']:continue
        chunks=[]
        for n,section in enumerate(entry['sections']):
            lines=[drafted[entry['id']+f'.s{n:02d}.l{k:02d}']['en'] for k in range(len(section['text'].split('<NL>')))];sections+=1
            assert all(s is not None for s in lines)
            text='<NL>'.join(lines);chunks.append(text)
            before_max=max(before_max,max(map(width,lines),default=0))
            # These source rows are fixed-width layout fragments. Every
            # section is one paragraph; leading/trailing boundaries attach
            # conditional paragraphs and must stay outside the reflow.
            assert not any(not line for line in lines[1:-1]),'Review internal paragraph break before reflow'
            leading=int(lines[0]=='');trailing=int(lines[-1]=='')
            core=lines[leading:len(lines)-trailing if trailing else len(lines)]
            assert all(not line.endswith('-') for line in core),'Review split hyphen before joining'
            wrapped='<NL>'*leading+wrap_line(' '.join(core),font)+'<NL>'*trailing
            maximum=max(maximum,max(map(width,wrapped.split('<NL>')),default=0))
            line_count+=sum(bool(s) for s in wrapped.split('<NL>'))
            assert text.replace('<NL>',' ').split()==wrapped.replace('<NL>',' ').split()
            if wrapped!=text:
                a=encode(text);b=encode(wrapped);assert len(a)==len(b)
                assert all(x==y or (x,y) in [(0,253),(253,0)] for x,y in zip(a,b))
                added=sum(x==0 and y==253 for x,y in zip(a,b));removed=sum(x==253 and y==0 for x,y in zip(a,b));rows+=added;joined+=removed
                result[entry['id']+f'.s{n:02d}']={'prior_en_sha256':digest(text.encode('utf-8')),'en':wrapped,'inserted_breaks':added,'joined_breaks':removed,'reason':'Reflow original fixed-width rows inside one unlock paragraph; preserve all words, punctuation and paragraph boundaries'}
        # Independent per-section wrapping is valid only when every possible
        # adjoining conditional span has an explicit boundary on one side.
        for a,b in zip(chunks,chunks[1:]):assert a.endswith('<NL>') or b.startswith('<NL>'),entry['id']
    return {'version':VERSION,'source_build':PRIOR,'font_sha256':digest(font),'pen_pixels':PEN,'ink_pixels':240,'sections_examined':sections,'changed_sections':len(result),'inserted_breaks':rows,'joined_breaks':joined,'nonempty_line_count':line_count,'maximum_prior_line_pixels':before_max,'maximum_line_pixels':maximum,'sections':result}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args();recipe=prepare()
    print(json.dumps({k:v for k,v in recipe.items() if k!='sections'},indent=2))
    if not args.write:print('DRY RUN: no recipe written');return
    DEST.parent.mkdir(parents=True,exist_ok=True);DEST.write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n','utf-8');print('Wrote',DEST)


if __name__=='__main__':main()
