"""Prepare private chapter-transition testing with accurate framebuffer paths. Dry first."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    template = ROOT / 'work/output/issue-1/runtime-0.7.23-battle-final'
    source = Path('M:/Program/FlyCast/data/T42201M_vmu_save_A1.bin')
    output = ROOT / 'work/output/hardware-transition/runtime-0.7.23-framebuffer'
    card = source.read_bytes(); assert len(card) == 131072
    changes = {'rend.EmulateFramebuffer': 'yes', 'rend.RenderToTextureBuffer': 'yes',
               'Dynarec.Enabled': 'no', 'FastGDRomLoad': 'no', 'Dreamcast.Cable': '0'}
    print(json.dumps({'version': '0.7.23', 'profile': str(output), 'VMU_source': str(source),
        'VMU_sha256': hashlib.sha256(card).hexdigest(), 'private_settings': changes,
        'controller': 'Manual input only; Lua reads telemetry and sends no input.'}, indent=2))
    if not a.write:
        print('DRY RUN: create a new isolated emulator profile; running Flycast and original VMU untouched.'); return
    assert not output.exists()
    output.mkdir(parents=True); (output / 'data').mkdir()
    shutil.copyfile(template / 'flycast.exe', output / 'flycast.exe')
    text = (template / 'emu.cfg').read_text(encoding='utf-8')
    for key, value in changes.items():
        lines = [line for line in text.splitlines() if line.startswith(key + ' = ')]
        assert len(lines) == 1, key
        text = text.replace(lines[0], key + ' = ' + value)
    (output / 'emu.cfg').write_text(text, encoding='utf-8')
    for name in ('dc_nvmem.bin', 'vmu_save_A2.bin'):
        shutil.copyfile(template / 'data' / name, output / 'data' / name)
    (output / 'data/T42201M_vmu_save_A1.bin').write_bytes(card)
    (output / 'flycast.lua').write_text('''local frame=0
local out=assert(io.open('transition.csv','w'))
flycast_callbacks={vblank=function()
 frame=frame+1
 if frame%60~=0 then return end
 local m=flycast.memory
 out:write(string.format('%d,VM=%08x,texture_error=%d',frame,m.read32(0x8c1dbe24),m.read32(0x8c419530)))
 for _,addr in ipairs({0xa05f8044,0xa05f805c,0xa05f8050,0xa05f8020,0xa05f8124,0xa05f8128,0xa05f6900,0x8c4621a4,0x8c4621b0}) do
  out:write(string.format(',%08x=%08x',addr,m.read32(addr)))
 end
 out:write('\\n');out:flush()
end}
''', encoding='utf-8')
    (output / 'profile-source.json').write_text(json.dumps({'version': '0.7.23',
        'source_VMU_sha256': hashlib.sha256(card).hexdigest(), 'settings': changes,
        'scope': 'Diagnostic Flycast approximation only; real Dreamcast confirmation still required.'}, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
