"""Codec boundary tests using independently specified streams and round trips."""
import random
from english_text_codec import encode,decode
from rayblade_codec import compress,decompress


def main():
    golden=[(b'',bytes.fromhex('40000000')),
            (b'abcdefgh',bytes.fromhex('ff616263646566676840000000')),
            (b'A'*257,bytes.fromhex('a841fff8ff000000'))]
    for plain,packed in golden:
        assert decompress(packed)==(plain,len(packed))
        assert compress(plain)==packed
    rng=random.Random(7419);cases=[bytes(rng.randrange(256) for _ in range(n)) for n in range(80)]
    cases += [bytes(rng.randrange(256) for _ in range(8192))]*2
    cases += [cases[-1]+cases[-1][:256],b'ABC'*1000,b'AB'*4097,b'\0'*20000,
              bytes(range(256))*40,b'This is English text with a repeated phrase. '*500]
    for plain in cases:
        packed=compress(plain);assert decompress(packed)==(plain,len(packed))
    samples=['AZaz 0123456789!?(),.-:/',
             '<FC:FF:FF><NL><ASCII:ON>Lv42 HP 10/100<ASCII:OFF> Prana +5',
             'Name<FC:80:82>Value<FC:FF:FF>',
             '<ASCII:ON>Ends in ASCII mode','2 < 3; 5 > 4; <3',
             ''.join(chr(n) for n in range(32,127)),
             '<FC:3C:3E><FC:84:3C:1D:F0><FC:01:3E><FC:84:3C:1C:F0>Hello.',
             '≪Ze=Ode≫♥♪AーB',
             '<ASCII:ON>≪Ze=Ode≫♥♪AーB<ASCII:OFF>']
    for text in samples:
        for end in (0xfe,0xff):assert decode(encode(text,end))==(text,end)
    # Independent byte fixtures lock old Latin IDs and the five new slots.
    assert encode('≪≫♥♪ー')==bytes.fromhex('6061626364ff')
    assert encode('<ASCII:ON>≪≫♥♪ー<ASCII:OFF>')==bytes.fromhex('fb7f80818283fbff')
    assert encode('AZaz 09!?')==bytes.fromhex('011a1b3400363f4054ff')
    assert encode('AーB',ascii_mode=True)==bytes.fromhex('418342ff')
    assert decode(bytes.fromhex('418342ff'),ascii_mode=True)==('AーB',0xff)
    for bad in ['\u2603','<G01FC>','<ASCII:OFF>','<FC:FF>','<FC:84:3C>','<FC:00:00:12:34>']:
        try:encode(bad)
        except ValueError:pass
        else:raise AssertionError('Unsupported text silently accepted: '+repr(bad))
    print('PASS: 3 exact PRS golden streams, {} PRS boundary/overlap/window cases, {} English mode/control/repertoire round trips, 3 byte fixtures and 6 rejection cases.'.format(len(cases),len(samples)*2))


if __name__=='__main__':main()
