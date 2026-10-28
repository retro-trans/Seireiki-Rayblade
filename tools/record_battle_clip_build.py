"""Record reviewed 0.7.23 combat/highlight evidence. Dry first."""
import argparse,json,struct
from pathlib import Path
from PIL import Image
from build_battle_clip_fix import ROOT,VERSION,PRIOR,ENTRY,LINE_POINTERS,BAR_EDITS,compose,digest

def spans(im):
    dark=[]
    for x in range(640):
        if sum(max(im.getpixel((x,y)))<20 for y in range(70,410))>330:dark.append(x)
    groups=[]
    for x in dark:
        if groups and groups[-1][-1]+1==x:groups[-1].append(x)
        else:groups.append([x])
    return [[a[0],a[-1]] for a in groups]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    exe,component=compose();base=ROOT/'work/output'/VERSION;assert (base/'1ST_READ.BIN').read_bytes()==exe
    final=ROOT/'work/ui/battle-clip/0.7.23/final';names=['action-abilities.jpg','counter-policy.jpg','counterattack-highlight.jpg','select-weapon-highlight.jpg','ai-split-0.jpg','ai-split-1.jpg','ai-split-2.jpg']
    captures=[]
    for n in names:
        path=final/n;im=Image.open(path);assert im.size==(642,512)
        captures.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path.read_bytes())})
    old=Image.open(ROOT/'work/ui/battle-clip/0.7.22/split-battle-seam.jpg').convert('RGB').crop((1,31,641,511))
    new=Image.open(final/'ai-split-1.jpg').convert('RGB').crop((1,31,641,511))
    before,after=spans(old),spans(new);assert [288,319] in before
    assert after and all(315<=lo<=hi<=323 and hi-lo<8 for lo,hi in after),after
    assert sum(max(new.getpixel((160,y)))<20 for y in range(70,250))<15
    rams=[]
    for name in ['forecast','split-final']:
        path=ROOT/f'work/source/issue-1/{name}-0723.ram';ram=path.read_bytes()
        off=ENTRY-0x8c010000;n=component['helper_bytes'];assert ram[ENTRY&0xffffff:(ENTRY&0xffffff)+n]==exe[off:off+n]
        for p in (*LINE_POINTERS,0x6b7a4):assert ram[p+0x10000:p+0x10004]==exe[p:p+4]
        for p,_,v,_ in BAR_EDITS:assert ram[p+0x10000]==v
        assert struct.unpack_from('<I',ram,0x419530)[0]==0
        probe=json.loads((ROOT/f'work/output/battle-clip/{name}-0723.json').read_text('utf-8'))
        assert probe['kernel_matches'] and probe['font_payload_matches'] and probe['font_modes']['selected']=='Native'
        rams.append({'path':path.relative_to(ROOT).as_posix(),'sha256':digest(ram),'all_modified_spans_match':True,'native_texture_error':0})
    stage=json.loads((ROOT/'work/output/0.7.22/stage-six-text-component.json').read_text('utf-8'))
    previous=(ROOT/'work/output/0.7.22/1ST_READ.BIN').read_bytes()
    for e in stage['edits']:
        p=int(e['file_offset'],16);n=e['bytes'];assert exe[p:p+n]==previous[p:p+n]
    report=json.loads((base/'english-disc-report.json').read_text('utf-8'))
    prior_report=json.loads((ROOT/'work/output/0.7.22/english-disc-report.json').read_text('utf-8'))
    for name,row in report['files'].items():
        if name!='1ST_READ.BIN':assert row['sha256']==prior_report['files'][name]['sha256']
    runtime=ROOT/'work/output/issue-1/runtime-0.7.23-battle-final'
    rows=(runtime/'residency.csv').read_text().splitlines();assert not [r for r in rows if int(r.split(',')[2])!=0]
    live={'version':VERSION,'battle_clipping_and_selection_bars':'pass','executable_sha256':digest(exe),
        'method':'Private Flycast, VGA, fresh boot with normal Stage 6 battle VMU File 4 made during the issue #1 replay. No emulator save states, guest RAM edits or texture replacements.',
        'VMU_source_sha256':'6208465cf3de3a7f24dd75a15fb2b0faf7413d66fcc90cf9cae1d163af75395a',
        'visual_review':['Counterattack and Select Weapon green bars fully cover their labels','Always Counterattack and Abilities fit inside their selection bars with original frame spacing',
            'Enemy attack and Clovis counterattack complete; subsequent enemy attack against Ai reaches settled split panes and continues',
            'The former x160 partial divider and x288–319 blank strip are absent; the divider follows the central split'],
        'dark_full_height_columns_before':before,'dark_full_height_columns_after':after,'game_crop':[1,31,641,511],
        'stage6_lossless_fix_byte_exact':True,'stage6_proof':'work/output/0.7.22/stage6-text-live-test.json',
        'all_14_other_payloads_exact_0722':True,'native_texture_error_rows':0,'residency_observations':len(rows),
        'RAM':rams,'captures':captures,'native_proof':'work/output/0.7.23/battle-clip-native-test.json',
        'limits':['Physical Dreamcast untested','Complete routes, extended sessions and independent translation proofreading remain pending'],
        'publication':'Release held at user request; public upgrade must be from the last public release, 0.7.11, to 0.7.23.'}
    print(json.dumps(live,indent=2))
    if not a.write:print('DRY RUN: record proof/docs and save a game-only crop; no files written.');return
    component['validation']='Native SDK/selection/line cases and fresh normal-VMU live combat/highlight checks pass; battle-clip-live-test.json'
    (base/'battle-clip-component.json').write_text(json.dumps(component,indent=2)+'\n','utf-8')
    (base/'battle-clip-live-test.json').write_text(json.dumps(live,indent=2)+'\n','utf-8')
    (ROOT/'docs/battle-clip.json').write_text(json.dumps({'version':VERSION,'component':component,'live':live},indent=2)+'\n','utf-8')
    new.save(final/'split-view-game.png')
    report['validation']['in_game']='Battle split-view and selection bars pass; battle-clip-live-test.json'
    (base/'english-disc-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')

if __name__=='__main__':main()
