"""Build 0.1.8 archive-only boot diagnostic: 0.1.3 code plus 0.1.4 WIN00.

This intentionally isolates an observed startup regression. It is not the
current full translation candidate. Dry run before writing any components.
"""
import argparse,copy,hashlib,json,struct
from build_font_patch import ROOT

VERSION='0.1.8'
def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    old=ROOT/'work/output/0.1.3';library=ROOT/'work/output/0.1.4'
    manifest=json.loads((old/'font4x-patch.json').read_text('utf-8'))
    lm=json.loads((library/'font4x-patch.json').read_text('utf-8'))
    exe=(old/'1ST_READ.BIN').read_bytes();afs=(library/'WIN00.AFS').read_bytes();prior=(old/'WIN00.AFS').read_bytes()
    assert sha(exe)==manifest['files']['1ST_READ.BIN']['target_sha256']
    assert sha(afs)==lm['files']['WIN00.AFS']['target_sha256']
    assert sha(prior)==manifest['files']['WIN00.AFS']['target_sha256']
    count=struct.unpack_from('<I',afs,4)[0]
    for index in range(count):
        if index==52:continue
        off,size=struct.unpack_from('<II',afs,8+8*index)
        assert (off,size)==struct.unpack_from('<II',prior,8+8*index)
        assert afs[off:off+size]==prior[off:off+size]
    result=copy.deepcopy(manifest);result.update(version=VERSION,
        status='archive-only startup diagnostic; not a full translation candidate',
        diagnostic={'executable_from':'0.1.3','archive_from':'0.1.4','changed_library_member':52,
            'shared_allocation_bytes':65536,'restriction':'Do not open the English library with this deliberately original-sized allocation',
            'purpose':'Distinguish library archive relocation from the 0.1.4 shared-allocation literal change'})
    result['files']['WIN00.AFS']['target_sha256']=sha(afs)
    copied={name:(old/'text'/name).read_bytes() for name in
        ['D_NAMES.BIN','D_NAMES.en.dec.bin','names-component-report.json']}
    entry='''## 0.1.8 — archive-only startup diagnostic

- Built a diagnostic using the previously booting 0.1.3 executable with the 0.1.4 library archive. All 89 archive members other than D_PAPER retain their original addresses/bytes; the executable and native shared allocation remain exactly 0.1.3. This isolates archive relocation from the allocation change after 0.1.4, 0.1.5 and 0.1.6 stopped during startup with Flycast's SH-4 blocked-exception error. It is not a full translation candidate. Do not open the English library with this intentionally unchanged 64 KiB allocation.
- Full story candidate 0.1.7 has been packaged: all five patched files re-extract exactly, 2,150 changed raw sectors pass EDC/ECC, and unrelated ISO entries are unchanged. The updated executable passed battle regressions and inherited code-byte checks. Live startup is not validated; the existing crash remains under investigation. Prior builds/original dump are unchanged; no release.

'''
    cp=ROOT/'CHANGELOG.md';old_log=cp.read_text('utf-8')
    assert '## 0.1.8 —' not in old_log and '## 0.1.7 —' in old_log
    print(json.dumps(result['diagnostic'],indent=2));print('Executable SHA',sha(exe));print('Archive SHA',sha(afs));print(entry)
    if not args.write:print('DRY RUN: no diagnostic components written.');return
    out=ROOT/'work/output'/VERSION;(out/'text').mkdir(parents=True,exist_ok=True)
    (out/'1ST_READ.BIN').write_bytes(exe);(out/'WIN00.AFS').write_bytes(afs)
    for name,raw in copied.items():(out/'text'/name).write_bytes(raw)
    (out/'font4x-patch.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    cp.write_text(old_log.replace('## 0.1.7 —',entry+'## 0.1.7 —',1),'utf-8')
    print('Wrote archive-only diagnostic components.')


if __name__=='__main__':main()
