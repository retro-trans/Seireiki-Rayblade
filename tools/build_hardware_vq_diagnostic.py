"""Isolate runtime text compression for the reported Dreamcast transition. Dry first.

Diagnostic 0.7.24 only: preserves 0.7.23 assets and clipping, but reverts the
seven 0.7.22 compression spans. This is not a confirmed fix or public release.
"""
import argparse
import hashlib
import json
from pathlib import Path

from build_bitmap_font import ROOT
from build_stage6_text_fix import compose as codec_compose
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION, PRIOR = '0.7.24', '0.7.23'


def compose():
    current = (ROOT / 'work/output' / PRIOR / '1ST_READ.BIN').read_bytes()
    legacy = (ROOT / 'work/output/0.7.21/1ST_READ.BIN').read_bytes()
    compressed, proof = codec_compose()
    exe = bytearray(current)
    permitted = set()
    for row in proof['edits']:
        p, size = int(row['file_offset'], 16), row['bytes']
        assert current[p:p+size] == compressed[p:p+size]
        exe[p:p+size] = legacy[p:p+size]
        permitted.update(range(p, p+size))
    changed = {i for i, (a, b) in enumerate(zip(current, exe)) if a != b}
    assert changed and changed <= permitted
    # 0.7.23's newer clipping helper and all three selection-bar edits survive.
    for p, n in [(0x6bbac, 36), (0x6b7a4, 4), (0xe727, 1), (0xfddb, 1), (0xf056, 1)]:
        assert exe[p:p+n] == current[p:p+n]
    return bytes(exe), {'version': VERSION, 'source_build': PRIOR, 'release': False,
        'kind': 'Hardware diagnostic; not a confirmed fix',
        'reported_failure': 'Real Dreamcast, GDEMU, VGA; latest public 0.7.23 black after Clear 2 Next, music continues. User reports Flycast passes and 0.7.2 hardware passes.',
        'hypothesis': 'Isolate runtime text compression/upload behavior from all other 0.7.23 changes; no root cause is established.',
        'changed_bytes': len(changed), 'reverted_spans': proof['edits'],
        'source_executable_sha256': hashlib.sha256(current).hexdigest(),
        'executable_sha256': hashlib.sha256(exe).hexdigest(),
        'preserved': 'All 0.7.23 assets, Native Skies 1x glyphs, translation, VGA code, 640x480 rendering, battle coordinates, clipping and selection bars.',
        'known_diagnostic_regression': 'Disables the Stage 6 lossless text-memory repair. White/missing Stage 6 UI may return; this is only a controlled chapter-transition test.',
        'physical_Dreamcast_result': 'pending'}


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--write', action='store_true')
    ap.add_argument('--finish', action='store_true', help='Finish metadata after verifying the interrupted unpublished build.')
    a = ap.parse_args(); exe, proof = compose()
    print(json.dumps(proof, indent=2), flush=True)
    if not a.write:
        print('DRY RUN: no files written. A new local 0.7.24 diagnostic disc would be created.'); return
    base = ROOT / 'work/output' / PRIOR
    mode = json.loads((base / 'font-mode-details.json').read_text(encoding='utf-8'))
    archive = (base / 'WIN00.AFS').read_bytes()
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=proof['executable_sha256'])
    p, _ = font_plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    p[7].update(kind=proof['kind'], component_manifest_name='hardware-transition-component.json',
        readme_component_text='Hardware diagnostic only: runtime text compression disabled; Native Skies 1x and other 0.7.23 fixes retained.\n',
        pending=['Real Dreamcast GDEMU/VGA chapter-transition retest', proof['known_diagnostic_regression']])
    out = ROOT / 'work/output' / VERSION
    if not a.finish:
        write_plan(p, VERSION, PRIOR, {'1ST_READ.BIN': exe, 'WIN00.AFS': archive})
    else:
        from disc_inventory import Disc
        assert not (out / 'READ-ME.txt').exists(), 'Only finish an interrupted unpublished build.'
        report = json.loads((out / 'english-disc-report.json').read_text(encoding='utf-8'))
        assert report['version'] == VERSION and report['kind'] == proof['kind']
        assert report['validation']['changed_sector_EDC_ECC'] == 'pass'
        disc = Disc(out / 'disc' / f'Rayblade English Test {VERSION}.cue')
        entries = {r['path']: r for r in disc.inventory()}
        for name, raw in p[3].items():
            row = entries[name]; assert disc.read(row['lba'], row['size']) == raw, name
        assert (out / '1ST_READ.BIN').read_bytes() == exe
        report['component_manifest_name'] = p[7]['component_manifest_name']
        (out / 'english-disc-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (out / 'hardware-transition-diagnostic.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    (out / 'READ-ME.txt').write_text('Rayblade 0.7.24 HARDWARE DIAGNOSTIC ONLY\n\n'
        'For the reported GDEMU/VGA black screen after Clear 2 -> Next.\n'
        'This is an isolation test, not a confirmed fix.\n'
        'Keeps the Native Skies 1x font and all other 0.7.23 assets/fixes.\n'
        'Disables runtime text compression: the known Stage 6 text-memory problem can return.\n'
        'Cold-boot the GDI and use a normal VMU save. Do not use an emulator save state.\n'
        'Do not publish as a general update; original hardware confirmation is pending.\n', encoding='utf-8')
    print('PASS: isolated executable changes and full-disc preservation. Hardware confirmation is still required.', flush=True)


if __name__ == '__main__': main()
