"""Prepare and verify local hardware diagnostic DCPs. Never publishes. Dry first."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/output/dcp-0.7.24-diagnostic'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    global OUT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rtt', type=Path, required=True)
    ap.add_argument('--phase', choices=['inspect', 'build', 'verify', 'bundle'], required=True)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--version', choices=['0.7.24', '0.7.25'], default='0.7.24')
    ap.add_argument('--reuse-verified-sources', action='store_true', help='Reuse immutable original/public-23 inspection receipts from the completed 0.7.24 diagnostic. Target is always inspected anew.')
    a = ap.parse_args()
    version = a.version
    OUT = ROOT / ('work/output/dcp-' + version + '-diagnostic')
    target_sha = {'0.7.24': 'e2357f9913e5e34c92dce4c290bd3ce252acb425f73cad33be296ab38c032ddf',
                  '0.7.25': 'ce117561eb4d67cdfd7d183a2f6b4aa4a00baac8c15c5fda9c8e2d83e5042df1'}[version]
    sys.path.insert(0, str(a.rtt.resolve()))
    from retro_trans import dcp
    sources = {
        'original': ROOT / 'Seireiki Rayblade (Japan).cue',
        'previous': ROOT / 'work/output/0.7.23/disc/Rayblade English Test 0.7.23.cue',
        'target': ROOT / f'work/output/{version}/disc/Rayblade English Test {version}.cue',
    }
    names = {
        'original': f'Rayblade-English-v{version}-HARDWARE-DIAGNOSTIC.dcp',
        'previous': f'Rayblade-English-v0.7.23-to-v{version}-HARDWARE-DIAGNOSTIC.dcp',
    }
    print(('RUN' if a.write else 'DRY RUN'), a.phase, 'under', OUT, flush=True)
    if not a.write:
        for label, path in sources.items(): print(label, path, flush=True)
        return
    OUT.mkdir(exist_ok=True)
    progress = lambda m, f=None: print(m, flush=True)
    if a.phase == 'inspect':
        for label, source in sources.items():
            if a.reuse_verified_sources and label != 'target':
                assert version != '0.7.24'
                prior = ROOT / 'work/output/dcp-0.7.24-diagnostic'
                assert (prior / 'bundle-validation.json').is_file()
                result = json.loads((prior / (label + '-tree.json')).read_text(encoding='utf-8'))
                assert Path(result['gdi']).is_file()
                result['reused_inspection'] = str(prior / (label + '-tree.json'))
            else:
                result = dcp.inspect_disc(source, OUT / ('inspect-' + label), progress=progress)
            assert len(result['files']) == 141
            save(OUT / (label + '-tree.json'), result)
        return
    trees = {label: json.loads((OUT / (label + '-tree.json')).read_text(encoding='utf-8')) for label in sources}
    assert dcp.tree_hash(trees['original']['files']) == '81addd42981923ba95636d06e912598b61f275069082cef62938add7d0416db3'
    assert dcp.tree_hash(trees['previous']['files']) == 'c1f73e677d4edf93fea4f897a0d07ef78e510a8e712feba5ca926e587512d476'
    assert trees['target']['files']['1ST_READ.BIN']['sha256'] == target_sha
    assert trees['previous']['files']['1ST_READ.BIN']['sha256'] == '6899e263653b1a29de45ee7bf04778e1ad240c40a99763511bd2da7ce9abbffe'
    changes = [n for n in trees['target']['files'] if trees['target']['files'][n] != trees['previous']['files'][n]]
    assert changes == ['1ST_READ.BIN'], changes
    assert trees['original']['audio_tracks'] == trees['previous']['audio_tracks'] == trees['target']['audio_tracks']
    if a.phase == 'build':
        directory = OUT / 'packages'
        directory.mkdir()
        records = []
        for label, name in names.items():
            path = directory / name
            result = dcp.run('build', {'source': trees[label]['gdi'], 'target': trees['target']['gdi'], 'output': str(path)}, OUT / ('build-' + label), progress=progress)
            metadata = {
                'retro_trans_dcp': 1, 'game_id': 'seireiki-rayblade',
                'source_version': 'original' if label == 'original' else '0.7.23',
                'version': version, 'diagnostic': True,
                'source_tree_sha256': dcp.tree_hash(trees[label]['files']),
                'target_tree_sha256': dcp.tree_hash(trees['target']['files']),
                'game_files': 140, 'engine': 'Universal Dreamcast Patcher 2.1.8',
                'upstream_commit': dcp.UPSTREAM, 'font': 'Native Skies 1x only',
                'bootsector_invariant_sha256': trees['target']['bootsector_invariant_sha256'],
            }
            with zipfile.ZipFile(path, 'a') as z:
                z.comment = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
                assert z.testzip() is None
            assert dcp.inspect_patch(path)['metadata'] == metadata
            records.append({'asset': name, 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'metadata': metadata, 'native_builder': result})
        save(OUT / 'build-validation.json', {'version': version, 'diagnostic': True, 'packages': records})
        # Same filenames and track geometry as the public 0.7.23 raw-track package.
        # UDP understands CUE pregaps; its GDI reader does not support nonzero offsets.
        (directory / 'Rayblade-v0.7.23-source.cue').write_bytes(sources['previous'].read_bytes())
        details = ('This diagnostic disables only runtime text compression (705 executable bytes).\n'
                   'The Stage 6 text-memory fix is disabled: white or missing Stage 6 text may return.\n') if version == '0.7.24' else (
                   'This diagnostic restores the stock 0.7.2 video/rendering path (184 executable bytes).\n'
                   'The game renders at 320x240 with the original VGA scan-doubled output.\n'
                   'All current assets and the single Native font bank remain exact; HD and its selector remain removed.\n'
                   'Text may look less sharp because the stock renderer samples fewer pixels.\n'
                   'The Stage 6 lossless text compression remains enabled.\n')
        (directory / 'READ-ME.txt').write_text(
            f'Rayblade {version} HARDWARE DIAGNOSTIC - not a public release or confirmed fix\n\n'
            'Use Universal Dreamcast Patcher 2.1.8 (or a DCP-enabled Retro Trans Tools build).\n'
            'Choose GDI output for GDEMU. Keep your original image and VMU save.\n\n'
            f'FULL: apply Rayblade-English-v{version}-HARDWARE-DIAGNOSTIC.dcp to the original Japanese CUE/BIN.\n'
            f'UPGRADE: apply Rayblade-English-v0.7.23-to-v{version}-HARDWARE-DIAGNOSTIC.dcp to public 0.7.23.\n'
            'For the public raw-track image, put Rayblade-v0.7.23-source.cue beside its five BIN files\n'
            'and select that CUE as input. It only describes existing files; do not rename the BIN files.\n'
            'A different version must use the full patch on the Japanese original.\n\n'
            'Cold boot on the reporting GDEMU/VGA system. Test New Game first.\n'
            'Then load the normal Clear 2 VMU save and choose Next.\n'
            'Report whether chapter 3 loads or the screen stays black with music.\n\n'
            + details + 'Hardware compatibility is unconfirmed until the reporter tests it.\n', encoding='utf-8')
        return
    if a.phase == 'bundle':
        proofs = {label: json.loads((OUT / (label + '-apply-validation.json')).read_text(encoding='utf-8')) for label in names}
        for proof in proofs.values():
            assert proof['verified_game_tree_sha256'] == dcp.tree_hash(trees['target']['files'])
            assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
        files = sorted((OUT / 'packages').iterdir())
        checksums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files)
        sums = OUT / 'packages/SHA256SUMS.txt'
        sums.write_text(checksums, encoding='utf-8')
        files.append(sums)
        bundle = OUT / f'Rayblade-v{version}-HARDWARE-DIAGNOSTIC-DCP.zip'
        with zipfile.ZipFile(bundle, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for path in files: z.write(path, path.name)
        with zipfile.ZipFile(bundle) as z:
            assert z.testzip() is None
            for path in files: assert z.read(path.name) == path.read_bytes()
        save(OUT / 'bundle-validation.json', {
            'version': version, 'diagnostic': True, 'public_release': False,
            'asset': bundle.name, 'bytes': bundle.stat().st_size,
            'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
            'routes': {label: {'game_tree_sha256': p['verified_game_tree_sha256'],
                              'bootsector_invariant_sha256': p['bootsector_invariant_sha256'],
                              'audio_content_preserved': p['audio_tracks_preserved']} for label, p in proofs.items()},
        })
        print('Verified bundle:', bundle, flush=True)
        return
    for label, name in names.items():
        proof = dcp.apply(sources[label], OUT / 'packages' / name, OUT / ('roundtrip-' + label), progress=progress)
        assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
        save(OUT / (label + '-apply-validation.json'), proof)
        print('PASS:', label, proof['verified_game_tree_sha256'], flush=True)


if __name__ == '__main__': main()
