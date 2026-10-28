"""Reserve texture space for battle/UI coexistence. Dry first; local 0.7.19."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.19','0.7.18'
AT=0x6b910
# Measured from a cold boot of the original Japanese disc, not inferred from
# an English build or guessed from the 640x480 SDK minimum.
UNITS=384176


@lru_cache(maxsize=1)
def compose():
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();exe=bytearray(old)
    assert struct.unpack_from('<I',old,AT)[0]==0x1f8000
    struct.pack_into('<I',exe,AT,UNITS)
    assert exe[:AT]==old[:AT] and exe[AT+4:]==old[AT+4:]
    return bytes(exe),{'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),
        'literal_file_offset':hex(AT),'TA_allocator_units':UNITS,'TA_VRAM_bytes':UNITS*2,
        'previous_TA_VRAM_bytes':0x3f0000,'additional_texture_capacity_bytes':0x3f0000-UNITS*2,
        'texture_capacity_bytes':0x800000-UNITS*2,
        'cause':'Fresh-boot S004 exhausts the 0.7.18 pool: five 512x512 terrain textures, battle atlas and unit sprites leave 2048 bytes; dialogue upload returns error 6.',
        'geometry_source':'Original Japanese disc cold-boot SDK telemetry: 384176 units / 768352 bytes. This is the stock geometry reservation.',
        'tradeoff':'Restores stock geometry capacity; the 640x480 minimum is larger than the original 320x240 minimum, so physical/full-game geometry headroom remains unverified.',
        'preserved':'Every other executable byte and all disc assets, including Native Skies pixels/widths/alpha, all wording and original movies, exact 0.7.18.',
        'release':False,'live_validation':'pending'}


def check():
    from test_native_movie_font import DrawCPU,STOP,bits
    class BudgetCPU(DrawCPU):
        def execute(self,pc,delay=False):
            if pc==0x8c0e77e0:self.reg[0]=self.query;return self.pr
            return super().execute(pc,delay)
    exe,r=compose();rows=[]
    from disc_inventory import Disc
    original=Disc(next(ROOT.glob('*.cue')));entry=next(e for e in original.inventory() if e['path']=='1ST_READ.BIN')
    original_exe=original.read(entry['lba'],entry['size'])
    cases=[('original Japanese',original_exe,UNITS,230400,17280),
        (PRIOR,(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes(),0x1f8000,0x96000,0xfd20),
        (VERSION,exe,UNITS,0x96000,0xfd20)]
    for version,image,expected,framebuffer,minimum in cases:
      for query in (0,1):
        c=BudgetCPU(image,b'',0,0);c.regions=[(0x8c000000,bytearray(0x1000000))]
        c.regions[0][1][0x10000:0x10000+len(image)]=image;c.query=query
        c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
        c.reg[13]=0x8c46214c;c.reg[14]=0x8c419b38
        for at,v in [(0x8c461bd0,0x800000),(0x8c46214c+92,0x1b4fa8),(0x8c46214c+96,framebuffer),(0x8c46214c+100,minimum)]:c.write(at,v,4)
        c.pc=0x8c0d230c;n=0
        while c.pc not in (0x8c0d2368,0x8c0d241a):
            assert n<1000;c.pc=c.execute(c.pc);n+=1
        assert c.pc==0x8c0d2368 and c.reg[11]==expected and c.read(0x8c4621a4,4)==expected
        c.pc=c.execute(c.pc);n+=1
        assert c.pc==0x8c0e5200 and c.reg[4]==expected and expected>c.read(0x8c4621b0,4)
        rows.append({'version':version,'configuration_query_result':query,'TA_allocator_units':expected,'TA_VRAM_bytes':expected*2,
            'framebuffer_bytes_each':framebuffer,'SDK_minimum_units':c.read(0x8c4621b0,4),'reaches_native_allocator':True,'instructions':n})
    return {**r,'actual_SDK_budget_minimum_and_allocator_entry':rows,
        'scope':'Actual SDK arithmetic and both configuration branches; real battle residency/GPU appearance require live cold-boot evidence.'}


def plan():
    exe,r=compose();base=ROOT/'work/output'/PRIOR;archive=(base/'WIN00.AFS').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
    p,_=font_plan(compose_fn=lambda:(exe,archive,b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local battle texture memory allocation',component_manifest_name='battle-memory-component.json',
        current_native_evidence={'battle_memory':'battle-memory-native-test.json'},
        current_live_evidence={'battle':'battle-memory-live-test.json'},
        readme_component_text='Native Skies 1x only. Restores the original Japanese 768,352-byte geometry reservation.\n'
            'Recovers 3,360,416 bytes for terrain, unit sprites, portraits, windows and dialogue; all other executable bytes/assets exact 0.7.18.\n',
        proof_scope='Actual SDK budget/minimum/allocator-entry checks and complete disc preservation; live battle/map evidence recorded separately.',
        inherited_proof_note='Unchanged assets/font retain their historical evidence identities; current battle proof is recorded separately.',
        pending=['Physical Dreamcast/full-game geometry and route review','Stage 6 issue #1'])
    return p,mode


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,r=compose()
    if not a.write:print(json.dumps(r,indent=2));return
    proof=check()
    if not a.disc:print(json.dumps(proof,indent=2));return
    p,mode=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':(ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()})
    out=ROOT/'work/output'/VERSION
    for name,obj in [('battle-memory-component.json',r),('battle-memory-native-test.json',proof),('font-mode-details.json',mode),('font-mode-component.json',mode)]:
        (out/name).write_text(json.dumps(obj,indent=2)+'\n','utf-8')
    m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
    m['files']['1ST_READ.BIN']['target_sha256']=digest(exe);(out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
    print('PASS: 0.7.19 SDK geometry checks and complete disc preservation.')


if __name__=='__main__':main()
