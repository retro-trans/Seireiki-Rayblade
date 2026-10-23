"""Inventory ANIME dialogue-like byte matches without treating them as text.

Default dry run. Bounded decoder probes are diagnostics only; no Japanese
prose is saved in the public report and no command/reachability claim is made.
"""
import argparse
from collections import Counter,defaultdict
import json
import re

from audit_animation_payloads import original
from build_bitmap_font import ROOT,digest
from rayblade_codec import decompress
from rayblade_text import TextCodec

OUT=ROOT/'work/ui/asset-audit/ANIME/text-markers-01'


def inspect():
    archive,members=original()
    frozen=json.loads((ROOT/'work/ui/asset-audit/ANIME/decoded-01/structure-index.json').read_text('utf-8'))
    assert frozen['source_archive_sha256']==digest(archive)
    codec=TextCodec()
    matches=[]
    identities=[]
    for n,raw in enumerate(members):
        plain,used=decompress(raw)
        assert used==len(raw)
        assert digest(plain)==frozen['members'][n]['decoded_sha256']
        identities.append({'member':n,'decoded_bytes':len(plain),'decoded_sha256':digest(plain)})
        for match in re.finditer(b'\x8a\x06',plain):
            offset=match.start()
            style=plain[offset+2] if offset+2<len(plain) else None
            row={'member':n,'offset':offset,'style_byte':style,
                 'matches_one_of_five_known_scenario_styles':style in (0,64,128,160,192),
                 'context_start':max(0,offset-16),
                 'context_sha256':digest(plain[max(0,offset-16):min(len(plain),offset+48)]),
                 'classification':'Unresolved byte match; native command/data context not established'}
            if row['matches_one_of_five_known_scenario_styles']:
                try:
                    probe=codec.decode(plain,offset+3,limit=min(len(plain),offset+515))
                    row['bounded_decoder_probe']={'bytes_consumed':probe['bytes_consumed'],
                         'terminator':probe['terminator'],'unknown_glyph_count':len(probe['unknown_glyphs']),
                         'inline_control_count':sum(t['kind']=='control' for t in probe['tokens']),
                         'mode_toggle_count':sum(t['kind']=='mode' for t in probe['tokens']),
                         'text_sha256':digest(probe['text'].encode('utf-8')),
                         'scope':'First FE/FF only within 512 payload bytes; arbitrary data can also decode'}
                except ValueError as error:
                    row['bounded_decoder_probe']={'error':str(error)}
            matches.append(row)
    groups=defaultdict(list)
    for row in matches:
        if row['matches_one_of_five_known_scenario_styles']:
            groups[row['context_sha256']].append({'member':row['member'],'offset':row['offset']})
    duplicates=[{'context_sha256':key,'matches':value} for key,value in groups.items() if len(value)>1]
    return {'archive':'ANIME.AFS','source_archive_sha256':digest(archive),'members_checked':len(members),
            'decoded_bytes':sum(r['decoded_bytes'] for r in identities),'PRS_consumption':'all full members exact',
            'byte_matches':len(matches),'known_style_byte_matches':sum(r['matches_one_of_five_known_scenario_styles'] for r in matches),
            'style_byte_histogram':dict(Counter(str(r['style_byte']) for r in matches)),
            'candidate_context_duplicate_groups':duplicates,'member_identities':identities,'matches':matches,
            'confirmed_new_text_commands':0,'meaning_of_zero':'No new command has been established by this audit; this is not a proof of text absence',
            'next_evidence':'Trace native command/data boundaries or resource consumers before translating, rejecting or counting matches',
            'limits':['Five known D_SCE styles do not exclude other styles or text encodings',
                      'Terminator/unknown-glyph statistics and duplicate numeric-looking contexts are not semantic proof',
                      'No native animation VM reachability, full page-continuation parsing or complete text coverage',
                      'No game/translation byte changed and no draft credit']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    report=inspect()
    print('PASS:',report['members_checked'],'exact decoded identities;',report['byte_matches'],
          'raw marker matches;',report['known_style_byte_matches'],'with known style bytes;',
          len(report['candidate_context_duplicate_groups']),'duplicate context groups.',flush=True)
    if not args.write:
        print('DRY RUN: no marker index written; matches remain unclassified')
        return
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'marker-index.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote bounded diagnostics; no new text or absence claim established.')


if __name__=='__main__':
    main()
