"""Check candidate source spans and drafted scenario structure, read-only.

Proves byte identity and translation structure for extracted spans. It cannot
prove that the signature scanner found every text-bearing VM instruction.
"""
import hashlib
import json
import re
from collections import Counter
from build_font_patch import ROOT
from prepare_scenario_translation import fingerprint
from build_font4x_patch import MEDIUM
from source_literals import checked_english_prose


def starts_single_quoted_speech(english):
    """Recognize the established speaker: 'whisper convention, not apostrophes."""
    return isinstance(english,str) and bool(re.match(r"^[^\n]*:\s*'",english))


def quotation_parity_matches(source,english,single_quoted_speech=False):
    """Keep FE-page quote parity while recognizing explicit whisper boundaries.

    Apostrophes inside contractions/possessives must not be counted as dialogue
    marks. Only the opening speaker boundary and source-marked final boundary
    contribute single quotes; ordinary double-quoted speech retains its check.
    """
    source_count=sum(source.count(c) for c in ('\u300c','\u300d','\u300e','\u300f','"'))
    # Three original Assistant reactions end with a hiragana "a" followed by
    # an ASCII double quote as a makeshift voicing mark, then the Japanese
    # speech closer. That visible sound mark is not a quotation boundary.
    # Keep this limited to the exact recovered ending; other ASCII quotes
    # still contribute parity, including ones in malformed source speech.
    source_count-=len(re.findall('\u3042"(?=\u300d)',source))
    english_count=english.count('"')
    if single_quoted_speech:
        english_count+=starts_single_quoted_speech(english)
        if source.endswith('\u300f'):
            if not english.endswith("'"):return False
            english_count+=1
    return source_count%2==english_count%2


def main():
    src=ROOT/'work/source/scenario-text'
    blocks=json.loads((src/'blocks.json').read_text(encoding='utf-8'))
    source_rows=json.loads((src/'rows.json').read_text(encoding='utf-8'))
    rows_by_id={r['id']:r for r in source_rows};by_block={b['id']:b for b in blocks}
    files={};last_end={};styles=Counter();commands={}
    for block in blocks:
        member=block['member']
        if member not in files:files[member]=(ROOT/'work/source/scenario'/member).read_bytes()
        data=files[member];start=block['command_offset'];end=block['end_offset'];text=block['text_offset']
        assert data[start:start+3]==bytes((0x8a,0x06,block['style'])),('Command mismatch',block['id'])
        command=block.get('command_id',block['id']);page=block.get('page_index',0)
        siblings=commands.setdefault(command,[])
        assert page==len(siblings),('Missing or misordered page',block['id'])
        if not page:
            assert text==start+3 and start>=last_end.get(member,0),('Overlapping command',block['id'])
            assert not block.get('ascii_mode_at_start',False)
        else:
            previous=siblings[-1]
            assert previous['terminator']==0xfe and text==previous['end_offset'],('Broken FE continuation',block['id'])
            assert block['ascii_mode_at_start']==previous['ascii_mode_at_end'],('ASCII state lost across pages',block['id'])
        assert data[text:end].hex()==block['raw_hex'],('Raw source mismatch',block['id'])
        assert hashlib.sha256(data[text:end]).hexdigest()==block['source_sha256'],('Source hash mismatch',block['id'])
        assert data[end-1]==block['terminator'] and block['terminator'] in (0xfe,0xff)
        siblings.append(block)
        assert page+1<block.get('page_count',1) or block['terminator']==0xff,('Final page lacks FF',block['id'])
        if page+1==block.get('page_count',1):
            assert end==block.get('command_end_offset',end)
        last_end[member]=end;styles[block['style']]+=1
    drafted=0;prepared=0;held=0;font_pending=set();quote_issues=[]
    for path in sorted((ROOT/'work/translation/en/scenario').glob('s_*.json')):
        if path.name.endswith('.en.json'):continue
        rows=json.loads(path.read_text(encoding='utf-8'));prepared+=len(rows)
        expected=[r['id'] for r in source_rows if r['member']==path.stem+'.bin']
        assert [r['id'] for r in rows]==expected,('Row ID mismatch',path.name)
        grouped={}
        for row in rows:
            original=rows_by_id[row['id']];block=by_block[row['block_id']]
            assert row['source_sha256']==fingerprint(original,block['source_sha256'])
            assert row['ends_with_newline']==original['ends_with_newline']
            if row.get('status')=='held':
                assert row['en'] is None and original['ja'],'Held row must remain untranslated content'
                assert isinstance(row.get('decisions'),str) and row['decisions'].strip(),'Missing hold reason'
                held+=1
            if row['en'] is not None:
                assert bool(row['en'])==bool(original['ja'])
                assert re.findall(r'<[^>]+>',row['en'])==re.findall(r'<[^>]+>',original['ja'])
                assert '\n' not in row['en'] and '\r' not in row['en'],'Extra physical line in draft'
                checked_english_prose(original['ja'],row['en'])
                if row['en']:drafted+=1
                plain=re.sub(r'<[^>]+>','',row['en']);font_pending.update(set(plain)-set(MEDIUM))
            grouped.setdefault(row['block_id'],[]).append(row)
        for bid,group in grouped.items():
            if any(r['en'] is None for r in group):continue
            ja=by_block[bid]['ja'];en='\n'.join(r['en'] for r in group)
            if ja.endswith(('\u300d','\u300f')) and not en.endswith(('"',"'")):quote_issues.append(bid)
            # FE pages may contain only one half of a speech quotation.
            # Compare parity with the source page rather than requiring each
            # page to be balanced; this also catches extra mid-speech quotes.
            command=by_block[bid].get('command_id',bid)
            first_bid=commands[command][0]['id']
            first_group=grouped.get(first_bid,[])
            first_english='\n'.join(r['en'] or '' for r in first_group)
            single_speech=starts_single_quoted_speech(first_english)
            if not quotation_parity_matches(ja,en,single_speech):
                quote_issues.append(bid+' (quotation parity)')
    assert not quote_issues,('Unclosed English source speech blocks',quote_issues)
    print('Verified {} display pages in {} candidate commands across {} members; raw bytes, hashes, FE continuation chains, terminators and non-overlap pass.'.format(len(blocks),len(commands),len(files)))
    print('Prepared {} physical rows; {} nonempty rows drafted; source IDs, line boundaries, control codes and closing quotes pass.'.format(prepared,drafted))
    if held:print('{} explicitly held content rows remain untranslated and excluded from the draft count.'.format(held))
    print('Font repertoire work still required:',json.dumps(sorted(font_pending),ensure_ascii=True))
    print('Full VM command coverage, meaning, layout and game insertion remain unverified.')


if __name__=='__main__':main()
