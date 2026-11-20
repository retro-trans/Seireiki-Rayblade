"""Verify the complete 0.7.34 original-input candidate; write records with --write."""
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    before, after = [ROOT/'work/output'/v for v in ('0.7.23', '0.7.34')]
    old, new = [(p/'1ST_READ.BIN').read_bytes() for p in (before, after)]
    report = read(after/'hardware-catchup-component.json')
    changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    spans = [(int(a, 16), int(b, 16)) for a, b in report['allowed_spans']]
    assert len(old) == len(new) and len(changed) == 99
    assert set(changed) <= {i for a, b in spans for i in range(a, b)}
    assert sha(after/'1ST_READ.BIN') == report['executable_sha256']
    assert new[0x8d60:0x9000] == old[0x8d60:0x9000]  # Adjacent Stage 6 encoder.
    a, b = [read(p/'english-disc-report.json') for p in (before, after)]
    assert set(a['files']) == set(b['files']) and len(b['files']) == 15
    assert [n for n in b['files'] if a['files'][n] != b['files'][n]] == ['1ST_READ.BIN']
    for name in b['files']:
        if name == '1ST_READ.BIN':
            continue
        relative = 'text/'+name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name
        assert (before/relative).read_bytes() == (after/relative).read_bytes(), name
    reference = (ROOT/'work/output/0.7.33/1ST_READ.BIN').read_bytes()
    shared = [(0x6b900, 0x6b918), (0x6b940, 0x6b998), (0xc234e, 0xc2356),
              (0xc24b4, 0xc24b8), (0x360c8, 0x360cc), (0xac2e4, 0xac3f4),
              (0x9c690, 0x9c694), (0x2a150, 0x2a158)]
    for lo, hi in shared:
        assert new[lo:hi] == reference[lo:hi]
    assert reference[0x10cb0:0x10cb4] == bytes.fromhex('04e531e4')
    assert new[0x10cb0:0x10cb4] == bytes.fromhex('00e531e4')
    mode = read(after/'font-mode-details.json')
    assert mode['native_only'] and mode['font_banks'] == 1 and mode['font_member_bytes'] == 99072
    assert {'HD font bank', 'Title X/Y font selector, labels and state'} <= set(mode['removed'])
    from build_map_font_patch import member
    font = member((after/'WIN00.AFS').read_bytes(), 0)
    assert len(font) == 99072
    assert hashlib.sha256(font).hexdigest() == mode['native_bank_sha256']
    native = read(after/'hardware-catchup-native-test.json')
    assert native['executable_sha256'] == report['executable_sha256']
    assert native['alignment']['strict_alignment_cases'] == 674
    assert len(native['alignment']['legacy_fault_witnesses']) == 3
    assert native['original_map_contexts']['cases'] == 126
    assert native['font']['Native_glyph_cases'] == 402
    assert native['font']['Native_bank_sha256'] == mode['native_bank_sha256']
    for name in ('target', 'clip', 'grid', 'stage6_text'):
        assert native[name]['executable_sha256'] == report['executable_sha256']
    assert native['target']['SDK_raw_packet_cases'] == 32
    assert native['target']['SDK_emitted_packets'] == 256
    assert [len(native['clip'][k]) for k in ('clip_cases', 'selection_cases', 'line_cases')] == [18, 3, 20]
    grid = native['grid']
    assert len(grid['actual_game_fill_cases']) == 4 and grid['adapter_fixtures'] == 5
    assert all(r['filled_tiles'] == 41 and r['vertices'] == 492 and r['all_xy_exactly_doubled']
               for r in grid['actual_game_fill_cases'])
    codec = native['stage6_text']
    assert codec['SDK_admission_cases'] == 48 and all(r['lossless'] for r in codec['encoder_cases'])
    assert [r['result'] for r in codec['actual_failed_Stage6_SDK_allocation_cases']] == [3, 0]
    assert codec['append_reencoding'] == 'exact' and codec['upload_worker_pointer_count_resume_ABI'] == 'pass'
    package = ROOT/'work/output/dcp-0.7.34-diagnostic'
    bundle = read(package/'bundle-validation.json')
    proof = read(package/'original-apply-validation.json')
    build = read(package/'build-validation.json')
    previous = read(ROOT/'work/output/dcp-0.7.23/target-tree.json')
    target = read(package/'target-tree.json')
    assert len(target['files']) == 141 and set(target['files']) == set(previous['files'])
    assert [n for n in target['files'] if previous['files'][n] != target['files'][n]] == ['1ST_READ.BIN']
    assert sha(package/bundle['asset']) == bundle['sha256']
    assert sha(package/'packages'/build['asset']) == build['sha256']
    assert build['metadata']['full_feature_catchup'] and build['metadata']['source_version'] == 'original'
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    assert proof['verified_game_tree_sha256'] == bundle['game_tree_sha256'] == build['metadata']['target_tree_sha256']
    assert proof['bootsector_invariant_sha256'] == target['bootsector_invariant_sha256'] == bundle['bootsector_invariant_sha256']
    assert bundle['original_only'] and bundle['VGA_boot_flag'] == '1' and not bundle['public_release']
    result = {**report, 'all_14_other_modified_payloads_exact_0_7_23': True,
              'all_140_game_files_and_boot_compared_to_latest': True,
              'only_executable_differs_from_latest': True,
              'complete_WIN00_exact_latest': True,
              'shared_0_7_33_repair_spans_exact': [[hex(a), hex(b)] for a, b in shared],
              'adjacent_Stage6_encoder_preserved': True,
              'native_validation': native, 'disc_validation': b['validation'],
              'DCP': dict(bundle, path=str((package/bundle['asset']).relative_to(ROOT)).replace('\\', '/')),
              'hardware_status': 'Not yet tested on the reporting Dreamcast. Synthetic alignment fault is confirmed; actual hang causality and full-feature compatibility are unconfirmed.'}
    hardware_path = ROOT/'docs/hardware-entry-hang-results.json'
    reported = read(hardware_path)['results'].get('0.7.34')
    if reported:
        result.update(hardware_result=reported['status'], hardware_status=reported['status'], hardware_follow_up=reported)
        result['DCP']['hardware_result'] = reported['status']
    if args.write:
        (ROOT/'docs/hardware-full-catchup.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        path = ROOT/'docs/hardware-chapter-transition.json'
        current = read(path)
        current['last_updated'] = max(current.get('last_updated', ''), '2026-11-04')
        current['full_catchup_candidate'] = {
            'version': '0.7.34', 'source': 'Complete final local 0.7.23, with alignment-safe shared map filename reads',
            'documentation': 'docs/hardware-full-catchup.json', 'DCP': result['DCP']['path'],
            'status': 'Full original-input DCP verified locally; combined hardware compatibility pending',
            'user_request': 'Restore all final emulator fixes in one combined candidate',
            'public_release': False, 'upgrade_patch': False}
        current['next_compatibility_candidate'] = current['full_catchup_candidate']
        if reported:
            current['full_catchup_candidate'].update(status=reported['status'], hardware_report=reported)
        if 'map_hook_bypass_candidate' in current:
            current['next_compatibility_candidate'] = current['map_hook_bypass_candidate']
        if 'asset_runtime_split_candidate' in current:
            current['next_compatibility_candidate'] = current['asset_runtime_split_candidate']
        if 'texture_budget_candidate' in current:
            current['next_compatibility_candidate'] = current['texture_budget_candidate']
        if 'framebuffer_candidate' in current:
            current['next_compatibility_candidate'] = current['framebuffer_candidate']
        if 'window_atlas_candidate' in current:
            current['next_compatibility_candidate'] = current['window_atlas_candidate']
        if 'display_polish_candidate' in current:
            current['next_compatibility_candidate'] = current['display_polish_candidate']
        path.write_text(json.dumps(current, indent=2)+'\n', encoding='utf-8')
        path = ROOT/'docs/hardware-entry-hang-results.json'
        hardware = read(path)
        hardware['last_updated'] = max(hardware.get('last_updated', ''), '2026-11-04')
        if not reported:hardware['interpretation'].update(
            new_build_created='0.7.34: complete final emulator feature set plus safe map filename guard; physical result pending',
            working_baseline_next_test='0.7.34: full combined feature candidate at explicit user request. 0.7.33 remains an untested isolated reference; no new physical pass is claimed.',
            full_feature_restore_request='so we update it like normal? can you add all patch to it so it catch up with emu version?',
            synthetic_map_fault='Confirmed old unaligned MOV.L in strict fixtures; repaired byte matcher passes. No reporter fault trace establishes actual hang causality.',
            full_feature_report='docs/hardware-full-catchup.json')
        path.write_text(json.dumps(hardware, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('version', 'changed_executable_bytes_from_latest',
          'all_14_other_modified_payloads_exact_0_7_23', 'DCP', 'hardware_status')}, indent=2))


if __name__ == '__main__':
    main()
