"""Package the original disc-icon artwork plus English subtitle as 0.1.36."""
import argparse
import json

from build_bitmap_font import ROOT
from build_disc_icon_subtitle import OUT,PRIOR,compose
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch

VERSION='0.1.36'


def plan():
    planned=plan_archive_patch(
        version=VERSION,prior_version=PRIOR,archive_name='0GDTEX.PVR',draft_dir=OUT,candidate=compose,
        slug='disc-icon',proof_count_key='subtitle_count',proof_count=1,
        prior_proof=('system-profiles-native-test.json','system_profiles_proof_sha256','D_SYSTEM.AFS'),
        description='Local English disc-icon identification subtitle; remaining translation and live/full-game review incomplete',
        pending=['Dreamcast/Flycast disc-icon subtitle appearance and small-caption readability',
                 'Independent disc-icon subtitle layout/artwork review'],
        proof_scope='Independent scalar ARGB1555 pixels, source-font word assembly, compositing and exact alpha/bright-artwork/header preservation. Native game SDK texture-header helper executes; this is not BIOS disc rendering. Full-sector and 32-byte file-tail substitution fixtures verify preserved padding and valid EDC/ECC. All previous native proof identities remain historical under their actual tested files.',
        readme='Adds SEIREIKI RAYBLADE below the original Japanese disc-selection logo, using the current Latin contours at one common scale.\n'
               'Original circular transparency, bright mech/logo pixels, 256x256 format and file length remain exact. The words are spaced around the central blade tip.\n'
               'All pixels outside the small caption strokes stay unchanged. Source font is unchanged; no texture replacement is used.\n'
               'Offline scalar/font/header and sector-padding checks pass. Actual Dreamcast/Flycast icon rendering and small-caption readability remain unverified.\n'
               'All thirteen preceding game payloads, normal font, story/current/additional profiles, icons, artwork and selected-logo subtitle movies remain exact 0.1.35.\n')
    assert len(planned[3])==14 and len(planned[6])==24
    return planned


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    planned=plan()
    print('PASS:',len(planned[4]),'disc-icon sector substitutions;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; fourteen payloads and 24 historical native proof identities.',flush=True)
    if not args.write:
        print('DRY RUN: no game build written')
        return
    write_plan(planned,VERSION,PRIOR,{'0GDTEX.PVR':planned[3]['0GDTEX.PVR']})
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','before-after.png'):
        (out/('disc-icon-'+name)).write_bytes((OUT/name).read_bytes())
    manifest_path=out/'font4x-patch.json'
    manifest=json.loads(manifest_path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
                    status='English identification subtitle added to original disc icon; translation and live/full-game review incomplete')
    manifest['disc_icon']={'build':VERSION,'file':'0GDTEX.PVR','sha256':planned[-1]['files']['0GDTEX.PVR']['sha256'],
                           'subtitle':'SEIREIKI RAYBLADE','normal_font_changed':False,'live_validation':'pending'}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
