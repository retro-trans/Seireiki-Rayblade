"""Stage the tested 0.7.50 as a DCP-only public release; never upload/publish."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION, PREVIOUS = '0.7.50', '0.7.23'
OUT = ROOT / 'work/output/release-0.7.50-dcp'
READY = OUT / 'publish'
DIAGNOSTIC = ROOT / 'work/output/dcp-0.7.50-diagnostic'
EXE = 'ef5254a341ccb48e04ce2d8b8a15247c2459ecd3fd9e21f2040cf08459424841'
PACKAGES = [('original', f'Rayblade-English-v{VERSION}.dcp'),
            (PREVIOUS, f'Rayblade-English-v{PREVIOUS}-to-v{VERSION}-upgrade.dcp')]
IDS = [{'platform': 'Dreamcast', 'kind': 'project', 'id': 'seireiki-rayblade'}]


def read(path): return json.loads(path.read_text('utf-8-sig'))
def save(path, data): path.write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def inputs():
    original = ROOT / 'Seireiki Rayblade (Japan).cue'
    previous = ROOT / f'work/output/{PREVIOUS}/disc/Rayblade English Test {PREVIOUS}.gdi'
    old = read(ROOT / f'work/output/dcp-{PREVIOUS}/target-tree.json')
    target = read(DIAGNOSTIC / 'target-tree.json')
    source = read(DIAGNOSTIC / 'original-tree.json')
    assert target['files']['1ST_READ.BIN']['sha256'] == EXE
    assert {n for n in target['files'] if target['files'][n] != old['files'][n]} == {'1ST_READ.BIN', 'WIN00.AFS'}
    published = read(OUT / 'previous-public-release.json')
    assert published['tagName'] == 'v'+PREVIOUS
    manifest_path = OUT / 'previous-public/BUILD-MANIFEST.json'
    remote = next(a for a in published['assets'] if a['name'] == manifest_path.name)
    assert remote['digest'] == 'sha256:'+sha(manifest_path)
    manifest = read(manifest_path)
    assert manifest['version'] == PREVIOUS
    # All public source and target tracks, including unchanged audio, must
    # match the actual released binary manifest before creating an upgrade.
    from retro_trans.dcp_automatic import descriptor_tracks
    original_tracks = descriptor_tracks(original)
    previous_cue = previous.with_suffix('.cue')
    previous_tracks = descriptor_tracks(previous_cue)
    assert len(original_tracks) == len(previous_tracks) == 5
    for i, (a, b) in enumerate(zip(original_tracks, previous_tracks)):
        if i in (2, 4):
            row = next(r for r in manifest['patches'] if r['source_version'] == 'original' and r['patch'].endswith(f'Track{i+1:02}.xdelta'))
            assert (a.stat().st_size, sha(a)) == (row['source_bytes'], row['source_sha256'])
            assert (b.stat().st_size, sha(b)) == (row['target_bytes'], row['target_sha256'])
        else: assert a.stat().st_size == b.stat().st_size and sha(a) == sha(b)
    return {'original': source, PREVIOUS: old}, target, {'original': original, PREVIOUS: previous}, {'original': original, PREVIOUS: previous_cue}


def build():
    from retro_trans import dcp
    trees, target, _, descriptors = inputs()
    READY.mkdir()
    records = []
    for version, name in PACKAGES:
        patch = READY / name
        if version == 'original':
            source = DIAGNOSTIC / 'packages/Rayblade-English-v0.7.50-HARDWARE-DIAGNOSTIC.dcp'
            validation = read(DIAGNOSTIC / 'build-validation.json')
            assert sha(source) == validation['sha256']
            shutil.copy2(source, patch)
            before = zip_members(source)
        else:
            dcp.run('build', {'source': trees[version]['gdi'], 'target': target['gdi'], 'output': str(patch)}, OUT / 'build-upgrade', progress=progress)
            before = zip_members(patch)
        metadata = dict(retro_trans_dcp=1, game_id='seireiki-rayblade', game_name='Seireiki Rayblade',
            disc=1, source_version=version, target_version=VERSION, version=VERSION,
            source_tree_sha256=dcp.tree_hash(trees[version]['files']), target_tree_sha256=dcp.tree_hash(target['files']),
            bootsector_invariant_sha256=target['bootsector_invariant_sha256'], game_files=140,
            engine='Universal Dreamcast Patcher 2.1.8', upstream_commit=dcp.UPSTREAM,
            font='Original Skies Native 1x only', diagnostic=False, public_release=True,
            hardware_result='User-reported passing on Dreamcast/GDEMU/VGA, 2026-11-20', package_ids=IDS)
        with zipfile.ZipFile(patch, 'a') as z:
            z.comment = json.dumps(metadata, separators=(',', ':')).encode()
            assert z.testzip() is None
            if version == 'original': assert z.read('bootsector/IP.BIN')[0x3d:0x3e] == b'1'
        assert zip_members(patch) == before
        assert dcp.inspect_patch(patch)['metadata'] == metadata
        from retro_trans.dcp_automatic import descriptor_tracks
        tracks = [dict(bytes=p.stat().st_size, sha256=sha(p)) for p in descriptor_tracks(descriptors[version])]
        records.append(dict(patch=name, bytes=patch.stat().st_size, sha256=sha(patch), edition='jp-disc1',
                            metadata=metadata, source_tracks=tracks))
        print('Prepared '+name, flush=True)
    save(OUT/'packages.json', records)


def zip_members(path):
    with zipfile.ZipFile(path) as z:
        return {n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}


def progress(message, fraction=None): print(message, flush=True)


def verify():
    from retro_trans import dcp
    _, target, sources, _ = inputs()
    records = read(OUT/'packages.json'); checks = []
    for version, name in PACKAGES:
        patch = READY/name; row = next(r for r in records if r['patch'] == name)
        assert sha(patch) == row['sha256']
        proof = dcp.apply(sources[version], patch, OUT/('roundtrip-'+version), progress=progress)
        assert proof['verified_game_tree_sha256'] == dcp.tree_hash(target['files'])
        assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
        assert proof['bootsector_invariant_sha256'] == target['bootsector_invariant_sha256']
        save(OUT/('apply-'+version+'.json'), proof)
        checks.append(dict(source_version=version, patch=name, patch_sha256=sha(patch),
            all_game_files_verified=140, bootsector_verified=True, VGA_supported=True,
            audio_content_and_sample_alignment_preserved=True, source_preserved=True,
            target_tree_sha256=proof['verified_game_tree_sha256'],
            bootsector_invariant_sha256=proof['bootsector_invariant_sha256']))
        print('PASS: public '+version+' -> '+VERSION, flush=True)
    # Rehash inputs after both actual applications, not just before them.
    inputs()
    save(OUT/'roundtrip-validation.json', dict(version=VERSION, format='DCP', routes=checks))


def seal():
    from retro_trans.dcp_automatic import validate_manifest, load_records, recognize, plan
    from retro_trans.game_library import validate_registration
    records = read(OUT/'packages.json'); verification = read(OUT/'roundtrip-validation.json')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = dict(schema_version=1, format='DCP', game_id='seireiki-rayblade', game_name='Seireiki Rayblade',
        platform='Dreamcast', language='en', version=VERSION, minimum_app_version='0.5.20',
        source_commit=commit, package_ids=IDS, patches=records)
    validate_manifest(manifest)
    validate_registration(manifest, 'retro-trans/Seireiki-Rayblade')
    save(READY/'DCP-AUTOMATIC.json', manifest)
    verification.update(source_commit=commit, hardware_report=read(ROOT/'docs/hardware-0750-follow-up.json'),
        native_checks='docs/hardware-complete-fixes.json', tested_payload_executable_sha256=EXE,
        limits=['Targeted hardware report; no full-route certification.', 'Stage 9 CG issue #5 remains open.'])
    save(READY/'VALIDATION.json', verification)
    shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.txt', READY/'THIRD_PARTY_NOTICES.txt')
    shutil.copy2(ROOT/'docs/releases/v0.7.50.md', READY/'RELEASE-NOTES-v0.7.50.md')
    readme = '''Seireiki Rayblade English 0.7.50 - DCP patches

Use current Retro Trans Tools for Windows (Automatic requires 0.5.20+).
https://github.com/retro-trans/retro-trans-tools/releases/latest

Original game: choose Rayblade-English-v0.7.50.dcp with your original Japanese
CUE/BIN set. Automatic recognizes the supported original after catalog refresh.

Upgrade: choose Rayblade-English-v0.7.23-to-v0.7.50-upgrade.dcp with the exact
public 0.7.23 English GDI. Use the DCP tab for that older offset-based GDI;
Automatic recognition of that layout is not supported. This is not an upgrade
from local diagnostics or other English versions. Use original input for those.

In the DCP tab, select the image and matching patch, select GDI output and a NEW
output folder, then apply. Keep the rebuilt GDI and ALL output tracks together.
For GDEMU, replace the complete game folder. Cold-boot and use a normal VMU save;
do not resume an emulator save state from an earlier build.

DCP rebuilds the disc layout. Rebuilt track hashes need not match earlier raw
images; the patcher verifies all game files, boot code and original CD audio.
No per-track xdelta patches are used. Never overwrite your source image.

The tested 0.7.50 game payloads are unchanged. Hardware testing was reported
successful on Dreamcast/GDEMU/VGA; full routes and long sessions remain unverified.
The translation remains unfinished; Stage 9 CG issue #5 is still under review.
Free fan patch; do not sell the patch or pre-patched images. Supply your own game.
'''
    (READY/'README-v0.7.50.txt').write_text(readme, 'utf-8')
    for version, name in PACKAGES:
        row = next(r for r in records if r['patch'] == name)
        assert sha(READY/name) == row['sha256']
        bundle = name.removesuffix('.dcp')+'-DCP.zip'
        with zipfile.ZipFile(READY/bundle, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for entry in (name, 'README-v0.7.50.txt', 'THIRD_PARTY_NOTICES.txt', 'RELEASE-NOTES-v0.7.50.md'):
                z.write(READY/entry, entry)
        with zipfile.ZipFile(READY/bundle) as z: assert z.testzip() is None
    assets = sorted(p for p in READY.iterdir() if p.is_file())
    (READY/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets), 'utf-8')
    assert not any(p.suffix.lower() in ('.xdelta','.bin','.gdi','.cue','.iso','.afs') for p in assets)
    # Exercise Automatic's actual recognizer and route selection, without UI.
    prefix = 'https://github.com/retro-trans/Seireiki-Rayblade/releases/download/v'+VERSION+'/'
    record = dict(repo='retro-trans/Seireiki-Rayblade', tag='v'+VERSION, manifest=manifest, prerelease=False,
        manifest_sha256=sha(READY/'DCP-AUTOMATIC.json'), assets={r['patch']:prefix+r['patch'] for r in records})
    profiles = load_records([record]); _, _, _, descriptors = inputs(); routes=[]
    for version, path in descriptors.items():
        found = recognize(path, profiles); assert len(found) == 1
        chosen = plan(found[0]); assert chosen.version == VERSION and found[0].version == version
        routes.append(dict(source_version=version, target_version=chosen.version, patch=chosen.edges[0].name))
    save(OUT/'sealed-validation.json', dict(version=VERSION, source_commit=commit, automatic_routes=routes,
        public_0_7_23_offset_GDI='DCP tab supported and round-trip verified; Automatic requires a matching CUE',
        assets=[dict(name=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(READY.iterdir())]))
    print('PASS: sealed DCP-only assets, registered game and Automatic routes.', flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtt', type=Path, required=True)
    p.add_argument('--phase', choices=('build','verify','seal'), required=True)
    p.add_argument('--write', action='store_true'); args=p.parse_args()
    sys.path.insert(0, str(args.rtt.resolve()))
    if not args.write: print('DRY RUN:', args.phase, READY)
    else: {'build':build, 'verify':verify, 'seal':seal}[args.phase]()
