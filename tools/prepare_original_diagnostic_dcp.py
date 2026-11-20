"""Build original-input-only hardware diagnostic DCPs. No upgrade or publication.

Each phase is dry by default. --write saves only under the new diagnostic folder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.7.26'
OUT = ROOT / ('work/output/dcp-' + VERSION + '-diagnostic')
NAME = f'Rayblade-English-v{VERSION}-HARDWARE-DIAGNOSTIC.dcp'
EXE_SHA = 'ca7cae8c793eeef144dcbb0846f0e112b49de50cb86c44d8ff921f4e553b2b1a'
MIDPOINTS = {'0.7.27':'0.7.6', '0.7.28':'0.7.4', '0.7.29':'0.7.11', '0.7.30':'0.7.8', '0.7.31':'0.7.5'}
PARENTS = dict(MIDPOINTS, **{'0.7.28':'0.7.3','0.7.32':'0.7.31','0.7.33':'0.7.32','0.7.34':'0.7.23','0.7.35':'0.7.34','0.7.36':'0.7.27','0.7.37':'0.7.36','0.7.38':'0.7.37','0.7.39':'0.7.38','0.7.40':'0.7.39'})
PARENTS['0.7.41']='0.7.23'  # Final asset donor; runtime port is based on 0.7.40.
PARENTS['0.7.42']='0.7.41'
PARENTS['0.7.43']='0.7.42'
PARENTS['0.7.44']='0.7.43'
PARENTS['0.7.45']='0.7.44'
PARENTS['0.7.46']='0.7.45'
PARENTS['0.7.47']='0.7.45'
PARENTS['0.7.48']='0.7.45'
PARENTS['0.7.49']='0.7.48'
PARENTS['0.7.50']='0.7.48'


def read(path):
    return json.loads(path.read_text('utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    global VERSION, OUT, NAME, EXE_SHA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rtt', type=Path, required=True)
    parser.add_argument('--phase', choices=['inspect','build','verify','bundle'], required=True)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--version', choices=['0.7.26',*PARENTS], default='0.7.26')
    args = parser.parse_args()
    VERSION = args.version
    OUT = ROOT / ('work/output/dcp-' + VERSION + '-diagnostic')
    NAME = f'Rayblade-English-v{VERSION}-HARDWARE-DIAGNOSTIC.dcp'
    EXE_SHA = {'0.7.26':'ca7cae8c793eeef144dcbb0846f0e112b49de50cb86c44d8ff921f4e553b2b1a',
               '0.7.27':'1f0e62fd6d1c95077ae9febce8132598df443b5f800a9736ceafad4afff47a20',
               '0.7.28':'1c29cc3c8c012389c5f3063555799fc6b3ca7f557ec3e2b0887f2443198dee84',
               '0.7.29':'f149554da38d98e1ca533d042de59c27151e153520bd03b384dc24d79f8075a7',
               '0.7.30':'1beb33ca8fad81d85b060aa7277511d9308af54665d7ace58c8395ebb00a2938',
               '0.7.31':'054d99fbd8a29d981d4ba478b05a3817181c8dfd77267e30208bdbb0b15de020',
               '0.7.32':'1df8579f57db1300848c41c8f9b3fda0c8122a20d7994c239af26888cb4bcec6',
               '0.7.33':'4e281dd960965bc94f38d8e7b5e5d7c43ff7fd742ce40376343aa4fce8736144',
               '0.7.34':'68f7102790efaaa52889da69bf4e1208671f72e27be7dd44fa0b88767ef250e8',
               '0.7.35':'90656bf21c1a96654e94c01d4ddfdd821bffd866f0c273b6f5c201768db1ad88',
               '0.7.36':'054d99fbd8a29d981d4ba478b05a3817181c8dfd77267e30208bdbb0b15de020',
               '0.7.37':'f04e4b011fa2ff42107a72ac65dda99733a0cc537fa529867014ea9b3dcf191a',
               '0.7.38':'f71a9bd77b7fb2f6028a4e327ad7414f02ef0c796b21cfd1f4cdc7b91ee1ce9c',
               '0.7.39':'f71a9bd77b7fb2f6028a4e327ad7414f02ef0c796b21cfd1f4cdc7b91ee1ce9c',
               '0.7.40':'1426cd32cbc942bed643ad6f5cd3e8e0fdcd0b1370867eb5599dc73e6a3a4d90',
               '0.7.41':'1632f331219b96ffa982b4a647cd29987060847fc5042800debafaadf23b5b84',
               '0.7.42':'ce66d2b4ea9a6d8a6d50913ee6eebe42e740d9c58439b0540e59b1a707c6ac94',
               '0.7.43':'463e54d5244ca008410c8a47369b3f2a6e42906303dc8eaa6143b46b415c2c55',
               '0.7.44':'1426cd32cbc942bed643ad6f5cd3e8e0fdcd0b1370867eb5599dc73e6a3a4d90',
               '0.7.45':'d13d6cf267e5ce6ec07a70439205901596174912042e41feed39fbc885bf107f',
               '0.7.46':'5bb81a7b491295d510780ed1dd152985e1d28456032d110c2df3c0812b005e38',
               '0.7.47':'87ab7271aa9132029268e960ffae2a19b7df7a37b6a7e0d7718b3ba1ff66fc9a',
               '0.7.48':'6de79055e4edabd428cf778385719086ee21db312c3bd9a48101897e326c0be6',
               '0.7.49':'d89223501c8a49ba7aba30cb65861d70c76147c5a3fac1a6ac4fc176ac91df22',
               '0.7.50':'ef5254a341ccb48e04ce2d8b8a15247c2459ecd3fd9e21f2040cf08459424841'}[VERSION]
    if not args.write:
        print('DRY RUN:', args.phase, OUT, '; full original input only.', flush=True); return
    sys.path.insert(0, str(args.rtt.resolve()))
    from retro_trans import dcp
    OUT.mkdir(exist_ok=True)
    progress = lambda message, fraction=None: print(message, flush=True)
    if args.phase == 'inspect':
        # Reuse the verified immutable original's extracted tree; apply() later
        # re-inspects the actual source and verifies its complete tree identity.
        source = read(ROOT / 'work/output/dcp-0.7.24-diagnostic/original-tree.json')
        assert Path(source['gdi']).is_file()
        save(OUT/'original-tree.json', source)
        target = dcp.inspect_disc(ROOT / f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.cue',
                                  OUT/'inspect-target', progress=progress)
        assert target['files']['1ST_READ.BIN']['sha256'] == EXE_SHA
        if VERSION == '0.7.26':
            old = read(ROOT / 'work/output/dcp-0.7.25-diagnostic/target-tree.json')
            changed = [n for n in target['files'] if target['files'][n] != old['files'][n]]
            assert changed == ['1ST_READ.BIN'], changed
        else:
            # Verify the complete midpoint target, including all files that
            # were unchanged from the Japanese original, rather than comparing
            # against a later build whose assets the midpoint must not inherit.
            built = read(ROOT / f'work/output/{VERSION}/english-disc-report.json')
            assert built['source_build'] == PARENTS[VERSION]
            assert set(target['files']) == set(source['files'])
            for name, identity in target['files'].items():
                if name.lower().startswith('bootsector/'):continue
                expected = built['files'].get(name)
                if expected is not None:
                    expected = {'bytes':expected['size'],'sha256':expected['sha256']}
                else:
                    expected = source['files'][name]
                assert identity == expected, name
        assert target['bootsector_invariant_sha256'] == '05aadce6ab93f677cb121cbb1c7135d34ef516848976e66d4fdad81597148853'
        if VERSION in ('0.7.31','0.7.32','0.7.33','0.7.35','0.7.37','0.7.38','0.7.40'):
            previous = {'0.7.31':'0.7.28','0.7.32':'0.7.31','0.7.33':'0.7.32','0.7.35':'0.7.34','0.7.37':'0.7.36','0.7.38':'0.7.37','0.7.40':'0.7.39'}[VERSION]
            baseline = read(ROOT/f'work/output/dcp-{previous}-diagnostic/target-tree.json')
            assert set(target['files']) == set(baseline['files'])
            assert [n for n in target['files'] if target['files'][n] != baseline['files'][n]] == ['1ST_READ.BIN']
        if VERSION=='0.7.39':
            baseline=read(ROOT/'work/output/dcp-0.7.38-diagnostic/target-tree.json')
            assert set(target['files'])==set(baseline['files'])
            assert [n for n in target['files'] if target['files'][n]!=baseline['files'][n]]==['WIN00.AFS']
            from build_hardware_window_atlas import compose
            _, archive, _ = compose()
            assert target['files']['WIN00.AFS']['sha256']==hashlib.sha256(archive).hexdigest()
        if VERSION=='0.7.34':
            baseline=read(ROOT/'work/output/dcp-0.7.23/target-tree.json')
            assert set(target['files'])==set(baseline['files'])
            assert [n for n in target['files'] if target['files'][n]!=baseline['files'][n]]==['1ST_READ.BIN']
        if VERSION=='0.7.41':
            donor=read(ROOT/'work/output/dcp-0.7.23/target-tree.json')
            baseline=read(ROOT/'work/output/dcp-0.7.40-diagnostic/target-tree.json')
            assert set(target['files'])==set(donor['files'])==set(baseline['files'])
            assert {n for n in target['files'] if target['files'][n]!=donor['files'][n]}=={'1ST_READ.BIN','WIN00.AFS'}
            assert target['files']['WIN00.AFS']==baseline['files']['WIN00.AFS']
            from build_hardware_consolidated import compose
            executable,archive,_,_=compose()
            assert target['files']['1ST_READ.BIN']['sha256']==hashlib.sha256(executable).hexdigest()
            assert target['files']['WIN00.AFS']['sha256']==hashlib.sha256(archive).hexdigest()
        if VERSION in ('0.7.42','0.7.43','0.7.44','0.7.45','0.7.46','0.7.47','0.7.48','0.7.49','0.7.50'):
            baseline=read(ROOT/f'work/output/dcp-{PARENTS[VERSION]}-diagnostic/target-tree.json')
            assert set(target['files'])==set(baseline['files'])
            assert [n for n in target['files'] if target['files'][n]!=baseline['files'][n]]==['1ST_READ.BIN']
            if VERSION=='0.7.42':
                from build_hardware_text_upload_split import compose
            elif VERSION=='0.7.45':
                from build_hardware_battle_split import compose
            elif VERSION=='0.7.46':
                from build_hardware_header_split import compose
            elif VERSION=='0.7.47':
                from build_hardware_static_header import compose
            elif VERSION=='0.7.48':
                from build_hardware_aligned_header import compose
            elif VERSION=='0.7.49':
                from build_hardware_signed_fields import compose
            elif VERSION=='0.7.50':
                from build_hardware_complete import compose
            elif VERSION=='0.7.44':
                from build_hardware_code_asset_split import compose, DATA_CHANGES
                working=read(ROOT/'work/output/dcp-0.7.40-diagnostic/target-tree.json')
                assert set(target['files'])==set(working['files'])
                assert {n for n in target['files'] if target['files'][n]!=working['files'][n]}==DATA_CHANGES
            else:
                from build_hardware_status_bypass import compose
            executable,_=compose()
            assert target['files']['1ST_READ.BIN']['sha256']==hashlib.sha256(executable).hexdigest()
        if VERSION=='0.7.36':
            baseline=read(ROOT/'work/output/dcp-0.7.31-diagnostic/target-tree.json')
            parent=read(ROOT/'work/output/dcp-0.7.27-diagnostic/target-tree.json')
            assert set(target['files'])==set(baseline['files'])==set(parent['files'])
            assert {n for n in target['files'] if target['files'][n]!=baseline['files'][n]}=={'D_SCE.AFS','WMAP.AFS'}
            assert [n for n in target['files'] if target['files'][n]!=parent['files'][n]]==['1ST_READ.BIN']
        save(OUT/'target-tree.json', target)
        return
    source, target = [read(OUT/(name+'-tree.json')) for name in ('original','target')]
    assert dcp.tree_hash(source['files']) == '81addd42981923ba95636d06e912598b61f275069082cef62938add7d0416db3'
    assert target['files']['1ST_READ.BIN']['sha256'] == EXE_SHA
    patch = OUT/'packages'/NAME
    if args.phase == 'build':
        patch.parent.mkdir()
        result = dcp.run('build', {'source': source['gdi'], 'target': target['gdi'], 'output': str(patch)},
                         OUT/'build-original', progress=progress)
        metadata = {'retro_trans_dcp': 1, 'game_id': 'seireiki-rayblade',
                    'source_version': 'original', 'version': VERSION, 'diagnostic': True,
                    'source_tree_sha256': dcp.tree_hash(source['files']),
                    'target_tree_sha256': dcp.tree_hash(target['files']), 'game_files': 140,
                    'engine': 'Universal Dreamcast Patcher 2.1.8', 'upstream_commit': dcp.UPSTREAM,
                    'font': 'Native Skies 1x only',
                    'bootsector_invariant_sha256': target['bootsector_invariant_sha256']}
        if VERSION in MIDPOINTS:metadata['historical_midpoint'] = MIDPOINTS[VERSION]
        if VERSION in ('0.7.29','0.7.30'):
            metadata['investigation'] = 'Immediate conversation-start / mission-entry hang'
        if VERSION == '0.7.31':
            metadata['investigation'] = 'Working 0.7.28 plus movie geometry only; hardware regression split'
        if VERSION == '0.7.32':
            metadata.update(baseline='0.7.31',investigation='Only loading geometry and movie-edge sampling; historical 0.7.6 changes excluded')
        if VERSION == '0.7.33':
            metadata.update(baseline='0.7.32',investigation='Stock geometry reservation and movement range coordinates only; historical 0.7.6 changes excluded')
        if VERSION == '0.7.34':
            metadata.update(baseline='0.7.23',full_feature_catchup=True,
                investigation='All final local emulator features plus alignment-safe map filename guard; physical confirmation pending')
        if VERSION == '0.7.35':
            metadata.update(baseline='0.7.34',full_feature_catchup=True,
                investigation='Only bypass the shared map-label sniff/snap hook; scenario-transition result pending')
        if VERSION == '0.7.36':
            metadata.update(baseline='0.7.31',asset_source='0.7.27',full_feature_catchup=False,
                investigation='Exact passing-baseline executable with only historical story-choice/map-label archives changed')
        if VERSION == '0.7.37':
            metadata.update(baseline='0.7.36',full_feature_catchup=False,
                investigation='Only stock graphics reservation restored; all assets and other executable bytes exact 0.7.36')
        if VERSION == '0.7.38':
            metadata.update(baseline='0.7.37',full_feature_catchup=False,
                investigation='Only framebuffer format RGB888 to RGB565; one executable byte changes; Office white rectangles test')
        if VERSION == '0.7.39':
            metadata.update(baseline='0.7.38',full_feature_catchup=False,
                investigation='Only lossless window-atlas crop and matching UVs; executable exact 0.7.38; Office white rectangles test')
        if VERSION == '0.7.40':
            metadata.update(baseline='0.7.39',full_feature_catchup=False,
                investigation='Only loading geometry and movie-edge sampling; all assets and memory repairs exact hardware-reported working 0.7.39')
        if VERSION == '0.7.41':
            metadata.update(baseline='0.7.40',asset_source='0.7.23',full_feature_catchup=True,
                investigation='Consolidated bug fixes on working font renderer; status-only routing and relocated text allocator; physical retest pending',
                compatibility_exception='Shared map filename/snapping hook remains bypassed; translated lettering retained')
        if VERSION == '0.7.42':
            metadata.update(baseline='0.7.41',upload_baseline='0.7.40',full_feature_catchup=False,runtime_text_compression=False,
                investigation='Only seven text-compression regions restored from working 0.7.40; all other code/assets exact failed 0.7.41',
                limitation='Stage 6 missing/white text may return; controlled hardware retest pending')
        if VERSION == '0.7.43':
            metadata.update(baseline='0.7.42',constructor_baseline='0.7.40',full_feature_catchup=False,
                runtime_text_compression=False,status_vertical_alignment=False,
                investigation='Only bypass the shared status-constructor gate; three executable bytes change, all assets exact 0.7.42',
                limitation='Trust/Skills vertical alignment and Stage 6 text compression disabled; hardware test pending')
        if VERSION == '0.7.44':
            metadata.update(baseline='0.7.40',asset_source='0.7.43',full_feature_catchup=False,
                investigation='Exact working-baseline executable with all newer assets; only D_NAMES.BIN, ITM00.AFS and WMAP.AFS differ from 0.7.40',
                limitation='Later executable UI and battle fixes revert to 0.7.40; controlled hardware test pending')
        if VERSION == '0.7.45':
            metadata.update(baseline='0.7.44',full_feature_catchup=False,runtime_text_compression=False,status_vertical_alignment=False,
                investigation='Restore only 413-byte battle-display group; other 508 failed-build bytes and all assets remain exact passing 0.7.44',
                limitation='Later status/SP/header code and Stage 6 compression remain absent; hardware confirmation pending')
        if VERSION == '0.7.46':
            metadata.update(baseline='0.7.45',full_feature_catchup=False,runtime_text_compression=False,status_vertical_alignment=False,
                investigation='Restore only 260-byte location-banner measurement; remaining 248 bytes and all assets stay exact passing 0.7.45',
                limitation='Signed-SP formatting, status hooks and Stage 6 compression remain absent; hardware test pending')
        if VERSION == '0.7.47':
            metadata.update(baseline='0.7.45',full_feature_catchup=False,runtime_text_compression=False,status_vertical_alignment=False,
                investigation='Location measurement uses immutable Native advances embedded in executable; no loaded-font pointer read. All other code and assets exact passing 0.7.45',
                limitation='Font resource lifetime is an unconfirmed hypothesis; hardware test pending. Status hooks, signed SP and Stage 6 compression remain absent')
        if VERSION == '0.7.48':
            metadata.update(baseline='0.7.45',full_feature_catchup=False,runtime_text_compression=False,status_vertical_alignment=False,
                investigation='Replace unaligned name-offset MOV.L with bytewise reconstruction; strict SH-4 tests reproduce the fault in 0.7.46/47 and pass the correction. All other code/assets exact 0.7.45',
                limitation='Hardware retest pending. Status hooks, signed SP and Stage 6 compression remain absent')
        if VERSION == '0.7.49':
            metadata.update(baseline='0.7.48',full_feature_catchup=False,runtime_text_compression=False,status_vertical_alignment=False,
                investigation='Restore only 21 signed-number formatting bytes. All other code/assets, including the alignment fix, remain exact passing 0.7.48',
                limitation='Hardware retest pending. Status hooks and Stage 6 compression remain absent')
        if VERSION == '0.7.50':
            metadata.update(baseline='0.7.48',full_feature_catchup=True,runtime_text_compression=True,status_vertical_alignment=True,
                map_pixel_snapping=True,bytewise_name_offsets=True,bytewise_map_filename=True,
                investigation='Combine remaining emulator fixes with the exact passing 0.7.48 name-offset routine and retained hardware renderer. Status and map hooks occupy separate checked locations',
                limitation='Combined hardware retest pending; separate Stage 9 issue #5 remains unresolved')
        with zipfile.ZipFile(patch, 'a') as archive:
            archive.comment = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
            assert archive.testzip() is None
            ip = archive.read('bootsector/IP.BIN')
            assert ip[0x3d:0x3e] == b'1', 'VGA flag must be present in the full DCP.'
        assert dcp.inspect_patch(patch)['metadata'] == metadata
        save(OUT/'build-validation.json', {'version': VERSION, 'original_only': True,
             'asset': NAME, 'bytes': patch.stat().st_size, 'sha256': sha(patch),
             'metadata': metadata, 'VGA_boot_flag': '1', 'native_builder': result})
        return
    if args.phase == 'verify':
        # This is the immutable normalized ORIGINAL Japanese disc used by the
        # builder, not an English patch source. Its CUE conversion was already
        # validated by the earlier original-input diagnostics. apply() still
        # verifies source identity and every rebuilt game file/boot/audio here.
        proof = dcp.apply(Path(source['gdi']), patch,
                          OUT/'roundtrip-original', progress=progress)
        assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
        assert proof['verified_game_tree_sha256'] == dcp.tree_hash(target['files'])
        save(OUT/'original-apply-validation.json', proof)
        return
    build, proof = read(OUT/'build-validation.json'), read(OUT/'original-apply-validation.json')
    assert sha(patch) == build['sha256']
    assert proof['verified_game_tree_sha256'] == dcp.tree_hash(target['files'])
    assert proof['bootsector_invariant_sha256'] == target['bootsector_invariant_sha256']
    assert proof['release_metadata_verified'] and proof['audio_tracks_preserved']
    directory = patch.parent
    assert list(directory.glob('*.dcp')) == [patch]
    details = (
        'Changes: stock video setup (320x240 rendering / original VGA output) plus\n'
        'uncompressed generated-text uploads, combining the earlier independent diagnostics.\n'
        'The single Native Skies 1x bank stays exact. No HD bank or font selector.\n'
        'VGA support is explicitly set in the included boot sector.\n\n'
        'NOT A CONFIRMED FIX. Stage 6 missing/white text can return because its text-memory\n'
        'repair is disabled. Font sharpness may be lower under stock rendering.\n'
    ) if VERSION == '0.7.26' else ((
        'MIDPOINT TEST: based on historical 0.7.6, with Native font only.\n'
        'Keeps the 0.7.3 Native runtime, 0.7.4 640x480 rendering, 0.7.5 movie fit,\n'
        'and 0.7.6 story-choice/map-label changes. Later 0.7.7-0.7.26 fixes are absent.\n'
        'HD glyphs are erased and the title selector is removed. Zero padding keeps\n'
        'historical resource sizes and offsets; Native glyph pixels stay exact.\n'
        'VGA support is explicitly set in the included boot sector.\n\n'
        'NOT A CONFIRMED FIX. Historical overflow, text-memory and rendering bugs may return.\n'
        'This is a Native-only variant, not a byte-identical replay of historical 0.7.6.\n'
    ) if VERSION == '0.7.27' else (
        'MIDPOINT TEST: historical 0.7.4 rendering experiment, Native font only.\n'
        'Keeps the 0.7.3 Native runtime and 0.7.4 640x480 rendering.\n'
        'Does not include 0.7.5 movie fitting or 0.7.6 story-choice/map-label changes.\n'
        'HD glyphs and selector are removed with the same normalization as 0.7.27;\n'
        'Native pixels, historical resource sizes and offsets are preserved.\n'
        'VGA support is explicitly set in the included boot sector.\n\n'
        'EXPECTED: the opening movie can appear quarter-sized. Do not stop for that.\n'
        'NEW GAME TEST: advance past the Hallway exchange where Koichiro says\n'
        '"Oh, s-sorry..." and Kasumi is due to say "Oh...". The tester confirms\n'
        '0.7.2 passes this exact scene and 0.7.27 freezes at the transition.\n'
        'Report whether this diagnostic advances beyond Kasumi\'s first reply.\n\n'
        'NOT A CONFIRMED FIX. Historical rendering/UI/text-memory bugs may return.\n'
        'This is a Native-only variant, not a byte-identical historical replay.\n'
    ))
    if VERSION in ('0.7.29','0.7.30'):
        midpoint = MIDPOINTS[VERSION]
        role = 'UPPER CONTROL' if VERSION=='0.7.29' else 'MIDPOINT'
        details = (
            f'{role}: Native-only historical {midpoint}.\n'
            f'All historical {midpoint} code/assets are retained except the same Native-only\n'
            'normalization used in 0.7.27 (historical 0.7.6). HD pixels and selector are\n'
            'removed; shared metrics, resource sizes, offsets and Native pixels stay exact.\n'
            'No later rendering, UI or memory repairs are backported. VGA boot flag is set.\n\n'
            'PRIMARY TEST: the ORIGINAL IMMEDIATE HANG when dialogue/mission starts.\n'
            'For EACH diagnostic, record separately:\n'
            'A. New Game: does the first conversation appear and advance, or hang immediately?\n'
            'B. Clear 2 normal VMU save -> Next: does the next chapter conversation load?\n'
            'C. If entry works, does the later Hallway pass Koichiro "Oh, s-sorry..."\n'
            '   and Kasumi "Oh..."? Record this separately; it is not an entry failure.\n'
            'Cold boot between tests. Report the diagnostic number and each result.\n\n'
            'Comparison: 0.7.27 enters missions/New Game but later freezes in the Hallway.\n'
            'If 0.7.29 still hangs immediately, 0.7.30 splits the changes after 0.7.6.\n'
            'If 0.7.29 enters, investigate Native-only normalization or its interaction;\n'
            'do not assume a later historical feature caused the original entry failure.\n\n'
            'NOT A CONFIRMED FIX. Historical font/UI, texture-memory and rendering bugs\n'
            'are intentionally retained. This is not a byte-identical historical replay.\n'
        )
    if VERSION == '0.7.31':
        details = (
            'MOVIE-ONLY DIAGNOSTIC: Native-only historical 0.7.5.\n'
            'Based on 0.7.28, which the tester reports runs without black screens/freezes\n'
            'on tested paths but displays movies at quarter-screen size.\n'
            'Only movie position/size setters change: uniform 2x coordinates and sizes\n'
            'for the existing 640x480 output. Original movie streams and ALL game assets\n'
            'remain exact 0.7.28. Native 1x font only; no HD bank or title selector.\n'
            'No 0.7.6 choice/map-label changes or later repairs are included.\n\n'
            'CHECK: movie size/centering, New Game first conversation, and the Hallway\n'
            'beyond Koichiro "Oh, s-sorry..." into Kasumi "Oh...". Separately test\n'
            'Clear 2 normal VMU save -> Next. Report each result and exact freeze point.\n'
            'The movie correction itself needs hardware confirmation. If a freeze\n'
            'returns, that is useful isolation evidence, not a confirmed fix.\n\n'
            'NOT A PUBLIC RELEASE OR FULL COMPATIBILITY PASS. Historical bugs remain.\n'
        )
    if VERSION == '0.7.32':
        details = (
            'COSMETIC FIXES ON WORKING 0.7.31 BASELINE:\n'
            '1. Restore NOW LOADING size/position relative to the original screen.\n'
            '2. Inset movie-edge texture sampling to avoid the green bottom line.\n'
            'Full-size movie placement, original movie/audio streams, font pixels and\n'
            'all game assets remain exact 0.7.31. Native 1x only; no HD font/selector.\n'
            'No historical 0.7.6 story-choice/map changes or other later fixes are added.\n\n'
            'CHECK: loading text placement; full-size movies and their bottom edge;\n'
            'New Game first dialogue, Koichiro/Kasumi Hallway, and separately\n'
            'Clear 2 normal VMU save -> Next. Report each result and any exact freeze point.\n'
            'The tester reports 0.7.31 has no black screens/scenario freezes on tested\n'
            'paths. These two cosmetic changes still need their own hardware check.\n\n'
            'No full-game compatibility claim. Other historical baseline bugs remain.\n'
        )
    if VERSION == '0.7.33':
        details = (
            'MAP / BATTLE GRID DIAGNOSTIC FROM 0.7.32:\n'
            '1. Restore the original Japanese graphics reservation, freeing about\n'
            '   3.27 MiB for terrain, unit, window, portrait and dialogue textures.\n'
            '   This targets the reported blank map panels and pale unit rectangles.\n'
            '2. Correct movement/range-fill XY coordinates for the existing 640x480\n'
            '   output, so tiles align with the selected unit and arrows.\n'
            'All assets, Native 1x font, RGB888 video mode, loading position and movie\n'
            'corrections stay exact 0.7.32. No HD bank/selector or 0.7.6 choice/map\n'
            'changes are restored; no texture repacking or text compression is added.\n\n'
            'CHECK THE REPORTED SCENES: map labels/dialogue and portraits; unit\n'
            'shadows and battle dialogue; movement grid while moving the cursor and\n'
            'panning the camera. Also retest New Game Hallway, Clear 2 -> Next and\n'
            'a busy battle. Report any remaining blank textures or exact freeze point.\n'
            'The photos resemble earlier allocation failures; no physical RAM capture\n'
            'was available for this report. The stock graphics reserve has less list\n'
            'headroom at 640x480 than at 320x240, so physical busy-battle testing matters.\n\n'
            'LOCAL DIAGNOSTIC: hardware confirmation and full-route coverage pending.\n'
        )
    if VERSION=='0.7.34':
        details=(
            'FULL FEATURE CATCH-UP: all final fixes through local emulator build 0.7.23,\n'
            'plus a repaired map-label filename check. This is ONE combined patch;\n'
            'do not stack older diagnostic patches or apply this to 0.7.33.\n\n'
            'Includes story choices/map labels, compact weapons, full Trust help, SP,\n'
            'memory-card notices, room names, headers, status/selection layout, loading\n'
            'and movie fixes, compact atlases, movement grid, targeting, split-battle\n'
            'clipping and the Stage 6 lossless text-memory repair.\n'
            'Native Skies 1x only. HD font/selector and superseded broken experiments\n'
            'remain removed. Final RGB565 video setup and text upload compression\n'
            'are restored to match the complete emulator build.\n\n'
            'HARDWARE TEST: first New Game conversation, Koichiro/Kasumi Hallway,\n'
            'normal Clear 2 VMU save -> Next, map labels/dialogue, cursor/grid and busy\n'
            'battle, attack targeting/split view, Stage 6 issue #1, menus and save/load.\n'
            'Check loading placement and complete movies too. Cold boot for each test.\n'
            'Report exact checkpoint/version if any black screen, freeze or blank UI returns.\n\n'
            'LOCAL COMBINED CANDIDATE: not a confirmed Dreamcast fix or public release.\n'
            'The old map guard has an alignment defect reproduced in strict SH-4 tests;\n'
            'no actual reporter fault address was captured, so causality is unconfirmed.\n'
            'Existing incomplete room-tag/save-label/translation limitations remain.\n'
        )
    if VERSION=='0.7.35':
        details=(
            'SCENARIO TRANSITION DIAGNOSTIC: based on complete 0.7.34.\n'
            'Only one shared sprite draw target changes (3 executable bytes).\n'
            'The custom map-label filename check/position snapping is bypassed;\n'
            'the original sprite draw receives the existing 2x-scaled descriptor.\n'
            'All assets, Native 1x font, story choices, map labels, UI, loading/movie,\n'
            'grid/target/clipping/selector and Stage 6 text-memory fixes remain.\n'
            'Map-label edges may look slightly different at fractional scrolling positions.\n\n'
            'TEST ON THE SAME DREAMCAST / GDEMU / VGA:\n'
            'A. New Game: first conversation, then the Koichiro/Kasumi Hallway.\n'
            'B. Clear 2 normal VMU save -> Next.\n'
            'C. Clear 3: A Girl\'s Resolve save: advance beyond ALL opening dialogue\n'
            '   and verify that the following scene appears instead of going black.\n'
            'Record each result, and the exact last line/scene if it still fails.\n'
            'Also check map labels and movement/camera scrolling. Cold boot between tests.\n\n'
            '0.7.34 is reported to retain New Game/scenario freezes despite other fixes\n'
            'working. The alignment-only repair was insufficient. This build isolates\n'
            'the complete custom map hook; it is not a confirmed cause or hardware fix.\n'
            'Use the original Japanese image; do not stack this onto an English build.\n'
        )
    if VERSION=='0.7.36':
        details=(
            'ASSET/RUNTIME SPLIT: exact executable and Native-only font from 0.7.31.\n'
            'Only D_SCE.AFS (story choices) and WMAP.AFS (map labels) differ from 0.7.31.\n'
            'These two archives are exact 0.7.27. The custom map drawing hook is absent.\n'
            'Later UI, loading/movie-edge, memory, grid, targeting and clipping fixes\n'
            'are intentionally absent. Earlier visual defects can return.\n'
            'This isolates the earlier regression, not the complete 0.7.35 feature set.\n\n'
            'TEST SEPARATELY, COLD BOOTING ON THE SAME DREAMCAST / GDEMU / VGA:\n'
            'A. New Game first dialogue AND the later Koichiro/Kasumi Hallway exchange.\n'
            'B. Clear 2 normal VMU save -> Next.\n'
            'C. Clear 3 save: advance through ALL dialogue and into the following scene.\n'
            'For any failure, record the last line/scene and compare that exact path\n'
            'on 0.7.31. A pass does not prove the full-feature freeze is fixed.\n\n'
            'Diagnostic only. No HD font, selector, upgrade or public release.\n'
        )
    if VERSION=='0.7.37':
        details=(
            'TEXTURE CAPACITY DIAGNOSTIC: only graphics reservation changes from 0.7.36.\n'
            'Restore the original reservation, giving textures 3,425,952 more bytes.\n'
            'All assets, Native 1x font, story choices, map labels, sprite drawing,\n'
            'RGB888 output and full-size movies remain exact 0.7.36.\n'
            'No map filename hook, runtime text compression or other later feature returns.\n\n'
            'TEST THE SAME SCENE AS THE LONG VIDEO:\n'
            'A. Early battle units: shadows should not be opaque white rectangles.\n'
            'B. Early dialogue: portraits, letters and dark background should be visible.\n'
            'C. Effects/camera pans: look for large white panels; advance through the\n'
            '   later Reamond dialogue, masked speaker and Arthur/Clovis world map.\n'
            'D. Continue beyond the point where the video ended, into the next scene.\n'
            'Also retest New Game/Hallway, Clear 2 -> Next, and busy battles.\n'
            'Cold boot each test on the same Dreamcast / GDEMU / VGA.\n\n'
            'Not a confirmed fix: freeing texture space reduces geometry list headroom.\n'
            'Small/misplaced NOW LOADING and other historical visual issues remain.\n'
            'Original Japanese image only; GDI output. No upgrade or public release.\n'
        )
    if VERSION=='0.7.38':
        details=(
            'OFFICE TEXTURE DIAGNOSTIC: one executable byte changes from 0.7.37.\n'
            'Switch 640x480 screen buffers from RGB888 to RGB565, saving 614,400 bytes.\n'
            'All assets, Native Skies 1x font, full-size movie placement, original\n'
            'graphics reservation and every other executable byte remain exact 0.7.37.\n'
            'Lower screen color precision can affect gradients; check movies and fades.\n\n'
            'PRIMARY TEST: cold boot, load Clear 3: A Girl\'s Resolve, then Next.\n'
            'Check the Office cutaway with Alforina (about 00:30-00:34 in the supplied\n'
            'video): the room background, portrait and dialogue should all display.\n'
            'Continue through the world map and Chapter 4 title into Ymir\'s battle\n'
            'dialogue. Check shadows, dialogue, movie colors and scene transitions.\n'
            'Separately retest New Game/Hallway, Clear 2 -> Next and busy battles.\n\n'
            'Texture pressure is a hypothesis; physical success is not yet confirmed.\n'
            'This is not the full emulator feature set. Historical loading/movie-edge,\n'
            'movement-grid and UI limitations remain. No custom map hook, text\n'
            'compression or atlas changes are added in this diagnostic.\n'
            'Original Japanese input only. GDI output for GDEMU/VGA. No upgrade.\n'
        )
    if VERSION=='0.7.39':
        details=(
            'OFFICE WINDOW-TEXTURE DIAGNOSTIC: executable identical to 0.7.38.\n'
            'Remove unused rows from the common window texture, reducing it from\n'
            '512x512 to 512x256 and saving 262,144 bytes of video memory.\n'
            'All used pixels, sprite sizes, anchors and filtering neighborhoods\n'
            'are preserved. Matching texture coordinates change; only two members\n'
            'of WIN00.AFS differ. Native font and every other game asset stay exact.\n\n'
            'PRIMARY TEST: cold boot, load Clear 3: A Girl\'s Resolve and choose Next.\n'
            'Check Alforina\'s Office (00:30-00:34 in the preceding video): room\n'
            'background, dialogue and portrait must display without white panels.\n'
            'Recheck the mountain scene around 01:30, reported fixed in 0.7.38.\n'
            'Continue into Chapter 4. Also check menus/window borders, New Game\n'
            'first dialogue/Hallway, Clear 2 -> Next and busy battles.\n\n'
            'This tests remaining texture pressure; physical success is pending.\n'
            'RGB565, stock graphics reservation and all code stay exact 0.7.38.\n'
            'No later hooks, font kernel, text compression or map/grid changes.\n'
            'Historical UI, loading/movie-edge and grid limitations remain.\n'
            'Original Japanese input only. GDI for GDEMU/VGA. No upgrade or release.\n'
        )
    if VERSION=='0.7.40':
        details=(
            'LOADING AND MOVIE-EDGE FIXES ON REPORTED WORKING 0.7.39:\n'
            '1. Restore NOW LOADING to its original proportional size and lower-right\n'
            '   position in the existing 640x480 output.\n'
            '2. Inset movie texture sampling half a texel to avoid the green bottom\n'
            '   padding line. Full movie size, position, streams and audio stay exact.\n'
            'All game assets, smaller window texture, Native Skies 1x font, RGB565\n'
            'and original graphics reservation remain exact 0.7.39.\n'
            'Only the two requested cosmetic fixes are added, not full feature parity.\n\n'
            'TEST: cold boot on GDEMU/VGA. Check NOW LOADING position and size,\n'
            'opening CG/movie bottom edge, full playback, fades and scene transitions.\n'
            'Recheck Office background/dialogue, mountain scene, chapter progression,\n'
            'New Game/Hallway and Clear 2 -> Next to confirm no regression.\n'
            'Report the exact movie/scene if any line or visual defect remains.\n\n'
            'Original Japanese input only. GDI output. No upgrade or public release.\n'
            'Hardware confirmation of this build remains pending.\n'
        )
    if VERSION=='0.7.41':
        details=(
            'CONSOLIDATED FIXES ON REPORTED WORKING 0.7.40:\n'
            'Retains its Native Skies 1x renderer/font, memory and compact-atlas\n'
            'repairs, full-size movies, lower-right loading and green-edge fix.\n'
            'Restores compact weapons/movie names, complete Trust help, status\n'
            'alignment, signed SP, notices, room tags and fitted location banners.\n'
            'Includes movement grid, targeting/lines, split-battle clipping,\n'
            'full-width selectors and lossless Stage 6 text-memory compression.\n\n'
            'The status alignment wrapper now runs only for the two status panels.\n'
            'Ordinary dialogue constructors directly use the original routine.\n'
            'Text compression allocation is adapted to the retained renderer.\n'
            'The old shared map filename/snapping hook remains bypassed; English\n'
            'map labels remain, but fractional scrolling can affect their edges.\n'
            'No HD font or title selector. No new translation changes.\n\n'
            'TEST: New Game/Hallway; Clear 2 -> Next; Clear 3 dialogue through\n'
            'Office/mountain and following chapter; movement grid and busy battles;\n'
            'targeting/split view; Stage 6 text; status/Trust/selection menus;\n'
            'save/load, loading placement and complete movie playback.\n'
            'This combined build needs its own hardware test. A passing 0.7.40\n'
            'does not establish compatibility of the newly restored features.\n'
            'Original Japanese input only. GDI output. No upgrade or public release.\n'
        )
    if VERSION=='0.7.42':
        details=(
            'RETURNING BLACK-SCREEN DIAGNOSTIC:\n'
            '0.7.41 is reported to black-screen during mission dialogue and New Game.\n'
            'This build removes ONLY its runtime text-compression group and restores\n'
            'the allocation/upload path from reported working 0.7.40.\n'
            'All other 0.7.41 code and every asset stay exact: menus, status routing,\n'
            'grid/targeting, split clipping, selectors, memory and font repairs,\n'
            'loading placement and movies. Native Skies 1x only; no HD/selector.\n\n'
            'KNOWN TRADEOFF: Stage 6 missing/white text may return because its\n'
            'text-memory compression repair is deliberately disabled.\n'
            'This is a controlled comparison, not a confirmed fix.\n\n'
            'TEST ON THE SAME DREAMCAST/GDEMU/VGA:\n'
            '1. Cold boot and start New Game. Test the first dialogue and Hallway.\n'
            '2. Cold boot, load the same normal VMU save and repeat the mission\n'
            '   dialogue that black-screened in 0.7.41. Continue past its end.\n'
            '3. Check Clear 2 -> Next and Clear 3/Office transitions if available.\n'
            'Report each result and the exact last line/scene if it still fails.\n'
            '0.7.40 remains the reported working fallback.\n\n'
            'A matched pass implicates the removed group or its interaction; a\n'
            'failure means the remaining changes still need a narrower split.\n'
            'Apply this single DCP to ORIGINAL JAPANESE input; do not stack it\n'
            'on 0.7.41. GDI output only for this test. No upgrade/public release.\n'
        )
    if VERSION=='0.7.43':
        details=(
            'STATUS-WINDOW HOOK DIAGNOSTIC:\n'
            '0.7.42 still black-screens in mission dialogue and New Game.\n'
            '0.7.43 changes only one constructor call target (three bytes),\n'
            'bypassing the restored status-panel hook for all window creation.\n'
            'The original routine is used directly, as in working 0.7.40.\n'
            'Every other executable byte and every asset stay exact 0.7.42.\n\n'
            'RETAINED: translated UI, fitted headers, maps, movement grid, targeting,\n'
            'lines, split clipping, selection bars, Native Skies 1x font, hardware\n'
            'memory repairs, loading placement and full-size/clean-edge movies.\n'
            'TRADEOFFS: Trust/Skills vertical marker alignment may be slightly off.\n'
            'Text compression remains disabled; Stage 6 missing text may return.\n\n'
            'TEST: cold boot on the same Dreamcast/GDEMU/VGA. Start New Game and\n'
            'advance through its first dialogue and Hallway. Separately cold boot,\n'
            'load the normal VMU save and repeat the mission dialogue that failed\n'
            'in 0.7.42; continue past its end. Check Clear 2 -> Next and Clear 3\n'
            'Office transitions if available. Report each result/checkpoint.\n'
            '0.7.40 remains the reported working fallback.\n\n'
            'This is a controlled diagnostic, not a confirmed fix or full parity.\n'
            'Apply only to ORIGINAL JAPANESE input and output GDI. Do not stack\n'
            'patches. No HD font/selector, upgrade patch or public release.\n'
        )
    if VERSION=='0.7.44':
        details=(
            'EXECUTABLE / ASSET SPLIT:\n'
            '0.7.43 still fails New Game and mission dialogue on hardware.\n'
            '0.7.44 uses the EXACT reported-working 0.7.40 executable, with\n'
            'every other file identical to 0.7.43. Only D_NAMES.BIN, ITM00.AFS\n'
            'and WMAP.AFS differ from 0.7.40. No partial code restoration.\n\n'
            'Retains the 0.7.40 Native-only font, hardware memory/window repairs,\n'
            'loading placement and movie fixes, with newer names/item/map data.\n'
            'TRADEOFF: later executable menu/header/status/SP and battle grid,\n'
            'target, line, clipping and selector fixes revert to 0.7.40.\n'
            'Stage 6 text compression is absent; some visual defects may return.\n\n'
            'TEST: cold boot New Game and the same mission dialogues that failed\n'
            'in 0.7.43. Continue past dialogue into the following scene.\n'
            'If it fails, compare the same checkpoint in 0.7.40 on this setup.\n'
            'A pass narrows the regression to removed code or its interactions;\n'
            'a failure with a matching 0.7.40 pass points to the three data files\n'
            'or their interactions. Neither result alone identifies a fault.\n\n'
            'Diagnostic only: hardware result pending, not full feature parity.\n'
            'Apply to ORIGINAL JAPANESE input, output GDI; do not stack patches.\n'
            'No HD font/selector, upgrade patch or public release.\n'
        )
    if VERSION=='0.7.45':
        details=(
            'BATTLE DISPLAY HALF-SPLIT:\n'
            'The passing report was corrected to 0.7.44; 0.7.43 still fails.\n'
            '0.7.45 restores 413 of the 921 differing executable bytes:\n'
            '- Movement/range grid alignment\n'
            '- Targeting and animation graphics coordinates\n'
            '- Application lines, inclusive split-battle clipping\n'
            '- Full-width menu selection bars\n'
            'The other 508 bytes and EVERY data file stay exact 0.7.44.\n\n'
            'Status hooks, signed-SP/header code and Stage 6 text compression\n'
            'remain absent. Native-only font, hardware memory/window repairs,\n'
            'loading placement and movie fixes remain. No HD selector.\n\n'
            'TEST: cold boot New Game and the same mission dialogues that failed\n'
            'in 0.7.43 but passed in 0.7.44. Continue past the end of dialogue.\n'
            'Then check movement tiles, targeting, split battles and menu bars.\n'
            'If it fails, note the last scene/line and compare with 0.7.44.\n'
            'A failure narrows the next split to this battle group. A pass leads\n'
            'to splitting the remaining code and its interactions.\n\n'
            'Routine and package checks passed; hardware result is pending.\n'
            'Original Japanese input only, GDI output; do not stack patches.\n'
            'No upgrade patch or public release. 0.7.44 remains the fallback.\n'
        )
    if VERSION=='0.7.46':
        details=(
            'LOCATION-BANNER HALF-SPLIT:\n'
            '0.7.45 is reported passing. This build adds ONLY the location-width\n'
            'measurement fix: banners fit the Native variable-width font while\n'
            'retaining the original right anchor, frame artwork and animation.\n'
            '260 of the remaining 508 bytes versus failed 0.7.43 are restored.\n'
            'Every other executable byte and every data file stay exact 0.7.45.\n\n'
            'RETAINED: passing battle grid, targeting, lines, split clipping,\n'
            'selection bars, hardware memory/window repairs, loading and movies.\n'
            'Signed-SP formatting, status hooks and text compression stay off.\n'
            'Native Skies 1x only; no HD bank or selector.\n\n'
            'TEST: cold boot New Game and the same mission dialogues that passed\n'
            'in 0.7.45. Continue past dialogue into the next scene. Inspect\n'
            'Hallway, Office and Summoning Facility banners where available.\n'
            'If it fails, record the last scene/line and compare with 0.7.45.\n'
            'A matched failure isolates location measurement or its interaction;\n'
            'a pass leads to splitting the remaining 248 bytes/interactions.\n\n'
            'Routine/package checks passed; hardware confirmation is pending.\n'
            'Apply to ORIGINAL JAPANESE input; output GDI. Do not stack patches.\n'
            'No upgrade or public release. 0.7.45 remains the working fallback.\n'
        )
    if VERSION=='0.7.47':
        details = (
            'Seireiki Rayblade English 0.7.47 - HARDWARE DIAGNOSTIC\n\n'
            '0.7.45 is reported passing; 0.7.46 black-screens during New Game and\n'
            'mission dialogue. The only added feature was location-banner width\n'
            'measurement. This build keeps those widths but embeds the exact\n'
            'Native font advances in the executable, avoiding the loaded-font\n'
            'pointer. Every other code byte and asset stays exact 0.7.45.\n\n'
            'This tests a resource-lifetime hypothesis, not a confirmed root cause.\n'
            'Cold-boot and repeat New Game and the previously failing mission\n'
            'dialogues. Continue into the next scene; inspect location banners.\n'
            'If it still fails, compare with 0.7.45 and note the last scene/line.\n\n'
            'Apply the included DCP to the supported ORIGINAL Japanese disc with\n'
            'Retro Trans Tools or Universal Dreamcast Patcher. Do not apply it\n'
            'to an English-patched image. No upgrade patch is included.\n'
            'Use fresh GDI output for GDEMU/VGA, replace the entire game folder,\n'
            'and cold-boot. Load a normal VMU save, not an emulator save state.\n\n'
            'Native Skies 1x only. Status hooks, signed SP formatting and Stage 6\n'
            'runtime text compression remain disabled. This is not full parity.\n'
            'No public release. 0.7.45 remains the working fallback.\n'
        )
    if VERSION=='0.7.48':
        details = (
            '0.7.48 - BYTEWISE NAME-OFFSET FIX\n\n'
            'Both 0.7.46 and 0.7.47 black-screened on hardware. A strict SH-4\n'
            'instruction test now reproduces an unaligned 32-bit read in their\n'
            'shared measurement routine, including the original dialogue caller.\n'
            'Name tables are packed at byte boundaries. The original game reads\n'
            'offsets one byte at a time; the replacement incorrectly used MOV.L.\n\n'
            '0.7.48 restores bytewise offset reading and retains the same measured\n'
            'location widths with static Native advances. Only that routine changes;\n'
            'all other code and assets remain exact working 0.7.45.\n'
            'Strict checks cover actual name rows, 128 dialogue caller cases and\n'
            '2,576 offset/control cases across all four address alignments.\n'
            'This is a reproduced code defect; the hardware retest is still pending.\n\n'
            'TEST: cold-boot New Game and the previously failing mission dialogues.\n'
            'Continue into the next scene and inspect location-banner widths.\n'
            'Use fresh original Japanese input, GDI output, and replace the entire\n'
            'game folder. No upgrade patch. Keep 0.7.45 as the working fallback.\n'
            'Native Skies 1x only. Status hooks, signed SP formatting and Stage 6\n'
            'text compression remain absent. No public release.\n\n'
        )
    if VERSION=='0.7.49':
        details = (
            '0.7.49 - SIGNED SP / NUMERIC FIELDS ONLY\n\n'
            '0.7.48 is reported working on hardware. This build restores only\n'
            '21 historical sign-writer bytes: + for positive values, - for negative\n'
            'values, and +0 for zero. Magnitudes, padding and gameplay stay the same.\n'
            'All other executable bytes and every asset remain exact 0.7.48,\n'
            'including its working bytewise name-offset alignment fix.\n\n'
            'Checks: 1,024 signed-byte/field-width cases against the original\n'
            'magnitude/padding bytes, 1,020 Native rendering cases, retained\n'
            'strict-alignment regression checks and original constructors.\n'
            'Hardware confirmation is still required for this build.\n\n'
            'TEST: cold-boot New Game and the previously failing mission dialogues.\n'
            'Inspect positive, negative and zero SP values in battle preview\n'
            'where available. Keep 0.7.48 as the working fallback.\n'
            'Apply to ORIGINAL Japanese input; output GDI and replace the entire\n'
            'game folder. No upgrade patch. Native Skies 1x only.\n'
            'Status adjustments and Stage 6 text compression remain disabled.\n'
            'This is a local diagnostic, not a public release.\n\n'
        )
    if VERSION=='0.7.50':
        details = (
            '0.7.50 - COMBINED FIXES WITH THE HARDWARE REPAIR\n\n'
            'Keeps the exact bytewise name-offset routine from working 0.7.48.\n'
            'Restores the remaining signed SP/numeric formatting, status-panel\n'
            'alignment, Stage 6 lossless text compression, and whole-pixel map\n'
            'lettering while scrolling. Map filenames are compared bytewise;\n'
            'status and map hooks use separate checked locations.\n'
            'Retains the working Native font/renderer, graphics-memory repairs,\n'
            'compact atlases, movement/targeting/clipping, loading and movies.\n'
            'All assets remain exact 0.7.48. Native Skies 1x only; no HD selector.\n\n'
            'Checks execute the current combined code under strict SH-4 alignment,\n'
            'including the prior dialogue-fault reproduction and repaired caller.\n'
            'This is not a new physical hardware pass or full-game certification.\n\n'
            'TEST: cold-boot New Game and Clear 2 -> Next; continue beyond dialogue\n'
            'to the following scene. Check Skills/Trust panels, signed SP, scrolling\n'
            'map labels, movement/targeting/split battles, Stage 6 dialogue, loading\n'
            'and movies. Keep 0.7.48 as the known working fallback.\n'
            'Apply to ORIGINAL Japanese input; choose GDI for GDEMU and replace\n'
            'the entire output game folder. No upgrade patch or public release.\n'
            'Separate Stage 9 CG issue #5 is still under investigation.\n\n'
        )
    (directory/'READ-ME.txt').write_text(
        f'Rayblade {VERSION} HARDWARE DIAGNOSTIC - full patch from original only\n\n'
        '1. Use a fresh copy of the ORIGINAL JAPANESE image, not an English patched image.\n'
        '2. In Universal Dreamcast Patcher 2.1.8, select its CUE/BIN image and the included DCP.\n'
        '   A DCP-enabled Retro Trans Tools build can also apply this package.\n'
        '3. Select GDI output for GDEMU; keep disc.gdi and every generated track together.\n'
        '4. Cold boot the Dreamcast with the VGA cable connected.\n'
        '5. Test New Game first. Separately load the normal Clear 2 VMU save and choose Next.\n'
        '   Do not use an emulator save state. Keep the original image and save.\n\n'
        + details +
        'Report whether New Game and Clear 2 -> Next load, or where they stop.\n'
        'No upgrade patch is included. This is a private diagnostic, not a public release.\n', encoding='utf-8')
    files = [patch, directory/'READ-ME.txt']
    sums = directory/'SHA256SUMS.txt'
    sums.write_text(''.join(sha(p)+'  '+p.name+'\n' for p in files), encoding='utf-8')
    files.append(sums)
    bundle = OUT/f'Rayblade-v{VERSION}-HARDWARE-DIAGNOSTIC-DCP.zip'
    with zipfile.ZipFile(bundle, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.name)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.endswith('.dcp')]) == 1
        assert not any('upgrade' in n.lower() or '-to-' in n.lower() for n in archive.namelist())
        for path in files:
            assert archive.read(path.name) == path.read_bytes()
    save(OUT/'bundle-validation.json', {'version': VERSION, 'diagnostic': True,
         'public_release': False, 'original_only': True, 'asset': bundle.name,
         'bytes': bundle.stat().st_size, 'sha256': sha(bundle),
         'game_tree_sha256': proof['verified_game_tree_sha256'],
         'bootsector_invariant_sha256': proof['bootsector_invariant_sha256'],
         'audio_content_preserved': True, 'VGA_boot_flag': '1', 'hardware_result': 'pending'})
    print('Verified original-only bundle:', bundle, flush=True)


if __name__ == '__main__':
    main()
