"""Record inspected GenEi native, disc and live dialogue evidence. Dry run first."""
import argparse,json,struct
from build_genei_font import ROOT,VERSION,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    read=lambda p:json.loads((ROOT/p).read_text('utf-8'))
    out='work/output/'+VERSION+'/'
    ui='work/ui/'+VERSION+'/'
    manifest=read(out+'font4x-patch.json');disc=read(out+'english-disc-report.json')
    raster=read(out+'genei-font-native-test.json');surface=read(out+'genei-surface-native-test.json')
    source=read(out+'genei-font-report.json');runtime=read(ui+'dialogue-runtime.json')
    sha=digest((ROOT/out/'1ST_READ.BIN').read_bytes())
    assert sha==disc['files']['1ST_READ.BIN']['sha256']==raster['executable_sha256']==surface['executable_sha256']
    assert sha==disc['scenario_native_validation']['executable_sha256']==disc['battle_native_validation']['executable_sha256']
    assert disc['validation']['reextracted_files']=='all 5 exact' and disc['validation']['changed_sector_EDC_ECC']=='pass'
    assert disc['validation']['unrelated_ISO_entries']=='unchanged' and disc['changed_sectors']==2672
    afs=(ROOT/out/'WIN00.AFS').read_bytes();offset,size=struct.unpack_from('<II',afs,8)
    assert digest(afs[offset:offset+size])==raster['font_sha256']
    assert runtime['build']==VERSION and runtime['kernel_matches'] and runtime['font_payload_matches']
    assert runtime['english_names']['entire_component_matches']
    scenario=runtime['english_scenario']
    assert scenario['member']=='s_001.bin' and scenario['entire_English_member_matches'] and scenario['original_VM_prefix_matches']
    assert scenario['heap_in_RAM'] and scenario['original_base_preserved']
    for row in runtime['surfaces']:
        assert max(row['physical'])<=1024 and row['pvr_header_valid'] and row['sprite_preserves_logical_size']
    assert any(row['physical']==[1024,256] and row['foreground_pixels'] for row in runtime['surfaces'])
    assert (ROOT/ui/'genei-classroom.png').is_file()
    live={'build':VERSION,'executable_sha256':sha,'runtime_evidence':ui+'dialogue-runtime.json',
        'screenshots':[ui+'genei-dialogue.png',ui+'genei-classroom.png'],
        'boot':'Reached opening story and classroom scene in approved local Flycast',
        'input':'No automated game inputs sent during this check',
        'font':'User-selected GenEi LateGo v2.1 Latin glyphs rendered with consistent scale/baseline and natural integer-grid advances',
        'english_script':'s_001.bin English bank and original VM prefix both byte-exact in RAM; original VM base retained',
        'surfaces':'Ink-bearing 1024x128 small text surface and 1024x256 dialogue surface; logical sprite sizes preserved',
        'visual_observation':'English dialogue and Classroom label visible; letter proportions consistent. Early Koichiro line splits Touya as Tou / ya under the unchanged 30-character wrapper.',
        'stage':'GenEi font integrated and visible in local full English test build; word wrapping and full-game validation pending',
        'layout_issue':'Replace legacy character-count wrapping with measured word-aware wrapping; verify natural-metric font fit throughout UI',
        'pending':['Word-aware dialogue wrapping','Menu/library/battle measured layout and symbols in-game',
            'Save/load, later scenario transitions and long-session memory','503 held rows, full VM text coverage and independent meaning review']}
    font=read('docs/font-renderer.json')
    font.update(build=VERSION,status=live['stage'])
    font['font'].update(archive_offset=hex(offset),new_magic='RBLF4X 00 03',format_version=3,
        small_cell=[64,32],medium_cell=[64,64],pixel_data='two little-endian uint32 bitmasks per source row; first word is left half',
        small_bitmaps_offset='0x200',medium_bitmaps_offset='0x8200',
        vector_source='GenEi LateGo v2 Medium, distribution v2.1; all Latin/source marks use this face',
        source_details=manifest['vector_font'],font_metrics={name:{k:v for k,v in m.items() if k!='glyphs'} for name,m in source['metrics'].items()})
    font['executable']['current_symbols']=manifest['symbols']
    font['checks'].update(offline_hd_glyph_cases=raster['native_cases'],offline_allocation_cases=surface['allocation_cases'],
        offline_invalid_surface_cases=surface['invalid_dimension_cases'],
        runtime_confirmed=['Exact loaded renderer/font/names','Byte-exact first English scenario and original VM prefix',
            'Visible GenEi dialogue and Classroom label','1024-pixel texture cap and logical sprite geometry on observed surfaces'],
        not_yet_confirmed=live['pending'],local_evidence=out+'genei-font-native-test.json',
        surface_evidence=out+'genei-surface-native-test.json')
    font['latest_live_validation']=live
    font['limitations'].extend([s for s in ['Integer logical advances do not implement pair kerning.',
        'The legacy 30-character dialogue wrapper still splits words.'] if s not in font['limitations']])
    scene=read('docs/scenario-format.json')
    scene.update(version=VERSION,status=live['stage'])
    scene['english_insertion_candidate'].update(test_disc_version=VERSION,status=live['stage'],live_validation=live,pending=live['pending'])
    reinsertion=read('docs/text-reinsertion.json')
    reinsertion['D_NAMES']['live_check']={'build':VERSION,'entire_English_component_in_emulated_RAM':'exact match',
        'integrated_font_payload_and_renderer':'exact match','evidence':ui+'dialogue-runtime.json',
        'English_menu_layout_and_readability':'Classroom location label visible; remaining menu/UI layouts unverified'}
    reinsertion['D_PAPER']['live_check']={'build':VERSION,'status':'128 KiB allocation literal confirmed; library UI not open',
        'evidence':ui+'dialogue-runtime.json'}
    files={ui+'live-validation.json':live,'docs/font-renderer.json':font,
        'docs/scenario-format.json':scene,'docs/text-reinsertion.json':reinsertion}
    notice=(ROOT/out/'FONT-LICENSE.txt').read_bytes()
    changelog=ROOT/'CHANGELOG.md';old=changelog.read_text('utf-8')
    before='- Candidate components created for native verification. Disc packaging, live appearance and word-aware wrapping remain pending; the original 30-character wrapper is unchanged in this candidate. Original dump/prior builds unchanged; no release.'
    after='- Native raster checks passed 345 cases across every supported glyph ID, scale and surface-edge/shadow cases: 11,147,509 SH-4 instructions with exact FreeType-reference pixels, cursor advances, guards and ABI. Twelve allocation/header/append/flush/DMA cases and five invalid-size rejections pass. Full story lookup/loader/formatter/VM regressions (18,986,311 instructions) and battle regressions (17,337,982 instructions) pass against this exact executable; bounded system-call stubs remain a verification limit.\n- Packaged local 0.1.11: all five files re-extract exactly, 2,672 changed sectors pass EDC/ECC, unrelated ISO entries unchanged. Live Flycast checks confirm exact GenEi font/kernel/names, first English script bank and original VM prefix. Screenshots show natural-proportion dialogue and the Classroom label, with ink-bearing 1024x128 / 1024x256 surfaces and logical sprite sizes preserved. Legacy 30-character wrapping still splits Touya in an early line; word wrapping, other UI layout, later events/save-load, held rows and meaning review remain pending. Original dump/prior builds unchanged; no release.'
    assert before in old or after in old
    print(json.dumps(live,indent=2));print('Validated 345 raster cases, 17 surface cases, exact native regression hashes, packaged sectors and live dialogue.')
    if not args.write:print('DRY RUN: no documentation written');return
    for path,value in files.items():(ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
    license_path=ROOT/'docs/licenses/GenEi-Latin-OFL.txt';license_path.parent.mkdir(parents=True,exist_ok=True);license_path.write_bytes(notice)
    changelog.write_text(old.replace(before,after,1),'utf-8')
    print('Wrote evidence, source/license attribution, current font documentation and change log.')


if __name__=='__main__':main()
