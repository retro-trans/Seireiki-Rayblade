"""Prepare v0.7.2 Retro Trans configuration or extras; dry first."""
import argparse
import json
import subprocess
from pathlib import Path
from prepare_public_release import ROOT, config, digest

VERSION = '0.7.2'
BASE = ROOT / 'work/output' / VERSION
OUT = ROOT / 'work/output' / ('release-' + VERSION)


def extras():
    directory = OUT / 'publish'
    manifest = json.loads((directory / 'BUILD-MANIFEST.json').read_text('utf-8'))
    assert manifest['version'] == VERSION
    automatic = json.loads((OUT / 'game-validation.json').read_text('utf-8'))
    assert automatic['real_automatic_solution_application'] == 'pass'
    assert automatic['source_commit'] == manifest['source_commit']
    proof = json.loads((BASE / 'original-movies-validation.json').read_text('utf-8'))
    vga = json.loads((ROOT / 'docs/vga-support.json').read_text('utf-8'))
    assert proof['version'] == VERSION and proof['unchanged_non_movie_payloads'] == 12
    assert proof['files']['1ST_READ.BIN']['sha256'] == vga['executable_sha256']
    automatic['original_movies'] = proof
    automatic['vga_integration'] = vga
    source, target = [], []
    private = config(manifest['source_commit'], VERSION, BASE)
    solution = manifest['solutions'][0]
    for row, local in zip(manifest['patches'], private['patches']):
        assert digest(Path(local['source'])) == row['source_sha256']
        assert digest(Path(local['target'])) == row['target_sha256']
        source.append(row['source_sha256'] + '  ' + Path(local['source']).name)
        name = next(c['output_name'] for c in solution['files'] if c['edition'] == row['edition'])
        target.append(row['target_sha256'] + '  ' + name)
    for row in solution['copy_files']:
        assert digest(ROOT / row['name']) == row['sha256']
        line = row['sha256'] + '  ' + row['name']
        source.append(line)
        target.append(line)
    return {
        f'README-v{VERSION}.txt': (ROOT / 'README.md').read_bytes(),
        f'CHANGELOG-v{VERSION}.txt': (ROOT / 'CHANGELOG.md').read_bytes(),
        f'SOURCE-HASHES-v{VERSION}.txt': ('\n'.join(source) + '\n').encode(),
        f'TARGET-HASHES-v{VERSION}.txt': ('\n'.join(target) + '\n').encode(),
        f'GAME-VALIDATION-v{VERSION}.json': (json.dumps(automatic, indent=2) + '\n').encode(),
        'THIRD_PARTY_NOTICES.txt': (ROOT / 'THIRD_PARTY_NOTICES.txt').read_bytes(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extras', action='store_true')
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    if args.extras:
        files = extras()
        print('Plan:', len(files), 'documentation/hash/proof extras; refresh all-asset checksums.')
        if not args.write:
            print('DRY RUN: no assets written.')
            return
        directory = OUT / 'publish'
        for name, raw in files.items():
            assert not (directory / name).exists(), 'Do not overwrite release extras'
            (directory / name).write_bytes(raw)
        checksums = [digest(p) + '  ' + p.name for p in sorted(directory.iterdir()) if p.name != 'SHA256SUMS.txt']
        (directory / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', 'utf-8')
        return
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    value = config(commit, VERSION, BASE)
    report = json.loads((BASE / 'english-disc-report.json').read_text('utf-8'))
    assert report['validation']['reextracted_files'] == 'all 14 exact'
    assert report['validation']['unrelated_track_bytes'] == 'all unchanged'
    for row in value['patches']:
        assert Path(row['source']).is_file() and Path(row['target']).is_file()
    print('Plan: three original-input deltas; copy Tracks 1/2/4; complete five-track/GDI solution.')
    print('Source commit:', commit)
    if not args.write:
        print('DRY RUN: no config written.')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / 'release-local.json'
    assert not destination.exists()
    destination.write_text(json.dumps(value, indent=2) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
