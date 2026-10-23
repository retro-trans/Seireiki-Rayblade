"""Verify chapter PRS/PVM data, native selection/submission and calculated fit.

Native GPU rasterization and live appearance remain separate. SDK arithmetic,
memcmp and file-loading/submission endpoints are bounded, recorded fixtures.
"""
import argparse,json,struct
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from build_chapter_cards import ROOT,VERSION,PRIOR,digest
from test_font_patch import CPU
from check_native_text_components import verify
from rayblade_codec import decompress
from build_bitmap_font import ATLAS

BASE=0x8c010000
STOP=0xdead0000


class ChapterCPU(CPU):
    def execute(self,pc,delay=False):
        if pc in (0x8c093930,0x8c093adc):
            divisor=self.reg[0];numerator=self.reg[1];assert divisor in (10,20)
            self.math_calls.append((hex(pc),numerator,divisor))
            self.reg[0]=numerator//divisor if pc==0x8c093930 else numerator%divisor
            return self.pr
        if pc==0x8c021bc4:
            self.loads.append(tuple(self.reg[4:8]));self.reg[0]=1;return self.pr
        if pc in (0x8c0290e0,0x8c0292f4):
            # Both real callees store R7 with MOV.W at entry, discarding
            # carry bits from the caller's 0xffff/0xfffe additions.
            self.sprites.append((hex(pc),*self.reg[4:7],self.reg[7]&65535,self.read(self.reg[15],4),self.read(self.reg[15]+4,4)))
            return self.pr
        if pc==0x8c093f80:
            a,b,n=self.reg[4:7]
            self.reg[0]=int(any(self.read(a+i,1)!=self.read(b+i,1) for i in range(n)))
            return self.pr
        return super().execute(pc,delay)


def fresh(exe,data=b''):
    cpu=ChapterCPU(exe,b'',0,0)
    cpu.regions=[(BASE,bytearray(exe)),(0x8c160000,bytearray(0x20000)),
        (0x8c1d0000,bytearray(0x40000)),(0x8c400000,bytearray(0x10000)),
        (0x8c500000,bytearray(data+b'\0'*64)),(0x8c700000,bytearray(0x1000))]
    cpu.loads=[];cpu.sprites=[];cpu.math_calls=[]
    cpu.write(0x8c169c68,0x8c400000,4)
    return cpu


def run(cpu,start):
    cpu.pc=start
    for steps in range(100000):
        if cpu.pc==STOP:return steps
        try:cpu.pc=cpu.execute(cpu.pc)
        except Exception as e:raise RuntimeError('Chapter native phase at '+hex(cpu.pc)) from e
    raise ValueError('Native chapter instruction limit')


def plane(data,info):
    # Independent scalar deinterleave; does not call the builder's twiddle
    # routine. Original Japanese previews also validate this ordering visually.
    w,h=info['texture_size'];start=info['texture_offset']+16;side=min(w,h)
    out=np.zeros((h,w),np.uint8)
    for y in range(h):
        for x in range(w):
            xx=x%side;yy=y%side;tw=0;bit=0
            while (1<<bit)<side:
                tw|=((yy>>bit)&1)<<(2*bit);tw|=((xx>>bit)&1)<<(2*bit+1);bit+=1
            tw+=(x//side+y//side)*side*side
            out[y,x]=(data[start+tw//2]>>(4*(tw%2)))&15
    return out


def quad(data,info,index):
    return struct.unpack_from('<HHhh6H',data,info['rect_start']+index*20)


def reference_text(text,data,info,bank=0):
    # Build from source-image pixels independently of the production strip
    # renderer, outline filter and nibble encoder.
    atlas=np.asarray(Image.open(ATLAS).convert('L'));pieces=[];total=2
    for char in text:
        if char==' ':pieces.append((None,4));total+=4;continue
        i=ord(char)-32;cell=atlas[(i//32)*24:(i//32+1)*24,(i%32)*12:(i%32+1)*12]
        columns=np.flatnonzero(cell.any(axis=0));assert columns.size
        crop=cell[:,columns[0]:columns[-1]+1];advance=crop.shape[1]+1
        pieces.append((crop,advance));total+=advance
    mask=np.zeros((24,(total+1)//2*2),np.uint8);x=1
    for crop,advance in pieces:
        if crop is not None:mask[:,x:x+crop.shape[1]]=crop
        x+=advance
    padded=np.pad(mask,1,mode='edge')
    expanded=np.maximum.reduce([padded[dy:dy+24,dx:dx+mask.shape[1]] for dy in range(3) for dx in range(3)])
    colors=struct.unpack_from('<16H',data,info['palette_offset']+16+bank*32)
    opaque=[i for i,c in enumerate(colors) if c&32768]
    rgb=[tuple((c>>shift&31)*255//31 for shift in (10,5,0)) for c in colors]
    nearest=lambda grey:min(opaque,key=lambda i:sum((v-grey)**2 for v in rgb[i]))
    expected=np.zeros(mask.shape,np.uint8);expected[expanded>0]=nearest(0)
    for grey in np.unique(mask):
        if grey:expected[mask==grey]=nearest(int(grey))
    return expected


def draw_quad(canvas,data,info,pixels,index,x,y,bank):
    width,height,cx,cy,u0,v0,u1,v1,tex_id,flags=quad(data,info,index)
    w,h=info['texture_size'];left=u0*w//256;top=v0*h//256;right=u1*w//256;bottom=v1*h//256
    assert 0<=left<right<=w and 0<=top<bottom<=h and width and height
    indices=pixels[top:bottom,left:right]
    colors=np.frombuffer(data[info['palette_offset']+16+32*bank:info['palette_offset']+48+32*bank],dtype='<u2')
    values=colors[indices]
    rgba=np.stack([((values>>s&31)*255//31).astype(np.uint8) for s in (10,5,0)]+
        [((values>>15)*255).astype(np.uint8)],axis=2)
    im=Image.fromarray(rgba)
    if im.size!=(width,height):im=im.resize((width,height),Image.Resampling.NEAREST)
    canvas.alpha_composite(im,(x-cx,y-cy))
    return (x-cx,y-cy,x-cx+width,y-cy+height)


def main():
    global VERSION,PRIOR
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.16','0.1.17','0.1.18','0.1.19','0.1.20','0.1.21'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    if VERSION=='0.1.17':PRIOR='0.1.16'
    elif VERSION=='0.1.18':PRIOR='0.1.17'
    elif VERSION=='0.1.19':PRIOR='0.1.18'
    elif VERSION=='0.1.20':PRIOR='0.1.19'
    elif VERSION=='0.1.21':PRIOR='0.1.20'
    print('Plan: five native PRS decodes, 15 PVM chunk lookups, 69 native chapter selections and 99 sprite-submission cases.',flush=True)
    if not args.verify:print('DRY RUN: no native execution/report written');return
    out=ROOT/'work/output'/VERSION;base=ROOT/'work/output'/PRIOR
    exe=(out/'1ST_READ.BIN').read_bytes()
    if VERSION=='0.1.17':
        from build_antialias_font import compose
        files,_,_,_=compose();assert exe==files['1ST_READ.BIN']
    elif VERSION=='0.1.18':
        from build_library_layout_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN']
    elif VERSION=='0.1.19':
        from build_library_header_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN']
    elif VERSION=='0.1.20':
        from build_ui_atlas_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN']
    elif VERSION=='0.1.21':
        from build_embedded_dialogue_patch import compose
        files,_,_=compose();assert exe==files['1ST_READ.BIN']
    else:assert exe==(base/'1ST_READ.BIN').read_bytes()
    archive=(out/'WIN00.AFS').read_bytes();old=(base/'WIN00.AFS').read_bytes()
    component=json.loads((out/'chapter-card-component.json').read_text('utf-8'))
    assert digest(archive)==component['archive_sha256']
    resources={r['member']:r for r in component['resources']};decoded={};pixels={};counts={'PRS':0,'PVM':0,'selection':0,'submission':0}
    native_steps={'PRS':0,'PVM':0,'selection':0,'submission':0}
    for i in range(90):
        off,size=struct.unpack_from('<II',archive,8+8*i);raw=archive[off:off+size]
        old_off,old_size=struct.unpack_from('<II',old,8+8*i)
        if i not in resources:
            if VERSION=='0.1.17' and i==0:
                assert raw==files['WIN00.AFS'][off:off+size];continue
            if VERSION=='0.1.18' and i==52:
                assert raw==files['WIN00.AFS'][off:off+size];continue
            if VERSION=='0.1.20' and i in (2,6,88):
                assert raw==files['WIN00.AFS'][off:off+size];continue
            assert raw==old[old_off:old_off+old_size];continue
        info=resources[i];data,used=decompress(raw);source,source_used=decompress(old[old_off:old_off+old_size])
        assert used==len(raw) and digest(data)==info['decoded_sha256'] and digest(raw)==info['packed_sha256']
        assert len(data)==len(source)==info['decoded_bytes']
        native_steps['PRS']+=verify(exe,raw,data,len(source));counts['PRS']+=1
        decoded[i]=data;pixels[i]=plane(data,info)
        # Real native PVM walker returns each DAT/palette/texture wrapper.
        expected=[0x90,info['palette_offset']-16,info['texture_offset']]
        for sub,wanted in enumerate(expected):
            cpu=fresh(exe,data);cpu.reg[4]=0x8c500000;cpu.reg[5]=0;cpu.reg[6]=sub
            preserved=cpu.reg[8:];native_steps['PVM']+=run(cpu,0x8c022060)
            assert cpu.reg[0]==0x8c500000+wanted and cpu.reg[8:]==preserved
            counts['PVM']+=1
    selections=[]
    for chapter in range(69):
        cpu=fresh(exe);cpu.write(0x8c1df794,chapter,1);cpu.write(0x8c1dbe74,2,4)
        frame=0x8c700500;cpu.reg[15]=frame;cpu.write(frame+12,STOP,4)
        native_steps['selection']+=run(cpu,0x8c02ea2c)
        wanted=(36,40,44,48)[chapter//20]
        assert cpu.loads==[(28,wanted,0,0x8c1f7220)] and cpu.read(0x8c1dbe74,4)==3
        counts['selection']+=1;selections.append({'chapter_index':chapter,'member':wanted})
    cases=[];previews=[]
    for number in range(1,100):
        chapter=(number-1)%69;member=(36,40,44,48)[chapter//20]
        cpu=fresh(exe);cpu.write(0x8c1df794,chapter,1);cpu.write(0x8c1df793,number,1)
        preserved=cpu.reg[8:];native_steps['submission']+=run(cpu,0x8c02ec02)
        assert cpu.reg[8:]==preserved
        assert len(cpu.sprites)==(20 if number<10 else 24)
        title_calls=[r for r in cpu.sprites if r[0]=='0x8c0292f4']
        assert len(title_calls)==8
        main=(chapter%20)*2;reading=main+1
        assert all(r[2:5]==(120,132,0x500+(main if i%2==0 else reading)) for i,r in enumerate(title_calls))
        data=decoded[member];info=resources[member];q=quad(data,info,main)
        left=120-q[2];right=left+q[0];assert (left+right)/2==160 and 8<=left<right<=312
        rq=quad(data,info,reading);w,h=info['texture_size']
        patch=pixels[member][rq[5]*h//256:rq[7]*h//256,rq[4]*w//256:rq[6]*w//256]
        assert patch.size and not patch.any(),'Reading overlay must be transparent'
        header=[r for r in cpu.sprites if r[0]=='0x8c0290e0'][:(3 if number<10 else 4)]
        assert [r[4] for r in header]==([0x406,0x407,0x408+number] if number<10 else [0x406,0x407,0x408+number//10,0x408+number%10])
        hdata=decoded[32];hi=resources[32]
        boxes=[]
        for r in header:
            if r[4]==0x407:continue
            g=quad(hdata,hi,r[4]-0x400);boxes.append((r[2]-g[2],r[2]-g[2]+g[0]))
        assert (min(b[0] for b in boxes)+max(b[1] for b in boxes))/2==160
        assert boxes[0][1]+4==boxes[1][0]
        counts['submission']+=1
        cases.append({'chapter_index':chapter,'episode_number':number,'sprite_calls':len(cpu.sprites),'title_center':160,'episode_center':160})
        if number in (1,10,43,69):
            canvas=Image.new('RGBA',(320,240),'#131b2c')
            for r in header:draw_quad(canvas,hdata,hi,pixels[32],r[4]-0x400,r[2],r[3],4)
            draw_quad(canvas,data,info,pixels[member],main,120,132,0)
            draw=ImageDraw.Draw(canvas);draw.text((8,8),'Offline chapter-card preview',fill='#9ba6ba')
            previews.append((number,canvas))
    # New title artwork is checked against all English links; source palette,
    # container sizes, POF relocations and effect/digit texels stay exact.
    links=json.loads((ROOT/'work/translation/en/ui/chapter-cards.en.json').read_text('utf-8'))['titles']
    assert {r['id']:r['en'] for i in (36,40,44,48) for r in resources[i]['entries']}=={r['id']:r['en'] for r in links}
    for member in (36,40,44,48):
        data=decoded[member];info=resources[member];w,h=info['texture_size']
        for row in info['entries']:
            g=quad(data,info,row['main_rectangle'])
            actual=pixels[member][g[5]*h//256:g[7]*h//256,g[4]*w//256:g[6]*w//256]
            assert np.array_equal(actual,reference_text('"'+row['en']+'"',data,info)),('English title pixels differ',row['id'])
    header_glyph=quad(decoded[32],resources[32],6)
    assert np.array_equal(pixels[32][header_glyph[5]:header_glyph[7],header_glyph[4]:header_glyph[6]],reference_text('Chapter',decoded[32],resources[32],4))
    hsource=(ROOT/'work/source/chapter-cards/S_TITLE0.PVM.dec.bin').read_bytes()
    hinfo=resources[32];original_header=plane(hsource,hinfo)
    assert np.array_equal(original_header[:56],pixels[32][:56])
    assert np.array_equal(original_header[56:80,48:208],pixels[32][56:80,48:208])
    assert not pixels[32][56:80,:48].any()
    proof={'version':VERSION,'executable_sha256':digest(exe),'archive_sha256':digest(archive),
        'component_sha256':digest((out/'chapter-card-component.json').read_bytes()),'title_slots':69,
        'native_cases':counts,'native_instructions':native_steps,'native_selection_cases':selections,'sprite_cases':cases,
        'checks':['All five native PRS decodes match within unchanged original capacities and guards',
            'All 69 complete English title strips and Chapter label match an independent source-bitmap pixel/outline reference',
            'Native PVM walker locates each DAT/palette/texel wrapper','All 69 native resource selections match the English slot mapping',
            'All episode numbers 1..99 and all 69 title indices have native submission witnesses',
            'Calculated sprite anchors center complete English titles and Chapter/number groups at x160',
            'Effect/digit texels and palettes remain original; all reading overlays are transparent; original Japanese episode cells are blank',
            ('84 unrelated non-font archive members remain exact; font checked separately' if VERSION=='0.1.17' else '84 unrelated non-library archive members remain exact; library checked separately' if VERSION=='0.1.18' else '82 unrelated non-UI-texture archive members remain exact; three UI textures checked separately' if VERSION=='0.1.20' else '85 unrelated archive members remain exact')+'; ordered aligned non-overlapping extents and archive length retained'],
        'limits':['SDK quotient/remainder, memcmp, file-loader and sprite-submission endpoints are bounded fixtures',
            'Sprite fit uses decoded rectangle/anchor semantics; the native GPU vertex/raster path is not executed',
            'No live chapter appearance, animation timing or complete game validation is claimed']}
    print(json.dumps({k:v for k,v in proof.items() if k not in ('native_selection_cases','sprite_cases')},indent=2),flush=True)
    if args.write_report:
        (out/'chapter-card-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
        sheet=Image.new('RGBA',(1280,960),'black')
        for j,(number,im) in enumerate(previews):sheet.alpha_composite(im.resize((640,480),Image.Resampling.NEAREST),((j%2)*640,(j//2)*480))
        sheet.save(out/'chapter-card-preview.png')
        manifest=json.loads((out/'font4x-patch.json').read_text('utf-8'))
        manifest['chapter_cards'].update(native_validation='pass; scope and limits in proof',native_proof_sha256=digest((out/'chapter-card-native-test.json').read_bytes()))
        manifest['status']='English chapter cards verified offline; packaging and live chapter check pending'
        (out/'font4x-patch.json').write_text(json.dumps(manifest,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
