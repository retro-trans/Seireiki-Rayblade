"""Record inspected 0.1.12 word-wrap packaging/native/live evidence."""
import argparse,json
from build_word_wrap_story import ROOT,VERSION,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    read=lambda p:json.loads((ROOT/p).read_text('utf-8'))
    out='work/output/'+VERSION+'/';ui='work/ui/'+VERSION+'/'
    component=read(out+'text/scenario-component-report.json');manifest=read(out+'font4x-patch.json')
    native=read(out+'scenario-native-test.json');wrap=read(out+'word-wrap-native-test.json')
    disc=read(out+'english-disc-report.json');runtime=read(ui+'dialogue-runtime.json')
    exe_sha=digest((ROOT/out/'1ST_READ.BIN').read_bytes())
    archive_sha=digest((ROOT/out/'D_SCE.AFS').read_bytes())
    assert exe_sha==native['executable_sha256']==wrap['executable_sha256']==disc['files']['1ST_READ.BIN']['sha256']
    assert archive_sha==native['archive_sha256']==wrap['archive_sha256']==component['archive_sha256']
    assert native['native_lookup_cases']==component['english_commands']==50273
    assert wrap['counts']['wrapped']==component['word_wrap']['word_wrapped_commands']==50107
    assert wrap['counts']['special_control_fallbacks']==166 and component['word_wrap']['forced_word_breaks']==0
    assert native['native_loader_cases']==13 and native['held_original_stream_cases']==353
    assert disc['validation']['reextracted_files']=='all 5 exact' and disc['validation']['changed_sector_EDC_ECC']=='pass'
    assert disc['validation']['unrelated_ISO_entries']=='unchanged' and disc['changed_sectors']==2666
    assert runtime['build']==VERSION and runtime['kernel_matches'] and runtime['font_payload_matches']
    story=runtime['english_scenario']
    assert story['member']=='s_001.bin' and story['entire_English_member_matches'] and story['original_VM_prefix_matches']
    assert all(h['matches'] for h in story['native_hook_checks']) and len(story['native_hook_checks'])==2
    assert story['word_wrapped_commands_in_bank']==126 and story['special_control_commands_in_bank']==1
    assert story['heap_in_RAM'] and story['original_base_preserved']
    assert all(max(s['physical'])<=1024 and s['pvr_header_valid'] and s['sprite_preserves_logical_size'] for s in runtime['surfaces'])
    screenshot=ui+'word-wrap-teacher.png';assert (ROOT/screenshot).is_file()
    pending=['Decode and fit the 166 special-display-control English commands',
        'Measure library/battle/menu layouts and review continuation-icon spacing',
        'Later scenario transitions, save/load and long-session memory checks',
        '503 held story rows, full VM text coverage, independent meaning review and remaining image UI/movie text']
    live={'build':VERSION,'executable_sha256':exe_sha,'archive_sha256':archive_sha,
        'runtime_evidence':ui+'dialogue-runtime.json','screenshot':screenshot,
        'stage':'Measured word wrapping inserted for 50,107 ordinary story commands; opening dialogue observed in-game; special-control layouts and full-game validation pending',
        'layout_issue':pending[0],
        'boot':'Opening story and classroom reached in approved local Flycast',
        'native_hooks':'Loaded RBS2 loader and RBSCEN02 formatter bytes match exact candidate',
        'script_bank':'s_001 bank byte-exact, including 126 wrapped entries and one special-control entry; original VM prefix/address retained',
        'visual_observation':'Opening teacher-warning dialogue breaks at spaces and keeps Touya together; a later display page was loaded while the original VM advanced. This does not prove every command or continuation prompt.',
        'input':'No successful automated game-button sequence claimed; live scene advanced externally',
        'pending':pending}
    component['kind']='native-verified word-wrap component; opening bank checked live, full-game validation pending'
    component['word_wrap']['native_verification']='All compiled payloads/flags/line metrics checked; 50,273 native lookups, 87 formatter/VM and 14 pagination witnesses pass'
    component['word_wrap']['live_verification']='Opening s_001 bank and word breaks observed; other commands/UI remain unverified'
    component['pending']=pending
    manifest['scenario']['word_wrap']=component['word_wrap']
    manifest['status']=live['stage']
    disc['scenario']['word_wrap']=component['word_wrap']
    evidence={'version':VERSION,'executable_sha256':exe_sha,'archive_sha256':archive_sha,
        'font_sha256':wrap['font_sha256'],'word_wrap':component['word_wrap'],
        'native_lookup_cases':native['native_lookup_cases'],'native_loader_cases':native['native_loader_cases'],
        'native_formatter_VM_cases':len(native['native_formatter_VM_advance_cases']),
        'native_pagination_cases':wrap['native_pagination_cases'],'all_compiled_lines_checked':wrap['counts']['lines'],
        'maximum_formatted_bytes':native['maximum_formatted_bytes'],'archive_spare_bytes':component['spare_archive_bytes'],
        'dynamic_PRS_members':component['dynamic_PRS_members'],
        'scope':'All command banks and line metrics checked in Python; native lookup executed on every entry, native formatting/VM advancement on 87 cases, native pagination on 14 witnesses. File I/O/allocation/cache remain bounded stubs offline; one opening bank checked live.',
        'live_validation':live,'pending':pending}
    doc=read('docs/scenario-format.json');doc.update(version=VERSION,status=live['stage'])
    candidate={k:v for k,v in component.items() if k not in ('members','working_file_sha256','source_member_sha256')}
    candidate.update(kind='native-verified word-wrap test-disc candidate; limited opening runtime evidence',
        status=live['stage'],test_disc_version=VERSION,original_script_base='0x8c010080',
        english_heap_pointer_storage='0x8c0183f0',combined_new_heap_bytes=196608,
        native_verification={k:v for k,v in native.items() if k!='native_formatter_VM_advance_cases'},
        live_validation=live,pending=pending)
    doc['english_insertion_candidate']=candidate
    doc['word_wrapping']=evidence
    doc['native_scenario_loader']['limit']='RBS2 file loading and RBSCEN02 English bank verified live for opening s_001; later transitions, save/load and full-game memory remain unverified'
    doc['native_scenario_loader']['packed_header_magic']='RBS2'
    doc['native_scenario_loader']['decoded_bank_magic']='RBSCEN02'
    reinsertion=read('docs/text-reinsertion.json')
    reinsertion['D_SCE']={k:v for k,v in evidence.items() if k not in ('word_wrap','live_validation')}
    reinsertion['D_SCE']['word_wrap_summary']={k:v for k,v in component['word_wrap'].items() if k!='special_control_fallbacks'}
    font=read('docs/font-renderer.json')
    font['latest_word_wrap_build']={'build':VERSION,'font_payload':'byte-exact 0.1.11 GenEi bank; font drawing unchanged',
        'native_raster_cases':345,'surface_cases':17,'executable_sha256':exe_sha,
        'word_wrap_evidence':'docs/word-wrapping.json','runtime_evidence':ui+'dialogue-runtime.json'}
    font['limitations']=[s for s in font['limitations'] if s!='The legacy 30-character dialogue wrapper still splits words.']
    font['limitations'].append('0.1.12 prewraps 50,107 ordinary story commands; 166 special-control commands and non-story UI layout still need work.')
    geometry={'build':VERSION,'reference_screenshot':screenshot,'game_image_size':[640,480],
        'window_image_size':[642,512],'game_image_origin_in_window':[1,31],
        'regions':[{'id':'story.dialogue','target_logical_pen_width':236,'target_logical_ink_width':240,
            'reference_text_region_game_pixels':[128,352,480,96],
            'geometry_scope':'Ordinary opening bottom dialogue; reference region derived from visible inset and 2x logical-to-screen scale; not a universal UI measurement'}],
        'pending':['Exact continuation-icon gap','Special display controls','Library/battle/menu geometry']}
    files={ui+'live-validation.json':live,ui+'dialogue-layout.json':geometry,'docs/scenario-format.json':doc,
        'docs/text-reinsertion.json':reinsertion,'docs/font-renderer.json':font,'docs/word-wrapping.json':evidence}
    files.update({out+'text/scenario-component-report.json':component,out+'font4x-patch.json':manifest,
        out+'english-disc-report.json':disc})
    changelog=ROOT/'CHANGELOG.md';old=changelog.read_text('utf-8')
    before='- Candidate archive/executable prepared for native verification. GenEi glyphs, font renderer, ordered WIN00 layout, menu/name/library/battle payloads and allocations are retained. Packaging, live fit, special-control layout, full VM coverage, held passages, independent meaning review and remaining image UI/movie text are unfinished. Original dump/prior builds unchanged; no release.'
    after='- Verified all 50,273 rebuilt payloads/lookup flags against measured reference and checked 122,286 ordinary line segments. Native checks pass all 50,273 lookups, 13 PRS loading witnesses including all four dynamically compressed members, 353 held-command fallbacks, 87 formatter/source-count/VM advancement cases and 14 pagination witnesses. Raster (345 cases), surface helpers (17 cases) and full battle regressions pass against the new executable. Bounded system-call stubs and limited native formatting witnesses remain scope limits.\n- Packaged local 0.1.12: all five files re-extract exactly, 2,666 changed sectors pass EDC/ECC, unrelated ISO entries unchanged. Live checks confirm both new story hooks, exact opening RBSCEN02 bank (126 wrapped entries, one special-control entry), original VM prefix/address, GenEi font and observed texture/sprite sizes. Opening dialogue now breaks at spaces and keeps Touya together. Special-control layouts, non-story UI and continuation-icon spacing, later events/save-load, full VM coverage, held passages, meaning review and remaining image UI/movie text remain unfinished. Original dump/prior builds unchanged; no release.'
    assert before in old or after in old
    print(json.dumps(live,indent=2));print('Validated native/packaging/live evidence; document targets:',list(files))
    if not args.write:print('DRY RUN: no documentation written');return
    for path,value in files.items():(ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
    changelog.write_text(old.replace(before,after,1),'utf-8')
    print('Wrote word-wrap evidence, UI reference geometry, documentation and change log.')


if __name__=='__main__':main()
