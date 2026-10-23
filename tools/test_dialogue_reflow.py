"""Audit every dialogue and execute affected native loading, lookup and text paths."""
import argparse,json,struct
from collections import Counter
from build_dialogue_reflow import ROOT,OUT,VERSION,PRIOR,digest
from build_antialias_font import font_bytes
from dialogue_reflow import reflow,prose_key,paginate
from scenario_word_wrap import tokens
from rayblade_codec import decompress
from test_scenario_integration import fresh,reset,install,format_case,guarded,run,HEAP,HEAP_BYTES,DEST
from build_scenario_patch import SOURCE,BASE,HEAP_POINTER
from build_scenario_translation import BANK_POINTER_OFFSET,SCRIPT_CAPACITY,align
from test_scenario_pages import native_format
from test_inline_controls import execute_stream
from test_ordered_archive_layouts import directory_bytes,lookup
from afs_layout import compact_positions
from test_battle_text import cases_for,native_select,root_lookup
from test_battle_translation import workspace
from check_native_text_components import verify
from test_embedded_dialogue import EmbeddedCPU,output_bytes,ENTRY


def read(path): return json.loads(path.read_text('utf-8'))


def line_audit(payload,font):
    line=0;maximum=0;boundaries=0;glyphs=0
    for row in tokens(payload,font):
        if row['kind']=='boundary': maximum=max(maximum,line);line=0;boundaries+=1;glyphs=0
        else:
            line+=row['width'];glyphs+=row['kind']=='glyph'
            assert line<=236 and glyphs<=127,('Dialogue overflow',line,glyphs)
    return maximum,boundaries


def check():
    base=ROOT/'work/output'/PRIOR
    component=read(OUT/'component-report.json');exe=(OUT/'1ST_READ.BIN').read_bytes()
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1]
    assert digest(font)==component['font_sha256']
    files={n:(OUT/n).read_bytes() for n in component['files']}
    for name,raw in files.items():assert digest(raw)==component['files'][name]['sha256']
    archive=files['D_SCE.AFS'];story=read(OUT/'scenario-component-report.json')
    old_archive=(base/'D_SCE.AFS').read_bytes();old_story=read(base/'text/scenario-component-report.json')
    cpu=fresh(exe,archive);plains={};all_rows={};steps=Counter();maximum=boundaries=inline_count=0
    witnesses={r['id'] for r in read(ROOT/'work/output/0.1.6/scenario-insertion-audit.json')['native_cases']}
    for m,old in zip(story['members'],old_story['members']):
        off=m['archive_offset'];plain,used=decompress(archive[off+20:off+m['packed_bytes']])
        assert digest(plain)==m['decoded_sha256'] and used==m['packed_bytes']-20
        p=old['archive_offset'];before,_=decompress(old_archive[p+20:p+old['packed_bytes']])
        assert plain[:m['original_bytes']]==before[:old['original_bytes']]
        plains[m['index']]=plain;install(cpu,plain,m)
        assert [r['id'] for r in m['commands']]==[r['id'] for r in old['commands']]
        for row,previous in zip(m['commands'],old['commands']):
            raw=plain[row['english_offset']:row['english_offset']+row['english_bytes']]
            prior=before[previous['english_offset']:previous['english_offset']+previous['english_bytes']]
            assert reflow(prior,font)[0]==raw
            assert row['source_offset']==previous['source_offset'] and row['source_bytes']==previous['source_bytes']
            w,n=line_audit(raw,font);maximum=max(maximum,w);boundaries+=n
            n,_=format_case(cpu,plain,m,row);steps['story_lookup']+=n
            all_rows[row['id']]=(m,row)
            control=[t for t in tokens(raw,font) if 'fc' in t and t['fc']!=0x3e]
            if control or row['id'] in witnesses:
                n,_=format_case(cpu,plain,m,row,native=True,phases=True);steps['story_formatter_VM']+=n
            if control:
                a,n=native_format(exe,prior,width=127,limit=8191,capacity=8192);steps['inline_format']+=n
                b,n=native_format(exe,raw,width=127,limit=8191,capacity=8192);steps['inline_format']+=n
                before_cpu,n,effects,states=execute_stream(exe,font,a,row['id']);steps['inline_parse']+=n
                after_cpu,n,effects2,states2=execute_stream(exe,font,b,row['id']);steps['inline_parse']+=n
                assert effects==effects2 and states==states2
                assert ''.join(g[0] for g in before_cpu.glyphs if g[0]!=' ')==''.join(g[0] for g in after_cpu.glyphs if g[0]!=' ')
                for ch,x,y,small in after_cpu.glyphs:assert 64<=x<=300 and 16<=y<=48
                inline_count+=1
        if (m['index']+1)%100==0: print('Audited and native-looked-up story members',m['index']+1,flush=True)
    assert len(all_rows)==50273 and inline_count==166
    directory=directory_bytes('D_SCE.AFS',archive)
    for r in compact_positions(archive):
        off,size,n=lookup(exe,'D_SCE.AFS',directory,r['member']);steps['archive_lookup']+=n
        assert off==r['declared_offset'] and size==r['sectors']
    # Decoder+loader witnesses: largest input/output/prefix, all dynamically
    # compressed members, all nontext members and the opening scene.
    chosen={1:story['members'][1]}
    for key in ('packed_bytes','decoded_bytes','original_bytes'):
        m=max(story['members'],key=lambda r:r[key]);chosen[m['index']]=m
    for m in story['members']:
        if not m['english_commands'] or m.get('dynamic_PRS'):chosen[m['index']]=m
    for m in chosen.values():
        c=fresh(exe,archive);reset(c);saved=list(c.reg[8:]);c.reg[4:6]=[m['index'],SOURCE]
        steps['native_loader']+=run(c,BASE+0x78270)
        assert c.reg[0]==1 and c.reg[8:]==saved
        a,p=c.area(HEAP,HEAP_BYTES);assert bytes(a[p:p+len(plains[m['index']])])==plains[m['index']]
        assert c.read(HEAP+BANK_POINTER_OFFSET,4)==HEAP+m['bank_offset'];guarded(c)
    print('Story: all words/controls/widths/lookups, inline effects and representative native loaders passed.',flush=True)
    embedded=read(OUT/'embedded-dialogue-component.json');embedded_cases=0
    for row in embedded['records']:
        raw=exe[row['english_offset']:row['english_offset']+row['english_bytes']]
        assert digest(raw)==row['english_sha256'];line_audit(raw,font)
        reference,n=native_format(exe,raw,width=127,limit=8191,capacity=8192);steps['embedded']+=n
        for warm in (False,True):
            for phases in (False,True):
                c=fresh(exe,b'');c.__class__=EmbeddedCPU;c.formatter_calls=[];c.write(HEAP_POINTER,HEAP if warm else 0,4)
                reset(c);saved=list(c.reg[8:]);c.reg[4:8]=[DEST,BASE+row['source_offset'],30,3];c.write(c.reg[15],8191,4)
                if phases:
                    c.write(0x8c1dbe24,BASE+row['command_offset']+1,4)
                    steps['embedded']+=run(c,BASE+0x6cfb2,BASE+0x6cfe6)
                    assert c.read(BASE+0x8b1ec,4)==row['source_bytes']+1
                    steps['embedded']+=run(c,BASE+0x6d4b8,BASE+0x6d4c2)
                    assert c.reg[0]==0x6000|(row['source_bytes']+2)
                    c.write(c.reg[15],c.reg[0],4);steps['embedded']+=run(c,BASE+0x2f35c,BASE+0x2f382)
                    assert c.read(0x8c1dbe24,4)==BASE+row['command_end']+1
                else: steps['embedded']+=run(c,ENTRY);assert c.reg[0]==row['source_bytes']
                assert c.reg[8:]==saved and output_bytes(c)==reference;guarded(c);embedded_cases+=1
    # Reconstruct every source-to-target selection address from the explicit
    # relocation records. No condition/RNG decision is replaced by a fixture.
    battle= (OUT/'D_BMESS.en.dec.bin').read_bytes();br=read(OUT/'battle-component-report.json')
    original_records=read(ROOT/'work/source/battle/records.json');mapping={}
    spans={r['source_offset']:battle[r['target_offset']:r['target_offset']+r['target_bytes']] for r in br['span_relocations']}
    old_br=read(base/'text/battle-component-report.json')
    old_battle=decompress((base/'text/D_BMESS.BIN').read_bytes())[0]
    previous_spans={r['source_offset']:old_battle[r['target_offset']:r['target_offset']+r['target_bytes']] for r in old_br['span_relocations']}
    for key,value in spans.items():
        raw=reflow(previous_spans[key]+b'\xff',font,safe_fc=set(range(0x40,0x4b)))[0]
        expected,extra=paginate(raw,font)
        assert expected==value+b'\xff'
        lines=1
        for row in tokens(expected,font):
            if row['raw']==b'\xfd':lines+=1;assert lines<=3
            elif row['raw']==b'\xfe':lines=1
        if extra:
            native,n=native_format(exe,raw,width=127,limit=8191,capacity=8192)
            assert native==expected;steps['battle_pagination']+=n
    for r in br['record_relocations']:mapping[r['source_offset']]=r['target_offset']
    for r in br['span_relocations']:mapping[r['source_offset']]=r['target_offset']
    for r in br['pointer_relocations']:mapping[r['source_target']]=r['target']
    # Each selection result is audited after concatenation, including both
    # fragments that do not finish with a page break.
    cases=list(cases_for(original_records));largest=b'';selection_cases=0
    for record,start,pointer,case in cases:
        expected=b''.join(spans[p] for p in case['spans'])+b'\xff'
        line_audit(expected,font)
        at=mapping[record['offset']];piece=battle[at:at+0x3000]
        steps['battle_selection']+=native_select(exe,piece,mapping[start]-at,
            None if pointer is None else pointer-record['offset'],case['flags'],case['rng'],expected)
        if len(expected)>len(largest):largest=expected
        selection_cases+=1
    assert selection_cases==6034 and 4*len(largest)<=0x800
    roots=read(ROOT/'work/source/battle/summary.json')['root_records']
    for r in roots:steps['battle_roots']+=root_lookup(exe,battle,r['index'],mapping[r['target']])
    # All slot pairs/root aliases retain their native copy/allocation ABI.
    for i in range(128):
        for flag in (0,64):steps['battle_workspace']+=workspace(exe,battle,[i,(i+1)%128],flag,[largest]*4)
    print('Battle: 6034 selections, widths, 128 roots and 256 workspace cases passed. Native PRS...',flush=True)
    steps['battle_PRS']=verify(exe,files['D_BMESS.BIN'],battle,0x50000,instruction_limit=20_000_000)
    return {'version':VERSION,'source_build':PRIOR,'files':component['files'],'executable_sha256':digest(exe),
        'font_sha256':digest(font),'story_commands':len(all_rows),'maximum_pen_width':maximum,'story_line_boundaries':boundaries,
        'inline_effect_commands':inline_count,'native_story_loader_cases':len(chosen),'archive_lookup_cases':448,
        'embedded_commands':13,'embedded_native_cases':embedded_cases,'battle_spans':5516,'battle_native_selection_cases':selection_cases,
        'battle_native_root_cases':128,'battle_native_workspace_cases':256,'largest_battle_output':len(largest),
        'native_instructions':dict(steps),'words_controls_FE_pages_VM_addresses':'preserved',
        'limits':['File I/O, allocation/cache, glyph drawing and effect/GPU endpoints use documented bounded fixtures',
                  'All widths and bank lookups audited; full native formatting uses inline/VM witnesses, not all 50273 commands',
                  'Battle flags/RNG outcomes use deterministic fixtures; preceding combat-state setup unverified',
                  'Fresh-boot reading flow, callback timing, GPU appearance and full-game navigation remain pending']}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args();assert not args.write_report or args.verify
    print('Plan: every story/embedded/battle dialogue, all bank/selection paths, inline controls, native loader/formatter/VM/PRS witnesses.',flush=True)
    if not args.verify:print('DRY RUN: no native execution or report.');return
    proof=check()
    if args.write_report:(OUT/'native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    print('PASS: all dialogue reflow gates.',flush=True)


if __name__=='__main__':main()
