"""Package the exact text-filter delta over verified 0.1.21. Dry run first.

Previous native reports retain their actual tested version/hash. The only new
behavior is separately verified by test_text_filter; this does not relabel old
proofs as fresh 0.1.22 executions or weaken the ordinary full-build gates.
"""
import argparse
import json
import re
import shutil

import build_english_test_disc as full
from build_text_filter_patch import ROOT, VERSION, PRIOR, compose, digest
from build_test_disc import regenerate
from disc_inventory import Disc, SECTOR


def plan():
    files, manifest, component = compose()
    base = ROOT / 'work/output' / PRIOR
    out = ROOT / 'work/output' / VERSION
    assert (out / '1ST_READ.BIN').read_bytes() == files['1ST_READ.BIN']
    # Re-run the existing full packager's mandatory source/proof/capacity gates
    # against the actual prior build. It does not write in plan mode.
    full.VERSION = PRIOR
    _, _, prior_targets, prior_changes, _ = full.plan()
    previous_report = json.loads((base / 'english-disc-report.json').read_text('utf-8'))
    assert previous_report['validation']['changed_sector_EDC_ECC'] == 'pass'
    old_cue = base / 'disc' / f'Rayblade English Test {PRIOR}.cue'
    old = Disc(old_cue)
    inventory = {r['path']: r for r in old.inventory()}
    targets = dict(prior_targets)
    targets['1ST_READ.BIN'] = files['1ST_READ.BIN']
    for name, prior in prior_targets.items():
        row = inventory[name]
        assert old.read(row['lba'], row['size']) == prior
        candidate = out / (name if name in ('1ST_READ.BIN', 'WIN00.AFS', 'D_SCE.AFS') else 'text/' + name)
        assert candidate.read_bytes() == targets[name]
    raw = (out / 'text-filter-native-test.json').read_bytes()
    proof = json.loads(raw)
    stored = json.loads((out / 'font4x-patch.json').read_text('utf-8'))
    assert proof['executable_sha256'] == digest(targets['1ST_READ.BIN'])
    assert proof['component_sha256'] == digest((out / 'text-filter-component.json').read_bytes())
    assert stored['text_filter']['proof_sha256'] == digest(raw)
    assert proof['selection_encoder_cases'] == 72 and proof['caller_cases'] == 12
    assert proof['state_transitions'] == [[63, 1], [12, 0], [63, 1], [64, 0], [0, 0]]
    historical = []
    for p in sorted(base.glob('*test.json')):
        assert (out / p.name).read_bytes() == p.read_bytes()
        previous = json.loads(p.read_text('utf-8'))
        assert previous['executable_sha256'] == digest(prior_targets['1ST_READ.BIN'])
        historical.append({'file': p.name, 'tested_build': PRIOR, 'sha256': digest(p.read_bytes())})
    assert len(historical) == 13
    source = prior_targets['1ST_READ.BIN']
    target = targets['1ST_READ.BIN']
    row = inventory['1ST_READ.BIN']
    sectors = sorted({i // 2048 for i, (a, b) in enumerate(zip(source, target)) if a != b})
    changes = []
    for logical in sectors:
        lba = row['lba'] + logical
        track = next(t for t in old.tracks if t['start_lba'] <= lba < t['end_lba'])
        offset = (track['index'] + lba - track['start_lba']) * SECTOR
        with track['path'].open('rb') as fh:
            fh.seek(offset)
            original = fh.read(SECTOR)
        assert regenerate(original) == original
        patched = bytearray(original)
        lo = logical * 2048
        hi = min(lo + 2048, len(source))
        assert original[16:16 + hi - lo] == source[lo:hi]
        patched[16:16 + hi - lo] = target[lo:hi]
        changes.append((track['path'].name, offset, regenerate(patched)))
    assert len(changes) == 2
    names = re.findall(r'FILE "(.+)" BINARY', old_cue.read_text('utf-8'))
    assert len(names) == 5
    report = {
        'version': VERSION, 'source_build': PRIOR,
        'kind': 'local native text-filter comparison over the prior English test disc',
        'new_changed_sectors': len(changes),
        'total_changed_sector_locations_from_original': len({(str(n), off) for n, off, _ in prior_changes} | {(str(n), off) for n, off, _ in changes}),
        'changed_executable_bytes': component['changed_executable_bytes'],
        'files': {n: {'size': len(b), 'sha256': digest(b)} for n, b in targets.items()},
        'text_filter_native_validation': proof,
        'historical_native_evidence': historical,
        'prior_build_gates': 'Existing full packager plan rerun against 0.1.21; all mandatory component/proof/capacity gates pass',
        'evidence_scope': 'Only selector/filter command path is freshly executed; other reports retain their actual 0.1.21 hashes and coverage. Complete candidate differs only in two verified ranges.',
        'pending': ['Live GPU filtering/blending and appearance', 'Held passages and independent meaning review',
                    'Remaining image/movie text and full-game validation'],
    }
    return old, old_cue, targets, changes, names, report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    old, cue, targets, changes, names, report = plan()
    print('PASS: prior full-build gates, 13 exact historical reports, fresh filter proof and two sector deltas.', flush=True)
    if not args.write:
        print('DRY RUN: no disc written')
        return
    folder = ROOT / 'work/output' / VERSION / 'disc'
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(cue.parent / name, folder / name)
    for name, offset, raw in changes:
        with (folder / name).open('r+b') as fh:
            fh.seek(offset)
            fh.write(raw)
    title = f'Rayblade English Test {VERSION}'
    target_cue = folder / (title + '.cue')
    target_cue.write_bytes(cue.read_bytes())
    (folder / (title + '.gdi')).write_bytes((cue.parent / f'Rayblade English Test {PRIOR}.gdi').read_bytes())
    shutil.copyfile(folder.parent / 'FONT-LICENSE.txt', folder / 'FONT-LICENSE.txt')
    finished = Disc(target_cue)
    assert old.inventory() == finished.inventory()
    entries = {r['path']: r for r in finished.inventory()}
    for name, expected in targets.items():
        row = entries[name]
        assert finished.read(row['lba'], row['size']) == expected
    # Full byte comparison of every track, substituting exactly the two allowed
    # raw sectors into the prior stream. This covers all unrelated disc bytes.
    verified_bytes = 0
    for name in names:
        edits = [(offset, raw) for n, offset, raw in changes if n == name]
        with (cue.parent / name).open('rb') as a, (folder / name).open('rb') as b:
            position = 0
            while True:
                before = bytearray(a.read(4 * 1024 * 1024))
                after = b.read(len(before))
                if not before:
                    assert not b.read(1)
                    break
                for offset, raw in edits:
                    lo = max(offset, position)
                    hi = min(offset + len(raw), position + len(before))
                    if lo < hi:
                        before[lo - position:hi - position] = raw[lo - offset:hi - offset]
                assert before == after, (name, position)
                verified_bytes += len(before)
                position += len(before)
    for name, offset, expected in changes:
        with (folder / name).open('rb') as fh:
            fh.seek(offset)
            actual = fh.read(SECTOR)
        assert actual == expected and regenerate(actual) == actual
    report['validation'] = {
        'reextracted_files': 'all 5 exact', 'changed_sector_EDC_ECC': 'pass',
        'unrelated_ISO_entries': 'unchanged', 'unrelated_track_bytes': 'all unchanged',
        'track_bytes_compared': verified_bytes, 'in_game': 'pending',
    }
    (folder.parent / 'english-disc-report.json').write_text(json.dumps(report, indent=2) + '\n', 'utf-8')
    (folder.parent / 'READ-ME.txt').write_text(
        title + '\n\nOpen disc/' + title + '.gdi in Flycast.\n'
        'Native bilinear filtering now applies only to dynamic text sprites.\n'
        'Font pixels, spacing, all translations and image resources are unchanged from 0.1.21.\n'
        'Fresh native filter selection/command checks pass; previous tests retain their historical coverage.\n'
        'Live appearance is unverified. Held text, review and full-game validation remain incomplete.\n'
        'Local comparison build; no release.\n', 'utf-8')
    print('PASS: all five files exact, two valid sector changes and all unrelated track bytes preserved.', flush=True)
    print(folder / (title + '.gdi'))


if __name__ == '__main__':
    main()
