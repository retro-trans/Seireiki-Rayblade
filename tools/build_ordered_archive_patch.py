"""Repair all compact-sector archive layouts in 0.1.38. Default dry run.

The native SDK uses first-sector plus cumulative rounded member sizes. Keep
every member payload/ID exact; rebuild only six incompatible AFS layouts.
"""
import argparse
import json
import struct

from build_bitmap_font import ROOT, digest
from repack_win_archive import repack
from afs_layout import compact_positions

PRIOR = '0.1.37'
VERSION = '0.1.38'
OUT = ROOT / 'work/output/ordered-archives-draft-01'
EXPECTED = {'WMAP.AFS', 'STAFF.AFS', 'ADV00.AFS', 'ALBUM.AFS', 'EFFECT.AFS', 'D_SYSTEM.AFS'}


def compose():
    previous = json.loads((ROOT / 'work/output' / PRIOR / 'english-disc-report.json').read_text('utf-8'))
    targets, archives, unchanged = {}, {}, []
    for name, identity in previous['files'].items():
        if not name.endswith('.AFS'):
            continue
        source = (ROOT / 'work/output' / PRIOR / name).read_bytes()
        assert digest(source) == identity['sha256'] and len(source) == identity['size']
        old = compact_positions(source)
        mismatches = [r for r in old if r['declared_offset'] != r['native_offset']]
        if not mismatches:
            unchanged.append(name)
            continue
        assert name in EXPECTED
        first = old[0]['declared_offset']
        required_end = sum(r['sectors'] * 2048 for r in old) + first
        # Free only the sector-aligned prefix space actually needed. No ISO
        # extent growth or text/image recompression is required.
        deficit = max(0, required_end - len(source))
        new_first = first - ((deficit + 2047) // 2048) * 2048
        assert new_first >= 8 + len(old) * 8 + 8
        target, packing = repack(source, first_offset=new_first)
        new = compact_positions(target)
        assert all(r['declared_offset'] == r['native_offset'] for r in new)
        assert all(a['bytes'] == b['bytes'] for a, b in zip(old, new))
        targets[name] = target
        archives[name] = {'source_archive_sha256': digest(source), 'target_archive_sha256': digest(target),
                          'archive_bytes': len(target), 'members': len(old),
                          'source_mismatched_members': len(mismatches),
                          'first_source_mismatch': mismatches[0],
                          'first_data_offset_before': first, 'first_data_offset_after': new_first,
                          'changed_member_payloads': 0, 'packing': packing}
    assert set(targets) == EXPECTED and set(unchanged) == {'WIN00.AFS', 'D_SCE.AFS'}
    report = {'source_build': PRIOR, 'version': VERSION,
              'kind': 'Native compact-sector archive layout repair; payloads/translation/font unchanged',
              'archives': archives, 'unchanged_compatible_archives': unchanged,
              'repacked_archives': len(targets),
              'unchanged_member_payloads': sum(r['members'] for r in archives.values()),
              'normal_text_font_changed': False, 'story_library_draft_credit': 0,
              'limits': ['Native SDK offset/length calculation and source failure reproduction checked separately',
                         'Actual Flycast new-game, later asset loads and full-game testing remain required']}
    return targets, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    targets, report = compose()
    for name, row in report['archives'].items():
        print(name, row['source_mismatched_members'], 'bad native offsets repaired;',
              row['members'], 'exact payloads; first sector', row['first_data_offset_after'] // 2048,
              '; spare bytes', row['packing']['spare_bytes'])
    if not args.write:
        print('DRY RUN: six archive candidates planned; no files written.')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in targets.items():
        (OUT / name).write_bytes(raw)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print('Wrote six ordered AFS candidates, with every member payload unchanged.')


if __name__ == '__main__':
    main()
