"""Create optional 0.7.23 DCP packages using the pinned UDP engine. Dry first.

The existing xdelta release is immutable. This tool neither uploads nor publishes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from build_bitmap_font import ROOT

VERSION = '0.7.23'
PREVIOUS = '0.7.11'
OUT = ROOT / 'work/output/dcp-0.7.23'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rtt', type=Path, required=True)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--seal', action='store_true', help='Refresh verification comments on unpublished local packages only.')
    a = ap.parse_args()
    sys.path.insert(0, str(a.rtt.resolve()))
    from retro_trans import dcp
    trees = {label: read(OUT / (label + '-tree.json')) for label in ('original', 'target', 'previous')}
    assert all(len(v['files']) == 141 for v in trees.values())
    target = trees['target']['files']
    assert target['1ST_READ.BIN']['sha256'] == '6899e263653b1a29de45ee7bf04778e1ad240c40a99763511bd2da7ce9abbffe'
    print('Target game filesystem:', dcp.tree_hash(target), flush=True)
    plans = []
    for label, source_version, name in (
        ('original', 'original', f'Rayblade-English-v{VERSION}.dcp'),
        ('previous', PREVIOUS, f'Rayblade-English-v{PREVIOUS}-to-v{VERSION}-upgrade.dcp')):
        changes = [n for n, v in target.items() if trees[label]['files'].get(n) != v]
        print(source_version, '->', VERSION, ':', len(changes), 'modified files including boot sector; one DCP.', flush=True)
        plans.append((label, source_version, name))
    if not a.write:
        print('DRY RUN:', 'seal verification comments' if a.seal else 'build two new packages', 'under', OUT / 'publish'); return
    directory = OUT / 'publish'
    if not a.seal: directory.mkdir()
    prior = {p['asset']: p['native_builder'] for p in read(OUT / 'build-validation.json')['packages']} if a.seal else {}
    records = []
    for label, source_version, name in plans:
        path = directory / name
        built = prior[name] if a.seal else dcp.run('build', {'source': trees[label]['gdi'], 'target': trees['target']['gdi'],
                                'output': str(path)}, OUT / ('build-' + label))
        metadata = {'retro_trans_dcp': 1, 'game_id': 'seireiki-rayblade', 'source_version': source_version,
                    'version': VERSION, 'source_tree_sha256': dcp.tree_hash(trees[label]['files']),
                    'target_tree_sha256': dcp.tree_hash(target), 'game_files': 140,
                    'engine': 'Universal Dreamcast Patcher 2.1.8',
                    'upstream_commit': dcp.UPSTREAM, 'font': 'Native Skies 1x only'}
        ip = bytearray((OUT / 'inspect-v4-target/files/bootsector/IP.BIN').read_bytes())
        assert ip[0x100:0x104] == b'TOC1'
        ip[0x104:0x110] = bytes(12)
        metadata['bootsector_invariant_sha256'] = hashlib.sha256(ip).hexdigest()
        with zipfile.ZipFile(path, 'a') as z:
            z.comment = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
            assert z.testzip() is None
        validation = dcp.inspect_patch(path)
        assert validation['metadata'] == metadata
        records.append({'asset': name, 'bytes': path.stat().st_size,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'metadata': metadata, 'native_builder': built})
        print('Built', name, path.stat().st_size, 'bytes', flush=True)
    (OUT / 'build-validation.json').write_text(json.dumps({'version': VERSION, 'packages': records}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()
