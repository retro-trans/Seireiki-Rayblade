"""Preserve selectable rows; use compact Skies text only for long option lists."""
from english_text_codec import encode, decode
from scenario_word_wrap import tokens, PEN_WIDTH


def widths(payload, font):
    rows = [0]
    for t in tokens(payload, font):
        if t['kind'] == 'boundary':
            if t['raw'] != b'\xff': rows.append(0)
        else: rows[-1] += t['width']
    return rows


def layout(payload, font):
    """Never insert/delete option boundaries or change their order/wording.

    Close compact mode before each boundary: native FD advances eight pixels
    while compact mode is on, versus the sixteen required by the selector.
    """
    before = widths(payload, font)
    if max(before) <= PEN_WIDTH:
        return payload, {'compact': False, 'widths': before}
    text, end = decode(payload)
    assert end == 0xff and '<ASCII:' not in text and '<FC:' not in text
    import re
    pieces = re.split('(<NL>)', text)
    result = encode(''.join(p if p == '<NL>' else '<ASCII:ON>'+p+'<ASCII:OFF>'
                            for p in pieces if p))
    assert max(widths(result, font)) <= PEN_WIDTH
    assert [t['raw'] for t in tokens(payload, font) if t['kind'] == 'boundary'] == [
        t['raw'] for t in tokens(result, font) if t['kind'] == 'boundary']
    return result, {'compact': True, 'widths': widths(result, font), 'original_widths': before}
