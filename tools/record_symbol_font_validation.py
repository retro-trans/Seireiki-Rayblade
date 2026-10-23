"""Record inspected 0.1.5 font evidence/docs/changelog. Dry first."""
import argparse,copy,hashlib,json
from pathlib import Path
from build_symbol_font_patch import compose
from build_font4x_patch import ROOT,VERSION,SMALL,MEDIUM,SYMBOLS,SYMBOL_FONT


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');args=ap.parse_args()
    folder=ROOT/'work/output'/VERSION
    files,copied,_,manifest,report=compose(Path('C:/Windows/Fonts/tahoma.ttf'),SYMBOL_FONT)
    for name,raw in {**files,**copied}.items():assert (folder/name).read_bytes()==raw,name
    disc=json.loads((folder/'english-disc-report.json').read_text('utf-8'))
    assert disc['version']==VERSION and disc['validation']['reextracted_files']=='all 3 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    native=(ROOT/'work/font-0.1.5-native.log').read_text('utf-8')
    symbols=(ROOT/'work/font-0.1.5-symbols.log').read_text('utf-8')
    assert '241 HD glyph cases; 12 allocation/header/flush/DMA cases; 3,692,685' in native
    assert '60 symbol cases through original parser and native raster, 60 mode toggles; 812,754' in symbols
    codec=(ROOT/'work/font-0.1.5-codecs.log').read_text('utf-8')
    assert '88 PRS boundary/overlap/window cases, 18 English mode/control/repertoire round trips, 3 byte fixtures and 6 rejection cases.' in codec
    validation={'version':VERSION,'kind':'offline native font and parser execution; not gameplay',
                'glyph_cases':241,'allocation_header_flush_DMA_cases':12,'invalid_surface_cases':5,
                'symbol_parser_raster_cases':60,'ASCII_mode_toggle_cases':60,
                'codec_roundtrips':18,'codec_byte_fixtures':3,'codec_rejections':6,
                'SH4_instructions':3692685+812754,'Latin_shapes_unchanged':190,
                'Latin_advances_unchanged':191,'small_space':'blank; overlapping legacy table fixed',
                'maximum_texture_edge':1024,'native_parser_and_font_hooks_match_tested_code':True,
                'font_member_and_executable_sha256':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
                'disc_checks':disc['validation'],'pending':['Live 0.1.5 symbol rendering and memory checks',
                    'Story/battle relocation and insertion','Independent meaning review and full VM coverage']}
    docpath=ROOT/'docs/font-renderer.json';doc=json.loads(docpath.read_text('utf-8'))
    historical=doc.get('historical_runtime_evidence') or {
        'build':doc['build'],'confirmed':doc['checks'].get('runtime_confirmed',[]),
        'local_evidence':doc['checks'].get('local_evidence')}
    doc.update(build=VERSION,status='local native symbol-font update; offline tests pass, live 0.1.5 validation pending',
               historical_runtime_evidence=historical)
    f=doc['font'];f.update(new_magic='RBLF4X 00 02',format_version=2,
        glyph_count_per_size={'small':len(SMALL),'medium':len(MEDIUM)},
        character_set='95 printable ASCII characters plus five protected source marks; original medium Latin IDs preserved',
        small_bitmaps_offset='0x200',medium_bitmaps_offset='0x4200',
        symbol_characters=SYMBOLS,
        small_symbol_bytes={c:hex(32+SMALL.index(c)) for c in SYMBOLS},
        medium_symbol_ids={c:MEDIUM.index(c) for c in SYMBOLS},
        vector_source='local Windows Tahoma plus Segoe UI Symbol for double-angle marks; no vector font files copied',
        model_code_dash='U+30FC stays distinct in text; uses an em-dash vector contour; no Japanese text bank',
        legacy_space_fix='128-byte medium advance table at0xa0 overlapped old small bitmap0x100; new bitmap0x200 is disjoint')
    doc['surfaces']['physical_scale_per_axis']='largest power of two up to4 for which logical dimension times scale is <=1024'
    doc['surfaces']['invalid_dimensions']='zero or >1024 logical dimensions return allocation failure without allocating'
    doc['surfaces']['examples']=[{'logical':[256,64],'maximum_physical':[1024,256]},
        {'logical':[512,64],'maximum_physical':[1024,256]},
        {'logical':[1024,32],'maximum_physical':[1024,128]}]
    doc['checks'].update(offline_hd_glyph_cases=241,offline_allocation_cases=12,
        offline_invalid_surface_cases=5,native_symbol_parser_cases=60,native_ASCII_mode_toggles=60,
        runtime_confirmed=[],local_evidence='work/output/0.1.5/font-native-validation.json',
        not_yet_confirmed=['Live 0.1.5 symbol rendering','Full English dialogue pages',
                          'Menu/encyclopedia measured layout','Long-session memory behavior'])
    doc['executable']['current_symbols']=manifest['symbols']
    changelog='''## 0.1.5 — native font symbols and space fix

- Added five protected source marks to both native font sizes: double-angle marks, heart, music note and model-code dash. Existing Latin IDs and all 191 advances are preserved. The small/ASCII symbol bytes are 0x7f–0x83; medium symbol IDs are 96–100. Control codes and mode toggles stay intact. The protected U+30FC model mark keeps its identity and uses an em-dash contour. No Japanese text bank or emulator texture replacement.
- Fixed an existing overlap between the medium advance table and the small space bitmap. Moved bitmap storage to 0x200/0x4200 in the same 99,072-byte font member; the small space is now blank. All 190 other Latin shapes are unchanged. Double-angle marks use local Segoe UI Symbol contours because Tahoma lacks them. Atlases remain 512×256 and 512×512; no vector font files are distributed. The offline specimen was visually checked.
- Enforced the 1024-pixel surface limit for every accepted logical dimension, including 1024-pixel and intermediate sizes. Invalid dimensions fail without allocating. Up-to-4× detail, variable spacing, the 2 MiB budget target and lower-detail fallback remain. Native tests pass 241 glyph cases, 12 allocation/header/flush/DMA cases, five invalid-dimension cases, 60 symbol parser/render cases and 60 mode toggles: 4,505,439 SH-4 instructions. Codec tests pass 18 round trips, three English byte fixtures, six rejections and the existing PRS cases.
- Built local 0.1.5 components and a menu/name/library test disc using the existing 0.1.4 translations. All 89 non-font archive members and the copied text components are unchanged. Existing library proof is reused only after exact code/payload hash checks. The disc changes 96 sectors across two tracks; all three patched files re-extract exactly, sector EDC/ECC passes and unrelated ISO entries stay unchanged. Prior builds and the original dump are untouched. No GitHub release was created.
- Font repertoire reporting now uses the implemented character set rather than flagging every non-ASCII mark. The 82,571 story drafts and 503 holds are unchanged. Live 0.1.5 validation, meaning review, source holds, full VM coverage, story/battle insertion, image UI/movie audit and layout/navigation/memory checks remain unfinished.

'''
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8');marker='## 0.1.4 — local library test build'
    assert marker in old and '## 0.1.5 —' not in old
    print(json.dumps(validation,ensure_ascii=False,indent=2));print(changelog)
    print('Font documentation:',doc['build'],f['glyph_count_per_size'],f['small_bitmaps_offset'],f['medium_bitmaps_offset'])
    if args.write:
        (folder/'font-native-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),'utf-8')
        docpath.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n','utf-8')
        cp.write_text(old.replace(marker,changelog+marker,1),'utf-8')
    print('Wrote inspected font evidence/docs/changelog.' if args.write else 'DRY RUN: no documentation changed.')


if __name__=='__main__':main()
