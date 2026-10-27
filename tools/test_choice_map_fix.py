"""Execute restored choice formatting/parsing and the restricted map draw hook."""
import argparse, json, struct, math
from collections import Counter
import numpy as np
from PIL import Image
from build_choice_map_fix import ROOT, OUT, VERSION, PRIOR, MAP_HOOK, compose, member, digest
from rayblade_codec import decompress
from scenario_word_wrap import tokens
from test_scenario_integration import fresh as story_cpu, install, format_case
from test_inline_controls import execute_stream
from test_native_movie_font import DrawCPU, fresh, run, bits, value, OBJ
from test_map_font_patch import registration, geometry
from test_ui_images import texture_info, scalar_plane
from test_ordered_archive_layouts import directory_bytes, lookup
from afs_layout import compact_positions, require_native_layouts
from analyze_skies_font import read_executable, skies_glyph, EXPECTED_EXE
from build_font4x_patch import MEDIUM


class SnapCPU(DrawCPU):
    def execute(self,pc,delay=False):
        if self.read(pc,2)==0xf03d:
            self.fpul=math.trunc(value(self.fr[0])) & 0xffffffff
            return pc+2
        if pc==0x8c0ab970:
            p=self.reg[4]
            self.observed=(bytes(self.read(p+i,1) for i in range(32)),self.reg[5:7],self.fr[4])
            self.reg[0],self.reg[2]=0x12345678,0x8c5f0040
            return self.pr
        return super().execute(pc,delay)


def map_draw(exe):
    steps=0;cases=0
    for label in (True,False):
        for count in (0,1,2):
            for sprite in (0,16,17,21,26,27,129):
                for x,y in ((0.,0.),(160.25,24.75),(-12.3,-.25)):
                    c=fresh(exe,SnapCPU)
                    # Actual relocated NJTEXLIST shape, with two 12-byte entries.
                    c.write(OBJ+0x2000,OBJ+0x2020,4);c.write(OBJ+0x2004,count,4)
                    c.write(OBJ+0x202c,OBJ+0x2040,4)
                    for i,b in enumerate(b'wmap_en\0' if label else b'other\0\0\0'):c.write(OBJ+0x2040+i,b,1)
                    raw=struct.pack('<5f3I',x,y,-.5,1.,1.,0x1234,OBJ+0x2000,OBJ+0x2100)
                    block=c.regions[3][1];block[0x1000:0x1020]=raw
                    c.reg[4:7]=[OBJ+0x1000,sprite,0x20];depth=c.fr[4]
                    before=bytes(block)
                    steps+=run(c,0x8c07b6e0)
                    expected=bytearray(raw)
                    for at in (0,4,12,16):struct.pack_into('<f',expected,at,struct.unpack_from('<f',expected,at)[0]*2)
                    if label and count==2 and 17<=sprite<27:
                        for at in (0,4):struct.pack_into('<f',expected,at,float(math.trunc(struct.unpack_from('<f',expected,at)[0])))
                    assert c.observed==(bytes(expected),[sprite,0x20],depth),(label,count,sprite,x,y,c.observed)
                    assert bytes(block)==before and c.reg[0]==0x12345678 and c.reg[2]==0x8c5f0040
                    cases+=1
    return {'cases':cases,'instructions':steps,'caller_data_and_ABI':'pass','label_pixel_alignment':'pass',
            'other_sprites':'Scaled exactly as 0.7.5; no snapping'}


def check():
    files,story,component,dat,raw,atlas=compose();exe=files['1ST_READ.BIN']
    for name,data in files.items():assert (OUT/name).read_bytes()==data
    font=member((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes(),0)[:99072]
    old_story=json.loads((ROOT/'work/output'/PRIOR/'text/scenario-component-report.json').read_text('utf-8'))
    old_archive=(ROOT/'work/output'/PRIOR/'D_SCE.AFS').read_bytes()
    c=story_cpu(exe,files['D_SCE.AFS']);steps=Counter();choices=unchanged=0;witness={}
    for m,old in zip(story['members'],old_story['members']):
        at=m['archive_offset'];p,used=decompress(files['D_SCE.AFS'][at+20:at+m['packed_bytes']])
        assert digest(p)==m['decoded_sha256'] and used==m['packed_bytes']-20
        at=old['archive_offset'];before=decompress(old_archive[at+20:at+old['packed_bytes']])[0]
        assert p[:m['original_bytes']]==before[:old['original_bytes']]
        install(c,p,m)
        for r,pr in zip(m['commands'],old['commands']):
            assert r['id']==pr['id'] and (r['source_offset'],r['source_bytes'])==(pr['source_offset'],pr['source_bytes'])
            payload=p[r['english_offset']:r['english_offset']+r['english_bytes']]
            assert digest(payload)==r['english_sha256']
            if not before[r['source_offset']-1]&128:
                assert payload==before[pr['english_offset']:pr['english_offset']+pr['english_bytes']]
                unchanged+=1;continue
            steps['formatter_and_VM']+=format_case(c,p,m,r,native=True,phases=True)[0]
            parsed,n,effects,states=execute_stream(exe,font,payload,r['id']);steps['parser']+=n
            assert not effects and not states
            lines=[[]]
            for t in tokens(payload,font):
                if t['raw']==b'\xfd':lines.append([])
                elif t['kind']=='glyph':lines[-1].append(t['character'])
            actual={}
            for ch,x,y,small in parsed.glyphs:
                assert (y-16)%16==0 and 64<=x<300,(r['id'],ch,x,y,small)
                actual.setdefault((y-16)//16,[]).append(ch)
            assert [''.join(v) for v in lines]==[''.join(actual.get(i,[])) for i in range(len(lines))]
            if r['id']=='scenario.s_003.o0415c':
                witness={'id':r['id'],'options':[''.join(v) for v in lines],
                         'row_y':[16+i*16 for i in range(len(lines))],'glyphs':parsed.glyphs}
                assert witness['options']==['Let them pass','Attack']
            choices+=1
    assert choices==961 and unchanged==49312 and witness
    assert member(files['D_SCE.AFS'],447)==member(old_archive,447)
    # Every archive member must be addressable through the real compact SDK reader.
    for name in ('D_SCE.AFS','WMAP.AFS'):
        directory=directory_bytes(name,files[name])
        for r in compact_positions(files[name]):
            off,size,n=lookup(exe,name,directory,r['member']);steps['archive_lookup']+=n
            assert (off,size)==(r['declared_offset'],r['sectors'])
    original=(ROOT/'work/output'/PRIOR/'WMAP.AFS').read_bytes()
    assert all(member(original,i)==member(files['WMAP.AFS'],i) for i in range(21) if i not in (17,19))
    source_dat=member(original,17);start=4+struct.unpack_from('<I',dat,4)[0]
    label_ids={r['sprite'] for r in component['labels']}
    for i in range(28):
        a,b=source_dat[start+i*20:start+(i+1)*20],dat[start+i*20:start+(i+1)*20]
        assert a[:8]==b[:8] and a[16:]==b[16:]
        if i not in label_ids:assert a==b
    plane=scalar_plane(raw,512,128);assert np.array_equal(plane,atlas)
    skies,_=read_executable();assert digest(skies)==EXPECTED_EXE
    for label in component['labels']:
        w,h=label['draw_size'];coverage=Image.new('L',(sum(font[0xa0+MEDIUM.index(ch)]*2 for ch in label['en'])+32,32));x=0
        for ch in label['en']:
            glyph=skies_glyph(skies,ord(ch),(0,85,187,255));box=glyph.getbbox();left=box[0] if box else 0
            mask=Image.new('L',(16,32));mask.paste(glyph,(2-left,2));coverage.paste(mask,(x,0))
            x+=font[0xa0+MEDIUM.index(ch)]*2
        right=coverage.getbbox()[2]+2;cell=Image.new('L',(w*2,32))
        cell.paste(coverage.crop((0,0,right,32)),((w*2-right)//2,0));ink=np.asarray(cell)
        assert digest(ink.tobytes())==label['coverage_sha256']
        x,y,xx,yy=label['atlas_box'];image=plane[y:yy,x:xx];fg=ink>0
        assert np.array_equal((image[fg]>>12)*17,ink[fg]) and np.all((image[fg]&0xfff)==0xffe)
    reg=registration(exe,dat);geom=geometry(exe,dat)
    steps['texture_format']=texture_info(exe,512,128,0xd02,expected_pixel_bits=2<<27)
    draw=map_draw(exe)
    return {'version':VERSION,'files':component['files'],'choice_commands':choices,
        'unchanged_normal_dialogue_commands':unchanged,'compact_choice_commands':component['compact_choice_commands'],
        'choice_wording_rows_VM_prefixes_and_source_consumption':'pass','native_choice_row_pitch':16,
        'reported_choice':witness,'map_original_glyph_pixels_and_alpha':'all ten exact',
        'unchanged_marker_sprites':18,'unchanged_map_artwork_and_marker_texture_members':19,
        'map_texture_dimensions':[512,128],'map_registration':reg,'map_geometry':geom,
        'map_draw_hook':draw,'SH4_instructions':dict(steps),'archive_layout':require_native_layouts(files),
        'limits':['I/O, GPU and raster endpoints are bounded fixtures; native lookup/formatter/parser/VM/geometry/hook execute',
                  'Live map motion and menu selection require separate inspection','Physical hardware/non-VGA/full-game testing pending']}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-report',action='store_true');a=ap.parse_args()
    result=check()
    print(json.dumps({k:v for k,v in result.items() if k not in ('map_geometry','reported_choice')},indent=2))
    if a.write_report:(OUT/'native-test.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
