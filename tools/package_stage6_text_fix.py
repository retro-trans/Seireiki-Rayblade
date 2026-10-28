"""Package verified local 0.7.22 full xdelta; no publication."""
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'work/vendor'),str(ROOT.parent/'retro-trans-tools')]
from prepare_public_release import config,digest
from retro_trans.release import build_release,validate_directory
V='0.7.22';BASE=ROOT/'work/output'/V;OUT=ROOT/'work/output'/('release-'+V)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--finish',action='store_true');a=ap.parse_args()
    cfg=config(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),V,BASE)
    disc=json.loads((BASE/'english-disc-report.json').read_text('utf-8'));assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    if not a.write:print('DRY RUN: original Japanese -> local 0.7.22 xdelta. Final ZIP requires supplied Stage 6 replay, menus/save and Retro Trans checks. No publication.');return
    if not a.finish:
        assert not OUT.exists();OUT.mkdir();cp=OUT/'release-local.json';cp.write_text(json.dumps(cfg,indent=2)+'\n','utf-8')
        build_release(cp,OUT/'publish');print('PASS: original-input deltas built and decoded.');return
    live=json.loads((BASE/'stage6-text-live-test.json').read_text('utf-8'));assert live['issue_1_reproduction_and_fix']=='pass'
    auto=json.loads((OUT/'game-validation.json').read_text('utf-8'));assert auto['all_six_output_files_match_verified_local_build']
    folder=OUT/'publish';manifest=json.loads((folder/'BUILD-MANIFEST.json').read_text('utf-8'))
    readme='''Seireiki Rayblade English 0.7.22 - local test build

Fixes Stage 6 dialogue/menu texture exhaustion reported in GitHub issue #1.
Generated Native text now uses lossless PVR VQ when all exact 2x2 blocks fit
the dictionary. Otherwise its original uncompressed form is retained.
A failing 1024x128 dialogue needs 34,816 video-memory bytes instead of
262,144. Font pixels, alpha levels, colors, 1x density and wording stay exact.
RGB source planes remain editable for append text. Compressed staging stays
alive with the original CPU allocation. All game assets are exact 0.7.21.
Retains grid/reticle alignment and earlier movie, startup and UI repairs.

For exact English 0.7.21 input, use the separate 0.7.21-to-0.7.22 upgrade.
For Japanese input, apply Track03 and Track05 deltas to matching original
BIN tracks and the GDI delta to the original Japanese CUE. Write to a
NEW folder with original track filenames, copying Tracks 1, 2 and 4
unchanged. Boot the GDI with all five BIN tracks present.
Use Retro Trans Tools Apply xdelta, DeltaPatcher or xdelta3.
Cold boot after patching and load a normal VMU save. Emulator save states
retain the previous executable and graphics state.

See GAME-VALIDATION.json for the exact supplied Stage 6 save replay,
dialogue, menu, save/load evidence and remaining limits. Native tests
decode generated VQ back to exact original texels and exercise the actual
SDK allocation on the captured failure. Retro Trans produces six exact
files and preserves the original inputs.
Physical Dreamcast and complete routes/long sessions remain unverified.
Local package only; no GitHub release or published catalog update.
'''
    (folder/'README.txt').write_text(readme,'utf-8')
    for source,target in [('THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt'),('CHANGELOG.md','CHANGELOG.txt')]:shutil.copyfile(ROOT/source,folder/target)
    proof={'version':V,'release':False,'native':json.loads((BASE/'stage6-text-native-test.json').read_text('utf-8')),
        'live':live,'disc':disc['validation'],'Retro_Trans':auto,
        'builder_sha256':{n:digest(ROOT/n) for n in ['tools/build_stage6_text_fix.py','tools/test_stage6_text.py','tools/prepare_stage6_test.py','tools/record_stage6_text_build.py','tools/package_stage6_text_fix.py']}}
    (folder/'GAME-VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    sources={}
    for row in manifest['patches']:
        name='Seireiki Rayblade (Japan).cue' if row['source_format']=='cue' else next(x['output_name'] for x in manifest['solutions'][0]['files'] if x['edition']==row['edition'])
        sources[name]=row['source_sha256']
    sources.update({r['name']:r['sha256'] for r in manifest['solutions'][0]['copy_files']})
    (folder/'SOURCE-HASHES.txt').write_text(''.join(f'{h}  {n}\n' for n,h in sources.items()),'utf-8')
    (folder/'TARGET-HASHES.txt').write_text(''.join(f"{r['sha256']}  {n}\n" for n,r in auto['output_hashes'].items()),'utf-8')
    (folder/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(folder.iterdir()) if p.name!='SHA256SUMS.txt'),'utf-8')
    validate_directory(folder);path=OUT/f'Rayblade-English-v{V}-xdelta.zip';assert not path.exists()
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(folder.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for n in z.namelist():assert hashlib.sha256(z.read(n)).hexdigest()==digest(folder/n)
    result={'version':V,'release':False,'package':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':digest(path),'zip_crc_and_member_hashes':'pass','Retro_Trans_roundtrip':'all six exact'}
    (OUT/'package-validation.json').write_text(json.dumps(result,indent=2)+'\n','utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
