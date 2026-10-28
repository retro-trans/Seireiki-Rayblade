"""Package local 0.7.17 xdelta files. Dry first; no GitHub operations."""
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'work/vendor'),str(ROOT.parent/'retro-trans-tools')]
from prepare_public_release import config,digest
from retro_trans.release import build_release,validate_directory
V='0.7.17';BASE=ROOT/'work/output'/V;OUT=ROOT/'work/output'/('release-'+V)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--finish',action='store_true');args=ap.parse_args()
    cfg=config(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),V,BASE)
    disc=json.loads((BASE/'english-disc-report.json').read_text('utf-8'))
    assert disc['validation']['changed_sector_EDC_ECC']=='pass'
    if not args.write:print('DRY RUN: Japanese original -> local 0.7.17; three deltas, full Retro Trans verification and live proof required. No publication.');return
    if not args.finish:
        assert not OUT.exists();OUT.mkdir();cp=OUT/'release-local.json';cp.write_text(json.dumps(cfg,indent=2)+'\n','utf-8')
        build_release(cp,OUT/'publish');print('PASS: original-input deltas built and fully decoded.');return
    live=json.loads((BASE/'startup-memory-live-test.json').read_text('utf-8'))
    assert all(live[k]=='pass' for k in ('startup','framebuffer_creation','map_scene','native_font'))
    auto=json.loads((OUT/'game-validation.json').read_text('utf-8'));assert auto['all_six_output_files_match_verified_local_build']
    folder=OUT/'publish';manifest=json.loads((folder/'BUILD-MANIFEST.json').read_text('utf-8'))
    text='''Seireiki Rayblade English 0.7.17 - local test build

Fixes 0.7.16 startup corruption before NOW LOADING. The 16-bit video
change exposed an inherited geometry-budget calculation that aborted
graphics initialization. The original 4 MiB geometry reservation is now
explicit, and the normal SDK framebuffer creation/clearing completes.
Output remains 640x480, now with the correct RGB565 display format.

Keeps the original Skies Native (1x) font only. There is no HD font or
title font selector. Font pixels/advances/alpha and original movie files
are unchanged. Retains the lossless smaller map-marker atlas from
0.7.16. The unused lower half of the shared window atlas is removed,
preserving all 125 sprite pixels and anchors. Combined video-memory saving versus 0.7.15 is 1,335,296 bytes.
RGB565 has lower framebuffer color precision than the prior 24-bit output.

Original Japanese input: apply Track03 and Track05 deltas to matching
original BIN tracks and the GDI delta to the original Japanese CUE.
Write to a NEW folder, retaining the original track filenames. Copy
Tracks 1, 2 and 4 unchanged. Boot the resulting GDI with all five BINs.
Retro Trans Tools Apply xdelta, DeltaPatcher or xdelta3 can apply them.

For exact English 0.7.16 input, use the separate 0.7.16-to-0.7.17 upgrade.
Cold boot after patching, then load a normal VMU save. Emulator save
states retain older code and graphics data.

Native SDK arithmetic, display-format and map asset tests pass. All
fifteen disc payloads re-extract exactly, changed-sector EDC/ECC and
complete track preservation pass. Retro Trans produced all six exact
disc files. See GAME-VALIDATION.json for live startup/map evidence.
Physical Dreamcast and full-route review remain pending. Stage 6
issue #1 remains unresolved. This is not a GitHub release.
'''
    (folder/'README.txt').write_text(text,'utf-8')
    for name,target in [('THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt'),('CHANGELOG.md','CHANGELOG.txt')]:shutil.copyfile(ROOT/name,folder/target)
    native=json.loads((BASE/'startup-memory-native-test.json').read_text('utf-8'))
    historical=json.loads((BASE/'map-memory-native-test.json').read_text('utf-8'))
    map_proof={k:historical[k] for k in ('version','executable_sha256','archive_sha256','marker_atlas','SDK_archive_cases',
        'SDK_texture_info','map_registration','sprite_geometry','native_PRS','exact_marker_and_gutter_pixels')}
    map_proof['scope']='Unchanged map assets and native registration/geometry/PRS paths from 0.7.16; its failed display-mode claim is superseded by current startup proof.'
    validation={'version':V,'release':False,'native_startup':native,'map_asset_proof_inherited_from_0716':map_proof,
        'live':live,'disc':disc['validation'],'Retro_Trans':auto,
        'builder_sha256':{n:digest(ROOT/n) for n in ['tools/build_startup_memory_fix.py','tools/build_map_memory_fix.py','tools/package_startup_memory_fix.py']}}
    (folder/'GAME-VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n','utf-8')
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
