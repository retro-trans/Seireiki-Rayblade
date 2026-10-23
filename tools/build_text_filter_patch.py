"""Select native bilinear filtering for dynamic text sprites only. Dry first."""
import argparse
import json
import struct

from build_bitmap_font import ROOT, digest
from build_font4x_patch import BASE, START, END
from sh4_asm import Assembler

VERSION = '0.1.22'
PRIOR = '0.1.21'
ENTRY = BASE + 0x6b800
POINTER = 0x20f44
SETTER = 0x8c0a78d0


def dispatcher():
    a = Assembler(ENTRY)
    a.lit(0x8c17fba0, 0)
    a.load('l', 0, 0)
    a.rr('tst', 0, 0)
    a.branch('bt', 'tail')
    a.addi(38, 0)
    a.load('w', 0, 0)
    a.rr('extu.w', 0, 0)
    a.emit(0x883f)  # CMP/EQ #63,R0: the dynamic text resource
    a.branch('bf', 'tail')
    a.imm(1, 4)  # Native API mode 1 -> context 2 -> PVR filter bits 1
    a.label('tail')
    a.lit(SETTER, 0)
    a.emit(0x402b)
    a.emit(0x0009)
    return a.pool_and_finish()


def compose():
    base = ROOT / 'work/output' / PRIOR
    source = (base / '1ST_READ.BIN').read_bytes()
    target = bytearray(source)
    code = dispatcher()
    at = ENTRY - BASE
    m = json.loads((base / 'font4x-patch.json').read_text('utf-8'))
    assert START + m['kernel_bytes_used'] <= at and at + len(code) <= END
    assert source[at:at + len(code)] == b'\x09\x00' * (len(code) // 2)
    assert struct.unpack_from('<I', source, POINTER)[0] == SETTER
    uses = []
    for pc in range(max(0, POINTER - 1024), POINTER, 2):
        word = struct.unpack_from('<H', source, pc)[0]
        if word >> 12 == 0xd and ((pc + 4) & ~3) + (word & 255) * 4 == POINTER:
            uses.append(BASE + pc)
    assert uses == [0x8c030e68, 0x8c030e74]
    assert source[0x20e66:0x20e68] == source[0x20e72:0x20e74] == b'\0\xe4'
    target[at:at + len(code)] = code
    struct.pack_into('<I', target, POINTER, ENTRY)
    ranges = [(at, at + len(code)), (POINTER, POINTER + 4)]
    changed = [i for i, (a, b) in enumerate(zip(source, target)) if a != b]
    assert len(source) == len(target)
    assert all(any(lo <= i < hi for lo, hi in ranges) for i in changed)
    files = {p.name: p.read_bytes() for p in base.iterdir()
             if p.is_file() and p.suffix.lower() != '.png'}
    files.update({'text/' + p.name: p.read_bytes() for p in (base / 'text').iterdir() if p.is_file()})
    for name in ('english-disc-report.json', 'READ-ME.txt'):
        files.pop(name, None)
    files['1ST_READ.BIN'] = bytes(target)
    component = {
        'version': VERSION, 'source_build': PRIOR,
        'source_executable_sha256': digest(source), 'executable_sha256': digest(target),
        'dispatcher_address': hex(ENTRY), 'dispatcher_bytes': len(code),
        'changed_executable_bytes': len(changed), 'callee_pointer_offset': hex(POINTER),
        'caller_load_addresses': [hex(v) for v in uses],
        'allowed_ranges': [[lo, hi] for lo, hi in ranges],
        'selection': 'Only object resource word at +38 equal to 63 selects native filter mode 1; other resources keep their input mode',
        'unchanged': 'All font/translation/image/archive payloads, advances, raster and allocator code, story helpers, resource IDs and texture dimensions',
        'native_validation': 'pending', 'live_appearance': 'pending',
        'reference': 'https://raw.githubusercontent.com/KallistiOS/KallistiOS/master/kernel/arch/dreamcast/include/dc/pvr/pvr_header.h',
    }
    m.update(version=VERSION, previous_build=PRIOR,
             status='Native text-filter candidate; verification and packaging pending')
    m['files']['1ST_READ.BIN']['target_sha256'] = digest(target)
    m['text_filter'] = component
    m['scenario']['executable_sha256'] = digest(target)
    m['native_proof_reuse'] = {
        'source_build': PRIOR,
        'scope': 'Prior reports remain historical; exact unchanged raster/text/archive paths may reuse their evidence. New filter dispatcher and native command encoding require fresh proof.',
    }
    files['font4x-patch.json'] = json.dumps(m, indent=2).encode() + b'\n'
    files['text-filter-component.json'] = json.dumps(component, indent=2).encode() + b'\n'
    return files, m, component


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    files, _, report = compose()
    print(json.dumps(report, indent=2))
    if not args.write:
        print('DRY RUN: no build written')
        return
    out = ROOT / 'work/output' / VERSION
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    print('Wrote native text-filter candidate:', out)


if __name__ == '__main__':
    main()
