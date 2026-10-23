"""Apply boot-tested ordered WIN00 layout to the full 0.1.7 story candidate.

Executable/text bytes and native proofs are reused only after exact hash
comparisons. No test disc is written here. Dry run before --write.
"""
import argparse,copy,json
from build_font_patch import ROOT
from build_scenario_patch import candidate_executable
from repack_win_archive import repack,digest

VERSION='0.1.10'


def compose():
    base=ROOT/'work/output/0.1.7';manifest=json.loads((base/'font4x-patch.json').read_text('utf-8'))
    exe=(base/'1ST_READ.BIN').read_bytes();expected,_=candidate_executable();assert exe==expected
    assert digest(exe)==manifest['files']['1ST_READ.BIN']['target_sha256']
    original=(base/'WIN00.AFS').read_bytes();assert digest(original)==manifest['files']['WIN00.AFS']['target_sha256']
    afs,packing=repack(original)
    proofs={}
    for name in ['scenario-native-test.json','battle-english-native-test.json','library-native-test.json']:
        raw=(base/name).read_bytes();proofs[name]=raw;p=json.loads(raw)
        if name!='library-native-test.json':assert p['executable_sha256']==digest(exe)
    component=json.loads((base/'text/scenario-component-report.json').read_text('utf-8'))
    for name,sha in component['working_file_sha256'].items():
        assert digest((ROOT/'work/translation/en/scenario'/name).read_bytes())==sha
    assert component['archive_sha256']==digest((base/'D_SCE.AFS').read_bytes())
    result=copy.deepcopy(manifest);result.update(version=VERSION,previous_build='0.1.7',
        status='ordered archive fix with full English story/menu/library/battle candidate; live validation pending')
    result['files']['WIN00.AFS']['target_sha256']=digest(afs)
    paper=packing['members'][52]
    assert paper['bytes']==result['library']['archive_member_bytes']
    result['library'].update(archive_member_offset=paper['target_offset'],
        unrelated_members='All 89 payloads unchanged; offsets rebuilt in member order',
        archive_repack_build=VERSION)
    result['archive_repack']={k:v for k,v in packing.items() if k!='members'}
    result['native_proof_reuse']={'tested_executable_version':'0.1.7','exact_executable_sha256':digest(exe),
        'story_and_battle_components':'unchanged','library_filter':'unchanged; all profile payload bytes retained',
        'font_payload':'unchanged; AFS member offset updated by repack'}
    files={name:(base/name).read_bytes() for name in manifest['files']};files['WIN00.AFS']=afs
    copied={**proofs}
    for path in (base/'text').iterdir():
        if path.is_file():copied['text/'+path.name]=path.read_bytes()
    return files,copied,result,packing


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,copied,manifest,packing=compose()
    print('Full build',VERSION,'keeps exact 0.1.7 executable/story/battle bytes.')
    print('Archive:',json.dumps(manifest['archive_repack'],indent=2))
    print('Library offset:',manifest['library']['archive_member_offset'],'size:',manifest['library']['archive_member_bytes'])
    entry='''## 0.1.10 — ordered archive fix with full story candidate

- Applied the ordered WIN00 layout to the full 0.1.7 story/font/menu/library/battle components. The executable, all 50,273 compiled English story commands, battle data, font payload and all 90 archive-member payload bytes are unchanged. Library metadata follows its new member offset. Reused native proofs only after matching exact executable/component hashes; this is not a claim of newly exercised game paths.
- The archive-only 0.1.8 comparison reproduced the startup exception with the previously booting 0.1.3 executable. The ordered 0.1.9 archive subsequently reached the actual title screen and passed live font-kernel/payload checks. The old library placement before archive member zero is therefore unsafe for this game loader. Repacking members in index order fixes that observed diagnostic boot, without shortening library text or increasing archive size.
- Full-build 0.1.10 packaging and gameplay/layout/save-load validation remain pending. The 503 held story rows, full VM coverage, independent meaning review and image UI/movie text remain unfinished. Prior builds and original dump are unchanged; no release.

'''
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8');assert '## 0.1.10 —' not in old
    print(entry)
    if not args.write:print('DRY RUN: no full-build components written.');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in {**files,**copied}.items():
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
    (out/'archive-repack-report.json').write_text(json.dumps(packing,indent=2)+'\n','utf-8')
    (out/'library-patch-report.json').write_text(json.dumps(manifest['library'],indent=2)+'\n','utf-8')
    cp.write_text(old.replace('## 0.1.9 —',entry+'## 0.1.9 —',1),'utf-8')
    print('Wrote full ordered-archive candidate components.')


if __name__=='__main__':main()
