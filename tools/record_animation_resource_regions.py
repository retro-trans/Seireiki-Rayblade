"""Record checked ANIME resource evidence without changing a game build."""
import argparse
import json

from analyze_animation_resource_regions import OUT
from build_bitmap_font import ROOT, digest


NOTE = '''## Working translation — native ANIME resource boundaries

- Mapped all 544 raw 8A06 coincidences, including all 22 known-style matches, to bounded counted-resource word streams: 541 in stream 2 and three in stream 1. The schema follows the original reader at 8c0241e0: a count of six-byte vector entries, then sixteen-byte record headers and two counted word streams, ending with two zero counts. Opcode 74/subcommand 2 registers this data; its positive displacement is relative to command+2 and rounded up to an even address. It is not a callback registration.
- Validated 66 standalone relative-root tables containing 127 resources, plus 1,302 contiguous resource spans in candidate inline chains. All 206 marker occurrences with independently rooted counterparts retain exact resource hashes. In particular, the six previously uncovered member-218 matches sit in a resource byte-identical to standalone member 582. Syntactic command matches and adjacent resource parsing do not prove whole-program reachability.
- Executed 294 original native resource registrations, covering all marker-bearing regions and every standalone resource, with independent complete work-buffer expectations, source/stack guards, alignment, slot/mode, prior count and ABI checks. Four actual source command fixtures also execute native dispatch and seven-byte command continuation. All 1,251,900 integer SH-4 instructions pass; no external-call stubs are reached. These are controlled interpreter fixtures, not hardware or live rendering tests.
- This establishes the counted-data context of these byte coincidences in the checked reader. Subsequent interpretation of the word streams, remaining control flow, other encodings/images and complete text absence remain open. No new dialogue or translation credit, game bytes or build changed; latest playable build remains 0.1.37. Source dump and prior proofs retained; no release.

'''


def prepare():
    index_path = OUT / 'resource-index.json'
    proof_path = OUT / 'native-test.json'
    index = json.loads(index_path.read_text('utf-8'))
    proof = json.loads(proof_path.read_text('utf-8'))
    status_path = ROOT / 'docs/translation-status.json'
    status = json.loads(status_path.read_text('utf-8'))
    assert status['version'] == '0.1.37'
    assert index['source_archive_sha256'] == proof['source_ANIME_archive_sha256']
    assert proof['executable_sha256'] == digest((ROOT / 'work/output/0.1.37/1ST_READ.BIN').read_bytes())
    assert len(index['markers']) == 544 and proof['direct_registration_cases'] == 294
    assert len(proof['dispatch_cases']) == 4 and proof['native_instructions'] == 1251900
    tested = {(r['member'], r['resource_start'], r['resource_sha256']) for r in proof['cases']}
    assert all((r['member'], r['resource_start'], r['resource_sha256']) in tested for r in index['markers'])
    summary = {'index': str(index_path.relative_to(ROOT)).replace('\\', '/'),
               'index_sha256': digest(index_path.read_bytes()),
               'native_proof': str(proof_path.relative_to(ROOT)).replace('\\', '/'),
               'native_proof_sha256': digest(proof_path.read_bytes()),
               'raw_byte_matches_in_counted_word_streams': 544,
               'known_scenario_style_matches_in_counted_word_streams': 22,
               'marker_field_histogram': index['marker_field_histogram'],
               'markers_with_independently_rooted_resources': 206,
               'standalone_members': 66, 'standalone_resources': 127,
               'candidate_inline_resources': 1302,
               'native_registration_cases': 294, 'native_dispatch_cases': 4,
               'native_instructions': 1251900,
               'status': 'All inventoried marker coincidences have checked counted-word-stream context; not new dialogue commands in this reader',
               'next_evidence': 'Trace later word-stream consumers and remaining VM control/data boundaries; no complete text-absence claim',
               'limits': proof['limits'], 'new_translation_credit': 0}
    doc_path = ROOT / 'docs/animation-payloads.json'
    doc = json.loads(doc_path.read_text('utf-8'))
    doc['status'] = '642 decoded identities; all 544 raw dialogue-marker coincidences mapped to native counted word streams. Full VM/consumer semantics and possible other text remain open'
    doc['current_game_build'] = '0.1.37'
    doc['resource_boundaries'] = summary
    doc['marker_audit']['status'] = 'Historical bounded probe; all 544 matches now have counted-word-stream context in resource_boundaries'
    doc['marker_audit']['next_evidence'] = summary['next_evidence']
    doc['limits'] = [s for s in doc['limits'] if not s.startswith('No native animation VM execution')]
    native_limit = 'Controlled native resource registration and four source dispatch cases pass; whole VM reachability, later word-stream consumers, rendering and live proof remain open'
    if native_limit not in doc['limits']:
        doc['limits'].append(native_limit)
    audit_path = ROOT / 'docs/non-movie-image-text-audit.json'
    audit = json.loads(audit_path.read_text('utf-8'))
    audit['ANIME_payload_discovery'] = doc
    status['ANIME_payload_discovery'] = doc
    status['non_movie_image_text_audit']['ANIME_payload_discovery'] = doc
    status['checks']['ANIME_counted_resource_registration'] = summary
    return [(doc_path, doc), (audit_path, audit), (status_path, status)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    updates = prepare()
    print('PASS: source/proof identities and native coverage of all 544 markers; latest game build 0.1.37.')
    if not args.write:
        print('DRY RUN: three document updates and change-log entry; no files written.')
        return
    for path, content in updates:
        path.write_text(json.dumps(content, indent=2) + '\n', 'utf-8')
    changelog = ROOT / 'CHANGELOG.md'
    old = changelog.read_text('utf-8')
    if NOTE.splitlines()[0] not in old:
        changelog.write_text(old.replace('# Change log\n\n', '# Change log\n\n' + NOTE, 1), 'utf-8')
    print('Recorded source-only evidence; no game/build/translation bytes changed.')


if __name__ == '__main__':
    main()
