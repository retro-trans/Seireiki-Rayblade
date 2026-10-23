"""Repair library/shared parameter overlap and library header rendering. Dry run first."""
import argparse,hashlib,json,struct
from pathlib import Path
from build_font_patch import ROOT
from build_names_translation import compose as names_component
from prepare_ui_layouts import prepare as prior_layout
from build_font4x_patch import MEDIUM

VERSION='0.1.19'
PRIOR='0.1.18'
SCRATCH=0x1f200
SCRATCH_BYTES=0xe00
EDITS=[(0x2afc4,4,0xf200,SCRATCH,'common parameter scratch beyond expanded library'),
       (0x2bc8a,2,0xe7,MEDIUM.index('.'),'native tenths decimal point'),
       (0x2bd24,2,0xe7,MEDIUM.index('.'),'native scaled decimal point')]
digest=lambda b:hashlib.sha256(b).hexdigest()


def recipe():
    result=prior_layout()
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
    row=next(r for r in rows if r['id']=='names.g00.135')
    assert row['en'].count('<FC:9A:80>')==1
    result['rows'][row['id']]={'en':row['en'].replace('<FC:9A:80>','<FC:98:80>'),
        'source_sha256':row['source_sha256'],'prior_en_sha256':digest(row['en'].encode()),
        'reason':'Age starts at local x192 so the complete years label fits inside the 240-pixel header area'}
    result.update(version=VERSION,font_build='0.1.17')
    return result


def executable(prior):
    result=bytearray(prior)
    for off,size,before,after,_ in EDITS:
        assert int.from_bytes(result[off:off+size],'little')==before
        result[off:off+size]=after.to_bytes(size,'little')
    return bytes(result)


def compose():
    base=ROOT/'work/output'/PRIOR
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    files.update({'text/'+p.name:p.read_bytes() for p in (base/'text').iterdir() if p.is_file()})
    for name in ('english-disc-report.json','READ-ME.txt','ui-layout-native-test.json'):
        files.pop(name,None)
    original,old_packed,_=names_component(overrides=prior_layout()['rows'],version='0.1.15')
    assert original==files['text/D_NAMES.en.dec.bin'] and old_packed==files['text/D_NAMES.BIN']
    layout=recipe();plain,packed,report=names_component(overrides=layout['rows'],version=VERSION)
    changes=[i for i,(a,b) in enumerate(zip(original,plain)) if a!=b]
    assert len(original)==len(plain) and len(changes)==1 and original[changes[0]]==0x9a and plain[changes[0]]==0x98
    exe=executable(files['1ST_READ.BIN']);files['1ST_READ.BIN']=exe
    # Exact script commands and registered parameter builders establish the
    # native phases exercised by test_library_headers, including name IDs.
    assert exe[0xf643:0xf64b]==bytes.fromhex('5300218a23048700')
    assert exe[0xf7bd:0xf7c5]==bytes.fromhex('5300228a23048900')
    assert struct.unpack_from('<I',exe,0x434c4)[0]==0x8c064920
    assert struct.unpack_from('<I',exe,0x434cc)[0]==0x8c064bb0
    files['text/D_NAMES.en.dec.bin']=plain;files['text/D_NAMES.BIN']=packed
    files['text/names-component-report.json']=json.dumps(report,indent=2).encode()
    files['library-header-layout.en.json']=json.dumps(layout,indent=2).encode()
    paper=files['text/D_PAPER.en.dec.bin'];assert 0x210+len(paper)<SCRATCH and SCRATCH+SCRATCH_BYTES==0x20000
    manifest=json.loads(files['font4x-patch.json']);manifest.update(version=VERSION,previous_build=PRIOR,status='Library header/scratch candidate; fresh native checks and packaging pending')
    manifest['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    manifest['ui_layout'].update(version=VERSION,recipe_sha256=digest(files['library-header-layout.en.json']),changed_rows=len(layout['rows']),names_sha256=digest(plain),names_packed_sha256=digest(packed),native_validation='pending')
    manifest['library_header']={'version':VERSION,'executable_edits':[{'offset':hex(o),'size':s,'before':hex(b),'after':hex(a),'purpose':p} for o,s,b,a,p in EDITS],
        'shared_capacity':0x20000,'library_start':0x210,'library_end':0x210+len(paper),'scratch_start':SCRATCH,'scratch_reserved_bytes':SCRATCH_BYTES,
        'gap_bytes':SCRATCH-0x210-len(paper),'names_changed_bytes':1,'native_validation':'pending','live_validation':'pending'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Payloads other than D_NAMES stay byte-exact; executable changes require fresh font, UI, library, battle, story and chapter native suites before packaging.'}
    files['font4x-patch.json']=json.dumps(manifest,indent=2).encode()
    return files,manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,m,r=compose();print(json.dumps({'version':VERSION,'library_header':m['library_header'],'names_packed_bytes':len(files['text/D_NAMES.BIN']),'executable_sha256':digest(files['1ST_READ.BIN'])},indent=2))
    if not args.write:print('DRY RUN: no candidate written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (ROOT/'work/translation/en/ui/library-header-layouts.en.json').write_bytes(files['library-header-layout.en.json'])
    print('Wrote',out)


if __name__=='__main__':main()
