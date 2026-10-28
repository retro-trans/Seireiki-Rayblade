"""Execute the unchanged SDK portrait allocator against verified live snapshots."""
import argparse,json
from build_bitmap_font import ROOT,digest
from build_portrait_memory_fix import compose
from inspect_vram_residency import inspect
from test_native_movie_font import DrawCPU,STOP,bits,run


def witness(version,path):
    exe=(ROOT/'work/output'/version/'1ST_READ.BIN').read_bytes();ram=path.read_bytes();state=inspect(ram)
    # Keep live SDK pools and mutable globals; do not overlay the executable.
    assert ram[0x10000+0x6b900:0x10000+0x6b918]==exe[0x6b900:0x6b918]
    c=DrawCPU(exe,b'',0,0);c.regions=[(0x8c000000,bytearray(ram))]
    c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
    c.reg[4:6]=[0x8cffd000,0x8cffd004];steps=run(c,0x8c0e59e6)
    free=[c.read(0x8cffd000,4),c.read(0x8cffd004,4)]
    assert free==[b['largest_free'] for b in state['banks']]
    p=0x8cffd100;c.reg[4:8]=[p,64,64,0x100];c.pr=STOP;steps+=run(c,0x8c0e1c4c)
    assert c.reg[0]==0 and c.read(p+20,4)==8192
    c.reg[4:6]=[8192,p];c.pr=STOP;steps+=run(c,0x8c0e52a0)
    return {'version':version,'snapshot_sha256':digest(ram),'VM':state['VM'],'largest_free_blocks':free,
        'portrait_bytes':8192,'native_allocate_result':c.reg[0],'native_instructions':steps}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    if not a.write:print('DRY RUN: compare actual SDK allocation on initial 0.7.17 map and exact Touya/Ymir 0.7.18 snapshots.');return
    exe,r=compose()
    assert (ROOT/'work/output/0.7.18/1ST_READ.BIN').read_bytes()==exe
    cases=[witness('0.7.17',ROOT/'work/source/runtime/native-map-0717e-target.ram')]
    assert cases[0]['native_allocate_result']==3
    for name in ('touya','ymir'):
        row=witness('0.7.18',ROOT/f'work/source/runtime/{name}-0718.ram');assert row['native_allocate_result']==0
        row['portrait']=name;cases.append(row)
    path=ROOT/'work/output/0.7.18/portrait-memory-native-test.json';report=json.loads(path.read_text('utf-8'))
    report['actual_SDK_portrait_allocation_cases']=cases
    path.write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print(json.dumps(cases,indent=2))


if __name__=='__main__':main()
