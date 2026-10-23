"""Dreamcast SDK compact-sector archive layout checks (no file mutation)."""
import struct


def compact_positions(data):
    assert data[:4] == b'AFS\0'
    count = struct.unpack_from('<I', data, 4)[0]
    assert 0 < count <= 65535 and 8 + count * 8 <= len(data)
    first = struct.unpack_from('<I', data, 8)[0]
    assert first % 2048 == 0 and 8 + count * 8 <= first and first // 2048 <= 65535
    position = first
    result = []
    for n in range(count):
        declared, size = struct.unpack_from('<II', data, 8 + 8 * n)
        sectors = (size + 2047) // 2048
        assert 0 < sectors <= 65535 and declared + size <= len(data)
        result.append({'member': n, 'declared_offset': declared,
                       'native_offset': position, 'bytes': size, 'sectors': sectors})
        position += sectors * 2048
    return result


def require_native_layouts(files):
    result = {}
    for name, raw in files.items():
        if not name.endswith('.AFS'):
            continue
        rows = compact_positions(raw)
        for row in rows:
            assert row['declared_offset'] == row['native_offset'], (
                'Incompatible native compact-sector AFS layout', name, row)
            assert row['native_offset'] + row['sectors'] * 2048 <= len(raw), (
                'Native sector read exceeds archive extent', name, row)
        result[name] = {'members': len(rows), 'first_sector': rows[0]['declared_offset'] // 2048,
                        'all_native_offsets_and_read_extents': 'pass'}
    return result
