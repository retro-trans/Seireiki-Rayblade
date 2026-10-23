"""Build the native Latin HD font test disc. Defaults to dry run.

Verifies both original files against the patch manifest; modifies a copy of
Track 5 only; regenerates changed-sector MODE1 EDC/ECC. Other tracks are copied
unchanged. Re-extracts both files from the finished disc and checks equality.
"""
import argparse
import hashlib
import json
import shutil
from build_font4x_patch import ROOT,VERSION
from build_test_disc import regenerate
from disc_inventory import Disc,SECTOR


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    cue=next(ROOT.glob('*.cue'));disc=Disc(cue)
    out=ROOT/'work/output'/VERSION
    manifest=json.loads((out/'font4x-patch.json').read_text(encoding='utf-8'))
    inventory=json.loads((ROOT/'work/source/disc-inventory.json').read_text())
    changes={};targets={};entries={}
    for name,record in manifest['files'].items():
        entry=next(v for v in inventory['files'] if v['path']==name);entries[name]=entry
        source=disc.read(entry['lba'],entry['size']);target=(out/name).read_bytes()
        assert len(source)==len(target)==record['size'],'File size changed'
        assert hashlib.sha256(source).hexdigest()==record['source_sha256'],'Original file mismatch'
        assert hashlib.sha256(target).hexdigest()==record['target_sha256'],'Candidate file mismatch'
        targets[name]=target;different=0
        for offset in range(0,len(source),2048):
            if source[offset:offset+2048]!=target[offset:offset+2048]:
                lba=entry['lba']+offset//2048
                if lba in changes:raise ValueError('Overlapping file edits')
                changes[lba]=target[offset:offset+2048];different+=1
        print('{}: {} changed logical sectors, verified SHA256.'.format(name,different))
    track=next(t for t in disc.tracks if t['start_lba']<=min(changes)<t['end_lba'])
    if not max(changes)<track['end_lba']:raise ValueError('Changes cross data tracks')
    raw_changes=[]
    with track['path'].open('rb') as fh:
        for lba,payload in changes.items():
            offset=(track['index']+lba-track['start_lba'])*SECTOR
            fh.seek(offset);raw=fh.read(SECTOR)
            assert regenerate(raw)==raw,'Original EDC/ECC mismatch'
            patched=bytearray(raw);patched[16:16+len(payload)]=payload
            raw_changes.append((offset,regenerate(patched)))
    folder=out/'disc'
    print('Copy five original tracks to {}; patch {} raw sectors.'.format(folder,len(raw_changes)))
    print('Native Latin font, no emulator texture replacement. Untranslated Japanese will not render correctly.')
    if not args.write:print('DRY RUN: no disc files written');return
    folder.mkdir(parents=True,exist_ok=True)
    files=[ROOT/('Seireiki Rayblade (Japan) (Track {}).bin'.format(i)) for i in range(1,6)]
    for path in files:
        destination=folder/path.name
        if destination.resolve()==path.resolve():raise ValueError('Refusing to modify original')
        shutil.copyfile(path,destination)
    with (folder/track['path'].name).open('r+b') as fh:
        for offset,raw in raw_changes:fh.seek(offset);fh.write(raw)
    title='Rayblade Latin HD '+VERSION
    test_cue=folder/(title+'.cue');test_cue.write_text(cue.read_text(),encoding='utf-8')
    starts=[0,450,45000,56432,57373];offsets=[0,150*SECTOR,0,150*SECTOR,225*SECTOR]
    lines=['5']+['{} {} {} 2352 "{}" {}'.format(i+1,starts[i],4 if i in (0,2,4) else 0,files[i].name,offsets[i]) for i in range(5)]
    (folder/(title+'.gdi')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    finished=Disc(test_cue)
    for name,target in targets.items():
        entry=entries[name];actual=finished.read(entry['lba'],entry['size'])
        assert actual==target,'Re-extracted candidate mismatch: '+name
        print('PASS: re-extracted {} matches candidate.'.format(name))
    (out/'READ-ME.txt').write_text(
        'Rayblade Latin HD '+VERSION+' - experimental font test\n\n'
        'Open disc/'+title+'.gdi in Flycast. No texture pack is used.\n'
        'Latin glyphs are rerasterized at 4x source detail. Display size stays native.\n'
        'Text surfaces use up to 4x per axis, capped at 1024 and a 2 MiB CPU text budget.\n'
        'A 512px logical line is 2x horizontally; memory fallback may reduce detail further.\n'
        'This is a Latin-only font test, not an English translation. Japanese text is incompatible.\n'
        'See CHANGELOG.md and work/ui for validation coverage. Full gameplay testing remains required.\n',encoding='utf-8')
    print('Built local native HD font test disc:',folder)


if __name__=='__main__':main()
