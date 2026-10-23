"""Record inspected English battle integration evidence/docs/changelog. Dry first."""
import argparse,json,re
from pathlib import Path
from build_battle_patch import compose,VERSION,ROOT
from build_battle_translation import digest
from build_font4x_patch import make_font,MEDIUM


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION;files,copied,manifest,component=compose()
    for name,raw in {**files,**copied}.items():assert (out/name).read_bytes()==raw,name
    disc=json.loads((out/'english-disc-report.json').read_text('utf-8'))
    proof=json.loads((out/'battle-english-native-test.json').read_text('utf-8'))
    assert disc['version']==VERSION and disc['validation']['reextracted_files']=='all 4 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    assert proof['component_sha256']==digest(copied['text/D_BMESS.en.dec.bin'])
    assert proof['executable_sha256']==digest(files['1ST_READ.BIN'])
    assert proof['text_spans_witnessed']==5516 and proof['condition_outcomes_witnessed']==412
    _,_,tables=make_font(Path('C:/Windows/Fonts/tahoma.ttf'))
    path=ROOT/'work/translation/en/battle/battle.json';working=json.loads(path.read_text('utf-8'))
    widths=[]
    for row in working:
        text=re.sub(r'<(?:FC:[^>]+|ASCII:(?:ON|OFF)|NL)>','',row['en'])
        width=sum(tables['medium'][MEDIUM.index(c)] for c in text)
        widths.append({'id':row['id'],'logical_advance_estimate':width})
    layout={'version':VERSION,'kind':'medium-font advance estimates; not measured in-game geometry',
        'translation_working_sha256':digest(path.read_bytes()),
        'physical_rows':len(widths),'over_256':sum(r['logical_advance_estimate']>256 for r in widths),
        'over_480':sum(r['logical_advance_estimate']>480 for r in widths),
        'over_512':sum(r['logical_advance_estimate']>512 for r in widths),
        'largest_rows':sorted(widths,key=lambda r:r['logical_advance_estimate'],reverse=True)[:12],
        'limits':['Actual battle window geometry is unmeasured','Estimates exclude runtime control expansion and glyph overhang/shadow',
                  'No translation was shortened or reflowed by this audit']}
    docpath=ROOT/'docs/battle-text-format.json';doc=json.loads(docpath.read_text('utf-8'))
    doc.update(version=VERSION,status='English first draft relocated and inserted in local test disc; meaning/state/layout/gameplay validation pending')
    doc['sizes'].update(english_decoded_bytes=component['output_decoded_bytes'],
        english_compressed_bytes=component['output_compressed_bytes'],english_native_allocation_bytes=0x50000,
        english_copy_tail_padding_bytes=component['copy_tail_padding_bytes'])
    doc['translation']['font_characters_pending']=[]
    doc['translation']['pending']='English first drafts are inserted in local0.1.6; independent meaning review, disputed names/source inconsistencies, preceding combat-state mapping and measured layout/gameplay remain pending.'
    doc['english_component']={k:v for k,v in component.items() if k not in ['record_relocations','span_relocations','pointer_relocations']}
    doc['english_native_verification']=proof
    doc['english_workspace']={'allocation_bytes':0x6800,'per_side_record_bytes':0x3000,
        'selected_output_offset':0x6000,'selected_output_bytes':0x800,
        'selected_calls':[0,1,2,3],'record_sides':[0,1,1,0],
        'four_call_phase_file_range':['0x1bb6c','0x1bbc6'],
        'allocation_copy_phase_file_range':['0x1ba48','0x1bad2'],
        'test_scope':'Phases executed separately; output-selection stubs force four maximum-size valid messages. All source selection paths are independently executed.',
        'maximum_single_output_bytes':413,'conservative_four_output_bytes':1652}
    doc['layout_advance_audit']={k:v for k,v in layout.items() if k not in ['largest_rows','translation_working_sha256']}
    changelog='''## 0.1.6 — English battle-message integration

- Relocated all 5,516 battle text spans: 6,979 nonempty first-draft rows plus 1,107 structural blanks. Rebuilt 7,232 self-relative pointer fields while retaining all 128 root slots/aliases, 94 physical records, weapon IDs/order, conditions, random alternatives and unreferenced programs. Per-page codec round trips, source fingerprints, graph edges and native pointer ranges pass. No dialogue was shortened to fit its old slot.
- English records occupy 308,368 bytes; an explicit 12,092-byte zero tail makes the final fixed-size record copy read initialized component data. Total decoded size is 320,460 bytes, compressed to 114,271. Expanded the native component allocation from 0x38000 to 0x50000. The largest record is 11,960 bytes, so both existing 0x3000 record-copy regions remain unchanged. The four-output workspace tail grows from 512 to 2,048 bytes (total allocation 0x6200 to 0x6800), covering the conservative 4×413-byte bound without shortening text. Both changed literals retain their native operand sizes/sign constraints.
- Native tests pass all 6,034 English selection cases, 128 root lookups, 256 workspace cases and the original PRS decoder: 17,337,982 SH-4 instructions. All spans and 412 condition outcomes have witnesses; raw outputs, return pointers and guards match. Workspace tests execute the allocation/copy and four-call phases separately, with selection stubs forcing four maximum-length outputs. The selection loop is tested independently on every original path. Preceding battle-state mapping, the RNG implementation, display layout and gameplay are separate unverified scopes.
- Composed the updated executable/data with the existing 0.1.5 native font, menu/name and encyclopedia components. Built the local 0.1.6 test disc, relocating D_NAMES and D_BMESS into distinct verified zero areas and updating both-endian directory fields. All four patched files re-extract exactly; 154 changed sectors across two tracks pass EDC/ECC, and unrelated ISO entries stay unchanged. Prior builds and the original dump are untouched; no GitHub release.
- A preliminary medium-font advance audit finds two battle rows above 512 logical pixels and nine above 480. Actual battle-window geometry, control expansion and glyph overhang remain unmeasured, so this is a layout warning, not a fit claim. Translation wording and source row boundaries remain unchanged. Story insertion, held passages, meaning review, full VM coverage, image UI/movie audit and live battle/navigation/memory checks remain unfinished.

'''
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8');marker='## 0.1.5 — native font symbols and space fix'
    assert marker in old and '## 0.1.6 —' not in old
    print('Component:',component['stage']);print('Layout estimates:',json.dumps(layout,indent=2));print(changelog)
    if args.write:
        (out/'text/battle-component-report.json').write_text(json.dumps(component,indent=2),'utf-8')
        (out/'battle-layout-audit.json').write_text(json.dumps(layout,indent=2),'utf-8')
        docpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf-8')
        cp.write_text(old.replace(marker,changelog+marker,1),'utf-8')
    print('Wrote inspected battle evidence/docs/changelog.' if args.write else 'DRY RUN: no documentation changed.')


if __name__=='__main__':main()
