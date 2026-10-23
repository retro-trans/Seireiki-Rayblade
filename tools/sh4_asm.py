"""Small checked SH-4 integer assembler for the font patch.

Emits only the explicitly supported instructions; no external compiler needed.
PC-relative pools and all branch ranges are checked during finalization.
"""
import struct


class Assembler:
    def __init__(self, base):
        self.base = base
        self.data = bytearray()
        self.labels = {}
        self.fixups = []
        self.pool = []

    @property
    def pc(self):
        return self.base + len(self.data)

    def emit(self, word):
        self.data.extend(struct.pack('<H', word))

    def label(self, name):
        if name in self.labels:
            raise ValueError('Duplicate label: ' + name)
        self.labels[name] = self.pc

    def align(self, size=4):
        while self.pc % size:
            self.emit(0x0009)

    def lit(self, value, reg):
        key = ('value', value) if isinstance(value, int) else ('label', value)
        if key not in self.pool:
            self.pool.append(key)
        self.fixups.append(('literal', len(self.data), self.pool.index(key), reg))
        self.emit(0)

    def branch(self, op, label):
        self.fixups.append((op, len(self.data), label, 0))
        self.emit(0)

    def imm(self, value, reg):
        if not -128 <= value <= 127:
            raise ValueError('Immediate outside signed byte range')
        self.emit(0xe000 | reg << 8 | value & 255)

    def addi(self, value, reg):
        if not -128 <= value <= 127:
            raise ValueError('Immediate outside signed byte range')
        self.emit(0x7000 | reg << 8 | value & 255)

    def rr(self, op, src, dst):
        codes = {'mov':0x6003,'add':0x300c,'sub':0x3008,'and':0x2009,
                 'or':0x200b,'tst':0x2008,'cmp/eq':0x3000,'cmp/hs':0x3002,
                 'mul.l':0x0007,'extu.b':0x600c,'extu.w':0x600d,
                 'swap.w':0x6009,'shld':0x400d}
        self.emit(codes[op] | dst << 8 | src << 4)

    def unary(self, op, reg):
        codes={'shll':0x4000,'shlr':0x4001,'shll2':0x4008,'shlr2':0x4009,
               'shll8':0x4018,'shlr8':0x4019,'shll16':0x4028,
               'shlr16':0x4029,'dt':0x4010,'movt':0x0029,'sts.macl':0x001a}
        self.emit(codes[op] | reg << 8)

    def load(self, size, ptr, dst):
        self.emit({'b':0x6000,'w':0x6001,'l':0x6002}[size] | dst << 8 | ptr << 4)

    def store(self, size, src, ptr):
        self.emit({'b':0x2000,'w':0x2001,'l':0x2002}[size] | ptr << 8 | src << 4)

    def push(self, reg):
        self.emit(0x2f06 | reg << 4)

    def pop(self, reg):
        self.emit(0x60f6 | reg << 8)

    def pool_and_finish(self):
        self.align()
        pool_pc = self.pc
        for kind, value in self.pool:
            if kind == 'label':
                value = self.labels[value]
            self.data.extend(struct.pack('<I', value & 0xffffffff))
        for op, offset, target, reg in self.fixups:
            pc = self.base + offset
            if op == 'literal':
                delta = (pool_pc + target * 4) - ((pc + 4) & ~3)
                if delta < 0 or delta % 4 or delta // 4 > 255:
                    raise ValueError('Literal pool out of range at {:x}'.format(pc))
                word = 0xd000 | reg << 8 | delta // 4
            else:
                delta = self.labels[target] - pc - 4
                bits = 12 if op in ('bra','bsr') else 8
                if delta % 2 or not -(1 << (bits-1)) <= delta//2 < (1 << (bits-1)):
                    raise ValueError('Branch out of range: {} -> {}'.format(hex(pc), target))
                word = {'bra':0xa000,'bsr':0xb000,'bt':0x8900,'bf':0x8b00}[op] | (delta//2 & ((1 << bits)-1))
            struct.pack_into('<H', self.data, offset, word)
        return bytes(self.data)
