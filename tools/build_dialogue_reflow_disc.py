"""Package verified dialogue reflow as local 0.1.41. Dry first."""
import argparse,json,re,shutil
from build_dialogue_reflow import ROOT,OUT,VERSION,PRIOR,digest
from build_movie_test_disc import write_plan
from package_archive_test_disc import substitute_payload_sector
from disc_inventory import Disc,SECTOR
from afs_layout import require_native_layouts


def read(path):return json.loads(path.read_text('utf-8'))


def plan():
    component=read(OUT/'component-report.json');proof_raw=(OUT/'native-test.json').read_bytes();proof=json.loads(proof_raw)
    assert proof['files']==component['files'] and proof['story_commands']==50273
    assert proof['embedded_native_cases']==52 and proof['battle_native_selection_cases']==6034
    assert proof['inline_effect_commands']==166 and proof['archive_lookup_cases']==448
    files={n:(OUT/n).read_bytes() for n in component['files']}
    for name,raw in files.items():assert digest(raw)==component['files'][name]['sha256']
    base=ROOT/'work/output'/PRIOR;previous=read(base/'english-disc-report.json')
    assert previous['validation']['reextracted_files']=='all 14 exact'
    assert previous['validation']['changed_sector_EDC_ECC']=='pass' and previous['validation']['unrelated_track_bytes']=='all unchanged'
    cue=base/'disc'/f'Rayblade English Test {PRIOR}.cue';disc=Disc(cue)
    entries={r['path']:r for r in disc.inventory()};inherited={}
    for name,record in previous['files'].items():
        raw=(base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes();row=entries[name]
        assert len(raw)==record['size'] and digest(raw)==record['sha256']
        assert disc.read(row['lba'],row['size'])==raw;inherited[name]=raw
    # The executable changes only existing embedded-English payload slots.
    allowed=set()
    for row in read(base/'embedded-dialogue-component.json')['records']:
        allowed.update(range(row['english_offset'],row['english_offset']+row['english_bytes']))
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(inherited['1ST_READ.BIN'],files['1ST_READ.BIN'])))
    targets=dict(inherited,**files);require_native_layouts(targets)
    historical=list(previous['historical_native_evidence'])
    old_proof=(base/'memory-album-native-test.json').read_bytes();v=json.loads(old_proof)
    assert digest(old_proof)==previous['memory_album_proof_sha256']
    historical.append({'file':'memory-album-native-test.json','sha256':digest(old_proof),
        'actual_tested_build':PRIOR,'executable_sha256':v['executable_sha256'],
        'scope':'Original .40 memory/album proof; album, names and relevant executable instructions remain exact'})
    for row in historical:assert digest((base/row['file']).read_bytes())==row['sha256']
    original=Disc(next(ROOT.glob('*.cue')));changes=[];locations=previous['total_changed_sector_locations_from_original'];per_file={}
    for name,target in files.items():
        source=inherited[name];row=entries[name];assert len(source)==len(target)==row['size']
        orig=original.read(row['lba'],row['size']);count=0
        for i in range((len(target)+2047)//2048):
            a,b=source[i*2048:(i+1)*2048],target[i*2048:(i+1)*2048]
            if a==b:continue
            lba=row['lba']+i;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
            offset=(track['index']+lba-track['start_lba'])*SECTOR
            with track['path'].open('rb') as fh:fh.seek(offset);raw=fh.read(SECTOR)
            changes.append((track['path'].name,offset,substitute_payload_sector(raw,a,b)));count+=1
        old=sum(source[i:i+2048]!=orig[i:i+2048] for i in range(0,len(source),2048))
        new=sum(target[i:i+2048]!=orig[i:i+2048] for i in range(0,len(target),2048));locations+=new-old
        per_file[name]={'new_sectors':count,'previous_locations_from_original':old,'target_locations_from_original':new}
    report={'version':VERSION,'source_build':PRIOR,'kind':'Local current-font reflow of inserted English dialogue; translation unfinished',
        'movie_extent':previous['movie_extent'],'movie_extents':previous['movie_extents'],'movies':previous['movies'],
        'original_audio_sector_count':previous.get('original_audio_sector_count',4041),
        'files':{n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        'new_changed_sectors':len(changes),'total_changed_sector_locations_from_original':locations,'per_file_changes':per_file,
        'historical_native_evidence':historical,'dialogue_reflow_component':component,'dialogue_reflow_native_proof':proof,
        'dialogue_reflow_proof_sha256':digest(proof_raw),'component_manifest_name':'dialogue-reflow-component.json',
        'readme_component_text':'All inserted English story, embedded and battle dialogue reflowed using current Skies font widths.\n'
            'Obsolete single line breaks joined; whole words wrapped within the dialogue box.\n'
            'Wording, original page breaks, pause/effect controls and VM command addresses retained.\n'
            'One overlong battle page gains an automatic page turn to keep its text inside three lines.\n'
            'Includes the memory-card and sharper album-caption improvements from 0.1.40.\n'
            'TEST: fresh-boot this GDI and load a normal in-game save; avoid loading an emulator save state.\n',
        'readme_movie_text':previous['readme_movie_text'],'proof_scope':'All 50273 story commands, 13 embedded commands and 5516 battle spans audited; '
            'native story lookups, representative loading/formatting/VM cases, 166 inline-effect comparisons, '
            '52 embedded cases, 6034 battle selections, 128 roots, 256 workspace cases and native battle PRS. '
            'Documented bounded fixtures; live reading/timing/appearance remain pending.',
        'pending':list(dict.fromkeys(['Live current-font dialogue flow, page turns, pause/callback timing and battle dialogue',*previous['pending']])),
        'release':False}
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'));assert len(names)==5
    return disc,cue,inherited,targets,changes,names,historical,report


def finalize(planned):
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json'):shutil.copyfile(OUT/name,out/('dialogue-reflow-'+name))
    for name in ('scenario-component-report.json','battle-component-report.json','D_BMESS.en.dec.bin'):
        shutil.copyfile(OUT/name,out/'text'/name)
    shutil.copyfile(OUT/'D_SCE.AFS',out/'text/D_SCE.AFS')
    shutil.copyfile(OUT/'embedded-dialogue-component.json',out/'embedded-dialogue-component.json')
    for relative in ('text/scenario-component-report.json','text/battle-component-report.json','embedded-dialogue-component.json'):
        path=out/relative;value=read(path)
        value['current_reflow_validation']={'version':VERSION,'native':'pass; scope and fixtures in dialogue-reflow-native-test.json','live':'pending'}
        if relative.startswith('text/scenario'):
            value['word_wrap'].update(native_verification='pass; scope in dialogue-reflow-native-test.json',live_verification='pending')
        path.write_text(json.dumps(value,indent=2)+'\n','utf-8')
    manifest=read(out/'font4x-patch.json');component=read(OUT/'component-report.json')
    manifest.update(version=VERSION,previous_build=PRIOR,status='Current-font dialogue reflow packaged; live reading-flow verification pending')
    manifest['current_payload_identities']=planned[7]['files']
    for name,row in component['files'].items():manifest['files'].setdefault(name,{})['target_sha256']=row['sha256']
    story=read(out/'text/scenario-component-report.json');battle=read(out/'text/battle-component-report.json')
    manifest['scenario'].update(version=VERSION,archive_sha256=component['files']['D_SCE.AFS']['sha256'],
        executable_sha256=component['files']['1ST_READ.BIN']['sha256'],word_wrap=story['word_wrap'])
    manifest['battle'].update(version=VERSION,compressed_sha256=component['files']['D_BMESS.BIN']['sha256'],
        decoded_sha256=battle['output_sha256'],decoded_bytes=battle['output_decoded_bytes'],
        maximum_record_bytes=battle['maximum_record_bytes'],reflow_counts=battle['reflow_counts'])
    manifest['embedded_dialogue']=read(out/'embedded-dialogue-component.json')
    manifest['dialogue_reflow']={'version':VERSION,'proof':'dialogue-reflow-native-test.json','live_validation':'pending'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'All instructions and eleven other payloads remain exact; embedded payload text and story/battle data reflowed. Fresh affected native proof is dialogue-reflow-native-test.json; other reports historical.'}
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true')
    ap.add_argument('--finalize-existing',action='store_true',help='Verify completed disc, then resume metadata only')
    args=ap.parse_args()
    planned=plan();print('PASS:',len(planned[4]),'sector edits;',len(planned[3]),'payloads;',len(planned[6]),'historical proofs.',flush=True)
    if not args.write:print('DRY RUN: no disc or metadata written.');return
    if args.finalize_existing:
        out=ROOT/'work/output'/VERSION;saved=read(out/'english-disc-report.json')
        assert saved['files']==planned[7]['files'] and saved['dialogue_reflow_proof_sha256']==planned[7]['dialogue_reflow_proof_sha256']
        assert saved['validation']['reextracted_files']=='all 14 exact'
        assert saved['validation']['changed_sector_EDC_ECC']=='pass' and saved['validation']['unrelated_track_bytes']=='all unchanged'
        assert saved['validation']['track_bytes_compared']==1188856032
        disc=Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue');entries={r['path']:r for r in disc.inventory()}
        for name,raw in planned[3].items():
            r=entries[name];assert disc.read(r['lba'],r['size'])==raw
    else:
        write_plan(planned,VERSION,PRIOR,{n:planned[3][n] for n in ('1ST_READ.BIN','D_SCE.AFS','D_BMESS.BIN')})
    finalize(planned)


if __name__=='__main__':main()
