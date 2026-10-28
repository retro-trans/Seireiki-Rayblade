"""Prepare an isolated Stage 6 replay from issue #1's VMU. Dry first."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--version',default='0.7.21');ap.add_argument('--label',default='baseline');ap.add_argument('--write',action='store_true');ap.add_argument('--auto-next',action='store_true');a=ap.parse_args()
    src=ROOT/'work/output/target-investigation/runtime-0721'
    dst=ROOT/'work/output/issue-1'/('runtime-'+a.version+'-'+a.label)
    with zipfile.ZipFile(ROOT/'incoming/issue-1/stage6-vmu.zip') as z:
        assert len(z.infolist())==1 and z.infolist()[0].file_size==131072
        save=z.read(z.namelist()[0])
    lua=(src/'flycast.lua').read_text('utf-8')
    lua=lua.replace('for _,step in ipairs({{30,16}}) do','for _,step in ipairs({}) do')
    if a.auto_next:
        lua='local stage_load_seen=nil\n'+lua
        lua=lua.replace(' flycast.input.releaseButtons(1,0xffff)', ''' if pc==0x8c01bed5 and not stage_load_seen then stage_load_seen=frame end
 if stage_load_seen and frame<stage_load_seen+300 then
  buttons=0
  for _,step in ipairs({{30,4,16},{210,16,16},{270,4,16}}) do
   local elapsed=frame-stage_load_seen
   if elapsed>=step[1] and elapsed<step[1]+step[3] then buttons=step[2] end
  end
 end
 flycast.input.releaseButtons(1,0xffff)''')
    print(json.dumps({'profile':str(dst),'version':a.version,'VMU_sha256':hashlib.sha256(save).hexdigest(),'save':'Issue #1 Stage 6 intermission, File 1','writes':'Only a new private test profile; original user VMU and running emulator untouched'},indent=2))
    if not a.write:print('DRY RUN: copy local emulator/config, supplied VMU and read-only telemetry/controller driver.');return
    assert not dst.exists();dst.mkdir(parents=True);(dst/'data').mkdir()
    for name in ('flycast.exe','emu.cfg'):shutil.copyfile(src/name,dst/name)
    for name in ('dc_nvmem.bin','vmu_save_A2.bin'):shutil.copyfile(src/'data'/name,dst/'data'/name)
    (dst/'data/T42201M_vmu_save_A1.bin').write_bytes(save)
    (dst/'flycast.lua').write_text(lua,'utf-8');(dst/'advance.txt').write_text('1');(dst/'control.txt').write_text('0,0,0');(dst/'pause-at.txt').write_text('8c0108ec' if a.auto_next else '8c01bed5')
    (dst/'profile-source.json').write_text(json.dumps({'version':a.version,'VMU_sha256':hashlib.sha256(save).hexdigest(),'save_source':'incoming/issue-1/stage6-vmu.zip','driver':'Supported controller input and read-only telemetry only'},indent=2)+'\n','utf-8')

if __name__=='__main__':main()
