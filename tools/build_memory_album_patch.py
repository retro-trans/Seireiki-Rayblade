"""Build compact memory-card wording and high-detail album captions. Dry first."""
import argparse
import json
from functools import lru_cache

from build_album_caption_overlay import ROOT, OUT, VERSION, PRIOR, compose as album, digest
from build_names_translation import compose as names_compose


@lru_cache(maxsize=1)
def compose():
    archive, exe, component, outputs, pages, photos = album()
    base = ROOT / 'work/output' / PRIOR
    recipe = json.loads((base / 'ui-layouts.en.json').read_text('utf-8'))
    rows = {r['id']: r for r in json.loads((ROOT / 'work/translation/en/ui/names.json').read_text('utf-8'))}
    changes = {
        192: 'Select a memory card slot to save to.',
        193: 'Select a memory card slot to load from.',
        194: 'No memory card is inserted in this slot.',
        210: 'Port A - Slot 1', 211: 'Port A - Slot 2',
        219: 'No memory card is inserted in this slot.<NL>Saving requires at least 8 free blocks.',
        223: '<NL>'.join(f'Port {port} - Slot {slot}' for port in 'ABCD' for slot in (1, 2)),
    }
    for index, text in changes.items():
        key = f'names.g00.{index:03d}'
        row = rows[key]
        recipe['rows'][key] = {'en': text, 'source_sha256': row['source_sha256'],
            'prior_en_sha256': digest(row['en'].encode()),
            'reason': 'Compact slot wording fits existing memory-card boxes; port, slot, action and block requirement retained'}
    decoded, packed, names_report = names_compose(overrides=recipe['rows'], version=VERSION)
    capacity = len((base / 'text/D_NAMES.BIN').read_bytes())
    assert len(packed) <= capacity
    padded = packed + bytes(capacity - len(packed))
    recipe.update(version=VERSION, previous_build=PRIOR)
    component.update(names_packed_sha256=digest(padded), names_decoded_sha256=digest(decoded),
        names_stream_bytes=len(packed), names_file_bytes=len(padded), names_zero_tail_bytes=capacity-len(packed),
        memory_card_changes={f'names.g00.{i:03d}': text for i, text in changes.items()})
    return {'1ST_READ.BIN': exe, 'ALBUM.AFS': archive, 'D_NAMES.BIN': padded}, decoded, recipe, component, names_report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    files, decoded, recipe, report, names = compose()
    print(json.dumps({'version': VERSION, 'memory_card_changes': report['memory_card_changes'],
        'captions': report['captions'], 'caption_dimensions': report['caption_texture_dimensions'],
        'names_bytes': len(decoded), 'names_stream_bytes': report['names_stream_bytes'],
        'names_padding': report['names_zero_tail_bytes']}, indent=2))
    if not args.write:
        print('DRY RUN: no files written'); return
    OUT.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (OUT / name).write_bytes(raw)
    (OUT / 'D_NAMES.en.dec.bin').write_bytes(decoded)
    for name, value in [('component-report.json', report), ('names-component-report.json', names), ('ui-layouts.en.json', recipe)]:
        (OUT / name).write_text(json.dumps(value, indent=2) + '\n', 'utf-8')


if __name__ == '__main__': main()
