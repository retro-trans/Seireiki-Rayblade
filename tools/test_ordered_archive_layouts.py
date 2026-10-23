"""Reproduce captured bad load and execute real SDK lookups for all members.

No Windows/app control. The sole external fixture copies 40 file-info bytes;
native validation, directory traversal, cumulative offsets and sizes execute.
"""
import argparse
import json
import struct

from build_bitmap_font import ROOT, digest
from build_ordered_archive_patch import OUT, PRIOR, compose, compact_positions
from check_attack_variant_selection import AttackCPU, BASE, STOP, run

DIRECTORY = 0x8c500000
OUTPUT = 0x8c600000
ROOTS = 0x8c42fac0
IDS = {'D_SCE.AFS': 2, 'D_SYSTEM.AFS': 3, 'EFFECT.AFS': 8, 'ADV00.AFS': 20,
       'STAFF.AFS': 23, 'ALBUM.AFS': 24, 'WMAP.AFS': 26, 'WIN00.AFS': 28}


class LookupCPU(AttackCPU):
    checking = False

    def write(self, address, value, count):
        if self.checking:
            assert (OUTPUT <= address and address + count <= OUTPUT + 0x100) or (
                0x8c700f00 <= address and address + count <= 0x8c701008), ('Unexpected native write', hex(address))
        super().write(address, value, count)

    def execute(self, pc, delay=False):
        if pc == 0x8c094db8:
            assert self.reg[6] == 40
            src, off = self.area(self.reg[5], 40)
            raw = bytes(src[off:off + 40])
            for n, value in enumerate(raw):
                self.write(self.reg[4] + n, value, 1)
            self.reg[0] = self.reg[4]
            self.copies += 1
            return self.pr
        return super().execute(pc, delay)


def directory_bytes(name, archive):
    rows = compact_positions(archive)
    data = bytearray(62 + 2 * len(rows))
    struct.pack_into('<I', data, 8, len(rows))
    struct.pack_into('<H', data, 12, len(rows))
    data[16:16 + len(name)] = name.encode('ascii')
    struct.pack_into('<I', data, 56, 0x1234)
    struct.pack_into('<H', data, 60, rows[0]['declared_offset'] // 2048)
    for n, row in enumerate(rows):
        struct.pack_into('<H', data, 62 + 2 * n, row['sectors'])
    return bytes(data)


def lookup(exe, name, directory, member):
    c = LookupCPU(exe, b'', 0, 0)
    c.regions = [(BASE, bytearray(exe)), (ROOTS, bytearray(128)),
                 (DIRECTORY, bytearray(directory)), (OUTPUT, bytearray(b'\xa5' * 0x100)),
                 (0x8c700000, bytearray(b'\xa5' * 0x2000))]
    c.reg[15] = 0x8c701000
    c.write(ROOTS + 4 * IDS[name], DIRECTORY, 4)
    c.reg[4:8] = [IDS[name], member, OUTPUT + 16, OUTPUT + 64]
    c.write(c.reg[15], OUTPUT + 72, 4)
    c.write(c.reg[15] + 4, OUTPUT + 80, 4)
    saved = list(c.reg[8:])
    c.visited, c.loads, c.polls, c.copies = set(), [], 0, 0
    c.checking = True
    steps = run(c, 0x8c09e190, STOP, limit=10000)
    assert c.reg[0] == 0 and c.reg[8:] == saved and c.copies == 1
    assert 0x8c09e060 in c.visited and not c.loads and not c.polls
    expected = bytearray(b'\xa5' * 0x100)
    expected[16:56] = directory[16:56]
    expected[64:68] = struct.pack('<I', 0x1234)
    offset, sectors = c.read(OUTPUT + 72, 4), c.read(OUTPUT + 80, 4)
    expected[72:76] = struct.pack('<I', offset)
    expected[80:84] = struct.pack('<I', sectors)
    assert c.regions[3][1] == expected
    assert bytes(c.regions[2][1]) == directory and bytes(c.regions[0][1]) == exe
    stack = c.regions[-1][1]
    assert stack[:0xf00] == b'\xa5' * 0xf00 and stack[0x1008:] == b'\xa5' * (0x2000 - 0x1008)
    return offset * 2048, sectors, steps


def failure(exe, source):
    path = ROOT / 'work/source/runtime/0.1.37-new-game-corruption-01.ram'
    ram = path.read_bytes()
    assert len(ram) == 0x1000000 and digest(ram) == '334decbb1c232762e1c31b631975a0aaf7dd235128e3139778a9d0714aa8a49d'
    assert ram[0x9e060:0x9e0a0] == exe[0x8e060:0x8e0a0]
    assert ram[0x9e190:0x9e264] == exe[0x8e190:0x8e264]
    node = struct.unpack_from('<I', ram, (ROOTS & 0xffffff) + 20 * 4)[0] & 0xffffff
    directory = directory_bytes('ADV00.AFS', source)
    assert ram[node + 60:node + len(directory)] == directory[60:]
    wrong, sectors, steps = lookup(exe, 'ADV00.AFS', directory, 380)
    correct, size = struct.unpack_from('<II', source, 8 + 380 * 8)
    assert (wrong, correct, sectors, size) == (22067200, 22063104, 1, 80)
    # The descriptor records member+1; its allocation address is captured.
    resource = struct.unpack_from('<12I', ram, 0x16ed5c + 58 * 48)
    assert resource[3] == (381 << 16 | 20)
    allocation = resource[2]
    addend = allocation + 8
    assert addend == 0x8c82f2e8
    recovered = bytearray(ram[(allocation & 0xffffff):(allocation & 0xffffff) + size])
    struct.pack_into('<I', recovered, 8, (struct.unpack_from('<I', recovered, 8)[0] - addend) & 0xffffffff)
    assert recovered == source[wrong:wrong + size]
    assert source[correct:correct + 4] == b'NJTL' and source[wrong:wrong + 4] != b'NJTL'
    shadow = bytearray(ram)
    for at in range(0x10008, 0x31a80, 12):
        struct.pack_into('<I', shadow, at, (struct.unpack_from('<I', shadow, at)[0] - addend) & 0xffffffff)
    assert shadow[0x18800:0x18908] == exe[0x8800:0x8908]
    assert shadow[0x18c00:0x18cfc] == exe[0x8c00:0x8cfc]
    assert struct.unpack_from('<I', shadow, 0x183f0)[0] == 0x8cd55700
    assert struct.unpack_from('<I', shadow, 0x204b4)[0] == 0x20000
    return {'captured_game_RAM_sha256': digest(ram), 'archive': 'ADV00.AFS', 'member': 380,
            'declared_correct_offset': correct, 'actual_native_offset': wrong,
            'wrong_read_bytes': size, 'wrong_payload_matches_captured_RAM_after_pointer_unrelocation': True,
            'corruption_addend': hex(addend), 'corruption_stride_bytes': 12,
            'shadow_recovery_of_scenario_hooks_heap_pointer_and_allocation_literal': 'pass',
            'native_lookup_instructions': steps,
            'scope': 'Read-only captured evidence and analysis shadow; no process/RAM mutation'}


def check():
    targets, report = compose()
    for name, raw in targets.items():
        assert (OUT / name).read_bytes() == raw
    assert json.loads((OUT / 'component-report.json').read_text('utf-8')) == report
    exe = (ROOT / 'work/output' / PRIOR / '1ST_READ.BIN').read_bytes()
    assert struct.unpack_from('<I', exe, 0x8e27c)[0] == ROOTS
    reproduced = failure(exe, (ROOT / 'work/output' / PRIOR / 'ADV00.AFS').read_bytes())
    names = list(targets) + report['unchanged_compatible_archives']
    results = {}
    for name in names:
        data = targets.get(name) or (ROOT / 'work/output' / PRIOR / name).read_bytes()
        rows = compact_positions(data)
        directory = directory_bytes(name, data)
        steps = 0
        for row in rows:
            offset, count, n = lookup(exe, name, directory, row['member'])
            assert offset == row['declared_offset'] == row['native_offset']
            assert count == row['sectors'] and offset + count * 2048 <= len(data)
            steps += n
        results[name] = {'members': len(rows), 'native_lookup_instructions': steps,
                         'all_native_offsets_and_sector_lengths_match_physical_layout': True}
        print('PASS native SDK:', name, len(rows), 'members;', steps, 'instructions', flush=True)
    assert sum(r['members'] for r in results.values()) == 2063
    # Verify every native read covers the same payload as the prior build.
    for name, data in targets.items():
        old = (ROOT / 'work/output' / PRIOR / name).read_bytes()
        for row in compact_positions(data):
            start, size = struct.unpack_from('<II', old, 8 + 8 * row['member'])
            assert data[row['native_offset']:row['native_offset'] + size] == old[start:start + size]
    return {'source_build': PRIOR, 'executable_sha256': digest(exe),
            'archives': {name: digest(data) for name, data in targets.items()},
            'repacked_archives': 6, 'unchanged_member_payloads': 1525,
            'native_lookup_cases': 2063, 'native_instructions': sum(r['native_lookup_instructions'] for r in results.values()) + reproduced['native_lookup_instructions'],
            'archive_checks': results, 'captured_failure_reproduction': reproduced,
            'native_guard_and_ABI': 'pass', 'archive_bytes_outside_declared_edits': 'exact',
            'declared_edits': 'Six complete archive layouts rebuilt; all 1525 member payload bytes exact, file sizes unchanged; two other archives remain exact',
            'fixtures': ['Controlled compact SDK directories; ADV00 first-sector/length list agrees byte-for-byte with captured runtime table',
                         'Only the external 40-byte file-info copy endpoint uses a bounded fixture; native validation/traversal/offset arithmetic execute',
                         'D_SYSTEM slot 3 is a generic directory fixture; actual D_SYSTEM registration/use remains unproved'],
            'limits': ['No live app control or restarted New Game test executed by this tool',
                       'No new PRS/raster/meaning proof: every member payload and executable is unchanged',
                       'Actual New Game, save/load and later asset navigation remain user testing gates']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    if not args.verify:
        print('DRY RUN: reproduce captured member-380 wrong read and test all 2063 native SDK archive lookups; no files written.')
        return
    report = check()
    print('PASS: captured wrong payload reproduced exactly; 2063 native lookups, six repacked archives, 1525 exact payloads;', report['native_instructions'], 'instructions.')
    if args.write_report:
        (OUT / 'native-test.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
