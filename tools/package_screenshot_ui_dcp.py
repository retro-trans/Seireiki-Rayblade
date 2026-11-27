"""Build and round-trip the original-input 0.7.51 local test DCP. No upload."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from build_screenshot_ui_fix import ROOT, VERSION, PRIOR, json_read, save


def build(rtt):
    sys.path.insert(0,str(rtt.resolve()))
    from retro_trans import dcp
    out=ROOT/f'work/output/dcp-{VERSION}-local'
    if out.exists():
        assert not (out/'build-original').exists(), 'Do not overwrite an existing package build.'
        source=json_read(out/'original-tree.json');target=json_read(out/'target-tree.json')
        assert Path(source['gdi']).is_file() and Path(target['gdi']).is_file()
    else:
        out.mkdir(parents=True)
        print('Inspecting original Japanese disc...',flush=True)
        source=dcp.inspect_disc(next(ROOT.glob('*.cue')),out/'inspect-original')
        save(out/'original-tree.json',source)
        print('Inspecting 0.7.51 target...',flush=True)
        target=dcp.inspect_disc(ROOT/f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.cue',out/'inspect-target')
        save(out/'target-tree.json',target)
    assert dcp.tree_hash(source['files'])=='81addd42981923ba95636d06e912598b61f275069082cef62938add7d0416db3'
    expected=json_read(ROOT/f'work/output/{VERSION}/english-disc-report.json')['files']
    for name,item in expected.items():
        if name=='IP.BIN':continue
        assert target['files'][name]['sha256']==item['sha256']
    # Inspection includes IP.BIN as well as the 140 filesystem payloads.
    assert set(source['files'])==set(target['files']) and len(target['files'])==141
    patch=out/f'Rayblade-English-v{VERSION}-LOCAL-TEST.dcp'
    print('Building original-input DCP...',flush=True)
    result=dcp.run('build',{'source':source['gdi'],'target':target['gdi'],'output':str(patch)},out/'build-original')
    metadata={'retro_trans_dcp':1,'game_id':'seireiki-rayblade','source_version':'original','version':VERSION,
        'diagnostic':True,'local_test':True,'baseline':PRIOR,'game_files':140,
        'source_tree_sha256':dcp.tree_hash(source['files']),'target_tree_sha256':dcp.tree_hash(target['files']),
        'bootsector_invariant_sha256':target['bootsector_invariant_sha256'],
        'engine':'Universal Dreamcast Patcher 2.1.8','upstream_commit':dcp.UPSTREAM,
        'font':'Native Skies 1x only','scope':'Album captions/title, small battle tabs, sort labels and weapon markers',
        'limitation':'UI hardware confirmation pending; hardware ranged-attack black scene remains unresolved.'}
    with zipfile.ZipFile(patch,'a') as archive:
        archive.comment=json.dumps(metadata,separators=(',',':')).encode()
        assert archive.testzip() is None
        assert archive.read('bootsector/IP.BIN')[0x3d:0x3e]==b'1'
    assert dcp.inspect_patch(patch)['metadata']==metadata
    print('Applying DCP to original input and verifying rebuilt disc...',flush=True)
    proof=dcp.apply(Path(source['gdi']),patch,out/'roundtrip-original')
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256']==metadata['target_tree_sha256']
    assert proof['bootsector_invariant_sha256']==metadata['bootsector_invariant_sha256']
    save(out/'original-apply-validation.json',proof)
    identity={'version':VERSION,'asset':str(patch.relative_to(ROOT)),'bytes':patch.stat().st_size,
        'sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'metadata':metadata,'build':result,
        'roundtrip':'All 140 files, boot metadata and audio verified','published':False}
    save(out/'package-validation.json',identity)
    (out/'README.txt').write_text('Rayblade English 0.7.51 - local UI test\n\n'
        'Apply Rayblade-English-v0.7.51-LOCAL-TEST.dcp to the original Japanese disc with Retro Trans Tools Automatic DCP.\n'
        'This is a full patch, not an upgrade for an already patched English image.\n'
        'For the locally verified rebuilt image, open roundtrip-original/disc.gdi and keep all five track files beside it.\n'
        'Cold boot; use a normal VMU save, not an old emulator save state.\n'
        'Check album captions/title, Trust Gauge/name tabs, sort labels, and weapon P/W markers.\n'
        'Check New Game/mission dialogue as a regression test. The hardware ranged-attack black scene remains unresolved.\n'
        'Native/layout/disc/DCP checks pass; live/hardware validation pending. No public release.\n','utf-8')
    print(json.dumps({k:identity[k] for k in ('asset','bytes','sha256','roundtrip')},indent=2),flush=True)
    return identity


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--rtt',required=True,type=Path);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    if a.write:build(a.rtt)
    else:print('Use --write to build and verify the local DCP from original input.')
