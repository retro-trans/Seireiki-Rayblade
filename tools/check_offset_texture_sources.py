"""Verify representative offset-table source PRS and scalar texture pixels.

Default dry run. This proves codec interpretation, not native table loading.
"""
import argparse
import json

import numpy as np

from audit_offset_texture_tables import FILES,original,decode_record
from build_bitmap_font import ROOT,digest
from check_native_text_components import verify
from rayblade_codec import decompress
from test_ui_images import scalar_plane

OUT=ROOT/'work/ui/asset-audit/offset-tables-native-test.json'


def check():
    exe=(ROOT/'work/output/0.1.35/1ST_READ.BIN').read_bytes()
    records=[]
    scalar_pixels=0
    for name in FILES:
        raw,table=original(name)
        index=json.loads((ROOT/'work/ui/asset-audit'/name.replace('.BIN','')/'offset-table-01/texture-index.json').read_text('utf-8'))
        assert index['source_sha256']==digest(raw) and not index['unsupported_or_failed']
        assert index['unique_nonempty_resources']==len(index['decoded_resources_info'])
        for row in (table['resources'][0],table['resources'][-1]):
            info,images=decode_record(raw,name,row,independent=True)
            blob=raw[row['offset']:row['offset']+row['bytes']]
            outer=info['outer_header_bytes']
            plain,used=decompress(blob[outer:])
            steps=verify(exe,blob[outer:outer+used],plain,len(plain))
            if name=='D_FACE.BIN':
                values=scalar_plane(plain,64,64)
                # Each channel/alpha is decoded independently from scalar u16.
                expected=np.stack([((values>>shift&31)*255//31).astype(np.uint8) for shift in (10,5,0)]
                                  +[((values>>15)*255).astype(np.uint8)],axis=2)
                assert np.array_equal(expected,np.asarray(images[0][0]))
                scalar_pixels+=64*64
            else:
                scalar_pixels+=sum(image.width*image.height for image,_ in images)
            records.append({'file':name,'index':row['index'],'source_sha256':table['source_sha256'],
                            'source_span_sha256':info['source_span_sha256'],'PRS_bytes':used,
                            'decoded_bytes':len(plain),'decoded_sha256':digest(plain),
                            'verified_zero_alignment_bytes':info['verified_zero_alignment_bytes'],
                            'textures_checked':len(images),'native_PRS_instructions':steps})
    return {'tested_executable_build':'0.1.35','executable_sha256':digest(exe),'source_streams':records,
            'native_PRS_instructions':sum(r['native_PRS_instructions'] for r in records),
            'independently_checked_source_pixels':scalar_pixels,
            'native_guard_and_ABI':'pass','scope':'Four representative original PRS streams; first/last source textures per table and palette entries checked independently',
            'native_table_lookup_archive_loading_and_GPU':False,'game_bytes_changed':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: first/last resources of both offset-table files; four native PRS streams and independent scalar source pixels/palettes.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution/report')
        return
    result=check()
    print('PASS:',result['native_PRS_instructions'],'native PRS instructions;',result['independently_checked_source_pixels'],'scalar pixels.',flush=True)
    if args.write_report:
        OUT.write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
