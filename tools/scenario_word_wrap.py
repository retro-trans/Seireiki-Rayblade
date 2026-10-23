"""Measure/reflow compiled Latin story streams without editing working rows.

Existing newlines, page boundaries, modes and FC operands retain their order.
Automatic breaks replace a space, or insert a newline in an overlong word.
Special display controls keep the original formatter until their geometry is
decoded. The normal dialogue target is 240 logical pixels, with four pixels
reserved for ink overhang/shadow beyond the integer cursor advance.
"""
import argparse,json,struct
from collections import Counter
from build_genei_font import ROOT,SMALL,MEDIUM,digest
from rayblade_codec import decompress

TARGET_WIDTH=240
PEN_WIDTH=236
SAFE_FC={0x3e} # Existing wait control; no text expansion or glyph advance.
INLINE_FC={0x3c,0x3d,0x3e,0x40,0x42,0x44,0x48,0x53}


def tokens(payload,font):
    pos=0;ascii_mode=False;result=[]
    while pos<len(payload):
        start=pos;value=payload[pos];pos+=1
        row={'offset':start,'width':0,'space':False,'kind':'control'}
        if value==0xfc:
            if pos+2>len(payload):raise ValueError('Truncated FC')
            subtype=payload[pos+1];pos+=4 if subtype==0x3c else 2
            row['fc']=subtype
        elif value==0xfb:ascii_mode=not ascii_mode
        elif value in (0xfd,0xfe,0xff):row['kind']='boundary'
        elif value>=0xf0:raise ValueError('Unexpected wide glyph in Latin compiled stream')
        else:
            chars=SMALL if ascii_mode else MEDIUM
            index=value-32 if ascii_mode else value
            if not 0<=index<len(chars):raise ValueError('Invalid compiled Latin glyph')
            row.update(kind='glyph',width=font[(0x20 if ascii_mode else 0xa0)+index],
                space=chars[index]==' ',character=chars[index])
        if pos>len(payload):raise ValueError('Truncated operand')
        row['raw']=payload[start:pos];result.append(row)
        if value==0xff:
            if pos!=len(payload):raise ValueError('Bytes follow FF')
            return result
    raise ValueError('Missing command terminator')


def semantic_tokens(rows):
    return [r['raw'] for r in rows if r['kind']!='boundary' and not r['space']]


def wrap(payload,font,*,safe_fc=SAFE_FC):
    rows=tokens(payload,font)
    unsupported=sorted({r['fc'] for r in rows if 'fc' in r and r['fc'] not in safe_fc})
    if unsupported:
        return payload,{'wrapped':False,'unsupported_FC':unsupported,'automatic_breaks':0,'forced_word_breaks':0}
    output=[];line=[];width=0;breaks=0;forced=0;max_width=0
    for row in rows:
        if row['kind']=='boundary':
            output.extend(r['raw'] for r in line);output.append(row['raw'])
            max_width=max(max_width,width);line=[];width=0;continue
        line.append(row);width+=row['width']
        if width<=PEN_WIDTH:continue
        spaces=[i for i,r in enumerate(line) if r['space'] and any(p['kind']=='glyph' and not p['space'] for p in line[:i])]
        if spaces:
            split=spaces[-1];left=line[:split];right=line[split+1:]
        else:
            # An unbroken token wider than the window must continue on the
            # next line. No letter or control is discarded or substituted.
            split=len(line)-1;left=line[:split];right=line[split:];forced+=1
        max_width=max(max_width,sum(r['width'] for r in left))
        output.extend(r['raw'] for r in left);output.append(b'\xfd');breaks+=1
        line=right;width=sum(r['width'] for r in line)
        assert width<=PEN_WIDTH
    assert not line
    result=b''.join(output);after=tokens(result,font)
    assert semantic_tokens(after)==semantic_tokens(rows),'Glyph/control sequence changed'
    assert [r['raw'] for r in after if r['raw'] in (b'\xfe',b'\xff')]==[r['raw'] for r in rows if r['raw'] in (b'\xfe',b'\xff')]
    return result,{'wrapped':True,'unsupported_FC':[],'automatic_breaks':breaks,
        'forced_word_breaks':forced,'maximum_pen_width':max_width,
        'input_bytes':len(payload),'output_bytes':len(result)}


def font_bytes(version='0.1.11'):
    raw=(ROOT/'work/output'/version/'WIN00.AFS').read_bytes()
    off,size=struct.unpack_from('<II',raw,8);return raw[off:off+size]


def command_payloads():
    base=ROOT/'work/output/0.1.11'
    comp=json.loads((base/'text/scenario-component-report.json').read_text('utf-8'))
    afs=(base/'D_SCE.AFS').read_bytes();assert digest(afs)==comp['archive_sha256']
    for member in comp['members']:
        off=member['archive_offset'];plain,used=decompress(afs[off+20:off+member['packed_bytes']])
        assert digest(plain)==member['decoded_sha256'] and used==member['packed_bytes']-20
        for record in member['commands']:
            p=record['english_offset'];payload=plain[p:p+record['english_bytes']]
            assert digest(payload)==record['english_sha256']
            yield member,record,payload


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    font=font_bytes();counts=Counter();held=[];long=[];maximum=0;max_bytes=0
    for member,row,payload in command_payloads():
        result,stats=wrap(payload,font);counts['commands']+=1
        counts['wrapped' if stats['wrapped'] else 'special_control_fallback']+=1
        counts['automatic_breaks']+=stats['automatic_breaks'];counts['forced_word_breaks']+=stats['forced_word_breaks']
        maximum=max(maximum,stats.get('maximum_pen_width',0));max_bytes=max(max_bytes,len(result))
        if not stats['wrapped']:held.append({'id':row['id'],'FC':stats['unsupported_FC']})
        if stats['forced_word_breaks']:long.append({'id':row['id'],'breaks':stats['forced_word_breaks']})
    report={'kind':'full compiled English command wrapping audit; no game patch',
        'font_sha256':digest(font),'target_width':TARGET_WIDTH,'pen_width':PEN_WIDTH,
        'counts':dict(counts),'maximum_pen_width':maximum,'maximum_reflowed_input_bytes':max_bytes,
        'special_control_commands':held,'overlong_word_commands':long,
        'checks':['All compiled input fingerprints match current components','All non-space glyphs, modes and FC operands preserved in order',
            'Original FE page boundaries and final FF preserved','Working English rows unchanged'],
        'limits':['Presentation width derived from 30 legacy 8-pixel cells and observed dialogue margin; live fit still required',
            'Special display controls retain legacy behavior','Native formatter pagination and VM advancement still require regression checks']}
    print(json.dumps({k:v for k,v in report.items() if k not in ('special_control_commands','overlong_word_commands')},indent=2))
    print('Special-control command IDs:',json.dumps(held));print('Overlong-word command IDs:',json.dumps(long))
    if args.write_report:
        out=ROOT/'work/output/0.1.11/word-wrap-audit.json';out.write_text(json.dumps(report,indent=2)+'\n','utf-8');print('Wrote',out)
    else:print('DRY RUN: no report or game files written')


if __name__=='__main__':main()
