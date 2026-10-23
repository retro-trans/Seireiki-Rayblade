"""Repack WIN00 member data in index order without changing any payload.

Uses part of the original zero prefix to fit the larger English library,
retaining the original archive byte length. Native boot remains required.
"""
import argparse,hashlib,json,struct
from build_font_patch import ROOT


def digest(raw):return hashlib.sha256(raw).hexdigest()
def align(n):return (n+2047)//2048*2048


def repack(source,first_offset=0x70000):
    assert source[:4]==b'AFS\0';count=struct.unpack_from('<I',source,4)[0]
    header_end=8+count*8+8
    assert header_end<first_offset and first_offset%2048==0
    assert source[8+count*8:header_end]==b'\0'*8
    out=bytearray(source[:header_end]);out.extend(b'\0'*(first_offset-len(out)))
    records=[]
    for index in range(count):
        old,size=struct.unpack_from('<II',source,8+index*8);raw=source[old:old+size]
        assert len(raw)==size
        target=align(len(out));out.extend(b'\0'*(target-len(out)));out.extend(raw)
        struct.pack_into('<II',out,8+index*8,target,size)
        records.append({'index':index,'source_offset':old,'target_offset':target,'bytes':size,'sha256':digest(raw)})
    used=len(out);assert used<=len(source),(used,len(source))
    out.extend(b'\0'*(len(source)-len(out)))
    for row in records:
        off,size=struct.unpack_from('<II',out,8+row['index']*8)
        assert off>=first_offset and off%2048==0 and size==row['bytes']
        assert digest(out[off:off+size])==row['sha256']
    assert all(a['target_offset']+a['bytes']<=b['target_offset'] for a,b in zip(records,records[1:]))
    report={'source_sha256':digest(source),'target_sha256':digest(out),'archive_bytes':len(out),
        'first_data_offset':first_offset,'used_bytes':used,'spare_bytes':len(out)-used,
        'members':records,'validation':'All payload bytes and member IDs unchanged; table offsets in ascending order; non-overlapping sector-aligned extents'}
    return bytes(out),report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base-version',default='0.1.4')
    ap.add_argument('--diagnostic',action='store_true');ap.add_argument('--write',action='store_true');args=ap.parse_args()
    base=ROOT/'work/output'/args.base_version
    source=(base/'WIN00.AFS').read_bytes();result,report=repack(source)
    print(json.dumps({k:v for k,v in report.items() if k!='members'},indent=2))
    print('Library:',json.dumps(report['members'][52]))
    if args.diagnostic:
        old=ROOT/'work/output/0.1.8';manifest=json.loads((old/'font4x-patch.json').read_text('utf-8'))
        manifest.update(version='0.1.9',status='ordered archive boot diagnostic; not a full translation candidate')
        manifest['files']['WIN00.AFS']['target_sha256']=digest(result)
        manifest['diagnostic'].update(archive_from=args.base_version+' repacked in index order',
            purpose='Determine whether ordered archive member placement resolves the startup failure',
            first_member_offset=report['first_data_offset'])
        entry='''## 0.1.9 — ordered library archive startup diagnostic

- Repacked all 90 WIN00 archive members in index order with sector-aligned, non-overlapping extents starting at 0x70000. All member payload bytes and IDs remain unchanged, including the complete English library. The original archive byte length is retained by using part of its zero prefix. This tests the archive-placement cause isolated by 0.1.8, which reproduced the SH-4 startup exception with the previously booting 0.1.3 executable.
- Diagnostic executable and 64 KiB shared allocation remain 0.1.3. Do not open the English library in this restricted diagnostic. Full story candidate 0.1.7, original dump and prior builds remain unchanged; no release. Native file-loader compatibility and boot are pending this diagnostic run.

'''
        cp=ROOT/'CHANGELOG.md';old_log=cp.read_text('utf-8')
        assert '## 0.1.9 —' not in old_log
        print(entry)
    if not args.write:print('DRY RUN: no archive or diagnostic written.');return
    if args.diagnostic:
        out=ROOT/'work/output/0.1.9';(out/'text').mkdir(parents=True,exist_ok=True)
        (out/'WIN00.AFS').write_bytes(result);(out/'1ST_READ.BIN').write_bytes((old/'1ST_READ.BIN').read_bytes())
        for path in (old/'text').iterdir():
            if path.is_file():(out/'text'/path.name).write_bytes(path.read_bytes())
        (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
        (out/'archive-repack-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
        cp.write_text(old_log.replace('## 0.1.8 —',entry+'## 0.1.8 —',1),'utf-8')
        print('Wrote ordered archive diagnostic.')
    else:raise ValueError('Direct writes require an explicit diagnostic or integration composer')


if __name__=='__main__':main()
