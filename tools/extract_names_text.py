"""Extract D_NAMES text tables into local ignored working files. Dry run by default."""
import argparse
import json
from collections import Counter
from build_font_patch import ROOT
from rayblade_codec import decompress
from rayblade_text import TextCodec,names_tables,relative_target


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true');args=ap.parse_args()
    data,used=decompress((ROOT/'work/source/disc/D_NAMES.BIN').read_bytes())
    codec=TextCodec();rows=[];unknown=Counter()
    roots={relative_target(data,g*4) for g in range(23)}
    for group,index,pointer,target in names_tables(data):
        # Unused Trust Command and private-event slots point at the next table.
        # Preserve those pointer values, never decode binary pointers as prose.
        if target in roots:
            if not ((group==1 and index>=52) or (group==8 and index>=48)):
                raise ValueError('Unexpected table-root sentinel')
            row={'text':'','tokens':[],'unknown_glyphs':[],'bytes_consumed':0,
                 'terminator':None,'raw_hex':'','record_kind':'unused_table_root_sentinel'}
        else:
            row=codec.decode(data,target);row['record_kind']='text'
        unknown.update(row['unknown_glyphs'])
        row.update(id='names.g{:02d}.{:03d}'.format(group,index),group=group,index=index,
                   source_file='D_NAMES.BIN',pointer_offset=pointer,text_offset=target)
        rows.append(row)
    print('D_NAMES: {} text pointers; {} unique targets; {} unresolved glyph IDs.'.format(
        len(rows),len(set(v['text_offset'] for v in rows)),len(unknown)))
    for group in range(13):
        group_rows=[v for v in rows if v['group']==group]
        print('Group {}: {} rows. Samples: {}'.format(group,len(group_rows),
            json.dumps([r['text'] for r in group_rows[:3]],ensure_ascii=True)))
    print('Most frequent unresolved glyphs:',unknown.most_common(12))
    if not args.write:print('DRY RUN: no files written');return
    out=ROOT/'work/source/text';out.mkdir(parents=True,exist_ok=True)
    (out/'D_NAMES.dec.bin').write_bytes(data)
    (out/'D_NAMES.rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'names-unresolved.json').write_text(json.dumps(dict(unknown),indent=2),encoding='utf-8')
    print('Wrote local source rows and decoding diagnostics; game files unchanged')


if __name__=='__main__':main()
