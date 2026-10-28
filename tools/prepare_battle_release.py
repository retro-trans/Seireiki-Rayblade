"""Repackage verified 0.7.23 deltas with both public routes. Dry-run by default.

Never overwrites the delivered local packages or publishes to GitHub.
Prepare after committing sources, verify both routes, then seal the ZIPs.
"""
import argparse
import copy
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import Mock, patch
import zipfile

from build_bitmap_font import ROOT
from prepare_public_release import digest

VERSION = '0.7.23'
PREVIOUS = '0.7.11'
REPO = 'retro-trans/Seireiki-Rayblade'
OUT = ROOT / f'work/output/release-{VERSION}-public'
FULL = ROOT / f'work/output/release-{VERSION}/publish'
UPGRADE = ROOT / f'work/output/upgrade-{PREVIOUS}-to-{VERSION}/patches'
OLD = ROOT / f'work/output/release-{PREVIOUS}-public'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sums(directory):
    (directory / 'SHA256SUMS.txt').write_text(''.join(
        f'{digest(p)}  {p.name}\n' for p in sorted(directory.iterdir())
        if p.is_file() and p.name != 'SHA256SUMS.txt'), encoding='utf-8')


def preflight():
    from retro_trans.release import validate_directory
    full = validate_directory(FULL)
    upgrade = validate_directory(UPGRADE)
    assert full['version'] == upgrade['version'] == VERSION
    assert {p['source_version'] for p in full['patches']} == {'original'}
    assert {p['source_version'] for p in upgrade['patches']} == {PREVIOUS}
    assert len(full['patches']) == len(upgrade['patches']) == 3
    for left, right in zip(full['patches'], upgrade['patches']):
        assert left['edition'] == right['edition']
        assert (left['target_sha256'], left['target_bytes']) == (right['target_sha256'], right['target_bytes'])
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == VERSION
    print('PASS: six verified deltas; original and last-public 0.7.11 routes share exact targets.', flush=True)
    return full, upgrade


def instructions(upgrade=False):
    prefix = f'Rayblade-English-v{PREVIOUS}-to-v{VERSION}' if upgrade else f'Rayblade-English-v{VERSION}'
    descriptor = f'Seireiki Rayblade English v{PREVIOUS}.gdi' if upgrade else 'Seireiki Rayblade (Japan).cue'
    return f'''Seireiki Rayblade English {VERSION}
Input: {'exact public 0.7.11 five-track English GDI set' if upgrade else 'original Japanese T-42201M five-track BIN/CUE dump'}.
Retro Trans Tools 0.4.1+: refresh catalog, Automatic, select the complete input folder,
choose {VERSION}, Patch to a new folder. Keep source verification enabled.

Manual xdelta3 / DeltaPatcher route:
  Track 3 + {prefix}-Track03.xdelta -> Track 3 (same filename)
  Track 5 + {prefix}-Track05.xdelta -> Track 5 (same filename)
  {descriptor} + {prefix}-GDI.xdelta -> Seireiki Rayblade English v{VERSION}.gdi
Copy Tracks 1, 2 and 4 unchanged. Keep all five original track filenames.
The output folder must contain five BIN tracks and the new GDI.
{'Tracks 3 and the descriptor have identity deltas; Automatic can skip them.' if upgrade else 'The full ZIP also includes the separately named 0.7.11 upgrade deltas; use one matching route.'}
Check the supplied source/target hashes. Other local builds are not public upgrade inputs.
Fresh boot the new GDI; load a normal VMU save rather than an emulator save state.
Native Skies 1x only. No HD selector or emulator texture pack.
Read RELEASE-NOTES-v{VERSION}.txt for changes, credits and known limitations.
No game images are included. The patch is free; do not sell it.
'''


def prepare():
    full, upgrade = preflight()
    assert not OUT.exists(), 'Use a fresh public directory; never overwrite packages.'
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=ROOT, text=True).strip(), 'Commit reviewed source changes first.'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    directory = OUT / 'publish'
    directory.mkdir(parents=True)
    merged = copy.deepcopy(full)
    merged['source_commit'] = commit
    merged['patches'] += copy.deepcopy(upgrade['patches'])
    write(directory / 'BUILD-MANIFEST.json', merged)
    validation = {'schema_version': 1, 'manifest_sha256': digest(directory / 'BUILD-MANIFEST.json'),
                  'patches': read(FULL / 'VALIDATION.json')['patches'] + read(UPGRADE / 'VALIDATION.json')['patches']}
    write(directory / 'VALIDATION.json', validation)
    for source, manifest in ((FULL, full), (UPGRADE, upgrade)):
        for row in manifest['patches']:
            shutil.copyfile(source / row['patch'], directory / row['patch'])
    for source, name in ((FULL / 'SOURCE-HASHES.txt', f'SOURCE-HASHES-v{VERSION}.txt'),
                         (UPGRADE / 'SOURCE-HASHES.txt', f'UPGRADE-SOURCE-HASHES-v{PREVIOUS}.txt'),
                         (FULL / 'TARGET-HASHES.txt', f'TARGET-HASHES-v{VERSION}.txt'),
                         (ROOT / 'THIRD_PARTY_NOTICES.txt', 'THIRD_PARTY_NOTICES.txt'),
                         (ROOT / 'CHANGELOG.md', f'CHANGELOG-v{VERSION}.txt'),
                         (ROOT / f'docs/releases/v{VERSION}.md', f'RELEASE-NOTES-v{VERSION}.txt')):
        shutil.copyfile(source, directory / name)
    (directory / f'README-v{VERSION}.txt').write_text(instructions(), encoding='utf-8')
    (directory / f'README-UPGRADE-v{PREVIOUS}-to-v{VERSION}.txt').write_text(instructions(True), encoding='utf-8')
    sums(directory)
    from retro_trans.release import validate_directory
    validate_directory(directory)
    print('Prepared public assets pinned to', commit, flush=True)


def verify(rtt):
    from retro_trans.release import validate_directory
    from retro_trans.catalog import Catalog, recognize, apply_plan
    from retro_trans.core import GitHubClient
    gc.set_threshold(1, 1, 1)
    directory = OUT / 'publish'
    manifest = validate_directory(directory)
    assert len(manifest['patches']) == 6
    old = read(OLD / 'publish/BUILD-MANIFEST.json')
    def record(m):
        return {'repo': REPO, 'tag': 'v' + m['version'], 'manifest': m,
                'assets': {p['patch']: f'https://github.com/{REPO}/releases/download/v{m["version"]}/{p["patch"]}' for p in m['patches']}}
    cat = Catalog({'schema_version': 1, 'releases': [record(old), record(manifest)]})
    expected = read(ROOT / f'work/output/release-{VERSION}/game-validation.json')['output_hashes']
    results = {}
    for label, source, operations in (('original', ROOT, 3), ('upgrade', OLD / 'roundtrip-disc', 1)):
        recognized = recognize(source, cat)
        assert len(recognized) == 1 and not recognized[0].problems
        plan = cat.plan(recognized[0])
        assert len(plan.edges) == operations, plan.summary
        client = Mock()
        client.download.side_effect = lambda asset, *args: directory / asset.name
        print(label, plan.summary, flush=True)
        with patch.object(GitHubClient, 'open', side_effect=AssertionError('Unexpected network in local test')):
            result = apply_plan(source, OUT / f'roundtrip-{label}', plan, cat, client, OUT / 'cache')
        assert {p.name for p in result.iterdir()} == set(expected)
        for name, identity in expected.items():
            assert (result / name).stat().st_size == identity['bytes']
            assert digest(result / name) == identity['sha256'], name
        current = recognize(result, cat)
        assert len(current) == 1 and current[0].version == VERSION and not cat.plan(current[0]).edges
        route = [p for p in manifest['patches'] if p['source_version'] == ('original' if label == 'original' else PREVIOUS)]
        for p in route:
            name = ('Seireiki Rayblade (Japan).cue' if p['source_format'] == 'cue' else
                    f'Seireiki Rayblade English v{PREVIOUS}.gdi' if p['source_format'] == 'gdi' else
                    next(f['output_name'] for f in manifest['solutions'][0]['files'] if f['edition'] == p['edition']))
            assert digest(source / name) == p['source_sha256']
        for p in manifest['solutions'][0]['copy_files']:
            assert digest(source / p['name']) == p['sha256']
        results[label] = {'actual_Retro_Trans_Automatic': 'pass', 'operations': operations,
                          'all_six_files_exact': True, 'input_hashes_preserved': True, 'recognized_output': VERSION}
        print('PASS:', label, 'all six output files exact; source preserved.', flush=True)
    report = {'version': VERSION, 'source_commit': manifest['source_commit'],
              'retro_trans_source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=rtt, text=True).strip(),
              'routes': results, 'output_hashes': expected,
              'game_checks': read(ROOT / f'work/output/release-{VERSION}/game-validation.json'),
              'battle_clip_evidence': read(ROOT / 'docs/battle-clip.json'),
              'stage6_evidence': read(ROOT / 'docs/stage6-text.json')}
    write(directory / f'GAME-VALIDATION-v{VERSION}.json', report)
    sums(directory)
    validate_directory(directory)


def archive(directory, target):
    assert not target.exists()
    members = [p for p in sorted(directory.iterdir()) if p.is_file() and p.suffix != '.zip']
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in members:
            z.write(p, p.name)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        import hashlib
        for p in members:
            assert hashlib.sha256(z.read(p.name)).hexdigest() == digest(p)


def seal():
    from retro_trans.release import validate_directory
    directory = OUT / 'publish'
    manifest = validate_directory(directory)
    report = read(directory / f'GAME-VALIDATION-v{VERSION}.json')
    assert report['source_commit'] == manifest['source_commit']
    assert all(r['all_six_files_exact'] for r in report['routes'].values())
    upgrade = OUT / 'upgrade-zip-stage'
    upgrade.mkdir()
    m = copy.deepcopy(manifest)
    m['patches'] = [p for p in m['patches'] if p['source_version'] == PREVIOUS]
    write(upgrade / 'BUILD-MANIFEST.json', m)
    v = read(directory / 'VALIDATION.json')
    v['patches'] = [r for r in v['patches'] if r['patch'] in {p['patch'] for p in m['patches']}]
    v['manifest_sha256'] = digest(upgrade / 'BUILD-MANIFEST.json')
    write(upgrade / 'VALIDATION.json', v)
    for p in directory.iterdir():
        if p.suffix == '.xdelta' and p.name not in {r['patch'] for r in m['patches']}:
            continue
        if p.name in {'BUILD-MANIFEST.json', 'VALIDATION.json', 'SHA256SUMS.txt', f'SOURCE-HASHES-v{VERSION}.txt', f'README-v{VERSION}.txt'}:
            continue
        if p.is_file():
            shutil.copyfile(p, upgrade / p.name)
    sums(upgrade)
    validate_directory(upgrade)
    archive(directory, OUT / f'Rayblade-English-v{VERSION}-xdelta.zip')
    archive(upgrade, OUT / f'Rayblade-English-v{PREVIOUS}-to-v{VERSION}-upgrade.zip')
    for p in OUT.glob('*.zip'):
        shutil.copyfile(p, directory / p.name)
    sums(directory)
    validate_directory(directory)
    write(OUT / 'public-package-validation.json', {
        'version': VERSION, 'source_commit': manifest['source_commit'],
        'last_public_upgrade_from': PREVIOUS, 'canonical_manifest_patches': 6,
        'routes': report['routes'], 'ZIP_CRC_and_member_SHA256': 'pass',
        'assets': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(directory.iterdir())}})
    print('PASS: sealed full and upgrade ZIPs, checksums and canonical six-patch release.', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase', choices=('prepare', 'verify', 'seal'), default='prepare')
    ap.add_argument('--rtt', type=Path, required=True)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    sys.path.insert(0, str(a.rtt.resolve()))
    if not a.write:
        preflight()
        print('DRY RUN:', a.phase, 'under', OUT, '; original local packages remain unchanged.')
        print(instructions(True))
        return
    if a.phase == 'prepare':
        prepare()
    elif a.phase == 'verify':
        verify(a.rtt.resolve())
    else:
        seal()


if __name__ == '__main__':
    main()
