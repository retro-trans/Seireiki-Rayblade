"""Check battle source linkage and English draft structure, read-only.

This does not establish translation meaning, combat-state setup, font layout
or game insertion. Native graph behavior is tested separately.
"""
import json
import re
import hashlib
from collections import defaultdict
from build_font_patch import ROOT
from build_font4x_patch import MEDIUM
from prepare_scenario_translation import fingerprint
from rayblade_codec import decompress


def main():
    packed=(ROOT/'work/source/disc/D_BMESS.BIN').read_bytes();data,used=decompress(packed)
    summary=json.loads((ROOT/'work/source/battle/summary.json').read_text(encoding='utf-8'))
    assert used==len(packed) and hashlib.sha256(packed).hexdigest()==summary['compressed_sha256']
    assert hashlib.sha256(data).hexdigest()==summary['decoded_sha256']
    assert data==(ROOT/'work/source/battle/D_BMESS.dec.bin').read_bytes(),'Stored battle component differs'
    records=json.loads((ROOT/'work/source/battle/records.json').read_text(encoding='utf-8'))
    spans={s['id']:s for r in records for s in r['spans']}
    for span in spans.values():
        raw=data[span['offset']:span['end_offset']]
        assert raw.hex()==span['raw_hex'] and hashlib.sha256(raw).hexdigest()==span['source_sha256'],('Battle raw span differs',span['id'])
    source=json.loads((ROOT/'work/source/battle/rows.json').read_text(encoding='utf-8'))
    rows=json.loads((ROOT/'work/translation/en/battle/battle.json').read_text(encoding='utf-8'))
    assert [r['id'] for r in rows]==[r['id'] for r in source],'Battle source/draft IDs differ'
    grouped=defaultdict(list);font_pending=set();drafted=0;completed_spans=defaultdict(list)
    for row,original in zip(rows,source):
        assert original['source_sha256']==spans[original['span_id']]['source_sha256'],'Source row/span hash differs'
        assert row['block_source_sha256']==original['source_sha256'],'Battle span hash differs'
        assert row['source_sha256']==fingerprint(original,original['source_sha256']),('Stale battle row',row['id'])
        for field in ('span_id','record_offset','root_indices','page_index','line_index','ends_with_newline','referenced_by_selection_graph'):
            assert row[field]==original[field],('Battle source metadata differs',row['id'],field)
        en=row['en']
        if en is not None:
            assert isinstance(en,str) and bool(en)==bool(original['ja']),('Content/empty mismatch',row['id'])
            assert '\n' not in en and '\r' not in en,('Extra physical line',row['id'])
            assert re.findall(r'<[^>]+>',en)==re.findall(r'<[^>]+>',original['ja']),('Changed battle controls',row['id'])
            assert not re.search(r'[\u3040-\u30ff\u3400-\u9fff]',en),('Japanese in battle English',row['id'])
            font_pending.update(set(re.sub(r'<[^>]+>','',en))-set(MEDIUM));drafted+=bool(en)
        grouped[(row['span_id'],row['page_index'])].append((row,original))
        completed_spans[row['span_id']].append(en is not None)
    for key,group in grouped.items():
        if any(r['en'] is None for r,_ in group):continue
        ja=''.join(o['ja'] for _,o in group).rstrip();en=''.join(r['en'] for r,_ in group).rstrip()
        if ja.endswith(('\u300d','\u300f')):assert en.endswith(('"',"'")),('Unclosed battle speech',key)
        if ja.endswith('\uff09'):assert en.endswith(')'),('Unclosed battle thought',key)
    print('PASS: {} source-linked battle rows; {} nonempty English drafts; {} completely prepared spans.'.format(
        len(rows),drafted,sum(all(v) for v in completed_spans.values())))
    print('Original compressed/decoded bytes, span hashes, source fingerprints, controls, page/line boundaries, reference metadata and closing punctuation pass.')
    print('Font repertoire work required:',json.dumps(sorted(font_pending),ensure_ascii=True))
    print('Meaning, combat-state setup, insertion and in-game layout remain unverified.')


if __name__=='__main__':main()
