"""Verify page/control boundaries against the original SH-4 text formatter.

No files are modified. Uses exact golden streams plus three original commands;
tests FE continuation, five-byte FC 3C operands and consumed command length.
"""
from build_font_patch import ROOT
from rayblade_text import TextCodec
from test_font_patch import CPU


def meaningful_tokens(data):
    result=[];pos=0
    while pos<len(data):
        start=pos;value=data[pos];pos+=1
        if value==0xff:
            if pos!=len(data):raise ValueError('Unexpected bytes after FF')
            return result
        if value==0xfc:
            if pos+2>len(data):raise ValueError('Truncated FC')
            pos+=4 if data[pos+1]==0x3c else 2
        elif 0xf0<=value<=0xfa:pos+=1
        if pos>len(data):raise ValueError('Truncated text operand')
        if value not in (0xfd,0xfe):result.append(data[start:pos])
    raise ValueError('Missing FF')


def native_format(exe,payload,*,limit=0x3ff,capacity=4096,width=30):
    assert 0 < limit < capacity
    source=0x8c500000;target=0x8c600000;guard=64
    cpu=CPU(exe,b'',0,0)
    cpu.regions=[cpu.regions[0],(source,bytearray(payload)),
                 (target-guard,bytearray(b'\xa5'*(capacity+2*guard))),cpu.regions[-1]]
    cpu.reg[4:8]=[target,source,width,3]
    cpu.write(cpu.reg[15],limit,4)
    saved=cpu.reg[8:];cpu.pc=0x8c07bc00
    for count in range(200_000):
        if cpu.pc==0xdead0000:break
        cpu.pc=cpu.execute(cpu.pc)
    else:raise ValueError('Native formatter instruction limit')
    if cpu.reg[8:]!=saved or cpu.reg[0]!=len(payload):
        raise ValueError('Native formatter ABI/consumed byte count mismatch')
    destination,offset=cpu.area(target,capacity)
    # The formatter always emits an FF. Derive its end with the native
    # operand lengths so FF inside a five-byte FC control is not mistaken.
    end=0
    while True:
        value=destination[offset+end];end+=1
        if value==0xff:break
        if value==0xfc:end+=4 if destination[offset+end+1]==0x3c else 2
        elif 0xf0<=value<=0xfa:end+=1
        if end>=capacity:raise ValueError('No native output terminator')
    output=bytes(destination[offset:offset+end])
    if destination[:guard]!=b'\xa5'*guard or destination[offset+end:]!=b'\xa5'*(capacity-end+guard):
        raise ValueError('Unexpected formatter destination writes')
    if meaningful_tokens(output)!=meaningful_tokens(payload):
        raise ValueError('Native formatter lost or changed glyph/control bytes')
    return output,count


def main():
    exe=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();codec=TextCodec()
    golden=[bytes.fromhex('01fe02ff'),bytes.fromhex('01fc843cfeff02ff'),
            bytes.fromhex('01fdfc843c1df0fe02ff')]
    for payload in golden:
        output,count=native_format(exe,payload)
        if output!=payload:raise ValueError('Golden native formatter bytes differ')
    special=codec.decode(golden[1])
    assert special['bytes_consumed']==len(golden[1]) and special['unknown_glyphs']==[]
    assert special['text']=='A<FC:84:3C:FE:FF>B'
    for member,start in [('s_002.bin',0x466),('s_106.bin',0x2309),('s_16b.bin',0xedb)]:
        data=(ROOT/'work/source/scenario'/member).read_bytes()
        assert data[start:start+2]==b'\x8a\x06'
        pos=start+3;mode=False;pages=[]
        while True:
            decoded=codec.decode(data,pos,ascii_mode=mode)
            assert not decoded['unknown_glyphs']
            pages.append(decoded);pos+=decoded['bytes_consumed'];mode=decoded['ascii_mode_at_end']
            if decoded['terminator']==0xff:break
        payload=data[start+3:pos];output,count=native_format(exe,payload)
        print('PASS:',member,hex(start),len(pages),'source pages;',len(payload),
              'bytes consumed through FF;',count,'original SH-4 instructions; glyph/control bytes retained.')
    print('PASS: 3 golden FE/FC3C streams; FF in control operands is not a terminator.')


if __name__=='__main__':main()
