"""Reserve 64 KiB for portrait swaps. Dry first; local 0.7.18 only."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.18','0.7.17'
AT=0x6b910
UNITS=0x1f8000


@lru_cache(maxsize=1)
def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();exe=bytearray(old)
    assert struct.unpack_from('<I',old,AT)[0]==0x200000
    struct.pack_into('<I',exe,AT,UNITS)
    assert exe[:AT]==old[:AT] and exe[AT+4:]==old[AT+4:]
    return bytes(exe),{'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),
        'literal_file_offset':hex(AT),'TA_allocator_units':UNITS,'TA_VRAM_bytes':UNITS*2,
        'previous_TA_VRAM_bytes':0x400000,'additional_texture_capacity_bytes':65536,
        'tradeoff':'Geometry reservation reduced by 1.5625 percent; full-game maximum geometry usage remains unverified.',
        'preserved':'Every other executable byte, all disc assets, Native Skies font pixels/advances/alpha, all wording and movies exact 0.7.17.',
        'release':False,'live_validation':'pending'}


def check():
    from test_native_movie_font import DrawCPU,STOP,bits
    class BudgetCPU(DrawCPU):
        def execute(self,pc,delay=False):
            if pc==0x8c0e77e0:self.reg[0]=0;return self.pr
            return super().execute(pc,delay)
    exe,r=compose();rows=[]
    for version,image,expected in [(PRIOR,(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes(),0x200000),(VERSION,exe,UNITS)]:
        c=BudgetCPU(image,b'',0,0);c.regions=[(0x8c000000,bytearray(0x1000000))]
        c.regions[0][1][0x10000:0x10000+len(image)]=image
        c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
        c.reg[13]=0x8c46214c;c.reg[14]=0x8c419b38
        for at,v in [(0x8c461bd0,0x800000),(0x8c46214c+92,0x1b4fa8),(0x8c46214c+96,0x96000),(0x8c46214c+100,0xfd20)]:c.write(at,v,4)
        c.pc=0x8c0d230c;n=0
        while c.pc not in (0x8c0d2368,0x8c0d241a):
            assert n<1000;c.pc=c.execute(c.pc);n+=1
        assert c.pc==0x8c0d2368 and c.reg[11]==expected and c.read(0x8c4621a4,4)==expected
        c.pc=c.execute(c.pc);n+=1
        assert c.pc==0x8c0e5200 and c.reg[4]==expected
        assert expected>c.read(0x8c4621b0,4)
        rows.append({'version':version,'TA_allocator_units':expected,'TA_VRAM_bytes':expected*2,
            'SDK_minimum_units':c.read(0x8c4621b0,4),'reaches_native_allocator':True,'instructions':n})
    return {**r,'actual_SDK_budget_and_minimum_check':rows,'scope':'Exact SDK arithmetic and minimum checks; real allocation/residency and both portraits require cold-boot evidence.'}


def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local portrait-swap memory reserve',component_manifest_name='portrait-memory-component.json',
        current_native_evidence={'portrait_memory':'portrait-memory-native-test.json'},
        readme_component_text='Native Skies 1x only. Adds 64 KiB texture headroom for portrait changes.\n'
            'Geometry reservation changes from 4 MiB to 3.9375 MiB; all assets and every other executable byte match 0.7.17.\n',
        proof_scope='Actual SDK budget/minimum checks and complete disc preservation; live portrait and scene evidence recorded separately.',
        pending=['Physical Dreamcast/full-game geometry review','Stage 6 issue #1'])
    p[7]['inherited_live_evidence_from_0717']=p[7].pop('current_live_evidence',{})
    p[7]['current_live_evidence']={'portraits':'portrait-memory-live-test.json',
        'Touya_residency':'touya-residency-live.json','Ymir_residency':'ymir-residency-live.json'}
    p[7]['inherited_proof_note']='Unchanged font/assets retain their historical proof identities. Current SDK budget and live portrait evidence are recorded separately.'
    return p,mode


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,r=compose()
    if not a.write:print(json.dumps(r,indent=2));return
    proof=check()
    if not a.disc:print(json.dumps(proof,indent=2));return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('portrait-memory-component.json',r),('portrait-memory-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:
        (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
    print('PASS: 0.7.18 SDK startup checks and complete disc preservation.')


if __name__=='__main__':main()
