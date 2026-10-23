"""Execute text-filter selection and the real SDK command encoder. Dry first."""
import argparse
import json
import struct

from build_text_filter_patch import ROOT, VERSION, PRIOR, BASE, ENTRY, POINTER, SETTER, compose, digest
from test_font_patch import CPU

STOP = 0xdead0000
CTX = 0x8c500000
OBJ = 0x8c510000


class FilterCPU(CPU):
    def execute(self, pc, delay=False):
        word = self.read(pc, 2)
        if word & 0xff00 == 0xc700:  # MOVA
            self.reg[0] = ((pc + 4) & ~3) + (word & 255) * 4
            return pc + 2
        if word & 0xf0ff == 0x0023:  # BRAF
            assert not delay
            target = (pc + 4 + self.reg[word >> 8 & 15]) & 0xffffffff
            self.execute(pc + 2, True)
            return target
        if pc == SETTER:
            self.inputs.append(self.reg[4])
        # The state-list finalizer is outside the mode2 encoder. Record entry,
        # leave all fields unchanged and return; no GPU submission is claimed.
        if pc == 0x8c0d0b00:
            self.finalizations += 1
            return self.pr
        return super().execute(pc, delay)


def fresh(exe, resource, mode, seed):
    c = FilterCPU(exe, b'', 0, 0)
    c.regions = [(BASE, bytearray(exe)), (CTX, bytearray(512)),
                 (OBJ, bytearray(128)), (0x8c170000, bytearray(0x10000)),
                 (0x8c410000, bytearray(0x10000)), (0x8c460000, bytearray(0x3000)),
                 (0x8c700000, bytearray([0xa5]) * 4096)]
    c.write(0x8c17fba0, OBJ if resource is not None else 0, 4)
    c.write(OBJ + 38, resource or 0, 2)
    c.write(0x8c419a38, CTX, 4)
    for off, val in ((0x90, 0x80840028), (0x94, 0xe0000000),
                     (0x98, seed), (0x9c, 0x14000000)):
        c.write(CTX + off, val, 4)
    c.reg[4] = mode
    c.reg[15] = 0x8c700c00
    c.pr = STOP
    c.inputs = []
    c.finalizations = 0
    return c


def run(c, pc, stop=STOP):
    c.pc = pc
    for n in range(10000):
        if c.pc == stop:
            return n
        c.pc = c.execute(c.pc)
    raise ValueError('Filter native instruction limit at ' + hex(c.pc))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    files, _, component = compose()
    print('Plan: exact build scope, both native caller sites, text/nontext selection, real SDK mode2 encoding and state transitions.')
    if not args.verify:
        print('DRY RUN: no execution/report')
        return
    out = ROOT / 'work/output' / VERSION
    exe = (out / '1ST_READ.BIN').read_bytes()
    assert exe == files['1ST_READ.BIN']
    previous = (ROOT / 'work/output' / PRIOR / '1ST_READ.BIN').read_bytes()
    assert struct.unpack_from('<4I', exe, 0xe6ee8) == (0, 2, 1, 3)
    # The font initializer registers its texture/sprite tables at entry 63.
    assert struct.unpack_from('<I', exe, 0x66ee8)[0] == 0x8c1f2f20
    assert struct.unpack_from('<I', exe, 0x66ee4)[0] == 0x8c16ed5c + 63 * 48
    assert exe[0x68bc0:0x68bc4] == bytes.fromhex('3fe2262f')
    # Build carries byte-exact historical proofs, not newly claimed test runs.
    archives = []
    for name in ('WIN00.AFS', 'D_SCE.AFS', 'text/D_PAPER.BIN', 'text/D_NAMES.BIN', 'text/D_BMESS.BIN'):
        raw = (out / name).read_bytes()
        assert raw == (ROOT / 'work/output' / PRIOR / name).read_bytes()
        archives.append({'file': name, 'sha256': digest(raw)})
    records = []
    steps = 0
    for resource in (None, 0, 1, 62, 63, 64, 255, 65535):
        for mode in (0, 1, 2):
            for seed in (0, 0x94be9c2d, 0xffffffff):
                c = fresh(exe, resource, mode, seed)
                regs = c.reg[8:]
                guards = bytes(c.regions[-1][1])
                steps += run(c, ENTRY)
                selected = 1 if resource == 63 else mode
                expected_filter = (0, 1, 2)[selected]
                assert c.inputs == [selected] and c.finalizations == 1
                assert c.read(CTX + 84, 4) == (0, 2, 1)[selected]
                assert c.read(CTX + 0x98, 4) == ((seed & ~0x6000) | expected_filter << 13)
                assert c.reg[8:] == regs and c.pr == STOP
                # Real Ninja sprite state copy preserves the new filter bits.
                c.write(0x8c419a58, CTX + 0x90, 4)
                c.write(0x8c41936c, 0, 4)
                c.pr = STOP
                steps += run(c, 0x8c0c7d34)
                assert c.read(0x8c461b88, 4) >> 13 & 3 == expected_filter
                # Texture binding replaces UV-size bits only. Use a real-sized
                # bounded texture-list fixture and execute the actual binder.
                c.write(0x8c119f64, OBJ, 4)
                c.write(OBJ, OBJ + 16, 4)
                c.write(OBJ + 24, OBJ + 64, 4)
                for off, val in ((0, 0x12345678), (4, 0xabcdef01), (8, 0x2b),
                                 (12, 0x14012345), (24, 0x00100000)):
                    c.write(OBJ + 64 + off, val, 4)
                c.reg[4] = 0
                c.pr = STOP
                steps += run(c, 0x8c0c8a9e)
                assert c.read(0x8c461b88, 4) >> 13 & 3 == expected_filter
                # Only active stack frame bytes may change.
                stack = bytes(c.regions[-1][1])
                assert stack[:0xb80] == guards[:0xb80] and stack[0xc00:] == guards[0xc00:]
                records.append({'resource': resource, 'input_mode': mode, 'selected_mode': selected,
                                'seed_mode2': hex(seed), 'encoded_mode2': hex(c.read(CTX + 0x98, 4))})
    caller_cases = []
    for start, stop in ((0x8c030e66, 0x8c030e6e), (0x8c030e72, 0x8c030e7a)):
        for resource in (62, 63, 64):
            for raw, label in ((previous, 'prior'), (exe, 'current')):
                c = fresh(raw, resource, 99, 0xffffffff)
                saved = c.reg[8:]
                steps += run(c, start, stop)
                desired = 1 if label == 'current' and resource == 63 else 0
                assert c.inputs == [desired] and c.read(CTX + 0x98, 4) >> 13 & 3 == desired
                assert c.reg[8:] == saved
                caller_cases.append({'site': hex(start), 'resource': resource, 'build': label, 'filter_bits': desired})
    # An immediately following nontext sprite must reset bilinear back to point.
    c = fresh(exe, 63, 0, 0x94be9c2d)
    transitions = []
    for resource in (63, 12, 63, 64, 0):
        c.write(OBJ + 38, resource, 2)
        c.reg[4] = 0
        c.pr = STOP
        steps += run(c, ENTRY)
        bits = c.read(CTX + 0x98, 4) >> 13 & 3
        assert bits == int(resource == 63)
        transitions.append([resource, bits])
    proof = {
        'version': VERSION, 'executable_sha256': digest(exe),
        'component_sha256': digest((out / 'text-filter-component.json').read_bytes()),
        'selection_encoder_cases': len(records), 'caller_cases': len(caller_cases),
        'state_transitions': transitions, 'native_instructions': steps,
        'archives_byte_exact': archives, 'cases': records, 'callers': caller_cases,
        'checks': ['Both real call sites select point for prior text and bilinear for current text',
                   'Real native SDK setter and mode2 command encoder executed; filter bits 14:13 match independent reference',
                   'Real Ninja sprite state copy and texture bind retain filter bits; font resource 63 registration checked',
                   'All other mode2 fields preserved, source font/advances/archives unchanged',
                   'Nontext draws reset point filtering; callee-saved registers, stack and guards retained'],
        'limits': ['State finalizer 8c0d0b00 is a recorded no-op fixture',
                   'Native command creation is verified; full sprite pipeline, GPU blending and live appearance are not',
                   'Prior font/text/regression reports remain historical; they were not rerun by this test'],
    }
    print(json.dumps({k: v for k, v in proof.items() if k not in ('cases', 'callers')}, indent=2))
    if args.write_report:
        p = out / 'text-filter-native-test.json'
        p.write_text(json.dumps(proof, indent=2) + '\n', 'utf-8')
        m = json.loads((out / 'font4x-patch.json').read_text('utf-8'))
        m['text_filter'].update(native_validation='pass; real selector/setter/mode2 encoder, bounded finalizer',
                                proof_sha256=digest(p.read_bytes()))
        (out / 'font4x-patch.json').write_text(json.dumps(m, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
