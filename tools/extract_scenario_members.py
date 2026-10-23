"""Index and extract original scenario members, without guessing text boundaries.

Default is a dry run. Local script files and their manifest remain under the
ignored work/source directory. Game archives and original disc are read only.
"""
import argparse
import hashlib
import json
import struct
from pathlib import PureWindowsPath
from build_font_patch import ROOT


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    data=(ROOT/'work/source/disc/D_SCE.AFS').read_bytes()
    if data[:4]!=b'AFS\0':raise ValueError('Not an AFS archive')
    count=struct.unpack_from('<I',data,4)[0]
    members=[struct.unpack_from('<II',data,8+n*8) for n in range(count)]
    for off,size in members:
        if off<8+count*8 or off+size>len(data):raise ValueError('Member out of bounds')
    off,size=members[-1];listing=data[off:off+size].decode('ascii')
    labels=[line.strip() for line in listing.splitlines() if line.strip()]
    if len(labels)==count and labels[-1].lower().endswith('.als'):labels.pop()
    if len(labels)!=count-1:raise ValueError('Archive filename list/count mismatch')
    rows=[];seen=set()
    for index,(label,(off,size)) in enumerate(zip(labels,members[:-1])):
        name=PureWindowsPath(label).name
        if name.lower() in seen or not name.lower().endswith('.bin') or name in ('.','..'):raise ValueError('Unsafe or duplicate member name')
        seen.add(name.lower());payload=data[off:off+size]
        rows.append({'id':'scenario.{:03d}'.format(index),'index':index,'name':name,'offset':off,'size':size,
                     'sha256':hashlib.sha256(payload).hexdigest(),'text_extraction_status':'opcode boundaries pending'})
    print('Scenario archive: {} script members; {} bytes; one filename-list member excluded.'.format(len(rows),sum(r['size'] for r in rows)))
    print('Sample:',json.dumps(rows[:3]));print('Last member:',rows[-1]['name'])
    if not args.write:print('DRY RUN: no scenario files written');return
    out=ROOT/'work/source/scenario';out.mkdir(parents=True,exist_ok=True)
    for row in rows:(out/row['name']).write_bytes(data[row['offset']:row['offset']+row['size']])
    result={'archive_sha256':hashlib.sha256(data).hexdigest(),'script_count':len(rows),'members':rows}
    (out/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Extracted original script members locally; no text marked translated')


if __name__=='__main__':main()
