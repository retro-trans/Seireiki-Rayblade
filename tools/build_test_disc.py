"""Create a local BIN/CUE test build; default is a dry run.

Copies the modified data track, references other original tracks read-only,
and regenerates EDC/ECC only for the changed MODE1 sectors.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from disc_inventory import Disc, SECTOR
from build_font_patch import ROOT, START, END, VERSION

EDC=[]
FORWARD=[]
BACKWARD=[0]*256
for i in range(256):
    x=i
    for _ in range(8):
        x=(x>>1) ^ (0xd8018001 if x&1 else 0)
    EDC.append(x)
    y=i<<1
    if y&256:y^=0x11d
    FORWARD.append(y)
    BACKWARD[i^y]=i


def ecc(data, major_count, minor_count, major_mult, minor_inc):
    out=bytearray(major_count*2)
    size=major_count*minor_count
    for major in range(major_count):
        index=(major>>1)*major_mult+(major&1)
        a=b=0
        for _ in range(minor_count):
            value=data[index]
            index=(index+minor_inc)%size
            a^=value;b^=value;a=FORWARD[a]
        a=BACKWARD[FORWARD[a]^b]
        out[major]=a;out[major+major_count]=a^b
    return out


def regenerate(raw):
    out=bytearray(raw)
    checksum=0
    for value in out[:0x810]:checksum=(checksum>>8)^EDC[(checksum^value)&255]
    out[0x810:0x814]=checksum.to_bytes(4,'little')
    out[0x814:0x81c]=bytes(8)
    out[0x81c:0x8c8]=ecc(out[12:],86,24,2,86)
    out[0x8c8:0x930]=ecc(out[12:],52,43,86,88)
    return bytes(out)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    cue=next(ROOT.glob('*.cue'));disc=Disc(cue)
    manifest=json.loads((ROOT/'work/source/disc-inventory.json').read_text())
    entry=next(row for row in manifest['files'] if row['path']=='1ST_READ.BIN')
    source=disc.read(entry['lba'],entry['size'])
    target=(ROOT/'work/output'/VERSION/'1ST_READ.VWF.BIN').read_bytes()
    expected=json.loads((ROOT/'work/output'/VERSION/'font-patch.json').read_text())
    if hashlib.sha256(source).hexdigest()!=expected['source_sha256']:
        raise ValueError('Original executable SHA256 mismatch')
    if hashlib.sha256(target).hexdigest()!=expected['target_sha256'] or len(source)!=len(target):
        raise ValueError('Candidate executable mismatch')
    track=next(t for t in disc.tracks if t['start_lba']<=entry['lba']<t['end_lba'])
    changes=[]
    with track['path'].open('rb') as fh:
        for logical in range(START//2048,(END-1)//2048+1):
            raw_offset=(track['index']+entry['lba']+logical-track['start_lba'])*SECTOR
            fh.seek(raw_offset);old=fh.read(SECTOR)
            if regenerate(old)!=old:
                raise ValueError('Source EDC/ECC validation failed at 0x{:x}'.format(raw_offset))
            patched=bytearray(old)
            lo=max(START,logical*2048);hi=min(END,(logical+1)*2048)
            p=16+lo-logical*2048
            if patched[p:p+hi-lo]!=source[lo:hi]:raise ValueError('Source sector mismatch')
            patched[p:p+hi-lo]=target[lo:hi]
            changes.append((raw_offset,regenerate(patched)))
    out=ROOT/'work/output'/VERSION/'disc'
    print('Copy {} ({:,} bytes)'.format(track['path'].name,track['path'].stat().st_size))
    print('Update {} sectors, regenerating and validating MODE1 EDC/ECC.'.format(len(changes)))
    print('CUE references the unchanged original tracks by absolute path.')
    print('Destination: {}'.format(out))
    if not args.write:
        print('DRY RUN: no disc files written')
        return
    out.mkdir(parents=True,exist_ok=True)
    track_out=out/track['path'].name
    if track_out.resolve()==track['path'].resolve():raise ValueError('Refusing to modify original')
    shutil.copyfile(track['path'],track_out)
    with track_out.open('r+b') as fh:
        for offset,sector in changes:
            fh.seek(offset);fh.write(sector)
    def replace(match):
        path=(ROOT/match.group(1)).resolve()
        return 'FILE "{}" BINARY'.format(path.name if path==track['path'] else str(path))
    cue_text=re.sub(r'FILE "(.+)" BINARY',replace,cue.read_text())
    cue_out=out/('Rayblade VWF '+VERSION+'.cue')
    cue_out.write_text(cue_text,encoding='utf-8')
    patched_disc=Disc(cue_out)
    rebuilt=patched_disc.read(entry['lba'],entry['size'])
    if rebuilt!=target:raise ValueError('Re-extracted candidate differs from executable')
    print('PASS: re-extracted executable matches candidate SHA256.')
    print('Local test disc: {}'.format(cue_out))


if __name__=='__main__':
    main()
