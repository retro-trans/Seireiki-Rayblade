"""Package verified map-font archive as local 0.1.44. Dry first."""
import argparse,json,re,shutil
from build_map_font_patch import ROOT,OUT,VERSION,PRIOR,compose,digest
from build_movie_test_disc import write_plan
from package_archive_test_disc import substitute_payload_sector
from disc_inventory import Disc,SECTOR
from afs_layout import require_native_layouts


def read(p):return json.loads(p.read_text('utf-8'))


def plan():
    target=compose()[0];component=compose()[6];assert (OUT/'WMAP.AFS').read_bytes()==target
    raw=(OUT/'native-test.json').read_bytes();proof=json.loads(raw)
    assert proof['archive_sha256']==digest(target) and proof['component_sha256']==digest((OUT/'component-report.json').read_bytes())
    assert proof['label_count']==10 and proof['protected_marker_sprites']==18 and proof['registration']['textures']==2
    assert len(proof['geometry']['cases'])==28 and proof['texture_dimensions']==[1024,256]
    base=ROOT/'work/output'/PRIOR;previous=read(base/'english-disc-report.json')
    assert previous['validation']['reextracted_files']=='all 14 exact' and previous['validation']['changed_sector_EDC_ECC']=='pass'
    assert previous['validation']['unrelated_track_bytes']=='all unchanged'
    cue=base/'disc'/f'Rayblade English Test {PRIOR}.cue';disc=Disc(cue);entries={r['path']:r for r in disc.inventory()}
    inherited={}
    for name,row in previous['files'].items():
        payload=(base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes();r=entries[name]
        assert len(payload)==row['size'] and digest(payload)==row['sha256'] and disc.read(r['lba'],r['size'])==payload
        inherited[name]=payload
    assert proof['executable_sha256']==digest(inherited['1ST_READ.BIN'])
    historical=list(previous['historical_native_evidence']);raw=(base/'counter-menu-native-test.json').read_bytes();v=json.loads(raw)
    assert digest(raw)==previous['counter_menu_proof_sha256'] and v['executable_sha256']==digest(inherited['1ST_READ.BIN'])
    historical.append({'file':'counter-menu-native-test.json','sha256':digest(raw),'actual_tested_build':PRIOR,
        'executable_sha256':v['executable_sha256'],'scope':'Exact executable/name/font/menu payloads retained in .44'})
    for row in historical:assert digest((base/row['file']).read_bytes())==row['sha256']
    targets=dict(inherited,**{'WMAP.AFS':target});require_native_layouts(targets)
    source=inherited['WMAP.AFS'];r=entries['WMAP.AFS'];assert len(source)==len(target)==r['size']
    orig=Disc(next(ROOT.glob('*.cue'))).read(r['lba'],r['size']);changes=[]
    for i in range((len(target)+2047)//2048):
        a,b=source[i*2048:(i+1)*2048],target[i*2048:(i+1)*2048]
        if a==b:continue
        lba=r['lba']+i;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba']);offset=(track['index']+lba-track['start_lba'])*SECTOR
        with track['path'].open('rb') as fh:fh.seek(offset);sector=fh.read(SECTOR)
        changes.append((track['path'].name,offset,substitute_payload_sector(sector,a,b)))
    old=sum(source[i:i+2048]!=orig[i:i+2048] for i in range(0,len(source),2048))
    new=sum(target[i:i+2048]!=orig[i:i+2048] for i in range(0,len(target),2048))
    report={'version':VERSION,'source_build':PRIOR,'kind':'Local map-font readability build; full translation unfinished',
        'movie_extent':previous['movie_extent'],'movie_extents':previous['movie_extents'],'movies':previous['movies'],
        'original_audio_sector_count':previous.get('original_audio_sector_count',4041),
        'files':{n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        'new_changed_sectors':len(changes),'total_changed_sector_locations_from_original':previous['total_changed_sector_locations_from_original']+new-old,
        'historical_native_evidence':historical,'map_font_component':component,'map_font_native_proof':proof,
        'map_font_proof_sha256':digest((OUT/'native-test.json').read_bytes()),'component_manifest_name':'map-font-component.json',
        'readme_component_text':'Rebuilt all ten world-map names using exact original Skies glyphs and variable spacing.\n'
            'Four-times-detail 1024x256 font texture, real four-level transparency, bright cream text and thin dark edge.\n'
            'Integrated in WMAP.AFS; 512 KiB added texture storage. Terrain/marker pixels and every executable/text payload unchanged.\n'
            'Includes all 0.1.43 menu/help fixes and earlier dialogue reflow.\n'
            'TEST: fresh-boot GDI, load a normal save, inspect the world map with and without dialogue and during movement.\n',
        'readme_movie_text':previous['readme_movie_text'],
        'proof_scope':'Independent original Skies masks/alpha; protected marker/art exact; 21 native archive lookups; '
            'native two-texture registration, all 28 sprite bounds/normalized UVs, texture format and both PRS streams. '
            'I/O/allocation fixtures are bounded. Live texture upload/VRAM, fade and overlaps remain pending.',
        'pending':list(dict.fromkeys(['Live high-detail map labels: texture upload/VRAM, contrast, dialogue fade, overlap and navigation',*previous['pending']])),
        'release':False}
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'));assert len(names)==5
    return disc,cue,inherited,targets,changes,names,historical,report


def finalize(planned):
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','map-labels-preview.png','map-labels.dat','markers.pvr','labels.pvr'):
        shutil.copyfile(OUT/name,out/('map-font-'+name))
    manifest=read(out/'font4x-patch.json');manifest.update(version=VERSION,previous_build=PRIOR,
        status='Original Skies world-map labels integrated; native checks pass; live map/VRAM appearance pending')
    manifest['current_payload_identities']=planned[7]['files']
    manifest['files'].setdefault('WMAP.AFS',{})['target_sha256']=digest(planned[3]['WMAP.AFS'])
    manifest['map_font']={'version':VERSION,'proof':'map-font-native-test.json','texture_dimensions':[1024,256],
        'added_VRAM_bytes':524288,'glyph_shapes':'exact original Skies','live_validation':'pending'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Only WMAP.AFS changed. Executable/font/text and all other payloads exact; historical proofs keep actual identities.'}
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args();p=plan()
    print('PASS:',len(p[4]),'sector edits;',len(p[3]),'payloads;',len(p[6]),'historical proofs.',flush=True)
    if not a.write:print('DRY RUN: no disc or metadata written.');return
    write_plan(p,VERSION,PRIOR,{'WMAP.AFS':p[3]['WMAP.AFS']});finalize(p)


if __name__=='__main__':main()
