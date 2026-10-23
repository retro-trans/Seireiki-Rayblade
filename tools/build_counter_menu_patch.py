"""Extend counter policy/forecast/objective boxes and reflow policy help. Dry first."""
import argparse,json,struct
from functools import lru_cache
from build_bitmap_font import ROOT,digest
from build_antialias_font import font_bytes
from build_font4x_patch import MEDIUM
from build_names_translation import compose as names_compose

VERSION='0.1.43';PRIOR='0.1.42'
OUT=ROOT/'work/output/counter-menu-draft-01'
# Only embedded VM operands and the popup's shared data template change.
EDITS=[
 (0xe70f,17,13,'Forecast choices text x136 to x104'),
 (0xe716,16,12,'Forecast frame x128 to x96'),
 (0xe718,8,16,'Forecast frame width64 to128'),
 (0xfdc3,16,13,'Policy choices text x128 to x104'),
 (0xfdc4,10,8,'Policy choices text y80 to y64; clear taller help box'),
 (0xfdca,15,12,'Policy frame x120 to x96'),
 (0xfdcb,9,7,'Policy frame y72 to y56; bottom aligns with help top'),
 (0xfdcc,10,16,'Policy frame width80 to128'),
 (0xfde3,5,4,'Help text x40 to x32'),
 (0xfde4,22,20,'Help text y176 to y160'),
 (0xfde5,21,38,'Use existing six-line text template for up to four help lines; 256px backing width'),
 (0xfdea,4,3,'Help frame x32 to x24'),
 (0xfdeb,21,19,'Help frame y168 to y152'),
 (0xfdec,31,34,'Help frame width248 to272'),
 (0xfded,8,10,'Help frame height64 to80'),
 (0xfeb4,17,14,'Objectives title text x136 to x112'),
 (0xfebb,16,13,'Objectives title frame x128 to x104'),
 (0xfebd,8,14,'Objectives title frame width64 to112'),
]+[(p,64,112,f'Popup tile {i}: visible width64 to112') for i,p in enumerate((0x8a3a8,0x8a3b5,0x8a3c2,0x8a3cf,0x8a3e2))]


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR;before=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(before)
    assert before[0xe70b:0xe71c]==bytes.fromhex('8a22060011122b8a2006001011080a8a23')
    assert before[0xfdbf:0xfdd0]==bytes.fromhex('8a220401100a2b8a2004010f090a0c8a23')
    assert struct.unpack_from('<I',before,0x89ba8+43*4)[0]==0x8c09a399
    uses=[p for p in range(0xc000,0x11000) if before[p:p+2]==b'\x8a\x22' and before[p+6]==43]
    assert uses==[0xe70b,0xfdbf]
    for p,a,b,_ in EDITS:assert exe[p]==a,(hex(p),exe[p],a);exe[p]=b
    rows={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    recipe=json.loads((base/'ui-layouts.en.json').read_text('utf-8'))
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1]
    width=lambda s:sum(font[0xa0+MEDIUM.index(c)] for c in s)
    aliases=[]
    for i in range(24,32):
        key=f'names.g01.{i:03d}';row=rows[key];old=recipe['rows'].get(key,row)['en']
        words=old.replace('<NL>',' ').split();lines=[];line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if width(candidate)>252:
                assert line;lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        assert len(lines)<=4 and max(map(width,lines))<=252
        # Keep the minimum row count while avoiding one-word final rows.
        count=len(lines);target=(width(' '.join(words))-(count-1)*width(' '))/count
        @lru_cache(maxsize=None)
        def balanced(start,left):
            if not left:return (0,()) if start==len(words) else (float('inf'),())
            best=(float('inf'),())
            for end in range(start+1,len(words)+1):
                text=' '.join(words[start:end]);pen=width(text)
                if pen>252:break
                cost,tail=balanced(end,left-1);candidate=(cost+(pen-target)**2,(text,)+tail)
                if candidate[0]<best[0]:best=candidate
            return best
        cost,result=balanced(0,count);assert cost<float('inf');lines=list(result)
        assert ' '.join(lines).split()==words
        new='<NL>'.join(lines)
        recipe['rows'][key]={'en':new,'source_sha256':row['source_sha256'],
            'prior_en_sha256':digest(row['en'].encode()),
            'reason':'Whole-word policy help reflow; every word retained; 252px pen limit in widened 272px frame'}
        aliases.append({'id':key,'before':old,'after':new,'line_widths':list(map(width,lines))})
    decoded,packed,names_report=names_compose(overrides=recipe['rows'],version=VERSION)
    stream=len(packed);capacity=len((base/'text/D_NAMES.BIN').read_bytes());assert stream<=capacity
    packed+=bytes(capacity-stream);recipe.update(version=VERSION,previous_build=PRIOR)
    report={'version':VERSION,'source_build':PRIOR,'source_executable_sha256':digest(before),
        'executable_sha256':digest(exe),'executable_data_edits':[{'offset':hex(p),'before':a,'after':b,'reason':s} for p,a,b,s in EDITS],
        'names_packed_sha256':digest(packed),'names_decoded_sha256':digest(decoded),
        'names_stream_bytes':stream,'names_file_bytes':capacity,'help_rows':aliases,
        'font_changed':False,'font_sha256':digest(font),'font_issue':{
            'reported_labels':['Counterattack','Select Weapon'],
            'old_popup_visible_width':64,'new_popup_visible_width':112,
            'original_font_pixels_and_advances':'unchanged original Skies medium bank',
            'scope':'Remove popup tile clipping; verify identical bank/scale on all choice lines; live appearance pending'},
        'geometry':{'policy_frame':[96,56,128,96],'forecast_frame':[96,136,128,80],
            'popup_text_x':104,'policy_text_y':64,'popup_text_visible_width':112,
            'help_frame':[24,152,272,80],'help_text_x':32,'help_pen_width':252,
            'objectives_frame':[104,24,112,32],'objectives_text_x':112},
        'release':False}
    return {'1ST_READ.BIN':bytes(exe),'D_NAMES.BIN':packed},decoded,recipe,names_report,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');a=ap.parse_args()
    files,decoded,recipe,names,report=compose();print(json.dumps(report,indent=2),flush=True)
    if not a.write:print('DRY RUN: no components written.');return
    OUT.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():(OUT/name).write_bytes(raw)
    (OUT/'D_NAMES.en.dec.bin').write_bytes(decoded)
    for name,value in [('component-report.json',report),('ui-layouts.en.json',recipe),('names-component-report.json',names)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
