"""Record packaged embedded-dialogue coverage and native evidence. Dry first."""
import argparse,json
from build_embedded_dialogue_patch import ROOT,VERSION,PRIOR,compose,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION;read=lambda p:json.loads(p.read_text('utf-8'))
    files,_,component=compose()
    for name in ('1ST_READ.BIN','WIN00.AFS','D_SCE.AFS','text/D_NAMES.BIN','text/D_PAPER.BIN','text/D_BMESS.BIN'):
        assert files[name]==(out/name).read_bytes()
    names=['embedded-dialogue-native-test','genei-font-native-test','genei-surface-native-test','ui-layout-native-test','word-wrap-native-test','inline-control-native-test','library-layout-native-test','library-header-native-test','scenario-native-test','battle-english-native-test','chapter-card-native-test','ui-image-native-test']
    proofs={name:read(out/(name+'.json')) for name in names};sha=digest(files['1ST_READ.BIN'])
    assert all(p['executable_sha256']==sha for p in proofs.values())
    native=proofs['embedded-dialogue-native-test'];disc=read(out/'english-disc-report.json');manifest=read(out/'font4x-patch.json')
    assert native['commands']==13 and native['native_formatter_VM_cases']==52 and native['native_parser_commands']==13 and native['native_fallback_cases']==2
    assert disc['files']['1ST_READ.BIN']['sha256']==sha and disc['validation']=={'reextracted_files':'all 5 exact','changed_sector_EDC_ECC':'pass','unrelated_ISO_entries':'unchanged','in_game':'pending'}
    summary=read(ROOT/'work/source/scenario-text/summary.json');review=read(ROOT/'docs/scenario-marker-review.json')
    assert not summary['issues'] and len(summary['native_resolved_operand_markers'])==2
    record={'version':VERSION,'source_build':PRIOR,'status':'13 embedded executable dialogue commands integrated and packaged; native formatting/VM advance/layout and broad regressions pass; live display and full coverage pending',
        'commands':13,'new_story_library_draft_credit':0,'English_source':'Existing byte-identical s_000/s_05d/s_087 drafts; context reviewed for same speakers and hint/event purposes','translation_map':'work/translation/en/ui/embedded-dialogue.en.json','dispatcher':component['dispatcher_address'],'dispatcher_bytes':component['dispatcher_bytes'],'static_English_bytes':component['english_payload_bytes'],'executable_changed_bytes':component['changed_bytes'],
        'original_commands_branch_addresses_story_helpers_allocations':'unchanged','native_formatter_VM_cases':52,'native_parser_commands':13,'native_fallback_cases':2,'maximum_formatted_bytes':native['maximum_formatted_bytes'],'native_instructions':native['native_instructions'],
        'proof':f'work/output/{VERSION}/embedded-dialogue-native-test.json','regression_proofs':{n:f'work/output/{VERSION}/{n}.json' for n in names},'preview':f'work/output/{VERSION}/embedded-dialogue-preview.png','component':f'work/output/{VERSION}/embedded-dialogue-component.json',
        'resolved_operand_markers':{'proof':'docs/scenario-marker-review.json','count':2,'native_instructions':review['native_instructions'],'source_blocks_unchanged':summary['blocks'],'physical_rows_unchanged':summary['physical_rows']},
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi','packaging':disc['validation'],'limits':native['limits']}
    results={ROOT/'docs/embedded-dialogue.json':record}
    manifest.update(status=record['status'],native_proof_reuse={'source_build':PRIOR,'scope':'All archives/font/text components byte-exact; all mandatory native suites freshly executed against 0.1.21, with every story lookup routed through the new entry'})
    manifest['embedded_dialogue'].update(packaging=disc['validation'],pending=['Live embedded dialogue, callbacks/timing and full VM/native text coverage'])
    manifest['ui_images']['native_regression_build']=VERSION
    manifest['antialias_font'].update(raster_proof_sha256=digest((out/'genei-font-native-test.json').read_bytes()),surface_proof_sha256=digest((out/'genei-surface-native-test.json').read_bytes()))
    results[out/'font4x-patch.json']=manifest
    p=ROOT/'docs/translation-status.json';d=read(p);d.update(version=VERSION,stage='English embedded affection hints/event copies now inserted alongside drafted story/library/battle/UI and image labels; held passages, independent review, other images/movies and full-game validation incomplete',latest_embedded_dialogue_build=record)
    d['test_disc'].update(version=VERSION,path=record['disc'],changed_sectors=disc['changed_sectors'],validation=disc['validation'])
    d['story']['source_review_items']=[];d['story']['resolved_source_operand_markers']=record['resolved_operand_markers'];d['story']['embedded_executable_commands']=13
    d['story']['inserted_commands_by_storage']={'D_SCE_complete_commands':manifest['scenario']['english_commands'],'embedded_executable_commands':13,'draft_credit':'No added source-row credit for embedded duplicates'}
    results[p]=d
    p=ROOT/'docs/scenario-format.json';d=read(p);d['candidate_inline_text']['review_items']=[];d['candidate_inline_text']['native_operand_marker_resolutions']=record['resolved_operand_markers'];d['latest_embedded_dialogue_build']=record;results[p]=d
    p=ROOT/'docs/text-reinsertion.json';d=read(p);d['embedded_executable_dialogue']=record;results[p]=d
    p=ROOT/'CHANGELOG.md';log=p.read_text('utf-8');before='Native embedded-dialogue and changed-executable regressions, packaging and live checks are pending.'
    after=f"Native checks pass 52 cold/warm direct/VM formatter cases, all 13 parsed command layouts and two unmatched-pointer fallbacks, preserving source consumption, ABI and guards. All mandatory font/UI/library/header/story/battle/image/chapter suites were freshly rerun for this executable; all story lookups pass through the new entry. Local packaging re-extracts all five files exactly, validates {disc['changed_sectors']:,} changed sectors and preserves unrelated ISO entries. Live embedded dialogue remains unverified."
    assert before in log or after in log
    print(json.dumps(record,indent=2))
    if not args.write:print('DRY RUN: no documentation written');return
    for p,d in results.items():p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
    (ROOT/'CHANGELOG.md').write_text(log.replace(before,after,1),'utf-8')
    p=out/'READ-ME.txt';note='\n0.1.21 translates 13 previously missed executable-embedded dialogue commands using existing story drafts. Original command addresses/bytes, branch targets, source consumption, story helpers, allocations and all archives stay unchanged. Native lookup/pagination/VM/layout and broad regression checks pass; actual embedded-dialogue appearance/callbacks/timing and full translation validation remain pending.\n'
    if note.strip() not in p.read_text('utf-8'):p.write_text(p.read_text('utf-8')+note,'utf-8')
    print('Recorded embedded dialogue insertion, marker resolutions, fresh native regressions and packaged disc.')


if __name__=='__main__':main()
