"""Execute the native unit-list order selector and real byte-field query.

Only the sprite constructor endpoint is captured. No allocation/GPU proof.
Default dry run; --verify executes, --write-report additionally saves evidence.
"""
import argparse
import json

from build_bitmap_font import ROOT, digest
from build_order_icons_patch import PRIOR, recipe
from check_attack_variant_selection import AttackCPU

OUT = ROOT / 'work/ui/asset-audit/EFFECT/counterattack-icons'
START, END = 0x8c0627d8, 0x8c062810
SP, UNIT = 0x8c701000, 0x8c500040


class OrderCPU(AttackCPU):
    def execute(self, pc, delay=False):
        if pc == 0x8c075c50:
            assert not delay
            self.calls.append({'arguments': list(self.reg[4:8]),
                               'stack_xy': [self.read(self.reg[15]+n, 4) for n in (0, 4)]})
            self.reg[0] = 0x1234
            return self.pr
        return super().execute(pc, delay)


def check():
    exe = (ROOT / 'work/output' / PRIOR / '1ST_READ.BIN').read_bytes()
    mapping = recipe()
    cases = []
    for order in range(5):
        for flags in (0, 7, 0xc0, 0xc7):
            for row, first in ((0, 0), (5, 2), (14, 10), (32766, 32764)):
                c = OrderCPU(exe, b'', 0, 0)
                memory = bytearray(b'\xa5'*128)
                stack = bytearray(b'\xa5'*0x2000)
                c.regions = [(0x8c010000, bytearray(exe)), (UNIT-64, memory), (0x8c700000, stack)]
                c.reg[15] = SP
                c.write(SP, row, 4)
                c.write(SP+6, first, 2)
                c.write(SP+12, UNIT, 4)
                c.write(UNIT+8, (order<<3)|flags, 1)
                saved, before_memory, before_stack = c.reg[8:].copy(), bytes(memory), bytes(stack)
                c.calls, c.visited = [], set()
                c.pc = START
                for count in range(1000):
                    if c.pc == END:
                        break
                    c.pc = c.execute(c.pc)
                else:
                    raise ValueError('Native order selector instruction limit at '+hex(c.pc))
                expected = {'arguments': [255, 3, 58+order, 0], 'stack_xy': [32, (row-first+1)*24+64]}
                assert c.calls == [expected], (order, flags, row, first, c.calls)
                assert 0x8c0938e0 in c.visited and 0x8c062802 in c.visited
                assert c.reg[8:] == saved and memory == before_memory
                # The byte-field SDK query uses a bounded callee stack below SP.
                allowed = set(range(SP-128, SP))
                changed = [0x8c700000+i for i, (a, b) in enumerate(zip(before_stack, stack)) if a != b]
                assert set(changed) <= allowed
                cases.append({'order': order, 'unrelated_bits': flags, 'row': row, 'first': first,
                              **expected, 'instructions': count,
                              'minimum_changed_stack_offset': min((n-SP for n in changed), default=0)})
    # Confirm the code interval hasn't changed in the English patch.
    source = (ROOT / 'work/source/disc/1ST_READ.BIN').read_bytes()
    lo, hi = START-0x8c010000, END-0x8c010000
    assert exe[lo:hi] == source[lo:hi]
    return {'source_build': PRIOR, 'executable_sha256': digest(exe),
            'native_interval': [hex(START), hex(END)], 'code_sha256': digest(exe[lo:hi]),
            'context_id': mapping['context_id'], 'context_source_sha256': mapping['context_source_sha256'],
            'menu_order': mapping['full_menu'], 'native_query': 'Actual 0x8c0938e0 unsigned byte field descriptor 0x203: bits 5:3 at unit+8',
            'sprite_rule': 'resource 3, sprite 58 + policy', 'case_count': len(cases),
            'native_instructions': sum(r['instructions'] for r in cases), 'cases': cases,
            'native_guard_and_ABI': 'pass', 'only_stub': '0x8c075c50 sprite constructor; captures R4..R7 and stack x/y',
            'EFFECT_copy': 'Exact original art/coordinate duplicate; separate EFFECT runtime selection not executed',
            'native_sprite_allocation_submission': False, 'GPU': False, 'live_validation': 'pending'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: 80 native policy/flags/list-row cases, real SDK query, captured sprite arguments, memory guards and ABI.', flush=True)
    if not args.verify:
        print('DRY RUN: no execution/report')
        return
    result = check()
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}, indent=2), flush=True)
    if args.write_report:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT/'native-selection.json').write_text(json.dumps(result, indent=2)+'\n', 'utf-8')


if __name__ == '__main__':
    main()
