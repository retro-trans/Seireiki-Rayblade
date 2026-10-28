"""Check real texture-pool space before allocating text surfaces. Dry first."""
import argparse,json
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from sh4_asm import Assembler
from test_native_movie_font import DrawCPU,run,STOP,bits,BASE
from build_native_font_mode_disc import plan as font_plan
from build_movie_test_disc import write_plan

VERSION,PRIOR='0.7.14','0.7.13'
OUT=ROOT/'work/output/hd-surface-candidate'
ENTRY=0x8c07bb7c
LIMIT=0x8c07bbe0
MAX_PIXELS_BYTES=512*1024
RAM=ROOT/'work/source/runtime/hd-white-load.ram'


def helper(labels):
    a=Assembler(ENTRY);a.labels.update(reduce=labels['a_reduce'],resume=labels['a_malloc']+4)
    a.emit(0x4f22);a.addi(-8,15)
    a.rr('mov',15,4);a.rr('mov',15,5);a.addi(4,5)
    a.lit(0x8c0e59e6,0);a.emit(0x400b);a.emit(0x0009)
    # Texture creation uses bank 1 by default, or the larger bank when its
    # existing automatic-bank flag is enabled. Bank 1 is a conservative bound
    # valid for both settings. Query is read-only; no VRAM reservation is made.
    a.emit(0x51f1);a.addi(8,15);a.emit(0x4f26)
    a.rr('mov',14,0);a.addi(-32,0)
    # Other pending UI textures can consume space before this surface uploads.
    # Bound individual surfaces even when the current free-space query is high.
    a.lit(MAX_PIXELS_BYTES,2);a.rr('cmp/hs',0,2);a.branch('bf','too_large')
    a.rr('cmp/hs',0,1);a.branch('bt','fits')
    a.label('too_large')
    a.rr('mov',11,0);a.rr('or',12,0);a.rr('tst',0,0);a.branch('bt','fits')
    a.branch('bra','reduce');a.emit(0x0009)
    a.label('fits');a.rr('mov',14,4);a.imm(0,5)
    a.branch('bra','resume');a.emit(0x0009)
    raw=a.pool_and_finish();assert len(raw)<=LIMIT-ENTRY,(len(raw),LIMIT-ENTRY)
    return raw


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;old=(base/'1ST_READ.BIN').read_bytes()
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'));labels=mode['labels']
    raw=helper(labels);at=ENTRY-BASE;hook=labels['a_malloc']-BASE
    assert old[at:at+len(raw)]==bytes.fromhex('0900')*(len(raw)//2)
    assert old[hook:hook+4]==bytes.fromhex('e36400e5')
    a=Assembler(BASE+hook);a.labels['helper']=ENTRY;a.branch('bra','helper');a.emit(0x0009)
    exe=bytearray(old);exe[at:at+len(raw)]=raw;exe[hook:hook+4]=a.pool_and_finish()
    changed={i for i,(x,y) in enumerate(zip(old,exe)) if x!=y}
    assert changed<=set(range(at,at+len(raw)))|set(range(hook,hook+4))
    component={'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(old),
        'executable_sha256':digest(exe),'helper_entry':hex(ENTRY),'helper_bytes':len(raw),
        'hook_offset':hex(hook),'query':hex(0x8c0e59e6),'pool':'Bank 1 largest available block, safe for default/automatic bank selection',
        'maximum_surface_pixel_bytes':MAX_PIXELS_BYTES,
        'policy':'Before each heap attempt, lower surface density if physical texture bytes exceed 512 KiB or current video-memory block capacity. The per-surface cap leaves headroom for pending uploads. Retain original minimum-density/heap-failure handling.',
        'unchanged':'Both font banks, pixels, widths, wording, preferred Native/HD scales, 1024-edge limit, 2 MiB CPU budget, headers and upload code',
        'release':False,'live_validation':'pending'}
    return bytes(exe),component


class SurfaceCPU(DrawCPU):
    def execute(self,pc,delay=False):
        if pc==0x8c0e59e6 and self.query_override is not None:
            self.write(self.reg[4],0,4);self.write(self.reg[5],self.query_override,4)
            return self.pr
        if pc==0x8c03f748:
            self.heap_calls.append(self.reg[4]);self.reg[0]=0 if len(self.heap_calls)<=self.failures else 0x8c600000
            return self.pr
        return super().execute(pc,delay)


def fresh(exe,ram):
    c=SurfaceCPU(exe,b'',0,0);c.regions=[(0x8c000000,bytearray(ram))]
    # Preserve captured mutable SDK data/free-list roots within the executable
    # image. Only install the two code spans changed by this component.
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    for at,size in ((0x6b5a8,4),(ENTRY-BASE,LIMIT-ENTRY)):
        assert ram[0x10000+at:0x10000+at+size]==old[at:at+size]
        c.regions[0][1][0x10000+at:0x10000+at+size]=exe[at:at+size]
    c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(0.)]*16;c.fpul=0;c.visited=set()
    c.heap_calls=[];c.failures=0;c.query_override=None
    return c


def largest(c):
    c.reg[4:6]=[0x8cffd000,0x8cffd004];n=run(c,0x8c0e59e6)
    return [c.read(0x8cffd000,4),c.read(0x8cffd004,4)],n


def allocate(exe,ram,mode,w,h,failures=0,query_override=None):
    c=fresh(exe,ram);ctx=0x8c1f0d3c+92
    c.write(ctx,0,4);c.write(ctx+10,w,2);c.write(ctx+12,h,2)
    c.write(0x8c07bbe0,mode,1);c.reg[8]=ctx;c.failures=failures;c.query_override=query_override
    labels=json.loads((ROOT/'work/output'/PRIOR/'font-mode-details.json').read_text('utf-8'))['labels']
    n=run(c,labels['allocate']);p=c.reg[0]
    assert p and len(c.heap_calls)>failures
    wh=[c.read(p+28,2),c.read(p+30,2)];ex=[c.read(p+12,1),c.read(p+13,1)]
    assert wh==[w<<ex[0],h<<ex[1]] and max(wh)<=1024
    assert c.read(p+20,4)==wh[0]*wh[1]*2
    return c,wh,ex,n


def create(c,w,h):
    p=0x8cffd100;c.pr=STOP;c.reg[4:8]=[p,w,h,0x902]
    n=run(c,0x8c0e1c4c);assert c.reg[0]==0
    c.pr=STOP;c.reg[4:6]=[c.read(p+20,4),p];n+=run(c,0x8c0e52a0)
    return c.reg[0],n


def check():
    exe,component=compose();ram=RAM.read_bytes();assert len(ram)==16*1024*1024
    old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes()
    c=fresh(old,ram);free,steps=largest(c);assert free==[0,903168],free
    cases=[]
    for mode in (0,1):
      for w,h in ((256,32),(128,128),(256,128),(256,256),(512,64)):
       for failures in (0,1,2):
        a,aw,ae,n=allocate(old,ram,mode,w,h,failures);steps+=n
        b,bw,be,n=allocate(exe,ram,mode,w,h,failures);steps+=n
        status,n=create(b,*bw);steps+=n
        assert status==0,(mode,w,h,bw,status)
        assert bw[0]*bw[1]*2<=min(free[1],MAX_PIXELS_BYTES)
        if mode==0 and not failures:assert (aw,ae)==(bw,be)
        before,n=create(a,*aw);steps+=n
        cases.append({'mode':('Native','HD')[mode],'logical':[w,h],'heap_failures':failures,
            'old_physical':aw,'new_physical':bw,'old_create_status':before,'new_create_status':status})
    assert any(r['old_create_status']==3 and r['new_create_status']==0 for r in cases)
    pending=[]
    for w,h in ((256,128),(256,256)):
        # Deliberately optimistic query witness: text preparation sees 2 MiB,
        # but the actual upload allocator sees the captured 903168-byte pool.
        a,aw,ae,n=allocate(old,ram,1,w,h,query_override=2*1024*1024);steps+=n
        b,bw,be,n=allocate(exe,ram,1,w,h,query_override=2*1024*1024);steps+=n
        before,n=create(a,*aw);steps+=n
        after,n=create(b,*bw);steps+=n
        assert before==3 and after==0 and bw[0]*bw[1]*2<=MAX_PIXELS_BYTES
        pending.append({'logical':[w,h],'query_fixture_bytes':2*1024*1024,'upload_free_bytes':free[1],
            'old_physical':aw,'new_physical':bw,'old_create_status':before,'new_create_status':after})
    return {**component,'captured_ram_sha256':digest(ram),'source_capture':'0.7.13 HD Load File white panel',
        'captured_largest_free_blocks':free,'allocation_and_native_surface_cases':cases,
        'optimistic_query_pending_upload_cases':pending,'SH4_instructions':steps,
        'checks':['Actual SDK free-block query, text allocator, PVR format validation and video-memory allocator execute on copied live state',
            'Both modes, five surface dimensions, repeated heap failures, size bounds, CPU budget and ABI retained',
            'Old large HD textures reproduce native allocation failure; all corrected witnesses allocate successfully'],
        'limits':['CPU heap allocation is a bounded fixture; native video-memory allocator executes against the captured live free lists',
            'Two additional pending-upload witnesses replace only the query with an optimistic capacity; actual texture creation still executes on the captured native pool',
            'Concurrent future uploads, complete VRAM pressure coverage and hardware require live confirmation','Stage 6 issue #1 unresolved']}


def plan():
    exe,component=compose();base=ROOT/'work/output'/PRIOR
    mode=json.loads((base/'font-mode-details.json').read_text('utf-8'))
    p,_=font_plan(compose_fn=lambda:(exe,(base/'WIN00.AFS').read_bytes(),b'',{},mode),prior=PRIOR,version=VERSION)
    p[7].update(kind='Local HD video-memory fallback fix',component_manifest_name='hd-surface-component.json',
        current_native_evidence={'hd_surface':'hd-surface-native-test.json'},
        readme_component_text='Large HD text panels check real texture-pool space and cap individual textures at 512 KiB before upload.\n'
            'Both font banks and all 0.7.13 fixes retained. Cold-boot; Y selects HD at the title.\n',
        proof_scope='Native video-memory query/allocator and text density fallback; complete disc preservation.',
        pending=['Full VRAM-pressure and physical hardware coverage','Stage 6 issue #1','Full-game translation review'])
    p[7]['inherited_proof_note']='Historical records retain their actual tested builds/hashes; current allocator evidence is hd-surface-native-test.json.'
    return p


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    exe,component=compose()
    if not a.write:print(json.dumps(component,indent=2));return
    proof=check();OUT.mkdir(parents=True,exist_ok=True);(OUT/'1ST_READ.BIN').write_bytes(exe)
    records=[('hd-surface-component.json',component),('hd-surface-native-test.json',proof)]
    for name,data in records:(OUT/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
    print('PASS:',len(proof['allocation_and_native_surface_cases']),'native allocation/create cases and',
        len(proof['optimistic_query_pending_upload_cases']),'pending-upload witnesses.',flush=True)
    if a.disc:
        p=plan();write_plan(p,VERSION,PRIOR,{'1ST_READ.BIN':exe});out=ROOT/'work/output'/VERSION
        for name,data in records:(out/name).write_text(json.dumps(data,indent=2)+'\n','utf-8')
        m=json.loads((out/'font4x-patch.json').read_text('utf-8'));m.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        m['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
        m['hd_surface']={'native_proof':'hd-surface-native-test.json','helper_entry':hex(ENTRY)}
        m['native_proof_reuse']={'source_build':PRIOR,'scope':'All assets and raster bytes are exact; allocator entry and previously unused helper padding change.'}
        (out/'font4x-patch.json').write_text(json.dumps(m,indent=2)+'\n','utf-8')
        mode=json.loads((out/'font-mode-details.json').read_text('utf-8'));mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe))
        (out/'font-mode-details.json').write_text(json.dumps(mode,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
