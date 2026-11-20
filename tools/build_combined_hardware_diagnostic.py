"""0.7.26: stock video plus uncompressed Native uploads. Dry by default.

This tests the combination of the earlier independent 0.7.24/0.7.25 changes.
It is a local hardware diagnostic, not a confirmed fix or public release.
"""
import argparse
import json
from pathlib import Path

from build_bitmap_font import ROOT, digest
from build_legacy_video_diagnostic import compose as video_compose, check as video_check
from build_hardware_vq_diagnostic import compose as uncompressed_compose

VERSION, PRIOR = '0.7.26', '0.7.25'


def compose():
    video, video_proof = video_compose()
    uncompressed, upload_proof = uncompressed_compose()
    public = (ROOT / 'work/output/0.7.23/1ST_READ.BIN').read_bytes()
    assert video == (ROOT / 'work/output/0.7.25/1ST_READ.BIN').read_bytes()
    assert uncompressed == (ROOT / 'work/output/0.7.24/1ST_READ.BIN').read_bytes()
    exe = bytearray(video)
    for row in upload_proof['reverted_spans']:
        p, size = int(row['file_offset'], 16), row['bytes']
        assert video[p:p+size] == public[p:p+size], hex(p)
        exe[p:p+size] = uncompressed[p:p+size]
    changed = [i for i, (a, b) in enumerate(zip(video, exe)) if a != b]
    assert len(changed) == 705
    assert sum(a != b for a, b in zip(public, exe)) == 889
    # No intervening code/asset or font-selector rollback is permitted.
    permitted = {i for row in upload_proof['reverted_spans']
                 for i in range(int(row['file_offset'], 16), int(row['file_offset'], 16)+row['bytes'])}
    assert set(changed) <= permitted
    assert exe[0x10150:0x10154] == video[0x10150:0x10154]
    return bytes(exe), {
        'version': VERSION, 'date': '2026-11-01', 'source_build': PRIOR,
        'public_release': False, 'hardware_fix_confirmed': False,
        'kind': 'Combined stock-video and uncompressed-text hardware diagnostic',
        'source_executable_sha256': digest(video), 'executable_sha256': digest(exe),
        'changed_bytes_from_0725': 705, 'changed_bytes_from_public_0723': 889,
        'video': video_proof['rendering'],
        'upload': 'Restore the seven pre-0.7.22 upload/allocation/admission spans; no runtime VQ encoder is used.',
        'reverted_upload_spans': upload_proof['reverted_spans'],
        'font': 'Exact existing single Native Skies 1x bank; no HD bank or selector.',
        'other_assets': 'All fourteen non-executable payloads remain byte-exact 0.7.25/0.7.23.',
        'purpose': 'Test the combination of changes previously tested separately in 0.7.24 and 0.7.25. No individual cause is established.',
        'known_limitations': [
            'Stage 6 text-memory repair is disabled; missing/white text can return.',
            'Stock 320x240 rendering can reduce apparent font sharpness.',
            'Real Dreamcast compatibility is unconfirmed until tested.',
        ],
        'distribution': 'Full DCP from original Japanese image only; no upgrade patch.',
    }


def check(exe):
    from build_font4x_patch import SMALL, MEDIUM
    from build_map_font_patch import member
    from test_font4x_patch import HDCPU
    from test_outline_font import legacy_mask, expected_pixels
    font = member((ROOT / 'work/output/0.7.25/WIN00.AFS').read_bytes(), 0)
    assert len(font) == 99072
    assert digest(font) == '1b909b7fc3e2755a74f2d2da5dbc0b9b67dad90d31eb808ad5ed016adb71820e'
    proof = video_check(exe)
    proof['version'] = VERSION
    cases = steps = 0
    for small, chars in ((True, SMALL), (False, MEDIUM)):
        for i, ch in enumerate(chars):
            for background in (0, 128):
                flags = (64 if small else 0) | background
                cpu = HDCPU(exe, font, i+32 if small else i, flags, w=64, h=32, ex=1, ey=1)
                mask = legacy_mask(font, ch, small)
                if ch.isascii():
                    mask = mask[:, :32]
                expected = expected_pixels(cpu, mask, flags, 12, 4, shadow_pixels=1)
                steps += cpu.run_until(limit=300000)
                assert cpu.regions[3][1] == expected, (small, ch, background)
                assert cpu.read(0x8c1f36b6, 2) == 12+font[(0x20 if small else 0xa0)+i]
                cases += 1
    labels = json.loads((ROOT / 'work/output/0.7.25/font-mode-details.json').read_text('utf-8'))['labels']
    cpu = HDCPU(exe, font)
    allocations = []
    for slot, (w, h) in enumerate(((256,128), (256,128), (128,128), (128,128))):
        context = 0x8c1f0d3c + slot*92
        cpu.reg[8] = context
        cpu.write(context+10, w, 2); cpu.write(context+12, h, 2)
        cpu.pc = labels['allocate']; steps += cpu.run_until()
        pointer = cpu.reg[0]; cpu.write(context, pointer, 4)
        assert cpu.read(pointer+12, 1) == cpu.read(pointer+13, 1) == 1
        assert cpu.read(pointer+20, 4) == w*h*8
        allocations.append({'logical': [w,h], 'physical': [w*2,h*2], 'pixel_bytes': w*h*8})
    proof.update(native_font_cases=cases, native_font_bank_sha256=digest(font),
                 native_font_instructions=steps, sequential_status_allocations=allocations,
                 scope='Native VGA/movie/geometry arithmetic, Native glyph pixels/advances and uncompressed surface allocations. No physical hardware pass claimed.')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    exe, report = compose()
    print(json.dumps(report, indent=2), flush=True)
    if not args.write:
        print('DRY RUN: no files written.'); return
    proof = check(exe)
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    base = ROOT / 'work/output' / PRIOR
    mode = json.loads((base / 'font-mode-details.json').read_text('utf-8'))
    mode.update(version=VERSION, source_build=PRIOR, executable_sha256=digest(exe),
                runtime_text_compression=False, output_resolution=[320,240], VGA_scanout=[640,480])
    archive = (base / 'WIN00.AFS').read_bytes()
    planned, _ = plan(compose_fn=lambda: (exe, archive, b'', {}, mode), prior=PRIOR, version=VERSION)
    planned[7].update(kind=report['kind'], component_manifest_name='combined-hardware-component.json',
                      readme_component_text=report['kind']+'\n',
                      proof_scope=proof['scope'],
                      pending=['Real Dreamcast / GDEMU / VGA cold boot, New Game and Clear 2 -> Next', *report['known_limitations']])
    write_plan(planned, VERSION, PRIOR, {'1ST_READ.BIN': exe})
    out = ROOT / 'work/output' / VERSION
    for name, value in (('combined-hardware-diagnostic.json', report),
                        ('combined-hardware-native-test.json', proof), ('font-mode-details.json', mode)):
        (out/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    update_manifest(out, report, planned[7]['files'])
    (out/'READ-ME.txt').write_text('Rayblade 0.7.26 HARDWARE DIAGNOSTIC ONLY\n\n'
        'Stock video plus uncompressed text uploads. Single unchanged Native font bank.\n'
        'Not a confirmed fix. Stage 6 missing/white text can return.\n'
        'Use the full DCP on the original Japanese image, choose GDI for GDEMU, and cold boot.\n'
        'Test New Game, then separately normal Clear 2 VMU save -> Next.\n'
        'No upgrade patch and no public release.\n', encoding='utf-8')
    print('PASS: native checks and complete disc preservation.', flush=True)


def update_manifest(out, report, files):
    path = out/'font4x-patch.json'
    manifest = json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION, previous_build=PRIOR,
                    status='Native-only hardware diagnostic; hardware result pending',
                    current_payload_identities=files,
                    hardware_diagnostic=report,
                    historical_component_reports='Inherited reports retain their actual tested identities; current diagnostic/native report overrides runtime video and upload behavior.')
    manifest['files']['1ST_READ.BIN']['target_sha256'] = report['executable_sha256']
    path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
