"""Record high-detail Skies map labels, witness and changelog. Dry first."""
import argparse,json,shutil
from build_map_font_patch import ROOT,OUT,VERSION,PRIOR,compose,digest


def read(p):return json.loads(p.read_text('utf-8'))


def prepare():
    out=ROOT/'work/output'/VERSION;disc=read(out/'english-disc-report.json');proof=read(out/'map-font-native-test.json');component=compose()[6]
    assert disc['validation']['reextracted_files']=='all 14 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass' and disc['validation']['unrelated_track_bytes']=='all unchanged'
    assert disc['validation']['track_bytes_compared']==1188856032
    assert disc['map_font_proof_sha256']==digest((out/'map-font-native-test.json').read_bytes())
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    for name,row in disc['files'].items():
        raw=(out/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes()
        assert len(raw)==row['size'] and digest(raw)==row['sha256']
        if name!='WMAP.AFS':assert row==previous['files'][name]
    summary={'version':VERSION,'source_build':PRIOR,'date':'2026-10-24',
        'status':'Ten original Skies map labels integrated, native/pixel/disc checks pass; live appearance/VRAM pending',
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        'preview':f'work/ui/{VERSION}/map-labels-preview.png','label_count':10,'font':component['font'],
        'method':component['method'],'font_sha256':component['font_sha256'],'texture_dimensions':[1024,256],
        'added_VRAM_bytes':524288,'archive_sha256':component['archive_sha256'],'labels':component['draws'],
        'native_proof':f'work/output/{VERSION}/map-font-native-test.json',
        'native_proof_sha256':disc['map_font_proof_sha256'],'native_instructions':proof['native_instructions'],
        'native_registration':proof['registration'],'native_sprite_bounds_and_UVs':28,
        'protected_marker_sprites':18,'unchanged_map_artwork_members':17,
        'original_authoring_file_list':'Retained unchanged at new member20; second label PVR occupies member19',
        'native_archive_layout':'21 members in actual SDK compact-sector order, 38653 spare bytes; same ISO extent',
        'limits':proof['limits'],'validation':disc['validation'],'sector_substitutions':disc['new_changed_sectors'],
        'unchanged_other_payloads':13,'translation_wording_changes':0,'new_translation_credit':0,'release':False}
    status=read(ROOT/'docs/translation-status.json');status.update(version=VERSION,
        stage='High-detail original Skies map names with bright alpha text/dark edge integrated; live map/VRAM and full translation review pending')
    status['latest_map_font_build']=summary
    old=read(ROOT/'docs/worldmap-labels.json');old['latest_font_build']=summary
    old['status']='Historical 0.1.25 insertion proof retained below; superseded by 0.1.44 original Skies map font/readability build'
    ui={'version':VERSION,'screenshot':'map-labels-before.png','request':'Another hard-to-read text on map',
        'visible_label_ids':['wmap.17.017','wmap.17.021','wmap.17.022','wmap.17.023'],
        'cause':'Historical labels used the supplied bitmap downsampled to 12px and dim opaque blue-gray edge pixels in ARGB1555.',
        'fix':'All ten names use exact original Skies foreground masks at four-times atlas detail, real four-level alpha, bright cream fill and a thin dark edge.',
        'asset_geometry':component['draws'],'font_texture_dimensions':[1024,256],'display_height':16,
        'protected':'All 18 marker sprite records/pixels and 17 terrain/art members unchanged. Horizontal call-point centers and vertical anchors retained.',
        'preview':'Offline asset gallery, not an in-game screenshot','live_validation':'pending'}
    recipe={'version':VERSION,'source_build':PRIOR,'source_translation':'work/translation/en/ui/worldmap-labels.en.json',
        'font':'Original Skies USA Dreamcast Latin, same medium mask/advances as dialogue',
        'font_sha256':component['font_sha256'],'texture_dimensions':[1024,256],
        'rows':component['draws'],'reason':'Readability presentation only; all English names/glossary spellings retained'}
    note=f'''## {VERSION} — sharper, higher-contrast world-map names

- Rebuilt all ten map place names with the original Skies Latin glyph pixels and variable advances. Replaced the historical downsampled supplied bitmap and dim blue-gray lettering with bright cream text, original four-level transparency and a thin dark edge. Glyph shapes and wording remain intact; no individual stretching, contour reconstruction or emulator replacement textures.
- Integrated a separate 1024×256 ARGB4444 rectangular twiddled font texture. Each label has four texture pixels per original display pixel on both axes, preserving the 16-pixel display height, vertical anchors and horizontal call-point centers. Wider English cells remain centered. Added texture storage is 524,288 bytes. Removed only the old text cells from the original 512×512 marker atlas; all eighteen marker sprites and all seventeen terrain/art member payloads remain exact.
- Expanded the map NJTL to two textures and its archive to twenty-one members. The new label PVR follows the marker PVR; the original authoring filename list is retained unchanged as the final member. Repacked in SDK compact-sector order within the existing ISO allocation, with 38,653 spare bytes. Executable code, normal dialogue font, every translation payload and the other thirteen build files are byte-exact 0.1.43.
- Passed independent original Skies VQ glyph/alpha comparisons for every label, protected-pixel/geometry preservation, all twenty-one native archive lookups, native two-texture NJTL relocation/registration and twenty-eight native sprite bounds/normalized-UV calculations. Both original-game PRS decodes and the native 1024×256 ARGB4444 texture-info case pass with guards/ABI checks. I/O/allocation fixtures are bounded; actual map routing, upload/VRAM, GPU blending/filtering, dialogue fade and screen overlap remain for live checking.
- Packaged {disc['new_changed_sectors']} sector substitutions; all fourteen files re-extract exactly. Changed-sector EDC/ECC and full 1,188,856,032-byte track comparison pass. Thirty-three prior proof identities retained. Fresh-boot 0.1.44, load a normal save and inspect map labels with and without dialogue. No public release or prior-build replacement.

'''
    return summary,[(ROOT/'docs/map-font-readability.json',summary),(ROOT/'docs/worldmap-labels.json',old),
        (ROOT/'docs/translation-status.json',status),(ROOT/f'work/ui/{VERSION}/map-font-layout.json',ui),
        (ROOT/'work/translation/en/ui/worldmap-font-current.en.json',recipe)],note


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    summary,updates,note=prepare();print('Verified',VERSION,';',summary['sector_substitutions'],'sector edits; ten original Skies map labels.')
    print('Records:',[str(p.relative_to(ROOT)) for p,_ in updates]);print(note)
    if not a.write:print('DRY RUN: no records/screenshots written.');return
    for p,v in updates:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n','utf-8')
    folder=ROOT/f'work/ui/{VERSION}'
    shutil.copyfile('C:/Users/Binh/AppData/Local/Temp/codex-clipboard-725f1a68-39b6-40a5-b843-5d1cb1e28413.png',folder/'map-labels-before.png')
    shutil.copyfile(OUT/'map-labels-preview.png',folder/'map-labels-preview.png')
    changes=ROOT/'CHANGELOG.md';old=changes.read_text('utf-8');assert note.splitlines()[0] not in old
    changes.write_text(old.replace('# Change log\n\n','# Change log\n\n'+note,1),'utf-8')
    print('Recorded UI witness, font gallery, source/layout recipe, build status and changelog.')


if __name__=='__main__':main()
