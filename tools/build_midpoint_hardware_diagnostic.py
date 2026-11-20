"""Native-only variants of historical regression midpoints. Dry by default.

No later gameplay/UI/rendering repairs are backported. Erase HD glyphs and the
selector, while retaining the original font resource length, offsets and native
renderer. This is a regression probe, not an exact historical-build replay.
"""
import argparse
import copy
import json
import struct
from functools import lru_cache

from build_bitmap_font import ROOT, digest
from build_font4x_patch import BASE, START, END
from build_native_font_mode import MODE, TITLE_HOOK, FRAME_CALLEE
from build_map_font_patch import member

VERSION, PRIOR = '0.7.27', '0.7.6'
MIDPOINT = '0.7.6'
NATIVE_SHA = '1b909b7fc3e2755a74f2d2da5dbc0b9b67dad90d31eb808ad5ed016adb71820e'
BUILDS = {'0.7.4': ('0.7.28', '0.7.3'), '0.7.6': ('0.7.27', '0.7.6'),
          '0.7.11': ('0.7.29', '0.7.11'), '0.7.8': ('0.7.30', '0.7.8'),
          '0.7.5': ('0.7.31', '0.7.5')}


@lru_cache(maxsize=5)
def historical_inputs(midpoint):
    if midpoint == '0.7.4':
        from build_native_movie_font import render_074
        exe, archive, _, _, details = render_074()
        assert digest(exe) == 'ead04815fd822e7be3bbe169818bb3a2f3f1e03f2a353798ebf950acdb188689'
        return exe, archive, details
    assert midpoint in ('0.7.5', '0.7.6', '0.7.8', '0.7.11')
    base = ROOT/'work/output'/midpoint
    exe = (base/'1ST_READ.BIN').read_bytes()
    details = json.loads((base/'font-mode-details.json').read_text('utf-8'))
    assert details['version'] == midpoint and digest(exe) == details['executable_sha256']
    assert digest(exe) == {
        '0.7.5':'690bb984eb87bf657070fffefae4a568fe33425e61545ab8ee15aa7744be4d87',
        '0.7.6':'ff6b1ca63c6923ec545d90270c89df6d4cafc01205f5790858c0f438f709ae48',
        '0.7.8':'2d1df901aa5a83312dd8e1125eec6e9a1b1fd4698c34884b0398bf7989553d84',
        '0.7.11':'9ce5d3bb16532d4af081673894982855f69b303a0d22b413e4d457b2475f9d84'}[midpoint]
    archive = (base/'WIN00.AFS').read_bytes()
    assert digest(archive) == details['archive_sha256']
    return exe, archive, details


def compose():
    old, source, details = historical_inputs(MIDPOINT)
    font = member(source, 0)
    assert len(font) == 198144 and digest(font[99072:]) == NATIVE_SHA
    # Keep the historical resource allocation and every archive offset. The
    # former HD pixel area becomes zero padding. Shared metrics/header stay
    # exact because other name measurement code uses them independently.
    resource = font[:0x200] + bytes(99072-0x200) + font[99072:]
    offset, size = struct.unpack_from('<II', source, 8)
    archive = source[:offset] + resource + source[offset+size:]
    assert len(archive) == len(source)
    assert all(member(archive, i) == member(source, i) for i in range(1, 90))
    exe, edits = bytearray(old), []
    for literal, expected_uses in ((0x6b4ac, 2), (0x6b620, 1), (0x6b820, 1)):
        assert struct.unpack_from('<I', old, literal)[0] == MODE
        sites = []
        for p in range(max(0, literal-1024)&~1, literal, 2):
            op = struct.unpack_from('<H', old, p)[0]
            if op >> 12 == 0xd and ((p+4)&~3)+(op&255)*4 == literal:
                load = struct.unpack_from('<H', old, p+2)[0]
                assert load in (0x6000, 0x6400), (hex(p), hex(load))
                destination = load >> 8 & 15
                struct.pack_into('<H', exe, p+2, 0xe000 | destination << 8)
                sites.append(p+2)
                edits.append({'offset': hex(p+2), 'bytes': 2, 'reason': 'Constant Native selection, retaining historical branch layout'})
        assert len(sites) == expected_uses
    assert struct.unpack_from('<I', old, 0x10150)[0] == TITLE_HOOK
    struct.pack_into('<I', exe, 0x10150, FRAME_CALLEE)
    exe[0x6b900:0x6bad0] = bytes.fromhex('0900')*(0x1d0//2)
    edits += [{'offset':'0x10150','bytes':4,'reason':'Restore original frame callback'},
              {'offset':'0x6b900','bytes':0x1d0,'reason':'Erase title selector and its labels'}]
    allowed = {i for r in edits for i in range(int(r['offset'],16), int(r['offset'],16)+r['bytes'])}
    changes = {i for i, (a,b) in enumerate(zip(old,exe)) if a != b}
    assert changes <= allowed
    assert exe[0x6b6e0:0x6b800] == old[0x6b6e0:0x6b800]
    assert exe[0x10cb0:0x10cb4] == old[0x10cb0:0x10cb4]
    assert exe[0xc2300:0xc2500] == old[0xc2300:0xc2500]
    report = {
        'version':VERSION, 'date':'2026-11-01', 'source_build':PRIOR, 'historical_midpoint':MIDPOINT,
        'kind':f'Binary-search midpoint: {MIDPOINT} with HD removed',
        'public_release':False, 'hardware_fix_confirmed':False,
        'source_executable_sha256':digest(old), 'executable_sha256':digest(exe),
        'archive_sha256':digest(archive), 'changed_executable_bytes':len(changes),
        'normalization_edits':edits, 'font_banks':1, 'native_bank_sha256':NATIVE_SHA,
        'font_resource_bytes':len(resource), 'zero_padding_bytes':99072-0x200,
        'padding_purpose':'Erase HD pixels without changing historical resource allocation, Native offsets or archive layout; shared header/metrics remain exact.',
        'retained':['0.7.3 Native font runtime, forced Native only; no selector',
                    '0.7.4 Native glyphs and 640x480 video/adapters'] + (
                    ['0.7.5 movie position/size conversion','0.7.6 story-choice fixes and English map labels'] if MIDPOINT!='0.7.4' else []),
        'excluded':('All changes introduced in 0.7.7 through 0.7.26.' if MIDPOINT=='0.7.6' else
                    'All changes introduced in 0.7.5 through 0.7.27, including movie 2x fit, revised story choices and rebuilt map labels.'),
        'other_payloads':f'Every non-executable/non-WIN00 payload remains exact historical {PRIOR}.',
        'source_font_runtime_labels':details['labels'], 'rendering':details['rendering'],
        'limits':[f'Historical {MIDPOINT} bugs and memory behavior are intentionally retained.',
                  f'Native-only normalization means this is not byte-identical historical {MIDPOINT}.',
                  'A passing midpoint narrows the normalized code path; removed HD/selector behavior must not be ruled out without a similarly normalized upper control.',
                  'Real Dreamcast result pending; no fix or hardware success is claimed.'],
        'test':'Original Japanese input only; GDI output; cold boot GDEMU/VGA; New Game, then separately Clear 2 normal VMU save -> Next.',
        'upgrade_patch':False,
    }
    if MIDPOINT == '0.7.4':
        report['limits'][2]='For the hallway failure, the upper control is the reported failing Native-only 0.7.6 variant (0.7.27). Treat the separate launch improvement independently.'
        report['limits'].append('The opening and other movies can appear quarter-sized: 0.7.5 movie fit is intentionally absent. Continue to New Game and test the hallway.')
        report['test']='Original Japanese input only; GDI output; cold boot GDEMU/VGA; New Game, advance beyond Koichiro "Oh, s-sorry..." and Kasumi "Oh..." in the Hallway.'
    if MIDPOINT in ('0.7.8', '0.7.11'):
        report.update(
            investigation='Original immediate conversation-start / mission-entry hang',
            role='Normalized upper control' if MIDPOINT=='0.7.11' else 'Normalized midpoint after 0.7.6',
            retained=[f'All historical {MIDPOINT} executable and assets except the identical Native-only normalization used for 0.7.27.'],
            excluded=f'All features introduced after historical {MIDPOINT}; no later repairs backported.',
            comparison_baseline='0.7.27: Native-only historical 0.7.6; tester passes entry but later freezes in the Hallway.',
            test='Cold boot each original-input GDI separately on GDEMU/VGA. Test New Game conversation entry, then Clear 2 VMU save -> Next. Record immediate black/hang separately from any later Hallway freeze.',
            result_interpretation='If Native-only 0.7.11 still fails immediately, use 0.7.8 to split 0.7.7-0.7.11. If Native-only 0.7.11 enters, do not blame that interval; investigate the shared normalization or its interaction. Later Hallway behavior is a separate observation, not proof of a separate root cause.')
    if MIDPOINT == '0.7.5':
        baseline = ROOT/'work/output/0.7.28'
        base_exe = (baseline/'1ST_READ.BIN').read_bytes()
        assert digest(base_exe) == '1c29cc3c8c012389c5f3063555799fc6b3ca7f557ec3e2b0887f2443198dee84'
        assert archive == (baseline/'WIN00.AFS').read_bytes()
        changed = [i for i,(a,b) in enumerate(zip(base_exe,exe)) if a!=b]
        allowed_movie = set(range(0x2a150,0x2a158)) | set(range(0x6b7a8,0x6b7c8))
        assert changed and set(changed) <= allowed_movie
        report.update(date='2026-11-03',
            kind='Working 0.7.28 baseline plus historical 0.7.5 movie geometry only',
            investigation='Movie-size correction and 0.7.5/0.7.6 hardware regression split',
            role='Native-only historical 0.7.5 control',
            retained=['Every 0.7.28 asset and executable byte except the two movie-setter pointers and their position/size wrappers.'],
            excluded='0.7.6 story-choice/map-label changes and every later feature; no other rendering or memory repair backported.',
            comparison_baseline='0.7.28: tester reports no black screen or freezes, but quarter-screen movies; scope limited to tested paths.',
            movie_only_changed_bytes_from_0_7_28=len(changed),
            movie_only_allowed_spans=['0x2a150:0x2a158','0x6b7a8:0x6b7c8'],
            test='Original Japanese input only; GDI output, cold boot GDEMU/VGA. Check normal movie size, New Game dialogue entry, the Koichiro/Kasumi Hallway exchange, and separately Clear 2 VMU save -> Next.',
            result_interpretation='If the same freeze returns, isolate movie scaling or its interaction with this baseline. If the tested paths still pass, investigate the 0.7.6 choice/map group for the Hallway failure. Keep the unresolved 0.7.30 entry checkpoint separate.')
        report['limits'][2]='0.7.28 is reported working on tested paths only. Historical 0.7.5 movie scaling is intentionally the sole new change and needs physical confirmation.'
    return bytes(exe), archive, resource, report


def check(exe, resource, report):
    from build_font4x_patch import SMALL, MEDIUM
    from test_font4x_patch import HDCPU
    from test_outline_font import legacy_mask, expected_pixels
    from test_vga_patch import VideoCPU
    from test_native_movie_font import fresh, MovieCPU, run, OBJ, value
    old, source, _ = historical_inputs(MIDPOINT)
    old_font = member(source,0)
    cases = steps = 0
    for small, chars in ((True,SMALL), (False,MEDIUM)):
        for i, ch in enumerate(chars):
            for bg in (0,128):
                flags = (64 if small else 0)|bg
                for poisoned_mode in (0,1):
                    cpu = HDCPU(exe,resource,i+32 if small else i,flags,w=64,h=32,ex=1,ey=1)
                    cpu.write(MODE,poisoned_mode,1)
                    mask = legacy_mask(resource[99072:],ch,small)
                    if ch.isascii():mask=mask[:,:32]
                    expected = expected_pixels(cpu,mask,flags,12,4,shadow_pixels=1)
                    steps += cpu.run_until(limit=300000)
                    assert cpu.regions[3][1] == expected, (small,ch,bg,poisoned_mode)
                    assert cpu.read(0x8c1f36b6,2) == 12+resource[99072+(0x20 if small else 0xa0)+i]
                    cases += 1
    allocations = []
    for poisoned_mode in (0,1):
        for w,h in ((32,32),(256,128),(512,64),(1024,32)):
            results = []
            for image,font,mode in ((old,old_font,0),(exe,resource,poisoned_mode)):
                cpu=HDCPU(image,font);cpu.write(MODE,mode,1);cpu.reg[8]=0x8c1f0d3c
                cpu.write(cpu.reg[8]+10,w,2);cpu.write(cpu.reg[8]+12,h,2)
                cpu.pc=report['source_font_runtime_labels']['allocate'];steps+=cpu.run_until()
                p=cpu.reg[0];assert p
                results.append([cpu.read(p+12,1),cpu.read(p+13,1),cpu.read(p+20,4),cpu.read(p+28,2),cpu.read(p+30,2)])
            assert results[0]==results[1]
            assert max(results[1][-2:])<=1024
            allocations.append({'logical':[w,h],'poisoned_mode':poisoned_mode,'matches_historical_Native':MIDPOINT,'descriptor':results[1]})
    video_cases = 0
    for entry in (0xda5c0,0xbbe00):
        for cable in range(4):
            for flags in (0,1,0x10,0x11,0x20,0x21,0x40,0x41,0x42,0x43,0x60,0x61):
                a,b=[VideoCPU(image,cable,flags,entry) for image in (old,exe)]
                steps+=a.run_video();steps+=b.run_video()
                assert a.reg==b.reg and a.calls==b.calls and a.fallback==b.fallback
                assert a.regions[-3:]==b.regions[-3:]
                video_cases+=1
    movie_cases = 0
    for i in range(129):
        filename,w,h=struct.unpack_from('<3I',exe,0x88e74+12*i)
        c=fresh(exe,MovieCPU);c.write(OBJ,OBJ+0x200,4)
        c.write(OBJ+0x200+40,0xdead1000,4);c.write(OBJ+0x200+24,0xdead2000,4)
        c.reg[4]=i;steps+=run(c,BASE+0x29fe8)
        if filename==BASE+0x87bac:continue
        scale=1 if MIDPOINT=='0.7.4' else 2
        assert [value(c.read(OBJ+o,4)) for o in (116,120,128,132)]==[scale*((320-w)//2),scale*((240-h)//2),scale*w,scale*h]
        movie_cases+=1
    return {'version':VERSION,'executable_sha256':digest(exe),'native_glyph_cases':cases,
            'allocation_cases':allocations,'VGA_cases':video_cases,'movie_cases':movie_cases,
            'SH4_instructions':steps,'scope':'Actual historical Native raster/allocator, video commit and movie initialization with bounded endpoint fixtures; no physical GPU success claimed.'}


def main():
    global VERSION, PRIOR, MIDPOINT
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true')
    parser.add_argument('--midpoint',choices=BUILDS,default='0.7.6')
    args=parser.parse_args();MIDPOINT=args.midpoint
    VERSION,PRIOR=BUILDS[MIDPOINT]
    exe,archive,font,report=compose()
    print(json.dumps({k:report[k] for k in ('version','source_build','executable_sha256','archive_sha256','changed_executable_bytes','retained','limits')},indent=2),flush=True)
    if not args.write:print('DRY RUN: no files written.');return
    proof=check(exe,font,report)
    from build_native_font_mode_disc import plan
    from build_movie_test_disc import write_plan
    mode=copy.deepcopy(historical_inputs(MIDPOINT)[2])
    mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(exe),native_only=True,title_selector=False,
                HD_bank_removed=True,native_bank_sha256=NATIVE_SHA)
    normalize_metadata(mode,font)
    planned,_=plan(compose_fn=lambda:(exe,archive,font,{},mode),prior=PRIOR,version=VERSION)
    planned[7].update(kind=report['kind'],component_manifest_name='midpoint-hardware-component.json',
                      readme_component_text=report['kind']+'\n',proof_scope=proof['scope'],pending=report['limits'])
    write_plan(planned,VERSION,PRIOR,{'1ST_READ.BIN':exe,'WIN00.AFS':archive})
    out=ROOT/'work/output'/VERSION
    for name,data in (('midpoint-hardware-diagnostic.json',report),('midpoint-hardware-native-test.json',proof),('font-mode-details.json',mode)):
        (out/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    path=out/'font4x-patch.json';manifest=json.loads(path.read_text('utf-8'))
    manifest.update(version=VERSION,previous_build=PRIOR,status=f'Native-only {MIDPOINT} midpoint diagnostic; hardware result pending',
                    current_payload_identities=planned[7]['files'],hardware_diagnostic=report,
                    historical_component_reports='Historical reports retain actual tested identities; current midpoint/native report describes the HD removal.')
    manifest['font_modes']={k:v for k,v in mode.items() if k not in ('metrics','labels','archive_packing')}
    manifest['surface_scaling']='Native only: two texels per 320x240 logical coordinate in the historical 640x480 rendering setup; original allocation fallback and 1024-edge cap retained.'
    for name in ('1ST_READ.BIN','WIN00.AFS'):manifest['files'][name]['target_sha256']=planned[7]['files'][name]['sha256']
    path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (out/'READ-ME.txt').write_text(f'Rayblade {VERSION} MIDPOINT HARDWARE DIAGNOSTIC\n\n'
        f'Based on historical {MIDPOINT}. Native glyphs only, no HD glyphs or title selector.\n'
        'Historical bugs are intentional. Not a confirmed fix or an exact historical replay.\n'
        'Apply full DCP to original Japanese image; choose GDI for GDEMU; cold boot with VGA.\n'
        +report['test']+'\n'+'\n'.join(report['limits'])+'\nNo upgrade patch.\n',encoding='utf-8')
    print('PASS: Native-only historical midpoint and full disc preservation.',flush=True)


def normalize_metadata(mode,font):
    for key in ('HD_bank_sha256','combined_font_sha256','title_hook','HD_pixels'):
        mode.pop(key,None)
    mode.update(font_banks=1,font_resource_sha256=digest(font),native_default=True,
                width_tables='Original shared metrics and Native metrics preserved',
                mode_state_unused=True,title_selector=False,HD_bank_removed=True)


if __name__=='__main__':main()
