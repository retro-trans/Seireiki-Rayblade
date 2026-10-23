"""Map ANIME marker coincidences to bounded counted resources; default dry run.

The schema follows native 8c0241e0. Syntactic 74/02 matches are candidate
references only. This does not establish program reachability or text absence.
"""
import argparse
from collections import Counter, defaultdict
import json
import re
import struct

from audit_animation_payloads import original
from build_bitmap_font import ROOT, digest
from rayblade_codec import decompress

OUT = ROOT / 'work/ui/asset-audit/ANIME/resource-regions-01'


def resource(data, start):
    """Strict length-delimited parse, independently checked against native code."""
    if start < 0 or start % 2 or start + 2 > len(data):
        raise ValueError('unaligned or missing resource header')
    vectors = struct.unpack_from('<H', data, start)[0]
    pos = start + 2 + 6 * vectors
    if pos > len(data):
        raise ValueError('vector span outside source')
    records = []
    while True:
        if pos + 4 > len(data):
            raise ValueError('missing record/terminator')
        a, b = struct.unpack_from('<HH', data, pos)
        if a == b == 0:
            return {'start': start, 'end': pos + 4, 'vectors': vectors,
                    'records': records, 'sha256': digest(data[start:pos + 4])}
        if len(records) >= 512:
            raise ValueError('record count exceeds native global capacity')
        end = pos + 16 + 2 * (a + b)
        if end > len(data):
            raise ValueError('record span outside source')
        records.append({'start': pos, 'a': a, 'b': b,
                        'header_word_4': struct.unpack_from('<H', data, pos + 4)[0],
                        'stream_1': pos + 16, 'stream_2': pos + 16 + 2 * a,
                        'end': end})
        pos = end


def locate(row, offset):
    if offset < row['start'] + 2:
        return 'vector_count'
    if offset < row['start'] + 2 + 6 * row['vectors']:
        return 'counted_vector_bytes'
    for rec in row['records']:
        if rec['start'] <= offset < rec['end']:
            if offset < rec['stream_1']:
                return 'record_header'
            return 'record_word_stream_1' if offset < rec['stream_2'] else 'record_word_stream_2'
    return 'terminator'


def inspect():
    archive, packed = original()
    frozen_path = ROOT / 'work/ui/asset-audit/ANIME/text-markers-01/marker-index.json'
    frozen = json.loads(frozen_path.read_text('utf-8'))
    assert frozen['source_archive_sha256'] == digest(archive)
    plains = []
    for n, raw in enumerate(packed):
        data, used = decompress(raw)
        assert used == len(raw)
        assert digest(data) == frozen['member_identities'][n]['decoded_sha256']
        plains.append(data)
    standalone, inline, candidates = [], [], []
    by_member = defaultdict(list)
    for n, data in enumerate(plains):
        first = int.from_bytes(data[:4], 'little')
        if first in (4, 8, 12):
            roots = [i + struct.unpack_from('<I', data, i)[0] for i in range(0, first, 4)]
            assert roots[0] == first and roots == sorted(set(roots))
            for i, start in enumerate(roots):
                row = resource(data, start)
                assert row['end'] == (roots[i + 1] if i + 1 < len(roots) else len(data) - 1)
                row.update(member=n, root_field=4 * i, provenance='relative_root_table')
                standalone.append(row)
                by_member[n].append(row)
            assert data[-1:] == b'\0'
            continue
        refs = []
        for match in re.finditer(b'\x74\x02', data):
            at = match.start()
            if at + 7 > len(data):
                continue
            displacement = struct.unpack_from('<i', data, at + 2)[0]
            if displacement < 16:
                continue
            target = (at + 2 + displacement + 1) & ~1
            try:
                row = resource(data, target)
            except ValueError:
                continue
            # Exclude empty accidental fits as entry-point discovery evidence.
            if row['vectors'] and row['records']:
                refs.append({'command_offset': at, 'target': target,
                             'slot': data[at + 6] & 15, 'mode': data[at + 6] >> 4})
        candidates.extend(dict(member=n, **ref) for ref in refs)
        if not refs:
            continue
        first_ref = min(refs, key=lambda r: r['target'])
        pos = first_ref['target']
        while pos < len(data) - 1:
            try:
                row = resource(data, pos)
            except ValueError:
                break
            row.update(member=n, provenance='candidate_reference_then_contiguous_parse',
                       first_candidate=first_ref)
            inline.append(row)
            by_member[n].append(row)
            pos = row['end']
    assert len(standalone) == 127 and len({r['member'] for r in standalone}) == 66
    rooted_hashes = defaultdict(list)
    for row in standalone:
        rooted_hashes[row['sha256']].append({'member': row['member'], 'start': row['start']})
    for row in inline:
        row['identical_standalone_resources'] = rooted_hashes.get(row['sha256'], [])
    markers = []
    for old in frozen['matches']:
        n, at = old['member'], old['offset']
        matches = [r for r in by_member[n] if r['start'] <= at and at + 2 <= r['end']]
        assert len(matches) == 1, (n, at, len(matches))
        row = matches[0]
        markers.append({'member': n, 'offset': at,
                        'known_scenario_style': old['matches_one_of_five_known_scenario_styles'],
                        'resource_start': row['start'], 'resource_sha256': row['sha256'],
                        'first_byte_field': locate(row, at), 'second_byte_field': locate(row, at + 1),
                        'provenance': row['provenance'],
                        'identical_standalone_resources': rooted_hashes.get(row['sha256'], [])})
    assert len(markers) == 544 and sum(r['known_scenario_style'] for r in markers) == 22
    all_rows = standalone + inline
    report = {'source_archive_sha256': digest(archive), 'marker_index_sha256': digest(frozen_path.read_bytes()),
              'members_checked': len(plains), 'decoded_bytes': sum(map(len, plains)),
              'member_identities': frozen['member_identities'],
              'native_schema_function': '8c0241e0..8c024316',
              'standalone_members': 66, 'standalone_resources': len(standalone),
              'inline_chain_members': len({r['member'] for r in inline}),
              'inline_chain_resources': len(inline), 'syntactic_reference_candidates': candidates,
              'resources': all_rows, 'markers': markers,
              'marker_field_histogram': dict(Counter(r['first_byte_field'] for r in markers)),
              'markers_with_independently_rooted_resource': sum(bool(r['identical_standalone_resources']) for r in markers),
              'limits': ['Candidate byte matches and contiguous parsing do not establish actual VM reachability',
                         'Schema compatibility alone is not native execution or a complete semantic classification',
                         'No claim that every ANIME program, word stream, encoding or image is text-free',
                         'No game/translation bytes changed; no new translation credit']}
    return report, plains


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    report, _ = inspect()
    print('PASS: 544 markers mapped;', report['markers_with_independently_rooted_resource'],
          'in independently rooted resources;', report['standalone_resources'],
          'standalone resources;', report['inline_chain_resources'], 'inline chain resources.', flush=True)
    print('Fields:', report['marker_field_histogram'])
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'resource-index.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
        print('Wrote bounded structural evidence; native checks remain separate.')
    else:
        print('DRY RUN: no files written.')


if __name__ == '__main__':
    main()
