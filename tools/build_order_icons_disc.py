"""Package both corrected order-icon archives as local 0.1.34. Dry first."""
import argparse
import json
import re

from build_bitmap_font import ROOT, digest
from build_movie_test_disc import write_plan
from build_order_icons_patch import OUT, PRIOR, compose
from build_test_disc import regenerate
from disc_inventory import Disc, SECTOR

VERSION = '0.1.34'


def plan():
    base = ROOT/'work/output'/PRIOR
    previous = json.loads((base/'english-disc-report.json').read_text('utf-8'))
    assert previous['version']==PRIOR
    assert previous['validation']['reextracted_files']=='all 12 exact'
    assert previous['validation']['changed_sector_EDC_ECC']=='pass'
    assert previous['validation']['unrelated_track_bytes']=='all unchanged'
    cue = base/'disc'/f'Rayblade English Test {PRIOR}.cue'
    disc = Disc(cue)
    original = Disc(next(ROOT.glob('*.cue')))
    inventory = {r['path']:r for r in disc.inventory()}
    original_inventory = {r['path']:r for r in original.inventory()}
    inherited = {}
    for name, record in previous['files'].items():
        row = inventory[name]
        raw = disc.read(row['lba'],row['size'])
        path = base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)
        assert raw==path.read_bytes() and digest(raw)==record['sha256'] and len(raw)==record['size']
        inherited[name]=raw
    built = compose()
    archives, component = built[:2]
    assert component==json.loads((OUT/'component-report.json').read_text('utf-8'))
    proof_raw = (OUT/'native-test.json').read_bytes()
    proof = json.loads(proof_raw)
    assert proof['executable_sha256']==digest(inherited['1ST_READ.BIN'])
    assert proof['native_guard_and_ABI']=='pass' and proof['icon_cells']==15
    assert proof['archive_bytes_outside_declared_edits']=='exact'
    assert proof['native_order_selector']['case_count']==80
    historical = list(previous['historical_native_evidence'])
    file = 'attack-lettering-native-test.json'
    prior_raw = (base/file).read_bytes()
    prior_proof = json.loads(prior_raw)
    assert digest(prior_raw)==previous['attack_lettering_proof_sha256']
    assert prior_proof['archive_sha256']==digest(inherited['EFFECT.AFS'])
    assert not any(r['file']==file for r in historical)
    historical.append({'file':file,'sha256':digest(prior_raw),'actual_tested_build':prior_proof['source_build'],
                       'executable_sha256':prior_proof['executable_sha256'],
                       'scope':'Historical native component report; original scope and limitations retained'})
    for entry in historical:
        raw=(base/entry['file']).read_bytes()
        assert digest(raw)==entry['sha256'] and json.loads(raw)['executable_sha256']==entry['executable_sha256']
    changes, stats, handles = [], {}, {}
    try:
        for name,target in archives.items():
            source = inherited[name]
            assert (OUT/name).read_bytes()==target
            assert digest(source)==component['archives'][name]['source_archive_sha256']
            assert digest(target)==component['archives'][name]['target_archive_sha256']==proof['archives'][name]
            assert len(source)==len(target)
            row = inventory[name]
            assert row == original_inventory[name]
            orig = original.read(row['lba'],row['size'])
            changed = [n for n in range(len(target)//2048) if source[n*2048:(n+1)*2048]!=target[n*2048:(n+1)*2048]]
            stats[name]={'substitutions':len(changed),
                         'before_original_locations':sum(source[n:n+2048]!=orig[n:n+2048] for n in range(0,len(orig),2048)),
                         'after_original_locations':sum(target[n:n+2048]!=orig[n:n+2048] for n in range(0,len(orig),2048))}
            for n in changed:
                lba = row['lba']+n
                track = next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
                file = track['path'].name
                if file not in handles:
                    handles[file]=track['path'].open('rb')
                offset = (track['index']+lba-track['start_lba'])*SECTOR
                handles[file].seek(offset)
                raw = handles[file].read(SECTOR)
                assert len(raw)==SECTOR and regenerate(raw)==raw
                assert raw[16:2064]==source[n*2048:(n+1)*2048]
                patch=bytearray(raw)
                patch[16:2064]=target[n*2048:(n+1)*2048]
                changes.append((file,offset,regenerate(patch)))
    finally:
        for handle in handles.values():
            handle.close()
    assert len({(f,o) for f,o,_ in changes})==len(changes)
    targets = {**inherited,**archives}
    assert len(targets)==12 and len(historical)==22
    names = re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'))
    assert len(names)==5
    report={'version':VERSION,'source_build':PRIOR,
            'kind':'Local counterattack-order icon correction; full translation and live review incomplete',
            'movie_extent':previous['movie_extent'],'movie_extents':previous['movie_extents'],'movies':previous['movies'],
            'original_audio_sector_count':4041,'new_changed_sectors':len(changes),
            'total_changed_sector_locations_from_original':previous['total_changed_sector_locations_from_original']+sum(s['after_original_locations']-s['before_original_locations'] for s in stats.values()),
            'archive_changed_locations':stats,
            'files':{n:{'size':len(raw),'sha256':digest(raw)} for n,raw in targets.items()},
            'historical_native_evidence':historical,'order_icons_component':component,
            'order_icons_native_proof':proof,'order_icons_proof_sha256':digest(proof_raw),
            'inherited_components':'All ten unaffected preceding game payloads exact 0.1.33; font member and every non-icon atlas pixel exact',
            'component_manifest_name':'order-icons-component.json',
            'readme_component_text':'Corrects all three native copies of the five order icons: M Manual, C Counterattack, A Aggressive, S Safe, D Defend.\n'
                'Corrects the old Resupply/None misidentification; full menu descriptions remain intact. Restores the source icon bevels using the Manual frame.\n'
                'All three compressed resources fit their original slots; all geometry, palettes, current font and other translated assets are unchanged.\n'
                'Offline native decompression/header checks and eighty actual selector/byte-field-query cases pass. Live icon/palette/readability checks remain pending.\n',
            'readme_movie_text':previous['readme_movie_text'],
            'proof_scope':'Fresh three PRS streams/texture headers, three PVM lookups and eighty native order-selector cases. Scalar texture/font/palette and exact protected data checks. Constructor endpoint and memcmp are bounded fixtures; actual archive loading, EFFECT runtime palette/selection, sprite submission and GPU/live appearance remain unverified. Historical reports retain actual tested identities.',
            'pending':list(dict.fromkeys(['Live five-order icon/initial discoverability and EFFECT palette/selection review',
                       'Independent corrected order wording review',
                       *[p for p in previous['pending'] if p!='Four single-kanji status icons and attack calligraphy readings/context']])), 'release':False}
    return disc,cue,inherited,targets,changes,names,historical,report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    planned=plan()
    print('PASS:',len(planned[4]),'sector substitutions;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; twelve payloads, ten unaffected payloads and 22 historical identities.',flush=True)
    print(json.dumps(planned[-1]['archive_changed_locations'],indent=2),flush=True)
    if not args.write:
        print('DRY RUN: no game build written')
        return
    write_plan(planned,VERSION,PRIOR,{n:planned[3][n] for n in ('WIN00.AFS','EFFECT.AFS')})
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','before-after.png'):
        (out/('order-icons-'+name)).write_bytes((OUT/name).read_bytes())
    path=out/'font4x-patch.json'
    manifest=json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
                    status='All fifteen order-icon cells corrected; full translation and live review incomplete')
    # This is the current binary manifest; historical proof files retain their
    # actual tested archive identities unchanged.
    manifest['files']['WIN00.AFS']['target_sha256']=planned[-1]['files']['WIN00.AFS']['sha256']
    manifest['order_icons']={'build':VERSION,'icon_cells':15,'native_proof':'order-icons-native-test.json',
                             'normal_font_changed':False,'live_validation':'pending'}
    path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
