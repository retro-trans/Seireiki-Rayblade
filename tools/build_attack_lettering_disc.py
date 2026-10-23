"""Package coordinated English attack artwork as local 0.1.33. Dry first."""
import argparse
import json

from build_attack_lettering_patch import OUT,compose
from build_bitmap_font import ROOT
from build_movie_test_disc import write_plan
from package_archive_test_disc import plan_archive_patch

VERSION,PRIOR='0.1.33','0.1.32'


def plan():
    planned=plan_archive_patch(
        version=VERSION,prior_version=PRIOR,archive_name='EFFECT.AFS',draft_dir=OUT,candidate=compose,
        slug='attack-lettering',proof_count_key='artwork_frame_count',proof_count=8,replace_existing=True,
        prior_proof=('effect-ui-native-test.json','effect_ui_proof_sha256','EFFECT.AFS'),
        description='Local English BREAK attack artwork test; remaining translation, artwork/meaning/live and full-game review incomplete',
        pending=['Whole-attack English BREAK artwork, actual sprite transforms and live palette/timing review',
                 'Independent attack wording and reauthored glow/trail fidelity review'],
        proof_scope='Fresh native PRS, PVM walker and PAL4 header execution; scalar font/texture/palette and exact geometry/archive preservation. Sixteen native source-variant branch/load/join cases rerun with bounded async I/O fixtures. Whole attack, actual resource I/O, sprite transforms, runtime palettes/timing and GPU/live appearance remain untested; historical reports retain actual source identities.',
        readme='Adds BREAK to eight Hongshenguang attack graphic frames in four native effect resources, including reversed and motion variants.\n'
               'Uses the current inferred Latin font at one common whole-word scale. Original 512x512 textures, palettes and all sprite geometry/animation programs remain unchanged.\n'
               'Red glow and yellow trails are newly authored approximations of the original effect treatment; independent artwork/meaning and live motion review are pending.\n'
               'All four packed resources fit their original slots. The nine preceding English effect/UI labels and other 456 EFFECT members remain exact.\n'
               'Native decoder/PVM/header checks and sixteen controlled source variant-selection cases pass; actual file I/O, sprite transforms, palette/timing and live attack appearance are unverified.\n'
               'The eleven other game payloads, normal font, existing translations and selected-logo subtitle movies remain exact 0.1.32.\n')
    assert len(planned[3])==12 and len(planned[6])==21
    return planned


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    planned=plan()
    print('PASS:',len(planned[4]),'attack-art sectors;',planned[-1]['total_changed_sector_locations_from_original'],
          'locations from original; twelve payloads, eleven unaffected payloads and 21 historical identities exact.',flush=True)
    if not args.write:
        print('DRY RUN: no game build written')
        return
    write_plan(planned,VERSION,PRIOR,additional_components={'EFFECT.AFS':planned[3]['EFFECT.AFS']})
    out=ROOT/'work/output'/VERSION
    for name in ['component-report.json','native-test.json']+[f'before-after-{i:03d}.png' for i in (142,143,455,456)]:
        (out/('attack-lettering-'+name)).write_bytes((OUT/name).read_bytes())
    path=out/'font4x-patch.json'
    manifest=json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,
                    status='Eight English BREAK attack-art frames integrated; existing font/text/UI/movies unchanged, live/full-game review pending')
    manifest['attack_lettering']={'build':VERSION,'archive_sha256':planned[-1]['files']['EFFECT.AFS']['sha256'],
                                  'artwork_frame_count':8,'native_proof':'attack-lettering-native-test.json',
                                  'normal_font_changed':False,'live_validation':'pending',
                                  'artwork_fidelity':'Reauthored glow/trail approximation; original brush/motion field not reconstructed exactly'}
    path.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
