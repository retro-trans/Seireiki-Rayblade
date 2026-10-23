"""Read-only annotated SH-4 listing. Requires Capstone in work/vendor.

Example: python tools/sh4_inspect.py --range 0x124a0 0x12700
All offsets are executable file offsets; load base is 0x8c010000.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/vendor'))
BASE = 0x8c010000


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--range', nargs=2, type=lambda x: int(x, 0))
    ap.add_argument('--refs', type=lambda x: int(x, 0))
    ap.add_argument('--fpu',action='store_true',help='Decode SH-4 FPU instructions as well as integer code')
    args = ap.parse_args()
    data = (ROOT / 'work/source/disc/1ST_READ.BIN').read_bytes()
    if args.refs is not None:
        for match in re.finditer(re.escape(struct.pack('<I', args.refs)), data):
            offset = match.start()
            uses = []
            for pc in range(max(0, offset - 1024) & ~1, offset, 2):
                op = struct.unpack_from('<H', data, pc)[0]
                if op >> 12 == 0xd and ((pc + 4) & ~3) + (op & 255) * 4 == offset:
                    uses.append('0x{:x}'.format(BASE + pc))
            print('literal file 0x{:x}, PC-relative uses {}'.format(offset, uses))
    if args.range:
        import capstone
        cs = capstone.Cs(capstone.CS_ARCH_SH,
                         capstone.CS_MODE_SH4 | capstone.CS_MODE_LITTLE_ENDIAN |
                         (capstone.CS_MODE_SHFPU if args.fpu else 0))
        cs.skipdata = True
        lo, hi = args.range
        for ins in cs.disasm(data[lo:hi], BASE + lo):
            note = ''
            if ins.mnemonic in ('mov.l', 'mov.w') and ins.op_str.startswith('0x'):
                offset = int(ins.op_str.split(',')[0], 16) - BASE
                if 0 <= offset < len(data) - 4:
                    value = struct.unpack_from('<I' if ins.mnemonic == 'mov.l' else '<H', data, offset)[0]
                    note = ' = 0x{:x}'.format(value)
            print('{:08x} {:8s} {}{}'.format(ins.address, ins.mnemonic, ins.op_str, note))


if __name__ == '__main__':
    main()
