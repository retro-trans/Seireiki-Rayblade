"""Relocate English library profiles and rebuild nested story-unlock spans.

Dry run by default. Retains metadata and all original bytes after the root
pointer table, appends rebuilt records, and verifies the result by reparsing.
This produces an offline component; native capacity/layout are separate checks.
"""
import argparse
import hashlib
import json
import struct
from build_font_patch import ROOT
from english_text_codec import encode, decode
from extract_library import extract, sections
from prepare_library_translation import fingerprint
from rayblade_codec import compress, decompress
from rayblade_text import relative_target


class EnglishSpanDecoder:
    def decode(self, data):
        text, end = decode(data)
        return {'text': text, 'terminator': end, 'bytes_consumed': len(data),
                'tokens': [{'type': 'terminator'}]}


def rebuild_record(data, entry, replacements):
    header_size = len(bytes.fromhex(entry['header_hex']))
    start = entry['record_offset'] + header_size
    seen = set()
    condition_count = 0

    def span(pos, end=None):
        nonlocal condition_count
        output = bytearray()
        begin = pos

        def text(finish):
            if begin < finish:
                if begin not in replacements:
                    raise ValueError('Missing translated span at ' + hex(begin))
                output.extend(replacements[begin])
                seen.add(begin)

        while pos < len(data) and (end is None or pos < end):
            value = data[pos]
            if value in (0xfc, 0xff):
                text(pos)
                if value == 0xff:
                    if end is not None:
                        raise ValueError('Unexpected nested terminator')
                    output.append(0xff)
                    return bytes(output), pos + 1
                flag, skip = struct.unpack_from('<HH', data, pos + 1)
                finish = pos + 3 + skip
                if skip < 2 or finish > len(data) or (end is not None and finish > end):
                    raise ValueError('Invalid original condition')
                payload, consumed = span(pos + 5, finish)
                if consumed != finish or len(payload) + 2 > 65535:
                    raise ValueError('Condition span cannot be encoded')
                output.append(0xfc)
                output.extend(struct.pack('<HH', flag, len(payload) + 2))
                output.extend(payload)
                condition_count += 1
                pos = begin = finish
            else:
                pos += 2 if 0xf0 <= value <= 0xfa else 1
        if end is None or pos != end:
            raise ValueError('Unterminated profile or crossed boundary')
        text(pos)
        return bytes(output), pos

    payload, finish = span(start)
    if seen != set(replacements):
        raise ValueError('Unconsumed English spans')
    if data[entry['record_offset']:finish].hex() != entry['raw_hex']:
        raise ValueError('Original profile changed')
    return bytes.fromhex(entry['header_hex']) + payload, condition_count


def build(*,section_overrides=None,version='0.1.3'):
    original, entries, source = extract()
    drafted = json.loads((ROOT / 'work/translation/en/library/library.json').read_text(encoding='utf-8'))
    if [r['id'] for r in source] != [r['id'] for r in drafted]:
        raise ValueError('Library source IDs changed')
    translated = {r['id']: r for r in drafted}
    for s in source:
        row = translated[s['id']]
        if row['source_sha256'] != fingerprint(s) or row['en'] is None:
            raise ValueError('Stale or missing translation: ' + s['id'])
    output = bytearray(original)
    while len(output) % 4:
        output.append(0)
    pool_start = len(output)
    canonical = {e['id']: e for e in entries if e['id'] == e['canonical_id']}
    targets = {}
    conditions = 0
    profiles = []
    expected_sections = {}
    for identity, entry in canonical.items():
        replacements = {}
        expected = []
        for n, section in enumerate(entry['sections']):
            lines = [translated[identity + '.s{:02d}.l{:02d}'.format(n, line)]['en']
                     for line in range(len(section['text'].split('<NL>')))]
            text = '<NL>'.join(lines)
            key=identity+'.s{:02d}'.format(n)
            if key in (section_overrides or {}):
                override=section_overrides[key]
                if hashlib.sha256(text.encode('utf-8')).hexdigest()!=override['prior_en_sha256']:
                    raise ValueError('Stale library layout: '+key)
                text=override['en']
            payload = encode(text)
            if decode(payload) != (text, 0xff):
                raise ValueError('English span round-trip failed')
            replacements[section['text_offset']] = payload[:-1]
            expected.append((text, section['conditions']))
        record, count = rebuild_record(original, entry, replacements)
        targets[identity] = len(output)
        output.extend(record)
        expected_sections[identity] = expected
        conditions += count
        profiles.append({'id': identity, 'old_offset': entry['record_offset'],
                         'new_offset': targets[identity], 'bytes': len(record),
                         'condition_nodes': count})
    for entry in entries:
        pointer = entry['pointer_offset']
        struct.pack_into('<I', output, pointer, targets[entry['canonical_id']] - pointer)
    if output[416 * 4:len(original)] != original[416 * 4:]:
        raise ValueError('Original profile bytes changed')
    codec = EnglishSpanDecoder()
    for entry in entries:
        target = relative_target(output, entry['pointer_offset'])
        if target != targets[entry['canonical_id']]:
            raise ValueError('Incorrect root pointer')
        header = bytes.fromhex(entry['header_hex'])
        if output[target:target + len(header)] != header:
            raise ValueError('Profile metadata changed')
        actual, end = sections(codec, output, target + len(header))
        if [(s['text'], s['conditions']) for s in actual] != expected_sections[entry['canonical_id']]:
            raise ValueError('Reparsed English/condition tree differs: ' + entry['id'])
        if end > len(output):
            raise ValueError('Profile points outside component')
    packed = compress(output)
    if decompress(packed) != (bytes(output), len(packed)):
        raise ValueError('Library PRS round-trip failed')
    report = {'version': version, 'kind': 'offline text component; not a playable disc',
              'source_sha256': hashlib.sha256(original).hexdigest(),
              'output_sha256': hashlib.sha256(output).hexdigest(),
              'source_decoded_size': len(original), 'output_decoded_size': len(output),
              'english_pool_start': pool_start, 'output_compressed_size': len(packed),
              'compressed_sha256': hashlib.sha256(packed).hexdigest(),
              'relocated_root_pointers': len(entries), 'physical_records': len(profiles),
              'rebuilt_condition_nodes': conditions, 'physical_rows': len(drafted),
              'validation': {'all_pointer_targets': 'pass', 'profile_metadata': 'unchanged',
                             'original_payload_bytes': 'unchanged', 'english_sections_and_conditions': 'pass',
                             'PRS_roundtrip': 'pass'},
              'pending': ['Disc integration and native capacity are tracked separately in library-patch-report.json',
                          'In-game layout and behavior checks'],
              'profiles': profiles}
    return bytes(output), packed, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    output, packed, report = build()
    print('D_PAPER: {} -> {} decoded bytes; {} compressed bytes.'.format(
        report['source_decoded_size'], len(output), len(packed)))
    print('{} root pointers, {} physical records, {} condition nodes verified.'.format(
        report['relocated_root_pointers'], report['physical_records'], report['rebuilt_condition_nodes']))
    print('Sample relocations:', json.dumps(report['profiles'][:3]))
    if not args.write:
        print('DRY RUN: no component written')
        return
    out = ROOT / 'work/output/0.1.3/text'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'D_PAPER.en.dec.bin').write_bytes(output)
    (out / 'D_PAPER.BIN').write_bytes(packed)
    (out / 'library-component-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Wrote offline library component; original game files unchanged.')


if __name__ == '__main__':
    main()
