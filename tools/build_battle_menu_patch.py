"""Widen action menu, shorten battle fields and normalize Cut-In status case. Dry first."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_names_translation import compose as names_compose

VERSION='0.1.42';PRIOR='0.1.41'
OUT=ROOT/'work/output/battle-menu-draft-01'
EDITS=[(0xf01f,34,30,'Action text origin: x272 to x240'),
       (0xf026,33,29,'Action frame origin: x264 to x232'),
       (0xf028,5,9,'Action frame width: 40 to 72 logical pixels'),
       (0x8a08b,32,56,'First action-text tile: 32 to 56 logical pixels'),
       (0x8a098,32,56,'Second action-text tile: 32 to 56 logical pixels')]


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;before=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(before)
    assert before[0xf01b:0xf02f]==bytes.fromhex('8a22010022f3198a20010021f205f18a23010800')
    assert before[0x8a07c:0x8a09b]==bytes.fromhex('000101020300000000010000010000204003000040000100010020002040ff')
    for at,old,new,_ in EDITS:assert exe[at]==old;exe[at]=new
    assert sum(a!=b for a,b in zip(before,exe))==len(EDITS)
    names={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    recipe=json.loads((base/'ui-layouts.en.json').read_text('utf-8'))
    changes={4:[('Trust Commands','Trust')],5:[('Movement Type','Move Type'),('Movement Range','Move'),('<FC:88:82>','<FC:87:82>')],
        6:[('Unit Abilities','Skills')],96:[('Accuracy','Hit')],
        97:[('Required Fighting Spirit','Req. SP'),('Prana Cost','PR Cost')],
        251:[('ON','On')],252:[('OFF','Off')]}
    aliases=[]
    for index,replacements in changes.items():
        key=f'names.g00.{index:03d}';row=names[key]
        old=recipe['rows'].get(key,row)['en'];new=old
        for a,b in replacements:assert a in new;new=new.replace(a,b)
        recipe['rows'][key]={'en':new,'source_sha256':row['source_sha256'],
            'prior_en_sha256':digest(row['en'].encode()),
            'reason':'Compact battle labels and title-case status; all placeholder counts retained. Terrain value moves from x64 to x56 to fit Water/Space.' if index==5 else 'Source-checked compact battle labels; matching title-case status. Every placeholder/control retained.'}
        aliases.append({'id':key,'before':old,'after':new})
    decoded,packed,names_report=names_compose(overrides=recipe['rows'],version=VERSION)
    stream=len(packed);capacity=len((base/'text/D_NAMES.BIN').read_bytes())
    assert stream<=capacity;packed+=bytes(capacity-stream)
    recipe.update(version=VERSION,previous_build=PRIOR)
    report={'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(before),
        'executable_sha256':digest(exe),'executable_data_edits':[{'offset':hex(p),'before':a,'after':b,'reason':s} for p,a,b,s in EDITS],
        'frame':{'before_x_width':[264,40],'after_x_width':[232,72],'right_edge':304,
                 'text_origin_x':240,'tile_visible_width':56,'surface_logical_width':64},
        'source_names_sha256':digest((base/'text/D_NAMES.BIN').read_bytes()),
        'names_packed_sha256':digest(packed),'names_decoded_sha256':digest(decoded),
        'names_stream_bytes':stream,'names_file_bytes':capacity,'names_zero_tail_bytes':capacity-stream,
        'aliases':aliases,'translation_check':{
            'command':'scenario.s_002.o026c6','target_rows':3,'context_rows_examined':25,
            'decision':'Retain wording. Ymir addresses Ai, then asks Touya to forgive Ai; she refers to Ai. The surname forms are deliberate scene-specific honorific localization.',
            'conventions':'docs/translation-conventions.json: forms_of_address[0]',
            'source_rows_sha256':digest(json.dumps([r for r in json.loads((ROOT/'work/translation/en/scenario/s_002.json').read_text('utf-8')) if r['block_id']=='scenario.s_002.o026c6'],sort_keys=True,ensure_ascii=False).encode()),
            'corpus_changes':0},
        'font_check':{'unchanged_font_build':'0.1.39','finding':'Native Cut-In and ON use the same medium Skies bank; visual distinction is all-capital status. Use On/Off, preserving state selection.'},
        'native_validation':'pending','live_validation':'pending','release':False}
    return {'1ST_READ.BIN':bytes(exe),'D_NAMES.BIN':packed},decoded,recipe,names_report,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,decoded,recipe,names,report=compose()
    print(json.dumps(report,indent=2),flush=True)
    if not args.write:print('DRY RUN: no components written.');return
    OUT.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():(OUT/name).write_bytes(raw)
    (OUT/'D_NAMES.en.dec.bin').write_bytes(decoded)
    for name,value in [('ui-layouts.en.json',recipe),('names-component-report.json',names),('component-report.json',report)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
