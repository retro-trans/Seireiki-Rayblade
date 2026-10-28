"""Execute range-fill construction against read-only captured battle RAM."""
import argparse,json,struct
from build_battle_grid_fix import compose,VERSION,PRIOR,ROOT,ENTRY,DRAW,POINTER,digest
from test_native_movie_font import DrawCPU,bits,value,STOP,run

RAM=ROOT/'work/source/runtime/cursor-user-0719.ram'


class GridCPU(DrawCPU):
    def execute(self,pc,delay=False):
        w=self.read(pc,2);n=w>>8&15;m=w>>4&15
        if w&0xf0ff in (0xf08d,0xf09d):self.fr[n]=bits(float(w&255==0x9d));return pc+2
        if w&0xf0ff==0xf00d:self.fr[n]=self.fpul;return pc+2
        if w&0xf0ff==0xf04d:self.fr[n]^=0x80000000;return pc+2
        if w&0xf00f==0xf001:self.fr[n]=bits(value(self.fr[n])-value(self.fr[m]));return pc+2
        if pc==DRAW:
            p=self.reg[4];vertices=self.read(p+12,4)*self.reg[5]
            self.draws.append({'flags':self.reg[6],'polygons':self.reg[5],'vertices_per_polygon':self.read(p+12,4),
                'points':[value(self.read(self.read(p,4)+i*4,4)) for i in range(vertices*2)],
                'descriptor_tail':[self.read(p+i,4) for i in (4,8,12)],'priority_bits':self.fr[4]})
            return self.pr
        return super().execute(pc,delay)


def fresh(exe,ram):
    c=GridCPU(exe,b'',0,0);c.regions=[(0x8c000000,bytearray(ram))]
    c.regions[0][1][0x10000:0x10000+len(exe)]=exe
    c.reg[15]=0x8cffe000;c.pr=STOP;c.fr=[bits(i+.25) for i in range(16)];c.fpul=0;c.visited=set();c.draws=[]
    return c


def check():
    exe,component=compose();old=(ROOT/'work/output'/PRIOR/'1ST_READ.BIN').read_bytes();ram=RAM.read_bytes();steps=0;rows=[]
    # Exercise actual game bit-field queries, elevation, range mask iteration,
    # camera offsets, triangle construction and final patched call site.
    for dx,dy in ((0,0),(48,24),(-96,-48),(19,-7)):
        outputs=[]
        for image in (old,exe):
            c=fresh(image,ram);x,y=struct.unpack_from('<2h',ram,0x1e026e);c.reg[4:6]=[(x+dx)&0xffffffff,(y+dy)&0xffffffff]
            before=bytes(c.regions[0][1][0x1e0230:0x1e0680]);steps+=run(c,0x8c045c38,1000000)
            assert bytes(c.regions[0][1][0x1e0230:0x1e0680])==before
            outputs.append(c.draws)
        a,b=outputs;assert len(a)==len(b)==41
        for first,last in zip(a,b):
            assert last=={**first,'points':[v*2 for v in first['points']]}
        rows.append({'camera_offset':[dx,dy],'filled_tiles':len(a),'vertices':sum(x['polygons']*x['vertices_per_polygon'] for x in a),'all_xy_exactly_doubled':True})
    # Verify the adapter independently: source arrays and descriptors, including
    # aliased XY arrays, stay unchanged; zero work does not loop indefinitely.
    fixtures=0
    for polygons,verts in ((0,3),(1,3),(4,3),(2,4),(1,16)):
        c=fresh(exe,ram);p=0x8cf00000;q=p+32;count=polygons*verts
        raw=struct.pack('<4I',q,q+0x1000,q+0x2000,verts);c.regions[0][1][p&0xffffff:(p&0xffffff)+16]=raw
        points=[float(i-7)*.25 for i in range(count*2)]
        c.regions[0][1][q&0xffffff:(q&0xffffff)+len(points)*4]=struct.pack('<'+'f'*len(points),*points)
        c.reg[4:7]=[p,polygons,0x60];before=bytes(c.regions[0][1][p&0xffffff:(p&0xffffff)+0x3000]);steps+=run(c,ENTRY)
        assert before==bytes(c.regions[0][1][p&0xffffff:(p&0xffffff)+0x3000])
        assert c.draws[0]['points']==[v*2 for v in points] and c.draws[0]['polygons']==polygons
        fixtures+=1
    x,y=struct.unpack_from('<2B',ram,0x1dc14d);camx,camy=struct.unpack_from('<2h',ram,0x1e026e)
    center=[48*x+48+camx,24*y+32+camy]
    assert center==[160,120]
    return {**component,'RAM_sha256':digest(ram),'scenario':'S001 first battle, captured from user Flycast 0.7.19',
        'actual_game_fill_cases':rows,'adapter_fixtures':fixtures,'SH4_instructions':steps,
        'selected_unit_tile':[x,y],'range_center_before_pixels':center,'range_center_after_pixels':[v*2 for v in center],
        'selection_arrow_center_pixels':[320,240],'logical_unit_anchor':[158,122],
        'ABI_source_geometry_and_range_mask_preserved':'pass',
        'scope':'Actual game fill and 2x adapter execute; SDK renderer endpoint records arguments. GPU appearance needs separate live validation.'}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    proof=check();print(json.dumps(proof,indent=2))
    if a.write:(ROOT/'work/output'/VERSION/'battle-grid-native-test.json').write_text(json.dumps(proof,indent=2)+'\n','utf-8')
