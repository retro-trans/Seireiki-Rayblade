"""Audit reported hardware regression without changing any game build. Dry first."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check():
    from test_native_movie_font import DrawCPU, STOP, bits
    from inspect_vram_residency import inspect
    from rayblade_codec import decompress

    output = ROOT / 'work/output'
    images = {v: (output / v / '1ST_READ.BIN').read_bytes() for v in ('0.7.2', '0.7.11', '0.7.23', '0.7.24')}
    # The routine whose memory layout is executed below is stock in all builds.
    assert all(e[0xd9846:0xd9acc] == images['0.7.2'][0xd9846:0xd9acc] for e in images.values())
    fields = (0x8c462008, 0x8c46202c, 0x8c462034, 0x8c462038)
    rows = []
    for label, filename, units in (
            ('older 320x240 snapshot', '0.1.39-album-01.ram', 384176),
            ('current 640x480 snapshot', 'battle-fixed-stock-0719.ram', 384176),
            ('hypothetical larger reserve; NOT a build', 'battle-fixed-stock-0719.ram', 574640)):
        raw = (ROOT / 'work/source/runtime' / filename).read_bytes()
        assert raw[0xe9846:0xe9acc] == images['0.7.23'][0xd9846:0xd9acc]
        c = DrawCPU(images['0.7.23'], b'', 0, 0)
        c.regions = [(0x8c000000, bytearray(raw))]
        c.reg[15], c.pr = 0x8cffe000, STOP
        c.fr, c.fpul, c.visited = [bits(0.)] * 16, 0, set()
        flags = c.read(0x8c461c24, 4)
        assert flags == 0x65000f
        c.write(c.reg[15], flags, 4)
        c.write(0x8c462014, units, 4)
        c.pc = 0x8c0e9846
        for steps in range(10000):
            if c.pc == 0x8c0e9a92:
                break  # Before unrelated list submission and register setup.
            c.pc = c.execute(c.pc)
        else:
            raise AssertionError('SDK layout execution bound')
        values = [c.read(p, 4) for p in fields]
        if units == 384176:
            assert values == [struct.unpack_from('<I', raw, p & 0xffffff)[0] for p in fields]
        rows.append({'label': label, 'snapshot': 'work/source/runtime/' + filename,
                     'snapshot_sha256': sha(raw), 'TA_allocator_units': units,
                     'geometry_reservation_bytes': units * 2, 'instructions': steps,
                     'SDK_fields': {hex(p): hex(v) for p, v in zip(fields, values)},
                     'list_growth_interval_bytes': values[2] - values[3]})
    assert [r['list_growth_interval_bytes'] for r in rows] == [78720, 31104, 78720]
    extra = (574640 - 384176) * 2
    pressure = []
    for name in ('princess-final-0722.ram', 'later-bridge-final-0722.ram', 'forecast-0723.ram', 'split-final-0723.ram'):
        raw = (ROOT / 'work/source/issue-1' / name).read_bytes()
        state = inspect(raw)
        pressure.append({'snapshot': 'work/source/issue-1/' + name, 'sha256': sha(raw),
                         'free_bytes_by_bank': [b['total_free'] for b in state['banks']],
                         'hypothetical_extra_geometry_bytes': extra,
                         'bank_0_free_minus_extra': state['banks'][0]['total_free'] - extra})

    old_archive = (output / '0.7.2/D_SCE.AFS').read_bytes()
    new_archive = (output / '0.7.23/D_SCE.AFS').read_bytes()
    reports = {v: json.loads((output / v / 'text/scenario-component-report.json').read_text(encoding='utf-8')) for v in ('0.7.2', '0.7.23')}
    scenarios = []
    for index in (2, 3):
        old, new = [reports[v]['members'][index] for v in ('0.7.2', '0.7.23')]
        assert old['name'] == new['name']
        decoded = []
        for archive, row in ((old_archive, old), (new_archive, new)):
            p, n = struct.unpack_from('<II', archive, 8 + index * 8)
            data, used = decompress(archive[p+20:p+n])
            assert sha(data) == row['decoded_sha256']
            decoded.append(data)
        size = old['original_bytes']
        assert size == new['original_bytes'] and decoded[0][:size] == decoded[1][:size]
        assert len(old['commands']) == len(new['commands'])
        changed, choice_changes = [], []
        for a, b in zip(old['commands'], new['commands']):
            assert a['id'] == b['id']
            if decoded[0][a['english_offset']:a['english_offset']+a['english_bytes']] != decoded[1][b['english_offset']:b['english_offset']+b['english_bytes']]:
                changed.append(a['id'])
                if decoded[0][a['source_offset']-1] & 0x80:
                    choice_changes.append(a['id'])
        scenarios.append({'member': old['name'], 'original_program_bytes': size,
                          'original_program_exact': True,
                          'changed_English_commands': changed, 'changed_choice_commands': choice_changes,
                          'scope': 'Source VM program is exact. English bank/layout changes remain a separate possible cause; this does not prove hardware execution.'})
    return {
        'date': '2026-10-29', 'reported_device': 'Dreamcast / GDEMU / VGA',
        'reported_diagnostic_result': 'User reports 0.7.24 did not fix the failure',
        'hardware_root_cause_confirmed': False, 'SDK_layout_execution': rows,
        'observed_regression': 'At the same total reservation, 640x480 reduces the SDK list-growth interval from 78,720 to 31,104 bytes.',
        'hypothetical_reserve_increase': {'bytes': extra, 'published_or_built': False,
            'warning': 'A naive reserve increase exceeds free bank-0 space in known Stage 6 snapshots; it is not accepted as a fix.'},
        'existing_resident_texture_pressure': pressure, 'early_scenario_comparison': scenarios,
        'primary_hardware_reference': 'https://github.com/KallistiOS/KallistiOS/blob/master/kernel/arch/dreamcast/hardware/pvr/pvr_internal.h',
        'reference_scope': 'Describes vertex, object-pointer and tile-matrix buffers and growth/overflow. Does not diagnose this game.',
        'pending': ['Tester result for public 0.7.11 on the same Clear 2 VMU save and GDEMU/VGA system',
                    'Physical failure location/IRQ evidence; no new diagnostic build selected yet'],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    if not args.write:
        print('DRY RUN: execute stock SDK layout on existing RAM copies, compare early script program bytes, and write an English-only audit. No game build changes.')
        return
    result = check()
    path = ROOT / 'work/output/hardware-transition/failed-0724-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('PASS: original/current SDK layout matches both captured states; audit saved to', path)
    print('No new build or confirmed hardware fix.')


if __name__ == '__main__': main()
