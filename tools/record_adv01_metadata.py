"""Classify ADV01's five remaining non-PVM members. Default dry run.

Four exact CP932 dummy markers and an ASCII asset-name list are preserved as
resource data. This is format coverage, not full image-text/reachability proof.
"""
import argparse
import json
from pathlib import PureWindowsPath
import struct

from build_bitmap_font import ROOT,digest
from disc_inventory import Disc


def read(path):
    return json.loads(path.read_text('utf-8'))


def record():
    disc=Disc(next(ROOT.glob('*.cue')))
    row=next(r for r in disc.inventory() if r['path']=='ADV01.AFS')
    archive=disc.read(row['lba'],row['size'])
    pvm=read(ROOT/'docs/pvm-image-audit.json')
    index=read(ROOT/pvm['index'])
    assert digest(archive)==pvm['source_archive_sha256']==index['source_archive_sha256']
    assert not index['unsupported_or_failed'] and len(index['containers'])==251
    assert index['texture_count']==476
    containers={r['member'] for r in index['containers']}
    expected={69,70,71,249,255}
    assert containers|expected==set(range(256)) and not containers&expected
    members=[]
    for i in sorted(expected):
        offset,size=struct.unpack_from('<II',archive,8+i*8)
        payload=archive[offset:offset+size]
        item={'member':i,'offset':offset,'bytes':size,'sha256':digest(payload)}
        if i!=255:
            assert size==27 and digest(payload)=='3b56a82fb61bd533d9cdfb0b32183c41367080a55f70d5a2368d1af08ebc557c'
            # Decode strictly; retain only an English meaning in public data.
            assert payload.endswith(b'\r\n\x1a')
            text=payload[:-1].decode('cp932')
            assert text.endswith('\r\n') and len(text)==14
            item.update(classification='Explicit CP932 dummy-file marker',
                        marker_meaning='This is a dummy file',terminator='CRLF plus DOS EOF',
                        target_action='Preserve exact resource bytes; do not translate as dialogue or image text')
        else:
            assert payload.endswith(b'\x1a')
            names=payload[:-1].decode('ascii').splitlines()
            assert len(names)==256 and names[-1]=='ADV01.ALS'
            assert all(n.lower().endswith('.pvm') and PureWindowsPath(n).name==n for n in names[:-1])
            item.update(classification='ASCII asset-name list with self-reference and DOS EOF',
                        asset_references=255,self_reference='ADV01.ALS',
                        names=names,target_action='Preserve asset identifiers, spelling, duplicates, CRLF and EOF exactly')
        members.append(item)
    doc={'archive':'ADV01.AFS','source_archive_sha256':digest(archive),
         'source_build':'Original disc; no translated bytes changed','current_game_build':'0.1.36',
         'total_members':256,'decoded_PVM_containers':251,'decoded_textures':476,
         'explicit_dummy_members':4,'asset_name_lists':1,'classified_non_PVM_members':members,
         'unclassified_members':[],
         'limits':['All container/member formats accounted for, not all possible fine image text or runtime use',
                   'No native dummy/list consumer, full-resolution absence or live GPU proof',
                   'No translation draft credit and no game byte/build change']}
    pvm['historical_decoder_skips']=pvm.get('historical_decoder_skips',pvm['other_members'])
    pvm.update(other_members=members,metadata_classification=doc,
               status='476 textures in 251 PVM containers decoded; remaining four dummy markers and one asset list classified. All 256 formats accounted for; image-text/reachability coverage incomplete')
    audit=read(ROOT/'docs/non-movie-image-text-audit.json')
    for finding in audit['remaining_findings']:
        if finding.get('archive')=='ADV01.AFS':
            finding.update(finding='All 256 members classified: 251 PVM containers with 476 textures, four explicit dummy markers and one asset-name list',
                           status='Fine-detail/full-resolution image-text and runtime reachability coverage remain unproved')
    for key in list(audit):
        if key.lower()=='pvm_discovery':
            audit[key]=pvm
    audit['ADV01_metadata_classification']=doc
    status=read(ROOT/'docs/translation-status.json')
    assert status['version']=='0.1.36'
    status.update(PVM_image_discovery=pvm,non_movie_image_text_audit=audit)
    return [(ROOT/'docs/adv01-metadata.json',doc),(ROOT/'docs/pvm-image-audit.json',pvm),
            (ROOT/'docs/non-movie-image-text-audit.json',audit),(ROOT/'docs/translation-status.json',status)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write',action='store_true')
    args=ap.parse_args()
    outputs=record()
    print('PASS: ADV01 all 256 members classified; 251 decoded PVM containers, four exact dummy markers and one 256-entry asset list.')
    if not args.write:
        print('DRY RUN: no source/documentation or game byte written')
        return
    for path,data in outputs:
        path.write_text(json.dumps(data,indent=2)+'\n','utf-8')
    log=ROOT/'CHANGELOG.md'
    text=log.read_text('utf-8')
    heading='## Working translation — classify remaining ADV01 metadata'
    entry='''## Working translation — classify remaining ADV01 metadata

- Classified ADV01 members 69/70/71/249 as byte-identical 27-byte CP932 dummy-file markers, not undiscovered PVM images or dialogue. Member 255 is an ASCII list of 255 PVM asset identifiers plus its ADV01.ALS self-reference, with exact CRLF and DOS EOF. Preserve their original bytes and asset names; no Japanese prose is added to public documents. All 256 archive members are now accounted for as 251 decoded PVM containers, four dummy markers and one filename list. Historical decoder-skip records and source index hashes retained.
- This closes the five unknown-format metadata entries only. Fine-detail image-text absence, actual resource use and native/live appearance remain unproved. No translated/game bytes or draft counts change; latest playable build stays 0.1.36. No release.

'''
    if heading not in text:
        assert text.startswith('# Change log\n\n')
        log.write_text(text.replace('# Change log\n\n','# Change log\n\n'+entry,1),'utf-8')
    print('Recorded metadata coverage without changing game assets or translation counts.')


if __name__=='__main__':
    main()
