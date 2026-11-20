"""Verify the two cosmetic changes preserve the hardware-tested 0.7.31 baseline.

Dry unless --write; requires a completed full original-input DCP application.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    before,after=[ROOT/'work/output'/v for v in ('0.7.31','0.7.32')]
    a,b=[(p/'1ST_READ.BIN').read_bytes() for p in (before,after)]
    changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    assert len(a)==len(b) and len(changed)==259
    assert set(changed)<=set(range(0xac2e4,0xac3f4))|{0x9c692}
    report=read(after/'hardware-cosmetic-component.json')
    assert sha(after/'1ST_READ.BIN')==report['executable_sha256']
    old,new=[read(p/'english-disc-report.json') for p in (before,after)]
    assert set(old['files'])==set(new['files'])
    assert [n for n in new['files'] if old['files'][n]!=new['files'][n]]==['1ST_READ.BIN']
    for name in new['files']:
        if name=='1ST_READ.BIN':continue
        path='text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name
        assert (before/path).read_bytes()==(after/path).read_bytes(),name
    loading=read(after/'loading-position-native-test.json')
    movie=read(after/'movie-edge-native-test.json')
    assert loading['executable_sha256']==movie['executable_sha256']==report['executable_sha256']
    assert loading['animation_frame_cases']==121 and loading['native_glyph_quads']==2420
    assert movie['geometry_cases']==20
    package=ROOT/'work/output/dcp-0.7.32-diagnostic'
    bundle=read(package/'bundle-validation.json')
    assert sha(package/bundle['asset'])==bundle['sha256']
    proof=read(package/'original-apply-validation.json')
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256']==bundle['game_tree_sha256']
    previous,target=[read(ROOT/f'work/output/dcp-{v}-diagnostic/target-tree.json') for v in ('0.7.31','0.7.32')]
    assert set(previous['files'])==set(target['files'])
    assert [n for n in target['files'] if previous['files'][n]!=target['files'][n]]==['1ST_READ.BIN']
    result={**report,
        'baseline_hardware_report':read(ROOT/'docs/hardware-entry-hang-results.json')['results']['0.7.31'],
        'all_13_other_modified_payloads_exact_baseline':True,
        'complete_WIN00_exact_baseline':True,'all_140_game_files_checked':True,
        'loading_validation':loading,'movie_edge_validation':movie,'disc_validation':new['validation'],
        'DCP':dict(bundle,path=str((package/bundle['asset']).relative_to(ROOT)).replace('\\','/')),
        'regression_boundary':'Working Native-only 0.7.5 baseline versus failing Native-only 0.7.6; story-choice/map changes or their interaction require separate isolation. No 0.7.6 changes are included here.'}
    reported=read(ROOT/'docs/hardware-entry-hang-results.json').get('results',{}).get('0.7.32')
    if reported:result['hardware_result']=reported
    if args.write:
        (ROOT/'docs/hardware-cosmetic-fixes.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        path=ROOT/'docs/hardware-chapter-transition.json';current=read(path)
        current['last_updated']='2026-11-04'
        current['reported_working_baseline']={'version':'0.7.31','hardware_report':result['baseline_hardware_report']}
        current['cosmetic_candidate']={
            'version':'0.7.32','source':'0.7.31 plus only loading geometry and movie-edge sampling',
            'documentation':'docs/hardware-cosmetic-fixes.json','DCP':result['DCP']['path'],
            'status':'Full original-input DCP verified locally; hardware cosmetic/regression test pending',
            'public_release':False,'upgrade_patch':False}
        current['next_compatibility_candidate']=current['cosmetic_candidate']
        if reported:
            current['cosmetic_candidate']['status']=reported['status']
            current['cosmetic_candidate']['hardware_report']=reported
        if 'map_grid_candidate' in current:current['next_compatibility_candidate']=current['map_grid_candidate']
        if 'full_catchup_candidate' in current:current['next_compatibility_candidate']=current['full_catchup_candidate']
        if 'map_hook_bypass_candidate' in current:current['next_compatibility_candidate']=current['map_hook_bypass_candidate']
        if 'asset_runtime_split_candidate' in current:
            current['next_compatibility_candidate'] = current['asset_runtime_split_candidate']
        if 'texture_budget_candidate' in current:
            current['next_compatibility_candidate'] = current['texture_budget_candidate']
        if 'framebuffer_candidate' in current:
            current['next_compatibility_candidate'] = current['framebuffer_candidate']
        if 'window_atlas_candidate' in current:
            current['next_compatibility_candidate'] = current['window_atlas_candidate']
        if 'display_polish_candidate' in current:
            current['next_compatibility_candidate'] = current['display_polish_candidate']
        path.write_text(json.dumps(current,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('version','changed_executable_bytes','all_13_other_modified_payloads_exact_baseline','DCP','hardware_result')},indent=2))


if __name__=='__main__':main()
