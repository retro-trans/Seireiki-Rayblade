"""Run the unchanged SDK allocator on actual failed/fixed S004 snapshots."""
import argparse,json
from build_bitmap_font import ROOT,digest
from inspect_vram_residency import inspect
from test_native_movie_font import DrawCPU,STOP,bits,run


def witness(version,filename,requests):
    exe=(ROOT/'work/output'/version/'1ST_READ.BIN').read_bytes();ram=(ROOT/'work/source/runtime'/filename).read_bytes();state=inspect(ram)
    assert ram[0x7b900:0x7b918]==exe[0x6b900:0x6b918]
    c=DrawCPU(exe,b'',0,0);c.regions=[(0x8c000000,bytearray(ram))]
    c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set();rows=[]
    for i,(label,w,h,fmt) in enumerate(requests):
        p=0x8cffd100+i*0x100;c.reg[4:8]=[p,w,h,fmt];c.pr=STOP;n=run(c,0x8c0e1c4c)
        assert c.reg[0]==0;size=c.read(p+20,4);c.reg[4:6]=[size,p];c.pr=STOP;n+=run(c,0x8c0e52a0)
        rows.append({'label':label,'dimensions':[w,h],'bytes':size,'native_result':c.reg[0],'instructions':n})
    return {'version':version,'snapshot_sha256':digest(ram),'VM':state['VM'],
        'initial_free_bytes':[b['total_free'] for b in state['banks']],'allocations':rows}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    if not a.write:print('DRY RUN: baseline dialogue rejection and four additional status surfaces plus two portrait swaps against fixed stock-geometry S004 residency.');return
    old=witness('0.7.18','user-battle-white-0718.ram',[('dialogue',1024,128,0x902)])
    assert old['allocations'][0]['native_result']==3
    new=witness('0.7.19','battle-fixed-stock-0719.ram',[(f'status-{i}',w,h,0x902) for i,(w,h) in enumerate([(512,256),(512,256),(256,256),(256,256)])]+[('next-portrait',64,64,0x100),('another-portrait',64,64,0x100)])
    assert all(r['native_result']==0 for r in new['allocations'])
    p=ROOT/'work/output/0.7.19/battle-memory-native-test.json';report=json.loads(p.read_text('utf-8'))
    report['actual_SDK_battle_allocation_cases']=[old,new]
    report['stress_scope']='Four additional full status surfaces and two more portraits fit while the entire captured battle residency, current portrait and dialogue remain loaded. The actual status menu is reviewed separately.'
    p.write_text(json.dumps(report,indent=2)+'\n','utf-8');print(json.dumps([old,new],indent=2))


if __name__=='__main__':main()
