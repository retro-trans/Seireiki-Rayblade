"""Check all ordinary story line widths and native pagination witnesses."""
import argparse,json,struct
from collections import Counter
from build_word_wrap_story import ROOT,VERSION,candidate_executable,digest
from scenario_word_wrap import wrap,tokens,font_bytes,command_payloads,TARGET_WIDTH,PEN_WIDTH,INLINE_FC
from english_text_codec import encode,decode
from test_scenario_pages import native_format,meaningful_tokens
from rayblade_codec import decompress


def main():
    global VERSION
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.12','0.1.13'])
    ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    VERSION=args.version
    print('Plan: all 50,273 compiled commands, literal goldens and native pagination/width witnesses.')
    if not args.verify:print('DRY RUN: no verification or report written');return
    font=font_bytes();exe,_=candidate_executable()
    reflow=lambda payload:wrap(payload,font,**({'safe_fc':INLINE_FC} if VERSION=='0.1.13' else {}))
    directory=ROOT/'work/output'/VERSION
    component=json.loads((directory/'text/scenario-component-report.json').read_text('utf-8'))
    archive=(directory/'D_SCE.AFS').read_bytes();assert digest(archive)==component['archive_sha256']
    actual={}
    for member in component['members']:
        off=member['archive_offset'];plain,used=decompress(archive[off+20:off+member['packed_bytes']])
        assert used==member['packed_bytes']-20 and digest(plain)==member['decoded_sha256']
        bank=member['bank_offset'];assert plain[bank:bank+8]==b'RBSCEN02'
        for i,row in enumerate(member['commands']):
            a,b,p=struct.unpack_from('<HHI',plain,bank+32+i*8)
            assert (a,b)==(row['source_offset'],row['source_bytes'])
            assert p==(row['english_offset']|(0x80000000 if row['word_wrapped'] else 0))
            start=row['english_offset'];payload=plain[start:start+row['english_bytes']]
            assert digest(payload)==row['english_sha256']
            actual[row['id']]=(payload,row['word_wrapped'])
    report=json.loads((ROOT/'work/output/0.1.11/genei-font-report.json').read_text('utf-8'))
    for name,bank in report['metrics'].items():
        assert max(g['source_bounds'][2]/4+2-g['advance'] for g in bank['glyphs'])<=TARGET_WIDTH-PEN_WIDTH
    # Literal expected line break, independent of the reflow implementation.
    greeting=encode('Ayaka: "Good morning, Touya Kazami."')
    result,stats=reflow(greeting)
    print('Opening greeting:',decode(result)[0])
    assert decode(result)==('Ayaka: "Good morning, Touya<NL>Kazami."',255)
    assert not stats['forced_word_breaks']
    wide=encode('W'*30);result,stats=reflow(wide)
    assert decode(result)==('W'*18+'<NL>'+'W'*12,255) and stats['forced_word_breaks']==1
    assert reflow(encode('i'*50))[0]==encode('i'*50),'Narrow letters should fit without character-count wrapping'
    control=bytes.fromhex('01fc843cfeff02ff')
    assert reflow(control)[0]==control and reflow(control)[1]['wrapped']==(VERSION=='0.1.13')
    counts=Counter(special_control_fallbacks=0);chosen={};maximum=0
    for member,row,payload in command_payloads():
        output,stats=reflow(payload);counts['commands']+=1
        assert actual[row['id']]==(output,stats['wrapped']),'Compiled component differs from measured reflow'
        counts['wrapped' if stats['wrapped'] else 'special_control_fallbacks']+=1
        if not stats['wrapped']:
            assert output==payload
            continue
        assert not stats['forced_word_breaks']
        line=[];width=0;glyphs=0
        for token in tokens(output,font):
            if token['kind']=='boundary':
                assert width<=PEN_WIDTH and glyphs<=127
                maximum=max(maximum,width);counts['lines']+=1
                line=[];width=0;glyphs=0
            else:
                line.append(token);width+=token['width'];glyphs+=token['kind']=='glyph'
        key=(stats['automatic_breaks']>0,b'\xfb' in output,b'\xfc' in output,payload.count(b'\xfe'))
        previous=chosen.get(key)
        if previous is None or len(output)>len(previous[2]):chosen[key]=(row['id'],payload,output)
    chosen['greeting']=('golden.greeting',greeting,reflow(greeting)[0])
    paragraph=encode(('One two three four five six seven eight nine ten. '*12))
    chosen['pagination']=('golden.pagination',paragraph,reflow(paragraph)[0])
    # Mode toggles survive inserted line/page controls; FC operands include
    # values resembling terminators in the unchanged special fallback case.
    mode=encode('<ASCII:ON>'+('narrow letters and words '*14)+'<ASCII:OFF>Medium text.')
    chosen['mode']=('golden.mode',mode,reflow(mode)[0])
    instructions=0;native=[]
    for key,(identity,original,payload) in chosen.items():
        output,steps=native_format(exe,payload,width=127,limit=8191,capacity=8192)
        assert meaningful_tokens(output)==meaningful_tokens(payload)
        instructions+=steps
        native.append({'id':identity,'input_bytes':len(payload),'output_bytes':len(output),'SH4_instructions':steps})
        if identity=='golden.pagination':assert output.count(b'\xfe')>0
        if identity=='golden.greeting':assert output==payload
    proof={'version':VERSION,'executable_sha256':digest(exe),'font_sha256':digest(font),
        'archive_sha256':digest(archive),
        'counts':dict(counts),'maximum_pen_width':maximum,'target_width':TARGET_WIDTH,
        'native_pagination_cases':len(native),'native_cases':native,'SH4_instructions':instructions,
        'checks':['Every current ordinary line fits the measured pen width and 127-character formatter budget',
            'Every rebuilt bank payload and high-bit mode flag matches the measured reference',
            'No current ordinary word split; non-space glyphs/modes/FC operands retained',
            str(counts['special_control_fallbacks'])+' special-control commands retain legacy wrapping',
            'Native pagination witnesses retain glyph/control bytes and ABI/guards'],
        'limits':['Live pixel fit and continuation prompts remain unverified','Inline effect behavior/timing and full gameplay remain pending']}
    print(json.dumps({k:v for k,v in proof.items() if k!='native_cases'},indent=2))
    if args.write_report:
        path=ROOT/'work/output'/VERSION/'word-wrap-native-test.json'
        path.write_text(json.dumps(proof,indent=2)+'\n','utf-8');print('Wrote',path)


if __name__=='__main__':main()
