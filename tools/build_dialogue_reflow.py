"""Reflow all inserted English story, embedded and battle dialogue. Dry first."""
import argparse
from collections import Counter
from functools import lru_cache
import copy
import json
import struct

from build_bitmap_font import ROOT,digest
from build_antialias_font import font_bytes
from build_scenario_translation import align,BANK_POINTER_OFFSET,SCRATCH_CAPACITY
from rayblade_codec import compress,decompress
from prs_optimal import compress_dynamic
from dialogue_reflow import reflow,readable,paginate
from afs_layout import require_native_layouts

VERSION='0.1.41';PRIOR='0.1.40'
OUT=ROOT/'work/output/dialogue-reflow-draft-01'


@lru_cache(maxsize=1)
def compose():
    base=ROOT/'work/output'/PRIOR
    font=font_bytes((base/'WIN00.AFS').read_bytes())[1]
    source=(base/'D_SCE.AFS').read_bytes()
    previous=json.loads((base/'text/scenario-component-report.json').read_text('utf-8'))
    assert previous['archive_sha256']==digest(source)
    total=Counter();encoded=[];members=[];samples=[]
    for old in previous['members']:
        off=old['archive_offset'];before,used=decompress(source[off+20:off+old['packed_bytes']])
        assert digest(before)==old['decoded_sha256'] and used==old['packed_bytes']-20
        plain=bytearray(before[:old['bank_offset']]);bank=len(plain)
        assert digest(plain[:old['original_bytes']])==old['original_sha256']
        plain.extend(before[bank:bank+32]);table=len(plain);plain.extend(bytes(len(old['commands'])*8))
        records=[]
        for i,row in enumerate(old['commands']):
            start=row['english_offset'];payload=before[start:start+row['english_bytes']]
            assert digest(payload)==row['english_sha256']
            result,stats=reflow(payload,font)
            total.update(commands=1,changed_commands=int(stats['changed']),joined_breaks=stats['joined_single_breaks'],new_breaks=stats['automatic_breaks'])
            struct.pack_into('<HHI',plain,table+i*8,row['source_offset'],row['source_bytes'],len(plain)|0x80000000)
            records.append({**row,'english_offset':len(plain),'english_bytes':len(result),'english_sha256':digest(result),
                'prior_english_sha256':digest(payload),'word_wrapped':True,'automatic_breaks':stats['automatic_breaks']})
            plain.extend(result)
            if row['id']=='scenario.s_002.o00526' or len(samples)<2:
                samples.append({'id':row['id'],'before':readable(payload,font),'after':readable(result,font)})
        plain.extend(bytes(align(len(plain),4)-len(plain)))
        struct.pack_into('<I',plain,bank+16,len(plain))
        assert len(plain)<=BANK_POINTER_OFFSET
        packed=compress(plain);assert decompress(packed)==(bytes(plain),len(packed))
        wrapped=struct.pack('<4s4I',b'RBS2',len(plain),len(packed),old['index'],bank)+packed
        assert align(len(wrapped))<=SCRATCH_CAPACITY
        encoded.append([bytes(plain),wrapped])
        record={**old,'decoded_bytes':len(plain),'decoded_sha256':digest(plain),'packed_bytes':len(wrapped),
                'packed_sha256':digest(wrapped),'commands':records}
        record.pop('dynamic_PRS',None);members.append(record)
        if (old['index']+1)%100==0: print('Reflowed story members:',old['index']+1,'/447',flush=True)
    off,size=struct.unpack_from('<II',source,8+447*8);listing=source[off:off+size]
    first=struct.unpack_from('<I',source,8)[0]
    projected=lambda:first+sum(align(len(p[1])) for p in encoded)+align(len(listing))
    optimized=[]
    for i in sorted(range(len(encoded)),key=lambda i:len(encoded[i][1])%2048 or 2048):
        if projected()<=len(source): break
        plain,old=encoded[i];packed=compress_dynamic(plain)
        target=old[:8]+struct.pack('<I',len(packed))+old[12:20]+packed
        assert decompress(packed)==(plain,len(packed))
        if len(target)>=len(old):continue
        encoded[i][1]=target;members[i].update(packed_bytes=len(target),packed_sha256=digest(target),dynamic_PRS=True)
        optimized.append({'index':i,'saved_bytes':len(old)-len(target)})
        print('Optimized PRS member',i,'projected bytes',projected(),flush=True)
    assert projected()<=len(source),('Story extent',projected(),len(source))
    archive=bytearray(source[:first])
    for m,(_,wrapped) in zip(members,encoded):
        off=align(len(archive));archive.extend(bytes(off-len(archive)));archive.extend(wrapped)
        struct.pack_into('<II',archive,8+m['index']*8,off,len(wrapped));m['archive_offset']=off
    off=align(len(archive));archive.extend(bytes(off-len(archive)));archive.extend(listing)
    struct.pack_into('<II',archive,8+447*8,off,len(listing));used=len(archive);archive.extend(bytes(len(source)-used))
    component=copy.deepcopy(previous)
    component.update(version=VERSION,archive_sha256=digest(archive),used_archive_bytes=used,spare_archive_bytes=len(source)-used,
        members=members,dynamic_PRS_members=optimized,maximum_decoded_member_bytes=max(m['decoded_bytes'] for m in members),
        maximum_packed_member_bytes=max(m['packed_bytes'] for m in members),maximum_sector_read_bytes=max(align(m['packed_bytes']) for m in members))
    component['word_wrap']={'font_sha256':digest(font),'target_width':240,'maximum_pen_width':236,**dict(total),
        'whitespace':'Obsolete single FD breaks joined; double-FD paragraph and FE page boundaries retained; whole-word measured wrapping',
        'working_translation_rows':'unchanged','forced_word_breaks':0,'native_verification':'pending','live_verification':'pending'}
    # Embedded payloads remain in the same preallocated slots; native lookup,
    # original command addresses and all executable instructions stay exact.
    source_exe=(base/'1ST_READ.BIN').read_bytes();exe=bytearray(source_exe)
    embedded=json.loads((base/'embedded-dialogue-component.json').read_text('utf-8'))
    embedded_counts=Counter();allowed=set()
    for row in embedded['records']:
        p=row['english_offset'];size=row['english_bytes'];old=source_exe[p:p+size]
        assert digest(old)==row['english_sha256']
        raw,stats=reflow(old,font);assert len(raw)<=size
        exe[p:p+size]=raw+bytes(size-len(raw));allowed.update(range(p,p+size))
        row.update(english_bytes=len(raw),english_sha256=digest(raw),prior_english_sha256=digest(old),automatic_breaks=stats['automatic_breaks'])
        embedded_counts.update(commands=1,changed_commands=int(stats['changed']))
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(source_exe,exe)))
    embedded.update(version=VERSION,source_build=PRIOR,source_executable_sha256=digest(source_exe),executable_sha256=digest(exe),
                    reflow_counts=dict(embedded_counts),native_verification='pending')
    # The two non-page-terminated battle fragments are checked again in every
    # native selection path. All 5516 graph span IDs and edges are retained.
    from build_battle_translation import build as battle_build
    battle_counts=Counter()
    def transform(payload,span):
        raw,stats=reflow(payload+b'\xff',font,safe_fc=set(range(0x40,0x4b)))
        raw,extra=paginate(raw,font)
        battle_counts.update(spans=1,changed_spans=int(stats['changed']),joined_breaks=stats['joined_single_breaks'],new_breaks=stats['automatic_breaks'])
        battle_counts['automatic_page_breaks']+=extra
        return raw[:-1]
    battle,packed,old_records,rebuilt,mapping,battle_spans,battle_report=battle_build(presentation_transform=transform)
    capacity=len((base/'text/D_BMESS.BIN').read_bytes())
    battle_compression='greedy PRS'
    if len(packed)>capacity:
        packed=compress_dynamic(battle);battle_compression='bit-cost dynamic PRS'
        assert decompress(packed)==(battle,len(packed))
    assert len(packed)<=capacity,('Battle ISO extent',len(packed),capacity)
    stream_bytes=len(packed);packed+=bytes(capacity-len(packed))
    battle_report.update(version=VERSION,output_sha256=digest(battle),compressed_sha256=digest(packed),
        output_compressed_bytes=len(packed),compressed_stream_bytes=stream_bytes,compression=battle_compression,
        reflow_counts=dict(battle_counts),stage='Reflowed English battle candidate; native verification pending')
    files={'1ST_READ.BIN':bytes(exe),'D_SCE.AFS':bytes(archive),'D_BMESS.BIN':packed}
    require_native_layouts({'D_SCE.AFS':bytes(archive)})
    report={'version':VERSION,'source_build':PRIOR,'font_sha256':digest(font),'files':{n:{'sha256':digest(v),'bytes':len(v)} for n,v in files.items()},
        'story':dict(total),'embedded':dict(embedded_counts),'battle':dict(battle_counts),'samples':samples,
        'maximum_pen_width':236,'working_rows':'unchanged','source_VM_prefixes':'exact',
        'pages_pauses_controls_words':'preserved; single layout FD breaks are reflowed',
        'native_verification':'pending','release':False}
    return files,component,embedded,battle,battle_report,report,encoded,(old_records,rebuilt,mapping,battle_spans)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,story,embedded,battle,battle_report,report,_,_=compose()
    print(json.dumps(report,indent=2),flush=True)
    if not args.write: print('DRY RUN: no components written.');return
    OUT.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():(OUT/name).write_bytes(raw)
    (OUT/'D_BMESS.en.dec.bin').write_bytes(battle)
    for name,value in [('scenario-component-report.json',story),('embedded-dialogue-component.json',embedded),
        ('battle-component-report.json',battle_report),('component-report.json',report)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n','utf-8')


if __name__=='__main__': main()
