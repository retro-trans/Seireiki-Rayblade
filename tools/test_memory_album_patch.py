"""Native caption dispatch/registration/VQ/PRS and measured slot UI. Dry first."""
import argparse
import json
import struct
import numpy as np

from build_memory_album_patch import compose, ROOT, OUT, PRIOR, VERSION, digest
from build_album_caption_overlay import compose as album, BASE, ENTRY, DRAW, RESOURCE
from test_font_patch import CPU, capstone, split_ops, signed
from check_attack_variant_selection import AttackCPU, run, STOP
from test_ordered_archive_layouts import directory_bytes, lookup
from afs_layout import compact_positions, require_native_layouts
from check_native_text_components import verify
from test_ui_layouts import parse_ui, entry
from build_antialias_font import font_bytes
from audit_texture_archive import untwiddle_indices
from build_ui_atlas_patch import pixels


def member(data, index):
    off, size = struct.unpack_from('<II', data, 8 + index * 8)
    return data[off:off+size]


class DrawCPU(CPU):
    def execute(self, pc, delay=False):
        opcode = self.read(pc, 2)
        if opcode == 0xff4b:
            self.reg[15] -= 4; self.write(self.reg[15], self.fr4, 4); return pc+2
        if opcode == 0xf4f9:
            self.fr4 = self.read(self.reg[15], 4); self.reg[15] += 4; return pc+2
        if pc == DRAW:
            self.draws.append((self.reg[4], self.reg[5], self.reg[6], self.fr4))
            for r in range(8): self.reg[r] = 0xdec00000+r
            self.fr4 = 0x12345678
            return self.pr
        return super().execute(pc, delay)


def dispatch(exe, enabled):
    total = cases = 0
    for mode in ('gallery', 'null_object', 'other_slot', 'other_archive', 'old_gallery', 'null_texlist'):
        for i in range(226):
            c = DrawCPU(exe, b'', 0, 0)
            c.regions = [(BASE, bytearray(exe)), (0x8c160000, bytearray(0x20000)),
                         (0x8c500000, bytearray(0x1000)), (0x8c700000, bytearray(b'\xa5'*0x1000))]
            c.reg[4:7] = [0x8c500800, i, 0x51]
            c.fr4 = 0xc3200000  # -160.0 priority, preserved bit for bit
            c.draws = []
            c.write(0x8c17fba0, 0 if mode == 'null_object' else 0x8c500100, 4)
            c.write(0x8c500100+38, 28 if mode == 'other_slot' else 29, 2)
            c.write(RESOURCE, 0 if mode == 'null_texlist' else 0x8c500200, 4)
            c.write(RESOURCE+12, 0x10018 if mode == 'other_archive' else 0xd70018, 4)
            c.write(0x8c500204, 28 if mode == 'old_gallery' else 35, 4)
            saved = list(c.reg[8:]); stack = bytes(c.regions[-1][1])
            total += run(c, ENTRY, STOP, 1000)
            original = (0x8c500800, i, 0x51, 0xc3200000)
            expected = [(0x8c500800, i+224, 0x51, 0xc3200000), original] if mode == 'gallery' and i in enabled else [original]
            assert c.draws == expected, (mode, i, c.draws)
            assert c.reg[8:] == saved
            assert c.regions[-1][1][:0x700] == stack[:0x700] and c.regions[-1][1][0x800:] == stack[0x800:]
            cases += 1
    return {'cases': cases, 'instructions': total, 'draw_order_and_arguments': 'pass',
            'ABI_and_stack_guards': 'pass', 'draw_endpoint': 'bounded recorder; no GPU execution'}


class InitCPU(AttackCPU):
    def execute(self, pc, delay=False):
        if pc == 0x8c0219e2:
            self.reg[0] = 0; return self.pr
        if pc == 0x8c021a16:
            self.reg[0] = 0x8c500000; return self.pr
        return super().execute(pc, delay)


class GeometryCPU(AttackCPU):
    fdis = capstone.Cs(capstone.CS_ARCH_SH,capstone.CS_MODE_SH4|capstone.CS_MODE_SHFPU|capstone.CS_MODE_LITTLE_ENDIAN)
    def execute(self, pc, delay=False):
        ins = next(self.fdis.disasm(self.read(pc,2).to_bytes(2,'little'),pc))
        op,args=ins.mnemonic,split_ops(ins.op_str)
        def number(reg): return int(reg[2:])
        def fbits(value): return struct.unpack('<I',struct.pack('<f',value))[0]
        def fvalue(bits): return struct.unpack('<f',struct.pack('<I',bits))[0]
        if op == 'fmov':
            a,b=args
            if a.startswith('@'): self.fr[number(b)]=self.read(self.address(a,4),4)
            elif b.startswith('@'): self.write(self.address(b,4,True),self.fr[number(a)],4)
            else: self.fr[number(b)]=self.fr[number(a)]
            return pc+2
        if op == 'lds' and args[1] == 'fpul': self.fpul=self.value(args[0]);return pc+2
        if op == 'float': self.fr[number(args[1])]=fbits(float(signed(self.fpul)));return pc+2
        if op == 'fmul':
            a,b=map(number,args);self.fr[b]=fbits(fvalue(self.fr[b])*fvalue(self.fr[a]));return pc+2
        return super().execute(pc,delay)


def geometry(exe, dat):
    start=struct.unpack_from('<I',dat,4)[0]+4
    steps=0
    for i in range(448):
        c=GeometryCPU(exe,b'',0,0)
        c.regions=[(BASE,bytearray(exe)),(0x8c500000,bytearray(dat)),
                   (0x8c510000,bytearray(32)),(0x8c700000,bytearray(b'\xa5'*0x2000))]
        c.reg[4:7]=[0x8c510000,i,0];c.reg[8]=0x8c701000;c.reg[15]=0x8c700fc0
        c.write(0x8c51001c,0x8c500000+start,4)
        c.write(0x8c51000c,0x3f800000,4);c.write(0x8c510010,0x3f800000,4)
        c.fr=[0]*16;c.fpul=0;c.visited=set()
        steps+=run(c,0x8c0ac310,0x8c0ac39c,1000)
        f=lambda value:struct.unpack('<f',value.to_bytes(4,'little'))[0]
        bounds=[f(v) for v in c.fr[:4]]
        expected=[0.,0.,64.,72.] if i<224 else [0.,48.,64.,72.]
        assert bounds == expected,(i,bounds)
        # The real geometry routine pushes four UV corners in this order.
        uv=[f(c.read(0x8c700fe0+j*4,4)) for j in range(8)]
        if i>=224:
            page,cell=divmod(i-224,32);x,y=cell%5*192,cell//5*72
            assert uv == [(y+72)/512,(x+192)/1024,y/512,(x+192)/1024,(y+72)/512,x/1024,y/512,x/1024],(i,uv)
    return {'cases':448,'instructions':steps,'native_bounds_and_normalized_UVs':'pass',
            'scope':'Actual Ninja pre-transform geometry; GPU submission and rasterization excluded'}


def registration(exe, raw, count, textures):
    c = InitCPU(exe, b'', 0, 0)
    c.regions = [(BASE, bytearray(exe)), (0x8c160000, bytearray(0x20000)),
                 (0x8c500000, bytearray(raw)), (0x8c700000, bytearray(b'\xa5'*0x2000))]
    c.reg[15] = 0x8c701000
    c.write(0x8c171710, 29, 1); c.write(0x8c171711, 24, 1); c.write(0x8c171712, 214, 2)
    c.visited = set(); saved = list(c.reg[8:])
    n = run(c, 0x8c031b7c, STOP, 100000)
    assert c.reg[0] == 0xffffffff and c.reg[8:] == saved
    assert c.read(RESOURCE, 4) == 0x8c500008
    sprite = 4 + struct.unpack_from('<I', raw, 4)[0]
    assert c.read(RESOURCE+4, 4) == 0x8c500000+sprite
    assert c.read(RESOURCE+8, 4) == 0x8c500000 and c.read(RESOURCE+12, 4) == 0xd70018
    assert c.read(RESOURCE+16, 2) == count
    relocated = bytearray(raw)
    for at in [8]+[16+12*i for i in range(textures)]:
        value = struct.unpack_from('<I', raw, at)[0]
        struct.pack_into('<I', relocated, at, value+0x8c500008)
    assert c.regions[2][1] == relocated
    assert c.regions[-1][1][:0xf00] == b'\xa5'*0xf00 and c.regions[-1][1][0x1000:] == b'\xa5'*0x1000
    return {'sprites': count, 'textures': textures, 'instructions': n, 'relocation_and_record_scan': 'pass',
            'I/O_poll_and_read': 'bounded fixtures; registration and relocation execute'}


def check(reuse_prs=False):
    files, names, recipe, component, names_report = compose()
    archive, exe, _, outputs, pages, old_images = album()
    base = ROOT / 'work/output' / PRIOR
    for name, raw in files.items(): assert (OUT/name).read_bytes() == raw
    assert (OUT/'D_NAMES.en.dec.bin').read_bytes() == names
    print('Native dispatch...', flush=True)
    draws = dispatch(exe, {r['sprite'] for r in component['records']})
    source = (base/'ALBUM.AFS').read_bytes()
    regs = [registration(exe, member(source,214),224,28), registration(exe,member(archive,214),448,35)]
    geom = geometry(exe,member(archive,214))
    directory = directory_bytes('ALBUM.AFS', archive)
    lookup_steps = 0
    for row in compact_positions(archive):
        off, size, n = lookup(exe,'ALBUM.AFS',directory,row['member']); lookup_steps += n
        assert off == row['declared_offset'] and size == row['sectors']
    layout = require_native_layouts({'ALBUM.AFS':archive})
    for i in range(214): assert member(source,i) == member(archive,i)
    assert member(source,243) == member(archive,250)
    cells = json.loads((ROOT/'work/ui/asset-audit/ALBUM/captions/rectangles.json').read_text('utf-8'))['rectangles']
    enabled = {r['sprite'] for r in component['records']}
    for row in cells:
        old = old_images[row['texture_member']]
        new = pixels(outputs[row['texture_member']][1],256,256)
        x,y,u,v = row['source_box']
        assert np.array_equal(old[y:y+48,x:u],new[y:y+48,x:u])
        if row['sprite'] in enabled: assert not np.any(new[y+48:v,x:u])
        else: assert np.array_equal(old[y:v,x:u],new[y:v,x:u])
    texture_cases = []
    for page in range(7):
        raw = outputs[243+page][1]
        palette = np.frombuffer(raw[32:2080],'<u2').reshape(256,4)
        index = np.frombuffer(raw[2080:],np.uint8)[untwiddle_indices(512,256)]
        decoded = np.zeros((512,1024),'<u2')
        for dx,dy,k in [(0,0,0),(0,1,1),(1,0,2),(1,1,3)]: decoded[dy::2,dx::2] = palette[index,k]
        alpha = np.array([0,85,187,255])
        gray = (29*(255-alpha)+127)//255
        colors = (0x8000 | gray<<10 | gray<<5 | gray).astype('<u2')
        assert np.array_equal(decoded,colors[pages[page]])
        c = CPU(exe,b'',0,0); c.regions.append((0x8c510000,bytearray(b'\xa5'*128)))
        c.reg[4:8] = [0x8c510020,1024,512,0x300]; saved=list(c.reg[8:])
        n = run(c,0x8c0e1c4c,STOP,10000)
        assert c.reg[0] == 4 and c.reg[8:] == saved
        assert [c.read(0x8c510020+i*4,4) for i in range(8)] == [0x03000002,1,0,1024,512,0x20800,12,0xa5a5a5a5]
        assert c.regions[-1][1][:32] == b'\xa5'*32 and c.regions[-1][1][60:] == b'\xa5'*68
        texture_cases.append({'page':page,'native_texture_info_instructions':n,'native_VRAM_bytes':0x20800,'VQ_roundtrip':'pixel-exact'})
    print('Native registration, 251 archive lookups and lossless VQ passed.',flush=True)
    font = font_bytes((base/'WIN00.AFS').read_bytes())[1]
    metrics = json.loads((base/'skies-font-component-report.json').read_text('utf-8'))['metrics']
    bounds = {b:{r['character']:r['packed_mask_bounds'] for r in m} for b,m in metrics.items()}
    cases=[]
    def ui(key,args=(),limit=248):
        gs,n = parse_ui(exe,font,names,entry(names,key),args,x=8)
        right=0
        for ch,x,y,small in gs:
            b = bounds['small' if small else 'medium'][ch]
            if b: right=max(right,x+b[2]/4+1)
        assert right<=limit,(key,right,limit)
        cases.append({'id':key,'instructions':n,'ink_right':right,'limit':limit})
        return gs
    for i in (192,193,194,219): ui(f'names.g00.{i}')
    gs=ui('names.g00.223',limit=104)
    lines={y:''.join(g[0] for g in gs if g[2]==y) for _,_,y,_ in gs}
    assert list(lines.values())==[f'Port {p} - Slot {s}' for p in 'ABCD' for s in (1,2)]
    for i in (210,211): ui(f'names.g00.{i}',limit=104)
    for p in 'ABCD':
        for s in (1,2):
            for i in (208,209): ui(f'names.g00.{i}',[(f'Port {p} - Slot {s}',False)],limit=248)
    print('Memory-card UI:',len(cases),'native parser cases passed. Native PRS...',flush=True)
    reuse = None
    if reuse_prs:
        path=OUT/'UV-stage-native-test.json';old=json.loads(path.read_text('utf-8'))
        old_component=json.loads((OUT/'UV-stage-component-report.json').read_text('utf-8'))
        assert old['archive_sha256']==old_component['archive_sha256']
        assert old['executable_sha256']==digest(exe)==old_component['executable_sha256']
        assert old['names_packed_sha256']==digest(files['D_NAMES.BIN'])
        assert old['names_decoded_sha256']==digest(names)
        assert old_component['resource_outputs']==component['resource_outputs']
        prs=old['native_PRS_instructions'];assert set(prs)=={'D_NAMES'}|{str(i) for i in outputs}
        reuse={'source_proof_sha256':digest(path.read_bytes()),'source_archive_sha256':old['archive_sha256'],
               'source_component_sha256':digest((OUT/'UV-stage-component-report.json').read_bytes()),
               'scope':'Only uncompressed DAT UV words changed after this pass; every PRS input/output and executable byte identical'}
    else:
        prs = {'D_NAMES':verify(exe,files['D_NAMES.BIN'],names,65536)}
        for i,(packed,raw) in outputs.items():
            prs[str(i)] = verify(exe,packed[16:],raw,len(raw))
            if i%7 == 0: print('Native PRS member',i,flush=True)
    return {'version':VERSION,'source_build':PRIOR,'executable_sha256':digest(exe),
        'archive_sha256':digest(archive),'names_packed_sha256':digest(files['D_NAMES.BIN']),
        'names_decoded_sha256':digest(names),'caption_dispatch':draws,'registration':regs,'geometry':geom,
        'archive_lookup_cases':251,'archive_lookup_instructions':lookup_steps,'archive_layout':layout,
        'protected_photo_cells':224,'unchanged_placeholder_cells':21,'unchanged_fullsize_members':214,
        'texture_cases':texture_cases,'UI_cases':cases,'native_PRS_instructions':prs,'PRS_identity_reuse':reuse,
        'caption_source_pixels_and_four_shades':'preserved; no reconstruction',
        'limits':['GPU drawing/depth/alpha and live album navigation need testing',
                  'Total live VRAM occupancy is not measured; additional captions require 931840 bytes',
                  'UI context/parameters, async read/poll and draw endpoint use bounded fixtures']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true')
    ap.add_argument('--reuse-prs',action='store_true',help='Require exact pre-UV-stage compressed stream, output and executable identities')
    args=ap.parse_args(); assert not args.write_report or args.verify
    if not args.verify: print('DRY RUN: plan dispatch guards, native registration, all archive lookups, VQ pixels, slot UI and 36 PRS streams.');return
    report=check(args.reuse_prs)
    if args.write_report: (OUT/'native-test.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('PASS: memory-card and album-caption gates.',flush=True)


if __name__ == '__main__': main()
