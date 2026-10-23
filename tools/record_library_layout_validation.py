"""Record measured library layout/native/disc evidence. Default dry run."""
import argparse,json
from build_library_layout_patch import ROOT,VERSION,PRIOR,compose,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION
    read=lambda p:json.loads(p.read_text('utf-8'))
    files,_,component=compose()
    for name in ('1ST_READ.BIN','WIN00.AFS','text/D_PAPER.en.dec.bin','text/D_PAPER.BIN'):assert files[name]==(out/name).read_bytes()
    layout=read(out/'library-layout-native-test.json');native=read(out/'library-native-test.json');disc=read(out/'english-disc-report.json');manifest=read(out/'font4x-patch.json')
    assert layout['executable_sha256']==digest(files['1ST_READ.BIN']) and layout['library_sha256']==component['output_sha256']==native['library_component_sha256']
    assert disc['files']['WIN00.AFS']['sha256']==digest(files['WIN00.AFS']) and disc['validation']['reextracted_files']=='all 5 exact' and disc['validation']['changed_sector_EDC_ECC']=='pass'
    assert native['physical_records']==257 and native['all_unlock_combinations']=='pass' and native['scroll_windows_six_and_seven_lines']=='pass'
    recipe=manifest['library_layout']
    assert layout['native_parser_line_occurrences']==2*recipe['nonempty_line_count'] and len(layout['native_scroll_witnesses'])==2
    record={'version':VERSION,'status':'Measured library wrapping packaged; native viewer/filter/parser/scroll checks pass; live appearance/navigation/memory pending',
        'source_build':PRIOR,'changed_sections':recipe['changed_sections'],'spaces_changed_to_breaks':recipe['inserted_breaks'],'soft_wraps_changed_to_spaces':recipe['joined_breaks'],'nonempty_lines':recipe['nonempty_line_count'],'decoded_bytes':component['output_decoded_size'],'packed_bytes':component['output_compressed_size'],
        'original_words_punctuation_and_paragraph_boundaries':'unchanged','profile_metadata_and_unlock_controls':'unchanged','font_and_executable':'byte-exact 0.1.17',
        'geometry':layout['geometry'],'native_counts':layout['counts'],'native_instructions':layout['native_instructions'],'native_parser_line_occurrences':layout['native_parser_line_occurrences'],
        'native_scroll_witnesses':layout['native_scroll_witnesses'],'maximum_page_buffer_bytes':native['maximum_six_or_seven_line_page_bytes'],'page_buffer_capacity':512,
        'native_proof':f'work/output/{VERSION}/library-layout-native-test.json','filter_proof':f'work/output/{VERSION}/library-native-test.json',
        'recipe':'work/translation/en/library/layouts.en.json','previews':[f'work/output/{VERSION}/library-{h}-line-preview.png' for h in (6,7)],
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi','packaging':disc['validation'],'limits':layout['limits'],
        'translation_credit':'No new draft credit; existing library text is reflowed without meaning changes'}
    results={ROOT/'docs/library-layout.json':record}
    p=ROOT/'docs/translation-status.json';d=read(p);d.update(version=VERSION,stage='Library descriptions now word-wrapped with native viewer/filter/parser/scroll checks; antialiased font, chapter cards, targeted UI and drafted text packaged; held rows, meaning review, remaining images and full-game validation incomplete',latest_library_build=record)
    d['test_disc'].update(version=VERSION,changed_sectors=disc['changed_sectors'],validation=disc['validation'],path=record['disc'])
    d['library']['offline_component'].update(output_compressed_size=component['output_compressed_size'],output_decoded_size=component['output_decoded_size'],pending=['Live library appearance, navigation and long-session memory'])
    d['library']['disc_integration']=manifest['library'];d['library']['native_filter_validation']=native
    d['remaining']=[x for x in d['remaining'] if x!='Measure library UI and implement layout/reflow without cutting meaning']
    results[p]=d
    p=ROOT/'docs/text-reinsertion.json';d=read(p);d['D_PAPER'].update(english_compressed_bytes=component['output_compressed_size'],insertion='Measured library text and existing English drafts inserted in 0.1.18; live viewer validation pending',latest_layout_build=record);results[p]=d
    p=out/'font4x-patch.json';manifest['status']=record['status'];manifest['library_layout']['packaging']=disc['validation'];results[p]=manifest
    results[out/'library-patch-report.json']=manifest['library']
    before='Native decoder/viewer/filter/parser/scroll checks and packaging are pending.'
    after=f"Native checks pass {native['native_filter_cases']:,} filter cases across all unlock outcomes and every six/seven-line scrolling start, {layout['counts']['parser_pages']:,} pages through real constructed text contexts, and {sum(x['native_button_cases'] for x in layout['native_scroll_witnesses'])} original up/down-controller cases covering both bounds. Maximum six/seven-line output is {native['maximum_six_or_seven_line_page_bytes']} of 512 bytes. Native graphics endpoints and glyph raster are bounded fixtures; actual context selection, parser, clear-state handling, filtering and scrolling execute. Local packaging re-extracts all five files exactly, validates {disc['changed_sectors']:,} changed sectors and preserves unrelated ISO entries."
    changelog=ROOT/'CHANGELOG.md';log=changelog.read_text('utf-8');assert before in log or after in log
    print(json.dumps(record,indent=2))
    if not args.write:print('DRY RUN: no documentation written');return
    for p,d in results.items():p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
    changelog.write_text(log.replace(before,after,1),'utf-8')
    p=out/'READ-ME.txt';note='\n0.1.18 wraps existing English library descriptions at spaces for the six- and seven-line viewers, preserving every word and unlock condition. Native/offline checks pass. Live library appearance, navigation and long-session memory remain pending. The antialiased font is unchanged from 0.1.17.\n'
    if note.strip() not in p.read_text('utf-8'):p.write_text(p.read_text('utf-8')+note,'utf-8')
    print('Recorded library wrapping, native coverage, packaged disc and explicit live-validation limits.')


if __name__=='__main__':main()
