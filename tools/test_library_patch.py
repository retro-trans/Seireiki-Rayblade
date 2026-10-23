"""Execute native library filtering with independent expected English pages.

Uses all unlock combinations per physical profile, plus scrolling windows.
Expected English bytes come independently from source-linked section drafts.
Default is read-only; --write-report saves English-only verification metadata.
"""
import argparse
import itertools
import json
import hashlib
from build_font_patch import ROOT,BASE
from build_library_patch import build,DISPLAY_CAPACITY
from english_text_codec import encode
from test_font_patch import CPU


def filtered_page(exe,payload,enabled,skip,lines):
    source=0x8c500000;target=0x8c600000;guard=32
    # Full-profile tests use a larger inspection destination. Actual six/
    # seven-line windows are checked inside the original 512-byte buffer.
    capacity=2048 if lines==255 else DISPLAY_CAPACITY
    cpu=CPU(exe,b'',0,0)
    cpu.regions=[(BASE,bytearray(exe)),(source,bytearray(payload)),
                 (target-guard,bytearray(b'\xa5'*(capacity+2*guard))),
                 (0x8c1df52c,bytearray(512)),cpu.regions[-1]]
    for flag in enabled:
        bit=(flag&0x3ff)+0x400
        cpu.write(0x8c1df52c+bit//8,cpu.read(0x8c1df52c+bit//8,1)|(1<<(7-bit%8)),1)
    cpu.reg[4:8]=[skip,lines,target,source];saved=cpu.reg[8:]
    cpu.pc=0x8c07bf00
    for count in range(400_000):
        if cpu.pc==0xdead0000:break
        cpu.pc=cpu.execute(cpu.pc)
    else:raise ValueError('Native profile filter instruction limit')
    if cpu.reg[8:]!=saved:raise ValueError('Native filter changed preserved registers/stack')
    memory,offset=cpu.area(target,capacity)
    # English library spans have only printable glyphs and NL; unlock
    # controls are removed by the native filter before returning a page.
    tail=bytes(memory[offset:offset+capacity]);end=tail.index(b'\xff')+1
    if memory[:guard]!=b'\xa5'*guard or memory[offset+end:]!=b'\xa5'*(capacity-end+guard):
        raise ValueError('Native library page exceeded output/guard bounds')
    return tail[:end],cpu.reg[0],count


def reference_window(text,skip,lines):
    parts=text.split(b'\xfd')
    if skip>=len(parts):return b'\xff',0xffffffff
    chosen=parts[skip:skip+lines]
    more=skip+lines<len(parts)
    return b'\xfd'.join(chosen)+(b'\xfd' if more else b'')+b'\xff',int(more)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
    files,manifest,report=build();exe=files['1ST_READ.BIN']
    entries=json.loads((ROOT/'work/source/library/entries.json').read_text(encoding='utf-8'))
    translations={r['id']:r for r in json.loads((ROOT/'work/translation/en/library/library.json').read_text(encoding='utf-8'))}
    library=(ROOT/'work/output/0.1.3/text/D_PAPER.en.dec.bin').read_bytes()
    profiles=json.loads((ROOT/'work/output/0.1.3/text/library-component-report.json').read_text())['profiles']
    by_id={e['id']:e for e in entries};cases=0;instructions=0;maximum=0;worst=None;page_maximum=0;page_worst=None
    for number,profile in enumerate(profiles):
        entry=by_id[profile['id']];header=len(bytes.fromhex(entry['header_hex']))
        start=profile['new_offset']+header;payload=library[start:profile['new_offset']+profile['bytes']]
        gates=sorted({g for s in entry['sections'] for g in s['conditions']})
        if any(g>>8!=0x35 for g in gates):raise ValueError('Review new conditional operator before testing')
        choices=list(itertools.product([False,True],repeat=len(gates)))
        for values in choices:
            enabled={g for g,v in zip(gates,values) if v};chunks=[]
            for n,section in enumerate(entry['sections']):
                if not all(g in enabled for g in section['conditions']):continue
                lines=[translations[entry['id']+'.s{:02d}.l{:02d}'.format(n,k)]['en']
                       for k in range(len(section['text'].split('<NL>')))]
                chunks.append(encode('<NL>'.join(lines))[:-1])
            full=b''.join(chunks)
            # Full visibility checks every gate outcome; page-size and skip
            # checks below exercise every scrolling start with all gates set.
            windows=[(0,255)]
            if all(values):windows += [(skip,height) for height in (6,7) for skip in range(full.count(b'\xfd')+2)]
            for skip,height in windows:
                expected,returned=reference_window(full,skip,height)
                actual,code,count=filtered_page(exe,payload,enabled,skip,height)
                if (actual,code)!=(expected,returned):raise ValueError('Native library page differs: '+entry['id']+' '+str((values,skip,height)))
                if len(actual)>maximum:maximum=len(actual);worst={'profile':entry['id'],'skip':skip,'lines':height}
                if height in (6,7) and len(actual)>page_maximum:
                    page_maximum=len(actual);page_worst={'profile':entry['id'],'skip':skip,'lines':height}
                cases+=1;instructions+=count
        if (number+1)%50==0:print('Verified {} physical records, {} native filter cases.'.format(number+1,cases),flush=True)
    result={'version':'0.1.4','native_filter_cases':cases,'native_filter_instructions':instructions,
            'library_component_sha256':hashlib.sha256(library).hexdigest(),
            'filter_function_sha256':hashlib.sha256(exe[0x6bf00:0x6c32a]).hexdigest(),
            'physical_records':len(profiles),'all_unlock_combinations':'pass','scroll_windows_six_and_seven_lines':'pass',
            'maximum_output_bytes_including_full_profile_test':maximum,'maximum_case':worst,
            'maximum_six_or_seven_line_page_bytes':page_maximum,'maximum_page_case':page_worst,
            'output_capacity':DISPLAY_CAPACITY,'guards':'unchanged','viewer_stack_frames':'unchanged',
            'remaining':'Actual screen layout, memory allocation at runtime, library navigation and long-session behavior need in-game checks'}
    print(json.dumps(result,indent=2),flush=True)
    if args.write_report:
        out=ROOT/'work/output/0.1.4';out.mkdir(parents=True,exist_ok=True)
        (out/'library-native-test.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('Saved native library verification metadata.')


if __name__=='__main__':main()
