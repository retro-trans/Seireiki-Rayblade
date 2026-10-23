"""Execute the original game's PRS decoder against English components.

Uses the existing strict SH-4 interpreter. Unmapped writes fail; guard bytes,
returned size, exact payload and callee-saved registers are checked. No files
are modified. Capacity for the library remains a separate loader question.
"""
import hashlib
import json
from build_font_patch import ROOT, BASE
from test_font_patch import CPU


def verify(executable, packed, expected, capacity, instruction_limit=8_000_000):
    source = 0x8c500000
    target = 0x8c600000
    guard = 64
    cpu = CPU(executable, b'', 0, 0)
    cpu.regions = [(BASE, bytearray(executable)),
                   (source, bytearray(packed)),
                   (target - guard, bytearray(b'\xa5' * (capacity + 2 * guard))),
                   (0x8c169af0, bytearray(20)),
                   (0x8c700000, bytearray(0x1000))]
    cpu.reg[4], cpu.reg[5] = source, target
    cpu.pc = 0x8c0221a4
    preserved = cpu.reg[8:]
    for count in range(instruction_limit):
        if cpu.pc == 0xdead0000:
            break
        cpu.pc = cpu.execute(cpu.pc)
    else:
        raise ValueError('Native decoder instruction limit exceeded')
    actual, offset = cpu.area(target, capacity)
    if cpu.reg[8:] != preserved or cpu.reg[0] != len(expected):
        raise ValueError('Native decoder return/ABI mismatch')
    if actual[offset:offset + len(expected)] != expected:
        raise ValueError('Native decoder output differs')
    if actual[:offset] != b'\xa5' * guard or actual[offset + len(expected):] != b'\xa5' * (capacity - len(expected) + guard):
        raise ValueError('Native decoder changed destination guard/tail')
    return count


def main():
    exe = (ROOT / 'work/source/disc/1ST_READ.BIN').read_bytes()
    # Confirm the D_NAMES loader's fixed 64 KiB allocation and decoder call.
    checks = {0x10e9e: '0ad4', 0x10ea2: '0b42', 0x10ede: '0b43'}
    for offset, expected in checks.items():
        if exe[offset:offset + 2].hex() != expected:
            raise ValueError('D_NAMES loader code changed at ' + hex(offset))
    if int.from_bytes(exe[0x10ec8:0x10ecc], 'little') != 0x10000:
        raise ValueError('Unexpected D_NAMES destination capacity')
    folder = ROOT / 'work/output/0.1.3/text'
    for name, capacity in [('D_NAMES', 65536), ('D_PAPER', None)]:
        report = json.loads((folder / ('names-component-report.json' if name == 'D_NAMES' else 'library-component-report.json')).read_text())
        packed = (folder / (name + '.BIN')).read_bytes()
        plain = (folder / (name + '.en.dec.bin')).read_bytes()
        if hashlib.sha256(packed).hexdigest() != report['compressed_sha256'] or hashlib.sha256(plain).hexdigest() != report['output_sha256']:
            raise ValueError('Component manifest hash mismatch')
        count = verify(exe, packed, plain, capacity or len(plain))
        print('PASS:', name, 'original SH-4 decoder,', len(plain), 'bytes,', count,
              'instructions; exact output and unchanged guard/tail bytes.')
        if capacity:
            print('D_NAMES native allocation:', capacity, 'bytes;', capacity - len(plain), 'bytes spare.')
        else:
            print('Library loader allocation is not yet proven; test buffer was sized to the expected component.')


if __name__ == '__main__':
    main()
