"""Package verified local 0.7.19 full xdelta. No GitHub operations."""
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'work/vendor'),str(ROOT.parent/'retro-trans-tools')]
from prepare_public_release import config,digest
from retro_trans.release import build_release,validate_directory
V='0.7.19';BASE=ROOT/'work/output'/V;OUT=ROOT/'work/output'/('release-'+V)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--finish',action='store_true');a=ap.parse_args()
    cfg=config(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),V,BASE)
    disc=json.loads((BASE/'english-disc-report.json').read_text('utf-8'));assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    if not a.write:print('DRY RUN: original Japanese -> local 0.7.19 full xdelta. Live battle and Retro Trans verification required before final ZIP. No publication.');return
    if not a.finish:
        assert not OUT.exists();OUT.mkdir();cp=OUT/'release-local.json';cp.write_text(json.dumps(cfg,indent=2)+'\n','utf-8')
        build_release(cp,OUT/'publish');print('PASS: original-input deltas built and decoded.');return
    live=json.loads((BASE/'battle-memory-live-test.json').read_text('utf-8'))
    assert all(live[k]=='pass' for k in ('startup','framebuffer_creation','native_font','battle_dialogue','battle_portrait','battle_windows','map_portraits','HUD_allocation_stress','status_menu'))
    auto=json.loads((OUT/'game-validation.json').read_text('utf-8'));assert auto['all_six_output_files_match_verified_local_build']
    folder=OUT/'publish';manifest=json.loads((folder/'BUILD-MANIFEST.json').read_text('utf-8'))
    readme='''Seireiki Rayblade English 0.7.19 - local test build

Fixes white dialogue/portrait/UI textures in the S004 battle reported
after a fresh boot of 0.7.18. Terrain and unit sprites exhausted that
build's texture pool before the dialogue could upload.

Restores the original Japanese geometry reservation: 768,352 bytes.
This recovers 3,360,416 bytes for textures relative to 0.7.18; the
earlier 640x480 change had inflated the reservation to almost 4 MiB.
Both SDK configuration branches and the current minimum checks pass.
Physical Dreamcast and full-game geometry headroom remain unverified.
Every other executable byte and all disc assets match 0.7.18 exactly.
Keeps only the original Skies Native 1x font, 640x480 RGB565 output,
VGA support, original movies and previous layout/startup repairs.

Original Japanese input: apply Track03 and Track05 deltas to matching
original BIN tracks and the GDI delta to the original Japanese CUE.
Write to a NEW folder with original track filenames, copying Tracks
1, 2 and 4 unchanged. Boot the GDI with all five BIN tracks present.
Use Retro Trans Tools Apply xdelta, DeltaPatcher or xdelta3.

For exact English 0.7.18 input, use the separate 0.7.18-to-0.7.19
upgrade. Cold boot after patching and load a normal VMU save.
Emulator save states retain older code and graphics state.

Fresh-boot Flycast verifies the reported battle and earlier world-map
portraits, the office cutaway and the status menu. Actual SDK checks
also fit four additional status surfaces and two more portraits while
the captured battle, current portrait and dialogue remain resident.
See GAME-VALIDATION.json for exact live scope and remaining limits.
Retro Trans produces all six exact output files and preserves inputs.
Full-route/long-session review and Stage 6 issue #1 remain unresolved.
Local package only; no GitHub release or Automatic catalog update.
'''
    (folder/'README.txt').write_text(readme,'utf-8')
    for source,target in [('THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt'),('CHANGELOG.md','CHANGELOG.txt')]:shutil.copyfile(ROOT/source,folder/target)
    proof={'version':V,'release':False,'native':json.loads((BASE/'battle-memory-native-test.json').read_text('utf-8')),
        'live':live,'disc':disc['validation'],'Retro_Trans':auto,
        'builder_sha256':{n:digest(ROOT/n) for n in ['tools/build_battle_memory_fix.py','tools/test_battle_memory.py','tools/inspect_vram_residency.py','tools/package_battle_memory_fix.py']}}
    (folder/'GAME-VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    sources={}
    for row in manifest['patches']:
        name='Seireiki Rayblade (Japan).cue' if row['source_format']=='cue' else next(x['output_name'] for x in manifest['solutions'][0]['files'] if x['edition']==row['edition'])
        sources[name]=row['source_sha256']
    sources.update({r['name']:r['sha256'] for r in manifest['solutions'][0]['copy_files']})
    (folder/'SOURCE-HASHES.txt').write_text(''.join(f'{h}  {n}\n' for n,h in sources.items()),'utf-8')
    (folder/'TARGET-HASHES.txt').write_text(''.join(f"{r['sha256']}  {n}\n" for n,r in auto['output_hashes'].items()),'utf-8')
    (folder/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(folder.iterdir()) if p.name!='SHA256SUMS.txt'),'utf-8')
    validate_directory(folder);path=OUT/f'Rayblade-English-v{V}-xdelta.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(folder.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for n in z.namelist():assert hashlib.sha256(z.read(n)).hexdigest()==digest(folder/n)
    result={'version':V,'release':False,'package':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,
        'sha256':digest(path),'zip_crc_and_member_hashes':'pass','Retro_Trans_roundtrip':'all six exact'}
    (OUT/'package-validation.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
