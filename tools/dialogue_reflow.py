"""Join obsolete single line breaks, retain pages/paragraphs, wrap whole words."""
from collections import Counter
from scenario_word_wrap import tokens, wrap, INLINE_FC, semantic_tokens
from english_text_codec import encode


def prose_key(rows):
    """Word boundaries and exact controls, independently of soft line breaks."""
    result=[];space=False
    for row in rows:
        if row['space'] or row['raw']==b'\xfd':
            space=True;continue
        if space and result and row['raw'] not in (b'\xfe',b'\xff'):
            result.append(b' ')
        result.append(row['raw']);space=False
    return result


def reflow(payload,font,*,safe_fc=INLINE_FC):
    rows=tokens(payload,font)
    mode=False;soft=[];joined=0;paragraphs=0
    for i,row in enumerate(rows):
        if row['raw']==b'\xfb': mode=not mode
        if row['raw']==b'\xfd':
            # Consecutive breaks explicitly form a blank paragraph line.
            if (i and rows[i-1]['raw']==b'\xfd') or (i+1<len(rows) and rows[i+1]['raw']==b'\xfd'):
                soft.append(row['raw']);paragraphs+=1
            else:
                soft.append(encode(' ',ascii_mode=mode)[:-1]);joined+=1
        else: soft.append(row['raw'])
    # Collapse presentation spaces, and trim them at retained boundaries.
    # Control bytes never move relative to any non-space glyph.
    normalized=[];pending=None
    for row in tokens(b''.join(soft),font):
        if row['space']:
            pending=row['raw'];continue
        if row['kind']=='boundary': pending=None
        elif pending is not None and normalized and normalized[-1] not in (b'\xfd',b'\xfe'):
            normalized.append(pending);pending=None
        else: pending=None
        normalized.append(row['raw'])
    clean=b''.join(normalized)
    result,stats=wrap(clean,font,safe_fc=safe_fc)
    assert stats['wrapped'] and not stats['forced_word_breaks'],stats
    after=tokens(result,font)
    assert semantic_tokens(rows)==semantic_tokens(after)
    assert prose_key(rows)==prose_key(after),'Word boundaries or controls changed'
    assert [r['raw'] for r in rows if r['raw'] in (b'\xfe',b'\xff')]==[r['raw'] for r in after if r['raw'] in (b'\xfe',b'\xff')]
    return result,{**stats,'joined_single_breaks':joined,'retained_paragraph_breaks':paragraphs,
                   'changed':result!=payload}


def readable(payload,font):
    return ''.join(t.get('character','\n' if t['raw']==b'\xfd' else '\n[PAGE]\n' if t['raw']==b'\xfe' else '') for t in tokens(payload,font))


def paginate(payload,font):
    """Battle messages bypass the story formatter: apply its three-line rule."""
    parts=[];lines=0;extra=0
    for row in tokens(payload,font):
        raw=row['raw']
        if raw==b'\xfd':
            lines+=1
            if lines==3: raw=b'\xfe';lines=0;extra+=1
        elif raw==b'\xfe':lines=0
        parts.append(raw)
    return b''.join(parts),extra
