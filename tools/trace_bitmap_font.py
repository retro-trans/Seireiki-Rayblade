"""Infer smooth outlines from the supplied coverage bitmap. Dry run first.

Marching-square contours plus uniform corner cutting, then supersampled area
rasterization. Inferred geometry, not recovery of the original vector font.
Existing native format/spacing/baseline and small/protected glyphs retained.
"""
import argparse
from collections import defaultdict
import json
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

from build_antialias_font import LEVELS, font_bytes
from build_bitmap_font import ROOT, ATLAS, digest
from build_font4x_patch import MEDIUM
from build_genei_font import MEDIUM_DATA
from preview_font_sampling import packed_mask

sys.path.insert(0,str(ROOT/'work/vendor/opencv5'))
import cv2

OUT = ROOT/'work/output/font-outline-draft-01'
PRIOR = '0.1.30'


def contours(cell, threshold=.5):
    a = np.pad(np.asarray(cell,dtype=float)/255,2)
    graph, points = defaultdict(list), {}
    pairs = {1:[(3,0)],2:[(0,1)],3:[(3,1)],4:[(1,2)],6:[(0,2)],7:[(3,2)],
             8:[(2,3)],9:[(0,2)],11:[(1,2)],12:[(3,1)],13:[(0,1)],14:[(3,0)]}
    for y in range(a.shape[0]-1):
        for x in range(a.shape[1]-1):
            values = [a[y,x],a[y,x+1],a[y+1,x+1],a[y+1,x]]
            code = sum((v>=threshold)<<i for i,v in enumerate(values))
            if code in (0,15):
                continue
            edge_pairs = pairs.get(code)
            if code in (5,10):
                high = sum(values)/4 >= threshold
                edge_pairs = [(0,1),(2,3)] if (code==5)==high else [(3,0),(1,2)]
            edges = [('h',y,x),('v',y,x+1),('h',y+1,x),('v',y,x)]
            for left,right in edge_pairs:
                p,q = edges[left],edges[right]
                graph[p].append(q)
                graph[q].append(p)
                for key in (p,q):
                    if key not in points:
                        axis,yy,xx = key
                        v0 = a[yy,xx]
                        v1 = a[yy,xx+1] if axis=='h' else a[yy+1,xx]
                        t = (threshold-v0)/(v1-v0)
                        points[key] = [xx-1.5+(t if axis=='h' else 0),yy-1.5+(t if axis=='v' else 0)]
    assert all(len(v)==2 for v in graph.values())
    result, visited = [],set()
    for start in graph:
        if start in visited:
            continue
        loop, previous, current = [],None,start
        while current not in visited:
            visited.add(current)
            loop.append(points[current])
            nxt = next(v for v in graph[current] if v != previous)
            previous,current = current,nxt
        assert current == start and len(loop)>=3
        result.append(loop)
    return result


def smooth(loop):
    points = np.asarray(loop,dtype=float)
    for _ in range(2):
        other = np.roll(points,-1,axis=0)
        # One shared geometric rule for every letter; no individual scaling.
        q,r = .8*points+.2*other,.2*points+.8*other
        points = np.stack([q,r],axis=1).reshape(-1,2)
    return points.tolist()


def raster(loops,left,scale=2):
    supersample = 16
    plane = np.zeros((64*supersample,64*supersample),bool)
    for loop in loops:
        im = Image.new('1',(64*supersample,64*supersample))
        xy = [(round((4+(x-left)*scale)*supersample-.5),round((4+y*scale)*supersample-.5)) for x,y in loop]
        ImageDraw.Draw(im).polygon(xy,fill=1)
        plane ^= np.asarray(im)
    # All contours use even/odd filling, retaining holes regardless of winding.
    samples = plane.reshape(64,supersample,64,supersample).sum(axis=(1,3))
    coverage = ((samples*255+supersample**2//2)//supersample**2).astype(np.uint8)
    lookup = np.array([min(LEVELS,key=lambda a:abs(a-i)) for i in range(256)],np.uint8)
    return Image.fromarray(lookup[coverage])


def topology(mask):
    a = (np.asarray(mask)>=128).astype(np.uint8)
    components = cv2.connectedComponents(a,connectivity=8)[0]-1
    _,hierarchy = cv2.findContours(a,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    holes = 0 if hierarchy is None else sum(row[3]>=0 for row in hierarchy[0])
    return [components,int(holes)]


def compose():
    source = Image.open(ATLAS).convert('L')
    archive = (ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes()
    offset,old = font_bytes(archive)
    assert old[:8] == b'RBLF4X\0\4'
    target = bytearray(old)
    records,masks = [],{}
    for char in (chr(i) for i in range(32,127)):
        code = ord(char)-32
        cell = source.crop((code%32*12,code//32*24,code%32*12+12,code//32*24+24))
        bounds = cell.point(lambda v:255 if v>=128 else 0).getbbox()
        left = bounds[0] if bounds else 0
        raw = contours(cell)
        loops = [smooth(loop) for loop in raw]
        mask = raster(loops,left)
        assert not mask.crop((32,0,64,64)).getbbox()
        i = MEDIUM.index(char)
        for y in range(64):
            words = [sum(LEVELS.index(mask.getpixel((half*16+x,y)))<<(30-2*x) for x in range(16)) for half in range(2)]
            struct.pack_into('<2I',target,MEDIUM_DATA+i*512+y*8,*words)
        assert packed_mask(target,char).tobytes() == mask.tobytes()
        old_mask = packed_mask(old,char)
        record = {'character':char,'glyph_id':i,'advance':old[0xa0+i],'source_binary_left':left,
                  'source_topology':topology(cell),'candidate_topology':topology(mask),
                  'source_coverage_sum':sum(cell.tobytes()),'candidate_coverage_sum_at_source_scale':sum(mask.tobytes())/4,
                  'old_mask_bounds':list(old_mask.getbbox()) if old_mask.getbbox() else None,
                  'new_mask_bounds':list(mask.getbbox()) if mask.getbbox() else None,
                  'mask_sha256':digest(mask.tobytes()),'inferred_contours':loops}
        records.append(record)
        masks[char] = mask
    allowed = {p for row in records for p in range(MEDIUM_DATA+row['glyph_id']*512,MEDIUM_DATA+(row['glyph_id']+1)*512)}
    changed = {i for i,(a,b) in enumerate(zip(old,target)) if a!=b}
    assert changed<=allowed and target[:MEDIUM_DATA] == old[:MEDIUM_DATA]
    assert target[0x20:0x120] == old[0x20:0x120]
    afs = archive[:offset]+target+archive[offset+len(target):]
    report = {'source_build':PRIOR,'status':'Inferred-outline font candidate; not installed or packaged',
              'source_atlas_sha256':digest(ATLAS.read_bytes()),'source_font_sha256':digest(old),
              'target_font_sha256':digest(target),'source_archive_sha256':digest(archive),'target_archive_sha256':digest(afs),
              'method':'AA-assisted marching squares at 0.5, two uniform 0.2 corner-cutting passes, 16x supersampled contour coverage, four stored alpha levels',
              'glyph_count':95,'changed_font_bytes':len(changed),
              'unchanged':'Executable, advances, baseline origin, small bank, five protected symbols, other WIN00 members and translations',
              'topology_changes':[r['character'] for r in records if r['source_topology']!=r['candidate_topology']],
              'limits':['Inferred contours, not the original font vectors; shape fidelity needs visual review',
                        'The current native format still stores only four alpha levels',
                        'Matched offline sizes are not a live game/GPU or Skies of Arcadia comparison'],
              'glyphs':records}
    return bytes(afs),report,masks,bytes(old),bytes(target)


def comparison(old,new):
    sheet = Image.new('RGB',(1060,690),'#171b24')
    d = ImageDraw.Draw(sheet)
    d.text((12,8),'Inferred contours - same source style, advances/baseline - offline, not a game capture',fill='white')
    d.text((12,29),'Current repeated bitmap samples',fill='#c6ccd6')
    d.text((542,29),'Contour rasterization (same four alpha levels)',fill='#c6ccd6')
    for top,scale in ((58,.5),(230,1),(414,2)):
        d.text((12,top),f'Same output scale: {scale:g}x stored pixels',fill='#c6ccd6')
        for x,font in ((12,old),(542,new)):
            line = Image.new('L',(1024,64))
            pen = 0
            for char in 'r O o R 0 - Morning, Touya!':
                line.paste(packed_mask(font,char),(pen,0))
                pen += font[0xa0+MEDIUM.index(char)]*4
            line = line.crop((0,0,pen+8,64))
            display = line.resize((round(line.width*scale),round(line.height*scale)),Image.Resampling.NEAREST)
            display = display.crop((0,0,min(display.width,510),display.height))
            sheet.paste('white',(x,top+24,x+display.width,top+24+display.height),display)
    d.text((12,663),'Uniform inferred contour treatment. Enlarged rows show native samples; 2x rows crop the same text on both sides.',fill='#c6ccd6')
    return sheet


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args = ap.parse_args()
    archive,report,masks,old,new = compose()
    print(json.dumps({k:v for k,v in report.items() if k!='glyphs'},indent=2))
    print('Coverage ratios:',[(r['character'],round(r['candidate_coverage_sum_at_source_scale']/r['source_coverage_sum'],3))
                              for r in report['glyphs'] if r['source_coverage_sum'] and
                              not .85<=r['candidate_coverage_sum_at_source_scale']/r['source_coverage_sum']<=1.15])
    if not args.write:
        print('DRY RUN: no font candidate or outline files written')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'WIN00.AFS').write_bytes(archive)
    (OUT/'font.bin').write_bytes(new)
    (OUT/'component-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    bank = OUT/'glyphs'
    bank.mkdir(exist_ok=True)
    for char,mask in masks.items():
        mask.save(bank/f'{ord(char):03d}.png')
    comparison(old,new).save(OUT/'comparison.png')
    specimen = Image.new('RGB',(1024,512),'#171b24')
    for row in report['glyphs']:
        i = ord(row['character'])-32
        specimen.paste('white',(i%16*64,i//16*80+14,i%16*64+64,i//16*80+78),masks[row['character']])
        ImageDraw.Draw(specimen).text((i%16*64,i//16*80),str(ord(row['character'])),fill='#c6ccd6')
    specimen.save(OUT/'all-glyphs.png')


if __name__ == '__main__':
    main()
