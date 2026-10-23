"""Record the verified local text-filter build, preserving prior proof scope."""
import argparse
import json

from build_text_filter_patch import ROOT, VERSION, PRIOR, compose, digest
from build_text_filter_disc import plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    out = ROOT / 'work/output' / VERSION
    files, _, component = compose()
    assert files['1ST_READ.BIN'] == (out / '1ST_READ.BIN').read_bytes()
    proof = json.loads((out / 'text-filter-native-test.json').read_text('utf-8'))
    disc = json.loads((out / 'english-disc-report.json').read_text('utf-8'))
    assert proof['executable_sha256'] == component['executable_sha256']
    assert proof['native_instructions'] == 24837
    assert disc['validation']['reextracted_files'] == 'all 5 exact'
    assert disc['validation']['unrelated_track_bytes'] == 'all unchanged'
    _, _, _, _, _, current_plan = plan()
    assert current_plan['files'] == disc['files']
    disc['total_changed_sector_locations_from_original'] = current_plan['total_changed_sector_locations_from_original']
    doc = component | {
        'status': 'Native text-specific bilinear filtering integrated and locally packaged; live appearance pending',
        'source_trace': {
            'font_resource_registration': '8c076e96 registers 8c16f92c (resource 63) with the dynamic texture/sprite tables',
            'text_object_submission': '8c078bc0 passes resource 63 to the native sprite object constructor',
            'native_filter_setter': '8c0a78d0: mode 0 -> context +84=0; mode 1 -> +84=2',
            'command_encoder': '8c0d0340 selects from [0,2,1,3] and stores filtering in mode2 bits 14:13',
            'sprite_state_copy': '8c0c7d34 retains command filter bits',
            'texture_bind': '8c0c8a9e changes size/address fields, retaining filter bits',
        },
        'native_validation': {'selection_encoder_cases': proof['selection_encoder_cases'],
                              'real_caller_comparisons': proof['caller_cases'],
                              'state_transitions': proof['state_transitions'],
                              'native_instructions': proof['native_instructions']},
        'proof': f'work/output/{VERSION}/text-filter-native-test.json',
        'disc': f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        'packaging': disc['validation'],
        'historical_evidence': f'13 unchanged {PRIOR} native reports retain their original executable hashes and actual coverage; previous full-packager gates rerun against that build',
        'limits': proof['limits'],
        'bitmap_detail': 'Source bitmap still has finite contour detail; no vector reconstruction or preblur added',
        'story_library_draft_credit': 0,
    }
    print('Record 0.1.22: fresh native filter evidence, exact two-sector packaging, historical proof boundaries and live appearance pending.')
    if not args.write:
        print('DRY RUN: no documentation changed')
        return
    def save(path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    save(out / 'english-disc-report.json', disc)
    save(ROOT / 'docs/font-filtering.json', doc)
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    status.update(version=VERSION, stage='Text-specific native bilinear filter integrated over existing English drafts; held passages, independent review, other images/movies and full-game validation incomplete')
    status['latest_text_filter_build'] = doc
    status['test_disc'].update(version=VERSION, source_build=PRIOR,
                               path=doc['disc'], kind=disc['kind'],
                               changed_sectors=disc['total_changed_sector_locations_from_original'],
                               validation=disc['validation'],
                               text_filter_delta_sectors=2,
                               filter_packaging=disc['validation'])
    status['test_disc']['names']['new_size'] = disc['files']['D_NAMES.BIN']['size']
    save(status_path, status)
    for name in ('font-antialiasing.json', 'ui-layout.json', 'text-reinsertion.json'):
        p = ROOT / 'docs' / name
        data = json.loads(p.read_text('utf-8'))
        data['latest_text_filter_build'] = doc
        save(p, data)
    mpath = out / 'font4x-patch.json'
    m = json.loads(mpath.read_text('utf-8'))
    m['status'] = 'Native text filter and local packaging pass; full-game translation/review and live appearance incomplete'
    m['text_filter']['packaging'] = disc['validation']
    save(mpath, m)


if __name__ == '__main__':
    main()
