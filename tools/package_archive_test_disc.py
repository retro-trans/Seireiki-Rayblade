"""Shared read-only plan for one additional native AFS/PVR file in a test disc."""
import json
import re

from build_bitmap_font import ROOT, digest
from build_test_disc import regenerate
from disc_inventory import Disc, SECTOR


def substitute_payload_sector(raw,source,target):
    """Patch a full or partial final file sector without shrinking padding."""
    assert len(raw)==SECTOR and regenerate(raw)==raw
    assert 0<len(source)==len(target)<=2048
    assert raw[16:16+len(source)]==source
    result=bytearray(raw)
    result[16:16+len(target)]=target
    assert len(result)==SECTOR and result[16+len(target):2064]==raw[16+len(target):2064]
    return regenerate(result)


def plan_archive_patch(*, version, prior_version, archive_name, draft_dir, candidate,
                       slug, proof_count_key, proof_count, prior_proof,
                       description, pending, readme, replace_existing=False, proof_scope=None):
    assert re.fullmatch(r'[A-Z0-9_]+\.(?:AFS|PVR)', archive_name)
    assert re.fullmatch(r'[a-z-]+', slug)
    base = ROOT / 'work/output' / prior_version
    previous = json.loads((base / 'english-disc-report.json').read_text('utf-8'))
    assert previous['version'] == prior_version
    assert previous['validation']['reextracted_files'] == f'all {len(previous["files"])} exact'
    assert previous['validation']['changed_sector_EDC_ECC'] == 'pass'
    assert previous['validation']['unrelated_track_bytes'] == 'all unchanged'
    cue = base / 'disc' / f'Rayblade English Test {prior_version}.cue'
    disc = Disc(cue)
    entries = {r['path']: r for r in disc.inventory()}
    inherited = {}
    for name, record in previous['files'].items():
        row = entries[name]
        raw = disc.read(row['lba'], row['size'])
        assert len(raw) == record['size'] and digest(raw) == record['sha256']
        path = base / ('text/' + name if name in ('D_NAMES.BIN', 'D_BMESS.BIN') else name)
        assert path.read_bytes() == raw
        inherited[name] = raw
    historical = list(previous['historical_native_evidence'])
    if prior_proof is not None:
        file, key, associated_archive = prior_proof
        proof_bytes = (base / file).read_bytes()
        old_proof = json.loads(proof_bytes)
        assert digest(proof_bytes) == previous[key]
        if associated_archive is None:
            # Coordinated components can test more than one archive. Check
            # every identity before retaining that report as historical.
            assert old_proof['archives']
            assert all(old_proof['archives'][name] == digest(inherited[name])
                       for name in old_proof['archives'])
        else:
            assert old_proof['archive_sha256'] == digest(inherited[associated_archive])
        assert not any(item['file'] == file for item in historical)
        historical.append({'file': file, 'sha256': digest(proof_bytes),
                           'actual_tested_build': old_proof['source_build'],
                           'executable_sha256': old_proof['executable_sha256'],
                           'scope': 'Historical native component report; original scope and limitations retained'})
    for item in historical:
        data = (base / item['file']).read_bytes()
        assert digest(data) == item['sha256'] and json.loads(data)['executable_sha256'] == item['executable_sha256']
    target = (draft_dir / archive_name).read_bytes()
    component = json.loads((draft_dir / 'component-report.json').read_text('utf-8'))
    proof_bytes = (draft_dir / 'native-test.json').read_bytes()
    proof = json.loads(proof_bytes)
    built = candidate()
    assert target == built[0] and component == built[1]
    assert proof['archive_sha256'] == component['target_archive_sha256'] == digest(target)
    assert proof['executable_sha256'] == digest(inherited['1ST_READ.BIN'])
    assert proof['native_guard_and_ABI'] == 'pass' and proof[proof_count_key] == proof_count
    assert proof['archive_bytes_outside_declared_edits'] == 'exact'
    row = entries[archive_name]
    source = disc.read(row['lba'], row['size'])
    original_disc = Disc(next(ROOT.glob('*.cue')))
    original_row = next(r for r in original_disc.inventory() if r['path'] == archive_name)
    assert row == original_row
    original = original_disc.read(row['lba'], row['size'])
    if replace_existing:
        assert archive_name in inherited and source == inherited[archive_name]
    else:
        assert archive_name not in inherited and original == source
    assert digest(source) == component['source_archive_sha256'] and len(source) == len(target)
    changed = [n for n in range((len(target)+2047) // 2048)
               if source[n*2048:(n+1)*2048] != target[n*2048:(n+1)*2048]]
    changes, handles = [], {}
    try:
        for n in changed:
            lba = row['lba'] + n
            track = next(t for t in disc.tracks if t['start_lba'] <= lba < t['end_lba'])
            name = track['path'].name
            if name not in handles:
                handles[name] = track['path'].open('rb')
            offset = (track['index'] + lba - track['start_lba']) * SECTOR
            handles[name].seek(offset)
            raw = handles[name].read(SECTOR)
            patch = substitute_payload_sector(raw,source[n*2048:(n+1)*2048],target[n*2048:(n+1)*2048])
            changes.append((name, offset, patch))
    finally:
        for handle in handles.values():
            handle.close()
    targets = dict(inherited, **{archive_name: target})
    if tuple(map(int,version.split('.'))) >= (0,1,38):
        from afs_layout import require_native_layouts
        require_native_layouts(targets)
    names = re.findall(r'FILE "(.+)" BINARY', cue.read_text('utf-8'))
    assert len(names) == 5
    key = slug.replace('-', '_')
    old_locations = sum(source[n:n+2048] != original[n:n+2048] for n in range(0,len(source),2048))
    new_locations = sum(target[n:n+2048] != original[n:n+2048] for n in range(0,len(target),2048))
    unchanged_payloads = len(inherited) - int(replace_existing)
    report = {'version': version, 'source_build': prior_version, 'kind': description,
              'movie_extent': previous['movie_extent'], 'movie_extents': previous['movie_extents'],
              'movies': previous['movies'], 'original_audio_sector_count': 4041,
              'new_changed_sectors': len(changes),
              'total_changed_sector_locations_from_original': previous['total_changed_sector_locations_from_original'] - old_locations + new_locations,
              'files': {n: {'size': len(raw), 'sha256': digest(raw)} for n, raw in targets.items()},
              'historical_native_evidence': historical,
              key + '_component': component, key + '_native_proof': proof,
              key + '_proof_sha256': digest(proof_bytes),
              'inherited_components': f'All {unchanged_payloads} unaffected preceding game payloads exact {prior_version}',
              'archive_replaces_existing_component': replace_existing,
              'source_archive_changed_locations_from_original': old_locations,
              'target_archive_changed_locations_from_original': new_locations,
              'component_manifest_name': slug + '-component.json',
              'readme_component_text': readme,
              'readme_movie_text': previous['readme_movie_text'],
              'proof_scope': proof_scope or 'New image-archive native PRS/texture-info and independent structure/pixel checks only. No native archive I/O, GPU or live reachability/appearance proof. Historical reports retain their original tested identities.',
              'pending': list(dict.fromkeys([*pending, *previous['pending']])), 'release': False}
    return disc, cue, inherited, targets, changes, names, historical, report
