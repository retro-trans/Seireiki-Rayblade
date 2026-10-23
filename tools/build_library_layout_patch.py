"""Compose measured library wrapping over 0.1.17. Default dry run."""
import argparse,json
from prepare_library_layouts import ROOT,VERSION,PRIOR,DEST,prepare,digest
from build_library_translation import build
from build_chapter_cards import repack


def compose():
    base=ROOT/'work/output'/PRIOR;recipe=json.loads(DEST.read_text('utf-8'));assert recipe==prepare()
    old_plain,old_packed,_=build()
    assert old_plain==(base/'text/D_PAPER.en.dec.bin').read_bytes() and old_packed==(base/'text/D_PAPER.BIN').read_bytes()
    plain,packed,component=build(section_overrides=recipe['sections'],version=VERSION)
    assert len(plain)==len(old_plain)
    assert sum(a!=b for a,b in zip(plain,old_plain))==recipe['inserted_breaks']+recipe['joined_breaks']
    assert all(a==b or (a,b) in [(0,253),(253,0)] for a,b in zip(old_plain,plain)), 'Only medium-font spaces and soft NL may be exchanged'
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    files.update({'text/'+p.name:p.read_bytes() for p in (base/'text').iterdir() if p.is_file()})
    for name in ('english-disc-report.json','READ-ME.txt','library-native-test.json','library-layout-native-test.json'):files.pop(name,None)
    archive,packing=repack(files['WIN00.AFS'],{52:packed});files['WIN00.AFS']=archive
    files['text/D_PAPER.en.dec.bin']=plain;files['text/D_PAPER.BIN']=packed;files['text/library-component-report.json']=json.dumps(component,indent=2).encode()
    manifest=json.loads(files['font4x-patch.json']);manifest.update(version=VERSION,previous_build=PRIOR,status='Measured library wrapping candidate; fresh native checks and packaging pending')
    manifest['files']['WIN00.AFS']['target_sha256']=digest(archive)
    member=packing['members'][52]
    manifest['library'].update(version=VERSION,archive_member_offset=member['target_offset'],archive_member_bytes=len(packed),decoded_library_bytes=len(plain),library_payload_sha256=digest(plain),archive_repack_build=VERSION,pending=['Fresh native library filter/layout checks','Live library navigation and appearance'])
    manifest['library_layout']={k:v for k,v in recipe.items() if k!='sections'}
    manifest['library_layout'].update(recipe_sha256=digest(DEST.read_bytes()),library_sha256=digest(plain),native_validation='pending',live_validation='pending')
    manifest['archive_repack']={k:v for k,v in packing.items() if k!='members'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Executable/font, names/UI, story, battle and chapter resources byte-exact; fresh library and archive checks required'}
    chapter=json.loads(files['chapter-card-component.json']);chapter.update(version=VERSION,source_build=PRIOR,archive_sha256=digest(archive));files['chapter-card-component.json']=json.dumps(chapter,indent=2).encode()
    files['font4x-patch.json']=json.dumps(manifest,indent=2).encode();files['library-patch-report.json']=json.dumps(manifest['library'],indent=2).encode();files['archive-repack-report.json']=json.dumps(packing,indent=2).encode()
    return files,manifest,component


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args();files,manifest,component=compose()
    print(json.dumps({'version':VERSION,'layout':manifest['library_layout'],'decoded_bytes':component['output_decoded_size'],'packed_bytes':component['output_compressed_size'],'archive_spare_bytes':manifest['archive_repack']['spare_bytes']},indent=2))
    if not args.write:print('DRY RUN: no candidate written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    print('Wrote library layout candidate:',out)


if __name__=='__main__':main()
