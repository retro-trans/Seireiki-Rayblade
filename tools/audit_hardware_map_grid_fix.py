"""Audit the original-input 0.7.33 map/grid candidate. Dry unless --write."""
import argparse,hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    before,after=[ROOT/'work/output'/v for v in ('0.7.32','0.7.33')]
    old,new=[(p/'1ST_READ.BIN').read_bytes() for p in (before,after)]
    report=read(after/'hardware-map-grid-component.json')
    spans=[(int(a,16),int(b,16)) for a,b in report['allowed_spans']]
    changed=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
    assert len(old)==len(new) and len(changed)==119
    assert set(changed)<={i for a,b in spans for i in range(a,b)}
    assert sha(after/'1ST_READ.BIN')==report['executable_sha256']
    a,b=[read(p/'english-disc-report.json') for p in (before,after)]
    assert set(a['files'])==set(b['files'])
    assert [n for n in b['files'] if a['files'][n]!=b['files'][n]]==['1ST_READ.BIN']
    for name in b['files']:
        if name=='1ST_READ.BIN':continue
        relative='text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name
        assert (before/relative).read_bytes()==(after/relative).read_bytes(),name
    budget=read(after/'hardware-budget-test.json');grid=read(after/'hardware-grid-test.json')
    assert budget['executable_sha256']==grid['executable_sha256']==report['executable_sha256']
    assert len(budget['actual_SDK_budget_cases'])==4
    current=[r for r in budget['actual_SDK_budget_cases'] if r['version']=='0.7.33']
    assert len(current)==2 and all(r['geometry_units']==384176 and r['reaches_allocator'] for r in current)
    assert len(grid['actual_game_fill_cases'])==4 and grid['adapter_fixtures']==5
    assert all(r['filled_tiles']==41 and r['vertices']==492 and r['all_xy_exactly_doubled'] for r in grid['actual_game_fill_cases'])
    assert grid['range_center_after_pixels']==grid['selection_arrow_center_pixels']==[320,240]
    assert grid['ABI_source_geometry_and_range_mask_preserved']=='pass'
    # Exact historical range adapter, without importing unrelated 0.7.20 bytes.
    legacy=(ROOT/'work/output/0.7.20/1ST_READ.BIN').read_bytes()
    assert new[0x6b940:0x6b998]==legacy[0x6b940:0x6b998]
    package=ROOT/'work/output/dcp-0.7.33-diagnostic'
    bundle=read(package/'bundle-validation.json');proof=read(package/'original-apply-validation.json')
    assert sha(package/bundle['asset'])==bundle['sha256']
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256']==bundle['game_tree_sha256']
    previous,target=[read(ROOT/f'work/output/dcp-{v}-diagnostic/target-tree.json') for v in ('0.7.32','0.7.33')]
    assert set(previous['files'])==set(target['files'])
    assert [n for n in target['files'] if previous['files'][n]!=target['files'][n]]==['1ST_READ.BIN']
    mode=read(after/'font-mode-details.json');assert mode['native_only'] and not mode['title_selector'] and mode['HD_bank_removed']
    evidence=read(ROOT/'work/ui/hardware-0732-map-grid-20261104/index.json')
    assert len(evidence['images'])==3
    for row in evidence['images']:assert sha(ROOT/row['copy'])==row['sha256']
    result={**report,'baseline_hardware_report':read(ROOT/'docs/hardware-entry-hang-results.json')['results']['0.7.32'],
            'screenshot_evidence':evidence,'all_13_other_modified_payloads_exact_baseline':True,
            'complete_WIN00_exact_baseline':True,'all_140_game_files_checked':True,
            'budget_validation':budget,'grid_validation':grid,'disc_validation':b['validation'],
            'DCP':dict(bundle,path=str((package/bundle['asset']).relative_to(ROOT)).replace('\\','/'))}
    if args.write:
        (ROOT/'docs/hardware-map-grid-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        path=ROOT/'docs/hardware-chapter-transition.json';current=read(path)
        current['last_updated']='2026-11-04'
        current['map_grid_candidate']={'version':'0.7.33','source':'0.7.32 plus only stock geometry reservation and range-fill XY adapter',
            'documentation':'docs/hardware-map-grid-diagnostic.json','DCP':result['DCP']['path'],
            'status':'Full original-input DCP verified locally; physical map/grid and scenario/busy-battle retest pending',
            'public_release':False,'upgrade_patch':False}
        current['next_compatibility_candidate']=current['map_grid_candidate']
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
