"""Extract embedded VM dialogue and link byte-identical reviewed story drafts.

Japanese is saved only below ignored work/source. English copies contain
fingerprints/IDs, not source prose. This grants no additional draft credit.
Default dry run; no game components are changed.
"""
import argparse,hashlib,json,re
from build_font_patch import ROOT
from rayblade_text import TextCodec

DEST=ROOT/'work/translation/en/ui/embedded-dialogue.en.json'
digest=lambda b:hashlib.sha256(b).hexdigest()


def extract():
    exe=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();codec=TextCodec()
    blocks=json.loads((ROOT/'work/source/scenario-text/blocks.json').read_text('utf-8'));by_hash={}
    for b in blocks:by_hash.setdefault(b['source_sha256'],[]).append(b)
    drafts={};entries=[];sources=[];end=0x908c
    for match in re.finditer(b'\x8a\x06',exe[0x908c:0x10000]):
        off=0x908c+match.start()
        if off<end:continue
        style=exe[off+2];assert style in (0,0x40,0x80,0xa0,0xc0)
        decoded=codec.decode(exe,off+3);assert decoded['terminator']==255 and not decoded['unknown_glyphs'];end=off+3+decoded['bytes_consumed']
        raw=exe[off+3:end];matches=by_hash.get(digest(raw),[]);assert len(matches)==1
        b=matches[0];member=b['member']
        if member not in drafts:drafts[member]=json.loads((ROOT/'work/translation/en/scenario'/(member[:-4]+'.json')).read_text('utf-8'))
        rows=[r for r in drafts[member] if r['block_id']==b['id']];assert rows and all(r['en'] is not None for r in rows)
        english='<NL>'.join(r['en'] for r in rows)
        assert decoded['text']==b['ja'] and len(decoded['text'].split('<NL>'))==len(rows)
        key=f'embedded.o{off:05x}'
        entries.append({'id':key,'command_offset':off,'source_offset':off+3,'source_bytes':len(raw),'command_end':end,'source_sha256':digest(raw),'style':style,'story_draft_block':b['id'],'story_draft_rows':[r['id'] for r in rows],
            'draft_sha256':digest(english.encode()),'en':english,'context_review':'Same named speaker and message purpose in embedded affection-check or event copy; existing wording retained','status':'existing draft linked; independent meaning review pending'})
        sources.append({'id':key,'command_offset':off,'style':style,'raw_hex':raw.hex(),'ja':decoded['text'],'source_sha256':digest(raw)})
    assert len(entries)==13
    return {'source_executable_sha256':digest(exe),'scan_region':[0x908c,0x10000],'commands':13,'story_library_draft_credit':0,'coverage':'Embedded VM program region only; full VM/native text coverage remains unproven','rows':entries},sources


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args();recipe,sources=extract()
    print(json.dumps({k:v for k,v in recipe.items() if k!='rows'},indent=2));print('Linked English source blocks:',[r['story_draft_block'] for r in recipe['rows']])
    if not args.write:print('DRY RUN: no files written');return
    DEST.write_text(json.dumps(recipe,indent=2)+'\n','utf-8')
    source=ROOT/'work/source/embedded-dialogue';source.mkdir(parents=True,exist_ok=True);(source/'entries.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('Wrote 13 English links and local-only source records; no new draft credit.')


if __name__=='__main__':main()
