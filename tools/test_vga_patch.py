"""Execute VGA patch SH-4 with bounded cable/register fixtures. Dry by default."""
import argparse
import json
import struct
from build_vga_patch import ROOT, OUT, VERSION, PRIOR, compose, digest
from test_font_patch import CPU, BASE

STOP = 0xdead0000
FALLBACK = BASE + 0xda904
STATE = 0x8c461bdc
REGS = 0xa05f8000


class VideoCPU(CPU):
    def __init__(self, exe, cable, flags, entry):
        super().__init__(exe, bytes(0x10000), 0, 0)
        self.regions += [(0x8c460000, bytearray(0x10000)),
                         (REGS, bytearray(0x1000)), (0xff800030, bytearray(4))]
        self.write(0xff800030, cable << 8, 2)
        self.write(STATE, flags, 4)
        # Plausible framebuffer offsets/stride and render-register shadow state.
        for i, v in enumerate((0x100000, 0x180000, 0, 0x007e0345, 0x20c0359,
                               0x0080000d, 0x150104, 0, 0, 0, 0, 0, 0, 0,
                               0, 0, 0, 0, 0x114, 0x3450000, 0x160000)):
            self.write(0x8c461e70 + 4*i, v, 4)
        self.write(STATE + 48, 0x100000, 4)
        self.write(STATE + 52, 0x180000, 4)
        self.pc = BASE + entry
        self.calls = []
        self.fallback = False

    def execute(self, pc, delay=False):
        op, args = self.ins(pc)
        if op == 'mova':
            self.reg[0] = int(args[0], 16)
            return pc + 2
        if pc == BASE + 0x96760:
            assert self.reg[4] == 0
            self.calls.append('video_blank_0')
            return self.pr
        if pc == FALLBACK:
            self.fallback = True
            return STOP
        if pc == BASE + 0x9686c:
            self.calls.append(('mode_selector', self.reg[4]))
            return STOP
        return super().execute(pc, delay)

    def run_video(self):
        saved = self.reg[8:]
        for count in range(2000):
            if self.pc == STOP:
                assert self.reg[8:] == saved and self.pr == STOP, 'ABI/stack corruption'
                return count
            self.pc = self.execute(self.pc)
        raise AssertionError('Video instruction limit')


def check():
    exe, ip, component = compose()
    # The exact original reference is an execution oracle for integration only;
    # independent register expectations below establish VGA timing/cable behavior.
    reference = next((ROOT / 'incoming/vga-reference').glob('**/rolly-dc-rayblade-vga-patch-v.1.0/1ST_READ.BIN')).read_bytes()
    base = (ROOT / f'work/output/{PRIOR}/1ST_READ.BIN').read_bytes()
    assert exe[0xbc150:0xbc154] == struct.pack('<I', BASE + 0xda5c0)
    rows = []
    for entry in (0xda5c0, 0xbbe00):
        for cable in range(4):
            for flags in (0, 1, 0x10, 0x11, 0x20, 0x21, 0x40, 0x41, 0x42, 0x43, 0x60, 0x61):
                actual = VideoCPU(exe, cable, flags, entry)
                oracle = VideoCPU(reference, cable, flags, entry)
                steps = actual.run_video()
                oracle.run_video()
                assert actual.reg == oracle.reg and actual.t == oracle.t
                assert actual.calls == oracle.calls and actual.fallback == oracle.fallback
                for address, _ in actual.regions[-3:]:
                    assert actual.area(address, 4)[0] == oracle.area(address, 4)[0]
                if entry == 0xda5c0:
                    assert actual.fallback == (cable != 0)
                    if cable:
                        assert actual.read(STATE - 4, 4) == 0
                        assert actual.read(STATE, 4) == flags & ~3
                        assert not any(actual.area(REGS, 4)[0])
                    else:
                        assert actual.read(REGS + 0xd0, 4) == 0x100  # SPG_CONTROL: VGA sync, interlace bit clear
                        assert actual.read(REGS + 0xd8, 4) == 0x020c0359  # 524/857 sync totals
                        assert actual.read(REGS + 0x44, 4) & (1 << 23)  # 27 MHz pixel clock
                        expected_output = 0x160108 if not flags & 0x10 else 0x160008
                        assert actual.read(REGS + 0xe8, 4) == expected_output
                else:
                    assert not actual.fallback
                    if cable == 0:
                        assert actual.calls == ['video_blank_0']
                        expected_size = (0x007e0345 & 0xc00fffff) | 0x00100000
                        if flags & 0x20:
                            expected_size += 0x3c000
                        assert actual.read(REGS + 0x5c, 4) == expected_size
                rows.append({'entry': hex(entry), 'cable': cable, 'flags': flags,
                             'instructions': steps, 'non_vga_fallback': actual.fallback})
    # Retained original TV fallback and video-blank implementation are byte-exact.
    assert exe[0xda904:0xdac00] == base[0xda904:0xdac00]
    assert exe[0x96760:0x9686c] == base[0x96760:0x9686c]
    return {'version': VERSION, 'executable_sha256': digest(exe),
            'boot_sha256': digest(ip), 'component_sha256': digest(json.dumps(component, indent=2).encode() + b'\n'),
            'cases': rows, 'case_count': len(rows),
            'scope': 'Actual patched SH-4 cable detection, init, commit and MMIO writes; all four cable IDs, twelve flag combinations, register/ABI comparison with exact retail VGA reference',
            'limits': 'Bounded MMIO/blank/fallback fixtures. No physical monitor, GPU scanout, BIOS, movie or full-game proof.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    proof = check()
    print('PASS:', proof['case_count'], 'native video cases;', sum(r['instructions'] for r in proof['cases']), 'SH-4 instructions.')
    if args.write:
        assert digest((OUT / '1ST_READ.BIN').read_bytes()) == proof['executable_sha256']
        assert digest((OUT / 'component-report.json').read_bytes()) == proof['component_sha256']
        (OUT / 'native-test.json').write_text(json.dumps(proof, indent=2) + '\n', 'utf-8')
    else:
        print('DRY RUN: no files written.')


if __name__ == '__main__':
    main()
