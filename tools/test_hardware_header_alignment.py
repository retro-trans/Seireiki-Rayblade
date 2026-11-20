"""Reproduce the shared name-width regression under strict SH-4 alignment."""
import struct
from build_bitmap_font import ROOT
from build_location_header_fix import BASE, START, MEDIUM
from build_map_font_patch import member
from test_library_headers import setup, call, GLOBALS
from rayblade_text import relative_target


def check(candidate):
    folder = ROOT / 'work/output/0.7.45'
    names = (folder / 'text/D_NAMES.en.dec.bin').read_bytes()
    paper = (folder / 'text/D_PAPER.en.dec.bin').read_bytes()
    font = member((folder / 'WIN00.AFS').read_bytes(), 0)[99072:]
    old = (folder / '1ST_READ.BIN').read_bytes()
    sources = {v: (ROOT / f'work/output/{v}/1ST_READ.BIN').read_bytes() for v in ('0.7.46', '0.7.47')}

    def cpu(exe):
        c = setup(exe, font, paper, names)
        c.strict_alignment = True
        return c

    # Use the actual group-8 dialogue caller, including its indirect call.
    # Stop immediately after measurement returns; no GPU/scene endpoint stub.
    assert old[0x2e706:0x2e708] == b'\x00\x08'
    failures = []
    for version, exe in sources.items():
        for group in (6, 8):
            c = cpu(exe)
            try:
                call(c, BASE + START, group << 8)
            except RuntimeError as error:
                message = str(error.__cause__)
                assert 'SH4 unaligned read' in message, message
                failures.append({'version': version, 'group': group,
                                 'pc': hex(c.pc), 'address': hex(c.reg[2]), 'error': message})
            else:
                raise AssertionError('Failed binary did not reproduce an alignment error')
        c = cpu(exe)
        c.write(0x8c701803, 0, 1)
        try:
            call(c, 0x8c03e684, stop=0x8c03e692)
        except RuntimeError as error:
            message = str(error.__cause__)
            assert 'SH4 unaligned read' in message and c.reg[2] == 0x8c900000+relative_target(names,8*4)
            failures.append({'version': version, 'caller': '0x8c03e684 (dialogue group 8)',
                             'pc': hex(c.pc), 'address': hex(c.reg[2]), 'error': message})
        else:
            raise AssertionError('Dialogue caller did not reproduce the fault')

    caller_cases = []
    for index in range(128):
        results = []
        for exe in (old, candidate):
            c = cpu(exe)
            c.write(0x8c701803, index, 1)
            saved = c.reg[8:]
            call(c, 0x8c03e684, stop=0x8c03e692)
            assert c.reg[8:] == saved
            results.append(c.reg[0])
        assert results[0] == results[1], (index, results)
        caller_cases.append({'group8_index': index, 'width': results[1]})

    # Both positive and negative relative offsets at every alignment. Exercise
    # every group handled by the native getter, including alias group 7.
    globals_ = dict(GLOBALS, **{})
    globals_.update({g: 0x8c1dbf20+(g-13)*4 for g in range(13,23)})
    payloads = [b'\xff', b'\x05\x06\xff', b'\xf0\x01\x05\xff',
                b'\xfa\xfb\xfd\xfe\x05\xff', b'\xfc\x00\x3c\x00\x00\x05\xff',
                b'\xfc\x00\x01\x05\xff', bytes([len(MEDIUM)+1, 0xff])]

    def expected(payload, native):
        total = i = 0
        while payload[i] != 255:
            v = payload[i]
            if v < 0xf0:
                total += font[0xa0+(v if v<len(MEDIUM) else MEDIUM.index('?'))] if native else 8
            elif v < 0xfa:
                total += 12
                i += 1
            elif v == 252:
                i += 2
                if payload[i] == 60:
                    i += 2
            i += 1
        return total

    count = 0
    for group in range(23):
        c = cpu(candidate)
        address = 0x8c920000
        c.regions.append((address, bytearray(0x3000)))
        for skew in range(4):
            table = address + 0x400 + skew
            c.write(GLOBALS[6] if group == 7 else globals_[group], table-1024 if group == 7 else table, 4)
            for index in (0, 255):
                cell = table + index*4
                for backwards in (False, True):
                    target = address + (0x40 if backwards else 0x2000)
                    offset = (target-cell) & 0xffffffff
                    # Fixture construction also uses byte writes; never bypass
                    # an actual CPU alignment check to populate the offset.
                    for i, value in enumerate(struct.pack('<I', offset)):
                        c.write(cell+i, value, 1)
                    for payload in payloads:
                        for i, value in enumerate(payload): c.write(target+i, value, 1)
                        saved = c.reg[8:]
                        call(c, BASE+START, group*256+index)
                        assert c.reg[0] == expected(payload, group == 6), (group, skew, index, backwards, payload)
                        assert c.reg[8:] == saved
                        count += 1
    return {'strict_alignment': True, 'failed_binary_reproductions': failures,
            'dialogue_caller_cases': caller_cases, 'offset_and_control_cases': count,
            'actual_location_group_offset': hex(relative_target(names,6*4)),
            'actual_dialogue_group_offset': hex(relative_target(names,8*4)),
            'architecture_source': 'https://www.renesas.com/en/document/mas/sh-4-software-manual?r=1055166',
            'limitation': 'Instruction-level address-error reproduction using actual packed tables and caller. No physical hardware exception trace or full-game test.'}
