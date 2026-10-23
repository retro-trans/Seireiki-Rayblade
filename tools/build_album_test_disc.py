"""Package local 0.1.28 with 201 English album captions. Dry run first."""
import argparse

from build_album_caption_patch import OUT, compose
from build_bitmap_font import ROOT
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch

VERSION, PRIOR = '0.1.28', '0.1.27'


def plan():
    planned = plan_archive_patch(
        version=VERSION, prior_version=PRIOR, archive_name='ALBUM.AFS', draft_dir=OUT,
        candidate=compose, slug='album-captions', proof_count_key='caption_count', proof_count=201,
        prior_proof=('story-images-native-test.json', 'story_images_proof_sha256', 'ADV00.AFS'),
        description='Local English album gallery captions; two caption readings and full translation/review incomplete',
        pending=['Two unclear album captions and independent caption meaning/context review',
                 'Album full-size pictured note and Japanese New Year artwork plus matching thumbnail images',
                 'Native relocated album loading, unlock/selection/navigation, caption fit and appearance'],
        readme='Adds 201 English album gallery captions in the original 64x24 caption areas.\n'
               'Two unclear captions remain Japanese; all 224 thumbnail photographs and 21 Coming Soon cells stay exact.\n'
               'The full-size album note and Japanese New Year card, plus their thumbnail artwork, still need translation.\n'
               'Six caption atlases move into verified archive padding. All original gallery sprite geometry is unchanged.\n'
               'Native decoder and structure checks pass; actual album loading/unlocks/navigation/appearance are untested.\n'
               'The normal text font and the ten preceding game payloads are unchanged from 0.1.27.\n')
    # The three formerly unsupported ADV01 mipmaps now have bounded previews;
    # preserve historical reports while keeping the new build's todo accurate.
    planned[-1]['pending'] = list(dict.fromkeys(
        'Remaining image-format decoding, full-resolution inspection and image-text coverage'
        if p == 'Three ADV01 mipmap textures and other uncovered image assets' else p
        for p in planned[-1]['pending']))
    return planned


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    planned = plan()
    print(f'PASS: {len(planned[4])} new album sectors; eleven payloads; ten inherited payloads and {len(planned[6])} historical proof identities exact.', flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned, VERSION, PRIOR, additional_components={'ALBUM.AFS': planned[3]['ALBUM.AFS']})
    out = ROOT / 'work/output' / VERSION
    for name in ('component-report.json', 'native-test.json', 'gallery-before-after.png'):
        (out / ('album-captions-' + name)).write_bytes((OUT / name).read_bytes())
    for page in range(7):
        name = f'English-captions-{page:02d}.png'
        (out / name).write_bytes((OUT / name).read_bytes())


if __name__ == '__main__':
    main()
