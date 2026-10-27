"""Package the selectable native/HD font, retaining VGA and original movies."""
import argparse
import copy
import json
import re
import shutil
from build_native_font_mode import ROOT,OUT,VERSION,PRIOR,compose,digest
from disc_inventory import Disc,SECTOR
from package_archive_test_disc import substitute_payload_sector
from build_movie_test_disc import write_plan


def plan(*,compose_fn=compose,prior=PRIOR,version=VERSION):
    exe,archive,font,_,component=compose_fn()
    base=ROOT/'work/output'/prior
    previous=json.loads((base/'english-disc-report.json').read_text('utf-8'))
    assert previous['validation']['reextracted_files']==f"all {len(previous['files'])} exact"
    assert previous['validation']['changed_sector_EDC_ECC']=='pass'
    assert previous['validation']['unrelated_track_bytes']=='all unchanged'
    cue=base/'disc'/f'Rayblade English Test {prior}.cue'
    disc=Disc(cue);entries={r['path']:r for r in disc.inventory()}
    inherited={}
    for name,row in previous['files'].items():
        path=base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)
        raw=path.read_bytes();ent=entries[name]
        assert digest(raw)==row['sha256'] and len(raw)==row['size']
        assert disc.read(ent['lba'],ent['size'])==raw
        inherited[name]=raw
    targets=dict(inherited,**{'1ST_READ.BIN':exe,'WIN00.AFS':archive})
    changes=[];delta=0;original=Disc(next(ROOT.glob('*.cue')))
    for name in ('1ST_READ.BIN','WIN00.AFS'):
        source,target=inherited[name],targets[name];ent=entries[name]
        assert len(source)==len(target)==ent['size']
        orig=original.read(ent['lba'],len(source))
        for off in range(0,len(source),2048):
            a,b=source[off:off+2048],target[off:off+2048]
            if a==b:continue
            lba=ent['lba']+off//2048
            track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
            position=(track['index']+lba-track['start_lba'])*SECTOR
            with track['path'].open('rb') as f:f.seek(position);raw=f.read(SECTOR)
            changes.append((track['path'].name,position,substitute_payload_sector(raw,a,b)))
            delta+=int(b!=orig[off:off+2048])-int(a!=orig[off:off+2048])
    report=copy.deepcopy(previous)
    report.update(version=version,source_build=prior,kind='Local selectable native/HD Skies font test',
        files={n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},
        new_changed_sectors=len(changes),
        total_changed_sector_locations_from_original=previous['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='font-mode-component.json',release=False,
        readme_component_text='At the title screen, X selects Native (1x), Y selects HD (up to 4x).\n'
            'Native is the cold-boot default. Selection lasts until reset; it is not written to the VMU.\n'
            'Use Native on Dreamcast or Flycast at 1x output. Both modes preserve existing word wrapping.\n'
            'Cold-boot this GDI; older emulator save states retain old executable/assets.\n'
            'VGA support, English wording and the original opening/demo movie bytes are retained.\n',
        proof_scope='Actual native raster/allocator and title UI construction/parser witnesses; all 14 file re-extractions and full track preservation. Historical reports retain their tested executable identities.',
        pending=['Physical Dreamcast native-font readability and hardware compatibility',
                 'Complete game/route/long-session review','Full independent translation review and held rows'])
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'))
    return (disc,cue,inherited,targets,changes,names,previous['historical_native_evidence'],report),component


def trial(p,component,*,out=OUT,prior=PRIOR,version=VERSION):
    out.mkdir(parents=True,exist_ok=True)
    folder=out/'disc';folder.mkdir(exist_ok=True)
    for name in p[5]:shutil.copyfile(p[1].parent/name,folder/name)
    for name,offset,raw in p[4]:
        with (folder/name).open('r+b') as f:f.seek(offset);f.write(raw)
    for extension in ('cue','gdi'):
        shutil.copyfile(p[1].parent/f'Rayblade English Test {prior}.{extension}',folder/f'Rayblade English Test {version}.{extension}')
    for name in ('1ST_READ.BIN','WIN00.AFS'):(out/name).write_bytes(p[3][name])
    (out/'font-mode-component.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
    print('Wrote disposable emulator candidate:',folder)


def finalize(p,component,*,version=VERSION,prior=PRIOR,proof_dir=OUT):
    out=ROOT/'work/output'/version
    for name in ('font-mode-native-test.json','title-font-native-test.json'):
        proof=json.loads((proof_dir/name).read_text('utf-8'))
        assert proof['executable_sha256']==component['executable_sha256']
        shutil.copyfile(proof_dir/name,out/name)
    (out/'font-mode-details.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
    manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
    manifest.update(version=version,previous_build=prior,status='Selectable native/HD Skies font; local test')
    manifest['current_payload_identities']=p[7]['files']
    for name in ('1ST_READ.BIN','WIN00.AFS'):manifest['files'][name]['target_sha256']=digest(p[3][name])
    manifest['font_modes']={k:v for k,v in component.items() if k not in ('metrics','labels','archive_packing')}
    manifest['kernel_bytes_used']=component['kernel_bytes']
    manifest['symbols']={k:hex(component['labels'][k]) for k in ('raster','allocate','initialize','flush')}
    scale=component.get('native_surface_scale',1)
    manifest['surface_scaling']=f'Native: {scale} texels per logical coordinate; HD: up to 4x per axis, capped at 1024 with existing allocation fallback'
    manifest['historical_component_reports']=f'Retain actual tested identities. Font member 0 has two banks; all 89 other WIN00 payloads remain exact {prior}.'
    manifest['native_proof_reuse']={'source_build':prior,'scope':'Historical tests retain actual hashes; new font/selector proofs are separate. Other 12 payloads, boot flag and VGA code retained.'}
    # All relocated library data is unchanged; update only its archive offset.
    import struct
    off,size=struct.unpack_from('<II',p[3]['WIN00.AFS'],8+52*8)
    manifest['library'].update(archive_member_offset=off,archive_member_bytes=size)
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
    library=json.loads((out/'library-patch-report.json').read_text('utf-8'))
    library.update(archive_member_offset=off,archive_member_bytes=size)
    (out/'library-patch-report.json').write_text(json.dumps(library,indent=2)+'\n','utf-8')
    assert (out/'IP.BIN').read_bytes()==(ROOT/'work/output'/prior/'IP.BIN').read_bytes()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');ap.add_argument('--trial',action='store_true')
    args=ap.parse_args();assert not(args.write and args.trial)
    p,component=plan()
    print('Plan:',VERSION,len(p[4]),'sector substitutions; 12 other payloads and VGA boot unchanged.')
    if args.trial:trial(p,component)
    elif args.write:
        for name in ('font-mode-native-test.json','title-font-native-test.json'):
            proof=json.loads((OUT/name).read_text('utf-8'))
            assert proof['executable_sha256']==component['executable_sha256']
        write_plan(p,VERSION,PRIOR,{n:p[3][n] for n in ('1ST_READ.BIN','WIN00.AFS')})
        finalize(p,component)
    else:print('DRY RUN: no disc written')


if __name__=='__main__':main()
