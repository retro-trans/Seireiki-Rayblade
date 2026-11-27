"""Package the verified screenshot fixes as a local 0.7.51 disc."""
import argparse
import struct
from build_screenshot_ui_fix import write_components, ROOT, OUT, VERSION, PRIOR, json_read, save, digest
from test_screenshot_ui_fix import check
from build_native_font_mode_disc import plan
from build_movie_test_disc import write_plan


def build():
    files, decoded, recipe, names_report, report, *_ = write_components()
    proof=check();save(OUT/'screenshot-ui-native-test.json',proof)
    base=ROOT/'work/output'/PRIOR
    mode=json_read(base/'font-mode-details.json')
    mode.update(version=VERSION,source_build=PRIOR,executable_sha256=digest(files['1ST_READ.BIN']),
                archive_sha256=digest(files['WIN00.AFS']))
    p,_=plan(compose_fn=lambda:(files['1ST_READ.BIN'],files['WIN00.AFS'],b'',{},mode),
             prior=PRIOR,version=VERSION,component_files=files)
    p[7].update(kind='Album, battle label and weapon/sort layout fixes',
        component_manifest_name='screenshot-ui-component.json',
        current_native_evidence={'screenshot_ui':'screenshot-ui-native-test.json'},current_live_evidence={},
        readme_component_text='Fixes blank album captions, translates Memory Album heading, replaces rough baked battle tabs with Skies lettering, shortens sort labels and aligns P/W weapon markers.\n'
            'The earlier New Game/dialogue runtime repairs, name-offset routine, Native font and other 0.7.50 fixes remain unchanged.\n',
        proof_scope='Native texture acceptance, caption registration/UVs, marker caller execution, sort parsing and full disc preservation.',
        pending=['Live/hardware checks for the four repaired screens','Hardware ranged-attack black scene remains unresolved; Flycast reportedly unaffected'])
    write_plan(p,VERSION,PRIOR,files)
    out=ROOT/'work/output'/VERSION
    (out/'text/D_NAMES.en.dec.bin').write_bytes(decoded)
    for name,value in [('ui-layouts.en.json',recipe),('names-component-report.json',names_report),
                       ('screenshot-ui-details.json',report),('screenshot-ui-native-test.json',proof),
                       ('font-mode-details.json',mode),('font-mode-component.json',mode)]:save(out/name,value)
    manifest=json_read(out/'font4x-patch.json')
    manifest.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'],
        status='Four screenshot fixes; local test, live confirmation pending',screenshot_ui=report,
        native_proof_reuse={'source_build':PRIOR,'scope':'Hardware renderer and Native font exact; current UI tests are separate.'})
    for name,raw in files.items():
        if name in manifest['files']:manifest['files'][name]['target_sha256']=digest(raw)
    offset,size=struct.unpack_from('<II',files['WIN00.AFS'],8+52*8)
    manifest['library'].update(archive_member_offset=offset,archive_member_bytes=size)
    save(out/'font4x-patch.json',manifest)
    library=json_read(out/'library-patch-report.json');library.update(archive_member_offset=offset,archive_member_bytes=size)
    save(out/'library-patch-report.json',library)
    (out/'READ-ME.txt').write_text('Rayblade English 0.7.51 - LOCAL UI TEST\n\n'
        'Cold boot disc/Rayblade English Test 0.7.51.gdi. Keep all five track files beside it.\n'
        'Check the Memory Album heading and captions, small Trust Gauge/name tabs, sorting labels and P/W weapon markers.\n'
        'Also check New Game and mission dialogue for regression. Use a normal VMU save, not an old save state.\n'
        'Native/code/layout and complete disc integrity checks pass. Live visual/hardware confirmation pending.\n'
        'The hardware ranged-attack black scene remains unresolved; no fix is claimed for it.\n'
        'No GitHub release has been published.\n','utf-8')
    return p[7]


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    if args.write:build()
    else:print('Use --write to validate and create the local 0.7.51 disc.')
