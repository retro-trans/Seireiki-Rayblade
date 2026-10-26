"""Verify real Retro Trans complete-disc application and public asset hygiene. Dry first."""
import argparse,json,hashlib,subprocess,sys,re,ast
from pathlib import Path
from unittest.mock import Mock,patch
from build_bitmap_font import ROOT
from prepare_public_release import OUT,BASE,REPO,VERSION,digest


def staged_audit():
    paths=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    paths=[p for p in paths if p];assert paths
    blocked=[];large=[];prose=[]
    def inspect(value,name,at=''):
        if isinstance(value,dict):
            for k,v in value.items():inspect(v,name,at+'.'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):inspect(v,name,at+f'[{i}]')
        elif isinstance(value,str) and len(re.findall(r'[\u3040-\u30ff\u3400-\u9fff]',value))>35:prose.append((name,at))
    for name in paths:
        p=ROOT/name
        if name.startswith(('work/source/','work/output/','work/ui/','incoming/','work/vendor/')) or p.suffix.lower() in ('.bin','.afs','.pvr','.sfd','.cue','.gdi','.chd','.iso','.ram','.xdelta','.zip','.ttf','.otf'):
            blocked.append(name)
        if p.stat().st_size>95*1024*1024:large.append(name)
        if name.startswith('work/translation/') and not name.endswith('.en.json'):blocked.append(name)
        if p.suffix=='.json':inspect(json.loads(p.read_text('utf-8')),name)
        elif p.suffix=='.py':
            for node in ast.walk(ast.parse(p.read_text('utf-8-sig'))):
                if isinstance(node,ast.Constant) and isinstance(node.value,str):inspect(node.value,name,str(node.lineno))
    assert not blocked,blocked;assert not large,large;assert not prose,prose
    print('PASS:',len(paths),'staged source/doc/English-export files; no discs, font binaries, local captures or original script folders.')
    return {'staged_files':len(paths),'game_binaries_and_local_source_excluded':True,'translation_exports_only':True}


def verify(rtt, version=VERSION, base=BASE, out=OUT):
    VERSION,BASE,OUT=version,base,out
    sys.path.insert(0,str(rtt))
    from retro_trans.release import validate_directory
    from retro_trans.catalog import Catalog,recognize,apply_plan
    from retro_trans.core import GitHubClient
    directory=OUT/'publish';manifest=validate_directory(directory)
    assert manifest['version']==VERSION and manifest['schema_version']==2 and len(manifest['patches'])==3
    assert len(manifest['solutions'])==1 and len(manifest['solutions'][0]['copy_files'])==3
    record={'repo':REPO,'tag':'v'+VERSION,'manifest':manifest,
        'assets':{p['patch']:f'https://github.com/{REPO}/releases/download/v{VERSION}/'+p['patch'] for p in manifest['patches']}}
    cat=Catalog({'schema_version':1,'releases':[record]});sources=recognize(ROOT,cat)
    assert len(sources)==1 and not sources[0].problems
    source=sources[0];plan=cat.plan(source);assert len(plan.edges)==3
    client=Mock();client.download.side_effect=lambda asset,*args:directory/asset.name
    output=OUT/'roundtrip-disc';assert not output.exists()
    print('Actual Retro Trans plan:',plan.summary,flush=True)
    with patch.object(GitHubClient,'open',side_effect=AssertionError('Unexpected network during local solution test')):
        result=apply_plan(ROOT,output,plan,cat,client,OUT/'cache')
    expected={c['output_name'] for c in manifest['solutions'][0]['files']}|{c['name'] for c in manifest['solutions'][0]['copy_files']}
    assert {p.name for p in result.iterdir()}==expected and len(expected)==6
    hashes={}
    for p in result.iterdir():
        reference=BASE/'disc'/(f'Rayblade English Test {BASE.name}.gdi' if p.suffix=='.gdi' else p.name)
        actual=digest(p);assert actual==digest(reference),p.name
        hashes[p.name]={'sha256':actual,'bytes':p.stat().st_size}
    current=recognize(result,cat);assert len(current)==1 and current[0].version==VERSION and not cat.plan(current[0]).edges
    gdi=(result/f'Seireiki Rayblade English v{VERSION}.gdi').read_text('utf-8');assert gdi.splitlines()[0]=='5'
    import re
    refs=re.findall(r'"([^"]+)"',gdi);assert len(refs)==5 and all((result/name).is_file() for name in refs)
    # Required original inputs remained unchanged after the complete app flow.
    for p in manifest['patches']:
        source_path=ROOT/('Seireiki Rayblade (Japan).cue' if p['source_format']=='cue' else next(
            c['output_name'] for c in manifest['solutions'][0]['files'] if c['edition']==p['edition']))
        assert digest(source_path)==p['source_sha256']
    report={'version':VERSION,'source_build':BASE.name,'source_commit':manifest['source_commit'],
        'retro_trans_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=rtt,text=True).strip(),
        'manifest_schema':2,'full_delta_roundtrips':3,'real_automatic_solution_application':'pass',
        'all_six_output_files_match_verified_local_build':True,'output_hashes':hashes,
        'recognized_source':'original Japanese five-track CUE set','recognized_output':VERSION,
        'GDI_all_five_track_references_exist':True,'original_inputs_preserved':True,
        'canonical_release_directory_validation':'pass','local_game_validation':json.loads((BASE/'english-disc-report.json').read_text('utf-8'))['validation'],
        'pending':['Live newest map labels/VRAM/fade and menu appearance','Independent meaning review and full-route/long-session testing','503 held/untranslated story rows','Original Dreamcast hardware support unverified']}
    (OUT/'game-validation.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print(f'PASS: actual Automatic backend produced all five exact tracks and GDI; output recognized as {VERSION}; originals preserved.',flush=True)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--staged',action='store_true');ap.add_argument('--rtt',type=Path)
    ap.add_argument('--version',default=VERSION);ap.add_argument('--base-build',default='0.1.44');a=ap.parse_args()
    assert re.fullmatch(r'0\.\d+\.\d+',a.version) and re.fullmatch(r'0\.\d+\.\d+',a.base_build)
    if not a.verify:print('DRY RUN: staged hygiene audit or real Retro Trans solution round trip will run only with --verify.');return
    if a.staged:staged_audit()
    else:
        assert a.rtt and (a.rtt/'retro_trans/release.py').exists()
        verify(a.rtt.resolve(),a.version,ROOT/'work/output'/a.base_build,ROOT/'work/output'/('release-'+a.version))


if __name__=='__main__':main()
