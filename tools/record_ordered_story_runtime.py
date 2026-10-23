"""Record inspected 0.1.10 first-dialogue evidence. Dry run by default."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.10'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    read=lambda p:json.loads((ROOT/p).read_text('utf-8'))
    out='work/output/'+VERSION+'/'
    ui='work/ui/'+VERSION+'/'
    disc=read(out+'english-disc-report.json')
    runtime=read(ui+'dialogue-runtime.json')
    repack=read(out+'archive-repack-report.json')
    assert disc['version']==runtime['build']==VERSION
    assert disc['validation']['reextracted_files']=='all 5 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    assert disc['validation']['unrelated_ISO_entries']=='unchanged'
    assert disc['changed_sectors']==2664
    for name in ('1ST_READ.BIN','WIN00.AFS','D_SCE.AFS'):
        assert hashlib.sha256((ROOT/out/name).read_bytes()).hexdigest()==disc['files'][name]['sha256']
    assert runtime['kernel_matches'] and runtime['font_payload_matches']
    assert runtime['english_names']['entire_component_matches']
    scenario=runtime['english_scenario']
    assert scenario['member']=='s_001.bin' and scenario['english_commands']==127
    assert scenario['heap_in_RAM'] and scenario['original_base_preserved']
    assert scenario['entire_English_member_matches'] and scenario['original_VM_prefix_matches']
    assert runtime['english_library']['allocation_literal_matches']
    assert (ROOT/ui/'first-dialogue.png').is_file()
    for surface in runtime['surfaces']:
        assert max(surface['physical'])<=1024 and surface['pvr_header_valid']
        assert surface['sprite_preserves_logical_size']
    live={'build':VERSION,'executable_sha256':disc['files']['1ST_READ.BIN']['sha256'],
        'runtime_evidence':ui+'dialogue-runtime.json','screenshot':ui+'first-dialogue.png',
        'boot':'opening movie, title and first story dialogue reached in approved local Flycast',
        'input':'User advanced to first dialogue; no successful automated controller sequence claimed',
        'english_script':'s_001.bin: entire decoded English member and original VM prefix match expected bytes',
        'font':'Integrated kernel and font payload match; current dialogue surface is 1024x256 for 512x64 logical pixels (2x horizontal, 4x vertical)',
        'visual_observation':'Readable English greeting; Kazami splits as Ka / zami after legacy 30-character wrap',
        'font_quality_issue':'Tahoma Regular contours were independently resized into each legacy glyph ink box; this distorts proportions and spacing. Replace per-glyph stretching with consistent font metrics.',
        'library':'128 KiB allocation literal confirmed; library not open, so loaded library contents/navigation unverified',
        'pending':['Natural glyph proportions and spacing','Word-aware measured dialogue wrapping',
            'Library and battle screen navigation/layout','Save/load and later scenario transitions',
            'Full VM text coverage, 503 held rows and independent meaning review']}
    scene=read('docs/scenario-format.json')
    scene['version']=VERSION
    scene['status']='packaged full story candidate boots and displays first English dialogue; font/layout and full-game checks pending'
    scene['english_insertion_candidate']['status']=scene['status']
    scene['english_insertion_candidate']['test_disc_version']=VERSION
    scene['english_insertion_candidate']['live_validation']=live
    scene['english_insertion_candidate']['pending']=live['pending']
    scene['native_scenario_loader']['limit']='Actual first scenario load and byte-exact original prefix/English bank verified in Flycast; later transitions, save/load and full-game memory remain unverified'
    text=read('docs/text-reinsertion.json')
    library=text['D_PAPER']
    library['archive_relocation']={'build':VERSION,'member_offset':1155072,
        'destination':'All 90 members repacked in index order from 0x70000, with sector-aligned non-overlapping extents',
        'archive_size':'unchanged','unrelated_members':'All 90 member payload bytes and IDs unchanged from 0.1.7; offsets updated',
        'evidence':out+'archive-repack-report.json',
        'superseded_layout':'The old 0x800 library placement before member zero reproduced a startup exception with the known-booting 0.1.3 executable; ordered archive comparison reached title'}
    library['insertion']='Included in 0.1.10; startup fixed, library navigation/layout still unverified'
    library['live_check']={'build':VERSION,'status':'startup and allocation checked; library UI not opened',
        'allocation_bytes':runtime['english_library']['loaded_allocation_literal'],
        'evidence':ui+'dialogue-runtime.json'}
    font=read('docs/font-renderer.json')
    font['latest_live_validation']=live
    changes=ROOT/'CHANGELOG.md'
    changelog=changes.read_text('utf-8')
    old='- Full-build 0.1.10 packaging and gameplay/layout/save-load validation remain pending.'
    new='- Full-build 0.1.10 packaged successfully: all five files re-extract exactly, 2,664 changed sectors pass EDC/ECC, unrelated ISO entries unchanged. User advanced to the first story dialogue. Live read-only checks confirm exact English s_001 member, original VM prefix/address, names, font kernel/payload and 128 KiB shared-allocation literal. The visible English greeting uses a 1024x256 surface (2x horizontal, 4x vertical, within the cap). First-dialogue screenshot exposes mid-word Kazami wrapping; font review identifies independently stretched Tahoma glyphs. Font proportions/spacing, word wrapping, later transitions, library/battle screens and save/load remain unfinished.'
    assert old in changelog or new in changelog
    changelog=changelog.replace(old,new,1)
    files={ui+'live-validation.json':live,'docs/scenario-format.json':scene,
        'docs/text-reinsertion.json':text,'docs/font-renderer.json':font}
    print(json.dumps(live,indent=2))
    print('Validated packaging hashes, first-scenario bytes, font payload, surfaces and saved screenshot.')
    print('Documents:',', '.join(files),'and CHANGELOG.md')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for name,value in files.items():
        (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
    changes.write_text(changelog,'utf-8')
    print('Wrote inspected runtime evidence and documentation.')


if __name__=='__main__':
    main()
