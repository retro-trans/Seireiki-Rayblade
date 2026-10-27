"""Restore all story choice rows and native-density map labels as local 0.7.6."""
import argparse, copy, json, re, struct
from functools import lru_cache
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from build_bitmap_font import ROOT, digest
from rayblade_codec import compress, decompress
from build_scenario_translation import align, BANK_POINTER_OFFSET, SCRATCH_CAPACITY
from build_map_font_patch import member, packed_pvr
from build_font4x_patch import MEDIUM
from test_outline_font import legacy_mask
from choice_layout import layout
from dialogue_reflow import readable
from afs_layout import require_native_layouts
from sh4_asm import Assembler

VERSION, PRIOR = '0.7.6', '0.7.5'
OUT = ROOT/'work/output/choice-map-candidate'
MAP_HOOK = 0x8c018d00


def story(font):
    base = ROOT/'work/output'/PRIOR
    source = (base/'D_SCE.AFS').read_bytes()
    report = json.loads((base/'text/scenario-component-report.json').read_text('utf-8'))
    original = ROOT/'work/output/0.1.11'
    unflowed = (original/'D_SCE.AFS').read_bytes()
    unflowed_report = json.loads((original/'text/scenario-component-report.json').read_text('utf-8'))
    assert digest(source) == report['archive_sha256']
    encoded, records, choices = [], [], []
    for old, initial in zip(report['members'], unflowed_report['members']):
        p = old['archive_offset']; before, used = decompress(source[p+20:p+old['packed_bytes']])
        assert digest(before) == old['decoded_sha256'] and used == old['packed_bytes']-20
        selected = [r for r in old['commands'] if before[r['source_offset']-1] & 0x80]
        if not selected:
            encoded.append(source[p:p+old['packed_bytes']]); records.append(copy.deepcopy(old)); continue
        p = initial['archive_offset']
        untouched = decompress(unflowed[p+20:p+initial['packed_bytes']])[0]
        assert untouched[:old['original_bytes']] == before[:old['original_bytes']]
        initial_rows = {r['id']: r for r in initial['commands']}
        bank = old['bank_offset']; plain = bytearray(before[:bank+32])
        table = len(plain); plain.extend(bytes(len(old['commands'])*8)); rows = []
        for i, row in enumerate(old['commands']):
            raw = before[row['english_offset']:row['english_offset']+row['english_bytes']]
            changed = before[row['source_offset']-1] & 0x80
            if changed:
                r = initial_rows[row['id']]
                original_payload = untouched[r['english_offset']:r['english_offset']+r['english_bytes']]
                assert re.findall(r'\S+', readable(raw,font)) == re.findall(r'\S+', readable(original_payload,font))
                raw, detail = layout(original_payload, font)
                choices.append({'id': row['id'], 'style': before[row['source_offset']-1],
                    'source_payload_sha256': digest(original_payload), 'sha256': digest(raw),
                    'changed': digest(raw) != row['english_sha256'], **detail})
            struct.pack_into('<HHI', plain, table+i*8, row['source_offset'], row['source_bytes'], len(plain)|0x80000000)
            rows.append({**row, 'english_offset': len(plain), 'english_bytes': len(raw),
                'english_sha256': digest(raw), **({'choice_rows_preserved': True, 'compact_choices': detail['compact']} if changed else {})})
            plain.extend(raw)
        plain.extend(bytes(align(len(plain),4)-len(plain)))
        struct.pack_into('<I',plain,bank+16,len(plain)); assert len(plain) <= BANK_POINTER_OFFSET
        packed = compress(plain); assert decompress(packed) == (bytes(plain),len(packed))
        wrapped = struct.pack('<4s4I',b'RBS2',len(plain),len(packed),old['index'],bank)+packed
        assert align(len(wrapped)) <= SCRATCH_CAPACITY
        encoded.append(wrapped)
        records.append({**old, 'commands': rows, 'decoded_bytes': len(plain),
            'decoded_sha256': digest(plain), 'packed_bytes': len(wrapped), 'packed_sha256': digest(wrapped)})
    first = struct.unpack_from('<I',source,8)[0]; archive = bytearray(source[:first])
    for row, raw in zip(records, encoded):
        off = align(len(archive)); archive.extend(bytes(off-len(archive))); archive.extend(raw)
        struct.pack_into('<II',archive,8+row['index']*8,off,len(raw)); row['archive_offset'] = off
    listing = member(source,447); off = align(len(archive)); archive.extend(bytes(off-len(archive))); archive.extend(listing)
    struct.pack_into('<II',archive,8+447*8,off,len(listing)); used = len(archive)
    assert used <= len(source), (used,len(source)); archive.extend(bytes(len(source)-used))
    report.update(version=VERSION,archive_sha256=digest(archive),members=records,
        used_archive_bytes=used,spare_archive_bytes=len(source)-used,
        choice_layout={'commands':len(choices),'compact_commands':sum(r['compact'] for r in choices),
                      'boundaries':'Original selectable rows retained; no prose reflow across options'})
    assert len(choices) == 961
    return bytes(archive),report,choices


def map_labels(font):
    source = (ROOT/'work/output'/PRIOR/'WMAP.AFS').read_bytes()
    dat = bytearray(member(source,17)); start = 4+struct.unpack_from('<I',dat,4)[0]
    atlas = np.zeros((128,512),np.uint16); x=y=0; details=[]
    rows=json.loads((ROOT/'work/translation/en/ui/worldmap-labels.en.json').read_text('utf-8'))['rows']
    for row in rows:
        at=start+row['sprite']*20
        w,h,cx,cy,*_ = struct.unpack_from('<HHhh6H',dat,at)
        assert h==16
        coverage=Image.new('L',(sum(font[0xa0+MEDIUM.index(c)]*2 for c in row['en'])+32,32)); cursor=0
        for ch in row['en']:
            mask=Image.fromarray(legacy_mask(font,ch,False)[::2,::2].copy())
            coverage.paste(mask,(cursor,0));cursor+=font[0xa0+MEDIUM.index(ch)]*2
        box=coverage.getbbox(); assert box and box[2]+2<=w*2
        cell=Image.new('L',(w*2,32));cell.paste(coverage.crop((0,0,box[2]+2,32)),((w*2-box[2]-2)//2,0))
        ink=np.asarray(cell);edge=np.asarray(cell.filter(ImageFilter.MaxFilter(3)))
        rgba=(edge.astype(np.uint16)//17)<<12
        fg=ink>0;rgba[fg]=((ink[fg].astype(np.uint16)//17)<<12)|0xffe
        if x+w*2>512:x=0;y+=32
        assert y+32<=128
        atlas[y:y+32,x:x+w*2]=rgba
        # NJSPRITE UVs are always fractions of 256, regardless of texture size.
        struct.pack_into('<4H',dat,at+8,x//2,y*2,(x+w*2)//2,(y+32)*2)
        details.append({'id':row['id'],'sprite':row['sprite'],'en':row['en'],
            'atlas_box':[x,y,x+w*2,y+32], 'draw_size':[w,h],
            'coverage_sha256':digest(ink.tobytes())})
        x+=w*2
    packed,raw=packed_pvr(atlas,0xd02,0x00ed0076)
    members=[member(source,i) for i in range(21)];members[17]=bytes(dat);members[19]=packed
    first=struct.unpack_from('<I',source,8)[0];target=bytearray(source[:first])
    for i,payload in enumerate(members):
        off=align(len(target));target.extend(bytes(off-len(target)));target.extend(payload)
        struct.pack_into('<II',target,8+i*8,off,len(payload))
    assert len(target)<=len(source);target.extend(bytes(len(source)-len(target)))
    return bytes(target),bytes(dat),raw,atlas,details


def map_hook(exe):
    """Snap only the English map-label sprites in the scaled sprite copy.

    Identify the original map's two-name texture list plus IDs 17..26.
    No terrain/marker or dialogue rendering arguments are modified.
    """
    a=Assembler(MAP_HOOK)
    a.imm(17,0);a.rr('cmp/hs',0,5);a.branch('bf','tail')
    a.imm(27,0);a.rr('cmp/hs',0,5);a.branch('bt','tail')
    a.emit(0x5146) # MOV.L @(24,R4),R1 (NJTEXLIST)
    a.rr('tst',1,1);a.branch('bt','tail')
    a.emit(0x5211);a.imm(2,0);a.rr('cmp/eq',0,2);a.branch('bf','tail')
    a.load('l',1,1);a.addi(12,1);a.load('l',1,1);a.load('l',1,2)
    a.lit(int.from_bytes(b'wmap','little'),0);a.rr('cmp/eq',0,2);a.branch('bf','tail')
    a.addi(4,1);a.load('l',1,2);a.lit(int.from_bytes(b'_en\0','little'),0)
    a.rr('cmp/eq',0,2);a.branch('bf','tail')
    a.rr('mov',4,1);a.imm(2,2)
    a.label('snap')
    a.emit(0xf019) # FMOV @R1+,FR0
    a.emit(0xf03d) # FTRC FR0,FPUL; truncate physical coordinate, including negatives
    a.emit(0xf02d) # FLOAT FPUL,FR0
    a.addi(-4,1);a.emit(0xf10a);a.addi(4,1)
    a.unary('dt',2);a.branch('bf','snap')
    a.label('tail');a.lit(0x8c0ab970,3);a.emit(0x432b);a.emit(0x0009)
    code=a.pool_and_finish();target=bytearray(exe);off=MAP_HOOK-0x8c010000
    assert not any(target[off:off+len(code)]) and 0x8cfc <= off and off+len(code)<0x9000
    target[off:off+len(code)]=code
    old=struct.pack('<I',0x8c0ab970)
    sites=[p for p in range(0x6b6e0,0x6b7a8,4) if target[p:p+4]==old]
    assert len(sites)==1,sites
    struct.pack_into('<I',target,sites[0],MAP_HOOK)
    return bytes(target), {'entry':hex(MAP_HOOK),'bytes':len(code),'pointer_offset':hex(sites[0]),
        'scope':'English map labels only; physical-pixel position snapping; no original caller data writes'}


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;exe=(base/'1ST_READ.BIN').read_bytes()
    assert digest(exe)=='690bb984eb87bf657070fffefae4a568fe33425e61545ab8ee15aa7744be4d87'
    afs=(base/'WIN00.AFS').read_bytes();font=member(afs,0)[:99072]
    scenario,story_report,choices=story(font)
    wmap,dat,raw,atlas,labels=map_labels(font)
    exe,hook=map_hook(exe)
    files={'1ST_READ.BIN':exe,'D_SCE.AFS':scenario,'WMAP.AFS':wmap}
    require_native_layouts(files)
    report={'version':VERSION,'source_build':PRIOR,'files':{n:{'size':len(v),'sha256':digest(v)} for n,v in files.items()},
        'choice_commands':len(choices),'changed_choice_commands':sum(r['changed'] for r in choices),
        'compact_choice_commands':sum(r['compact'] for r in choices),'wording':'unchanged',
        'map_texture_dimensions':[512,128],'map_VRAM_bytes':131072,
        'map_font':'Exact original 12x24 Skies main glyph samples, four alpha levels; one texel per native output pixel',
        'map_position_hook':hook,'labels':labels,'choice_rows':choices,
        'limits':['Native checks and live GPU appearance pending','Physical hardware/non-VGA/full-game validation pending']}
    return files,story_report,report,dat,raw,atlas


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,story_report,report,dat,raw,atlas=compose()
    print(json.dumps({k:v for k,v in report.items() if k not in ('labels','choice_rows')},indent=2))
    if not args.write:print('DRY RUN: no files written');return
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():(OUT/name).write_bytes(data)
    for name,value in [('scenario-component-report.json',story_report),('component-report.json',report)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')
    (OUT/'map-labels.dat').write_bytes(dat);(OUT/'map-labels.pvr').write_bytes(raw)


if __name__=='__main__':main()
