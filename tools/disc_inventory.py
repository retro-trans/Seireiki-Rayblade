"""Read-only Redump CUE inventory/extraction. Default is a dry run.

Map each data track from its first INDEX 01 sector's actual MSF header.
This handles the split high-density data tracks in Rayblade's five-track dump.
Original tracks are opened only in binary read mode.
"""
import argparse
import fnmatch
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTOR = 2352
PAYLOAD = 2048
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def bcd(v):
    return (v >> 4) * 10 + (v & 15)


def msf(value):
    m, s, f = map(int, value.split(':'))
    return (m * 60 + s) * 75 + f


class Disc:
    def __init__(self, cue):
        self.cue = cue
        self.tracks = []
        filename = mode = None
        for line in cue.read_text(encoding='utf-8-sig').splitlines():
            match = re.match(r'\s*FILE "(.+)" BINARY', line)
            if match:
                filename = match.group(1)
            match = re.match(r'\s*TRACK (\d+) (\S+)', line)
            if match:
                number, mode = int(match.group(1)), match.group(2)
            match = re.match(r'\s*INDEX 01 ([\d:]+)', line)
            if match and mode == 'MODE1/2352':
                path = (cue.parent / filename).resolve()
                index = msf(match.group(1))
                with path.open('rb') as f:
                    f.seek(index * SECTOR)
                    header = f.read(16)
                if header[:12] != SYNC or header[15] != 1:
                    raise ValueError('Invalid MODE1 header: {}'.format(filename))
                lba = (bcd(header[12]) * 60 + bcd(header[13])) * 75 + bcd(header[14]) - 150
                count = path.stat().st_size // SECTOR - index
                self.tracks.append(dict(number=number, path=path, index=index,
                                        start_lba=lba, end_lba=lba + count))
        self.hd = next(t for t in self.tracks if t['start_lba'] == 45000)

    def read(self, lba, size):
        data = bytearray()
        while len(data) < size:
            track = next((t for t in self.tracks if t['start_lba'] <= lba < t['end_lba']), None)
            if track is None:
                raise ValueError('No data track contains LBA {}'.format(lba))
            count = min((size - len(data) + PAYLOAD - 1) // PAYLOAD,
                        track['end_lba'] - lba)
            offset = (track['index'] + lba - track['start_lba']) * SECTOR
            with track['path'].open('rb') as f:
                f.seek(offset)
                raw = f.read(count * SECTOR)
            if len(raw) != count * SECTOR:
                raise EOFError('Short sector read')
            for n in range(count):
                pos = n * SECTOR
                if raw[pos:pos + 12] != SYNC or raw[pos + 15] != 1:
                    raise ValueError('Invalid sector at LBA {}'.format(lba + n))
                data.extend(raw[pos + 16:pos + 16 + PAYLOAD])
            lba += count
        return bytes(data[:size])

    def inventory(self):
        pvd = self.read(45016, PAYLOAD)
        if pvd[1:6] != b'CD001':
            raise ValueError('Missing ISO9660 descriptor')
        queue = [('', int.from_bytes(pvd[158:162], 'little'),
                  int.from_bytes(pvd[166:170], 'little'))]
        files, seen = [], set()
        while queue:
            prefix, lba, size = queue.pop(0)
            if (lba, size) in seen:
                continue
            seen.add((lba, size))
            data = self.read(lba, size)
            pos = 0
            while pos < len(data):
                length = data[pos]
                if not length:
                    pos = (pos // PAYLOAD + 1) * PAYLOAD
                    continue
                record = data[pos:pos + length]
                pos += length
                if len(record) < 34:
                    raise ValueError('Truncated directory record')
                raw_name = record[33:33 + record[32]]
                if raw_name in (b'\x00', b'\x01'):
                    continue
                name = raw_name.decode('ascii').split(';')[0]
                path = prefix + '/' + name if prefix else name
                extent = int.from_bytes(record[2:6], 'little')
                count = int.from_bytes(record[10:14], 'little')
                if record[25] & 2:
                    queue.append((path, extent, count))
                else:
                    files.append(dict(path=path, lba=extent, size=count))
        return sorted(files, key=lambda row: row['path'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extract', action='append', default=[], help='Case-insensitive path glob')
    ap.add_argument('--write', action='store_true', help='Write inventory and selected files after dry-run review')
    args = ap.parse_args()
    cues = list(ROOT.glob('*.cue'))
    if len(cues) != 1:
        raise ValueError('Expected one CUE')
    disc = Disc(cues[0])
    files = disc.inventory()
    for track in disc.tracks:
        print('Data track {}: LBAs {}..{}; INDEX 01 at sector {}'.format(
            track['number'], track['start_lba'], track['end_lba'] - 1, track['index']))
    print('{} files; {:,} logical bytes'.format(len(files), sum(x['size'] for x in files)))
    selected = [row for row in files if any(fnmatch.fnmatch(row['path'].upper(), pat.upper())
                                          for pat in args.extract)]
    for row in files:
        print('{} {:9d} LBA {:6d} {}'.format('EXTRACT' if row in selected else '       ',
              row['size'], row['lba'], row['path']))
    if not args.write:
        print('DRY RUN: no files written. Selected {} files.'.format(len(selected)))
        return
    destination = ROOT / 'work' / 'source' / 'disc'
    destination.mkdir(parents=True, exist_ok=True)
    for row in selected:
        target = (destination / row['path']).resolve()
        if destination.resolve() not in target.parents:
            raise ValueError('Unsafe destination path')
        content = disc.read(row['lba'], row['size'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        row['sha256'] = hashlib.sha256(content).hexdigest()
    manifest = dict(cue=cues[0].name, tracks=[dict(number=t['number'], filename=t['path'].name,
        index=t['index'], start_lba=t['start_lba'], end_lba=t['end_lba']) for t in disc.tracks], files=files)
    (ROOT / 'work' / 'source' / 'disc-inventory.json').write_text(
        json.dumps(manifest, indent=2), encoding='utf-8')
    print('Wrote manifest and {} extracted files. Original dump was read only.'.format(len(selected)))


if __name__ == '__main__':
    main()
