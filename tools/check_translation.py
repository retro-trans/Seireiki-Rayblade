"""Validate source-linked library drafts and write an English-only status report.

Default is read-only. This checks structure and consistency, not translation
meaning or in-game layout. Human review remains a separate stage.
"""
import argparse
import json
import re
from collections import Counter
from build_font_patch import ROOT
from prepare_library_translation import fingerprint
from build_font4x_patch import MEDIUM


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8'))
    source=read('work/source/library/rows.json');rows=read('work/translation/en/library/library.json')
    entries=read('work/source/library/entries.json');names=read('work/source/text/D_NAMES.rows.json')
    glossary=read('work/glossary/glossary.json')['entries']
    assert len({r['id'] for r in rows})==len(rows),'Duplicate row ID'
    assert [r['id'] for r in rows]==[r['id'] for r in source],'Source/translation ID mismatch'
    for row,original in zip(rows,source):
        assert row['source_sha256']==fingerprint(original),('Stale source',row['id'])
        assert row['conditions']==original['conditions'],('Unlock conditions changed',row['id'])
        assert row['ends_with_newline']==original['ends_with_newline'],('Newline boundary changed',row['id'])
        if row['en'] is not None:
            assert bool(row['en'])==bool(original['ja']),('Missing/extra content',row['id'])
            assert re.findall(r'<[^>]+>',row['en'])==re.findall(r'<[^>]+>',original['ja']),('Lost control token',row['id'])
            assert row['en'].isascii(),('Outside implemented font repertoire',row['id'])
    for entry in entries:
        for section in entry['sections']:
            assert ''.join(t['raw'] for t in section['tokens'])==section['raw_hex'],'Library token/raw mismatch'
            assert not section['unknown_glyphs'],'Unknown library glyph'
    for row in names:
        assert ''.join(t['raw'] for t in row['tokens'])==row['raw_hex'],'Name token/raw mismatch'
        assert not row['unknown_glyphs'],'Unknown name glyph'
    by_entry={}
    for row in rows:
        item=by_entry.setdefault(row['entry_id'],{'ja':[],'en':[]})
        item['ja'].append(row['ja']);item['en'].append(row['en'] or '')
    missing=[]
    for eid,text in by_entry.items():
        ja=''.join(text['ja']);en=' '.join(text['en'])
        # Check entities and specific terminology, not common substrings such
        # as "Pilot", "Love" or "Trust", which naturally vary with grammar.
        seen=set()
        for term in glossary:
            if term['category'] not in ('character','mech','person','organization','place','model','device','program','nickname'):continue
            j=term['ja'];e=term.get('en');key=(j,e)
            if not e or key in seen or len(j)<3:continue
            seen.add(key)
            pattern=re.escape(j)
            if term['category'] in ('character','mech','person','nickname'):
                # Match a whole katakana name, not Sharl inside Vishal or
                # Render inside the ordinary adjective "slender".
                if re.match(r'[\u30a0-\u30ff]',j):pattern=r'(?<![\u30a0-\u30ff])'+pattern
                if re.search(r'[\u30a0-\u30ff]$',j):pattern+=r'(?![\u30a0-\u30ff])'
            forms=[e]+term.get('accepted_english_forms',[])
            if re.search(pattern,ja) and not any(v.lower() in en.lower() for v in forms):
                missing.append({'entry_id':eid,'expected':e,'glossary_id':term['id']})
    canonical=[e for e in entries if e['id']==e['canonical_id'] and e['sections']]
    unique_content={(e['kind'],e['raw_hex']) for e in canonical}
    report={'version':'0.1.3','stage':'library first draft; no translated game build yet',
        'glossary':{'entries':len(glossary),'categories':dict(Counter(e['category'] for e in glossary)),
                    'character_metadata_entries':sum(e.get('metadata_status','').startswith(('draft','partial')) for e in glossary)},
        'library':{'physical_profiles':len(canonical),'distinct_profile_payloads':len(unique_content),
                   'physical_profiles_by_kind':dict(Counter(e['kind'] for e in canonical)),
                   'physical_rows':len(rows),'nonempty_rows':sum(bool(r['ja']) for r in rows),
                   'drafted_nonempty_rows':sum(bool(r['en']) for r in rows),'structural_empty_rows':sum(not r['ja'] for r in rows),
                   'unique_unlock_condition_stacks':len({tuple(r['conditions']) for r in rows if r['conditions']}),
                   'all_source_glyphs_decoded':True,'ascii_font_repertoire_pass':True},
        'checks':{'source_ids_and_fingerprints':'pass','raw_token_reconstruction':'pass','unlock_conditions':'pass',
                  'physical_line_boundaries':'pass','english_repertoire':'pass','name_checks_to_review':missing},
        'remaining':['Independent meaning review','Confirm disputed names and source inconsistencies',
                     'Measure library UI and implement layout/reflow without cutting meaning',
                     'Relocate and reinsert English text; preserve conditional spans',
                     'In-game English font and library checks','Finish story translation and audit remaining UI text'],
        'story':{'archive_members':448,'script_members_excluding_file_list':447,'authoritative_extracted_rows':None,
                 'translated_rows':0,'status':'opcode/text-boundary research pending; no speculative script dump treated as dialogue'}}
    scenario_summary=ROOT/'work/source/scenario-text/summary.json'
    if scenario_summary.exists():
        summary=json.loads(scenario_summary.read_text(encoding='utf-8'))
        story=report['story'];story.update(candidate_text_blocks=summary['blocks'],candidate_physical_rows=summary['physical_rows'],
            unique_candidate_payloads=summary['unique_text_payloads'],source_review_items=summary['issues'],
            candidate_inline_commands=summary.get('inline_commands',summary['blocks']),
            continuation_pages=summary.get('continuation_pages',0),
            status='candidate inline text and FE continuation pages extracted; full VM coverage and text relocation pending')
        drafted=0;prepared=0;unsupported=set();held=[]
        for path in (ROOT/'work/translation/en/scenario').glob('s_*.json'):
            if path.name.endswith('.en.json'):continue
            scenario_rows=json.loads(path.read_text(encoding='utf-8'));prepared+=len(scenario_rows)
            for row in scenario_rows:
                if row.get('status')=='held':
                    assert row.get('en') is None,'Held row must remain untranslated'
                    held.append({'id':row['id'],'reason':row.get('decisions','')})
                if row.get('en'):
                    drafted+=1;unsupported.update(c for c in re.sub(r'<[^>]+>','',row['en']) if c not in MEDIUM)
        story.update(translated_rows=drafted,prepared_physical_rows=prepared,unsupported_characters_pending_font=sorted(unsupported),
                     held_untranslated_rows=len(held),translation_holds=held)
        report['remaining'].extend(['Prove full scenario command coverage and relocate VM targets correctly',
                                    'Audit all image-based UI text and any movie captions'])
        print('Scenario candidate corpus: {} blocks; {} unique payloads; {} content rows drafted.'.format(summary['blocks'],summary['unique_text_payloads'],drafted))
    ui_path=ROOT/'work/translation/en/ui/names.json'
    battle_summary=ROOT/'work/source/battle/summary.json'
    if battle_summary.exists():
        battle=json.loads(battle_summary.read_text(encoding='utf-8'))
        report['battle_messages']={k:battle[k] for k in ('source_file','physical_records','root_pointers',
            'text_spans','distinct_text_payloads','physical_rows','nonempty_rows','unreferenced_text_rows',
            'uncovered_nonpadding_bytes','unknown_glyph_ids')}
        complete_battle=False
        report['battle_messages'].update(translated_nonempty_rows=0,first_draft_complete=False,
            status='extracted; translation and insertion pending')
        working=ROOT/'work/translation/en/battle/battle.json'
        if working.exists():
            drafted_battle=json.loads(working.read_text(encoding='utf-8'))
            source_battle=json.loads((ROOT/'work/source/battle/rows.json').read_text(encoding='utf-8'))
            complete_battle=([r['id'] for r in drafted_battle]==[r['id'] for r in source_battle] and
                all(r['en'] is not None and bool(r['en'])==bool(s['ja']) for r,s in zip(drafted_battle,source_battle)))
            pending_battle_font=sorted({c for r in drafted_battle if r['en'] for c in re.sub(r'<[^>]+>','',r['en']) if c not in MEDIUM})
            report['battle_messages'].update(prepared_physical_rows=len(drafted_battle),
                translated_nonempty_rows=sum(bool(r['en']) for r in drafted_battle),
                first_draft_complete=complete_battle,
                unsupported_characters_pending_font=pending_battle_font,
                status=('complete source-linked first draft; combat-state mapping, independent meaning review, insertion and layout pending'
                    if complete_battle else 'source-linked drafting in progress; combat-state mapping, meaning, insertion and layout pending'))
        native=ROOT/'work/output/0.1.4/battle-native-test.json'
        if native.exists():
            proof=json.loads(native.read_text(encoding='utf-8'))
            if proof['decoded_sha256']!=battle['decoded_sha256'] or proof['text_spans_witnessed']!=battle['text_spans']:
                raise ValueError('Battle native proof does not match current extraction')
            report['battle_messages']['native_selection_validation']={k:proof[k] for k in
                ('native_root_lookup_cases','golden_cases','selection_cases','SH4_instructions',
                 'text_spans_witnessed','condition_outcomes_witnessed','maximum_single_output_bytes',
                 'raw_output_and_return_pointer','destination_guards','limits')}
        report['remaining'].append(('Review and insert fully drafted battle-message selection graphs; verify combat-state setup and game layout'
            if complete_battle else 'Translate and insert battle-message selection graphs; verify combat-state setup and game layout'))
    if ui_path.exists():
        ui=json.loads(ui_path.read_text(encoding='utf-8'))
        pending=Counter(r['group'] for r in ui if r['en'] is None)
        report['ui_names']={'source_file':'D_NAMES.BIN','total_records':len(ui),
            'nonempty_source_rows':sum(bool(r['ja']) for r in ui),'english_nonempty_rows':sum(bool(r['en']) for r in ui),
            'prepared_methods':dict(Counter(r.get('translation_method','legacy') for r in ui if r['en'])),
            'untranslated_by_group':dict(pending),'fully_prepared_groups':[g for g in range(13) if not pending[g]],
            'status':'draft; layout, runtime assembly and insertion unverified'}
    component_path=ROOT/'work/output/0.1.3/text/library-component-report.json'
    if component_path.exists():
        component=json.loads(component_path.read_text(encoding='utf-8'))
        report['library']['offline_component']={k:component[k] for k in
            ('output_decoded_size','output_compressed_size','relocated_root_pointers','rebuilt_condition_nodes','validation','pending')}
    disc_reports=[p for p in (ROOT/'work/output').glob('0.*.*/english-disc-report.json')
                  if 'diagnostic' not in json.loads(p.read_text('utf-8'))]
    disc_report=max(disc_reports,key=lambda p:tuple(map(int,p.parent.name.split('.')))) if disc_reports else None
    if disc_report is not None:
        disc=json.loads(disc_report.read_text(encoding='utf-8'))
        report['stage']='local English menu/name test disc built; library first draft and offline component; full game translation in progress'
        report['test_disc']={k:disc[k] for k in ('version','kind','names','changed_sectors','validation','pending')}
        if 'ui_names' in report:
            report['ui_names']['status']='draft inserted in local '+disc['version']+' test disc; in-game layout and runtime assembly unverified'
        report['remaining']=[s for s in report['remaining'] if s!='Relocate and reinsert English text; preserve conditional spans']
        report['remaining'].append('Verify library loader capacity and insert rebuilt conditional profiles')
        if 'library' in disc:
            report['version']=disc['version']
            report['stage']='local English menu/name/library test disc built; full game translation and in-game validation in progress'
            report['library']['disc_integration']=disc['library']
            report['library']['native_filter_validation']=disc['library_native_validation']
            report['library']['offline_component']['pending']=['In-game layout and behavior checks']
            report['remaining'].remove('Verify library loader capacity and insert rebuilt conditional profiles')
            report['remaining'].append('Verify library navigation, measured screen layout and memory use in-game')
        if 'battle' in disc:
            report['battle_messages']['disc_integration']=disc['battle']
            report['battle_messages']['english_native_validation']=disc['battle_native_validation']
            report['battle_messages']['status']='first draft inserted in local '+disc['version']+' test disc; combat-state mapping, meaning review and layout/gameplay pending'
            report['stage']='local English menu/name/library/battle test disc built; story insertion and full-game validation pending'
            report['remaining']=[s for s in report['remaining'] if s!='Review and insert fully drafted battle-message selection graphs; verify combat-state setup and game layout']
            report['remaining'].append('Verify inserted battle messages, combat-state selection, measured layout and memory in-game')
        if 'scenario' in disc:
            report['story']['disc_integration']=disc['scenario']
            report['story']['native_insertion_validation']=disc['scenario_native_validation']
            report['story']['status']='complete drafted commands inserted in local '+disc['version']+'; held commands remain original; full VM coverage, meaning review and gameplay/layout pending'
            report['stage']='local English story/menu/name/library/battle test disc built; startup and full-game validation pending'
            report['remaining']=[s for s in report['remaining'] if s not in
                ('Prove full scenario command coverage and relocate VM targets correctly','Finish story translation and audit remaining UI text')]
            report['remaining'].extend(['Resolve held story passages; prove full VM text coverage',
                'Verify actual script loading, original event pointers, save/load and dialogue layout'])
        live_path=ROOT/'work/ui'/disc['version']/'live-validation.json'
        if live_path.exists():
            live=json.loads(live_path.read_text('utf-8'))
            if live['executable_sha256']!=disc['files']['1ST_READ.BIN']['sha256']:
                raise ValueError('Live evidence executable differs from packaged build')
            report['test_disc']['live_validation']=live
            report['stage']=live.get('stage','local English story/menu/name/library/battle test disc boots and displays first English dialogue; font proportions, word wrapping and full-game validation pending')
            report['remaining'].append(live.get('layout_issue','Correct individually stretched font glyphs and character-count wrapping observed in first dialogue'))
    print('Library: {drafted_nonempty_rows}/{nonempty_rows} nonempty rows drafted; {physical_profiles} physical profiles, {distinct_profile_payloads} distinct payloads.'.format(**report['library']))
    print('Structural checks passed. Name/term candidates requiring review:',len(missing))
    print(json.dumps(missing[:25]))
    out=ROOT/'docs/translation-status.json'
    if not args.write:print('DRY RUN: no status file written');return
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',out)


if __name__=='__main__':main()
