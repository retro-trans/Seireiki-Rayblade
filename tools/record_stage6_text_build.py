"""Record the manually reviewed Stage 6 replay evidence. Dry run by default."""
import argparse,hashlib,json,struct
from pathlib import Path
from inspect_vram_residency import inspect

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'work/output/0.7.22'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    comp=json.loads((BASE/'stage-six-text-component.json').read_text('utf-8'))
    exe=(BASE/'1ST_READ.BIN').read_bytes();assert hashlib.sha256(exe).hexdigest()==comp['executable_sha256']
    captures={p.stem:{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in sorted((ROOT/'work/ui/issue-1/0.7.22').glob('*.jpg'))}
    required=['princess-dialogue','later-bridge-dialogue','allied-unit-list','counters','unit-profile-list','unit-profile-detail','character-profile-list','character-profile-detail','save-complete','load-battle-file4','reload-allied-unit-list','reload-counters','reload-unit-profile-detail','reload-character-profile-detail']
    assert set(required)<=captures.keys()
    rams={}
    for name in ['princess','later-bridge','battle','reload']:
        path=ROOT/f'work/source/issue-1/{name}-final-0722.ram';r=path.read_bytes()
        for row in comp['edits']:
            off=int(row['file_offset'],16);n=row['bytes'];assert r[0x10000+off:0x10000+off+n]==exe[off:off+n]
        state=inspect(r);assert state['native_texture_error']==0
        probe=json.loads((ROOT/f'work/output/issue-1/{name}-final-0722.json').read_text('utf-8'))
        assert probe['kernel_matches'] and probe['font_payload_matches'] and probe['font_modes']['selected']=='Native'
        rams[name]={'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path),'all_seven_patch_spans_exact':True,'residency':state}
    sessions={}
    for label in ['final','reload']:
        folder=ROOT/f'work/output/issue-1/runtime-0.7.22-{label}'
        rows=(folder/'residency.csv').read_text().splitlines()
        assert rows and not [r for r in rows if int(r.split(',')[2])!=0]
        sessions[label]={'native_texture_error_rows':0,'residency_observations':len(rows),'telemetry_sha256':digest(folder/'residency.csv'),'driver_sha256':digest(folder/'flycast.lua')}
    baseline={}
    for name in ['work/ui/issue-1/0.7.0/princess-missing-dialogue.jpg','work/ui/issue-1/0.7.21/later-bridge-white-panel.jpg']:
        p=ROOT/name;baseline[name]=digest(p)
    codec=json.loads((ROOT/'work/output/issue-1/final-bridge-codec-live.json').read_text('utf-8'))
    assert len(codec)==2 and all(r['decoded_text_texels_exact'] for r in codec)
    proof={'version':'0.7.22','issue':'https://github.com/retro-trans/Seireiki-Rayblade/issues/1','issue_1_reproduction_and_fix':'pass',
        'executable_sha256':comp['executable_sha256'],'method':'Fresh boot, supplied issue VMU File 1, Next, full S0c8 bridge replay to Stage 6 battle. Supported controller input; read-only RAM/telemetry. No emulator save states or guest RAM writes.',
        'supplied_VMU_sha256':'23670a05accbcb3311b93f3812b5244733394698b4691cf876abe4c96badb01e',
        'dialogue':{'first_princess_VM':'0x8c0108ec','later_bridge_VM':'0x8c010cbe','visual_review':'Both formerly missing/white dialogue scenes display correctly.','codec':codec},
        'battle_menu_visual_review':{'Allied Unit List':'pass','Counters':'pass','System / Unit Profiles list and Almaris detail':'pass','System / Character Profiles list and Arthur detail':'pass','Save list and Save complete message':'pass'},
        'save_load':{'private_VMU_only':True,'saved_to':'Port A Slot 1, previously empty File 4, Touya Lv6 / Turns 1 / Chapter 6',
            'saved_VMU_sha256':'6208465cf3de3a7f24dd75a15fb2b0faf7413d66fcc90cf9cae1d163af75395a',
            'method':'Closed private emulator; copied its saved VMU to a separate private profile; cold booted same final disc and selected File 4 in normal Load File UI.',
            'after_reload':'Allied Unit List, Counters, Unit Profile detail and Character Profile detail visually pass; native texture error remains zero.'},
        'screenshots':captures,'baseline_reproductions':baseline,'RAM':rams,'sessions':sessions,
        'limits':['Physical Dreamcast untested','Complete routes and extended sessions untested','This is a targeted texture-corruption check, not complete UI proofreading; the existing long Chapter 6 save label overlaps the In Battle label.'],
        'publication':'Local build only; no GitHub release, issue comment or closure.'}
    print(json.dumps({'version':proof['version'],'issue_1':proof['issue_1_reproduction_and_fix'],'captures':len(captures),'RAM_checks':list(rams),'sessions':sessions,'writes':['local live test proof','docs/stage6-text.json','current build validation metadata']},indent=2))
    if not a.write:print('DRY RUN: evidence exists and matches final code; no records written.');return
    (BASE/'stage6-text-live-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
    doc_path=ROOT/'docs/stage6-text.json';doc=json.loads(doc_path.read_text('utf-8'))
    doc.update(status='Issue #1 supplied-save reproduction and fix pass in Flycast; local full/upgrade packages',live_proof='work/output/0.7.22/stage6-text-live-test.json',live=proof)
    doc_path.write_text(json.dumps(doc,indent=2)+'\n','utf-8')
    comp['validation']='Native exact-texel/SDK tests and fresh supplied-save bridge/battle/normal VMU save-load replay pass; see stage6-text-live-test.json'
    (BASE/'stage-six-text-component.json').write_text(json.dumps(comp,indent=2)+'\n','utf-8')
    report_path=BASE/'english-disc-report.json';report=json.loads(report_path.read_text('utf-8'));report['validation']['in_game']='Stage 6 issue #1 fresh supplied-save replay, menus and normal VMU save/load pass; stage6-text-live-test.json'
    report_path.write_text(json.dumps(report,indent=2)+'\n','utf-8')

if __name__=='__main__':main()
