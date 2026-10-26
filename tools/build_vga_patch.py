"""Merge Rolly's retail VGA changes into the English build. Dry by default.

Download the free v1.0 archive from the credited source into incoming/vga-reference
and extract it there. Reference game executables are never committed or shipped.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION, PRIOR = '0.7.1', '0.1.44'
OUT = ROOT / 'work/output/vga-component'
REFERENCE = ROOT / 'incoming/vga-reference'
SOURCE_URL = 'https://segasky.itch.io/seireiki-rayblade-vga-patch-for-sega-dreamcast'
ZIP_SHA = '366a520dbdcecaacab7651422c4ec881af1edcff68489d7f92ca09d7f67570d7'
ORIGINAL_SHA = '08f34a6a8b55a04c03bfe4e6d3a294792d8113e67f79c7759f9efbaeff29b9a5'
REFERENCE_SHA = '8eb39130a289aae14eead0236aace2116c3549d9e39c2267853a81fc2a406469'
ENGLISH_SHA = '39878d6b332b3f4ef1bd59a1b27d69de87f7b4695ddfcb4c98138c419e42d1fd'
CODE_RANGES = [(0x96d24, 0x96d26), (0xbbe00, 0xbbe10),
               (0xbc150, 0xbc152), (0xda5c0, 0xda7b5)]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text('utf-8'))


def compose():
    from disc_inventory import Disc
    original_disc = Disc(next(ROOT.glob('*.cue')))
    entries = {r['path']: r for r in original_disc.inventory()}
    original = original_disc.read(entries['1ST_READ.BIN']['lba'], entries['1ST_READ.BIN']['size'])
    reference = next(REFERENCE.glob('**/rolly-dc-rayblade-vga-patch-v.1.0/1ST_READ.BIN')).read_bytes()
    package = REFERENCE / 'rolly-dc-rayblade-vga-patch-v.1.0.zip'
    assert digest(package.read_bytes()) == ZIP_SHA
    assert digest(original) == ORIGINAL_SHA and digest(reference) == REFERENCE_SHA
    english = (ROOT / 'work/output' / PRIOR / '1ST_READ.BIN').read_bytes()
    assert digest(english) == ENGLISH_SHA and len(original) == len(reference) == len(english)
    changed = {i for i in range(len(original)) if original[i] != reference[i]}
    allowed = {i for a, b in CODE_RANGES for i in range(a, b)}
    assert len(changed) == 497 and changed <= allowed
    # Verify complete replaced routines, including unchanged bytes within them.
    for a, b in CODE_RANGES:
        assert english[a:b] == original[a:b], ('English/VGA code overlap', hex(a))
    target = bytearray(english)
    for i in changed:
        target[i] = reference[i]
    target = bytes(target)
    assert {i for i in range(len(target)) if target[i] != english[i]} == changed
    original_ip = original_disc.read(45000, 32768)
    dcp = next(REFERENCE.glob('**/rolly-dc-rayblade-vga-patch-v.1.0/*.dcp'))
    with zipfile.ZipFile(dcp) as archive:
        reference_ip = archive.read('bootsector/IP.BIN')
    english_ip = Disc(ROOT / f'work/output/{PRIOR}/disc/Rayblade English Test {PRIOR}.cue').read(45000, 32768)
    assert original_ip[0x3d] == english_ip[0x3d] == ord('0')
    assert reference_ip[0x3d] == ord('1')
    target_ip = bytearray(english_ip)
    target_ip[0x3d] = ord('1')
    # Only declare VGA compatibility; retain Japanese region and our disc icon.
    assert bytes(target_ip[:0x3d] + target_ip[0x3e:]) == english_ip[:0x3d] + english_ip[0x3e:]
    report = {
        'version': VERSION, 'source_build': PRIOR, 'date': '2026-10-26',
        'kind': 'Local VGA compatibility test; no public release',
        'source': {'author': 'Rolly (SEGA-SKY)', 'url': SOURCE_URL, 'reference_version': '1.0',
                   'archive_sha256': ZIP_SHA, 'retail_executable_sha256': REFERENCE_SHA,
                   'original_executable_sha256': ORIGINAL_SHA},
        'executable_sha256': digest(target), 'english_base_sha256': digest(english),
        'changed_executable_bytes': len(changed),
        'ranges': [{'start': hex(a), 'end_exclusive': hex(b),
                    'original_sha256': digest(original[a:b]), 'target_sha256': digest(target[a:b])}
                   for a, b in CODE_RANGES],
        'boot': {'lba': 45000, 'size': 32768, 'offset': '0x3d', 'before': '0', 'after': '1',
                 'source_sha256': digest(english_ip), 'target_sha256': digest(target_ip),
                 'scope': 'Only VGA flag; original region selection and English disc artwork retained'},
        'method': 'Exact retail reference executable deltas merged after original-byte conflict checks',
        'preserved': 'All English executable bytes outside the 497 reference changes; all text/font/archive/movie payloads',
        'pending': ['Cold boot on a Dreamcast with VGA cable/box and on NTSC/PAL consoles',
                    'Opening movies, dialogue, battle and save/load in VGA; non-VGA cable regression'],
        'release': False,
    }
    return target, bytes(target_ip), report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    exe, ip, report = compose()
    print('PASS: 497 non-conflicting executable byte changes; boot VGA flag 0 -> 1.')
    print('Target executable:', digest(exe))
    print('Retains Japanese region, translated disc artwork, and every English text/font component.')
    if not args.write:
        print('DRY RUN: no files written.')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '1ST_READ.BIN').write_bytes(exe)
    (OUT / 'IP.BIN').write_bytes(ip)
    (OUT / 'component-report.json').write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
