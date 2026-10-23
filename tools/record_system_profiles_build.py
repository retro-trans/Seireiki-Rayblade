"""Record 0.1.35 additional profile translation and its precise limits."""
import argparse
import json

from build_bitmap_font import ROOT,digest
from build_system_profiles_disc import VERSION,PRIOR,plan
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    out=ROOT/'work/output'/VERSION
    report=read(out/'english-disc-report.json')
    assert {k:v for k,v in report.items() if k!='validation'}==plan()[-1]
    assert report['new_changed_sectors']==5 and report['total_changed_sector_locations_from_original']==28446
    assert report['validation']['reextracted_files']=='all 13 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    previous=read(ROOT/'work/output'/PRIOR/'english-disc-report.json')
    disc_path=out/'disc'/f'Rayblade English Test {VERSION}.gdi'
    disc=Disc(out/'disc'/f'Rayblade English Test {VERSION}.cue')
    entries={r['path']:r for r in disc.inventory()}
    for name,info in report['files'].items():
        row=entries[name]
        raw=disc.read(row['lba'],row['size'])
        assert len(raw)==info['size'] and digest(raw)==info['sha256']
        if name!='D_SYSTEM.AFS':
            assert info==previous['files'][name]
    assert len(report['historical_native_evidence'])==23
    for record in report['historical_native_evidence']:
        raw=(out/record['file']).read_bytes()
        assert digest(raw)==record['sha256'] and json.loads(raw)['executable_sha256']==record['executable_sha256']
    proof_raw=(out/'system-profiles-native-test.json').read_bytes()
    proof=json.loads(proof_raw)
    component=read(out/'system-profiles-component-report.json')
    assert proof==report['system_profiles_native_proof'] and component==report['system_profiles_component']
    assert digest(proof_raw)==report['system_profiles_proof_sha256']
    assert proof['archive_sha256']==report['files']['D_SYSTEM.AFS']['sha256']
    assert proof['source_rows_drafted']==16 and proof['root_aliases_checked']==384
    assert proof['native_filter_cases']==46 and proof['native_parser_cases']==135
    assert proof['maximum_native_page_bytes']==330 and proof['maximum_logical_ink_extent']==237
    preview=out/'system-profiles-profile-preview.png'
    summary={'version':VERSION,'source_build':PRIOR,'archive':'D_SYSTEM.AFS',
             'status':'Two additional source-profile drafts inserted; actual archive use/loading, independent meaning and live review unverified',
             'disc':rel(disc_path),'archive_sha256':proof['archive_sha256'],
             'profiles':2,'new_Japanese_source_rows_drafted':16,'aliases_preserved':384,
             'existing_English_labels_reencoded':128,'new_main_library_rows':0,'new_story_rows':0,
             'recipe':component['translation_recipe'],'recipe_sha256':component['translation_recipe_sha256'],
             'native_report':rel(out/'system-profiles-native-test.json'),'native_report_sha256':digest(proof_raw),
             'preview':rel(preview),'preview_sha256':digest(preview.read_bytes()),
             'source_differences':'Preserves year 5959, Zeifon then Rayblade, weapons/main controls and two-pilot activation, without adding current-library lore or a female-pilot restriction',
             'native_filter_cases':46,'native_parser_cases':135,'maximum_page_bytes':330,'page_capacity':512,
             'maximum_ink_pixels':237,'ink_capacity':240,'normal_font_changed':False,
             'actual_archive_reachability':'Unproved; literal filename absence alone does not prove unused',
             'new_changed_sectors':5,'changed_locations_from_original':28446,
             'validation':report['validation'],'pending':report['pending'],'release':False}
    doc={**summary,'source_archive_sha256':component['source_archive_sha256'],
         'source_member_sizes':[1963,2432],'target_member_sizes':[2342,2304],
         'source_profile_split':'128 aliases to a six-byte-header character profile; 256 aliases to a five-byte-header mech profile',
         'target_relocation':'Raw member 0 moves from 524288 to 2048 in verified zero prefix space; raw member 1 remains at 526336',
         'preservation':'Archive extent, eleven profile header bytes, aliases, existing label text/leading spaces and all bytes outside two member payloads/descriptors exact. Source profile body remains at its unreferenced old slot.',
         'component':component,'native_proof':proof}
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,
                  stage='Sixteen additional D_SYSTEM profile rows drafted and inserted; remaining text/images, actual runtime use and independent/live/full-game validation incomplete',
                  latest_system_profiles_build=summary)
    status['library']['additional_system_profiles']=summary
    status['test_disc'].update(version=VERSION,source_build=PRIOR,path=rel(disc_path),kind=report['kind'],
                               changed_sectors=28446,system_profiles_delta_sectors=5,
                               D_SYSTEM_sha256=proof['archive_sha256'],validation=report['validation'],pending=report['pending'])
    status['test_disc'].pop('order_icons_delta_sectors',None)
    return [(ROOT/'docs/system-profiles.json',doc),(ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: sixteen additional drafted rows, thirteen exact disc payloads, 23 retained proof identities; five new sectors.')
    if not args.write:
        print('DRY RUN: no records/change log written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
    heading='## 0.1.35 — translate two additional system profiles'
    entry='''## 0.1.35 — translate two additional system profiles

- Found an additional raw-text archive, D_SYSTEM.AFS, outside the current translated WIN00 library. Its first member has 384 relative pointers sharing two different/older profile records: 128 character aliases and 256 mech aliases. Drafted all sixteen Japanese source rows separately, using existing glossary names. Preserved year 5959, the Zeifon-to-Rayblade pilot history, weapons/main-control duties and the two-pilot activation statement; no name is assigned from ambiguous alias indices and no current-library lore is substituted. Independent meaning/category review remains pending. Source prose is stored only in ignored local files; the English-only recipe contains fingerprints and metadata.
- Preserved the eleven header bytes and every alias relationship. Reflowed full English words to the current 236-pixel pen budget, yielding eleven/seven display lines. The profile member grows from 1,963 to 2,342 bytes and relocates from 524,288 to 2,048 in verified zero archive prefix space. The second member retains all 128 numbered Unknown labels and their leading spaces, reencoded for the integrated Latin font, including replacement of the legacy wide-glyph colon. It shrinks from 2,432 to 2,304 bytes in place. Original archive extent and bytes outside declared payloads/descriptors remain exact; original profile body remains at its unreferenced source slot.
- Checked all 384 pointers and 128 labels independently, exact English words/punctuation, headers and archive guards. Forty-six actual native filtering cases and 135 parser cases through both current constructed library viewers pass. Largest real six/seven-line output is 330 of 512 bytes; maximum glyph/shadow ink extent is 237 of 240 pixels. These are controlled text-compatibility fixtures: they do not establish D_SYSTEM loading, legacy selection/viewer behavior, loader capacity or actual reachability. Glyph advances and graphics/allocation/clear endpoints retain bounded fixtures; no GPU/live proof or PRS-compression claim applies to the raw members.
- Packaged local build 0.1.35 with five sector substitutions, bringing the total to 28,446 locations from original. All thirteen payloads re-extract exactly; changed-sector EDC/ECC, unchanged ISO inventory and comparison of all 1,188,856,032 track bytes pass. All twelve preceding game payloads, current font, story/current library, icons, artwork, selected-logo subtitle movies and twenty-three historical native proof identities remain exact. Original dump and older builds untouched; no release.
- This adds sixteen additional-profile draft rows, not main-library or story credit. Remaining image/encoded-text discovery, two album captions, held passages, independent meaning/artwork/font review and live/full-game validation remain incomplete. Literal absence of D_SYSTEM.AFS in the executable is not proof that the archive is unused.

'''
    log=ROOT/'CHANGELOG.md'
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded additional profile status and change log; full translation remains incomplete.')


if __name__=='__main__':
    main()
