"""Make local test disc paths portable; also write a five-track GDI.

Default is dry-run. Copies only the four unchanged small tracks; the already
patched fifth track stays in place. Original files remain read-only.
"""
import argparse
import shutil
from disc_inventory import Disc, SECTOR
from build_font_patch import ROOT, VERSION


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    cue=next(ROOT.glob('*.cue'));disc=Disc(cue)
    out=ROOT/'work/output'/VERSION/'disc'
    files=[ROOT/'Seireiki Rayblade (Japan) (Track {}).bin'.format(i) for i in range(1,6)]
    data={t['number']:t for t in disc.tracks}
    starts=[0,data[1]['end_lba']+150,45000,data[3]['end_lba']+150,data[5]['start_lba']]
    offsets=[0,150*SECTOR,0,150*SECTOR,225*SECTOR]
    print('Copy four unchanged tracks: {:,} bytes'.format(sum(p.stat().st_size for p in files[:4])))
    print('Keep existing patched Track 5. Write relative-path CUE and GDI to {}'.format(out))
    print('GDI track starts:',starts,'file offsets:',offsets)
    if not args.write:
        print('DRY RUN: no files written');return
    if not (out/files[4].name).is_file():raise ValueError('Build patched test disc first')
    for path in files[:4]:shutil.copyfile(path,out/path.name)
    (out/('Rayblade VWF '+VERSION+'.cue')).write_text(cue.read_text(),encoding='utf-8')
    rows=['5']
    for i,path in enumerate(files):
        rows.append('{} {} {} 2352 "{}" {}'.format(i+1,starts[i],4 if i in (0,2,4) else 0,path.name,offsets[i]))
    (out/('Rayblade VWF '+VERSION+'.gdi')).write_text('\n'.join(rows)+'\n',encoding='utf-8')
    print('Wrote portable emulator test descriptors')


if __name__=='__main__':main()
