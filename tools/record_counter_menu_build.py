"""Record verified counter-menu changes, UI witnesses and changelog. Dry first."""
import argparse,json,shutil
from build_counter_menu_patch import ROOT,OUT,VERSION,PRIOR,compose,digest


def read(p):return json.loads(p.read_text('utf-8'))


def prepare():
    out=ROOT/'work/output'/VERSION;disc=read(out/'english-disc-report.json');proof=read(out/'counter-menu-native-test.json')
    files,decoded,recipe,names,component=compose()
    assert disc['validation']['reextracted_files']=='all 14 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass' and disc['validation']['unrelated_track_bytes']=='all unchanged'
    assert disc['validation']['track_bytes_compared']==1188856032
    assert disc['counter_menu_proof_sha256']==digest((out/'counter-menu-native-test.json').read_bytes())
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    for name,row in disc['files'].items():
        raw=(out/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes()
        assert len(raw)==row['size'] and digest(raw)==row['sha256']
        if name not in files:assert row==previous['files'][name]
    summary={'version':VERSION,'source_build':PRIOR,'date':'2026-10-24',
        'status':'Counter menus/help/objectives native-verified and packaged; live GPU/input/simultaneous allocation checks pending',
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        'geometry':component['geometry'],'help_rows':component['help_rows'],'font_issue':component['font_issue'],
        'font_sha256':proof['font_sha256'],'font_changed':False,'files':disc['files'],
        'native_proof':f'work/output/{VERSION}/counter-menu-native-test.json',
        'native_proof_sha256':disc['counter_menu_proof_sha256'],'native_geometry_cases':proof['geometry_cases'],
        'native_composed_forecast':proof['native_composed_forecast'],'native_raster_cases':30,
        'unchanged_other_name_rows':proof['unchanged_other_name_rows'],'native_instructions':proof['native_instructions'],
        'limits':proof['limits'],'validation':disc['validation'],'sector_substitutions':disc['new_changed_sectors'],
        'translation_wording_changes':0,'new_translation_credit':0,'release':False}
    status=read(ROOT/'docs/translation-status.json');status.update(version=VERSION,
        stage='Counter/help/objective boxes extended; eight help rows reflowed; full reaction-choice raster verified; live testing and translation review pending')
    status['latest_counter_menu_build']=summary
    ui={'version':VERSION,'logical_game_size':[320,240],'reports':[
        {'screenshot':'01-orders-before.png','request':'Extend box and rewrap',
         'ids':['names.g00.174','names.g01.024..031'],'frames':[component['geometry']['policy_frame'],component['geometry']['help_frame']],
         'text':component['help_rows'],'result':'Five policy labels fully visible; balanced whole-word help in at most four lines. Policy frame ends at help top; no overlap.'},
        {'screenshot':'02-objectives-before.png','request':'Extend box','id':'names.g00.171',
         'frame':component['geometry']['objectives_frame'],'text_x':112,'result':'Complete Mission Objectives title fits 96px text interior'},
        {'screenshot':'03-reaction-before.png','request':'Counterattack and Select Weapon font',
         'id':'names.g00.124','frame':component['geometry']['forecast_frame'],
         'result':'Widened the old 64px tile clipping to 112px. Actual constructed forecast/real name lookup/parser/native raster produces exact Skies masks for all four choices at the same 4x scale in isolation. No glyph substitution or new outline.'}],
        'previews':'Offline native-parser specimens; not live screenshots','live_validation':'pending'}
    note=f'''## {VERSION} — counter menus, help wrapping and objective header

- Extended counter-order and reaction frames to 128 logical pixels and all five shared popup text tiles from 64 to 112 pixels. Centered the frames at x96, text at x104. Complete Always Counterattack and Select Weapon labels fit. Moved the policy frame up to y56 so its bottom meets the taller help box without covering its last choice.
- Extended policy help from 248×64 to 272×80 at x24/y152. Reflowed all eight help rows with measured whole words and balanced line lengths, at most four lines and a 252-pixel pen budget. Every word and punctuation mark is retained. The four-line paragraph uses an existing six-line native template with a 256-pixel backing width; no 512-pixel-wide logical surface or texture above 1024 is introduced.
- Extended and centered the Mission Objectives title frame to 112×32 at x104/y24, with text at x112. Victory/defeat content remains unchanged.
- Addressed the reported Counterattack / Select Weapon presentation by removing text-tile clipping. Verified the actual context constructor, common parameter queue, nested names, parser and native raster end to end: all four reaction choices use the same original Skies medium glyphs and 4×4 scale in the isolated native case. Composed pixels exactly match an independent alpha/shadow reference. Font bytes, glyph shapes, advances and all executable instructions are unchanged. Live GPU appearance and simultaneous allocation are not claimed as verified.
- Passed four native frame/context cases, eleven UI bounds cases, eight help entries through the constructed native parser, thirty exact native glyph raster cases and names PRS decoding. All {proof['unchanged_other_name_rows']} other names-table rows remain byte-exact. Changed only embedded layout/template operands and help line breaks; all twelve other build payloads retain 0.1.42 identities, including story/battle reflow, font, library, album and movies.
- Packaged {disc['new_changed_sectors']} sector substitutions. All fourteen payloads re-extract exactly; changed-sector EDC/ECC and the full 1,188,856,032-byte track comparison pass. Thirty-two historical proofs keep their actual tested identities. Fresh-boot the 0.1.43 GDI and load a normal in-game save for live menu/cursor/highlight/font checking. No public release or previous-build replacement.

'''
    return summary,[(ROOT/'docs/counter-menu-layout.json',summary),(ROOT/'docs/translation-status.json',status),
        (ROOT/f'work/ui/{VERSION}/counter-menu-layout.json',ui),
        (ROOT/'work/translation/en/ui/counter-menu-layouts-current.en.json',recipe)],note


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    summary,updates,note=prepare();print('Verified',VERSION,';',summary['sector_substitutions'],'sector edits; all three screenshot requests recorded.')
    print('Records:',[str(p.relative_to(ROOT)) for p,_ in updates]);print(note)
    if not a.write:print('DRY RUN: no records/screenshots written.');return
    for p,v in updates:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n','utf-8')
    folder=ROOT/f'work/ui/{VERSION}'
    for clip,name in [('e2bcc9f7-a33e-432f-b405-0636eb148253','01-orders-before.png'),
        ('a6a873ba-be70-4a94-b320-f11ae813e7f2','02-objectives-before.png'),
        ('fe2406c5-e0de-4d78-932b-f17acb5189b5','03-reaction-before.png')]:
        shutil.copyfile(f'C:/Users/Binh/AppData/Local/Temp/codex-clipboard-{clip}.png',folder/name)
    for p in OUT.glob('*-preview.png'):shutil.copyfile(p,folder/p.name)
    changes=ROOT/'CHANGELOG.md';old=changes.read_text('utf-8');assert note.splitlines()[0] not in old
    changes.write_text(old.replace('# Change log\n\n','# Change log\n\n'+note,1),'utf-8')
    print('Recorded three UI witnesses, parser previews, layout recipe, build status and changelog.')


if __name__=='__main__':main()
