"""Record reviewed image discovery and resolved MAP source formats. Dry first.

Discovery only: latest playable game remains 0.1.32. Original assets unchanged.
"""
import argparse
import copy
import json

from build_bitmap_font import ROOT,digest


def read(path):
    return json.loads((ROOT/path).read_text('utf-8'))


def witness(path):
    return {'path':path,'sha256':digest((ROOT/path).read_bytes())}


def record():
    index_path='work/ui/asset-audit/MAP/formats-01/texture-index.json'
    index=read(index_path)
    proof_path='work/ui/asset-audit/MAP/formats-01/native-source-test.json'
    proof=read(proof_path)
    assert index['decoded_textures']==398 and index['unsupported_or_failed']==[]
    assert len(index['non_GBIX_members'])==124 and index['dummy']['member']==428
    assert proof['source_archive_sha256']==index['source_archive_sha256']
    assert proof['independent_pixels_checked']==349525 and proof['native_PRS_instructions']==21565194
    assert proof['native_guard_and_ABI']=='pass' and proof['native_decoded_bytes']==699088
    source124=next(r for r in index['textures'] if r['member']==124)
    assert source124['decoded_sha256']==proof['decoded_sha256']
    pages={archive:[witness(f'work/ui/asset-audit/{archive}/'+('formats-01/' if archive=='MAP' else '')+f'contact-{page:02d}.png')
                    for page in range(count)] for archive,count in [('MAP',5),('CUTIN',2),('BTT_FACE',8)]}
    map_doc={'status':'398 real standalone map textures decoded; two historical decoder errors resolved; discovery contacts reviewed, full-resolution/reachability review incomplete',
             'source_archive_sha256':index['source_archive_sha256'],
             'current_game_build':'0.1.32','game_build_changed':False,
             'texture_index':witness(index_path),'source_native_proof':witness(proof_path),
             'real_GBIX_textures':398,'non_GBIX_members_outside_decoder':124,
             'dummy':index['dummy'],'historical_397_source_identities':'all exact',
             'resolved_mipmap':{'member':124,'pixel_format':'RGB565','data_format':18,
                                'dimensions':[512,512],'levels':10,'independent_pixels':349525,
                                'decoded_bytes':699088,'native_PRS_instructions':21565194,
                                'preview':witness('work/ui/asset-audit/MAP/formats-01/member-124-base.png')},
             'reviewed_contacts':pages['MAP'],
             'visual_findings':'Town/terrain/building atlas images. No definite additional readable Japanese observed on the five contacts or the full member-124 base view.',
             'remaining_small_detail':'Tiny plaque/sign-like details, including member 124, are not established as readable text; no full-resolution absence claim for the archive.',
             'limits':index['limits']+['Native proof executes only source PRS, not map loading, texture submission or GPU rendering']}
    anime_path='work/ui/asset-audit/ANIME/decoded-01/structure-index.json'
    anime=read(anime_path)
    assert anime['PRS_members_decoded']==642 and anime['PRS_full_member_consumption']=='all exact'
    assert anime['decoded_bytes']==31250921 and anime['image_signature_matches']==18
    assert anime['recognized_JPEG_structures']==0 and anime['unsupported_or_failed']==[]
    assert all(h['signature'].startswith('JPEG_') for r in anime['members'] for h in r['known_image_signature_hits'])
    anime_doc={'status':'All 642 animation archive members PRS-decoded; binary VM/table semantics and possible embedded encoded text remain unclassified',
               'index':witness(anime_path),'source_archive_sha256':anime['source_archive_sha256'],
               'decoded_members':642,'decoded_bytes':31250921,'whole_member_consumption':'all exact',
               'decoded_first_byte_histogram':anime['decoded_first_byte_histogram'],
               'known_Ninja_or_PNG_GIF_signature_matches':0,
               'JPEG_like_byte_matches':18,'recognized_or_verified_JPEGs':0,
               'limits':anime['limits'],'game_build_changed':False}
    portrait_doc={'status':'All 15 discovery contacts reviewed; no additional readable Japanese observed at thumbnail scale',
                  'archives':[{'archive':'MAP.AFS','textures':398,'contacts':pages['MAP'],'contents':'terrain, buildings and town scenery'},
                              {'archive':'CUTIN.AFS','textures':122,'contacts':pages['CUTIN'],'contents':'mech/environment cut-in pictures; 367 other members remain outside GBIX decoder'},
                              {'archive':'BTT_FACE.AFS','textures':703,'contacts':pages['BTT_FACE'],'contents':'battle portraits and final light-effect frames; two other members outside GBIX decoder'}],
                  'limits':['Thumbnail review is not complete full-resolution no-text or reachability proof',
                            'Fine signs/insignia/decorative marks and non-GBIX formats still need classification',
                            'No source images, translated assets or game build changed']}
    context_doc={'status':'Four effect status-icon meanings still on context hold; native literal coincidences rejected',
                 'UI_text_context':[
                     {'id':'names.g00.124','meaning':'Counterattack selection offers Counterattack, Select Weapon, Evade and Defend'},
                     {'id':'names.g00.174','meaning':'Counterattack orders include Manual, Always Counterattack, Be Aggressive, Play It Safe and Always Defend'},
                     {'ids':['names.g01.024','names.g01.028','names.g01.029','names.g01.030','names.g01.031'],
                      'meaning':'Help explains manual reactions and automatic counterattack/evade/defend policies'}],
                 'native_search_limits':[
                     'Small immediates 59..62 occur as unrelated parser thresholds and stack byte offsets; no direct atlas-icon use established.',
                     'PC-relative words 0x33b..0x33e at 0x8c024daa..0x8c024dbc and 0x8c0258c4..0x8c0259ea are stack offsets, not proven global sprite IDs. Do not use them as semantic evidence.'],
                 'external_manual_candidate':'https://psinstructionmanual.com/rayblade/',
                 'manual_version':'PlayStation; not assumed identical to Dreamcast',
                 'manual_images_verified':False,
                 'access_limit':'Web image opens unavailable; Windows browser inspection stopped because URL-policy enforcement is unsupported. No further computer input or media-download workaround used.',
                 'icon_ids':['effect.250.059','effect.250.060','effect.250.061','effect.250.062'],
                 'next_evidence_needed':'Native icon selection path or readable in-game/manual context matching each icon; script choice text alone does not bind icons to meanings'}
    expanded=read('docs/expanded-image-audit.json')
    mapping={r['archive']:r for r in expanded['audits']}
    m=mapping['MAP.AFS']
    if 'historical_GBIX_audit' not in m:
        m['historical_GBIX_audit']={k:copy.deepcopy(m[k]) for k in ['GBIX_index','GBIX_index_sha256','GBIX_textures_decoded','GBIX_errors']}
    m.update(GBIX_index=index_path,GBIX_index_sha256=digest((ROOT/index_path).read_bytes()),
             GBIX_textures_decoded=398,GBIX_errors=[],explicit_dummy_members=[428],
             visual_review='Five revised map contact sheets and full member-124 base texture reviewed; no definite readable Japanese observed; fine-detail/full-resolution review incomplete',
             format_details='docs/map-formats.json')
    mapping['CUTIN.AFS']['visual_review']='Both contact sheets reviewed: mech/environment close-ups, no definite readable Japanese at thumbnail scale; full-resolution/non-GBIX/reachability review incomplete'
    mapping['BTT_FACE.AFS']['visual_review']='All eight contact sheets reviewed: battle portraits and final light-effect frames, no definite readable Japanese at thumbnail scale; full-resolution/non-GBIX/reachability review incomplete'
    mapping['ANIME.AFS'].update(decoded_payload_index=anime_path,decoded_payload_index_sha256=anime_doc['index']['sha256'],
                              PRS_payloads_decoded=642,
                              visual_review='All 642 raw PRS payloads decoded; no Ninja/PNG/GIF signatures; 18 JPEG-like byte matches not recognized/verified as images. VM/table semantics remain unclassified')
    expanded['limits']=[
        'ANIME payloads now decoded, but VM/table semantics and signatureless image/encoded-text possibilities remain unclassified',
        'EFFECT palettes decoded and nine UI labels inserted; icon/calligraphy readings, native bindings and complete full-resolution/reachability review pending',
        'MAP/CUTIN/BTT_FACE discovery contacts reviewed; remaining non-GBIX formats and fine-detail/full-resolution review incomplete',
        'Two album caption readings, held passages, independent meaning/artwork/font and live/full-game review remain incomplete']
    audit=read('docs/non-movie-image-text-audit.json')
    audit.update(map_format_discovery=map_doc,ANIME_payload_discovery=anime_doc,
                 additional_contact_review=portrait_doc,effect_icon_context=context_doc,
                 expanded_archive_audits=expanded['audits'],expanded_audit_limits=expanded['limits'])
    status=read('docs/translation-status.json')
    status.update(map_format_discovery=map_doc,ANIME_payload_discovery=anime_doc,
                  additional_contact_review=portrait_doc,effect_icon_context=context_doc,
                  non_movie_image_text_audit=audit)
    return [(ROOT/'docs/map-formats.json',map_doc),(ROOT/'docs/animation-payloads.json',anime_doc),
            (ROOT/'docs/additional-image-review.json',portrait_doc),(ROOT/'docs/effect-icon-context.json',context_doc),
            (ROOT/'docs/expanded-image-audit.json',expanded),(ROOT/'docs/non-movie-image-text-audit.json',audit),
            (ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('Plan: document resolved MAP formats/source native proof, 15 reviewed contacts, 642 decoded animation payloads and unresolved icon-context evidence.')
    if not args.write:
        print('DRY RUN: no documentation written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    heading='## Working translation — remaining map formats and image discovery'
    entry='''## Working translation — remaining map formats and image discovery

- Resolved both historical MAP GBIX errors. Member 124 is a 512x512 RGB565 alternate mipmap resource: all ten level spans and six leading zero bytes are accounted for; the existing base-mip decoder now previews it. Member 428 is a 38-byte explicit ASCII dummy, not a compressed texture; its exact capitalization/CRLF marker was corrected in the initial dry assertion before writing. New index retains 398 real standalone texture identities, 124 non-GBIX members and the dummy separately. All 397 previously decoded source identities remain exact; historical audit retained.
- Independently verified 349,525 RGB565 pixels across all ten mip levels. The native original PRS routine executes 21,565,194 SH-4 instructions for 699,088 exact source bytes with guards/ABI preserved. This is source format/decoder evidence, not new native map loading, texture submission or GPU proof.
- Reviewed all fifteen contact sheets: five MAP, two CUTIN and eight BTT_FACE, plus member 124 at native size. Observed town/terrain/building art, mech/environment cut-ins, battle portraits and final light-effect frames. No definite additional readable Japanese observed at preview size; fine signs/insignia, non-GBIX formats, full-resolution absence and live reachability remain unproven.
- PRS-decoded all 642 ANIME members with exact full-member stream consumption, totaling 31,250,921 decoded bytes. Recorded every source/decoded identity and prefix family. No Ninja/PNG/GIF signatures occur; eighteen JPEG-like byte matches in ten members fail image identification/verification. Signature searches do not exclude signatureless images or encoded text; the animation VM/table formats and their semantics remain unclassified. No source scripts are committed.
- Recorded local reaction-menu/help context for the four effect icons and rejected unrelated native immediate/stack-offset coincidences as semantic evidence. The discovered PlayStation manual remains unviewed: web image opens failed and Windows browser inspection was stopped by unavailable URL-policy enforcement. No browser/input retry or remote-media workaround. Other local work continues; the four icon meanings remain held.
- No translated asset/game byte or build changed in this discovery pass; latest playable build remains 0.1.32. No release and no additional story/library draft credit. Full translation and independent meaning/artwork/font/live/full-game validation remain incomplete.

'''
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded discovery and change log; playable build remains 0.1.32.')


if __name__=='__main__':
    main()
