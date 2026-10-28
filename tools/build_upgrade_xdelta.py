"""Build a local upgrade between exact English builds; default 0.7.2 to 0.7.11."""
import argparse,hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
RTT=ROOT.parent/'retro-trans-tools'
FROM,TO='0.7.2','0.7.11'
OUT=ROOT/'work/output'/f'upgrade-{FROM}-to-{TO}'
LOCAL_SOURCE=False


def release_dir(version):
    public=ROOT/f'work/output/release-{version}-public'
    return public if (public/'publish/BUILD-MANIFEST.json').exists() else ROOT/f'work/output/release-{version}'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def config():
    target=json.loads((release_dir(TO)/'publish/BUILD-MANIFEST.json').read_text('utf-8'))
    base=ROOT/f'work/output/{TO}/disc'
    if LOCAL_SOURCE:
        # Recognition-only identity for an unpublished, verified local build.
        # No fictitious source release/assets are created or published.
        build=ROOT/f'work/output/{FROM}';source=build/'disc'
        proof=json.loads((build/'english-disc-report.json').read_text('utf-8'))
        assert proof['version']==FROM and proof['validation']['changed_sector_EDC_ECC']=='pass'
        from disc_inventory import Disc
        disc=Disc(source/f'Rayblade English Test {FROM}.cue');entries={r['path']:r for r in disc.inventory()}
        for name,row in proof['files'].items():
            raw=disc.read(entries[name]['lba'],entries[name]['size'])
            assert hashlib.sha256(raw).hexdigest()==row['sha256']
        old=json.loads(json.dumps(target));old['version']=FROM
        for row in old['solutions'][0]['files']:
            if row['output_name'].endswith('.gdi'):row['output_name']=f'Rayblade English Test {FROM}.gdi'
        for row in old['patches']:
            name=next(r['output_name'] for r in old['solutions'][0]['files'] if r['edition']==row['edition'])
            path=source/name;row['target_sha256']=digest(path);row['target_bytes']=path.stat().st_size
            row['patch']=row['patch'].replace('v'+TO,'v'+FROM)
    else:
        old=json.loads((release_dir(FROM)/'publish/BUILD-MANIFEST.json').read_text('utf-8'))
        source=release_dir(FROM)/'roundtrip-disc'
    new={'game_id':target['game_id'],'game_name':target['game_name'],'platform':target['platform'],
        'version':TO,'source_commit':target['source_commit'],'patches':[],'solutions':[]}
    solution=json.loads(json.dumps(target['solutions'][0]));old_patches={p['edition']:p for p in old['patches']}
    targets={p['edition']:p for p in target['patches']};changed=[]
    for item in solution['files']:
        edition=item['edition'];before=old_patches[edition];after=targets[edition]
        name=next(r['output_name'] for r in old['solutions'][0]['files'] if r['edition']==edition)
        src=source/name;dst=base/(f'Rayblade English Test {TO}.gdi' if item['output_name'].endswith('.gdi') else item['output_name'])
        assert digest(src)==before['target_sha256'] and src.stat().st_size==before['target_bytes']
        assert digest(dst)==after['target_sha256'] and dst.stat().st_size==after['target_bytes']
        suffix='GDI' if dst.suffix=='.gdi' else 'Track03' if '(Track 3)' in dst.name else 'Track05'
        if before['target_sha256']!=after['target_sha256']:changed.append(suffix)
        new['patches'].append({'patch':f'Rayblade-English-v{FROM}-to-v{TO}-{suffix}.xdelta',
            'edition':edition,'language':'en','source_version':FROM,'source_format':before['target_format'],
            'target_format':after['target_format'],'source':str(src),'target':str(dst)})
    for row in solution['copy_files']:
        p=source/row['name'];assert digest(p)==row['sha256'] and p.stat().st_size==row['bytes']
        row.pop('sha256');row.pop('bytes');row['source']=str(p)
    new['solutions']=[solution];assert changed==['Track05']
    return new,old,target,source,base


def verify(manifest,old,source,base):
    from retro_trans.catalog import Catalog,recognize,apply_plan
    from retro_trans.core import GitHubClient
    if LOCAL_SOURCE:
        # A local test disc also contains its original-input CUE. Including it
        # makes the catalog see two descriptor candidates (CUE and GDI).
        # Use the six actual English inputs only; hardlinks avoid copying BINs
        # and are safe because the backend treats every source as read-only.
        import os
        isolated=OUT/'local-source-disc';assert not isolated.exists();isolated.mkdir()
        names={r['output_name'] for r in old['solutions'][0]['files']}|{r['name'] for r in old['solutions'][0]['copy_files']}
        for name in names:
            if name.endswith('.gdi'):shutil.copyfile(source/name,isolated/name)
            else:os.link(source/name,isolated/name)
        source=isolated
    def record(m):return {'repo':'retro-trans/Seireiki-Rayblade','tag':'v'+m['version'],'manifest':m,
        'assets':{p['patch']:f"https://github.com/retro-trans/Seireiki-Rayblade/releases/download/v{m['version']}/{p['patch']}" for p in m['patches']}}
    # Isolated test catalog only. Published release manifests remain immutable.
    cat=Catalog({'schema_version':1,'releases':[record(old),record(manifest)]})
    found=recognize(source,cat);assert len(found)==1 and not found[0].problems
    plan=cat.plan(found[0]);assert plan.target.version==TO and len(plan.edges)==1
    assert plan.edges[0].asset.name.endswith('Track05.xdelta')
    client=Mock();client.download.side_effect=lambda asset,*args:OUT/'patches'/asset.name
    print('Actual Retro Trans upgrade:',plan.summary,flush=True)
    with patch.object(GitHubClient,'open',side_effect=AssertionError('Unexpected network')):
        result=apply_plan(source,OUT/'roundtrip-disc',plan,cat,client,OUT/'cache')
    outputs={};unchanged=[]
    expected={c['output_name'] for c in manifest['solutions'][0]['files']}|{c['name'] for c in manifest['solutions'][0]['copy_files']}
    assert {p.name for p in result.iterdir()}==expected
    for p in result.iterdir():
        reference=base/(f'Rayblade English Test {TO}.gdi' if p.suffix=='.gdi' else p.name)
        actual=digest(p);assert actual==digest(reference)
        outputs[p.name]={'bytes':p.stat().st_size,'sha256':actual}
        prior=source/(next(r['output_name'] for r in old['solutions'][0]['files'] if r['output_name'].endswith('.gdi')) if p.suffix=='.gdi' else p.name)
        if actual==digest(prior):unchanged.append(p.name)
    assert len(unchanged)==5
    for row in manifest['patches']:
        name=next(r['output_name'] for r in old['solutions'][0]['files'] if r['edition']==row['edition'])
        assert digest(source/name)==row['source_sha256']
    after=recognize(result,cat);assert len(after)==1 and after[0].version==TO and not cat.plan(after[0]).edges
    refs=re.findall(r'"([^"]+)"',(result/f'Seireiki Rayblade English v{TO}.gdi').read_text('utf-8'))
    assert len(refs)==5 and all((result/n).is_file() for n in refs)
    return {'from':FROM,'to':TO,'native_xdelta_roundtrips':3,'Retro_Trans_Automatic_isolated_test':'pass',
        'xdelta_operations':1,'all_six_files_equal_verified_target':True,'source_preserved':True,
        'unchanged_components':unchanged,'outputs':outputs,'published_catalog_changed':False,
        'note':'Automatic test uses an isolated catalog containing the new upgrade route. Use Apply xdelta manually until a future explicitly requested release publishes a route.'}


def main():
    global FROM,TO,OUT,LOCAL_SOURCE
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true')
    ap.add_argument('--from-version',default=FROM);ap.add_argument('--to-version',default=TO)
    ap.add_argument('--local-source-build',action='store_true',help='Verify source identity directly from a local disc build, without claiming a source release')
    ap.add_argument('--finish',action='store_true',help='Resume verification/packaging of already built exact deltas')
    args=ap.parse_args();LOCAL_SOURCE=args.local_source_build
    FROM,TO=args.from_version,args.to_version
    assert all(re.fullmatch(r'0\.\d+\.\d+',v) for v in (FROM,TO)) and FROM!=TO
    OUT=ROOT/'work/output'/f'upgrade-{FROM}-to-{TO}'
    sys.path.insert(0,str(RTT))
    from retro_trans.release import build_release,validate_directory
    cfg,old,target,source,base=config()
    print(f'Plan: {FROM} -> {TO}; only Track 5 changes. Track 3 and GDI identity patches are optional verified copies.',flush=True)
    if not args.write:print('DRY RUN: source and target hashes verified; no files written.');return
    cp=OUT/'upgrade-local.json'
    if args.finish:
        assert json.loads(cp.read_text('utf-8'))==cfg
        manifest=validate_directory(OUT/'patches')
    else:
        assert not OUT.exists();OUT.mkdir(parents=True)
        if LOCAL_SOURCE:(OUT/'LOCAL-SOURCE-IDENTITY.json').write_text(json.dumps(old,indent=2)+'\n','utf-8')
        cp.write_text(json.dumps(cfg,indent=2)+'\n','utf-8')
        manifest=build_release(cp,OUT/'patches')
    proof=verify(manifest,old,source,base)
    folder=OUT/'patches'
    issue_note='Stage 6 issue #1 remains unresolved.'
    live_path=ROOT/f'work/output/{TO}/stage6-text-live-test.json'
    if live_path.exists() and json.loads(live_path.read_text('utf-8')).get('issue_1_reproduction_and_fix')=='pass':
        issue_note='Stage 6 issue #1 passes the supplied-save dialogue, menus and normal VMU save/load replay. See RELEASE-NOTES.txt for test limits.'
    clip_path=ROOT/f'work/output/{TO}/battle-clip-live-test.json'
    if clip_path.exists():
        clip=json.loads(clip_path.read_text('utf-8'))
        if clip.get('battle_clipping_and_selection_bars')=='pass' and clip.get('stage6_lossless_fix_byte_exact'):
            stage=json.loads((ROOT/clip['stage6_proof']).read_text('utf-8'))
            assert stage['issue_1_reproduction_and_fix']=='pass'
            issue_note='Stage 6 issue #1 fix is retained byte-exact from its supplied-save dialogue/menu/VMU replay. Current split-battle and selection-bar fixes pass native and live testing. See RELEASE-NOTES.txt for limits.'
    text=f'''Seireiki Rayblade English upgrade: {FROM} -> {TO}

Required input: the exact English {FROM} five-track BIN/GDI set matching
SOURCE-HASHES.txt.
This is an upgrade, not the full original-Japanese patch. Do not apply it
to Japanese Track 5 or another English build.

Only Track 5 changes. Using Retro Trans Tools:
1. Open Apply xdelta, or use DeltaPatcher/xdelta3.
2. Source: your {FROM} Seireiki Rayblade (Japan) (Track 5).bin.
3. Patch: Rayblade-English-v{FROM}-to-v{TO}-Track05.xdelta.
4. Write to a NEW folder with the same original Track 5 filename.
5. Copy Tracks 1, 2, 3 and 4 plus the GDI from {FROM} into that folder.
   The GDI contents are identical; its filename may be changed to
   Seireiki Rayblade English v{TO}.gdi.
6. Check TARGET-HASHES.txt, cold-boot the GDI and load a normal VMU save.
   Emulator save states retain old executable and font data.

Command after creating the English-{TO} output folder:
xdelta3 -d -s "Seireiki Rayblade (Japan) (Track 5).bin" "Rayblade-English-v{FROM}-to-v{TO}-Track05.xdelta" "English-{TO}/Seireiki Rayblade (Japan) (Track 5).bin"

Track03/GDI deltas are optional identity patches for complete manifest
verification. They leave those files byte-identical; copying is sufficient.
BUILD-MANIFEST.json declares the complete six-file output and unchanged
tracks. The real Retro Trans backend passed a one-operation complete-disc
upgrade using an isolated test catalog. This local package has not been
added to the published Automatic catalog or uploaded to GitHub.

Every game byte matches verified build {TO}. {issue_note}
See RELEASE-NOTES.txt for all improvements and remaining limitations.
'''
    (folder/'README-UPGRADE.txt').write_text(text,'utf-8')
    (folder/'UPGRADE-VALIDATION.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    notes=ROOT/f'docs/releases/v{TO}.md'
    if not notes.exists():notes=release_dir(TO)/'publish/README.txt'
    shutil.copyfile(notes,folder/'RELEASE-NOTES.txt')
    shutil.copyfile(release_dir(TO)/'publish/THIRD_PARTY_NOTICES.txt',folder/'THIRD_PARTY_NOTICES.txt')
    source_hashes={}
    for p in manifest['patches']:
        name=next(r['output_name'] for r in old['solutions'][0]['files'] if r['edition']==p['edition'])
        source_hashes[name]=p['source_sha256']
    source_hashes.update({r['name']:r['sha256'] for r in old['solutions'][0]['copy_files']})
    (folder/'SOURCE-HASHES.txt').write_text(''.join(f'{h}  {n}\n' for n,h in source_hashes.items()),'utf-8')
    (folder/'TARGET-HASHES.txt').write_text(''.join(f"{r['sha256']}  {n}\n" for n,r in proof['outputs'].items()),'utf-8')
    files=sorted(p for p in folder.iterdir() if p.name!='SHA256SUMS.txt')
    (folder/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in files),'utf-8')
    validate_directory(folder)
    path=OUT/f'Rayblade-English-v{FROM}-to-v{TO}-upgrade.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(folder.iterdir()):z.write(p,p.name)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for name in z.namelist():assert hashlib.sha256(z.read(name)).hexdigest()==digest(folder/name)
    proof['package']={'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':digest(path)}
    (ROOT/f'docs/upgrade-{FROM}-to-{TO}.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    print('PASS: upgrade and all six outputs verified. ZIP:',path,flush=True)


if __name__=='__main__':main()
