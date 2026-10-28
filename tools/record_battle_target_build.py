"""Record reviewed 0.7.21 target captures and runtime identity. Dry first."""
import argparse,json,shutil,struct
from PIL import Image
from build_battle_target_fix import ROOT,VERSION,compose,digest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');a=ap.parse_args()
    exe,component=compose();base=ROOT/'work/output'/VERSION
    probe_path=ROOT/'work/output/target-investigation/forecast-0721.json'
    probe=json.loads(probe_path.read_text('utf-8'))
    ram=(ROOT/'work/source/runtime/reticle-forecast-0721.ram').read_bytes()
    assert probe['kernel_matches'] and probe['font_payload_matches']
    scenario=probe['english_scenario']
    assert scenario['entire_English_member_matches'] and scenario['original_VM_prefix_matches']
    assert scenario['member']=='s_001.bin' and scenario['VM_pointer']=='0x8c01e7eb'
    for row in component['adapters']:
        entry=int(row['entry'],16);off=entry-0x8c010000;size=row['bytes']
        assert ram[entry&0xffffff:(entry&0xffffff)+size]==exe[off:off+size]
    for row in component['pointer_edits']:
        assert struct.unpack_from('<I',ram,0x10000+int(row['file_offset'],16))[0]==int(row['new'],16)
    assert struct.unpack_from('<I',ram,0x7b910)[0]==384176
    assert struct.unpack_from('<I',ram,0x419530)[0]==0
    anchor=struct.unpack_from('<2h',ram,0x1717a0+76*18+32)
    expected=[anchor[0]*2,(anchor[1]-24)*2];assert expected==[316,196]
    captures=[];images=[]
    for source,name,case in [
        ('sequence/player-02.jpg','enemy-target-game.png','Player attack: black enemy mech'),
        ('sequence/enemy-09.jpg','player-target-game.png','Enemy attack: Touya')]:
        path=ROOT/'work/ui'/VERSION/source;im=Image.open(path)
        assert im.size==(642,512)
        crop=im.crop((1,31,641,511)).convert('RGB')
        pts=[(x,y) for y in range(480) for x in range(640)
             if (lambda c:c[1]>185 and c[0]<120 and c[2]<160)(crop.getpixel((x,y)))]
        box=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)]
        center=[(box[0]+box[2])/2,(box[1]+box[3])/2]
        assert max(abs(c-e) for c,e in zip(center,expected))<=1
        dst=ROOT/'work/ui'/VERSION/name;images.append((crop,dst))
        captures.append({'case':case,'source':str(path.relative_to(ROOT)).replace('\\','/'),
            'source_sha256':digest(path.read_bytes()),'game_capture':str(dst.relative_to(ROOT)).replace('\\','/'),
            'crop_pixels':[1,31,641,511],'green_bounds_inclusive':box,'reticle_center':center,
            'review':'Green ring and crosshair centered on the targeted mech torso; no half-position offset.'})
    live={'version':VERSION,'target_alignment':'pass','executable_sha256':digest(exe),
        'emulator':'Private Flycast profile, VGA, 480 / 1x; no texture replacements',
        'boot':'Fresh New Game with blank private VMU; no emulator save states or emulated RAM writes',
        'scenario':'S001 tutorial battle, first player attack completed, enemy attack/counterattack completed, second player target selection reached forecast',
        'Native_1x_font':'pass','runtime_adapters_and_six_pointers_exact':True,
        'texture_error':0,'stock_TA_geometry_units':384176,'RAM_sha256':digest(ram),
        'runtime_probe':str(probe_path.relative_to(ROOT)).replace('\\','/'),
        'english_scenario_member_exact':True,'original_VM_prefix_exact':True,
        'enemy_sprite_anchor_logical':list(anchor),'enemy_aim_logical':[158,98],
        'enemy_aim_physical':expected,'camera':list(struct.unpack_from('<2h',ram,0x1e026e)),
        'captures':captures,
        'user_session':'Read-only inspection of user Flycast 0.7.20; no game input, guest RAM writes, file changes or termination in that instance.',
        'limits':['S001 visual/input coverage only; both attacking sides reviewed',
                  'GPU strip emission is live-tested here; line descriptors additionally have native ABI/source-preservation tests',
                  'Physical Dreamcast, full-game/long-session animation coverage and Stage 6 issue #1 remain pending']}
    print(json.dumps(live,indent=2))
    if not a.write:print('DRY RUN: would save two game crops, copy the supplied report image, and write live/build JSON.');return
    for im,path in images:
        assert not path.exists();im.save(path)
    source=ROOT/'work/ui'/VERSION/'reported-offset.png';assert not source.exists()
    shutil.copyfile('C:/Users/Binh/AppData/Local/Temp/codex-clipboard-5171283e-f970-440b-a858-c9a2cde884d4.png',source)
    for row in captures:row['game_capture_sha256']=digest((ROOT/row['game_capture']).read_bytes())
    (base/'battle-target-live-test.json').write_text(json.dumps(live,indent=2)+'\n','utf-8')
    component['live_validation']='pass: separate live record'
    doc={'version':VERSION,'release':False,'component':component,
         'reported_issue':{'image':str(source.relative_to(ROOT)).replace('\\','/'),
                           'image_sha256':digest(source.read_bytes()),'old_center':[158,98],'correct_center':[316,196]},
         'native':json.loads((base/'battle-target-native-test.json').read_text('utf-8')),'live':live,
         'disc':json.loads((base/'english-disc-report.json').read_text('utf-8'))['validation'],
         'Retro_Trans':json.loads((ROOT/'work/output/release-0.7.21/game-validation.json').read_text('utf-8'))}
    dst=ROOT/'docs/battle-target.json';assert not dst.exists();dst.write_text(json.dumps(doc,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
