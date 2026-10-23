"""Encode translated text for the integrated Latin font without stripping controls.

The medium character IDs match build_font4x_patch.MEDIUM. ASCII mode uses
literal ASCII byte values. Unsupported characters fail instead of becoming ?.
"""
import re
from build_font4x_patch import MEDIUM,SMALL


def encode(text,terminator=0xff,*,ascii_mode=False):
    if terminator not in (0xfe,0xff):raise ValueError('Invalid text terminator')
    result=bytearray();pos=0
    while pos<len(text):
        if text[pos]=='<':
            end=text.find('>',pos)
            tag=text[pos:end+1] if end>=0 else ''
            recognized=tag=='<NL>' or tag in ('<ASCII:ON>','<ASCII:OFF>') or bool(re.fullmatch(r'<FC:[0-9A-F]{2}:[0-9A-F]{2}(?::[0-9A-F]{2}:[0-9A-F]{2})?>',tag))
            if not recognized:
                if re.fullmatch(r'<[A-Z][A-Z0-9]*(?::[^>]*)?>',tag) or re.match(r'<(?:FC:|ASCII:|G[0-9A-F])',text[pos:]):
                    raise ValueError('Unsupported control tag '+repr(tag))
                # Ordinary angle brackets remain printable Latin punctuation.
                ch=text[pos];pos+=1
                result.append(ord(ch) if ascii_mode else MEDIUM.index(ch));continue
            if tag=='<NL>':result.append(0xfd)
            elif tag in ('<ASCII:ON>','<ASCII:OFF>'):
                desired=tag=='<ASCII:ON>'
                if desired==ascii_mode:raise ValueError('Redundant or inconsistent ASCII mode tag')
                ascii_mode=desired;result.append(0xfb)
            elif tag.startswith('<FC:'):
                params=[int(v,16) for v in tag[4:-1].split(':')]
                if len(params)!=(4 if params[1]==0x3c else 2):raise ValueError('FC parameter count differs from native format')
                result.extend((0xfc,*params))
            else:raise ValueError('Unsupported control tag '+repr(tag))
            pos=end+1;continue
        ch=text[pos];pos+=1
        if ascii_mode:
            if ch not in SMALL:raise ValueError('Unsupported small-font character '+repr(ch))
            result.append(32+SMALL.index(ch))
        else:
            if ch not in MEDIUM:raise ValueError('Unsupported medium-font character '+repr(ch))
            result.append(MEDIUM.index(ch))
    result.append(terminator)
    return bytes(result)


def decode(data,*,ascii_mode=False):
    result=[];pos=0
    while pos<len(data):
        value=data[pos];pos+=1
        if value in (0xfe,0xff):
            if pos!=len(data):raise ValueError('Bytes after English terminator')
            return ''.join(result),value
        if value==0xfc:
            if pos+2>len(data):raise ValueError('Truncated English FC control')
            length=4 if data[pos+1]==0x3c else 2
            if pos+length>len(data):raise ValueError('Truncated five-byte English FC control')
            result.append('<FC:'+':'.join('{:02X}'.format(v) for v in data[pos:pos+length])+'>');pos+=length
        elif value==0xfd:result.append('<NL>')
        elif value==0xfb:
            ascii_mode=not ascii_mode;result.append('<ASCII:ON>' if ascii_mode else '<ASCII:OFF>')
        elif ascii_mode:
            if not 32<=value<32+len(SMALL):raise ValueError('Invalid English small glyph')
            result.append(SMALL[value-32])
        else:
            if value>=len(MEDIUM):raise ValueError('Invalid English medium glyph')
            result.append(MEDIUM[value])
    raise ValueError('Missing English terminator')
