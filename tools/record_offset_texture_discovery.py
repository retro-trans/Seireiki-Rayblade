"""Record additional offset-table images and bounded ANIME marker evidence.

Default dry run. No game asset/build or translation-credit changes.
"""
import argparse
import json

from build_bitmap_font import ROOT,digest


def read(path):
    return json.loads(path.read_text('utf-8'))


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\','/')


def record():
    files=[]
    for name,resources,textures,pages in [('D_FACE',735,735,8),('D_UNIT',87,470,5)]:
        folder=ROOT/f'work/ui/asset-audit/{name}/offset-table-01'
        path=folder/'texture-index.json'
        data=read(path)
        assert not data['unsupported_or_failed']
        assert data['unique_nonempty_resources']==data['decoded_resources']==resources
        assert data['decoded_texture_count']==textures
        sheets=[folder/f'contact-{i:02d}.png' for i in range(pages)]
        assert all(p.is_file() for p in sheets)
        files.append({'file':name+'.BIN','source_sha256':data['source_sha256'],
                      'index':rel(path),'index_sha256':digest(path.read_bytes()),
                      'pointer_entries':data['pointer_entries'],
                      'nonempty_references':data['nonempty_pointer_references'],
                      'terminal_empty_references':len(data['terminal_empty_indices']),
                      'unique_resources':resources,'decoded_textures':textures,
                      'decoded_bytes':data['decoded_total_bytes'],
                      'palette_entries':sum(r.get('palette_entries',0) for r in data['decoded_resources_info']),
                      'texture_pixels':sum(r['width']*r['height'] for r in data['textures']),
                      'unsupported_or_failed':[],
                      'source_contacts_reviewed':[{'path':rel(p),'sha256':digest(p.read_bytes())} for p in sheets],
                      'observed':'Dialogue portraits, alternate expressions and small light/field effects' if name=='D_FACE' else 'Directional mech/vehicle sprites, small humanoid sprites and colored orb/field effects',
                      'image_text_review':'No additional readable Japanese observed at contact-sheet size; fine-detail absence and runtime reachability not proved'})
    proof_path=ROOT/'work/ui/asset-audit/offset-tables-native-test.json'
    proof=read(proof_path)
    assert proof['native_guard_and_ABI']=='pass' and len(proof['source_streams'])==4
    assert proof['native_PRS_instructions']==1596448
    assert proof['independently_checked_source_pixels']==139264
    doc={'current_game_build':'0.1.35','kind':'Additional relative-offset resource discovery; source bytes read only',
         'files':files,'decoded_textures':1205,'source_contacts_reviewed':13,
         'native_source_report':rel(proof_path),'native_source_report_sha256':digest(proof_path.read_bytes()),
         'native_source_checks':proof,
         'format_findings':['Both root tables contain relative offsets, rather than AFS offset/size pairs',
                            'D_FACE has 739 nonempty references to 735 distinct GBIX/PRS portraits, four alias references and 29 terminal/empty entries',
                            'D_UNIT has 87 PRS/PVM resources and one terminal offset; palettes are wrapped PVPL metadata within the PVM',
                            'Accounted for every 0..3-byte trailing zero alignment gap; PAL4 texture chunks can also have sixteen trailing zero bytes',
                            'Source contact discovery reveals no confirmed extra Japanese image label, not proof that no fine text exists'],
         'limits':['Only four representative source PRS streams are executed natively; all 822 resources decode structurally in the source audit',
                   'Only representative source pixels/palette entries are independently checked; complete source fingerprints are retained',
                   'Native offset-table consumers, palette selection, GPU and live appearance remain unexecuted',
                   'No translated/game bytes changed; latest playable build remains 0.1.35'],
         'game_bytes_changed':False,'draft_credit':0}
    marker_path=ROOT/'work/ui/asset-audit/ANIME/text-markers-01/marker-index.json'
    markers=read(marker_path)
    assert markers['members_checked']==642 and markers['byte_matches']==544 and markers['known_style_byte_matches']==22
    assert len(markers['candidate_context_duplicate_groups'])==11
    assert all(len(r['matches'])==2 for r in markers['candidate_context_duplicate_groups'])
    marker_summary={'index':rel(marker_path),'index_sha256':digest(marker_path.read_bytes()),
                    'source_archive_sha256':markers['source_archive_sha256'],'members_checked':642,
                    'raw_byte_matches':544,'known_style_byte_matches':22,'duplicate_context_groups':11,
                    'status':'Byte matches remain unresolved; decoder probes and duplicate numeric-looking contexts do not prove command/data semantics or text absence',
                    'next_evidence':markers['next_evidence'],'new_translation_credit':0}
    animation=read(ROOT/'docs/animation-payloads.json')
    animation.update(current_game_build='0.1.35',marker_audit=marker_summary,
                     status='642 exact decoded identities; 544 dialogue-like byte matches inventoried, 22 known-style matches in 11 duplicate context pairs. Native command/data boundaries and possible encoded text remain unresolved')
    animation['limits']=[p if not p.startswith('No source or translated game asset changed;') else 'Source format/marker discovery changes no game or translation bytes' for p in animation['limits']]
    expanded=read(ROOT/'docs/expanded-image-audit.json')
    expanded['offset_table_files']=files
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    audit['offset_table_texture_discovery']=doc
    status=read(ROOT/'docs/translation-status.json')
    assert status['version']=='0.1.35'
    status.update(offset_table_texture_discovery=doc,ANIME_payload_discovery=animation)
    status['non_movie_image_text_audit']=audit
    return [(ROOT/'docs/offset-texture-tables.json',doc),(ROOT/'docs/animation-payloads.json',animation),
            (ROOT/'docs/expanded-image-audit.json',expanded),(ROOT/'docs/non-movie-image-text-audit.json',audit),
            (ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: 1205 newly audited source textures, thirteen reviewed contacts, four native source PRS streams; 544 unresolved ANIME byte matches retained.')
    if not args.write:
        print('DRY RUN: no documentation/change log written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,indent=2)+'\n','utf-8')
    heading='## Working translation — additional offset-table image and ANIME marker discovery'
    entry='''## Working translation — additional offset-table image and ANIME marker discovery

- Found two texture-table files outside earlier AFS scans. D_FACE.BIN contains 768 relative pointers: 739 nonempty references map to 735 unique 64x64 portrait textures, with four alias references and 29 terminal/empty indices. D_UNIT.BIN contains 87 distinct PRS/PVM resources plus its terminal offset, with 470 directional unit/vehicle/effect textures and 1,392 stored palette entries. Decoded all 822 distinct resources with no format errors, retaining complete source/decoded identities and accounting for all zero alignment gaps. Unit PAL4 palettes live in wrapped PVPL metadata; some texture chunks retain sixteen trailing zero bytes.
- Reviewed all thirteen source contact sheets: eight portrait pages and five unit pages. Observed portraits/expressions, small light/field effects, mech/vehicle/humanoid sprites and colored orbs. No additional readable Japanese seen at preview size. This is not fine-detail text absence, actual resource reachability, live palette binding or GPU proof.
- Independently checked 139,264 representative source pixels and applicable palette entries. Four actual original PRS streams execute 1,596,448 SH-4 instructions with exact output and guards/ABI preserved. Other resource streams have structural decoder checks and complete hashes; native table lookup/loading and GPU remain unexecuted.
- Rechecked all 642 ANIME decoded identities and inventoried 544 raw 8A06 byte matches. Twenty-two have one of the five known scenario-style bytes; their 64-byte contexts form eleven duplicate pairs. Bounded first-page decoder probes preserve diagnostic counts/hashes without public Japanese prose. These coincidences remain unclassified: numeric-looking/duplicate contexts, successful decoding and unknown-glyph statistics do not prove command/data boundaries or exclude other text styles. No new dialogue row or text-absence credit.
- No game byte, font or translation draft changed in this discovery pass. Latest playable build remains 0.1.35; original dumps and prior builds untouched, no release. Remaining image/encoded-text discovery, unresolved captions/held passages, independent review and live/full-game validation continue.

'''
    log=ROOT/'CHANGELOG.md'
    text=log.read_text('utf-8')
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded source discovery and remaining semantic boundaries; no game build changed.')


if __name__=='__main__':
    main()
