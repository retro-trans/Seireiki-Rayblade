"""Compose the source-checked menu layout candidate 0.1.15. Default dry run."""
import argparse,json
from build_bitmap_font import ROOT,digest
from build_names_translation import compose as names_component
from prepare_ui_layouts import DEST,prepare

VERSION='0.1.15'
PRIOR='0.1.14'


def compose():
    base=ROOT/'work/output'/PRIOR
    recipe=json.loads(DEST.read_text('utf-8'));assert recipe==prepare()
    old,packed,prior=names_component()
    assert old==(base/'text/D_NAMES.en.dec.bin').read_bytes() and packed==(base/'text/D_NAMES.BIN').read_bytes()
    plain,packed,report=names_component(overrides=recipe['rows'],version=VERSION)
    files={p.name:p.read_bytes() for p in base.iterdir() if p.is_file() and p.suffix.lower()!='.png'}
    for p in (base/'text').iterdir():
        if p.is_file():files['text/'+p.name]=p.read_bytes()
    files.pop('english-disc-report.json',None);files.pop('READ-ME.txt',None)
    files['text/D_NAMES.en.dec.bin']=plain;files['text/D_NAMES.BIN']=packed
    files['text/names-component-report.json']=json.dumps(report,indent=2).encode()
    manifest=json.loads(files['font4x-patch.json'])
    manifest.update(version=VERSION,previous_build=PRIOR,status='UI layout candidate; native parser/decoder and live checks pending')
    manifest['ui_layout']={'version':VERSION,'recipe_sha256':digest(DEST.read_bytes()),'changed_rows':len(recipe['rows']),
        'names_sha256':digest(plain),'names_packed_sha256':digest(packed),'native_validation':'pending','live_validation':'pending'}
    manifest['native_proof_reuse']={'source_build':PRIOR,'reason':'Executable, font, WIN00, story and battle components byte-exact; only D_NAMES rebuilt',
        'executable_sha256':digest(files['1ST_READ.BIN']),'font_archive_sha256':digest(files['WIN00.AFS']),
        'story_archive_sha256':digest(files['D_SCE.AFS'])}
    files['font4x-patch.json']=json.dumps(manifest,indent=2).encode()
    return files,manifest,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,manifest,report=compose()
    print(json.dumps({'version':VERSION,'changed_rows':manifest['ui_layout']['changed_rows'],
        'names_decoded_bytes':report['output_decoded_size'],'names_packed_bytes':report['output_compressed_size'],
        'spare_native_bytes':65536-report['output_decoded_size'],'unchanged':'Executable/font/story/library/battle'},indent=2))
    if not args.write:print('DRY RUN: no candidate files written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    print('Wrote UI layout candidate:',out)


if __name__=='__main__':main()
