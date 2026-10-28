"""Record reviewed 0.7.20 live captures and exact runtime identities. Dry first."""
import argparse,json,struct
from build_battle_grid_fix import ROOT,VERSION,ENTRY,POINTER,compose,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    exe,component=compose();cases=[]
    for label,probe,ram_name in [('selected Touya','fresh-0720.json','cursor-fixed-0720.ram'),('cursor and camera redraw','redraw-0720.json','cursor-redraw-0720.ram')]:
        p=json.loads((ROOT/'work/output/cursor-investigation'/probe).read_text('utf-8'));ram=(ROOT/'work/source/runtime'/ram_name).read_bytes()
        assert p['kernel_matches'] and p['font_payload_matches'] and p['english_scenario']['entire_English_member_matches']
        assert p['english_scenario']['member']=='s_001.bin' and p['english_scenario']['VM_pointer']=='0x8c01e282'
        off=ENTRY-0x8c010000;size=component['adapter_bytes']
        assert ram[ENTRY&0xffffff:(ENTRY&0xffffff)+size]==exe[off:off+size]
        assert struct.unpack_from('<I',ram,0x10000+POINTER)[0]==ENTRY
        assert struct.unpack_from('<I',ram,0x7b910)[0]==384176
        assert struct.unpack_from('<I',ram,0x419530)[0]==0
        cases.append({'scene':label,'probe':f'work/output/cursor-investigation/{probe}','RAM_sha256':digest(ram),
            'camera':list(struct.unpack_from('<2h',ram,0x1e026e)),'runtime_adapter_and_pointer_exact':True,'texture_error':0})
    assert cases[0]['camera']!=cases[1]['camera']
    shots=[]
    for n in ['touya-range-game.jpg','cursor-range-redraw-game.jpg']:
        p=ROOT/'work/ui'/VERSION/n;shots.append({'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':digest(p.read_bytes())})
    live={'version':VERSION,'executable_sha256':digest(exe),'range_grid_alignment':'pass','cursor_camera_redraw':'pass',
        'startup':'pass','Native_1x_font':'pass','emulator':'Isolated Flycast profile; VGA, 480 / 1x output',
        'boot':'New Game after a full boot; no emulator save state, no emulated RAM writes',
        'review':'Actual GPU captures show filled tiles aligned with Touya and the selection arrows; after Down input, the camera pans and the cursor follows the displayed tile corners.',
        'cases':cases,'captures':shots,'user_session':'Read-only process inspection; no game inputs, file changes or process termination in the user Flycast instance.',
        'limits':['S001 first-battle visual/input scope only','Four camera cases use native instruction execution with the SDK draw endpoint recorded','Physical Dreamcast and full-game/long-session coverage remain pending']}
    print(json.dumps(live,indent=2))
    if not a.write:print('DRY RUN: no records written');return
    (ROOT/'work/output'/VERSION/'battle-grid-live-test.json').write_text(json.dumps(live,indent=2)+'\n','utf-8')
    path=ROOT/'docs/battle-grid.json';doc=json.loads(path.read_text('utf-8'));doc['live']=live
    doc['Retro_Trans']=json.loads((ROOT/'work/output/release-0.7.20/game-validation.json').read_text('utf-8'))
    path.write_text(json.dumps(doc,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
