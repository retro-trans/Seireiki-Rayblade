"""Run the actual movie initializer, setters and 640-pixel drawing adapters."""
import argparse
import json
import struct
from build_native_movie_font import compose, ROOT, OUT, digest
from test_memory_album_patch import GeometryCPU

BASE, STOP, OBJ, STACK = 0x8c010000, 0xdead0000, 0x8c500000, 0x8c708000


def bits(f):
    return struct.unpack('<I', struct.pack('<f', f))[0]


def value(n):
    return struct.unpack('<f', struct.pack('<I', n))[0]


class DrawCPU(GeometryCPU):
    def execute(self, pc, delay=False):
        word = self.read(pc, 2)
        if word & 0xf00f == 0x300e:  # ADDC
            n, m = word >> 8 & 15, word >> 4 & 15
            total = self.reg[n] + self.reg[m] + self.t
            self.reg[n], self.t = total & 0xffffffff, int(total > 0xffffffff)
            return pc + 2
        if word & 0xf00f == 0xf000:  # FADD, including adapter delay semantics
            n, m = word >> 8 & 15, word >> 4 & 15
            self.fr[n] = bits(value(self.fr[n]) + value(self.fr[m]))
            return pc + 2
        if pc in (0x8c0ab970, 0x8c0a9db0, 0x8c0a7c06):
            self.draws.append((pc, self.reg[4:7], self.fr[4]))
            if pc == 0x8c0ab970:
                p = self.reg[4]
                expected = bytearray(self.original)
                for o in (0, 4, 12, 16):
                    struct.pack_into('<f', expected, o, struct.unpack_from('<f', expected, o)[0] * 2)
                assert bytes(self.read(p+o, 1) for o in range(32)) == expected
            elif pc == 0x8c0a9db0:
                p, count = self.reg[4:6]
                assert count == self.count
                ptr = self.read(p, 4)
                assert bytes(self.read(p+o, 1) for o in range(4, 16)) == self.original[4:]
                assert [value(self.read(ptr+o*4, 4)) for o in range(count*2)] == [f*2 for f in self.points]
            else:
                p = self.reg[5]
                assert [value(self.read(p+o*4, 4)) for o in range(4)] == [f*2 for f in self.points]
            self.reg[0], self.reg[2] = 0x12345678, 0x8c5f0040
            return self.pr
        return super().execute(pc, delay)


class MovieCPU(DrawCPU):
    def execute(self, pc, delay=False):
        if pc == 0x8c09e614:  # Player allocation endpoint only
            self.reg[0] = OBJ
            return self.pr
        if pc == 0x8c09fe00:  # Priority setter, unrelated to rectangle geometry
            assert self.reg[4] == OBJ
            return self.pr
        if pc in (0xdead1000, 0xdead2000):
            self.calls.append((pc, self.reg[4], self.reg[5]))
            return self.pr
        return super().execute(pc, delay)


def fresh(exe, cls=DrawCPU):
    c = cls(exe, b'', 0, 0)
    c.regions = [(BASE, bytearray(exe)), (0x8c180000, bytearray(0x10000)),
                 (0x8c1d0000, bytearray(0x10000)), (OBJ, bytearray(0x20000)),
                 (0x8c700000, bytearray(b'\xa5' * 0x10000))]
    c.reg[15], c.pr = STACK, STOP
    c.fr = [bits(i+.25) for i in range(16)]
    c.fpul, c.draws, c.calls, c.visited = 0, [], [], set()
    return c


def run(c, entry, limit=20000):
    saved, floats = c.reg[8:], c.fr[12:]
    c.pc = entry
    for n in range(limit):
        if c.pc == STOP:
            assert c.reg[8:] == saved and c.fr[12:] == floats and c.pr == STOP
            return n
        c.pc = c.execute(c.pc)
    raise AssertionError(('Native execution bound', hex(c.pc)))


def check():
    exe, archive, _, _, component = compose()
    frames, steps = [], 0
    for i in range(129):
        filename, w, h = struct.unpack_from('<3I', exe, 0x88e74+12*i)
        c = fresh(exe, MovieCPU)
        c.write(OBJ, OBJ+0x200, 4)
        c.write(OBJ+0x200+40, 0xdead1000, 4)
        c.write(OBJ+0x200+24, 0xdead2000, 4)
        c.reg[4] = i
        before = bytes(c.regions[0][1])
        steps += run(c, BASE+0x29fe8)
        if filename == BASE+0x87bac:
            assert not c.calls
            continue
        xywh = [value(c.read(OBJ+o, 4)) for o in (116, 120, 128, 132)]
        assert xywh == [2*((320-w)//2), 2*((240-h)//2), w*2, h*2], (i, xywh, w, h)
        assert c.calls == [(0xdead1000, OBJ, 0), (0xdead2000, OBJ, filename)]
        assert bytes(c.regions[0][1]) == before
        frames.append({'id': i, 'source': [w, h], 'display_xywh': xywh})
    draw_cases = 0
    for x, y, sx, sy in ((0., 0., 1., 1.), (-12.5, 24., .5, 3.), (160., 120., -1., .75)):
        c = fresh(exe)
        c.original = struct.pack('<5f3I', x, y, -.5, sx, sy, 0x1234, 0x8c500100, 0x8c500200)
        c.regions[3][1][0x1000:0x1020] = c.original
        c.reg[4:7] = [OBJ+0x1000, 77, 0x51]
        depth = c.fr[4]
        steps += run(c, int(component['rendering']['sprite_wrapper'], 16))
        assert c.draws[0][1][1:] == [77, 0x51] and c.draws[0][2] == depth
        assert c.regions[3][1][0x1000:0x1020] == c.original
        assert c.reg[0] == 0x12345678 and c.reg[2] == 0x8c5f0040
        draw_cases += 1
    for count in (0, 1, 2, 4, 16, 129):
        c = fresh(exe)
        c.count, c.points = count, [float(j-7)*.5 for j in range(count*2)]
        c.original = struct.pack('<4I', OBJ+0x2000, 0x8c500300, 0x8c500400, count)
        c.regions[3][1][0x1000:0x1010] = c.original
        c.regions[3][1][0x2000:0x2000+count*8] = struct.pack('<'+'f'*count*2, *c.points)
        c.reg[4:7] = [OBJ+0x1000, count, 0x60]
        before = bytes(c.regions[3][1])
        steps += run(c, int(component['rendering']['polygon_wrapper'], 16))
        assert c.draws[0][1][2] == 0x60 and bytes(c.regions[3][1]) == before
        draw_cases += 1
    for mode in (0, 1, 2, 3, 4):
        c = fresh(exe)
        c.points = [12., 24., 308., 216.]
        raw = struct.pack('<4f', *c.points)
        c.regions[3][1][0x1000:0x1010] = raw
        c.reg[4:6] = [mode, OBJ+0x1000]
        steps += run(c, int(component['rendering']['clip_wrapper'], 16))
        assert c.draws[0][1][0] == mode and c.regions[3][1][0x1000:0x1010] == raw
        draw_cases += 1
    assert archive == (ROOT/'work/output/skies-render-test/WIN00.AFS').read_bytes()
    return {'version': component['version'], 'executable_sha256': digest(exe),
            'movie_cases': len(frames), 'movies': frames, 'drawing_adapter_cases': draw_cases,
            'SH4_instructions': steps, 'ABI_input_preservation': 'pass',
            'scope': 'Actual application movie initialization plus original native position/size setters; renderer adapter endpoint argument witnesses. Allocation/priority/start/draw endpoints are fixtures; GPU/video requires live verification.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write-report', action='store_true')
    args = ap.parse_args()
    proof = check()
    print(json.dumps({k: v for k, v in proof.items() if k != 'movies'}, indent=2))
    if args.write_report:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT/'native-geometry-test.json').write_text(json.dumps(proof, indent=2)+'\n', 'utf-8')
