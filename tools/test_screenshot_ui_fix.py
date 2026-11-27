"""Native texture acceptance, caption mapping, marker and text regression checks."""
import json
import struct
import numpy as np
from build_screenshot_ui_fix import compose, OUT, ROOT, PRIOR, VERSION, save, member, digest, LEVELS
from test_font_patch import CPU
from check_attack_variant_selection import run, STOP
from test_memory_album_patch import registration
from test_ui_layouts import parse_ui, entry
from build_font4x_patch import MEDIUM
from english_text_codec import decode
from rayblade_codec import decompress
from audit_texture_archive import untwiddle_indices
from test_ordered_archive_layouts import directory_bytes, lookup
from afs_layout import compact_positions


def check():
    files, names, _, _, report, album_raw, win_raw, _, _ = compose()
    exe = files['1ST_READ.BIN']; base = ROOT/'work/output'/PRIOR
    old_exe = (base/'1ST_READ.BIN').read_bytes()
    allowed = set(range(0x4f924,0x4f928)) | set(range(0x4f95a,0x4f95e))
    assert all(i in allowed for i,(a,b) in enumerate(zip(old_exe,exe)) if a != b)
    assert member(files['WIN00.AFS'],0) == member((base/'WIN00.AFS').read_bytes(),0)
    font = member(files['WIN00.AFS'],0)[99072:]
    assert len(font) == 99072
    native = []
    for w,h,expected in ((1024,512,4),(512,512,0)):
        c = CPU(exe,b'',0,0); c.regions.append((0x8c510000,bytearray(128)))
        c.reg[4:8] = [0x8c510020,w,h,0x300]
        steps = run(c,0x8c0e1c4c,STOP,10000)
        assert c.reg[0] == expected
        native.append({'size':[w,h],'status':c.reg[0],'instructions':steps,
                       'interpretation':'rejected' if expected else 'accepted'})
    reg = registration(exe,member(files['ALBUM.AFS'],214),448,35)
    dat = member(files['ALBUM.AFS'],214); start = struct.unpack_from('<I',dat,4)[0]+4
    # Independent VQ unpack and geometric addressing for every caption.
    for page in range(7):
        raw = album_raw[243+page]
        assert struct.unpack_from('<IHH',raw,24) == (0x300,512,512)
        assert decompress(member(files['ALBUM.AFS'],243+page)[16:])[0] == raw
        cb = np.frombuffer(raw[32:2080],'<u2').reshape(256,4)
        indices = np.frombuffer(raw[2080:],np.uint8)[untwiddle_indices(256,256)]
        pixels = np.empty((512,512),'<u2')
        for k,(dx,dy) in enumerate(((0,0),(0,1),(1,0),(1,1))): pixels[dy::2,dx::2] = cb[indices,k]
        for cell in range(32):
            w,h,cx,cy,u,v,u1,v1,t,f = struct.unpack_from('<HHhh6H',dat,start+(224+page*32+cell)*20)
            assert (w,h,cx,cy,t,f) == (64,24,0,-48,28+page,0)
            assert (u1-u,v1-v)==(64,24) and 0<=u<u1<=256 and 0<=v<v1<=256
            assert ((u*2,v*2)==(cell%4*128,cell//4*64))
            assert pixels[v*2:v1*2,u*2:u1*2].shape==(48,128)
    rows = json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))
    old_names = (base/'text/D_NAMES.en.dec.bin').read_bytes(); unchanged=0; widths=[]; max_weapon=0
    for row in rows:
        if row['source_record_kind']=='unused_table_root_sentinel': continue
        key=row['id']
        if key not in report['sort_labels']:
            assert entry(names,key)==entry(old_names,key); unchanged+=1
        else:
            gs,n=parse_ui(exe,font,names,entry(names,key),x=8)
            assert ''.join(g[0] for g in gs)==report['sort_labels'][key]
            width=sum(font[0xa0+MEDIUM.index(ch)] for ch in report['sort_labels'][key])
            assert width <= 48
            widths.append({'id':key,'width':width,'instructions':n})
        if row['group']==4:
            text=decode(entry(names,key))[0]
            width=sum(font[0xa0+MEDIUM.index(ch)] for ch in text)
            max_weapon=max(max_weapon,width)
            assert 40+width<=174, (key,width)
    # Execute actual caller snippets: stack arguments and sprite identity must
    # be correct independent of the old fixed-width result or scroll offset.
    marker_cases=0
    for kind,start_pc,call_pc,x,sprite in [('P',0x4f916,0x4f934,176,46),('W',0x4f94c,0x4f96a,184,45)]:
        for row in range(4):
            for measured in (0,8,102,152,320):
                c=CPU(exe,b'',0,0);sp=c.reg[15]
                c.write(sp,row+7,4);c.write(sp+4,measured,2);c.write(sp+6,7,2)
                c.pc=0x8c010000+start_pc
                for _ in range(80):
                    if c.pc==0x8c010000+call_pc:break
                    c.pc=c.execute(c.pc)
                else:raise AssertionError('Marker caller did not reach draw')
                assert c.read(c.reg[15],4)==x
                assert c.read(c.reg[15]+4,4)==72+16*row
                assert c.reg[6]==sprite and c.reg[5]==3 and c.reg[7]==0
                marker_cases+=1
    directories=[]
    for name in ('ALBUM.AFS','WIN00.AFS'):
        archive=files[name];directory=directory_bytes(name,archive);steps=0
        for r in compact_positions(archive):
            offset,count,n=lookup(exe,name,directory,r['member']);steps+=n
            assert (offset,count)==(r['declared_offset'],r['sectors'])
        directories.append({'file':name,'members':len(compact_positions(archive)),'instructions':steps})
    for n,raw in win_raw.items():assert decompress(member(files['WIN00.AFS'],n)[16:])[0]==raw
    assert decompress(files['D_NAMES.BIN'])[0]==names
    return {'version':VERSION,'executable_sha256':digest(exe),'texture_acceptance':native,
        'caption_registration':reg,'caption_UV_cases':224,'marker_cases':marker_cases,
        'sort_widths':widths,'unchanged_name_rows':unchanged,'maximum_weapon_width':max_weapon,
        'archive_native_lookups':directories,'hardware_runtime_and_font_preserved':True,
        'compressed_resource_roundtrips':10,'limits':['CPU/native loader acceptance and asset/layout tests; live GPU screens and hardware pending.',
        'Hardware ranged-attack animation failure remains unresolved; Flycast reportedly unaffected.']}


if __name__=='__main__':
    result=check();OUT.mkdir(parents=True,exist_ok=True);save(OUT/'screenshot-ui-native-test.json',result)
    print(json.dumps(result,indent=2))
