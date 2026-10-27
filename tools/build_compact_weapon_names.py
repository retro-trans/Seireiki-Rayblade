"""Shorten menu-only attack names and their movie titles. Local 0.7.7."""
import argparse, copy, json, re, struct
from functools import lru_cache
from build_bitmap_font import ROOT, digest
from build_names_translation import compose as names_compose
from build_map_font_patch import member
from build_font4x_patch import MEDIUM
from english_text_codec import decode, encode
from test_ui_layouts import entry, parse_ui
from test_outline_font import legacy_mask
from check_native_text_components import verify
from disc_inventory import Disc, SECTOR
from package_archive_test_disc import substitute_payload_sector
from build_movie_test_disc import write_plan

VERSION, PRIOR = '0.7.7', '0.7.6'
OUT = ROOT/'work/output/compact-weapon-candidate'
RECIPE = ROOT/'work/translation/en/ui/compact-weapon-names.en.json'
# Full authored names remain in names.json/names.en.json. These are display aliases.
ALIASES = {
 'True One-Sword Art: Vanishing Shadow': 'Vanishing Shadow',
 'First Blade: Mighty Thunder Triumph Slash': '1st Blade: Thunder Slash',
 'Seven Flashes: Dragon Command Rift Breaker': 'Seven Flashes: Dragon Rift',
 'Second Blade: Dragon Slayer': '2nd Blade: Dragon Slayer',
 'Phantom Night Blade: Heaven Soar, Sky Rend': 'Phantom Blade: Sky Rend',
 'Heavenly Blade: Violet Flame Supreme Victory Slash': 'Heavenly Blade: Violet Flame',
 'Twin Supremacy: Gale Demon Wolf Flash Slash': 'Twin Might: Demon Wolf Flash',
 'Fury: Flame Wave, Heavenward Thunder Burst': 'Fury: Heavenward Thunder',
 'Rondo in a Breeze of Sorrow': 'Sorrow-Wind Rondo',
 'Pleasures of the Mortal Form': 'Mortal Pleasures',
 'Mighty Sword Zeulear (Malfunctioning)': 'Mighty Zeulear (Broken)',
}


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
    recipe=json.loads((base/'ui-layouts.en.json').read_text('utf-8'))
    previous=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    font=member((base/'WIN00.AFS').read_bytes(),0)[:99072]
    width=lambda s:sum(font[0xa0+MEDIUM.index(c)] for c in s)
    changes=[];seen=set()
    for row in rows:
        if row['group'] not in (4,12) or not row['en']:continue
        old=decode(entry(previous,row['id']))[0];new=old
        for full,short in ALIASES.items():
            if old==full or (row['group']==12 and old.endswith(': '+full)):
                new=old[:-len(full)]+short;seen.add(full);break
        if new==old:continue
        assert width(new)<width(old)
        recipe['rows'][row['id']]={'en':new,'source_sha256':row['source_sha256'],
            'prior_en_sha256':digest(row['en'].encode()),
            'reason':'Compact attack display name; retain full authored term in translation records. Matching movie title uses the same alias.'}
        changes.append({'id':row['id'],'before':old,'after':new,'old_pen_width':width(old),
                        'pen_width':width(new),'limit':136 if row['group']==4 else 240})
    assert seen==set(ALIASES)
    plain,packed,names_report=names_compose(overrides=recipe['rows'],version=VERSION)
    stream=len(packed);capacity=len((base/'text/D_NAMES.BIN').read_bytes());assert stream<=capacity
    packed+=bytes(capacity-stream)
    for row in rows:
        if row['group'] in (4,12) and row['en']:
            text=decode(entry(plain,row['id']))[0]
            assert width(text)<=(136 if row['group']==4 else 240),(row['id'],text,width(text))
    recipe.update(version=VERSION,previous_build=PRIOR)
    report={'version':VERSION,'source_build':PRIOR,'files':{'D_NAMES.BIN':{'size':len(packed),'sha256':digest(packed)}},
        'decoded_sha256':digest(plain),'decoded_bytes':len(plain),'compressed_stream_bytes':stream,
        'weapon_pen_limit':136,'movie_title_pen_limit':240,'changes':changes,
        'full_names':'Retained in working names.json and English names.en.json; aliases apply to display strings',
        'font_executable_and_gameplay':'unchanged','live_validation':'pending','release':False}
    return packed,plain,recipe,names_report,report


def check():
    packed,plain,recipe,names_report,component=compose();base=ROOT/'work/output'/PRIOR
    exe=(base/'1ST_READ.BIN').read_bytes();font=member((base/'WIN00.AFS').read_bytes(),0)[:99072]
    previous=(base/'text/D_NAMES.en.dec.bin').read_bytes()
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
    changed={r['id'] for r in component['changes']};unchanged=0;cases=[];steps=0
    for row in rows:
        if row['source_record_kind']=='unused_table_root_sentinel':continue
        if row['id'] not in changed:
            assert entry(plain,row['id'])==entry(previous,row['id']);unchanged+=1
        if row['group'] not in (4,12):continue
        payload=entry(plain,row['id']);gs,n=parse_ui(exe,font,plain,payload,x=0);steps+=n
        expected=decode(payload)[0];assert ''.join(g[0] for g in gs)==expected
        limit=136 if row['group']==4 else 240;right=0
        for ch,x,y,small in gs:
            assert y==0 and not small
            box=legacy_mask(font,ch,False).nonzero()
            if len(box[1]):right=max(right,x+(max(box[1])+1)/4+1)
        assert right<=limit,(row['id'],right,limit)
        cases.append({'id':row['id'],'ink_right_including_shadow':right,'limit':limit})
    # Exercise nested group-4 lookup alongside the actual Power/Range/Hit
    # coordinate controls. The row prefix is a bounded context fixture, not
    # an assertion about the complete weapon caller's parameter queue.
    weapon_rows=[]
    for i in (5,20,6,84,87):
        payload=encode('<FC:84:82><FC:FF:FF><FC:95:82><FC:FF:FF><FC:9A:82><FC:FF:FF><FC:9F:82><FC:FF:FF>')
        gs,n=parse_ui(exe,font,plain,payload,[(i,4),('200',False),('1~2',False),('+20',False)],x=16);steps+=n
        row_y=16;line=[g for g in gs if g[2]==row_y];name=[g for g in line if g[1]<168]
        assert name and ''.join(g[0] for g in name).strip()
        # Conservative name start32/Power168: 136px, including shadow/ink.
        right=max(x+(max(legacy_mask(font,ch,False).nonzero()[1])+1)/4+1
                  for ch,x,y,small in name if legacy_mask(font,ch,False).any())
        assert right<168,(row_y,right)
        assert next(g for g in line if g[0]=='2' and g[1]>=168)[1]==168
        weapon_rows.append({'id':f'names.g04.{i:03d}','row_y':row_y,'name':''.join(g[0] for g in name),'ink_right':right,'power_x':168})
    decoder=verify(exe,packed,plain,65536)
    return {'version':VERSION,'names_packed_sha256':digest(packed),'names_decoded_sha256':digest(plain),
        'executable_sha256':digest(exe),'unchanged_other_text_rows':unchanged,'native_rows':cases,
        'native_weapon_table':weapon_rows,'native_UI_instructions':steps,'native_PRS_instructions':decoder,
        'names_builder_validation':names_report['validation'],
        'limits':['Native parser, nested name lookup, PRS and ink bounds checked; caller parameter queue, GPU and live navigation not executed',
                  'Original font/executable/gameplay and all other payloads retained']}


def plan():
    packed,plain,recipe,names_report,component=compose();base=ROOT/'work/output'/PRIOR
    previous=json.loads((base/'english-disc-report.json').read_text('utf-8'))
    cue=base/'disc'/f'Rayblade English Test {PRIOR}.cue';disc=Disc(cue)
    entries={r['path']:r for r in disc.inventory()};inherited={}
    for name,row in previous['files'].items():
        raw=(base/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes()
        assert digest(raw)==row['sha256'] and disc.read(entries[name]['lba'],len(raw))==raw
        inherited[name]=raw
    target=dict(inherited,**{'D_NAMES.BIN':packed});entry_=entries['D_NAMES.BIN']
    source=inherited['D_NAMES.BIN'];original=Disc(next(ROOT.glob('*.cue'))).read(entry_['lba'],len(source))
    changes=[];delta=0
    for off in range(0,len(source),2048):
        a,b=source[off:off+2048],packed[off:off+2048]
        if a==b:continue
        lba=entry_['lba']+off//2048;track=next(t for t in disc.tracks if t['start_lba']<=lba<t['end_lba'])
        position=(track['index']+lba-track['start_lba'])*SECTOR
        with track['path'].open('rb') as f:f.seek(position);raw=f.read(SECTOR)
        changes.append((track['path'].name,position,substitute_payload_sector(raw,a,b)))
        delta+=int(b!=original[off:off+2048])-int(a!=original[off:off+2048])
    report=copy.deepcopy(previous)
    report.update(version=VERSION,source_build=PRIOR,kind='Local compact weapon/movie title names',
        files={n:{'size':len(v),'sha256':digest(v)} for n,v in target.items()},new_changed_sectors=len(changes),
        total_changed_sector_locations_from_original=previous['total_changed_sector_locations_from_original']+delta,
        component_manifest_name='compact-weapon-component.json',
        readme_component_text='Shortened overlong weapon names and matching event-movie list titles.\n'
            'All weapon names fit a 136-logical-pixel pen limit and all movie titles fit 240.\n'
            'Font, executable, stats, dialogue, choices, map labels and original opening/demo movies retain 0.7.6 bytes.\n'
            'Use a fresh boot and a normal memory-card save; emulator save states retain old name tables.\n',
        proof_scope='Native UI parser/nested weapon lookup, five row fixtures with fixed stat anchors and PRS; names builder preserves nontext data. All 14 extracted files and full track preservation.',
        current_native_evidence={'compact_names':'compact-weapon-native-test.json'},
        inherited_proof_note='Other native records retain their actual tested builds/hashes; only the names component has new current evidence.',
        pending=['Live weapon/menu/forecast and event-movie list appearance','Full-game/translation review'],release=False)
    names=re.findall(r'FILE "(.+)" BINARY',cue.read_text('utf-8'))
    return (disc,cue,inherited,target,changes,names,previous['historical_native_evidence'],report)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--disc',action='store_true');a=ap.parse_args()
    packed,plain,recipe,names_report,report=compose()
    if not a.write:print(json.dumps(report,indent=2));print('DRY RUN: no files written');return
    OUT.mkdir(parents=True,exist_ok=True)
    proof=check()
    for name,raw in [('D_NAMES.BIN',packed),('D_NAMES.en.dec.bin',plain)]:(OUT/name).write_bytes(raw)
    for name,value in [('component-report.json',report),('native-test.json',proof),('ui-layouts.en.json',recipe),('names-component-report.json',names_report)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    RECIPE.write_text(json.dumps({'version':VERSION,'previous_build':PRIOR,'weapon_pen_limit':136,'movie_pen_limit':240,'aliases':report['changes']},indent=2)+'\n','utf-8')
    print('PASS:',len(report['changes']),'display aliases;',len(proof['native_rows']),'native rows; five nested weapon rows and native PRS.',flush=True)
    if a.disc:
        p=plan();write_plan(p,VERSION,PRIOR,{'D_NAMES.BIN':packed});out=ROOT/'work/output'/VERSION
        (out/'text/D_NAMES.en.dec.bin').write_bytes(plain)
        for name,value in [('text/names-component-report.json',names_report),('ui-layouts.en.json',recipe),('compact-weapon-component.json',report),('compact-weapon-native-test.json',proof)]:
            (out/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
        manifest.update(version=VERSION,previous_build=PRIOR,current_payload_identities=p[7]['files'])
        manifest['files']['D_NAMES.BIN']['target_sha256']=digest(packed)
        manifest['native_proof_reuse']={'source_build':PRIOR,'scope':'Only D_NAMES display strings/relocated pointers changed. All other 13 payloads and boot area exact; historical proofs retain actual identities.'}
        manifest['compact_weapon_names']={'recipe':str(RECIPE.relative_to(ROOT)).replace('\\','/'),'native_proof':'compact-weapon-native-test.json'}
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
