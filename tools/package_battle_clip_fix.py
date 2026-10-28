"""Prepare verified local 0.7.23 xdelta assets; never publish. Dry first."""
import argparse,json,subprocess,sys,shutil,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'work/vendor'),str(ROOT.parent/'retro-trans-tools')]
from prepare_public_release import config,digest
from retro_trans.release import build_release,validate_directory
V='0.7.23';BASE=ROOT/'work/output'/V;OUT=ROOT/'work/output'/('release-'+V)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--finish',action='store_true');a=ap.parse_args()
    cfg=config(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),V,BASE)
    disc=json.loads((BASE/'english-disc-report.json').read_text('utf-8'));assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    if not a.write:print('DRY RUN: local 0.7.23 original-input deltas; final ZIP requires live clipping/menu and Retro Trans evidence. Public upgrade source is 0.7.11. No publication.');return
    if not a.finish:
        assert not OUT.exists();OUT.mkdir();cp=OUT/'release-local.json';cp.write_text(json.dumps(cfg,indent=2)+'\n','utf-8');build_release(cp,OUT/'publish');print('PASS: original-input deltas built and decoded.');return
    live=json.loads((BASE/'battle-clip-live-test.json').read_text('utf-8'));assert live['battle_clipping_and_selection_bars']=='pass'
    auto=json.loads((OUT/'game-validation.json').read_text('utf-8'));assert auto['all_six_output_files_match_verified_local_build']
    folder=OUT/'publish';manifest=json.loads((folder/'BUILD-MANIFEST.json').read_text('utf-8'))
    readme='''Seireiki Rayblade English 0.7.23 - local test build

Repairs inclusive split-battle clipping, the displaced divider line and
short selection bars in forecast, counter-policy and action menus.
Retains Native Skies 1x only and the Stage 6 text-memory fix from 0.7.22.
Font pixels, colors, alpha, wording, game assets and statistics stay exact.

For exact English 0.7.11 input (the last public release), use the separate
0.7.11-to-0.7.23 upgrade. For original Japanese input, apply Track03 and
Track05 deltas to matching original BIN tracks, and the GDI delta to the
original Japanese CUE. Write to a NEW folder with original track names,
copying Tracks 1, 2 and 4 unchanged. Boot the GDI with all five tracks.
Use Retro Trans Tools Apply xdelta, DeltaPatcher or xdelta3.
Cold boot after patching and load a normal VMU save; emulator save states
retain previous code and graphics state.

GAME-VALIDATION.json records exact native checks, live combat/menu captures
and complete-disc round trips. Physical Dreamcast, complete routes,
extended sessions and independent translation proofreading remain pending.
There are 503 held/untranslated story rows. This is a work in progress.
Local package only; no GitHub release/catalog publication by this tool.
'''
    (folder/'README.txt').write_text(readme,'utf-8')
    for src,dst in [('THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt'),('CHANGELOG.md','CHANGELOG.txt')]:shutil.copyfile(ROOT/src,folder/dst)
    proof={'version':V,'release':False,'native':json.loads((BASE/'battle-clip-native-test.json').read_text('utf-8')),'live':live,
        'stage6_issue_1':json.loads((ROOT/'work/output/0.7.22/stage6-text-live-test.json').read_text('utf-8')),
        'disc':disc['validation'],'Retro_Trans':auto,'builder_sha256':{n:digest(ROOT/n) for n in ['tools/build_battle_clip_fix.py','tools/test_battle_clip.py','tools/record_battle_clip_build.py','tools/package_battle_clip_fix.py']}}
    (folder/'GAME-VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    sources={}
    for row in manifest['patches']:
        name='Seireiki Rayblade (Japan).cue' if row['source_format']=='cue' else next(x['output_name'] for x in manifest['solutions'][0]['files'] if x['edition']==row['edition'])
        sources[name]=row['source_sha256']
    sources.update({r['name']:r['sha256'] for r in manifest['solutions'][0]['copy_files']})
    (folder/'SOURCE-HASHES.txt').write_text(''.join(f'{h}  {n}\n' for n,h in sources.items()),'utf-8')
    (folder/'TARGET-HASHES.txt').write_text(''.join(f"{r['sha256']}  {n}\n" for n,r in auto['output_hashes'].items()),'utf-8')
    (folder/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(folder.iterdir()) if p.name!='SHA256SUMS.txt'),'utf-8');validate_directory(folder)
    path=OUT/f'Rayblade-English-v{V}-xdelta.zip';assert not path.exists()
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(folder.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for n in z.namelist():assert hashlib.sha256(z.read(n)).hexdigest()==digest(folder/n)
    result={'version':V,'release':False,'package':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path),'zip_crc_and_member_hashes':'pass','Retro_Trans_roundtrip':'all six exact'}
    (OUT/'package-validation.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
