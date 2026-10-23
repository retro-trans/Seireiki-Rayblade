"""Decode original Rayblade text without changing or discarding control bytes.

The F0..FA glyph formula and FB..FF controls are reconstructed from the
original SH-4 renderer at file offsets 0x6ac64..0x6b28e.
Unknown glyphs remain explicit markers. Parsing is independent of translation.
decode returns one display page at FE/FF. Scenario callers follow FE pages
through FF; FC with second parameter 3C includes two additional operand bytes.
"""
import json
import struct
from build_font_patch import ROOT


class TextCodec:
    def __init__(self):
        data=json.loads((ROOT/'work/source/font/original-charmap.json').read_text(encoding='utf-8'))
        self.glyphs={int(k):v['text'] for k,v in data['glyphs'].items()}

    def decode(self,data,start=0,limit=None,ascii_mode=False):
        pos=start;tokens=[];unknown=set();pieces=[];end=min(len(data),limit if limit is not None else len(data))
        while pos<end:
            offset=pos;b=data[pos];pos+=1
            if b in (0xfe,0xff):
                tokens.append({'offset':offset-start,'raw':data[offset:pos].hex(),'kind':'end'})
                return {'text':''.join(pieces),'tokens':tokens,'unknown_glyphs':sorted(unknown),
                        'bytes_consumed':pos-start,'terminator':b,'raw_hex':data[start:pos].hex(),
                        'ascii_mode_at_end':ascii_mode}
            if b==0xfc:
                if pos+2>end:raise ValueError('Truncated FC control')
                p1,p2=data[pos:pos+2];pos+=2;text='<FC:{:02X}:{:02X}>'.format(p1,p2)
                if p2==0x3c:
                    if pos+2>end:raise ValueError('Truncated five-byte FC 3C control')
                    text='<FC:{:02X}:{:02X}:{:02X}:{:02X}>'.format(p1,p2,data[pos],data[pos+1]);pos+=2
                kind='control'
            elif b==0xfd:text='<NL>';kind='newline'
            elif b==0xfb:
                ascii_mode=not ascii_mode;text='<ASCII:ON>' if ascii_mode else '<ASCII:OFF>';kind='mode'
            else:
                if 0xf0<=b<=0xfa:
                    if pos>=end:raise ValueError('Truncated wide glyph')
                    gid=((b<<8)+data[pos]+0x1100)&0xffff;pos+=1
                elif ascii_mode:
                    text=chr(b) if 32<=b<=126 else '<ASCII:{:02X}>'.format(b)
                    tokens.append({'offset':offset-start,'raw':data[offset:pos].hex(),'kind':'glyph','text':text})
                    pieces.append(text);continue
                else:gid=b
                text=self.glyphs.get(gid)
                if text is None:unknown.add(gid);text='<G{:04X}>'.format(gid)
                kind='glyph'
            tokens.append({'offset':offset-start,'raw':data[offset:pos].hex(),'kind':kind,'text':text})
            pieces.append(text)
        raise ValueError('Text has no terminator before bound at 0x{:x}'.format(start))


def relative_target(data,pos):
    if not 0<=pos<=len(data)-4:raise ValueError('Pointer outside data')
    target=pos+struct.unpack_from('<I',data,pos)[0]
    if not 0<=target<len(data):raise ValueError('Relative target outside data')
    return target


def names_tables(data):
    # Root groups 13 onward include binary gameplay data, not text. Group 6
    # and 7 share a string pool: root 7 points into the combined pointer bank.
    counts=[256,64,144,128,256,64,256,144,128,48,128,144,80]
    assert struct.unpack_from('<I',data)[0]==23*4
    for group,count in enumerate(counts):
        start=relative_target(data,group*4)
        for index in range(count):
            pointer=start+index*4;target=relative_target(data,pointer)
            yield group,index,pointer,target
