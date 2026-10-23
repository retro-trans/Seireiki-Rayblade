"""Package native inferred Latin outlines in 0.1.31. Dry run first."""
import argparse
import copy
import json

from build_bitmap_font import ROOT, digest
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch
from trace_bitmap_font import OUT, compose

VERSION, PRIOR = '0.1.31','0.1.30'


def plan():
    return plan_archive_patch(
        version=VERSION,prior_version=PRIOR,archive_name='WIN00.AFS',draft_dir=OUT,candidate=compose,
        slug='outline-font',proof_count_key='glyph_cases',proof_count=397,replace_existing=True,
        prior_proof=('album-pictures-native-test.json','album_pictures_proof_sha256','ALBUM.AFS'),
        description='Local inferred-outline Latin font candidate; live font/translation/full-game review incomplete',
        pending=['Live inferred-font appearance, blending/pixel alignment and matched Skies comparison',
                 'Independent outline shape fidelity and all-context font review'],
        proof_scope='Fresh SH-4 raster/cursor checks from unpacked inferred masks; source topology/coverage/bounds and exact outside font edits. No new executable, PRS, allocation, GPU or live appearance proof; historical reports retain their tested identities.',
        readme='Reconstructs smoother Latin contours from the supplied bitmap and rasterizes them into the native font member.\n'
               'This is inferred geometry, not the original vector font. Native format still stores four alpha levels.\n'
               'All advances/baseline origins, the small bank, protected marks and existing word breaks stay unchanged.\n'
               'The executable and all other ten game payloads remain exact 0.1.30; every text texture remains capped at 1024 per dimension.\n'
               'No emulator texture replacement. Native pixel/cursor checks pass; live quality and Skies comparison are unverified.\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args = ap.parse_args()
    planned = plan()
    print('PASS:',len(planned[4]),'font sectors;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; ten unaffected payloads and 19 historical identities exact.',flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned,VERSION,PRIOR,additional_components={'WIN00.AFS':planned[3]['WIN00.AFS']})
    out = ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','comparison.png','all-glyphs.png'):
        (out/('outline-font-'+name)).write_bytes((OUT/name).read_bytes())
    component = json.loads((OUT/'component-report.json').read_text('utf-8'))
    manifest_path = out/'font4x-patch.json'
    manifest = json.loads(manifest_path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,status='Inferred Latin outline candidate integrated; native raster checks pass, live appearance pending')
    manifest['files']['WIN00.AFS']['target_sha256'] = component['target_archive_sha256']
    manifest['font_outline'] = {'build':VERSION,'source_build':PRIOR,'font_sha256':component['target_font_sha256'],
                               'method':component['method'],'native_proof':'outline-font-native-test.json',
                               'live_appearance':'pending','historical_source_coverage_reports':'Retain original tested font/build identities; not fresh proofs of the new geometry'}
    manifest['vector_font'].update(type='Inferred contours from the supplied bitmap; original vectors unavailable',
                                   sampling=component['method'],
                                   coverage='Four native levels 0,85,187,255 quantize inferred contour coverage; no exact source-sample preservation claim')
    manifest['historical_antialias_font'] = copy.deepcopy(manifest['antialias_font'])
    manifest['antialias_font'] = {'version':VERSION,'source_sha256':component['source_atlas_sha256'],
                                  'font_sha256':component['target_font_sha256'],
                                  'texture_format':'Unchanged native ARGB4444 surfaces and two-bit glyph coverage',
                                  'advances':'Byte-exact 0.1.30',
                                  'native_validation':'397 fresh raster/cursor cases from unpacked inferred masks',
                                  'raster_proof':'outline-font-native-test.json','live_validation':'pending'}
    path = out/'text/scenario-component-report.json'
    scenario = json.loads(path.read_text('utf-8'))
    wrap = scenario['word_wrap']
    wrap.setdefault('previous_measurement_font_sha256',wrap['font_sha256'])
    wrap.update(font_sha256=component['target_font_sha256'],
                current_font_validation='Advances byte-exact 0.1.30; native cursor cases pass; existing boundaries unchanged, no full command rerun claimed')
    scenario['presentation_font_update_build'] = VERSION
    path.write_text(json.dumps(scenario,indent=2)+'\n','utf-8')
    manifest['scenario']['word_wrap'] = copy.deepcopy(wrap)
    manifest['native_proof_reuse'] = {'source_build':PRIOR,'changed_scope':'Medium ASCII font masks only; executable, advances and other payloads exact',
                                    'fresh_proof':'outline-font-native-test.json','live_validation':'pending'}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__ == '__main__':
    main()
