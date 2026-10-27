"""Package original Skies pixels at native output density as local 0.7.5."""
import argparse,json
from build_native_movie_font import ROOT,OUT,VERSION,PRIOR,compose
from build_native_font_mode_disc import plan,trial,finalize
from build_movie_test_disc import write_plan


def finish_metadata(out):
    manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
    manifest['native_proof_reuse']['scope']='Historical reports retain actual hashes. The 640x480 video request, drawing adapters and movie geometry have separate current evidence; the other twelve payloads and boot area remain exact 0.7.3.'
    manifest['surface_scaling']='Native: two texture samples per logical UI coordinate and two framebuffer pixels per logical UI coordinate, preserving original 12x24 Skies main glyphs. Compact status uses 8x16. HD: up to 4x surfaces, texture dimensions capped at 1024.'
    (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
    readme=(out/'READ-ME.txt').read_text('utf-8')
    readme=readme.replace('Use Native on Dreamcast or Flycast at 1x output.', 'Select the VGA cable in Flycast; 1x output is 640x480. Physical Dreamcast and non-VGA testing remain pending.')
    readme=readme.replace('Software decoding/audio/preservation checks pass; native movie playback, timing and full-game behavior are unverified.', 'Native geometry checks cover all 129 movie entries. Flycast opening playback/fit was visually checked; complete movie timing, physical hardware and full-game behavior remain unverified.')
    (out/'READ-ME.txt').write_text(readme,'utf-8')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');ap.add_argument('--trial',action='store_true')
    args=ap.parse_args();assert not(args.write and args.trial)
    p,component=plan(compose_fn=compose,prior=PRIOR,version=VERSION)
    p[7]['kind']='Local 640x480 native Skies font with corrected movie presentation'
    p[7]['readme_component_text']+='Native preserves every original 12x24 Skies medium-glyph sample at 640x480 output.\n'
    p[7]['readme_component_text']+='Movie positions and sizes now follow the 640x480 framebuffer; original SFD video/audio bytes remain unchanged.\n'
    p[7]['readme_component_text']+='Compact status text uses 8x16 samples, instead of enlarging a reduced 4x8 bitmap.\n'
    print('Plan:',VERSION,len(p[4]),'sector substitutions; preserve all wording, layouts and 12 other payloads.')
    if args.trial:trial(p,component,out=OUT,prior=PRIOR,version=VERSION)
    elif args.write:
        for name in ('font-mode-native-test.json','title-font-native-test.json'):
            proof=json.loads((OUT/name).read_text('utf-8'))
            assert proof['executable_sha256']==component['executable_sha256']
        geometry=json.loads((OUT/'native-geometry-test.json').read_text('utf-8'))
        assert geometry['executable_sha256']==component['executable_sha256']
        write_plan(p,VERSION,PRIOR,{n:p[3][n] for n in ('1ST_READ.BIN','WIN00.AFS')})
        finalize(p,component,version=VERSION,prior=PRIOR,proof_dir=OUT)
        finish_metadata(ROOT/'work/output'/VERSION)
        import shutil
        shutil.copyfile(OUT/'native-geometry-test.json',ROOT/'work/output'/VERSION/'native-geometry-test.json')
    else:print('DRY RUN: no disc written')


if __name__=='__main__':main()
