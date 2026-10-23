"""Rayblade MSB-first PRS-family codec, reconstructed from 1ST_READ.BIN.

Source routine: file offset 0x121a4, load address 0x8c0221a4.
Unlike common Sega PRS, flags are MSB-first and long tokens are big-endian.
No original file is modified. decompress returns (decoded, bytes_used);
compress returns encoded bytes.
"""


def decompress(data, max_output=32 * 1024 * 1024):
    pos, flags, remaining = 0, 0, 0
    output = bytearray()

    def byte():
        nonlocal pos
        if pos >= len(data):
            raise ValueError('Truncated compressed stream at 0x{:x}'.format(pos))
        value = data[pos]
        pos += 1
        return value

    def bit():
        nonlocal flags, remaining
        if not remaining:
            flags, remaining = byte(), 8
        value = (flags >> 7) & 1
        flags = (flags << 1) & 255
        remaining -= 1
        return value

    while True:
        if bit():
            output.append(byte())
        else:
            if bit():
                token = (byte() << 8) | byte()
                distance = (token >> 3) - 8192
                length = token & 7
                if length:
                    length += 2
                else:
                    extra = byte()
                    if extra == 0:
                        return bytes(output), pos
                    length = extra + 1
            else:
                length = (bit() << 1 | bit()) + 2
                distance = byte() - 256
            if distance >= 0 or -distance > len(output):
                raise ValueError('Invalid back-reference at 0x{:x}: {} with {} output'.format(
                    pos, distance, len(output)))
            for _ in range(length):
                output.append(output[len(output) + distance])
        if len(output) > max_output:
            raise ValueError('Decoded output exceeds limit')


def compress(data):
    """Greedy valid PRS encoding; not claimed to be size-optimal.

    Uses short copies at distances 1..256 and long copies at 1..8192, including
    overlapping copies. Control bytes are interleaved exactly as the decoder
    reads them. Every stream ends with a zero-length long token.
    """
    data=bytes(data);output=bytearray();flag_pos=None;remaining=0;pos=0
    def bit(value):
        nonlocal flag_pos,remaining
        if not remaining:flag_pos=len(output);output.append(0);remaining=8
        remaining-=1
        if value:output[flag_pos]|=1<<remaining
    while pos<len(data):
        limit=min(256,len(data)-pos);short_len=0;short_dist=0;long_len=0;long_dist=0
        if limit>=2 and pos:
            candidate=data.rfind(data[pos:pos+2],max(0,pos-256),pos+1)
            if candidate>=0:
                length=2
                while length<min(5,limit) and data[candidate+length]==data[pos+length]:length+=1
                short_len=length;short_dist=pos-candidate
        if limit>=3 and pos:
            low=max(0,pos-8192);upper=pos+2;tries=0;key=data[pos:pos+3]
            while tries<128:
                candidate=data.rfind(key,low,upper)
                if candidate<0:break
                length=3
                while length<limit and data[candidate+length]==data[pos+length]:length+=1
                if length>long_len:long_len=length;long_dist=pos-candidate
                if length==limit:break
                upper=candidate+2;tries+=1
        short_gain=short_len*9-12 if short_len else 0
        long_gain=long_len*9-(18 if long_len<=9 else 26) if long_len else 0
        if short_gain<=0 and long_gain<=0:
            bit(1);output.append(data[pos]);pos+=1
        elif short_gain>=long_gain:
            bit(0);bit(0);bit((short_len-2)>>1);bit((short_len-2)&1)
            output.append(256-short_dist);pos+=short_len
        else:
            bit(0);bit(1)
            token=(8192-long_dist)<<3
            if long_len<=9:token|=long_len-2
            output.extend((token>>8,token&255))
            if long_len>9:output.append(long_len-1)
            pos+=long_len
    bit(0);bit(1);output.extend((0,0,0))
    return bytes(output)
