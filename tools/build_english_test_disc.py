"""Build a local English menu/name test disc with the integrated HD font.

Relocates enlarged D_NAMES and optional D_BMESS into verified zero padding after the last
file. Changes ISO9660 directory extent/size in both byte orders. Original dump
is read only. Library, battle and optional story integration follow the
component manifest and matching native proofs. Dry run by default.
"""
import argparse
import hashlib
import json
import shutil
import struct
import re
from build_font4x_patch import ROOT, VERSION
from build_test_disc import regenerate
from disc_inventory import Disc, SECTOR
from rayblade_codec import decompress


def directory_records(disc):
    pvd = disc.read(45016, 2048)
    queue = [('', int.from_bytes(pvd[158:162], 'little'),
              int.from_bytes(pvd[166:170], 'little'))]
    seen = set()
    records = []
    while queue:
        prefix, lba, size = queue.pop(0)
        if (lba, size) in seen:
            continue
        seen.add((lba, size))
        data = disc.read(lba, size)
        pos = 0
        while pos < len(data):
            length = data[pos]
            if not length:
                pos = (pos // 2048 + 1) * 2048
                continue
            record = data[pos:pos + length]
            if len(record) < 34 or pos % 2048 + length > 2048:
                raise ValueError('Malformed ISO directory record')
            name = record[33:33 + record[32]]
            if name not in (b'\0', b'\1'):
                name = name.decode('ascii').split(';')[0]
                path = prefix + '/' + name if prefix else name
                extent, count = struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]
                if struct.unpack_from('>I', record, 6)[0] != extent or struct.unpack_from('>I', record, 14)[0] != count:
                    raise ValueError('ISO both-endian metadata differs')
                if record[25] & 2:
                    queue.append((path, extent, count))
                else:
                    records.append({'path': path, 'lba': extent, 'size': count,
                                    'directory_lba': lba + pos // 2048, 'record_offset': pos % 2048})
            pos += length
    return records


def plan():
    cues = list(ROOT.glob('*.cue'))
    if len(cues) != 1:
        raise ValueError('Expected exactly one original CUE')
    cue = cues[0]
    disc = Disc(cue)
    inventory = disc.inventory()
    files = {r['path']: r for r in inventory}
    out = ROOT / 'work/output' / VERSION
    font_manifest = json.loads((out / 'font4x-patch.json').read_text(encoding='utf-8'))
    targets = {}
    for name, info in font_manifest['files'].items():
        original = disc.read(files[name]['lba'], files[name]['size'])
        candidate = (out / name).read_bytes()
        if hashlib.sha256(original).hexdigest() != info['source_sha256'] or hashlib.sha256(candidate).hexdigest() != info['target_sha256'] or len(candidate) != len(original):
            raise ValueError('Font component fingerprint mismatch: ' + name)
        targets[name] = candidate
    name_report = json.loads((out / 'text/names-component-report.json').read_text())
    names = (out / 'text/D_NAMES.BIN').read_bytes()
    if hashlib.sha256(names).hexdigest() != name_report['compressed_sha256']:
        raise ValueError('English name component changed')
    plain, used = decompress(names)
    if len(plain) > 65536 or used != len(names) or hashlib.sha256(plain).hexdigest() != name_report['output_sha256']:
        raise ValueError('English names exceed verified native capacity or differ from report')
    exe = (ROOT / 'work/source/disc/1ST_READ.BIN').read_bytes()
    if exe[0x10e9e:0x10ea6].hex() != '0ad40ad20b420900' or struct.unpack_from('<I', exe, 0x10ec8)[0] != 65536:
        raise ValueError('Native D_NAMES loader allocation changed')
    relocated={'D_NAMES.BIN':names}
    battle_proof=None
    if 'battle' in font_manifest:
        battle=font_manifest['battle'];packed=(out/'text/D_BMESS.BIN').read_bytes()
        original=disc.read(files['D_BMESS.BIN']['lba'],files['D_BMESS.BIN']['size'])
        decoded,consumed=decompress(packed)
        if hashlib.sha256(original).hexdigest()!=battle['source_compressed_sha256'] or hashlib.sha256(packed).hexdigest()!=battle['compressed_sha256']:
            raise ValueError('Battle source/candidate hash mismatch')
        if consumed!=len(packed) or hashlib.sha256(decoded).hexdigest()!=battle['decoded_sha256'] or len(decoded)>battle['data_capacity']:
            raise ValueError('Battle decoded payload/capacity mismatch')
        if struct.unpack_from('<I',targets['1ST_READ.BIN'],0x10dc4)[0]!=battle['data_capacity'] or struct.unpack_from('<H',targets['1ST_READ.BIN'],0x1bb18)[0]!=battle['workspace_bytes']:
            raise ValueError('Battle native allocation patches absent')
        battle_proof=json.loads((out/'battle-english-native-test.json').read_text('utf-8'))
        if battle_proof['component_sha256']!=battle['decoded_sha256'] or battle_proof['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest():
            raise ValueError('Battle native proof belongs to another candidate')
        relocated['D_BMESS.BIN']=packed
    story_proof=None
    if 'scenario' in font_manifest:
        story=font_manifest['scenario']
        story_proof=json.loads((out/'scenario-native-test.json').read_text('utf-8'))
        if 'D_SCE.AFS' not in targets or hashlib.sha256(targets['D_SCE.AFS']).hexdigest()!=story['archive_sha256']:
            raise ValueError('Story archive absent or different from verified component')
        if story_proof['archive_sha256']!=story['archive_sha256'] or story_proof['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest():
            raise ValueError('Story native proof belongs to another candidate')
        if story_proof['native_lookup_cases']!=story['english_commands'] or story_proof['held_original_stream_cases']!=story['held_commands']:
            raise ValueError('Story native proof coverage does not match component')
    pvd = disc.read(45016, 2048)
    volume_end = 45000 + struct.unpack_from('<I', pvd, 80)[0]
    first_free = max(r['lba'] + (r['size'] + 2047) // 2048 for r in inventory)
    needed = sum((len(raw)+2047)//2048 for raw in relocated.values())
    if first_free + needed > volume_end:
        raise ValueError('No room inside original volume for relocated English files')
    for track in disc.tracks:
        if track['start_lba'] <= first_free < track['end_lba']:
            if first_free + needed > track['end_lba']:
                raise ValueError('Relocation crosses a track boundary')
            break
    else:
        raise ValueError('Relocation does not belong to a data track')
    if any(disc.read(first_free, needed * 2048)):
        raise ValueError('Destination padding is not zero; refusing to overwrite')
    changes = {}
    for name, candidate in targets.items():
        entry = files[name]
        original = disc.read(entry['lba'], entry['size'])
        for off in range(0, len(candidate), 2048):
            if original[off:off + 2048] != candidate[off:off + 2048]:
                lba = entry['lba'] + off // 2048
                sector = bytearray(disc.read(lba, 2048))
                sector[:len(candidate[off:off + 2048])] = candidate[off:off + 2048]
                changes[lba] = bytes(sector)
    directory=directory_records(disc);cursor=first_free;locations={}
    for name,raw in relocated.items():
        sectors=(len(raw)+2047)//2048
        for off in range(0,sectors*2048,2048):
            lba=cursor+off//2048
            if lba in changes:raise ValueError('Relocation overlaps another edit')
            changes[lba]=raw[off:off+2048].ljust(2048,b'\0')
        matches=[r for r in directory if r['path']==name]
        if len(matches)!=1:raise ValueError('Expected a single directory entry: '+name)
        row=matches[0]
        if (row['lba'],row['size'])!=(files[name]['lba'],files[name]['size']):
            raise ValueError('Directory differs from source inventory: '+name)
        lba, pos = row['directory_lba'], row['record_offset']
        sector = bytearray(changes.get(lba, disc.read(lba, 2048)))
        struct.pack_into('<I', sector, pos + 2, cursor)
        struct.pack_into('>I', sector, pos + 6, cursor)
        struct.pack_into('<I', sector, pos + 10, len(raw))
        struct.pack_into('>I', sector, pos + 14, len(raw))
        changes[lba] = bytes(sector)
        locations[name]={'original_lba':files[name]['lba'],'new_lba':cursor,'new_size':len(raw),'new_sectors':sectors}
        cursor+=sectors
    raw_changes = []
    for lba, payload in sorted(changes.items()):
        track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
        off = (track['index'] + lba - track['start_lba']) * SECTOR
        with track['path'].open('rb') as fh:
            fh.seek(off)
            raw = fh.read(SECTOR)
        if len(raw) != SECTOR or regenerate(raw) != raw:
            raise ValueError('Original MODE1 EDC/ECC invalid')
        changed = bytearray(raw)
        changed[16:2064] = payload
        raw_changes.append((track['path'].name, off, regenerate(changed)))
    targets.update(relocated)
    report = {'version': VERSION, 'kind': 'local English menu/name test disc',
              'names': {**locations['D_NAMES.BIN'],
                        'decoded_size': len(plain), 'native_capacity': 65536},
              'relocations':locations,
              'changed_sectors': len(changes),
              'changed_tracks': sorted({x[0] for x in raw_changes}),
              'directory_both_endian_fields': 'updated', 'original_dump': 'read only',
              'files': {name: {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in targets.items()},
              'pending': ['In-game menu/font/layout check', 'Library insertion', 'Story and battle translation/insertion', 'Image-based UI audit']}
    if 'library' in font_manifest:
        tested=json.loads((out/'library-native-test.json').read_text())
        actual_library=decompress(targets['WIN00.AFS'][font_manifest['library']['archive_member_offset']:
            font_manifest['library']['archive_member_offset']+font_manifest['library']['archive_member_bytes']])[0]
        if tested['library_component_sha256']!=hashlib.sha256(actual_library).hexdigest() or tested['filter_function_sha256']!=hashlib.sha256(targets['1ST_READ.BIN'][0x6bf00:0x6c32a]).hexdigest():
            raise ValueError('Library verification report does not match the integrated component/filter')
        report['kind']='local English menu/name/library test disc'
        report['library']=font_manifest['library']
        report['library_native_validation']=tested
        if font_manifest.get('library_layout'):
            layout=font_manifest['library_layout'];raw=(out/'library-layout-native-test.json').read_bytes();witness=json.loads(raw)
            if hashlib.sha256(raw).hexdigest()!=layout['proof_sha256']:
                raise ValueError('Library layout proof fingerprint differs from manifest')
            if witness['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest() or witness['library_sha256']!=tested['library_component_sha256']:
                raise ValueError('Library layout proof belongs to another component/executable')
            font_off,font_size=struct.unpack_from('<II',targets['WIN00.AFS'],8)
            if witness['font_sha256']!=hashlib.sha256(targets['WIN00.AFS'][font_off:font_off+font_size]).hexdigest():
                raise ValueError('Library layout proof belongs to another font')
            if len(witness['geometry'])!=2 or len(witness['native_scroll_witnesses'])!=2 or witness['native_parser_line_occurrences']!=2*layout['nonempty_line_count']:
                raise ValueError('Library layout proof lacks required native viewer/parser/scroll coverage')
            report['library_layout_native_validation']=witness
        report['pending']=['In-game menu/library/font/layout and memory checks',
                           'Story and battle review/insertion','Image-based UI audit']
    if font_manifest.get('library_header'):
        header=font_manifest['library_header'];raw=(out/'library-header-native-test.json').read_bytes();witness=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=header.get('proof_sha256'):
            raise ValueError('Library header proof fingerprint differs from manifest')
        font_off,font_size=struct.unpack_from('<II',targets['WIN00.AFS'],8)
        actual_hashes={'executable_sha256':hashlib.sha256(targets['1ST_READ.BIN']).hexdigest(),
            'names_sha256':hashlib.sha256(plain).hexdigest(),
            'library_sha256':tested['library_component_sha256'],
            'font_sha256':hashlib.sha256(targets['WIN00.AFS'][font_off:font_off+font_size]).hexdigest()}
        # `plain` still holds D_NAMES; battle uses its own `decoded` local.
        if any(witness.get(k)!=v for k,v in actual_hashes.items()):
            raise ValueError('Library header proof belongs to another candidate')
        if witness.get('counts')!={'character':144,'mech':128} or witness.get('queue_bytes_roundtripped')!=3072 or witness.get('decimal_cases')!=528:
            raise ValueError('Library header proof lacks required coverage')
        if not (header['library_end']<header['scratch_start'] and header['scratch_start']+header['scratch_reserved_bytes']==header['shared_capacity']==0x20000):
            raise ValueError('Library/scratch ranges overlap or exceed allocation')
        report['library_header_native_validation']=witness
    if 'battle' in font_manifest:
        report['kind']='local English menu/name/library/battle test disc'
        report['battle']={**font_manifest['battle'],'disc_relocation':locations['D_BMESS.BIN']}
        report['battle_native_validation']=battle_proof
        report['pending']=['In-game battle-state/font/layout/memory checks','Story review and insertion','Independent meaning review','Image-based UI/movie audit']
    if 'scenario' in font_manifest:
        report['kind']='local English story/menu/name/library/battle test disc'
        report['scenario']=font_manifest['scenario']
        report['scenario_native_validation']=story_proof
        report['pending']=['Actual file I/O, memory, cache, event navigation and save/load checks',
            'Measured dialogue/library/battle layout and word wrapping','Full VM text coverage and held passages',
            'Independent meaning review','Image-based UI/movie audit']
    if 'diagnostic' in font_manifest:
        report['kind']='local restricted startup diagnostic'
        report['diagnostic']=font_manifest['diagnostic']
        report['pending']=['Boot comparison only; do not use as full translation test build']
    if font_manifest.get('font_format') in (3,4):
        raster=json.loads((out/'genei-font-native-test.json').read_text('utf-8'))
        surface=json.loads((out/'genei-surface-native-test.json').read_text('utf-8'))
        executable_sha=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest()
        if raster['executable_sha256']!=executable_sha or surface['executable_sha256']!=executable_sha:
            raise ValueError('GenEi font proof belongs to another executable')
        font_off,font_size=struct.unpack_from('<II',targets['WIN00.AFS'],8)
        if raster['font_sha256']!=hashlib.sha256(targets['WIN00.AFS'][font_off:font_off+font_size]).hexdigest():
            raise ValueError('GenEi raster proof belongs to another font')
        if font_manifest.get('font_format')==4:
            if raster.get('native_cases')!=393 or raster.get('alpha_levels')!=[0,5,11,15] or len(surface.get('native_texture_format_cases',[]))!=8:
                raise ValueError('Four-level font proof lacks required coverage/texture format cases')
        if not (out/'FONT-LICENSE.txt').is_file():raise ValueError('GenEi copyright/OFL notices absent')
        report['font_native_validation']={'font':font_manifest['vector_font'],'raster':raster,'surfaces':surface}
    if font_manifest.get('scenario',{}).get('word_wrap'):
        proof=json.loads((out/'word-wrap-native-test.json').read_text('utf-8'))
        if proof['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest() or proof['archive_sha256']!=hashlib.sha256(targets['D_SCE.AFS']).hexdigest():
            raise ValueError('Story word-wrap proof belongs to another executable/archive')
        if proof['counts']['commands']!=font_manifest['scenario']['english_commands'] or proof['counts']['wrapped']!=font_manifest['scenario']['word_wrap']['word_wrapped_commands']:
            raise ValueError('Story word-wrap proof coverage differs from component')
        report['word_wrap_native_validation']=proof
        inline=font_manifest['scenario']['word_wrap']
        if inline.get('inline_control_commands_reflowed'):
            raw=(out/'inline-control-native-test.json').read_bytes();tested=json.loads(raw)
            if hashlib.sha256(raw).hexdigest()!=inline['inline_control_proof_sha256'] or tested['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest():
                raise ValueError('Inline-control proof differs from the compiled story/executable')
            if tested['commands']!=inline['inline_control_commands_reflowed']:
                raise ValueError('Inline-control coverage differs from component')
            report['inline_control_native_validation']=tested
    if font_manifest.get('ui_layout'):
        layout=font_manifest['ui_layout'];raw=(out/'ui-layout-native-test.json').read_bytes();tested=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=layout['proof_sha256']:
            raise ValueError('UI layout proof fingerprint differs from manifest')
        plain_names=decompress(targets['D_NAMES.BIN'])[0]
        for key,actual in [('executable_sha256',hashlib.sha256(targets['1ST_READ.BIN']).hexdigest()),
            ('names_sha256',hashlib.sha256(plain_names).hexdigest()),
            ('packed_names_sha256',hashlib.sha256(targets['D_NAMES.BIN']).hexdigest())]:
            if tested[key]!=actual:raise ValueError('UI layout proof belongs to another '+key)
        font_off,font_size=struct.unpack_from('<II',targets['WIN00.AFS'],8)
        if tested['font_sha256']!=hashlib.sha256(targets['WIN00.AFS'][font_off:font_off+font_size]).hexdigest():
            raise ValueError('UI layout proof belongs to another font')
        if tested['version']!=layout['version'] or tested['native_UI_cases']!=145:
            raise ValueError('UI layout proof version or required case coverage differs')
        report['ui_layout']=layout;report['ui_layout_native_validation']=tested
    if font_manifest.get('chapter_cards'):
        chapter=font_manifest['chapter_cards'];raw=(out/'chapter-card-native-test.json').read_bytes();tested=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=chapter['native_proof_sha256']:
            raise ValueError('Chapter-card proof fingerprint differs from manifest')
        if tested['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest() or tested['archive_sha256']!=hashlib.sha256(targets['WIN00.AFS']).hexdigest():
            raise ValueError('Chapter-card proof belongs to another executable/archive')
        if tested['component_sha256']!=hashlib.sha256((out/'chapter-card-component.json').read_bytes()).hexdigest():
            raise ValueError('Chapter-card component metadata differs from proof')
        if tested['title_slots']!=69 or tested['native_cases']!={'PRS':5,'PVM':15,'selection':69,'submission':99}:
            raise ValueError('Chapter-card proof coverage differs from required resource/title cases')
        report['chapter_cards']=chapter;report['chapter_card_native_validation']=tested
    if font_manifest.get('ui_images'):
        component=font_manifest['ui_images'];raw=(out/'ui-image-native-test.json').read_bytes();tested=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=component.get('proof_sha256'):
            raise ValueError('UI image proof fingerprint differs from manifest')
        if tested['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest() or tested['archive_sha256']!=hashlib.sha256(targets['WIN00.AFS']).hexdigest():
            raise ValueError('UI image proof belongs to another executable/archive')
        if tested['component_sha256']!=hashlib.sha256((out/'ui-image-component.json').read_bytes()).hexdigest():
            raise ValueError('UI image component metadata differs from proof')
        if tested['label_sprites']!=35 or tested['protected_sprites']!=277 or tested['unrelated_archive_members']!=87 or len(tested['resources'])!=3:
            raise ValueError('UI image proof lacks required sprite/resource coverage')
        report['ui_images']=component;report['ui_image_native_validation']=tested
    if font_manifest.get('embedded_dialogue'):
        embedded=font_manifest['embedded_dialogue'];raw=(out/'embedded-dialogue-native-test.json').read_bytes();tested=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=embedded.get('proof_sha256'):
            raise ValueError('Embedded dialogue proof fingerprint differs from manifest')
        if tested['executable_sha256']!=hashlib.sha256(targets['1ST_READ.BIN']).hexdigest():
            raise ValueError('Embedded dialogue proof belongs to another executable')
        if tested['component_sha256']!=hashlib.sha256((out/'embedded-dialogue-component.json').read_bytes()).hexdigest():
            raise ValueError('Embedded dialogue metadata differs from proof')
        font_off,font_size=struct.unpack_from('<II',targets['WIN00.AFS'],8)
        if tested['font_sha256']!=hashlib.sha256(targets['WIN00.AFS'][font_off:font_off+font_size]).hexdigest():
            raise ValueError('Embedded dialogue proof belongs to another font')
        if tested['commands']!=13 or tested['native_formatter_VM_cases']!=52 or tested['native_parser_commands']!=13 or tested['native_fallback_cases']!=2:
            raise ValueError('Embedded dialogue proof lacks required pointer/VM/fallback coverage')
        report['embedded_dialogue']=embedded;report['embedded_dialogue_native_validation']=tested
    return cue, disc, targets, raw_changes, report


def main():
    global VERSION
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--version',default=VERSION,help='Existing component version, e.g. 0.1.4')
    args = ap.parse_args()
    if not re.fullmatch(r'0\.\d+\.\d+',args.version):raise ValueError('Expected a 0.x.y component version')
    VERSION=args.version
    cue, disc, targets, changes, report = plan()
    print('English D_NAMES relocation:', json.dumps(report['names']))
    if 'battle' in report:print('English D_BMESS relocation:',json.dumps(report['battle']['disc_relocation']))
    print('Update {} raw sectors across {}; both-endian ISO fields and EDC/ECC regenerated.'.format(
        len(changes), len(report['changed_tracks'])))
    print('Includes native HD font and English names/menus'+(' and library' if 'library' in report else '')+(' and battle messages' if 'battle' in report else '')+
          ('. Complete drafted story commands are inserted; held commands stay original.' if 'scenario' in report else '. Story is not inserted.'))
    if not args.write:
        print('DRY RUN: no disc files written')
        return
    folder = ROOT / 'work/output' / VERSION / 'disc'
    folder.mkdir(parents=True, exist_ok=True)
    tracks = [ROOT / 'Seireiki Rayblade (Japan) (Track {}).bin'.format(n) for n in range(1, 6)]
    for path in tracks:
        dest = folder / path.name
        if dest.resolve() == path.resolve():
            raise ValueError('Refusing to modify original track')
        shutil.copyfile(path, dest)
    for name in report['changed_tracks']:
        with (folder / name).open('r+b') as fh:
            for path, offset, raw in changes:
                if path == name:
                    fh.seek(offset)
                    fh.write(raw)
    title = ('Rayblade Boot Diagnostic ' if 'diagnostic' in report else 'Rayblade English Test ') + VERSION
    target_cue = folder / (title + '.cue')
    target_cue.write_text(cue.read_text(), encoding='utf-8')
    starts = [0, 450, 45000, 56432, 57373]
    offsets = [0, 150 * SECTOR, 0, 150 * SECTOR, 225 * SECTOR]
    gdi = ['5'] + ['{} {} {} 2352 "{}" {}'.format(i + 1, starts[i], 4 if i in (0, 2, 4) else 0,
             tracks[i].name, offsets[i]) for i in range(5)]
    (folder / (title + '.gdi')).write_text('\n'.join(gdi) + '\n', encoding='utf-8')
    if 'font_native_validation' in report:
        shutil.copyfile(folder.parent/'FONT-LICENSE.txt',folder/'FONT-LICENSE.txt')
    finished = Disc(target_cue)
    before = {r['path']: r for r in disc.inventory()}
    after = {r['path']: r for r in finished.inventory()}
    if set(before) != set(after):
        raise ValueError('ISO file list changed')
    for name, entry in after.items():
        if name not in report['relocations'] and entry != before[name]:
            raise ValueError('Unrelated ISO entry changed: ' + name)
    for name, data in targets.items():
        entry = after[name]
        if finished.read(entry['lba'], entry['size']) != data:
            raise ValueError('Re-extracted file differs: ' + name)
    for path, off, expected in changes:
        with (folder / path).open('rb') as fh:
            fh.seek(off)
            actual = fh.read(SECTOR)
        if actual != expected or regenerate(actual) != actual:
            raise ValueError('Written sector checksum failed')
    report['validation'] = {'reextracted_files': 'all {} exact'.format(len(targets)), 'changed_sector_EDC_ECC': 'pass',
                            'unrelated_ISO_entries': 'unchanged', 'in_game': 'pending'}
    (folder.parent / 'english-disc-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    readme=(
        title + '\n\nOpen disc/' + title + '.gdi in Flycast.\n'
        'Drafted English name/menu tables and integrated Latin HD font.\n'+
        ('English library first draft is inserted, with an expanded native shared allocation.\n' if 'library' in report else 'Library text remains original Japanese and will show missing glyphs.\n')+
        ('English battle first drafts are inserted; battle-state, meaning and layout checks remain pending.\n' if 'battle' in report else 'Battle remains original Japanese and will show missing glyphs.\n')+
        ('50,273 complete drafted story commands are inserted through the native loader/formatter hooks.\n'
         '353 commands containing 503 held rows retain original Japanese, which the Latin font cannot display.\n'
         'Actual script loading, event navigation, save/load, memory and dialogue layout remain unverified.\n'
         if 'scenario' in report else 'Story is still unpatched.\n')+
        'This build needs in-game menu/library, layout and memory checks. It is not a complete translation.\n')
    if 'diagnostic' in report:
        readme=title+'\n\n'+report['diagnostic']['purpose']+'\n'+report['diagnostic']['restriction']+'\nThis is a restricted diagnostic, not a full translation candidate.\n'
    (folder.parent / 'READ-ME.txt').write_text(readme,encoding='utf-8')
    print('PASS: re-extracted all {} files, unchanged unrelated ISO entries, valid changed-sector EDC/ECC.'.format(len(targets)))
    print('Local test disc:', folder / (title + '.gdi'))


if __name__ == '__main__':
    main()
