"""Compose English battle data with 0.1.5, preserving font/menu/library work."""
import argparse,copy,json,struct
from build_font_patch import ROOT
from build_battle_translation import VERSION,build,digest

DATA_CAPACITY=0x50000
RECORD_COPY=0x3000
OUTPUT_CAPACITY=0x800
WORKSPACE_SIZE=2*RECORD_COPY+OUTPUT_CAPACITY


def candidate_executable():
    base=ROOT/'work/output/0.1.5'
    manifest=json.loads((base/'font4x-patch.json').read_text('utf-8'))
    source=(base/'1ST_READ.BIN').read_bytes()
    assert digest(source)==manifest['files']['1ST_READ.BIN']['target_sha256']
    target=bytearray(source)
    edits=[(0x10dc4,4,0x38000,DATA_CAPACITY,'decompressed battle component allocation'),
           (0x1bb18,2,0x6200,WORKSPACE_SIZE,'two record copies plus four selected outputs')]
    for offset,size,before,after,_ in edits:
        assert int.from_bytes(source[offset:offset+size],'little')==before
        target[offset:offset+size]=after.to_bytes(size,'little')
    # The mov.w workspace literal remains signed-positive. Record offsets
    # and memcpy lengths stay 0x3000, so existing combat-state code is intact.
    assert WORKSPACE_SIZE<0x8000
    assert struct.unpack_from('<HH',target,0x1bb1a)==(0x6000,RECORD_COPY)
    assert struct.unpack_from('<H',target,0x1bc28)[0]==RECORD_COPY
    return bytes(target),manifest,edits


def compose():
    plain,packed,_,_,_,_,component=build()
    exe,manifest,edits=candidate_executable();base=ROOT/'work/output/0.1.5'
    assert len(plain)<=DATA_CAPACITY and component['maximum_record_bytes']<=RECORD_COPY
    proof=json.loads((ROOT/'work/output'/VERSION/'battle-english-native-test.json').read_text('utf-8'))
    assert proof['component_sha256']==digest(plain) and proof['executable_sha256']==digest(exe)
    assert proof['maximum_four_output_bound']<=OUTPUT_CAPACITY
    component['stage']='native-verified relocated English battle component; gameplay/layout validation pending'
    component['validation'].update(native_selection='pass',native_decompression='pass',native_workspace_geometry='pass')
    component['pending']=['Preceding combat-state mapping','Measured battle layout','Gameplay and long-session memory','Independent meaning review']
    afs=(base/'WIN00.AFS').read_bytes()
    assert digest(afs)==manifest['files']['WIN00.AFS']['target_sha256']
    result=copy.deepcopy(manifest);result.update(version=VERSION,previous_build='0.1.5',
        status='local English battle integration; combat-state/layout/gameplay validation pending')
    result['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    result['battle']={'version':VERSION,'source_file':'D_BMESS.BIN',
        'source_compressed_sha256':json.loads((ROOT/'work/source/battle/summary.json').read_text('utf-8'))['compressed_sha256'],
        'compressed_sha256':digest(packed),'decoded_sha256':digest(plain),
        'compressed_bytes':len(packed),'decoded_bytes':len(plain),'data_capacity':DATA_CAPACITY,
        'record_copy_bytes':RECORD_COPY,'maximum_record_bytes':component['maximum_record_bytes'],
        'workspace_bytes':WORKSPACE_SIZE,'selected_output_capacity':OUTPUT_CAPACITY,
        'maximum_four_output_bound':proof['maximum_four_output_bound'],
        'memory_edits':[{'offset':hex(o),'bytes':n,'before':hex(a),'after':hex(b),'purpose':p} for o,n,a,b,p in edits],
        'native_validation':{k:proof[k] for k in ['native_selection_cases','native_root_cases','workspace_cases',
            'SH4_selection_instructions','SH4_workspace_instructions','maximum_single_output_bytes']},
        'pending':['Preceding combat-state mapping','Measured battle layout','Gameplay and long-session memory checks','Independent meaning review']}
    copied={}
    for path in (base/'text').iterdir():
        if path.is_file():copied['text/'+path.name]=path.read_bytes()
    copied['library-native-test.json']=(base/'library-native-test.json').read_bytes()
    copied['text/D_BMESS.BIN']=packed;copied['text/D_BMESS.en.dec.bin']=plain
    return {'1ST_READ.BIN':exe,'WIN00.AFS':afs},copied,result,component


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,copied,manifest,component=compose();print(json.dumps(manifest['battle'],indent=2))
    if not args.write:print('DRY RUN: no integration components written');return
    out=ROOT/'work/output'/VERSION;out.mkdir(parents=True,exist_ok=True)
    for name,raw in {**files,**copied}.items():
        path=out/name;path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
    (out/'battle-patch-report.json').write_text(json.dumps(manifest['battle'],indent=2),'utf-8')
    (out/'text/battle-component-report.json').write_text(json.dumps(component,indent=2),'utf-8')
    print('Wrote local battle integration components:',out)


if __name__=='__main__':main()
