"""Record packaged library header/scratch evidence. Dry run before --write."""
import argparse,json
from build_library_header_patch import ROOT,VERSION,PRIOR,compose,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    out=ROOT/'work/output'/VERSION;read=lambda p:json.loads(p.read_text('utf-8'))
    files,_,component=compose()
    for name in ('1ST_READ.BIN','WIN00.AFS','D_SCE.AFS','text/D_NAMES.BIN','text/D_NAMES.en.dec.bin','text/D_PAPER.en.dec.bin'):
        assert files[name]==(out/name).read_bytes()
    proofs={name:read(out/(name+'.json')) for name in ('library-header-native-test','genei-font-native-test','genei-surface-native-test','ui-layout-native-test','word-wrap-native-test','inline-control-native-test','library-layout-native-test','scenario-native-test','battle-english-native-test','chapter-card-native-test')}
    sha=digest(files['1ST_READ.BIN']);assert all(p['executable_sha256']==sha for p in proofs.values())
    header=proofs['library-header-native-test'];disc=read(out/'english-disc-report.json');manifest=read(out/'font4x-patch.json')
    assert header['counts']=={'character':144,'mech':128} and header['decimal_cases']==528 and header['queue_bytes_roundtripped']==3072
    assert disc['files']['1ST_READ.BIN']['sha256']==sha and disc['validation']=={'reextracted_files':'all 5 exact','changed_sector_EDC_ECC':'pass','unrelated_ISO_entries':'unchanged','in_game':'pending'}
    record={'version':VERSION,'source_build':PRIOR,'status':'Library scratch collision, decimal glyphs and age-field fit corrected; native checks and local packaging pass; live navigation/GPU/long-session gameplay pending',
        'executable_sha256':sha,'names_sha256':digest(files['text/D_NAMES.en.dec.bin']),'library_sha256':header['library_sha256'],'old_bug_reproduction':header['old_bug_reproduction'],
        'memory':{k:v for k,v in manifest['library_header'].items() if k not in ('native_validation','proof_sha256','live_validation')},
        'native_headers':header['counts'],'native_instructions':header['native_instructions'],'native_queue_bytes_roundtripped':header['queue_bytes_roundtripped'],'native_decimal_cases':header['decimal_cases'],
        'geometry':header['geometry'],'proof':f'work/output/{VERSION}/library-header-native-test.json','regression_proofs':{k:f'work/output/{VERSION}/{k}.json' for k in proofs},
        'unchanged':'Font, WIN00 archive including library/chapter payloads, story and battle bytes exact 0.1.18; one D_NAMES coordinate byte and three executable bytes change',
        'previews':[f'work/output/{VERSION}/library-{k}-header-preview.png' for k in ('character','mech')],
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi','packaging':disc['validation'],'limits':header['limits'],'new_translation_credit':0}
    results={ROOT/'docs/library-headers.json':record}
    manifest.update(status=record['status'],native_proof_reuse={'source_build':PRIOR,'scope':'Font/archive/story/battle payloads byte-exact; all required native suites freshly executed against the 0.1.19 executable'})
    manifest['library_header']['packaging']=disc['validation']
    manifest['library']['shared_parameter_scratch']={'initializer_literal':'0x2afc4','offset':0x1f200,'reserved_bytes':0xe00,'library_gap_bytes':5057,'native_proof':record['proof']}
    manifest['antialias_font'].update(raster_proof_sha256=digest((out/'genei-font-native-test.json').read_bytes()),surface_proof_sha256=digest((out/'genei-surface-native-test.json').read_bytes()))
    results[out/'font4x-patch.json']=manifest;results[out/'library-patch-report.json']=manifest['library']
    p=ROOT/'docs/translation-status.json';d=read(p);d.update(version=VERSION,stage='Expanded library protected from native header scratch writes; decimal glyphs and age layout repaired; drafted English packaged; held text, independent review, image/movie audit and full-game validation incomplete',latest_library_header_build=record)
    d['test_disc'].update(version=VERSION,changed_sectors=disc['changed_sectors'],validation=disc['validation'],path=record['disc'])
    d['library']['disc_integration']=manifest['library'];d['library']['native_header_validation']=record
    d['ui_names']['latest_library_header_build']=VERSION
    results[p]=d
    p=ROOT/'docs/text-reinsertion.json';d=read(p);d['D_NAMES'].update(english_decoded_bytes=component['output_decoded_size'],english_compressed_bytes=component['output_compressed_size'],latest_header_build=record)
    d['D_NAMES']['disc_relocation']=disc['names'];d['D_PAPER']['native_loader'].update(parameter_scratch_offset=0x1f200,parameter_scratch_reserved_bytes=0xe00,library_to_scratch_gap_bytes=5057)
    d['D_PAPER']['native_header_check']=record;results[p]=d
    p=ROOT/'docs/ui-layout.json';d=read(p);d['library_header_build']=record;results[p]=d
    p=ROOT/'docs/font-antialiasing.json';d=read(p);d['latest_native_regression']={'version':VERSION,'raster_proof':record['regression_proofs']['genei-font-native-test'],'surface_proof':record['regression_proofs']['genei-surface-native-test'],'font_bytes':'unchanged from 0.1.17','live_appearance':'pending'};results[p]=d
    before='Fresh native checks and local packaging are in progress.'
    after=f"Fresh native checks pass all 272 header/name slots through real constructed contexts, 3,072 queue-byte round trips and 528 decimal/ring-wrap cases, preserving the entire library and allocation guards. All required native font/UI/library/story/battle/chapter suites were rerun against the changed executable. Local packaging re-extracts all five files exactly, validates {disc['changed_sectors']:,} changed sectors and preserves unrelated ISO entries."
    p=ROOT/'CHANGELOG.md';log=p.read_text('utf-8');assert before in log or after in log
    print(json.dumps(record,indent=2))
    if not args.write:print('DRY RUN: no documentation written');return
    for p,d in results.items():p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
    (ROOT/'CHANGELOG.md').write_text(log.replace(before,after,1),'utf-8')
    p=out/'READ-ME.txt';note='\n0.1.19 moves native parameter scratch beyond the expanded library to prevent header preparation corrupting profiles; repairs unit decimal points and age-field fit. Fresh native checks and disc integrity pass. Actual Flycast appearance/navigation, long-session gameplay and full translation review remain pending.\n'
    if note.strip() not in p.read_text('utf-8'):p.write_text(p.read_text('utf-8')+note,'utf-8')
    print('Recorded shared scratch repair, header fit, fresh native regressions and packaged disc.')


if __name__=='__main__':main()
