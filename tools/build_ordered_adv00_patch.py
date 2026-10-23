"""Prepare an ordered ADV00 layout after the observed new-game corruption.

Default dry run. All 777 member payloads remain exact 0.1.37, including the
English letter. Restores ascending offsets and original first-data position.
Live loading must still establish whether this fixes the reported failure.
"""
import argparse
import json
import struct

from build_bitmap_font import ROOT, digest
from repack_win_archive import repack

PRIOR = '0.1.37'
OUT = ROOT / 'work/output/ordered-adv00-draft-01'


def compose():
    source = (ROOT / 'work/output' / PRIOR / 'ADV00.AFS').read_bytes()
    assert digest(source) == '08c682f98b2a5d483cbcda4c3ddf1b42ee33fe69121c32ccac26c3e60f879fc7'
    assert struct.unpack_from('<I', source, 4)[0] == 777
    assert struct.unpack_from('<I', source, 8)[0] == 0x80000
    assert struct.unpack_from('<I', source, 8 + 379 * 8)[0] == 0x60000
    target, packing = repack(source, first_offset=0x80000)
    component = {'source_build': PRIOR, 'kind': 'Ordered archive loading correction candidate; live reproduction pending',
                 'source_archive_sha256': digest(source), 'target_archive_sha256': digest(target),
                 'archive_bytes': len(target), 'archive_members': 777,
                 'changed_member_payloads': 0, 'unchanged_member_payloads': 777,
                 'first_data_offset': 0x80000, 'packing': packing,
                 'reason': 'The English letter member 379 was placed before member zero and outside index order, repeating an unsafe relocation pattern previously isolated for WIN00',
                 'limits': ['All archive payloads and IDs are preserved; native archive I/O and live new-game compatibility require testing',
                            'Reported RAM corruption is evidence of failure, not by itself proof of the responsible loader path'],
                 'normal_text_font_changed': False, 'story_library_draft_credit': 0}
    return target, component


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    target, report = compose()
    print('Ordered ADV00: 777 exact member payloads; first offset 0x80000;',
          report['packing']['spare_bytes'], 'spare bytes; unchanged archive size.')
    print('Letter:', report['packing']['members'][379])
    print('Following metadata:', report['packing']['members'][380])
    if not args.write:
        print('DRY RUN: no candidate files written; live correction not yet established.')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'ADV00.AFS').write_bytes(target)
    (OUT / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    print('Wrote ordered loading candidate; game build not yet packaged.')


if __name__ == '__main__':
    main()
