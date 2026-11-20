"""Read-only audit of the failed 0.7.25 hardware diagnostic. Dry by default.

--write saves derived evidence only. No game image or patch is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/output/dcp-0.7.25-diagnostic'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check():
    packages, bootsectors = [], []
    for path in sorted((OUT / 'packages').glob('*.dcp')):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            boot = archive.read('bootsector/IP.BIN')
            meta = json.loads(archive.comment)
        assert len(boot) == 32768 and boot[0x3d:0x3e] == b'1'
        assert meta['version'] == '0.7.25' and meta['diagnostic']
        bootsectors.append(boot)
        packages.append({'name': path.name, 'sha256': sha(path.read_bytes()),
                         'bootsector_sha256': sha(boot),
                         'hardware_flags': boot[0x38:0x40].decode('ascii'),
                         'VGA_flag': boot[0x3d:0x3e].decode('ascii')})
    assert len(packages) == 2 and bootsectors[0] == bootsectors[1]
    routes = {}
    for label in ('original', 'previous'):
        receipt = json.loads((OUT / (label + '-apply-validation.json')).read_text('utf-8'))
        actual = {}
        for name, identity in receipt['output_files'].items():
            path = OUT / ('roundtrip-' + label) / name
            with path.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            actual[name] = {'bytes': path.stat().st_size, 'sha256': digest}
            assert actual[name] == identity, (label, name)
        with (OUT / ('roundtrip-' + label) / 'track03.bin').open('rb') as source:
            boot = b''.join(source.read(2352)[16:2064] for _ in range(16))
        changed = [i for i, (a, b) in enumerate(zip(bootsectors[0], boot)) if a != b]
        assert all(0x104 <= i < 0x110 for i in changed)
        normalized = bytearray(boot)
        normalized[0x104:0x110] = bytes(12)
        assert sha(normalized) == receipt['bootsector_invariant_sha256']
        routes[label] = {'freshly_verified_output_files': actual,
                         'bootsector_sha256': sha(boot),
                         'hardware_flags': boot[0x38:0x40].decode('ascii'),
                         'bootsector_changes_from_patch': [hex(i) for i in changed],
                         'changes_limited_to_rebuilt_track_table': True}
        print('Verified complete disc:', label, flush=True)
    assert routes['original'] == routes['previous']
    images = {v: (ROOT / 'work/output' / v / '1ST_READ.BIN').read_bytes()
              for v in ('0.7.2', '0.7.11', '0.7.24', '0.7.25')}
    baseline, current = images['0.7.2'], images['0.7.25']
    differences = [i for i, (a, b) in enumerate(zip(baseline, current)) if a != b]
    groups = []
    for offset in differences:
        if groups and offset - groups[-1][-1] <= 16:
            groups[-1].append(offset)
        else:
            groups.append([offset])
    assert len(differences) == 2823
    assert current[0xda5c0:0xda7b5] == baseline[0xda5c0:0xda7b5]
    return {
        'date': '2026-11-01', 'version': '0.7.25', 'hardware_fix_confirmed': False,
        'reported_hardware': 'Real Dreamcast / GDEMU / VGA',
        'reported_full_result': 'Freezes when leaving menus to start any mission and when launching the game; font appearance differs.',
        'reported_upgrade_result': 'Tester describes no VGA support and a freeze on the memory-card screen while loading or starting New Game.',
        'report_clarification': 'User confirms VGA cable; exact patching application, output format, rejection message and hashes of tester output remain unavailable.',
        'patches': packages, 'routes': routes,
        'full_and_upgrade_rebuilt_disc_files_byte_identical': True,
        'working_072_executable_sha256': sha(baseline),
        '0725_executable_sha256': sha(current),
        '0725_stock_VGA_commit_exact_072': True,
        '0725_remaining_changed_executable_bytes_vs_072': len(differences),
        '0725_remaining_changed_executable_spans': [
            {'start': hex(g[0]), 'end_exclusive': hex(g[-1]+1), 'changed_bytes': len(g)}
            for g in groups],
        'assessment': [
            '0.7.25 is unsuccessful on the reporting hardware. Reverting the video boundary alone was insufficient.',
            'The two supplied DCP routes have identical VGA-enabled boot code and rebuild identical complete disc files with the pinned upstream engine.',
            'This establishes local package identities only; it does not establish what the tester applied or exclude a different output/conversion path.',
            '0.7.25 is not a complete 0.7.2 rollback: 2,823 executable bytes and multiple asset changes remain. Their interactions are not excluded.',
            '0.7.11 already fails with both font choices; changing the font selection alone and the later codec-only rollback did not resolve the reports.',
            'A black screen does not by itself distinguish a video-output failure, blocked file read, CPU exception or graphics wait.',
        ],
        'next_required_evidence': [
            'Identify the tester output format/application and compare actual generated files with this receipt, to resolve the reported full/upgrade difference.',
            'Narrow the earliest failing runtime/assets against the known-working 0.7.2 without restoring HD mode in a new game build.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = check()
    print(json.dumps({k: report[k] for k in ('hardware_fix_confirmed',
          'full_and_upgrade_rebuilt_disc_files_byte_identical',
          '0725_remaining_changed_executable_bytes_vs_072')}, indent=2), flush=True)
    if args.write:
        path = ROOT / 'work/output/hardware-transition/0725-follow-up-audit.json'
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('Saved evidence:', path, flush=True)


if __name__ == '__main__':
    main()
