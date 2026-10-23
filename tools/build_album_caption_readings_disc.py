"""Package the last two album caption drafts as local 0.1.37. Dry first."""
import argparse
import json

from build_album_caption_readings_patch import OUT,PRIOR,compose
from build_bitmap_font import ROOT
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch

VERSION='0.1.37'


def plan():
    planned=plan_archive_patch(
        version=VERSION,prior_version=PRIOR,archive_name='ALBUM.AFS',draft_dir=OUT,candidate=compose,
        slug='album-caption-readings',proof_count_key='new_caption_count',proof_count=2,replace_existing=True,
        prior_proof=('disc-icon-native-test.json','disc_icon_proof_sha256','0GDTEX.PVR'),
        description='Local final two album caption drafts; independent meaning/live and full-game review incomplete',
        pending=['Independent newly resolved album caption readings and wording review',
                 'Live updated album caption appearance, selection/unlock/navigation review'],
        proof_scope='Two fresh native PRS streams and texture headers; independent scalar caption masks, pixel addressing, exact geometry and protected archive/photo/other-caption data. The 203 combined source-caption drafts include 201 preceding captions preserved exactly. Manual Japanese glyph readings remain editorial evidence, not byte-test proof. Actual archive loading, album selection/unlock/navigation and GPU/live appearance remain unverified.',
        readme='Adds English drafts for the two previously unread album captions: Naked Touya and Alforina\'s Feeble Gaze.\n'
               'Readings are manual source-glyph decisions supported by original-game/reference shapes; independent reading/meaning review remains pending.\n'
               'All 203 nonblank source captions now have English drafts. The 201 preceding English captions, 21 Coming Soon cells and all 224 photo regions stay exact.\n'
               'Only two caption cells in two native 256x256 atlases change; both resources fit existing slots, with all geometry and other 242 members unchanged.\n'
               'Native decoder/header, scalar font/pixel and archive checks pass. Actual album loading, unlock/selection/navigation and live appearance remain unverified.\n'
               'The thirteen other game payloads, current normal font, prior translated album pictures, disc icon and selected-logo subtitle movies remain exact 0.1.36.\n')
    assert len(planned[3])==14 and len(planned[6])==25
    planned[-1]['pending']=[p for p in planned[-1]['pending']
                            if p!='Two unresolved album caption readings and remaining game translation/review']
    return planned


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    planned=plan()
    print('PASS:',len(planned[4]),'album-caption substitutions;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; fourteen payloads and 25 historical proof identities.',flush=True)
    if not args.write:
        print('DRY RUN: no game build written')
        return
    write_plan(planned,VERSION,PRIOR,{'ALBUM.AFS':planned[3]['ALBUM.AFS']})
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','before-after.png'):
        (out/('album-caption-readings-'+name)).write_bytes((OUT/name).read_bytes())
    manifest_path=out/'font4x-patch.json'
    manifest=json.loads(manifest_path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
                    status='All 203 album caption drafts inserted; independent meaning/live and full-game translation/review incomplete')
    manifest['album_caption_readings']={'build':VERSION,'archive_sha256':planned[-1]['files']['ALBUM.AFS']['sha256'],
                                       'new_caption_count':2,'combined_caption_count':203,'unresolved_caption_ids':[],
                                       'normal_font_changed':False,'live_validation':'pending'}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
