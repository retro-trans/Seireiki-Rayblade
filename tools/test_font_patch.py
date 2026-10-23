"""Offline SH-4 execution comparison against the original glyph routine.

Runs original and replacement instructions in an integer-only interpreter.
This verifies raster output/ABI for selected cases; it is not emulator playtesting.
No game or translation files are written.
"""
import random
import re
import struct
import sys
from pathlib import Path
from build_font_patch import ROOT, BASE, START, END, assemble, font_data, widths,metrics,unswap

sys.path.insert(0, str(ROOT / 'work/vendor'))
import capstone


def signed(value):
    value &= 0xffffffff
    return value - 0x100000000 if value & 0x80000000 else value


def split_ops(value):
    result, start, level = [], 0, 0
    for n, ch in enumerate(value):
        if ch == '(':
            level += 1
        elif ch == ')':
            level -= 1
        elif ch == ',' and level == 0:
            result.append(value[start:n].strip()); start = n + 1
    result.append(value[start:].strip())
    return result


class CPU:
    decoded = {}
    dis = capstone.Cs(capstone.CS_ARCH_SH,capstone.CS_MODE_SH4 | capstone.CS_MODE_LITTLE_ENDIAN)

    def __init__(self, exe, font, glyph, flags, color=17):
        self.reg = [(0x12340000 + i * 0x100) for i in range(16)]
        self.reg[4] = glyph; self.reg[15] = 0x8c700800
        self.pr = 0xdead0000; self.macl = 0; self.t = 0; self.pc = BASE + START
        self.regions = [(BASE,bytearray(exe)),(0x8c600000,bytearray(font)),
            (0x8c1f36a0,bytearray(0x100)),(0x8c500000,bytearray([0x23,0x81])* (256*40)),
            (0x8c700000,bytearray(0x1000))]
        self.write(0x8c1f36a0,0x8c600300,4); self.write(0x8c1f36a4,0x8c600000,4)
        self.write(0x8c1f36ac,0x8c500000,4); self.write(0x8c1f36b0,256,2)
        self.write(0x8c1f36b4,color,2); self.write(0x8c1f36b6,12,2)
        self.write(0x8c1f36b8,4,2); self.write(0x8c1f36ba,flags,1)

    def area(self, address, count):
        for base, data in self.regions:
            if base <= address and address + count <= base + len(data):
                return data, address - base
        raise ValueError('Unmapped access {:08x}+{}'.format(address,count))

    def read(self, address, count):
        data, off = self.area(address,count)
        return int.from_bytes(data[off:off+count],'little')

    def write(self,address,value,count):
        data, off = self.area(address,count)
        data[off:off+count]=(value & ((1 << (count*8))-1)).to_bytes(count,'little')

    def value(self,operand):
        if operand.startswith('r'):
            return self.reg[int(operand[1:])]
        if operand.startswith('#'):
            return int(operand[1:],0) & 0xffffffff
        return int(operand,0)

    def address(self,operand,size,write=False):
        body=operand[1:]
        if body.startswith('-r'):
            reg=int(body[2:]);self.reg[reg]=(self.reg[reg]-size)&0xffffffff
            return self.reg[reg]
        if body.startswith('('):
            offset,reg=split_ops(body[1:-1])
            return (self.value(offset)+self.value(reg))&0xffffffff
        if body.endswith('+'):
            reg=int(body[1:-1]);address=self.reg[reg];self.reg[reg]=(address+size)&0xffffffff
            return address
        return self.value(body)

    def ins(self,pc):
        word=self.read(pc,2)
        key=(pc,word)
        if key not in self.decoded:
            ins=next(self.dis.disasm(word.to_bytes(2,'little'),pc),None)
            if ins is None:raise ValueError('Unknown SH4 instruction at {:x}'.format(pc))
            self.decoded[key]=(ins.mnemonic,split_ops(ins.op_str))
        return self.decoded[key]

    def execute(self,pc,delay=False):
        op, args=self.ins(pc)
        next_pc=pc+2
        a=args[0];b=args[1] if len(args)>1 else None
        def put(operand,value):self.reg[int(operand[1:])]=value & 0xffffffff
        if op=='nop':pass
        elif op.startswith('mov.'):
            size={'b':1,'w':2,'l':4}[op[-1]]
            if a.startswith('@') or a.startswith('0x'):
                address=self.address(a,size) if a.startswith('@') else int(a,16)
                value=self.read(address,size)
                if size<4 and value & (1 << (size*8-1)):value-=1 << (size*8)
                put(b,value)
            else:self.write(self.address(b,size,True),self.value(a),size)
        elif op=='mov':put(b,self.value(a))
        elif op in ('extu.b','extu.w','exts.b','exts.w'):
            mask=255 if op.endswith('.b') else 65535;v=self.value(a)&mask
            if op.startswith('exts') and v&(mask//2+1):v-=mask+1
            put(b,v)
        elif op in ('add','sub','and','or','xor'):
            x,y=self.value(a),self.value(b)
            put(b,{'add':lambda:y+x,'sub':lambda:y-x,'and':lambda:y&x,'or':lambda:y|x,'xor':lambda:y^x}[op]())
        elif op=='tst':self.t=int((self.value(a)&self.value(b))==0)
        elif op.startswith('cmp/'):
            kind=op[4:]
            if b is None:
                self.t=int(signed(self.value(a)) >= 0 if kind=='pz' else signed(self.value(a))>0)
            else:
                x,y=self.value(a),self.value(b)
                self.t=int({'eq':lambda:y==x,'hs':lambda:y>=x,'hi':lambda:y>x,
                    'ge':lambda:signed(y)>=signed(x),'gt':lambda:signed(y)>signed(x)}[kind]())
        elif op in ('shll','shal','shlr','shar'):
            value=self.value(a)
            if op in ('shll','shal'):self.t=value>>31;put(a,value<<1)
            else:self.t=value&1;put(a,(signed(value)>>1) if op=='shar' else value>>1)
        elif op in ('shll2','shll8','shll16','shlr2','shlr8','shlr16'):
            count=int(op[4:]);put(a,self.value(a)<<count if op.startswith('shll') else self.value(a)>>count)
        elif op in ('shad','shld'):
            count=signed(self.value(a));value=self.value(b)
            if count>=0:put(b,value << (count&31))
            else:
                amount=(-count)&31
                if not amount:amount=32
                put(b,(signed(value) if op=='shad' else value)>>amount)
        elif op=='dt':put(a,self.value(a)-1);self.t=int(self.value(a)==0)
        elif op=='movt':put(a,self.t)
        elif op=='neg':put(b,-self.value(a))
        elif op=='not':put(b,~self.value(a))
        elif op=='swap.w':put(b,((self.value(a)<<16)|(self.value(a)>>16)))
        elif op in ('mul.l','mulu.w','muls.w'):
            x,y=self.value(a),self.value(b)
            if op=='mulu.w':x&=65535;y&=65535
            if op=='muls.w':x=(x&65535)-65536 if x&32768 else x&65535;y=(y&65535)-65536 if y&32768 else y&65535
            self.macl=(x*y)&0xffffffff
        elif op=='sts':
            if a!='macl':raise ValueError(op+str(args))
            put(b,self.macl)
        elif op=='sts.l':self.write(self.address(b,4,True),self.pr,4)
        elif op=='lds.l':self.pr=self.read(self.address(a,4),4)
        elif op in ('bt','bf','bt/s','bf/s','bra','bsr','jmp','jsr','rts'):
            if delay:raise ValueError('Branch in delay slot')
            take= op not in ('bt','bf','bt/s','bf/s') or (bool(self.t) if op.startswith('bt') else not self.t)
            target=self.pr if op=='rts' else (self.address(a,0) if op in ('jmp','jsr') else self.value(a))
            has_delay=op not in ('bt','bf')
            if op in ('bsr','jsr'):self.pr=pc+4
            if has_delay:self.execute(pc+2,True)
            if take and op=='jsr' and target==0x8c093c48:
                # SDK register-call memcpy used twice by the original font routine.
                count=self.reg[0]
                content=bytes(self.read(self.reg[2]+i,1) for i in range(count))
                for i,v in enumerate(content):self.write(self.reg[1]+i,v,1)
                next_pc=pc+4
            else:next_pc=target if take else pc+(4 if has_delay else 2)
        else:raise ValueError('Unsupported {} {} at {:x}'.format(op,args,pc))
        return next_pc

    def run(self):
        initial=self.reg[8:]
        for count in range(20000):
            if self.pc==0xdead0000:
                assert self.reg[8:]==initial,'Callee-saved registers or stack changed'
                return count
            self.pc=self.execute(self.pc)
        raise ValueError('Instruction limit exceeded')


def reference_pixels(exe,font,glyph,flags,bearing):
    if flags&64:
        start=((glyph-32)&127)*8;height=8;width=8;pitch=1
    elif glyph<512:
        start=0x300+glyph*16;height=16;width=8;pitch=1
    else:
        start=0x2300+(glyph-512)*32;height=16;width=12;pitch=2
    result=bytearray([0x23,0x81])*(256*40)
    color=struct.unpack_from('<H',exe,0x880a8+(flags&14)*2+2)[0]
    for y in range(height):
        bits=unswap(font[start+y*pitch])<<24
        if pitch==2:bits|=unswap(font[start+y*pitch+1])<<16
        bits=(bits<<bearing)&0xffffffff
        for x in range(width):
            bit=(bits>>(31-x))&1
            if flags&128:
                struct.pack_into('<H',result,((4+y)*256+12+x+1)*2,0x8000 if bit else 0)
            if bit:struct.pack_into('<H',result,((4+y)*256+12+x)*2,color)
    return result


def main():
    source=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();font=font_data()
    fixed,_=assemble(font,False);vwf,_=assemble(font,True)
    fixed_exe=source[:START]+fixed+source[END:]
    variable_exe=source[:START]+vwf+source[END:]
    cases=[]
    for flags in (0,0x80,2,0x82):
        for glyph in (0,1,9,23,35,62,63,511,512,600,3327):cases.append((glyph,flags))
    for flags in (0x40,0xc0,0x42,0xc2):
        for glyph in (32,33,65,73,87,105,108,126):cases.append((glyph,flags))
    steps=0
    for glyph,flags in cases:
        original=CPU(source,font,glyph,flags);replacement=CPU(fixed_exe,font,glyph,flags)
        steps+=original.run()+replacement.run()
        assert original.regions[3][1]==replacement.regions[3][1], 'Raster mismatch glyph {} flags {:x}'.format(glyph,flags)
        assert original.regions[3][1]==reference_pixels(source,font,glyph,flags,0),'Original/reference bitmap mismatch'
        assert original.read(0x8c1f36b6,2)==replacement.read(0x8c1f36b6,2),'Cursor mismatch'
        variable=CPU(variable_exe,font,glyph,flags);steps+=variable.run()
        sm,md=metrics(font)
        bearing=sm[(glyph-32)&127][1] if flags&64 else (md[glyph][1] if glyph<63 else 0)
        assert reference_pixels(source,font,glyph,flags,bearing)==variable.regions[3][1],'VWF crop/reference mismatch'
        small,medium=widths(font)
        expected=small[(glyph-32)&127] if flags&64 else (medium[glyph] if glyph<63 else (8 if glyph<512 else 12))
        assert variable.read(0x8c1f36b6,2)==12+expected,'VWF advance mismatch'
    print('PASS: {} cases, {:,} SH-4 instructions executed.'.format(len(cases),steps))
    print('Original/new fixed-width raster output and cursor positions match.')
    print('VWF removes empty left bearings, matches an independent bitmap reference, and preserves the ABI.')
    print('Emulator/hardware playtesting is still required.')


if __name__=='__main__':
    main()
