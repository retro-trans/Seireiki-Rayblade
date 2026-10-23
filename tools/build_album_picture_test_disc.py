"""Package local 0.1.30 with translated album picture text. Dry run first."""
import argparse

from build_album_picture_patch import OUT, compose
from build_bitmap_font import ROOT
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch

VERSION, PRIOR = '0.1.30', '0.1.29'


def plan():
    planned = plan_archive_patch(
        version=VERSION, prior_version=PRIOR, archive_name='ALBUM.AFS', draft_dir=OUT,
        candidate=compose, slug='album-pictures', proof_count_key='image_resource_count', proof_count=5,
        prior_proof=None, replace_existing=True,
        description='Local English album greeting/note and matching thumbnails; full translation/review incomplete',
        pending=['Native relocated album note loading, unlock/selection/navigation and live artwork appearance',
                 'Independent meaning/artwork review and estimated paper/thumbnail cleanup review',
                 'Two unresolved album caption readings and remaining game translation/review'],
        readme='Adds the English New Year greeting and Kasumi note to their full album pictures and three matching thumbnails.\n'
               'The greeting retains the original heart and portrait; the note retains every original YUV color byte.\n'
               'Paper cleanup is locally estimated. Native decoder/structure checks pass; live album loading/artwork are untested.\n'
               'All 224 gallery caption areas remain exact, including the 201 English captions and two original reading holds.\n'
               'The note moves into verified zero archive padding; original gallery layout and other 221 photographs remain exact.\n'
               'All ten other game payloads, including both selected-logo subtitle movies and normal text font, stay exact 0.1.29.\n')
    # These two artwork tasks are now represented by the fresh component;
    # retain unresolved readings, review and live checks without stale todos.
    stale = {'Album full-size pictured note and Japanese New Year artwork plus matching thumbnail images',
             'Two unclear album captions and independent caption meaning/context review'}
    planned[-1]['pending'] = [p for p in planned[-1]['pending'] if p not in stale]
    return planned


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args = ap.parse_args()
    planned = plan()
    print('PASS:',len(planned[4]),'new sectors;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; eleven payloads, ten unaffected payloads and 18 historical identities exact.',flush=True)
    if not args.write:
        print('DRY RUN: no build written')
        return
    write_plan(planned,VERSION,PRIOR,additional_components={'ALBUM.AFS':planned[3]['ALBUM.AFS']})
    out = ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','picture-015-before-after.png',
                 'picture-081-before-after.png','thumbnail-before-after.png'):
        (out/('album-pictures-'+name)).write_bytes((OUT/name).read_bytes())


if __name__ == '__main__':
    main()
