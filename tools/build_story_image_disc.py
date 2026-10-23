"""Package local 0.1.27 with English note and placeholder images. Dry first."""
import argparse

from build_bitmap_font import ROOT
from build_movie_test_disc import write_plan
from build_story_image_patch import OUT, compose
from package_archive_test_disc import plan_archive_patch
from prepare_story_letter import OUT as LETTER_OUT

VERSION, PRIOR = '0.1.27', '0.1.26'


def plan():
    return plan_archive_patch(
        version=VERSION, prior_version=PRIOR, archive_name='ADV00.AFS', draft_dir=OUT,
        candidate=compose, slug='story-images', proof_count_key='image_resource_count', proof_count=9,
        prior_proof=('credits-native-test.json', 'credits_proof_sha256', 'STAFF.AFS'),
        description='Local English Kasumi note and eight development-placeholder images; full translation/review incomplete',
        pending=['Live relocated letter-archive loading, image selection and appearance',
                 'Paper-estimate artwork review and development-placeholder reachability',
                 'Three ADV01 mipmap textures and other uncovered image assets'],
        readme='Adds Kasumi\'s pictured note using all ten existing English story rows, including the postscript/signature.\n'
               'Only brightness bytes change in the letter; original YUV color bytes remain exact. Blank paper is locally estimated.\n'
               'Eight development-placeholder image labels are translated; their actual reachability is unverified.\n'
               'The letter texture moves into verified archive padding; live loading/appearance remain untested.\n'
               'All nine preceding game payloads, including normal text/font, credits, map and movies, are unchanged.\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print(f'PASS: {len(planned[4])} new image-archive sectors; ten payloads; nine inherited payloads and {len(planned[6])} historical proof identities exact.', flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned, VERSION, PRIOR, additional_components={'ADV00.AFS': planned[3]['ADV00.AFS']})
    out = ROOT / 'work/output' / VERSION
    for name in ('component-report.json', 'native-test.json', 'story-images-preview.png'):
        (out / (name if name.startswith('story-images-') else 'story-images-' + name)).write_bytes((OUT / name).read_bytes())
    (out / 'letter-before-after.png').write_bytes((LETTER_OUT / 'before-after.png').read_bytes())


if __name__ == '__main__':
    main()
