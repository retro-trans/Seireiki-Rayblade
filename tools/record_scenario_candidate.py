"""Record inspected 0.1.7 native story candidate evidence. Dry run first."""
import argparse,json,struct
from build_font_patch import ROOT,BASE
from build_scenario_translation import VERSION,digest
from build_scenario_patch import SOURCE,HEAP_POINTER,ORIGINAL_PREFIX_CAPACITY


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION
    component=json.loads((out/'text/scenario-component-report.json').read_text('utf-8'))
    patch=json.loads((out/'scenario-patch-report.json').read_text('utf-8'))
    proof=json.loads((out/'scenario-native-test.json').read_text('utf-8'))
    assert digest((out/'text/D_SCE.AFS').read_bytes())==component['archive_sha256']==proof['archive_sha256']
    assert digest((out/'1ST_READ.BIN').read_bytes())==patch['executable_sha256']==proof['executable_sha256']
    assert proof['native_lookup_cases']==component['english_commands']==50273
    assert proof['held_original_stream_cases']==component['held_commands']==353
    assert proof['original_script_base']==hex(SOURCE)
    for name,sha in component['working_file_sha256'].items():
        assert digest((ROOT/'work/translation/en/scenario'/name).read_bytes())==sha
    original=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    pointer=struct.unpack_from('<I',original,0x88b08+2*4)[0]-BASE
    assert original[pointer:pointer+10]==b'D_SCE.AFS\0'
    candidate={k:v for k,v in component.items() if k not in
        ('members','working_file_sha256','source_member_sha256','pending')}
    candidate.update(status='native-verified local component/executable candidate; test disc composition and gameplay pending',
        original_script_base=hex(SOURCE),english_heap_pointer_storage=hex(HEAP_POINTER),
        original_prefix_capacity=ORIGINAL_PREFIX_CAPACITY,combined_new_heap_bytes=patch['combined_heap_bytes'],
        native_verification={k:v for k,v in proof.items() if k!='native_formatter_VM_advance_cases'},
        pending=['Compose test disc and verify all inherited components with the new executable',
            'Verify actual emulator file I/O, allocation, cache behavior, save/load and event navigation',
            'Measure dialogue layout and preserve words/meaning during presentation reflow',
            'Full VM text coverage, 503 held rows and independent meaning review'])
    docpath=ROOT/'docs/scenario-format.json';doc=json.loads(docpath.read_text('utf-8'))
    doc.update(version=VERSION,status=candidate['status'])
    doc['english_insertion_candidate']=candidate
    doc['native_scenario_loader']={'original_entry_runtime':'8c088270','original_entry_file':'78270',
        'original_behavior':'Synchronous reader 8c021d9e with file ID 2 (filename table resolves D_SCE.AFS), selected member ID and caller destination; returns Boolean success.',
        'observed_caller_file_offsets':['30d52','315b6','6f984','83482','83718'],
        'original_script_pointer_global':'8c1dbf50','original_script_destination':'8c010080',
        'original_destination_initialization_file_offsets':['10352','10354','10356'],
        'source_prefix_reinstalled':'Native memcpy receives only the unchanged original member prefix, at the original address',
        'compressed_member_read':'Separate 64 KiB scratch; sector-rounded maximum 40,960 bytes',
        'separate_decoded_bank':'128 KiB; maximum member 76,568 bytes, bank pointer in final word',
        'code_storage':'Unused original arena tail after the largest source script; pointer at file83f0 and functions at8400,8800,8c00',
        'limit':'I/O, malloc, memcpy and cache implementations are stubbed in offline tests; game behavior remains unverified'}
    doc['reinsertion_research_hypothesis']['status']='Implemented as 0.1.7 candidate; full game testing and text coverage unfinished'
    doc['reinsertion_research_hypothesis']['approach']='A compressed member expands into a separate English bank. Its original VM prefix is copied to its original fixed address. The scenario-only formatter hook binary-searches original source offsets, formats English and returns original source consumption. Original next-opcode advancement is exercised independently through native phase instructions.'
    total=sum(proof[k] for k in ['SH4_initialization_instructions','SH4_loader_instructions',
        'SH4_lookup_instructions','SH4_formatter_VM_instructions','SH4_fallback_instructions'])
    entry=f'''## 0.1.7 — native story insertion candidate

- Compiled 50,273 complete English story commands into per-member banks. All 447 original VM prefixes remain byte-exact, including original branch operands, FE controls and command boundaries. Eight-byte lookup records retain separate original source lengths and English addresses; the working translation rows were not shortened, merged or split. The existing 503 held rows occupy 353 commands and retain original untranslated payloads, without replacement prose or added draft credit.
- Compressed each rebuilt member with the game's PRS format and repacked D_SCE.AFS into its original 4,079,616-byte extent, using 4,038,448 bytes with 41,168 spare. All 447 component round trips and indices pass; archive count and raw filename list are retained. Maximum packed member is 40,289 bytes (40,960 bytes read by sectors), and maximum decoded member is 76,568 bytes. This component requires the matching patched executable.
- Added a 196,608-byte heap for a 128 KiB English member and 64 KiB compressed scratch area. Original script bytes are copied back to the unchanged 8c010080 address. Hook code and its heap pointer occupy unused arena bytes beyond the largest original prefix; embedded program root data remains unchanged. The formatter lookup returns original source consumption, and the native dialogue allocation/limit expand together from 1,024/1,023 to 8,192/8,191 bytes. No new font textures or Japanese glyph slots.
- Native checks pass all 50,273 English lookups, 353 held-command original-stream fallbacks, 87 English formatting/source-count/next-opcode witnesses, nine PRS loading witnesses, a raw filename-list load, two other fallbacks, initialization and failed-read stale-bank clearing: {total:,} SH-4 instructions. The maximum witnessed formatted output is 1,411 bytes. Guards, callee-saved registers, original-address copies and next-opcode positions pass. File I/O, malloc, memcpy and cache operations are bounded stubs; their real implementations and full-game behavior remain separate unverified scopes.
- Saved only a local component/executable candidate, not a test disc or release. Test-disc composition, inherited-component checks, actual file loading/memory, save/load, event navigation, measured word/layout handling, full VM text coverage, held passages, meaning review and remaining image UI/movie text are unfinished.

'''
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8');marker='## 0.1.6 — English battle-message integration'
    assert marker in old and '## 0.1.7 —' not in old
    print(json.dumps(candidate,indent=2));print(entry)
    if args.write:
        docpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf-8')
        cp.write_text(old.replace(marker,entry+marker,1),'utf-8')
        component['kind']='native-verified compressed English story candidate; test disc/gameplay pending'
        component['pending']=candidate['pending']
        (out/'text/scenario-component-report.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
        patch['kind']='native-verified scenario executable candidate; test disc/gameplay pending'
        (out/'scenario-patch-report.json').write_text(json.dumps(patch,indent=2)+'\n','utf-8')
    print('Wrote scenario candidate evidence/docs/changelog.' if args.write else 'DRY RUN: no documentation changed.')


if __name__=='__main__':main()
