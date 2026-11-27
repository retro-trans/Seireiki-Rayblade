"""Stage and verify public 0.7.51 DCP assets. Does not upload or publish."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from prepare_hardware_public_release import read, save, sha, zip_members, progress

ROOT = Path(__file__).resolve().parents[1]
VERSION, PREVIOUS = '0.7.51', '0.7.50'
OUT = ROOT / 'work/output/release-0.7.51-dcp'
READY = OUT / 'publish'
LOCAL = ROOT / 'work/output/dcp-0.7.51-local'
EXE = '8f9a660cc3f586df2c3b34a5989acaa35d69e43118537852521a27399a4a75e1'
IDS = [{'platform': 'Dreamcast', 'kind': 'project', 'id': 'seireiki-rayblade'}]
PACKAGES = [('original', f'Rayblade-English-v{VERSION}.dcp'),
            (PREVIOUS, f'Rayblade-English-v{PREVIOUS}-to-v{VERSION}-upgrade.dcp')]
LIMITS = ['Long-range attacks reportedly lose their animation/show a black scene on physical hardware, for both player and CPU. Unresolved; owner reports Flycast is unaffected.',
          'The four 0.7.51 UI fixes have native/layout checks; physical hardware visual confirmation is pending.',
          'Stage 9 CG issue #5, held story translations, full-route and extended-session review remain open.']


def sources():
    return {'original': ROOT / 'Seireiki Rayblade (Japan).cue',
            PREVIOUS: ROOT / 'work/output/release-0.7.50-dcp/roundtrip-original/disc.gdi'}


def public_manifest():
    published = read(OUT / 'previous-public-release.json')
    assert published['tagName'] == 'v'+PREVIOUS and not published['isDraft'] and not published['isPrerelease']
    path = OUT / 'previous-public/DCP-AUTOMATIC.json'
    remote = next(a for a in published['assets'] if a['name'] == path.name)
    assert remote['digest'] == 'sha256:'+sha(path)
    manifest = read(path)
    assert manifest['version'] == PREVIOUS
    issued = ROOT / 'work/output/release-0.7.50-dcp/publish/Rayblade-English-v0.7.50.dcp'
    record = next(r for r in manifest['patches'] if r['metadata']['source_version'] == 'original')
    assert sha(issued) == record['sha256']
    return manifest


def track_identity(descriptor):
    from retro_trans.dcp_automatic import descriptor_tracks
    return [dict(bytes=p.stat().st_size, sha256=sha(p)) for p in descriptor_tracks(descriptor)]


def build():
    from retro_trans import dcp
    manifest = public_manifest()
    READY.mkdir()
    trees = {}
    for version, source in sources().items():
        print('Inspecting actual input: '+version, flush=True)
        trees[version] = dcp.inspect_disc(source, OUT/('inspect-'+version), progress=progress)
        save(OUT/('tree-'+version+'.json'), trees[version])
    old_meta = manifest['patches'][0]['metadata']
    assert dcp.tree_hash(trees[PREVIOUS]['files']) == old_meta['target_tree_sha256']
    assert trees[PREVIOUS]['bootsector_invariant_sha256'] == old_meta['bootsector_invariant_sha256']
    assert dcp.tree_hash(trees['original']['files']) == old_meta['source_tree_sha256']
    assert track_identity(sources()['original']) == manifest['patches'][0]['source_tracks']
    target = dcp.inspect_disc(LOCAL/'roundtrip-original/disc.gdi', OUT/'inspect-target', progress=progress)
    save(OUT/'target-tree.json', target)
    assert target['files'] == read(LOCAL/'target-tree.json')['files']
    assert target['files']['1ST_READ.BIN']['sha256'] == EXE
    proof = read(ROOT/'work/output/0.7.51/screenshot-ui-native-test.json')
    assert proof['executable_sha256'] == EXE
    assert len(target['files']) == 141
    assert {n for n in target['files'] if target['files'][n] != trees[PREVIOUS]['files'][n]} == {'1ST_READ.BIN','ALBUM.AFS','WIN00.AFS','D_NAMES.BIN'}
    records = []
    for version, name in PACKAGES:
        patch = READY/name
        if version == 'original':
            local = LOCAL/'Rayblade-English-v0.7.51-LOCAL-TEST.dcp'
            assert sha(local) == read(LOCAL/'package-validation.json')['sha256']
            shutil.copy2(local, patch)
        else:
            dcp.run('build', dict(source=trees[version]['gdi'], target=target['gdi'], output=str(patch)), OUT/'build-upgrade', progress=progress)
        before = zip_members(patch)
        metadata = dict(retro_trans_dcp=1, game_id='seireiki-rayblade', game_name='Seireiki Rayblade',
            disc=1, source_version=version, target_version=VERSION, version=VERSION,
            source_tree_sha256=dcp.tree_hash(trees[version]['files']), target_tree_sha256=dcp.tree_hash(target['files']),
            bootsector_invariant_sha256=target['bootsector_invariant_sha256'], game_files=140,
            engine='Universal Dreamcast Patcher 2.1.8', upstream_commit=dcp.UPSTREAM,
            font='Original Skies Native 1x only', diagnostic=False, public_release=True, package_ids=IDS,
            hardware_result='Ranged-attack animation failure reported on hardware; unresolved. UI fixes await hardware visual confirmation.',
            known_issues=LIMITS)
        with zipfile.ZipFile(patch, 'a') as z:
            z.comment = json.dumps(metadata, separators=(',', ':')).encode()
            assert z.testzip() is None
            if version == 'original': assert z.read('bootsector/IP.BIN')[0x3d:0x3e] == b'1'
        assert zip_members(patch) == before
        assert dcp.inspect_patch(patch)['metadata'] == metadata
        records.append(dict(patch=name, bytes=patch.stat().st_size, sha256=sha(patch), edition='jp-disc1',
                            metadata=metadata, source_tracks=track_identity(sources()[version])))
    save(OUT/'packages.json', records)


def verify():
    from retro_trans import dcp
    public_manifest()
    target = read(OUT/'target-tree.json')
    records = read(OUT/'packages.json')
    checks = []
    for version, name in PACKAGES:
        row = next(r for r in records if r['patch'] == name)
        patch = READY/name
        assert sha(patch) == row['sha256']
        assert track_identity(sources()[version]) == row['source_tracks']
        proof = dcp.apply(sources()[version], patch, OUT/('roundtrip-'+version), progress=progress)
        assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
        assert proof['verified_game_tree_sha256'] == dcp.tree_hash(target['files'])
        assert proof['bootsector_invariant_sha256'] == target['bootsector_invariant_sha256']
        assert track_identity(sources()[version]) == row['source_tracks']
        save(OUT/('apply-'+version+'.json'), proof)
        checks.append(dict(source_version=version, patch=name, patch_sha256=sha(patch), all_game_files_verified=140,
            bootsector_verified=True, VGA_supported=True, audio_content_and_sample_alignment_preserved=True,
            source_preserved=True, target_tree_sha256=proof['verified_game_tree_sha256'],
            bootsector_invariant_sha256=proof['bootsector_invariant_sha256']))
        print('PASS: '+version+' -> '+VERSION, flush=True)
    save(OUT/'roundtrip-validation.json', dict(version=VERSION, format='DCP', routes=checks))


def seal():
    from retro_trans.dcp_automatic import validate_manifest, load_records, recognize, plan
    from retro_trans.game_library import validate_registration
    prior = public_manifest()
    records = read(OUT/'packages.json')
    verification = read(OUT/'roundtrip-validation.json')
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    manifest = dict(schema_version=1, format='DCP', game_id='seireiki-rayblade', game_name='Seireiki Rayblade',
        platform='Dreamcast', language='en', version=VERSION, minimum_app_version='0.5.20', source_commit=commit,
        package_ids=IDS, patches=records)
    validate_manifest(manifest)
    validate_registration(manifest, 'retro-trans/Seireiki-Rayblade')
    save(READY/'DCP-AUTOMATIC.json', manifest)
    verification.update(source_commit=commit, tested_payload_executable_sha256=EXE,
        payloads='Exact local 0.7.51 game files; publication only changes DCP metadata.',
        native_checks='docs/screenshot-ui-fixes.json', hardware_status=LIMITS[0], limits=LIMITS)
    save(READY/'VALIDATION.json', verification)
    shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.txt', READY/'THIRD_PARTY_NOTICES.txt')
    shutil.copy2(ROOT/'docs/releases/v0.7.51.md', READY/'RELEASE-NOTES-v0.7.51.md')
    (READY/'README-v0.7.51.txt').write_text('''Seireiki Rayblade English 0.7.51 - DCP patches

Use current Retro Trans Tools for Windows (Automatic requires 0.5.20+):
https://github.com/retro-trans/retro-trans-tools/releases/latest

Original Japanese CUE/BIN: Rayblade-English-v0.7.51.dcp
Public 0.7.50 English image: Rayblade-English-v0.7.50-to-v0.7.51-upgrade.dcp
Automatic recognizes the supported original and verified 0.7.50 DCP-built GDI
after catalog refresh. For other matching 0.7.50 layouts, use the DCP tab;
input game files and boot metadata must still pass verification.
Other releases/local diagnostics: use original Japanese input with the full patch.

Select GDI output and a NEW folder. Keep the GDI and ALL generated tracks
together. For GDEMU, replace the complete folder. Cold-boot and load a normal
VMU save; do not resume an emulator save state from an older build.
Never overwrite your source. DCP verifies game files, boot code and CD audio.

Fixes: album captions/title, small Trust Gauge/name tabs, sorting labels,
and P/W weapon markers. Native Skies 1x font and earlier runtime fixes retained.
KNOWN ISSUE: long-range attacks can show a black scene with no animation on
physical hardware, for both player and CPU. This is NOT fixed in 0.7.51.
The project owner reports Flycast does not exhibit this issue. UI hardware
visual confirmation, full-route testing and Stage 9 CG issue #5 remain pending.
Translation is unfinished. See release notes for validation and other limits.

Free fan patch; do not sell the patch or pre-patched images. Supply your own game.
''', encoding='utf-8')
    for _, name in PACKAGES:
        row = next(r for r in records if r['patch'] == name)
        assert sha(READY/name) == row['sha256']
        with zipfile.ZipFile(READY/(name.removesuffix('.dcp')+'-DCP.zip'), 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for entry in (name,'README-v0.7.51.txt','THIRD_PARTY_NOTICES.txt','RELEASE-NOTES-v0.7.51.md'):
                z.write(READY/entry,entry)
        with zipfile.ZipFile(READY/(name.removesuffix('.dcp')+'-DCP.zip')) as z: assert z.testzip() is None
    assets = sorted(p for p in READY.iterdir() if p.is_file())
    assert len(assets) == 9
    assert not any(p.suffix.lower() in ('.xdelta','.bin','.gdi','.cue','.iso','.afs') for p in assets)
    (READY/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets), encoding='utf-8')
    def catalog(m):
        tag='v'+m['version']
        prefix='https://github.com/retro-trans/Seireiki-Rayblade/releases/download/'+tag+'/'
        return dict(repo='retro-trans/Seireiki-Rayblade',tag=tag,manifest=m,prerelease=False,
            manifest_sha256=sha(READY/'DCP-AUTOMATIC.json') if m['version']==VERSION else sha(OUT/'previous-public/DCP-AUTOMATIC.json'),
            assets={r['patch']:prefix+r['patch'] for r in m['patches']})
    profiles=load_records([catalog(prior),catalog(manifest)])
    routes=[]
    for version,path in sources().items():
        found=[p for p in recognize(path,profiles) if p.version==version]
        assert found
        chosen=plan(found[0]);assert chosen.version==VERSION
        routes.append(dict(source_version=version,target_version=chosen.version,patch=chosen.edges[0].name))
    save(OUT/'sealed-validation.json',dict(version=VERSION,source_commit=commit,automatic_routes=routes,
        assets=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(READY.iterdir())]))
    print('PASS: sealed DCP assets, registration and original/public-upgrade Automatic routes.',flush=True)


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rtt',type=Path,required=True)
    ap.add_argument('--phase',choices=('build','verify','seal'),required=True)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args();sys.path.insert(0,str(args.rtt.resolve()))
    if args.write: {'build':build,'verify':verify,'seal':seal}[args.phase]()
    else: print('DRY RUN:',args.phase,READY)
