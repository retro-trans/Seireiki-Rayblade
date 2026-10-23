"""Execute native counted-resource registration against independent bounds.

Controlled entries, RAM and stack only; no I/O stubs or graphics submission.
Default dry run; --verify executes, --write-report saves successful evidence.
"""
import argparse
import json
import struct

from analyze_animation_resource_regions import inspect, OUT, resource
from build_bitmap_font import ROOT, digest
from check_attack_variant_selection import AttackCPU, run, advance, BASE, SOURCE, STOP

WORK = 0x8c400040


def fresh(exe, data):
    c = AttackCPU(exe, b'', 0, 0)
    c.regions = [(BASE, bytearray(exe)), (0x8c160000, bytearray(0x20000)),
                 (0x8c1d0000, bytearray(0x40000)),
                 (0x8c400000, bytearray(b'\xa5' * 0x3300)),
                 (SOURCE - 64, bytearray(b'\xa5' * 64 + data + b'\xa5' * 64)),
                 (0x8c700000, bytearray(b'\xa5' * 0x2000))]
    c.reg[15] = 0x8c701000
    c.write(c.reg[15] + 4, STOP, 4)
    c.write(0x8c169c68, WORK, 4)
    c.write(WORK + 0x30f8, 3, 2)
    c.write(0x8c1dbf61, 0xa1, 1)
    c.visited = set()
    c.loads = []
    c.polls = 0
    return c


def expected_work(c, row, slot, mode):
    buf = bytearray(c.regions[3][1])
    def put(offset, value, count):
        at = WORK - 0x8c400000 + offset
        buf[at:at + count] = value.to_bytes(count, 'little')
    put(0x30b8 + slot * 4, SOURCE + row['start'], 4)
    put(0x30d8 + slot * 2, 3, 2)
    for n, rec in enumerate(row['records'], 3):
        put(0x1cb8 + n * 4, SOURCE + rec['stream_1'], 4)
        put(0x24b8 + n * 4, SOURCE + rec['stream_2'], 4)
        put(0x2cb8 + n * 2, rec['header_word_4'], 2)
    put(0x30e8 + slot * 2, len(row['records']), 2)
    put(0x30f8, 3 + len(row['records']), 2)
    put(0x1cab + slot, mode, 1)
    return buf


def checked(c, data, row, slot, mode, saved, expected):
    assert c.reg[8:] == saved, 'callee-preserved registers/stack'
    assert c.regions[3][1] == expected, 'complete work structure and guards'
    assert c.regions[4][1] == b'\xa5' * 64 + data + b'\xa5' * 64
    assert c.read(0x8c1dbf61, 1) == 0xb1
    assert not c.loads and not c.polls
    stack = c.regions[-1][1]
    assert stack[:0xf00] == b'\xa5' * 0xf00
    assert stack[0x1008:] == b'\xa5' * (0x2000 - 0x1008)


def check():
    index, plains = inspect()
    exe = (ROOT / 'work/output/0.1.37/1ST_READ.BIN').read_bytes()
    assert struct.unpack_from('<I', exe, 0x8c024250 - BASE)[0] == 0x8c169c68
    assert struct.unpack_from('<HHH', exe, 0x8c024248 - BASE) == (0x30b8, 0x30d8, 0x30f8)
    assert struct.unpack_from('<HHHHHHH', exe, 0x8c024318 - BASE) == (
        0x2cb8, 0x1cb8, 0x24b8, 512, 0x30e8, 0x30f8, 0x1cab)
    selected = {(r['member'], r['start']) for r in index['resources']
                if r['provenance'] == 'relative_root_table'}
    selected.update((m['member'], m['resource_start']) for m in index['markers'])
    cases = []
    for serial, (member, start) in enumerate(sorted(selected)):
        data = plains[member]
        row = resource(data, start)
        slot, mode = (0, 3, 7)[serial % 3], serial % 16
        c = fresh(exe, data)
        saved = list(c.reg[8:])
        expected = expected_work(c, row, slot, mode)
        # Both exact and one-byte-earlier pointers align to the same resource.
        c.reg[4:7] = [SOURCE + start - (serial % 2), slot, mode]
        steps = run(c, 0x8c0241e0, STOP, limit=100000)
        checked(c, data, row, slot, mode, saved, expected)
        assert all(0x8c0241e0 <= p <= 0x8c024316 for p in c.visited)
        cases.append({'member': member, 'resource_start': start, 'resource_sha256': row['sha256'],
                      'vectors': row['vectors'], 'records': len(row['records']),
                      'slot': slot, 'mode': mode, 'unaligned_input': bool(serial % 2),
                      'native_instructions': steps})
    dispatch_cases = []
    for member, command in [(218, 470), (245, 490), (245, 566), (401, 508)]:
        data = plains[member]
        assert data[command:command + 2] == b'\x74\x02'
        displacement = struct.unpack_from('<i', data, command + 2)[0]
        start = (command + 2 + displacement + 1) & ~1
        row = resource(data, start)
        slot, mode = data[command + 6] & 15, data[command + 6] >> 4
        assert slot < 8
        c = fresh(exe, data)
        c.write(0x8c1dbe24, SOURCE + command + 1, 4)
        c.write(0x8c1dbe70, 0x74, 4)
        c.write(0x8c1dbe74, 0, 4)
        saved = list(c.reg[8:])
        expected = expected_work(c, row, slot, mode)
        steps = run(c, 0x8c03f48a, 0x8c03f498, limit=100000)
        assert c.reg[0] == 0x6006 and 0x8c0241e0 in c.visited
        checked(c, data, row, slot, mode, saved, expected)
        steps += advance(c, c.reg[0])
        assert c.read(0x8c1dbe24, 4) == SOURCE + command + 8
        assert c.read(0x8c1dbe70, 4) == data[command + 7]
        assert c.reg[8:] == saved
        dispatch_cases.append({'member': member, 'command_offset': command,
                               'resource_start': start, 'slot': slot, 'mode': mode,
                               'next_opcode_offset': command + 7, 'native_instructions': steps})
    return {'source_build': '0.1.37', 'executable_sha256': digest(exe),
            'source_ANIME_archive_sha256': index['source_archive_sha256'],
            'direct_registration_cases': len(cases), 'dispatch_cases': dispatch_cases,
            'native_instructions': sum(r['native_instructions'] for r in cases + dispatch_cases),
            'cases': cases, 'complete_work_and_source_guards_ABI': 'pass',
            'fixtures': ['Controlled RAM work pointer and initial record count 3',
                         'Controlled entry into native resource registration and four real source commands',
                         'Strict integer SH-4 interpreter; no external call stubs reached'],
            'limits': ['Not whole-program reachability or native hardware execution',
                       'Registration stores length-delimited pointers; subsequent word-stream interpretation remains open',
                       'No file loading, graphics submission, rendering, live timing or text-absence proof',
                       'No game/translation bytes changed or new translation credit']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    if not args.verify:
        print('DRY RUN: verify counted-resource registration and four source dispatch cases; no files written.')
        return
    report = check()
    print('PASS:', report['direct_registration_cases'], 'resource cases; four native dispatch/advance cases;',
          report['native_instructions'], 'instructions; full work/source guards and ABI.')
    if args.write_report:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'native-test.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
