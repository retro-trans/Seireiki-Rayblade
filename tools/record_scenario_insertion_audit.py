"""Record inspected scenario insertion research. Dry run before --write."""
import argparse
import hashlib
import json
from build_font_patch import ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    path=ROOT/'work/output/0.1.6/scenario-insertion-audit.json'
    proof=json.loads(path.read_text('utf-8'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert proof['source_executable_sha256']==sha(ROOT/'work/source/disc/1ST_READ.BIN')
    for name,value in proof['source_member_sha256'].items():
        assert sha(ROOT/'work/source/scenario'/name)==value
    for name,value in proof['working_file_sha256'].items():
        assert sha(ROOT/'work/translation/en/scenario'/name)==value
    assert len(proof['native_cases'])==proof['selected_native_witnesses']==87
    assert proof['native_SH4_instructions']==2828248
    docpath=ROOT/'docs/scenario-format.json';doc=json.loads(docpath.read_text('utf-8'))
    doc['version']='0.1.6'
    doc['status']='English command stream/native formatter audit complete; runtime mapping and scenario insertion unfinished; source scenario binaries unchanged'
    doc['english_insertion_audit']={k:v for k,v in proof.items() if k not in
        ('source_member_sha256','working_file_sha256','native_cases')}
    doc['english_insertion_audit']['evidence']='work/output/0.1.6/scenario-insertion-audit.json'
    doc['native_inline_command']['allocation_kind']='heap allocation through native malloc at runtime 8c03f748; not a 1 KiB stack array'
    doc['reinsertion_requirements']=[s for s in doc['reinsertion_requirements']
        if s!='Extend font repertoire for retained player-facing heart symbol before building s_001']
    doc['reinsertion_requirements'].append('Grow the dialogue heap allocation and formatter limit together; 62 current English commands produce over 1024 bytes. Native witness maximum is 1411 bytes; pixel layout and runtime FC expansion need separate checks.')
    doc['reinsertion_research_hypothesis']['rejected_shortcuts']=[
        'Do not use 8c019088 as a proven loaded D_SCE member base. The executable initializes it to embedded program root data at 8c01908c, and native root/call helpers use that table.',
        'Do not treat opcode 8E handler return 0x8000 as a proven scenario allocation size. It is a VM return value; the actual loader/buffer ownership is unproven.',
        'Do not advance the original VM pointer by English consumption. The original command end/length must be retained independently.']
    entry='''- Audited complete English story command streams before insertion: 50,273 of 50,626 extracted candidate commands encode/decode exactly with source controls, FE continuation ends, ASCII state, fingerprints and physical row boundaries retained. The 353 held commands contain the existing 503 held rows and three already-drafted companion rows; this command-level exclusion adds no new translation holds. Complete English payloads total 3,088,758 bytes, with a maximum of 1,380 bytes.
- Executed the original story formatter on 87 English witnesses, including all 62 streams longer than the original 1,023-byte budget and representatives of every observed style, continuation count and FC/ASCII pattern. With a separate larger research destination/limit, 2,828,248 native instructions preserve all glyph/control bytes, source consumption, stack/register ABI and guards; maximum formatted output is 1,411 bytes. This proves a larger dialogue heap allocation and matching formatter limit are needed; it does not insert story text or prove pixel layout. Recorded source/working hashes and explicit scope limits. Embedded VM root data and the 8E return value remain distinct from an unproven D_SCE loader/base.
'''
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8');marker='\n## 0.1.5 — native font symbols and space fix'
    assert marker in old and 'Audited complete English story command streams' not in old
    print(json.dumps(doc['english_insertion_audit'],indent=2));print(entry)
    if args.write:
        docpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf-8')
        cp.write_text(old.replace(marker,'\n'+entry+marker,1),'utf-8')
    print('Wrote scenario audit documentation/changelog.' if args.write else 'DRY RUN: no documentation changed.')


if __name__=='__main__':main()
