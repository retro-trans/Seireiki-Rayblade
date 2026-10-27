"""Package original Skies pixels at native output density as local 0.7.4."""
import argparse,json
from build_skies_native_font import ROOT,OUT,VERSION,PRIOR,compose
from build_native_font_mode_disc import plan,trial,finalize
from build_movie_test_disc import write_plan


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');ap.add_argument('--trial',action='store_true')
    args=ap.parse_args();assert not(args.write and args.trial)
    p,component=plan(compose_fn=compose,prior=PRIOR,version=VERSION)
    p[7]['readme_component_text']+='Native preserves every original 12x24 Skies medium-glyph sample at 640x480 output.\n'
    p[7]['readme_component_text']+='Compact status text uses 8x16 samples, instead of enlarging a reduced 4x8 bitmap.\n'
    print('Plan:',VERSION,len(p[4]),'sector substitutions; preserve all wording, layouts and 12 other payloads.')
    if args.trial:trial(p,component,out=OUT,prior=PRIOR,version=VERSION)
    elif args.write:
        for name in ('font-mode-native-test.json','title-font-native-test.json'):
            proof=json.loads((OUT/name).read_text('utf-8'))
            assert proof['executable_sha256']==component['executable_sha256']
        write_plan(p,VERSION,PRIOR,{n:p[3][n] for n in ('1ST_READ.BIN','WIN00.AFS')})
        finalize(p,component,version=VERSION,prior=PRIOR,proof_dir=OUT)
    else:print('DRY RUN: no disc written')


if __name__=='__main__':main()
