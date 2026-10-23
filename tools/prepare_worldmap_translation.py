"""Link ten world-map image labels to glossary entries. Dry run first."""
import argparse
import json

from build_bitmap_font import ROOT, ATLAS, digest
from extract_worldmap_labels import analyze

DEST = ROOT / 'work/translation/en/ui/worldmap-labels.en.json'
LINKS = [
    (17, 'term.069', 'Flamuelk Castle'),
    (18, 'term.161', 'Shangria'),
    (19, 'term.153', 'Brandenkrois'),
    (20, 'place.wmap.belta', 'Belta'),
    (21, 'term.114', 'Glascher Valley'),
    (22, 'term.163', 'Alterias Valley'),
    (23, 'term.105', 'Muur Forest'),
    (24, 'term.421', 'Ze=Ode Research Institute Ruins'),
    (25, 'term.104', 'Cornel Village'),
    (26, 'term.008', 'Holy Land'),
]


def prepare():
    info, *_ = analyze()
    glossary = json.loads((ROOT / 'work/glossary/glossary.json').read_text('utf-8'))
    terms = {r['id']: r for r in glossary['entries']}
    rows = []
    for index, term_id, text in LINKS:
        term = terms[term_id]
        # Research-institute label uses title case and omits decorative quotes.
        expected = term['en'].replace('≪', '').replace('≫', '')
        assert expected.lower() == text.lower(), (term_id, expected, text)
        row = dict(info['rectangles'][index])
        row.update(en=text, glossary_id=term_id, glossary_en=term['en'])
        rows.append(row)
    return {'source': 'Original WMAP.AFS members 17/18',
            'source_archive_sha256': info['source_archive_sha256'],
            'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'),
            'font_sha256': digest(ATLAS.read_bytes()),
            'font_scale': 'Uniform 1/2 source scale, 12-pixel cell height, common baseline',
            'rows': rows,
            'notes': ['Belta is a provisional phonetic spelling from the image label.',
                      'Short image forms Muur Forest / Glascher Valley follow existing glossary locations.',
                      'No story or library draft credit; map layout and live selection remain to be verified.']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    data = prepare()
    print(json.dumps(data, indent=2))
    if not args.write:
        print('DRY RUN: no translation map written')
        return
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')
    print('Wrote', DEST)


if __name__ == '__main__':
    main()
