"""Package local build 0.1.32 with nine effect UI labels. Dry run first."""
import argparse
import json

from build_bitmap_font import ROOT
from build_effect_ui_patch import OUT, compose
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch

VERSION,PRIOR='0.1.32','0.1.31'


def plan():
    planned=plan_archive_patch(
        version=VERSION,prior_version=PRIOR,archive_name='EFFECT.AFS',draft_dir=OUT,candidate=compose,
        slug='effect-ui',proof_count_key='label_count',proof_count=9,
        prior_proof=('outline-font-native-test.json','outline_font_proof_sha256','WIN00.AFS'),
        description='Local English effect/UI label test; remaining translation, meaning and full-game review incomplete',
        pending=['Live native effect loading/palette selection and translated battle result/ability label appearance',
                 'Four single-kanji status icons and attack calligraphy readings/context',
                 'Remaining image formats/text discovery and independent translation/artwork review'],
        proof_scope='Fresh native PRS and PAL4 texture-info execution, independent index/color/source-mask/geometry/archive checks. Original palettes and raw binding parameters retained. Native file I/O, palette selection, sprite submission and GPU/live behavior remain untested; historical reports retain their actual tested source identities.',
        readme='Adds nine English image labels: Prana, Critical, Evade, Guard, Plasma Coating, Plasma Barrier, Ballistic Barrier, Special Field and Barrier.\n'
               'All text fits the original screen sizes/centers. Ballistic Barrier uses unused space in the same 256x256 atlas.\n'
               'Every palette and raw texture parameter, 116 other sprites and 459 other archive members remain exact.\n'
               'Four status icons and attack calligraphy remain untranslated pending context/readings.\n'
               'Native PRS/PAL4 header and independent preservation checks pass; live palette selection/loading/appearance are unverified.\n'
               'All eleven existing game payloads, including the 0.1.31 inferred Latin font and selected-logo subtitle movies, remain exact.\n')
    assert len(planned[3])==12 and len(planned[6])==20
    return planned


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    planned=plan()
    print('PASS:',len(planned[4]),'effect/UI sectors;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; twelve payloads, eleven inherited payloads and 20 historical identities exact.',flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned,VERSION,PRIOR,additional_components={'EFFECT.AFS':planned[3]['EFFECT.AFS']})
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','labels-before-after.png','atlas-bank-04-4x.png'):
        (out/('effect-ui-'+name)).write_bytes((OUT/name).read_bytes())
    path=out/'font4x-patch.json'
    manifest=json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
                    status='Nine native effect/UI image label drafts integrated; original font/text/movies unchanged, live review pending')
    manifest['effect_ui']={'build':VERSION,'archive_sha256':planned[-1]['files']['EFFECT.AFS']['sha256'],
                           'native_proof':'effect-ui-native-test.json','label_count':9,
                           'live_validation':'pending','normal_font_changed':False}
    path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
