"""Package choice/map fixes with unchanged 0.7.5 font and movie behavior."""
import argparse, copy, json, struct
from build_choice_map_fix import ROOT, OUT, VERSION, PRIOR, compose, digest
from build_native_font_mode_disc import plan as font_plan, trial
from build_movie_test_disc import write_plan
from package_archive_test_disc import substitute_payload_sector
from disc_inventory import Disc, SECTOR


def plan():
    files,story,component,*_=compose()
    base=ROOT/'work/output'/PRIOR
    font_component=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    font_component.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(files['1ST_READ.BIN']))
    def unchanged_font():return files['1ST_READ.BIN'],(base/'WIN00.AFS').read_bytes(),b'',{},font_component
    p,_=font_plan(compose_fn=unchanged_font,prior=PRIOR,version=VERSION)
    disc,cue,inherited,targets,changes,names,historical,report=p
    original=Disc(next(ROOT.glob('*.cue')));entries={r['path']:r for r in disc.inventory()};delta=0
    for name in ('D_SCE.AFS','WMAP.AFS'):
        source,target=inherited[name],files[name];entry=entries[name];targets[name]=target
        assert len(source)==len(target)==entry['size']
        orig=original.read(entry['lba'],len(source))
        for off in range(0,len(source),2048):
            a,b=source[off:off+2048],target[off:off+2048]
            if a==b:continue
            lba=entry['lba']+off//2048
            track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
            pos=(track['index']+lba-track['start_lba'])*SECTOR
            with track['path'].open('rb') as f:f.seek(pos);raw=f.read(SECTOR)
            changes.append((track['path'].name,pos,substitute_payload_sector(raw,a,b)))
            delta+=int(b!=orig[off:off+2048])-int(a!=orig[off:off+2048])
    report.update(kind='Local story choice rows and stable native world-map lettering',
        files={n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},new_changed_sectors=len(changes),
        total_changed_sector_locations_from_original=report['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='choice-map-component.json',
        readme_component_text=report['readme_component_text']+
            'Restored all 961 translated choice lists: one option per original selectable row.\n'
            'Thirteen long lists use the compact Skies font with the same 16-pixel logical row spacing; wording is unchanged.\n'
            'Map labels use original 12x24 glyphs in a 512x128 native-density texture, with whole-pixel placement.\n'
            'Opening fit, Native/HD selector and normal dialogue reflow retain 0.7.5 behavior.\n',
        proof_scope='Current choice formatter/parser/VM, map original-pixel, registration/geometry and restricted draw-hook checks; all 14 disc payloads and full track preservation. Historical font/movie checks keep their actual identities.')
    return p,component,story,font_component


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--trial',action='store_true');ap.add_argument('--write',action='store_true');a=ap.parse_args()
    assert not(a.trial and a.write)
    p,component,story,font_component=plan()
    print('Planned',len(p[4]),'sector substitutions; only executable, story bank and map archive changed.',flush=True)
    if a.trial:trial(p,component,out=OUT,prior=PRIOR,version=VERSION)
    elif a.write:
        proof=json.loads((OUT/'native-test.json').read_text('utf-8'));assert proof['files']==component['files']
        write_plan(p,VERSION,PRIOR,{n:p[3][n] for n in component['files']})
        out=ROOT/'work/output'/VERSION
        (out/'text/scenario-component-report.json').write_text(json.dumps(story,indent=2)+'\n','utf-8')
        for name,value in [('choice-map-component.json',component),('choice-map-native-test.json',proof),('font-mode-details.json',font_component)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
        manifest.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        for name in component['files']:manifest['files'].setdefault(name,{})['target_sha256']=digest(p[3][name])
        manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Font, 49,312 normal story streams, all other payloads, VGA boot and original movies retained. Current choice/map evidence is separate; previous native reports retain tested identities.'}
        manifest['choice_and_map_fix']={'component':'choice-map-component.json','proof':'choice-map-native-test.json'}
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
        from build_native_movie_font_disc import finish_metadata
        # Only adjust user instructions; retain current proof-reuse statement.
        readme=(out/'READ-ME.txt').read_text('utf-8').replace('Use Native on Dreamcast or Flycast at 1x output.','Select VGA in Flycast; 1x output is 640x480. Physical hardware/non-VGA checks remain pending.')
        (out/'READ-ME.txt').write_text(readme,'utf-8')
    else:print('DRY RUN: no disc written')


if __name__=='__main__':main()
