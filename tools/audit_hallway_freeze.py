"""Compare the reported 0.7.27 hallway transition with working 0.7.2.

Default dry run. Saves English labels, identities and bytecode-span hashes;
never emits or commits original Japanese script text.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check():
    from rayblade_codec import decompress
    names = ('scenario.s_001.o00cce', 'scenario.s_001.o00cdf',
             'scenario.s_001.o00d2f', 'scenario.s_001.o00d42')
    compiled = {}
    for version in ('0.7.2','0.7.27'):
        directory = ROOT/'work/output'/version
        report = json.loads((directory/'text/scenario-component-report.json').read_text('utf-8'))
        member = report['members'][1]
        assert member['name'].lower() == 's_001.bin'
        archive = (directory/'D_SCE.AFS').read_bytes()
        offset, size = struct.unpack_from('<II',archive,8+8)
        data,_ = decompress(archive[offset+20:offset+size])
        assert sha(data) == member['decoded_sha256']
        original_size = member['original_bytes']
        assert sha(data[:original_size]) == member['original_sha256']
        commands = {r['id']:r for r in member['commands']}
        streams = {}
        for name in names:
            row = commands[name]
            blob = data[row['english_offset']:row['english_offset']+row['english_bytes']]
            assert sha(blob) == row['english_sha256']
            streams[name] = {'source_offset':row['source_offset'], 'source_bytes':row['source_bytes'],
                             'english_offset':row['english_offset'], 'english_bytes':len(blob),
                             'english_sha256':sha(blob)}
        sorry, kasumi = [commands[n] for n in names[1:3]]
        start = sorry['source_offset']+sorry['source_bytes']
        end = kasumi['source_offset']-3
        assert 0 <= start <= end < original_size
        compiled[version] = {'archive_sha256':sha(archive),'member_decoded_sha256':sha(data),
            'original_program_bytes':original_size,'original_program_sha256':sha(data[:original_size]),
            'dialogue':streams,'transition_after_sorry':{'start':hex(start),'end_exclusive':hex(end),
                'bytes':end-start,'sha256':sha(data[start:end])}}
    a,b = compiled.values()
    assert a['original_program_sha256'] == b['original_program_sha256']
    assert a['transition_after_sorry'] == b['transition_after_sorry']
    assert all(a['dialogue'][n]['english_sha256'] == b['dialogue'][n]['english_sha256'] for n in names)
    return {'date':'2026-11-01','reported_version':'0.7.27','device':'Real Dreamcast / GDEMU / VGA',
        'result':'Partial improvement only: New Game and missions now enter, but a later opening hallway dialogue freezes.',
        'working_exact_scene_baseline':'User confirms 0.7.2 passes this exact hallway on the same hardware.',
        'last_visible_line':{'id':names[1],'en':'Koichiro: "Oh, s-sorry..."'},
        'next_scripted_dialogue':{'id':names[2],'en':'Kasumi: "Oh..."'},
        'screenshot_observation':'First frame has Koichiro text/prompt. Later frame has Koichiro and Kasumi with no dialogue visible. These still images do not identify a blocking instruction.',
        'comparisons':compiled,'original_program_exact':True,'transition_span_exact':True,
        'nearby_English_streams_exact':True,
        'assessment':['The reported hallway freeze is present in the Native-only 0.7.6 midpoint and absent in the confirmed 0.7.2 baseline.',
                      'The next Kasumi wording, surrounding compiled English streams and original VM transition bytes are identical. No translation-content fix is justified by this comparison.',
                      'Runtime execution, allocations, scene-resource state and timing are not proven by identical script bytes. Root cause remains unconfirmed.',
                      'Treat mission-entry improvement and the later hallway failure as separate test observations; do not mark 0.7.27 fully working or rule out interactions.'],
        'next_midpoint':'0.7.4 rendering experiment, normalized to Native-only as 0.7.28; no 0.7.5 movie fit or 0.7.6 story/map changes.',
        'next_test':'Full DCP from original Japanese image, GDI output, cold boot on the same GDEMU/VGA hardware; advance past this exact hallway exchange.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    if not args.write:
        print('DRY RUN: compare the compiled hallway transition without changing a game build.');return
    report=check()
    path=ROOT/'docs/hardware-hallway-freeze.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: original VM transition and four nearby English streams match 0.7.2. Hardware cause unconfirmed.',flush=True)


if __name__=='__main__':main()
