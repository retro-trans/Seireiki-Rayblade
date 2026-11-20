"""Verify 0.7.31 changes only movie geometry from the reported working 0.7.28.

Dry unless --write. Build artifacts and package receipts remain immutable.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    before,after=[ROOT/'work/output'/v for v in ('0.7.28','0.7.31')]
    old,new=[(p/'1ST_READ.BIN').read_bytes() for p in (before,after)]
    assert len(old)==len(new)
    edits=[(i,a,b) for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    allowed=set(range(0x2a150,0x2a158))|set(range(0x6b7a8,0x6b7c8))
    assert edits and {i for i,_,_ in edits}<=allowed
    a,b=[read(p/'english-disc-report.json') for p in (before,after)]
    assert set(a['files'])==set(b['files'])
    assert [n for n in b['files'] if a['files'][n]!=b['files'][n]]==['1ST_READ.BIN']
    for name in b['files']:
        if name=='1ST_READ.BIN':continue
        relative='text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name
        assert (before/relative).read_bytes()==(after/relative).read_bytes(),name
    movie=read(after/'midpoint-hardware-diagnostic.json')
    native=read(after/'midpoint-hardware-native-test.json')
    assert movie['movie_only_changed_bytes_from_0_7_28']==len(edits)
    assert movie['executable_sha256']==native['executable_sha256']==sha(after/'1ST_READ.BIN')
    assert native['native_glyph_cases']==804 and len(native['allocation_cases'])==8
    assert native['VGA_cases']==96 and native['movie_cases']==129
    # The 0.7.31 proof executes historical 0.7.5 movie initialization at 2x.
    assert movie['historical_midpoint']=='0.7.5'
    package=ROOT/'work/output/dcp-0.7.31-diagnostic'
    bundle=read(package/'bundle-validation.json')
    assert bundle['sha256']==sha(package/bundle['asset'])
    proof=read(package/'original-apply-validation.json')
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256']==bundle['game_tree_sha256']
    previous,target=[read(ROOT/f'work/output/dcp-{v}-diagnostic/target-tree.json') for v in ('0.7.28','0.7.31')]
    assert set(previous['files'])==set(target['files'])
    assert [n for n in target['files'] if target['files'][n]!=previous['files'][n]]==['1ST_READ.BIN']
    result={
        'date':'2026-11-03','version':'0.7.31','historical_source':'0.7.5',
        'baseline':'0.7.28, Native-only historical 0.7.4',
        'baseline_hardware_report':read(ROOT/'docs/hardware-entry-hang-results.json')['results']['0.7.28'],
        'scope':'Movie geometry only: two setter pointers plus position/size wrappers. Every other executable byte and every game asset is exact 0.7.28.',
        'changed_executable_bytes':len(edits),'allowed_spans':['0x2a150:0x2a158','0x6b7a8:0x6b7c8'],
        'executable_sha256':sha(after/'1ST_READ.BIN'),
        'all_13_other_modified_payloads_exact_baseline':True,
        'complete_WIN00_exact_baseline':True,'all_140_game_files_checked':True,
        'normalization':movie,'native_validation':native,'disc_validation':b['validation'],
        'DCP':dict(bundle,path=str((package/bundle['asset']).relative_to(ROOT)).replace('\\','/')),
        'interpretation':movie['result_interpretation'],
        'original_entry_hang':'Test first conversation and Clear 2 -> Next separately from the later Hallway; 0.7.30 checkpoint clarification remains pending.',
        'test':movie['test'],'public_release':False,'upgrade_patch':False,
        'hardware_result':'pending','cause_confirmed':False}
    reported=read(ROOT/'docs/hardware-entry-hang-results.json').get('results',{}).get('0.7.31')
    if reported:
        result.update(last_updated='2026-11-04',hardware_result=reported,
                      hardware_follow_up_source='docs/hardware-entry-hang-results.json')
    if args.write:
        (ROOT/'docs/hardware-movie-only-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        path=ROOT/'docs/hardware-chapter-transition.json'
        current=read(path)
        current['working_baseline_movie_control']={
            'version':'0.7.31','source':'0.7.28 plus only historical movie scaling',
            'documentation':'docs/hardware-movie-only-diagnostic.json','DCP':result['DCP']['path'],
            'status':'Full original-input DCP verified locally; hardware movie/gameplay result pending',
            'public_release':False,'upgrade_patch':False}
        current['next_compatibility_candidate'] = current['working_baseline_movie_control']
        current['hallway_bisection'].update(next_version='0.7.31',
            next_midpoint='Native-only historical 0.7.5; movie geometry only from reported working 0.7.28',
            on_fail='Investigate 0.7.5 movie scaling or its interaction with the working baseline on matched test paths',
            on_pass='Investigate 0.7.6 choice/map group for matched Hallway failure')
        if reported:
            current['working_baseline_movie_control']['status']=reported['status']
            current['working_baseline_movie_control']['hardware_report']=reported
            current['hallway_bisection'].update(
                good='0.7.31: Native-only historical 0.7.5, reported full-size movies with no black screen/scenario freezes on tested paths',
                narrowed_group='Historical 0.7.6 story-choice/map changes or their interaction; exact cause unconfirmed',
                next_version=None,next_midpoint='Next regression control must separate 0.7.6 story choices from map assets/hook',
                latest_result=reported)
        if 'cosmetic_candidate' in current:
            current['next_compatibility_candidate']=current['cosmetic_candidate']
        if 'map_grid_candidate' in current:
            current['next_compatibility_candidate']=current['map_grid_candidate']
        if 'full_catchup_candidate' in current:
            current['next_compatibility_candidate']=current['full_catchup_candidate']
        if 'map_hook_bypass_candidate' in current:
            current['next_compatibility_candidate']=current['map_hook_bypass_candidate']
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


if __name__=='__main__':
    main()
