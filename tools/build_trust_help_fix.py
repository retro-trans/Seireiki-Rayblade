"""Fit Trust popup labels and source-reviewed help in local build 0.7.9."""
import argparse, copy, json, math, re, struct
from functools import lru_cache
from build_bitmap_font import ROOT, digest
from build_names_translation import compose as names_compose
from build_map_font_patch import member
from build_font4x_patch import MEDIUM
from english_text_codec import encode, decode
from test_ui_layouts import entry, parse_ui
from test_outline_font import legacy_mask
from check_native_text_components import verify
from disc_inventory import Disc, SECTOR
from package_archive_test_disc import substitute_payload_sector
from build_movie_test_disc import write_plan

VERSION, PRIOR = '0.7.9', '0.7.8'
OUT = ROOT/'work/output/trust-help-candidate'
RECIPE = ROOT/'work/translation/en/ui/trust-help.en.json'
# Only the narrow tactical popup uses these aliases. Status names stay full.
LABELS = ('Bond','Friend','Enc.','Accel.','Focus','Intuit.','Arms','Wall','Again','Aware','Cover')
HELP = (
 'Restores 30% HP to one allied unit.',
 'Restores 50% HP to all allied units.',
 "Raises one ally's SP by 10.",
 "Adds 3 to one ally's move range for one move.",
 "Raises one ally's Accuracy by 30% for one turn.",
 "Raises one ally's Evasion by 30% for one turn.",
 "Raises one ally's attack power by 30% for its next attack.",
 "Raises one ally's defense by 50% for the next attack it takes.",
 'Gives your action to an ally that has already acted.',
 'Negates hit-rate and damage modifiers for the next side/rear attack on the selected unit.',
 'Takes the damage meant for the selected allied unit.',
)


def reflow(text, width):
    lines=['']
    for word in text.split():
        candidate=(lines[-1]+' '+word).strip()
        if width(candidate)>236:
            assert lines[-1] and width(word)<=236
            lines.append(word)
        else:lines[-1]=candidate
    assert len(lines)<=2,lines
    return '<NL>'.join(lines)


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR
    rows={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    recipe=json.loads((base/'ui-layouts.en.json').read_text('utf-8'))
    previous=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    font=member((base/'WIN00.AFS').read_bytes(),0)[:99072]
    width=lambda s:sum(font[0xa0+MEDIUM.index(c)] for c in s)
    changes=[]
    for i,(label,help_text) in enumerate(zip(LABELS,HELP),1):
        # Keep the existing dynamic parameter, with room for any three digits.
        spaces=math.ceil((34-width(label))/width(' '))
        title=label+' '*spaces+'<FC:FF:FF>'
        for key,text,reason in (
            (f'names.g00.{32+i:03d}',title,'Compact popup alias and value spacing; full status name and dynamic parameter retained.'),
            (f'names.g01.{i:03d}',reflow(help_text,width),'Source-reviewed complete effect, wrapped to at most two 236-pixel lines.')):
            row=rows[key];before=decode(entry(previous,key))[0]
            assert before.count('<FC:FF:FF>')==text.count('<FC:FF:FF>')
            recipe['rows'][key]={'en':text,'source_sha256':row['source_sha256'],
                'prior_en_sha256':digest(row['en'].encode()),'reason':reason}
            changes.append({'id':key,'before':before,'after':text,'source_sha256':row['source_sha256'],'reason':reason})
    plain,packed,names_report=names_compose(overrides=recipe['rows'],version=VERSION)
    stream=len(packed);capacity=len((base/'text/D_NAMES.BIN').read_bytes());assert stream<=capacity
    packed+=bytes(capacity-stream);recipe.update(version=VERSION,previous_build=PRIOR)
    report={'version':VERSION,'source_build':PRIOR,'files':{'D_NAMES.BIN':{'size':len(packed),'sha256':digest(packed)}},
        'decoded_sha256':digest(plain),'decoded_bytes':len(plain),'compressed_stream_bytes':stream,
        'changes':changes,'popup_ink_limit_logical_pixels':56,'help_pen_limit':236,'help_lines':2,
        'review':{'source':'Local original D_NAMES rows, group 1, entries 1..11',
            'effects_in_order':['30% HP, one ally','50% HP, all allies','SP +10, one ally',
                'Move +3, one move','Accuracy +30%, one turn','Evasion +30%, one turn',
                'Attack +30%, one attack','Defense +50%, one incoming attack',
                'Transfer action to an ally that has acted','Negate side/rear hit-rate and damage modifiers once',
                'Caster takes damage intended for selected ally'],
            'Awareness':'Concise equivalent of treating one side/rear attack as frontal; no extra attack or positional movement implied.'},
        'unchanged':'Full status command names, executable, fonts, gameplay tables, all dialogue and other 13 disc payloads',
        'issue_1':'Separate Stage 6 corruption investigation remains unresolved; this build does not claim to fix it.',
        'live_validation':'pending','release':False}
    return packed,plain,recipe,names_report,report


def check():
    packed,plain,recipe,names_report,component=compose();base=ROOT/'work/output'/PRIOR
    exe=(base/'1ST_READ.BIN').read_bytes();fonts=member((base/'WIN00.AFS').read_bytes(),0)
    previous=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    changed={r['id'] for r in component['changes']};unchanged=0;cases=[];steps=0
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
    for row in rows:
        if row['source_record_kind']=='unused_table_root_sentinel':continue
        if row['id'] not in changed:
            assert entry(plain,row['id'])==entry(previous,row['id']);unchanged+=1
    for mode,font in [('HD',fonts[:99072]),('Native',fonts[99072:])]:
        for i,label in enumerate(LABELS,1):
            key=f'names.g00.{32+i:03d}'
            for number in ('0','1','2','10','30','80','99','100','255','999'):
                gs,n=parse_ui(exe,font,plain,entry(plain,key),[(number,False)],x=0);steps+=n
                assert ''.join(g[0] for g in gs).replace(' ','')==label+number
                assert all(y==0 and not small for _,x,y,small in gs)
                right=0
                for ch,x,y,small in gs:
                    yy,xx=legacy_mask(font,ch,small).nonzero()
                    if len(xx):right=max(right,x+(max(xx)+1)/4+1)
                assert right<=56,(mode,key,number,right)
                cases.append({'mode':mode,'id':key,'number':number,'ink_right_with_shadow':right,'limit':56})
            key=f'names.g01.{i:03d}';payload=entry(plain,key);gs,n=parse_ui(exe,font,plain,payload,x=0);steps+=n
            expected=decode(payload)[0]
            assert ''.join(g[0] for g in gs)==expected.replace('<NL>','')
            assert set(g[2] for g in gs)<={0,16}
            right=bottom=0
            for ch,x,y,small in gs:
                assert not small
                yy,xx=legacy_mask(font,ch,small).nonzero()
                if len(xx):right=max(right,x+(max(xx)+1)/4+1);bottom=max(bottom,y+(max(yy)+1)/4)
            assert right<=240 and bottom<=32,(mode,key,right,bottom)
            cases.append({'mode':mode,'id':key,'lines':expected.count('<NL>')+1,'ink_right_with_shadow':right,'ink_bottom':bottom})
    return {'version':VERSION,'files':component['files'],'unchanged_other_name_rows':unchanged,
        'popup_cases':220,'help_cases':22,'cases':cases,'native_parser_instructions':steps,
        'native_PRS_instructions':verify(exe,packed,plain,65536),
        'validation':names_report['validation'],
        'limits':['Actual native parser and original font masks with bounded context/parameter fixtures; GPU/navigation not executed.',
            'Popup uses a conservative 56-pixel text interior; help uses at most two lines and 236-pixel pen width.',
            'The separate Stage 6 issue #1 is not resolved by this change.']}


def plan():
    packed,plain,recipe,names_report,component=compose();base=ROOT/'work/output'/PRIOR
    previous=json.loads((base/'english-disc-report.json').read_text('utf-8'))
    cue=base/'disc'/f'Rayblade English Test {PRIOR}.cue';disc=Disc(cue);entries={r['path']:r for r in disc.inventory()}
    inherited={}
    for name,row in previous['files'].items():
        raw=(base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes()
        assert digest(raw)==row['sha256'] and disc.read(entries[name]['lba'],entries[name]['size'])==raw
        inherited[name]=raw
    targets=dict(inherited,**{'D_NAMES.BIN':packed});ent=entries['D_NAMES.BIN'];source=inherited['D_NAMES.BIN']
    original=Disc(next(ROOT.glob('*.cue'))).read(ent['lba'],len(source));changes=[];delta=0
    for off in range(0,len(source),2048):
        a,b=source[off:off+2048],packed[off:off+2048]
        if a==b:continue
        lba=ent['lba']+off//2048;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
        position=(track['index']+lba-track['start_lba'])*SECTOR
        with track['path'].open('rb') as f:f.seek(position);raw=f.read(SECTOR)
        changes.append((track['path'].name,position,substitute_payload_sector(raw,a,b)))
        delta+=int(b!=original[off:off+2048])-int(a!=original[off:off+2048])
    report=copy.deepcopy(previous)
    report.update(version=VERSION,source_build=PRIOR,kind='Local Trust command labels and complete help',
        files={n:{'size':len(v),'sha256':digest(v)} for n,v in targets.items()},new_changed_sectors=len(changes),
        total_changed_sector_locations_from_original=previous['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='trust-help-component.json',
        readme_component_text='Compact Trust popup labels leave room for all numeric values. Full status names are retained.\n'
            'All eleven effect descriptions are source-reviewed and fit at most two lines.\n'
            'Accelerate: movement +3 for one move. Awareness: negate side/rear hit-rate and damage modifiers once.\n'
            'Only D_NAMES changes; executable, fonts, gameplay and other thirteen payloads are exact 0.7.8.\n'
            'Issue #1 (Stage 6 text corruption) remains a separate unresolved investigation.\n'
            'Cold-boot and load a normal in-game save; emulator states retain old text tables.\n',
        proof_scope='242 native parser fixtures in both font modes, all eleven original effect descriptions reviewed, PRS and complete disc preservation.',
        current_native_evidence={'trust_help':'trust-help-native-test.json'},
        pending=['Live Trust popup/help appearance and navigation','Separate Stage 6 issue #1 reproduction and fix','Full-game/translation review'],release=False)
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'))
    return disc,cue,inherited,targets,changes,names,previous['historical_native_evidence'],report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');args=ap.parse_args()
    packed,plain,recipe,names_report,report=compose()
    if not args.write:print(json.dumps(report,indent=2));return
    OUT.mkdir(parents=True,exist_ok=True);proof=check()
    for name,raw in [('D_NAMES.BIN',packed),('D_NAMES.en.dec.bin',plain)]:(OUT/name).write_bytes(raw)
    for name,value in [('component-report.json',report),('native-test.json',proof)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    RECIPE.write_text(json.dumps({'version':VERSION,'previous_build':PRIOR,'changes':report['changes'],'review':report['review']},indent=2)+'\n','utf-8')
    print('PASS: 220 popup and 22 complete-help native parser cases, native PRS, other name rows exact.',flush=True)
    if args.disc:
        p=plan();write_plan(p,VERSION,PRIOR,{'D_NAMES.BIN':packed});out=ROOT/'work/output'/VERSION
        (out/'text/D_NAMES.en.dec.bin').write_bytes(plain)
        for name,value in [('text/names-component-report.json',names_report),('ui-layouts.en.json',recipe),('trust-help-component.json',report),('trust-help-native-test.json',proof)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'));manifest.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        manifest['files']['D_NAMES.BIN']['target_sha256']=digest(packed)
        manifest['trust_help']={'recipe':str(RECIPE.relative_to(ROOT)).replace('\\','/'),'native_proof':'trust-help-native-test.json'}
        manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Only D_NAMES text and text pointers changed; all other thirteen payloads and boot area exact. Historical records retain actual identities.'}
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
