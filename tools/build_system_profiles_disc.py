"""Package the additional English system profiles as local 0.1.35. Dry first."""
import argparse
import json

from build_bitmap_font import ROOT
from build_movie_test_disc import write_plan
from build_system_profiles_patch import OUT,PRIOR,compose
from package_archive_test_disc import plan_archive_patch

VERSION='0.1.35'


def plan():
    result=plan_archive_patch(
        version=VERSION,prior_version=PRIOR,archive_name='D_SYSTEM.AFS',draft_dir=OUT,candidate=compose,
        slug='system-profiles',proof_count_key='profile_count',proof_count=2,
        prior_proof=('order-icons-native-test.json','order_icons_proof_sha256',None),
        description='Local additional system-profile translation test; remaining text/images and full-game review incomplete',
        pending=['Actual D_SYSTEM archive use/loading, legacy selection/viewer layout and loader-capacity validation',
                 'Independent additional-profile meaning, source lore differences and La=Dis category review'],
        proof_scope='Raw relative-table/header/alias and independent English encoding checks; 46 actual native text-filter cases and 135 parser cases through both current constructed viewers. These are controlled text-compatibility fixtures, not D_SYSTEM runtime loading/selection or legacy-viewer proof. No PRS-compression claim applies to these raw members. Historical reports retain tested identities.',
        readme='Adds English drafts for sixteen rows in two additional shared profiles found in D_SYSTEM.AFS, preserving all 384 aliases and original profile metadata.\n'
               'This source differs from the current library: year 5959, Zeifon-to-Rayblade pilot history, weapons/main controls and two-pilot activation are retained.\n'
               'The 128 existing English numbered Unknown labels retain their text/leading spaces, reencoded for the current Latin font.\n'
               'The larger profile table relocates into verified zero archive prefix space; original archive size and unrelated bytes remain intact.\n'
               'Forty-six native filter cases and 135 current-viewer parser cases pass. Actual D_SYSTEM loading/use, loader capacity and legacy viewer remain unverified.\n'
               'All twelve preceding game payloads, including current font, story/current library, icons, artwork and selected-logo subtitle movies, are unchanged.\n')
    assert len(result[3])==13 and len(result[6])==23
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    planned=plan()
    print('PASS:',len(planned[4]),'system-profile sector substitutions;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; thirteen payloads and 23 historical proof identities.',flush=True)
    if not args.write:
        print('DRY RUN: no game build written')
        return
    write_plan(planned,VERSION,PRIOR,{'D_SYSTEM.AFS':planned[3]['D_SYSTEM.AFS']})
    out=ROOT/'work/output'/VERSION
    for name in ('component-report.json','native-test.json','profile-preview.png'):
        (out/('system-profiles-'+name)).write_bytes((OUT/name).read_bytes())
    path=out/'font4x-patch.json'
    manifest=json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
                    status='Additional system profiles drafted and inserted; actual archive use/loading and full-game translation/review incomplete')
    manifest['system_profiles']={'build':VERSION,'archive_sha256':planned[-1]['files']['D_SYSTEM.AFS']['sha256'],
                                 'profile_count':2,'source_rows_drafted':16,'existing_English_labels':128,
                                 'native_proof':'system-profiles-native-test.json','normal_font_changed':False,
                                 'runtime_use_and_live_validation':'unverified'}
    path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
