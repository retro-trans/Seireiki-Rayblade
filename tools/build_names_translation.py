"""Build an expanded D_NAMES component with relocated English strings.

Appends a new text pool and changes only known text-pointer words. Binary
gameplay tables, root pointers and unused sentinels remain byte-identical.
This is not a playable disc; loader memory capacity must be verified first.
Default is dry run. Original files are never modified.
"""
import argparse
import hashlib
import json
import struct
from build_font_patch import ROOT
from rayblade_codec import decompress,compress
from rayblade_text import names_tables,relative_target
from prepare_names_translation import fingerprint
from english_text_codec import encode,decode


def compose(*,overrides=None,version='0.1.3'):
    original,used=decompress((ROOT/'work/source/disc/D_NAMES.BIN').read_bytes())
    source=json.loads((ROOT/'work/source/text/D_NAMES.rows.json').read_text(encoding='utf-8'))
    rows=json.loads((ROOT/'work/translation/en/ui/names.json').read_text(encoding='utf-8'))
    if [r['id'] for r in rows]!=[r['id'] for r in source]:raise ValueError('Source IDs differ')
    translated={r['id']:dict(r) for r in rows};output=bytearray(original)
    applied=[]
    for key,entry in (overrides or {}).items():
        row=translated[key]
        if entry['source_sha256']!=row['source_sha256']:raise ValueError('Stale layout source '+key)
        if entry['prior_en_sha256']!=hashlib.sha256(row['en'].encode('utf-8')).hexdigest():raise ValueError('Stale layout English '+key)
        applied.append({'id':key,'before':row['en'],'after':entry['en'],'reason':entry['reason']})
        row['en']=entry['en']
    while len(output)%4:output.append(0)
    pool_start=len(output);pool={};patched=set();relocations=[];sentinels=0
    for s in source:
        row=translated[s['id']]
        if row['source_sha256']!=fingerprint(s):raise ValueError('Stale English row '+s['id'])
        if s['record_kind']=='unused_table_root_sentinel':sentinels+=1;continue
        if row['en'] is None:raise ValueError('Untranslated row '+s['id'])
        payload=encode(row['en'],s['terminator'])
        if decode(payload)!=(row['en'],s['terminator']):raise ValueError('English round-trip failed '+s['id'])
        if payload not in pool:pool[payload]=len(output);output.extend(payload)
        target=pool[payload];pointer=s['pointer_offset']
        struct.pack_into('<I',output,pointer,target-pointer)
        patched.update(range(pointer,pointer+4))
        relocations.append({'id':s['id'],'pointer_offset':pointer,'old_target':s['text_offset'],
                            'new_target':target,'encoded_size':len(payload)})
    for i,(before,after) in enumerate(zip(original,output)):
        if i not in patched and before!=after:raise ValueError('Non-text source byte changed at '+hex(i))
    reconstructed={(g,n):(p,t) for g,n,p,t in names_tables(output)}
    for s in source:
        pointer,target=reconstructed[s['group'],s['index']]
        if pointer!=s['pointer_offset']:raise ValueError('Pointer-bank layout changed')
        if s['record_kind']=='unused_table_root_sentinel':
            if target!=s['text_offset']:raise ValueError('Unused binary sentinel changed')
        else:
            payload=encode(translated[s['id']]['en'],s['terminator'])
            if output[target:target+len(payload)]!=payload:raise ValueError('Relocated text mismatch')
    packed=compress(output)
    if decompress(packed)!=(bytes(output),len(packed)):raise ValueError('Expanded component PRS round-trip failed')
    executable=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes()
    if executable[0x10e9e:0x10ea6].hex()!='0ad40ad20b420900' or struct.unpack_from('<I',executable,0x10ec8)[0]!=65536:
        raise ValueError('Native name loader differs from verified allocation')
    report={'version':version,'kind':'offline text component; not a playable disc',
            'source_sha256':hashlib.sha256(original).hexdigest(),'output_sha256':hashlib.sha256(output).hexdigest(),
            'source_decoded_size':len(original),'output_decoded_size':len(output),'english_pool_start':pool_start,
            'output_compressed_size':len(packed),'compressed_sha256':hashlib.sha256(packed).hexdigest(),
            'native_destination_capacity':65536,'fits_native_destination':len(output)<=65536,
            'unique_encoded_strings':len(pool),'relocated_pointers':len(relocations),'unchanged_unused_sentinels':sentinels,
            'validation':{'english_roundtrip':'pass','text_pointer_targets':'pass','non_text_original_bytes':'unchanged','PRS_roundtrip':'pass'},
            'pending':(['Expand native allocation before inserting'] if len(output)>65536 else [])+
                      ['Disc insertion and in-game checks are tracked separately in english-disc-report.json and docs/text-reinsertion.json'],
            'relocations':relocations,'layout_overrides':applied}
    if not report['fits_native_destination']:raise ValueError('English names exceed the native allocation')
    return bytes(output),packed,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    output,packed,report=compose()
    print('D_NAMES expanded from {} to {} decoded bytes; {} pointers relocated into {} unique English strings.'.format(report['source_decoded_size'],len(output),report['relocated_pointers'],report['unique_encoded_strings']))
    print('Unchanged binary sentinels:',report['unchanged_unused_sentinels'],'; non-text prefix bytes preserved.')
    print('Recompressed component:',len(packed),'bytes; PRS round-trip passes.')
    print('First relocations:',json.dumps(report['relocations'][:3]))
    if not args.write:print('DRY RUN: no component written');return
    out=ROOT/'work/output/0.1.3/text';out.mkdir(parents=True,exist_ok=True)
    (out/'D_NAMES.en.dec.bin').write_bytes(output)
    (out/'D_NAMES.BIN').write_bytes(packed)
    (out/'names-component-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Wrote expanded component under',out,'; original game files unchanged')


if __name__=='__main__':main()
