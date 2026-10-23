"""Package verified battle-menu corrections as 0.1.42. Dry first."""
import argparse,json,re,shutil
from build_battle_menu_patch import ROOT,OUT,VERSION,PRIOR,compose,digest,EDITS
from build_movie_test_disc import write_plan
from package_archive_test_disc import substitute_payload_sector
from disc_inventory import Disc,SECTOR
from afs_layout import require_native_layouts


def read(path):return json.loads(path.read_text('utf-8'))


def plan():
    files,decoded,recipe,names_report,component=compose()
    for name,raw in files.items():assert (OUT/name).read_bytes()==raw
    proof_raw=(OUT/'native-test.json').read_bytes();proof=json.loads(proof_raw)
    assert proof['executable_sha256']==digest(files['1ST_READ.BIN']) and proof['names_packed_sha256']==digest(files['D_NAMES.BIN'])
    assert len(proof['menu_geometry_cases'])==8 and len(proof['UI_cases'])==19 and len(proof['native_status_cases'])==2
    assert proof['native_raster_cases']==8 and proof['font_changed'] is False
    base=ROOT/'work/output'/PRIOR;previous=read(base/'english-disc-report.json')
    assert previous['validation']['reextracted_files']=='all 14 exact'
    assert previous['validation']['changed_sector_EDC_ECC']=='pass' and previous['validation']['unrelated_track_bytes']=='all unchanged'
    cue=base/'disc'/f'Rayblade English Test {PRIOR}.cue';disc=Disc(cue);entries={r['path']:r for r in disc.inventory()}
    inherited={}
    for name,row in previous['files'].items():
        raw=(base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes();r=entries[name]
        assert len(raw)==row['size'] and digest(raw)==row['sha256'] and disc.read(r['lba'],r['size'])==raw
        inherited[name]=raw
    assert {i for i,(a,b) in enumerate(zip(inherited['1ST_READ.BIN'],files['1ST_READ.BIN'])) if a!=b}=={p for p,_,_,_ in EDITS}
    targets=dict(inherited,**files);require_native_layouts(targets)
    historical=list(previous['historical_native_evidence'])
    raw=(base/'dialogue-reflow-native-test.json').read_bytes();v=json.loads(raw)
    assert digest(raw)==previous['dialogue_reflow_proof_sha256'] and v['executable_sha256']==digest(inherited['1ST_READ.BIN'])
    historical.append({'file':'dialogue-reflow-native-test.json','sha256':digest(raw),'actual_tested_build':PRIOR,
        'executable_sha256':v['executable_sha256'],'scope':'Actual .41 dialogue proof; all story/battle payloads, embedded text and executable instructions retained in .42'})
    for row in historical:assert digest((base/row['file']).read_bytes())==row['sha256']
    original=Disc(next(ROOT.glob('*.cue')));locations=previous['total_changed_sector_locations_from_original'];changes=[];counts={}
    for name,target in files.items():
        source=inherited[name];r=entries[name];assert len(source)==len(target)==r['size']
        orig=original.read(r['lba'],r['size']);count=0
        for i in range((len(target)+2047)//2048):
            a,b=source[i*2048:(i+1)*2048],target[i*2048:(i+1)*2048]
            if a==b:continue
            lba=r['lba']+i;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba']);offset=(track['index']+lba-track['start_lba'])*SECTOR
            with track['path'].open('rb') as fh:fh.seek(offset);raw=fh.read(SECTOR)
            changes.append((track['path'].name,offset,substitute_payload_sector(raw,a,b)));count+=1
        old=sum(source[i:i+2048]!=orig[i:i+2048] for i in range(0,len(source),2048))
        new=sum(target[i:i+2048]!=orig[i:i+2048] for i in range(0,len(target),2048));locations+=new-old
        counts[name]={'new_sectors':count,'previous_locations_from_original':old,'target_locations_from_original':new}
    report={'version':VERSION,'source_build':PRIOR,'kind':'Local battle menu/header corrections and translation check; full translation unfinished',
        'movie_extent':previous['movie_extent'],'movie_extents':previous['movie_extents'],'movies':previous['movies'],
        'original_audio_sector_count':previous.get('original_audio_sector_count',4041),
        'files':{n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        'new_changed_sectors':len(changes),'total_changed_sector_locations_from_original':locations,'per_file_changes':counts,
        'historical_native_evidence':historical,'battle_menu_component':component,'battle_menu_native_proof':proof,
        'battle_menu_proof_sha256':digest(proof_raw),'component_manifest_name':'battle-menu-component.json',
        'readme_component_text':'Widened unit action menu and text tiles; complete labels including Transform fit inside the screen.\n'
            'Shorter battle labels: Move Type / Move / Trust / Skills / Hit / Req. SP / PR Cost.\n'
            'Cut-In uses On/Off title case; both label and status use the same original Skies font.\n'
            'Checked the reported Ymir line against Japanese/context: she refers to Ai; wording retained.\n'
            'Includes 0.1.41 whole-word dialogue reflow and 0.1.40 memory-card/album fixes.\n'
            'TEST: fresh-boot this GDI, load a normal in-game save, check unit actions/status/weapons and Cut-In states.\n',
        'readme_movie_text':previous['readme_movie_text'],
        'proof_scope':'Eight native action text/frame constructions, all nine action-label ink bounds, 19 UI cases, '
            'both real common-queue/nested status lookups, eight native glyph raster cases and native names PRS. '
            'GPU/frame/cursor appearance and full gameplay remain pending.',
        'pending':list(dict.fromkeys(['Live action-menu frame/cursor/highlight and compact battle labels; both Cut-In states',*previous['pending']])),
        'release':False}
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'));assert len(names)==5
    return disc,cue,inherited,targets,changes,names,historical,report


def finalize(planned):
    out=ROOT/'work/output'/VERSION;files,decoded,recipe,names,component=compose()
    (out/'text/D_NAMES.en.dec.bin').write_bytes(decoded)
    for relative,value in [('text/names-component-report.json',names),('ui-layouts.en.json',recipe)]:
        (out/relative).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    for name in ('component-report.json','native-test.json'):shutil.copyfile(OUT/name,out/('battle-menu-'+name))
    for p in OUT.glob('*-preview.png'):shutil.copyfile(p,out/('battle-menu-'+p.name))
    manifest=read(out/'font4x-patch.json');manifest.update(version=VERSION,previous_build=PRIOR,
        status='Battle UI fixes packaged; native affected checks pass; live appearance pending')
    manifest['current_payload_identities']=planned[7]['files']
    for name,raw in files.items():manifest['files'].setdefault(name,{})['target_sha256']=digest(raw)
    manifest['ui_layout'].update(version=VERSION,names_sha256=digest(decoded),names_packed_sha256=digest(files['D_NAMES.BIN']),
        native_validation='19 affected cases plus eight native action contexts/frames and both real status lookups')
    manifest['battle_menu']={'version':VERSION,'proof':'battle-menu-native-test.json','live_validation':'pending'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Only five action-layout data bytes and names text changed. Font, all executable instructions, story/battle/library/album and movie payloads retained; old proofs preserve actual tested hashes.'}
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    planned=plan();print('PASS:',len(planned[4]),'sector edits;',len(planned[3]),'payloads;',len(planned[6]),'historical proofs.',flush=True)
    if not args.write:print('DRY RUN: no disc or metadata written.');return
    write_plan(planned,VERSION,PRIOR,{n:planned[3][n] for n in ('1ST_READ.BIN','D_NAMES.BIN')});finalize(planned)


if __name__=='__main__':main()
