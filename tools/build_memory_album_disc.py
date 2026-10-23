"""Package 0.1.40 over the exact verified 0.1.39 disc. Dry first."""
import argparse
import json
import re
import shutil

from build_memory_album_patch import ROOT, OUT, VERSION, PRIOR, compose, digest
from build_movie_test_disc import write_plan
from package_archive_test_disc import substitute_payload_sector
from disc_inventory import Disc, SECTOR
from afs_layout import require_native_layouts


def plan():
    files, decoded, recipe, component, names_report = compose()
    for name,raw in files.items(): assert (OUT/name).read_bytes() == raw
    assert json.loads((OUT/'component-report.json').read_text('utf-8')) == component
    proof_raw=(OUT/'native-test.json').read_bytes();proof=json.loads(proof_raw)
    assert proof['executable_sha256']==digest(files['1ST_READ.BIN'])
    assert proof['archive_sha256']==digest(files['ALBUM.AFS'])
    assert proof['names_packed_sha256']==digest(files['D_NAMES.BIN'])
    assert proof['caption_dispatch']['cases']==1356 and proof['geometry']['cases']==448
    assert len(proof['UI_cases'])==23 and len(proof['native_PRS_instructions'])==36
    assert proof['archive_lookup_cases']==251
    base=ROOT/'work/output'/PRIOR
    previous=json.loads((base/'english-disc-report.json').read_text('utf-8'))
    assert previous['validation']['reextracted_files']=='all 14 exact'
    assert previous['validation']['changed_sector_EDC_ECC']=='pass'
    assert previous['validation']['unrelated_track_bytes']=='all unchanged'
    cue=base/'disc'/f'Rayblade English Test {PRIOR}.cue'
    disc=Disc(cue);entries={r['path']:r for r in disc.inventory()}
    inherited={}
    for name, record in previous['files'].items():
        path=base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)
        raw=path.read_bytes();row=entries[name]
        assert len(raw)==record['size'] and digest(raw)==record['sha256']
        assert disc.read(row['lba'],row['size'])==raw
        inherited[name]=raw
    targets=dict(inherited,**files)
    require_native_layouts(targets)
    # All raster/advance/parser/texture-filter instructions remain exact .39.
    old_exe=inherited['1ST_READ.BIN'];new_exe=files['1ST_READ.BIN']
    allowed=set(range(0x6b840,0x6b840+component['dispatcher_bytes']))
    for p in component['patched_draw_pointers']: allowed.update(range(p,p+4))
    assert len(old_exe)==len(new_exe)
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(old_exe,new_exe)))
    original=Disc(next(ROOT.glob('*.cue')))
    historical=list(previous['historical_native_evidence'])
    for name,key in [('skies-font-native-test.json','skies_font_proof_sha256'),
                     ('skies-font-inline-native-test.json','skies_font_inline_proof_sha256')]:
        raw=(base/name).read_bytes();value=json.loads(raw)
        assert digest(raw)==previous[key] and value['executable_sha256']==digest(old_exe)
        assert not any(r['file']==name for r in historical)
        historical.append({'file':name,'sha256':digest(raw),'actual_tested_build':PRIOR,
            'executable_sha256':value['executable_sha256'],
            'scope':'Historical .39 font proof; its actual identity retained. Font bytes and relevant code unchanged in .40.'})
    for row in historical:
        assert digest((base/row['file']).read_bytes())==row['sha256']
    changes=[];locations=previous['total_changed_sector_locations_from_original']
    per_file={}
    for name,target in files.items():
        source=inherited[name];row=entries[name]
        assert len(source)==len(target)==row['size']
        orig=original.read(row['lba'],row['size'])
        delta=[]
        for n in range((len(target)+2047)//2048):
            a,b=source[n*2048:(n+1)*2048],target[n*2048:(n+1)*2048]
            if a==b: continue
            lba=row['lba']+n
            track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
            offset=(track['index']+lba-track['start_lba'])*SECTOR
            with track['path'].open('rb') as fh: fh.seek(offset);raw=fh.read(SECTOR)
            changes.append((track['path'].name,offset,substitute_payload_sector(raw,a,b)))
            delta.append(n)
        old_count=sum(source[n:n+2048]!=orig[n:n+2048] for n in range(0,len(source),2048))
        new_count=sum(target[n:n+2048]!=orig[n:n+2048] for n in range(0,len(target),2048))
        locations+=new_count-old_count
        per_file[name]={'sector_substitutions':len(delta),'source_locations_from_original':old_count,
                        'target_locations_from_original':new_count}
    assert len({(name,offset) for name,offset,_ in changes})==len(changes)
    report={'version':VERSION,'source_build':PRIOR,
        'kind':'Local memory-card layout and three-times-detail album-caption test; translation remains unfinished',
        'movie_extent':previous['movie_extent'],'movie_extents':previous['movie_extents'],'movies':previous['movies'],
        'original_audio_sector_count':previous.get('original_audio_sector_count',4041),
        'files':{name:{'size':len(raw),'sha256':digest(raw)} for name,raw in targets.items()},
        'new_changed_sectors':len(changes),'total_changed_sector_locations_from_original':locations,
        'per_file_changes':per_file,'historical_native_evidence':historical,
        'memory_album_component':component,'memory_album_native_proof':proof,'memory_album_proof_sha256':digest(proof_raw),
        'inherited_components':f'Eleven game payloads exact {PRIOR}; normal font and all story/library pixels/wording unchanged',
        'component_manifest_name':'memory-album-component.json',
        'readme_component_text':'Compact memory-card prompts and Port A - Slot 1 labels fit existing boxes.\n'
            'All 203 album captions now use original Skies glyph pixels on separate 3x-detail textures.\n'
            'The photos and 21 Coming Soon cards are unchanged. Every caption texture is 1024x512 or smaller.\n'
            'TEST: fresh-boot this GDI, check save/load slot numbers and headers, then page through Memory Album.\n'
            'Use a normal in-game save to reach the album. Old emulator save states retain old code and textures.\n',
        'readme_movie_text':previous['readme_movie_text'],
        'proof_scope':'1356 bounded native draw-dispatch cases; 448 actual Ninja geometry cases; native registration, '
            '251 SDK archive lookups, seven native VQ texture-info cases, independent pixel checks, '
            '23 native UI parser cases and 36 native PRS streams. GPU rendering/live navigation and total live VRAM unverified.',
        'pending':list(dict.fromkeys(['Fresh-boot memory-card/header appearance and save/load interaction',
            'Live album caption appearance, depth/alpha, paging and VRAM occupancy',*previous['pending']])),
        'release':False}
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'));assert len(names)==5
    return disc,cue,inherited,targets,changes,names,historical,report


def finalize(planned):
    out=ROOT/'work/output'/VERSION
    files,decoded,recipe,component,names_report=compose()
    (out/'text/D_NAMES.en.dec.bin').write_bytes(decoded)
    (out/'text/names-component-report.json').write_text(json.dumps(names_report,indent=2)+'\n','utf-8')
    (out/'ui-layouts.en.json').write_text(json.dumps(recipe,indent=2)+'\n','utf-8')
    for name in ('component-report.json','native-test.json'):
        shutil.copyfile(OUT/name,out/('memory-album-'+name))
    for name in ('UV-stage-component-report.json','UV-stage-native-test.json'):
        shutil.copyfile(OUT/name,out/('memory-album-'+name))
    manifest_path=out/'font4x-patch.json';manifest=json.loads(manifest_path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
        status='Compact memory-card labels and high-detail album captions; live verification pending')
    manifest['current_payload_identities']=planned[7]['files']
    manifest['memory_album']={'build':VERSION,'component':'memory-album-component-report.json',
        'native_proof':'memory-album-native-test.json','additional_caption_VRAM_bytes':931840,'live_validation':'pending'}
    for name in files:
        manifest['files'].setdefault(name,{})['target_sha256']=digest(files[name])
    manifest['ui_layout'].update(version=VERSION,names_sha256=digest(decoded),
        names_packed_sha256=digest(files['D_NAMES.BIN']),native_validation='23 affected native memory-card cases')
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
    # Prevent inherited captions metadata from implying old low-detail cells.
    path=out/'album-caption-component.json'
    if path.exists():
        value=json.loads(path.read_text('utf-8'));value['superseded_rendering']={
            'build':VERSION,'method':component['method'],'current_archive_sha256':digest(files['ALBUM.AFS']),
            'component':'memory-album-component-report.json'}
        path.write_text(json.dumps(value,indent=2)+'\n','utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true')
    args=ap.parse_args();planned=plan()
    print('PASS:',len(planned[4]),'sector edits;',len(planned[3]),'payloads;',len(planned[6]),'historical proofs.',flush=True)
    if not args.write: print('DRY RUN: no disc or metadata written.');return
    write_plan(planned,VERSION,PRIOR,{name:planned[3][name] for name in ('1ST_READ.BIN','ALBUM.AFS','D_NAMES.BIN')})
    finalize(planned)


if __name__ == '__main__': main()
