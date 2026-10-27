"""Read-only native-font inspection of an explicitly selected Flycast process.

Finds the patched SH-4 routine in emulated RAM, validates the loaded font, and
reports live text surface headers. Never writes process memory or game files.
Use --inspect after reviewing the default dry run. Windows 64-bit only.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import struct
import re
from pathlib import Path
from array import array
from build_font4x_patch import ROOT,VERSION,START,END


class Region(C.Structure):
    _fields_=[('base',C.c_void_p),('allocation',C.c_void_p),('allocation_protect',W.DWORD),
              ('partition',W.WORD),('size',C.c_size_t),('state',W.DWORD),('protect',W.DWORD),('kind',W.DWORD)]


def main():
    global VERSION
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid',required=True,type=int);ap.add_argument('--inspect',action='store_true')
    ap.add_argument('--exe-path',type=Path,default=Path(r'M:\Program\FlyCast\flycast.exe'),
                    help='Exact executable path of an isolated Flycast profile, if used')
    ap.add_argument('--report',type=Path,help='Optional local JSON evidence report; only written with --inspect')
    ap.add_argument('--capture-dir',type=Path,help='Optional CPU text-surface PNGs; only written with --inspect')
    ap.add_argument('--dump-game-ram',type=Path,help='Optional 16 MiB emulated game RAM evidence, only after verified kernel/font identification; use ignored work/source/')
    ap.add_argument('--version',default=VERSION,help='Component build to compare, e.g. 0.1.4')
    ap.add_argument('--component-dir',type=Path,help='Explicit local candidate components, instead of work/output/<version>')
    args=ap.parse_args()
    if not re.fullmatch(r'0\.\d+\.\d+',args.version):raise ValueError('Expected a 0.x.y component version')
    VERSION=args.version
    component_dir=args.component_dir or ROOT/'work/output'/VERSION
    print('Inspect only PID {}: locate HD font kernel and read emulated font/surface headers.'.format(args.pid))
    if args.report:print('Evidence report destination:',args.report)
    if args.capture_dir:print('CPU text-surface capture destination:',args.capture_dir)
    if args.dump_game_ram:
        resolved=args.dump_game_ram.resolve()
        assert resolved.is_relative_to((ROOT/'work/source').resolve()), 'RAM evidence must stay in ignored local source files'
        print('Emulated game RAM evidence destination:',args.dump_game_ram)
    if not args.inspect:print('DRY RUN: process not opened');return
    api=C.WinDLL('kernel32',use_last_error=True)
    api.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];api.OpenProcess.restype=W.HANDLE
    api.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    api.VirtualQueryEx.argtypes=[W.HANDLE,C.c_void_p,C.POINTER(Region),C.c_size_t];api.VirtualQueryEx.restype=C.c_size_t
    api.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
    handle=api.OpenProcess(0x410,False,args.pid)
    if not handle:raise OSError(C.get_last_error(),'Cannot open selected process read-only')
    def read(address,size):
        buf=C.create_string_buffer(size);used=C.c_size_t()
        if not api.ReadProcessMemory(handle,C.c_void_p(address),buf,size,C.byref(used)) or used.value!=size:
            raise OSError('Cannot read selected memory region')
        return buf.raw
    try:
        path=C.create_unicode_buffer(32768);length=W.DWORD(len(path))
        if not api.QueryFullProcessImageNameW(handle,0,path,C.byref(length)):raise OSError('Cannot verify executable path')
        if Path(path.value).resolve()!=args.exe_path.resolve():raise ValueError('Selected PID is not the explicitly selected Flycast executable')
        target=(component_dir/'1ST_READ.BIN').read_bytes()[START:END]
        mutable=None
        for filename in ('font-mode-details.json','font-mode-component.json'):
            component_path=component_dir/filename
            if component_path.exists():
                component=json.loads(component_path.read_text('utf-8'))
                if 'mode_address' in component:
                    mutable=int(component['mode_address'],16)-0x8c010000-START
                    assert 0<=mutable<=len(target)-32
                    break
        def kernel_matches(actual):
            if mutable is None:return actual==target
            return actual[:mutable]==target[:mutable] and actual[mutable+32:]==target[mutable+32:]
        expected_afs=(component_dir/'WIN00.AFS').read_bytes()
        off,size=struct.unpack_from('<II',expected_afs,8)
        expected_magic=expected_afs[off:off+8]
        if expected_magic not in (b'RBLF4X\x00\x01',b'RBLF4X\x00\x02',b'RBLF4X\x00\x03',b'RBLF4X\x00\x04'):
            raise ValueError('Unexpected integrated font member format')
        ram=None;address=0;matches=[]
        while address<0x7fffffffffff:
            r=Region()
            if not api.VirtualQueryEx(handle,C.c_void_p(address),C.byref(r),C.sizeof(r)):break
            base=r.base or 0;address=base+r.size
            if r.state!=0x1000 or r.protect&0x101 or r.kind==0x1000000 or not 8*1024*1024<=r.size<=256*1024*1024:continue
            try:data=read(base,r.size)
            except OSError:continue
            start=0
            while True:
                match=data.find(target[:64],start)
                if match<0:break
                start=match+2;candidate=base+match-0x10000-START
                try:
                    actual=read(candidate+0x10000+START,len(target))
                    if not kernel_matches(actual):continue
                    matches.append(candidate)
                    ptr=struct.unpack('<I',read(candidate+0x1f36a4,4))[0]
                    if not 0x8c000000<=ptr<0x8d000000:continue
                    magic=read(candidate+ptr-0x8c000000,8)
                    if magic!=expected_magic:continue
                    ram=candidate;break
                except OSError:continue
            if ram is not None:break
        if ram is None:
            report={'build_compared':VERSION,'pid':args.pid,'kernel_copies_found':len(matches),'font_loaded':False,
                    'runtime_status':'HD font not initialized or emulated RAM not identified',
                    'scope':'No loaded kernel identified; does not establish the currently selected disc or a successful game boot'}
            print(json.dumps(report))
            if args.report:
                args.report.parent.mkdir(parents=True,exist_ok=True)
                args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            return
        def game(addr,size):return read(ram+(addr&0xffffff),size)
        if args.dump_game_ram:
            if args.dump_game_ram.exists():raise ValueError('Refusing to overwrite existing game RAM evidence')
            payload=read(ram,0x1000000)
            args.dump_game_ram.parent.mkdir(parents=True,exist_ok=True)
            args.dump_game_ram.write_bytes(payload)
        font_ptr=struct.unpack('<I',game(0x8c1f36a4,4))[0]
        font_matches=game(font_ptr,size)==expected_afs[off:off+size]
        names_check=None
        english_names=component_dir/'text/D_NAMES.en.dec.bin'
        if english_names.exists():
            expected_names=english_names.read_bytes()
            bank0=int.from_bytes(game(0x8c1dbef4,4),'little')
            root0=int.from_bytes(expected_names[:4],'little')
            names_base=bank0-root0
            valid=0x8c000000<=names_base and names_base+len(expected_names)<=0x8d000000
            names_check={'group0_pointer':hex(bank0),'inferred_component_base':hex(names_base),
                         'decoded_size':len(expected_names),
                         'entire_component_matches':valid and game(names_base,len(expected_names))==expected_names}
        library_check=None
        library_patch=component_dir/'library-patch-report.json'
        if library_patch.exists():
            patch=json.loads(library_patch.read_text())
            shared=int.from_bytes(game(0x8c1dbf4c,4),'little')
            expected_library=(component_dir/'text/D_PAPER.en.dec.bin').read_bytes()
            library_base=shared+patch['library_destination_offset']
            valid=0x8c000000<=shared and library_base+len(expected_library)<=0x8d000000
            literal=int.from_bytes(game(0x8c0204b4,4),'little')
            library_check={'shared_pointer':hex(shared),'library_destination':hex(library_base),
                'loaded_allocation_literal':literal,'allocation_literal_matches':literal==patch['shared_allocation_bytes'],
                'entire_library_matches':valid and game(library_base,len(expected_library))==expected_library,
                'note':'The shared buffer is reused; the library payload only matches while the profile UI has loaded it.'}
        scenario_check=None
        scenario_report=component_dir/'text/scenario-component-report.json'
        if scenario_report.exists():
            component=json.loads(scenario_report.read_text('utf-8'))
            heap=int.from_bytes(game(0x8c0183f0,4),'little')
            original_base=int.from_bytes(game(0x8c1dbf50,4),'little')
            valid=0x8c000000<=heap and heap+component['script_capacity']+component['scratch_capacity']<=0x8d000000
            scenario_check={'english_heap_pointer':hex(heap),'heap_in_RAM':valid,
                'original_script_base':hex(original_base),'original_base_preserved':original_base==0x8c010080,
                'VM_pointer':hex(int.from_bytes(game(0x8c1dbe24,4),'little')),
                'member_loaded':False,'note':'A member can be checked after the game actually loads a scenario.'}
            hook_report=component_dir/'scenario-patch-report.json'
            if hook_report.exists():
                hooks=json.loads(hook_report.read_text('utf-8'))
                executable=(component_dir/'1ST_READ.BIN').read_bytes()
                checks=[]
                for edit in hooks.get('edits',[]):
                    if 'code_bytes' not in edit:continue
                    offset=int(edit['offset'],16);length=edit['code_bytes']
                    checks.append({'address':hex(0x8c010000+offset),'bytes':length,
                        'matches':game(0x8c010000+offset,length)==executable[offset:offset+length]})
                if checks:scenario_check['native_hook_checks']=checks
            if valid:
                bank=int.from_bytes(game(heap+component['bank_pointer_offset'],4),'little')
                scenario_check['bank_pointer']=hex(bank)
                if heap<=bank and bank+32<=heap+component['script_capacity']:
                    header=game(bank,32)
                    if header[:8] in (b'RBSCEN01',b'RBSCEN02'):
                        original_size,commands,total,index,entry_bytes,_=struct.unpack_from('<6I',header,8)
                        expected=next((m for m in component['members'] if m['index']==index),None)
                        if expected is not None and total==expected['decoded_bytes'] and total<=component['script_capacity']:
                            raw=game(heap,total)
                            scenario_check.update(member_loaded=True,member=expected['name'],english_commands=commands,
                                bank_entry_bytes=entry_bytes,entire_English_member_matches=hashlib.sha256(raw).hexdigest()==expected['decoded_sha256'],
                                original_VM_prefix_matches=hashlib.sha256(game(original_base,original_size)).hexdigest()==expected['original_sha256'])
                            if header[:8]==b'RBSCEN02':
                                flags=[struct.unpack_from('<I',game(bank+32+8*i+4,4))[0]>>31 for i in range(commands)]
                                scenario_check.update(word_wrapped_commands_in_bank=sum(flags),special_control_commands_in_bank=commands-sum(flags))
        surfaces=[]
        for slot in range(48):
            context=game(0x8c1f0cf8+92*slot,92)
            ptr=struct.unpack_from('<I',context,0x44)[0]
            if not ptr:continue
            header=game(ptr,32);width,height=struct.unpack_from('<HH',header,28)
            logical=struct.unpack_from('<HH',context,0x4e)
            if not 0<width<=1024 or not 0<height<=1024:raise ValueError('Invalid live texture dimensions')
            ex,ey=header[12:14];sx,sy=1<<ex,1<<ey
            if (width,height)!=(logical[0]*sx,logical[1]*sy):raise ValueError('Live physical/logical size mismatch')
            payload=game(ptr+32,width*height*2);pixels=array('H',payload)
            pixel_format=header[24]
            if pixel_format not in (0,2):raise ValueError('Unsupported live text pixel format')
            foreground=[bool(v&(0xfff if pixel_format==2 else 0x7fff)) for v in pixels]
            mixed=0
            for ly in range(logical[1]):
                for lx in range(logical[0]):
                    count=sum(foreground[(ly*sy+y)*width+lx*sx+x] for y in range(sy) for x in range(sx))
                    mixed+=0<count<sx*sy
            xs=[i%width for i,v in enumerate(foreground) if v]
            ys=[i//width for i,v in enumerate(foreground) if v]
            bbox=[min(xs),min(ys),max(xs)+1,max(ys)+1] if xs else None
            sprite_size=struct.unpack('<HH',game(0x8c1f2f20+slot*20,4))
            row={'slot':slot,'logical':logical,'physical':[width,height],
                'scale_exponents':list(header[12:14]),'bytes':struct.unpack_from('<I',header,20)[0],
                'pvr_header_valid':header[:4]==b'GBIX' and header[16:20]==b'PVRT',
                'sprite_size':sprite_size,'sprite_preserves_logical_size':sprite_size==logical,
                'foreground_pixels':sum(foreground),'foreground_bounds':bbox,
                'mixed_subpixel_cells':mixed,
                'pixel_format':'ARGB4444' if pixel_format==2 else 'ARGB1555',
                'partial_alpha_pixels':sum(0<(v>>12)<15 for v in pixels) if pixel_format==2 else 0,
                'payload_sha256':hashlib.sha256(payload).hexdigest()}
            if args.capture_dir:
                from PIL import Image
                rgba=bytearray()
                for value in pixels:
                    if pixel_format==2:
                        rgba.extend((((value>>8)&15)*17,((value>>4)&15)*17,(value&15)*17,((value>>12)&15)*17))
                    else:
                        r=(value>>10)&31;g=(value>>5)&31;b=value&31
                        rgba.extend(((r<<3)|(r>>2),(g<<3)|(g>>2),(b<<3)|(b>>2),255 if value&0x8000 else 0))
                args.capture_dir.mkdir(parents=True,exist_ok=True)
                file=args.capture_dir/('slot-{:02d}-{}x{}.png'.format(slot,width,height))
                Image.frombytes('RGBA',(width,height),bytes(rgba)).save(file)
                row['capture']=str(file)
            surfaces.append(row)
        report={'build':VERSION,'kernel_matches':True,'font_payload_matches':font_matches,
                'kernel_sha256':hashlib.sha256(target).hexdigest(),'english_names':names_check,'english_library':library_check,
                'english_scenario':scenario_check,'surfaces':surfaces,
                'visual_validation':'requires separate manual screenshot assessment; surface data alone is not a visual check'}
        if mutable is not None:
            state=game(0x8c010000+START+mutable,32)
            report['font_modes']={'selected':'native' if state[0]==0 else 'HD',
                'selector_active':bool(state[1]),'mutable_state_bytes':32,
                'kernel_comparison':'All executable code and constant bytes exact; declared mutable state excluded'}
        print(json.dumps(report,indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:
        api.CloseHandle.argtypes=[W.HANDLE];api.CloseHandle(handle)


if __name__=='__main__':main()
