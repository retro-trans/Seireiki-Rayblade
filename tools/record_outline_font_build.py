"""Record packaged inferred outlines and bounded native proof. Dry first."""
import argparse
import copy
import json

from build_bitmap_font import ROOT, digest
from build_outline_font_disc import VERSION, PRIOR
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\', '/')


def record():
    out = ROOT/'work/output'/VERSION
    report = read(out/'english-disc-report.json')
    prior = read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    assert report['version'] == VERSION and report['source_build'] == PRIOR
    assert report['new_changed_sectors'] == 25 and report['total_changed_sector_locations_from_original'] == 28390
    assert report['validation']['reextracted_files'] == 'all 11 exact'
    assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    assert report['validation']['track_bytes_compared'] == 1188856032
    disc_path = out/'disc'/f'Rayblade English Test {VERSION}.gdi'
    disc = Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries = {r['path']:r for r in disc.inventory()}
    for name,info in report['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'],row['size'])
        assert len(raw) == info['size'] and digest(raw) == info['sha256']
        if name != 'WIN00.AFS':
            assert info == prior['files'][name]
    assert len(report['historical_native_evidence']) == 19
    for item in report['historical_native_evidence']:
        raw = (out/item['file']).read_bytes()
        assert digest(raw) == item['sha256'] and json.loads(raw)['executable_sha256'] == item['executable_sha256']
    raw = (out/'outline-font-native-test.json').read_bytes()
    proof = json.loads(raw)
    component = read(out/'outline-font-component-report.json')
    assert proof == report['outline_font_native_proof'] and component == report['outline_font_component']
    assert digest(raw) == report['outline_font_proof_sha256']
    assert proof['archive_sha256'] == report['files']['WIN00.AFS']['sha256']
    assert proof['glyph_cases'] == 397 and proof['SH4_instructions'] == 13075994
    assert proof['native_guard_and_ABI'] == 'pass' and proof['archive_bytes_outside_declared_edits'] == 'exact'
    manifest = read(out/'font4x-patch.json')
    assert manifest['files']['WIN00.AFS']['target_sha256'] == proof['archive_sha256']
    assert manifest['antialias_font']['version'] == VERSION
    assert manifest['antialias_font']['font_sha256'] == proof['font_sha256']
    assert manifest['historical_antialias_font']['font_sha256'] == proof['source_font_sha256']
    scenario = read(out/'text/scenario-component-report.json')
    assert scenario['word_wrap']['font_sha256'] == proof['font_sha256']
    assert scenario['word_wrap'] == manifest['scenario']['word_wrap']
    previews = [out/'outline-font-comparison.png',out/'outline-font-all-glyphs.png']
    assert all(p.is_file() for p in previews)
    ratios = [r['candidate_coverage_sum_at_source_scale']/r['source_coverage_sum']
              for r in component['glyphs'] if r['source_coverage_sum']]
    doc = {'version':VERSION,'source_build':PRIOR,
           'status':'Inferred-outline Latin font integrated in local build; native raster checks pass, live appearance/fidelity and Skies comparison pending',
           'disc':rel(disc_path),'font_source':'incoming/fonts/user-bitmap/dialogue-atlas.png',
           'source_atlas_sha256':component['source_atlas_sha256'],'source_font_sha256':proof['source_font_sha256'],
           'font_sha256':proof['font_sha256'],'archive_sha256':proof['archive_sha256'],
           'method':component['method'],'glyphs_reconstructed':95,'changed_font_bytes':6076,
           'topology_changes':[],'observed_source_normalized_coverage_range':[min(ratios),max(ratios)],
           'previews':[{'path':rel(p),'sha256':digest(p.read_bytes())} for p in previews],
           'visual_review':'Matched-size comparison and all 95 inferred glyphs reviewed; r/O/diagonal edges look cleaner than duplicated samples. Offline appearance only.',
           'native_proof':proof,'validation':report['validation'],
           'unchanged':['Executable and its allocator/filter code; native texture limit <=1024 per dimension',
                        'All advances and baseline origins; existing text and word-break bytes',
                        'Small bank, five protected marks and all non-font WIN00 bytes',
                        'All ten other game payloads, including translated album pictures/captions and both movies'],
           'metadata':'Current font identity updated; earlier source-coverage/renderer reports retain their actual tested font/build identity as historical evidence',
           'test_corrections':['Serialized mask bounds normalized to JSON lists before native execution.',
                               'Small raw bytes 0/255 alias protected symbols; fallback test inputs corrected to genuinely invalid indices 4/31, checked separately, then the full 397-case suite passed.'],
           'new_changed_sectors':25,'changed_sector_locations_from_original':28390,
           'remaining':['Independent inferred-shape fidelity review; original vector outlines are unavailable',
                        'Live text/GPU blending, pixel alignment, UI/dialogue/library/battle contexts and matched Skies comparison',
                        'Remaining translation/image discovery, held passages, independent meaning and full-game validation'],
           'font_texture_dimension_limit':1024,'emulator_texture_replacement':False,'release':False,
           'story_library_draft_credit':0}
    renderer_path = ROOT/'docs/font-renderer.json'
    renderer = read(renderer_path)
    renderer.update(current_build=VERSION,status=doc['status'],latest_outline_build=doc)
    if 'historical_bitmap_font' not in renderer:
        renderer['historical_bitmap_font'] = copy.deepcopy(renderer['font'])
    renderer['font'] = {'source_family':'Inferred contours of user-supplied dialogue bitmap',
                        'type':'Inferred geometry; original vectors unavailable',
                        'source_filename':'dialogue-atlas.png','source_sha256':component['source_atlas_sha256'],
                        'source_dimensions':[384,168],'font_sha256':proof['font_sha256'],'format_version':4,
                        'pixel_data':'Unchanged two-bit Latin masks / native ARGB4444 surfaces',
                        'glyphs':'95 medium ASCII contours reconstructed; small bank and five prior protected symbols unchanged',
                        'spacing':'Existing advance tables and baseline origin exact; no individual glyph stretching',
                        'sampling':component['method'],'live_appearance':'pending'}
    smoothing_path = ROOT/'docs/font-smoothing-investigation.json'
    smoothing = read(smoothing_path)
    smoothing.update(status=doc['status'],latest_outline_build=doc,
                     initial_game_files_changed_scope='Original inspection/blur experiment made no game changes; the separately recorded outline build does.')
    smoothing['remaining'] = doc['remaining'][:2]
    aa_path = ROOT/'docs/font-antialiasing.json'
    aa = read(aa_path)
    aa.update(current_build=VERSION,latest_outline_build=doc,
              status='Historical original four-level coverage integration retained; current inferred outline build has fresh raster proof and pending live appearance')
    status_path = ROOT/'docs/translation-status.json'
    status = read(status_path)
    if status.get('latest_font_build',{}).get('version') != VERSION:
        status['preceding_font_build'] = status.get('latest_font_build')
    status.update(version=VERSION,stage='Inferred Latin outlines integrated over unchanged 0.1.30 translations/artwork/movies; live font/fidelity review, two caption readings, remaining images/held text/meaning and full-game validation incomplete',
                  latest_font_build=doc,latest_font_outline_build=doc)
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(disc_path),kind=report['kind'],
                               changed_sectors=28390,validation=report['validation'],font_delta_sectors=25,
                               font_sha256=proof['font_sha256'],WIN00_sha256=proof['archive_sha256'],
                               font_component_origin_build=VERSION,pending=report['pending'])
    status['test_disc'].pop('album_picture_delta_sectors',None)
    status['test_disc'].pop('text_filter_delta_sectors',None)
    return [(ROOT/'docs/font-outline.json',doc),(renderer_path,renderer),(smoothing_path,smoothing),
            (aa_path,aa),(status_path,status)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args = ap.parse_args()
    edits = record()
    print('PASS: 0.1.31, 95 inferred glyphs, 397 native cases, eleven exact payloads, 19 historical identities; 25 font-sector substitutions. Live appearance remains pending.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path,data in edits:
        path.write_text(json.dumps(data,indent=2)+'\n','utf-8')


if __name__ == '__main__':
    main()
