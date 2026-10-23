"""Record battle UI fixes, source/context review, screenshot map and changelog. Dry first."""
import argparse,json,shutil
from build_battle_menu_patch import ROOT,OUT,VERSION,PRIOR,compose,digest


def read(path):return json.loads(path.read_text('utf-8'))


def prepare():
    out=ROOT/'work/output'/VERSION;disc=read(out/'english-disc-report.json')
    files,decoded,recipe,names,component=compose();proof=read(out/'battle-menu-native-test.json')
    assert disc['validation']['reextracted_files']=='all 14 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass' and disc['validation']['unrelated_track_bytes']=='all unchanged'
    assert disc['validation']['track_bytes_compared']==1188856032
    assert disc['battle_menu_proof_sha256']==digest((out/'battle-menu-native-test.json').read_bytes())
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    for name,row in disc['files'].items():
        raw=(out/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes()
        assert len(raw)==row['size'] and digest(raw)==row['sha256']
        if name not in files:assert row==previous['files'][name]
    summary={'version':VERSION,'source_build':PRIOR,'date':'2026-10-24',
        'status':'Local battle UI correction build verified offline; fresh-boot cursor/highlight/navigation appearance pending',
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        'translation_check':component['translation_check'],'frame':component['frame'],'aliases':component['aliases'],
        'font_check':component['font_check'],'font_sha256':proof['font_sha256'],'font_changed':False,
        'files':disc['files'],'native_proof':f'work/output/{VERSION}/battle-menu-native-test.json',
        'native_proof_sha256':disc['battle_menu_proof_sha256'],
        'native_cases':{'action_labels':9,'frame_and_context_counts':8,'UI':19,'real_status_lookups':2,'glyph_rasters':8,'names_PRS':1},
        'native_limits':proof['limits'],'validation':disc['validation'],'sector_substitutions':disc['new_changed_sectors'],
        'translation_wording_changes':0,'new_translation_credit':0,'release':False}
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,stage='Battle action menu/compact headers corrected; source/context translation check retained wording; live testing and translation review pending')
    status['latest_battle_menu_build']=summary
    ui={'version':VERSION,'logical_game_size':[320,240],'screenshot_coordinate_note':'Menu geometry and FC fields verified natively; screenshot rectangles are approximate visual labels',
        'reports':[
            {'screenshot':'01-translation-before.png','request':'Check translation','id':'scenario.s_002.o026c6',
             'result':component['translation_check'],'rectangle':[64,176,240,48]},
            {'screenshot':'02-action-menu-before.png','request':'Extend box','id':'VM 0xf01b/0xf022; template 25',
             'result':component['frame'],'native_cases':proof['menu_geometry_cases']},
            {'screenshot':'03-status-before.png','request':'Shorten labels','ids':['names.g00.004','names.g00.005','names.g00.006'],
             'result':'Trust / Move Type / Move / Skills; terrain value anchor moves from x64 to x56 for Water/Space; values and other controls retained'},
            {'screenshot':'04-weapons-before.png','request':'Shorten labels','ids':['names.g00.096','names.g00.097'],
             'result':'Hit / Req. SP / PR Cost; full terminology retained in glossary/drafts'},
            {'screenshot':'05-cut-in-before.png','request':'Cut-In ON appears to use a different font',
             'ids':['names.g00.166','names.g00.251','names.g00.252'],
             'result':component['font_check'],'native_parameter_and_font_evidence':proof['native_status_cases']}],
        'previews':'Copied native-parser specimens are offline diagnostic compositions, not in-game screenshots'}
    review={'version':VERSION,'kind':'Focused source/context review; no translation changes',
        'source_file':'work/translation/en/scenario/s_002.json','target_command':'scenario.s_002.o026c6',
        'target_rows':['scenario.s_002.o026c6.l00','scenario.s_002.o026c6.l01','scenario.s_002.o026c6.l02'],
        'context_range_rows':[304,328],'context_rows_read':25,'rows_reviewed_for_reported_utterance':3,
        'context':'Ai has just complained about Touya treating Ymir differently. Touya responds that he is responding in kind. Ymir tells Ai to stop, then turns to Touya to defend Ai and ask forgiveness.',
        'decisions':['The first sentence directly addresses Ai. The following she refers to Ai, not Touya or Ymir.',
            'Retain That\'s enough from you too, Ai and She doesn\'t mean any harm; both preserve the source meaning.',
            'Retain Mr. Kazami / Miss Clasio under the documented scene-specific honorific localization; they are intentional choices, not mistaken character identities.'],
        'conventions':'docs/translation-conventions.json: forms_of_address[0]',
        'source_rows_sha256':component['translation_check']['source_rows_sha256'],
        'changes':0,'limits':['Focused three-row review, not independent review credit for the full scene or game']}
    note=f'''## {VERSION} — battle action-menu width and compact UI labels

- Widened the unit action frame from 40 to 72 logical pixels, shifted its left edge from x264 to x232 and its text origin from x272 to x240, and expanded both menu text tiles from 32 to 56 pixels. The frame retains its x304 right edge and a 16-pixel screen margin. Every legal action label, including Transform, fits with ink/shadow allowance. Power-of-two backing remains 64×128 logical pixels; native surfaces stay within 1024 per dimension and the existing allocation fallback/budget.
- Shortened the reported status and weapon fields to Trust, Skills, Move Type, Move, Hit, Req. SP and PR Cost. Kept all numeric values, placeholders and non-layout FC operands; moved only the terrain value anchor eight pixels left (x64 to x56), so Land, Air, Water and Space all fit the 88-pixel status interior. Full terms remain in glossary/working translations. The shared status strings now display On/Off. Native common-queue and nested-name execution confirms Cut-In and its dynamic value already use the same medium Skies font bank; this is a case/style normalization, not a font replacement. Font pixels, all story/battle dialogue and all executable instructions remain unchanged.
- Checked the reported Ymir utterance against its three Japanese rows and 25 surrounding rows. Ymir first addresses Ai, then asks Touya to forgive Ai; she correctly refers to Ai. Retained the translation. The documented Mr. Kazami / Miss Clasio forms deliberately localize this scene's polite address; no name correction or new translation credit was applied. The initial suspicion that these surname forms were mistakes was resolved by the existing translation conventions.
- Passed eight native action-context/frame constructions (one through eight actions), ink bounds for all nine action labels, 19 affected UI cases, both real status parameter-queue/nested lookups, eight native letter raster/ABI cases, and the actual names PRS decoder. Fixtures and pre-GPU frame limits are documented; live cursor/highlight appearance, interaction and navigation remain pending.
- Packaged {disc['new_changed_sectors']} sector substitutions over 0.1.41. All fourteen payloads re-extract exactly; changed-sector EDC/ECC and the full 1,188,856,032-byte track comparison pass. Twelve other payloads remain exact, including the font, reflowed story/battle dialogue, library, album and movies. Thirty-one historical proofs retain their actual tested identities. Fresh-boot the 0.1.42 GDI and load a normal in-game save. No public release, original-disc change or prior-build replacement.

'''
    return summary,[(ROOT/'docs/battle-menu-layout.json',summary),(ROOT/'docs/translation-status.json',status),
        (ROOT/f'work/ui/{VERSION}/battle-menu-layout.json',ui),
        (ROOT/'work/translation/en/scenario/review-s002-026c6.en.json',review),
        (ROOT/'work/translation/en/ui/battle-menu-layouts-current.en.json',recipe)],note


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    summary,updates,note=prepare()
    print('Verified',VERSION,';',summary['sector_substitutions'],'sector edits; reported translation retained; menu/labels/status corrected.')
    print('Records:',[str(p.relative_to(ROOT)) for p,_ in updates]);print(note.splitlines()[:3])
    if not args.write:print('DRY RUN: no records/screenshots written.');return
    for path,value in updates:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n','utf-8')
    folder=ROOT/f'work/ui/{VERSION}'
    for clip,name in [('9df0e5cc-e51d-4586-aca1-4378af9dd284','01-translation-before.png'),
        ('4129d61c-d976-4fd9-ae34-e2b605aaa1ff','02-action-menu-before.png'),
        ('50ca1812-2f63-4847-b8ee-6292f0cfb5b1','03-status-before.png'),
        ('aa7983f1-905b-4e75-8b52-8a63dd713571','04-weapons-before.png'),
        ('f77daace-e7b2-478c-be1a-fbe2ff04b014','05-cut-in-before.png')]:
        shutil.copyfile(f'C:/Users/Binh/AppData/Local/Temp/codex-clipboard-{clip}.png',folder/name)
    for path in OUT.glob('*-preview.png'):shutil.copyfile(path,folder/path.name)
    changes=ROOT/'CHANGELOG.md';old=changes.read_text('utf-8')
    heading=note.splitlines()[0]
    if heading not in old:old=old.replace('# Change log\n\n','# Change log\n\n'+note,1)
    else:
        start=old.index(heading);end=old.find('\n## ',start+1)
        old=old[:start]+note+(old[end+1:] if end>=0 else '')
    changes.write_text(old,'utf-8')
    print('Recorded five UI witnesses, source review, parser previews, build status and changelog.')


if __name__=='__main__':main()
