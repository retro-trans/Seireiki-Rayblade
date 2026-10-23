"""Compile font-measured story wrapping and matching native hook for 0.1.12.

Default dry run. Only compiled presentation whitespace and the lookup mode
change; original VM prefixes and working translations stay byte-exact.
"""
import argparse,copy,json,struct
from collections import Counter
from build_genei_font import ROOT,digest
from build_scenario_translation import align,SCRIPT_CAPACITY,SCRATCH_CAPACITY,BANK_POINTER_OFFSET
from build_scenario_patch import LOADER,FORMATTER,BASE,loader_code,formatter_code
from scenario_word_wrap import wrap,font_bytes,TARGET_WIDTH,PEN_WIDTH,INLINE_FC
from rayblade_codec import compress,decompress
from prs_optimal import compress_dynamic

VERSION='0.1.12'
BANK_MAGIC=b'RBSCEN02'
PACK_MAGIC=b'RBS2'
WRAP_FLAG=0x80000000


def candidate_executable():
    base=ROOT/'work/output/0.1.11'
    manifest=json.loads((base/'font4x-patch.json').read_text('utf-8'))
    original=(base/'1ST_READ.BIN').read_bytes()
    assert digest(original)==manifest['files']['1ST_READ.BIN']['target_sha256']
    target=bytearray(original);edits=[]
    for address,before,after in [(LOADER,loader_code(),loader_code(pack_magic=PACK_MAGIC)),
        (FORMATTER,formatter_code(),formatter_code(bank_magic=BANK_MAGIC,word_wrap=True))]:
        off=address-BASE
        assert target[off:off+len(before)]==before
        assert not any(target[off+len(before):off+0x400])
        assert len(after)<0x400
        target[off:off+0x400]=after+b'\0'*(0x400-len(after))
        edits.append({'offset':hex(off),'code_bytes':len(after),'before_sha256':digest(before),'after_sha256':digest(after)})
    allowed=set(range(0x8800,0x9000))
    assert {i for i,(a,b) in enumerate(zip(original,target)) if a!=b}<=allowed
    return bytes(target),{'version':VERSION,'base_executable_sha256':digest(original),
        'executable_sha256':digest(target),'edits':edits,'pack_magic':PACK_MAGIC.decode(),
        'bank_magic':BANK_MAGIC.decode(),'word_wrap_offset_flag':hex(WRAP_FLAG),
        'wrapped_formatter_columns':127,'special_control_formatter_columns':30,
        'original_source_consumption':'retained; original VM prefix/address and instruction operands unchanged'}


def compose(*,version=VERSION):
    base=ROOT/'work/output/0.1.11';font=font_bytes()
    original_component=json.loads((base/'text/scenario-component-report.json').read_text('utf-8'))
    source=(base/'D_SCE.AFS').read_bytes()
    assert digest(source)==original_component['archive_sha256']
    for name,sha in original_component['working_file_sha256'].items():
        assert digest((ROOT/'work/translation/en/scenario'/name).read_bytes())==sha
    exe,patch=candidate_executable()
    patch['version']=version
    inline_proof=None;inline_cases={}
    if version=='0.1.13':
        inline_path=ROOT/'work/output/0.1.12/inline-control-native-test.json'
        inline_proof=json.loads(inline_path.read_text('utf-8'))
        assert inline_proof['executable_sha256']==digest(exe) and inline_proof['font_sha256']==digest(font)
        assert inline_proof['commands']==166
        inline_cases={case['id']:case for case in inline_proof['cases']}
    observed_inline=set()
    count=struct.unpack_from('<I',source,4)[0];header_end=align(8+count*8+8)
    archive=bytearray(source[:header_end]);members=[];totals=Counter(word_wrapped_commands=0,special_control_commands=0,automatic_breaks=0);fallbacks=[];encoded=[]
    for old in original_component['members']:
        off=old['archive_offset'];prior,used=decompress(source[off+20:off+old['packed_bytes']])
        assert digest(prior)==old['decoded_sha256'] and used==old['packed_bytes']-20
        original=prior[:old['original_bytes']]
        assert digest(original)==old['original_sha256']
        plain=bytearray(original);plain.extend(b'\0'*(align(len(plain),4)-len(plain)))
        bank=len(plain);n=len(old['commands'])
        plain.extend(struct.pack('<8s6I',BANK_MAGIC,len(original),n,0,old['index'],8,1))
        table=len(plain);plain.extend(b'\0'*(n*8));records=[]
        for i,r in enumerate(old['commands']):
            p=r['english_offset'];payload=prior[p:p+r['english_bytes']]
            assert digest(payload)==r['english_sha256']
            wrapped,stats=wrap(payload,font,**({'safe_fc':INLINE_FC} if inline_proof else {}))
            if r['id'] in inline_cases:
                witness=inline_cases[r['id']]
                assert digest(payload)==witness['source_sha256'] and digest(wrapped)==witness['reflowed_sha256']
                observed_inline.add(r['id'])
            assert not stats['forced_word_breaks'],'Current ordinary words should fit without splitting'
            location=len(plain);entry_offset=location|(WRAP_FLAG if stats['wrapped'] else 0)
            struct.pack_into('<HHI',plain,table+i*8,r['source_offset'],r['source_bytes'],entry_offset)
            plain.extend(wrapped)
            record={**r,'english_offset':location,'english_bytes':len(wrapped),'english_sha256':digest(wrapped),
                'unwrapped_english_sha256':digest(payload),'word_wrapped':stats['wrapped'],
                'automatic_breaks':stats['automatic_breaks']}
            records.append(record)
            totals['word_wrapped_commands' if stats['wrapped'] else 'special_control_commands']+=1
            totals['automatic_breaks']+=stats['automatic_breaks']
            if not stats['wrapped']:fallbacks.append({'id':r['id'],'FC':stats['unsupported_FC']})
        plain.extend(b'\0'*(align(len(plain),4)-len(plain)))
        struct.pack_into('<I',plain,bank+16,len(plain))
        assert plain[:len(original)]==original and len(plain)<=BANK_POINTER_OFFSET
        packed=compress(plain);assert decompress(packed)==(bytes(plain),len(packed))
        wrapped=struct.pack('<4s4I',PACK_MAGIC,len(plain),len(packed),old['index'],bank)+packed
        assert align(len(wrapped))<=SCRATCH_CAPACITY
        encoded.append([bytes(plain),wrapped])
        for i,r in enumerate(records):
            a,b,c=struct.unpack_from('<HHI',plain,table+i*8)
            assert (a,b,c)==(r['source_offset'],r['source_bytes'],r['english_offset']|(WRAP_FLAG if r['word_wrapped'] else 0))
        members.append({**old,'decoded_bytes':len(plain),'decoded_sha256':digest(plain),
            'packed_bytes':len(wrapped),'packed_sha256':digest(wrapped),'bank_offset':bank,
            'archive_offset':0,'commands':records})
        if (old['index']+1)%50==0:print('Reflowed members:',old['index']+1,'/447',flush=True)
    off,size=struct.unpack_from('<II',source,8+447*8);listing=source[off:off+size]
    projected=lambda:header_end+sum(align(len(pair[1])) for pair in encoded)+len(listing)
    optimized=[]
    # Recover only the few sectors required, prioritizing members just over
    # sector boundaries. This changes PRS token choices, never decoded bytes.
    for index in sorted(range(len(encoded)),key=lambda i:len(encoded[i][1])%2048 or 2048):
        if projected()<=len(source):break
        plain,prior=encoded[index];packed=compress_dynamic(plain)
        revised=struct.pack('<4s4I',PACK_MAGIC,len(plain),len(packed),index,members[index]['bank_offset'])+packed
        if len(revised)>=len(prior):continue
        encoded[index][1]=revised;members[index].update(packed_bytes=len(revised),packed_sha256=digest(revised),dynamic_PRS=True)
        optimized.append({'member':members[index]['name'],'prior_bytes':len(prior),'optimized_bytes':len(revised),
            'sectors_saved':(align(len(prior))-align(len(revised)))//2048})
        print('Dynamic PRS:',members[index]['name'],len(prior),'->',len(revised),'projected',projected(),flush=True)
    for member,(_,wrapped) in zip(members,encoded):
        location=align(len(archive));archive.extend(b'\0'*(location-len(archive)));archive.extend(wrapped)
        struct.pack_into('<II',archive,8+member['index']*8,location,len(wrapped));member['archive_offset']=location
    location=align(len(archive));archive.extend(b'\0'*(location-len(archive)));archive.extend(listing)
    struct.pack_into('<II',archive,8+447*8,location,len(listing));used=len(archive)
    assert used<=len(source),('Reflowed archive exceeds original extent',used,len(source))
    archive.extend(b'\0'*(len(source)-len(archive)))
    component=copy.deepcopy(original_component)
    assert observed_inline==set(inline_cases)
    component.update(version=version,kind='font-measured story wrapping candidate; native verification pending',
        archive_sha256=digest(archive),used_archive_bytes=used,
        spare_archive_bytes=len(source)-used,members=members,
        maximum_decoded_member_bytes=max(m['decoded_bytes'] for m in members),
        maximum_packed_member_bytes=max(m['packed_bytes'] for m in members),
        maximum_sector_read_bytes=max(align(m['packed_bytes']) for m in members),
        bank_magic=BANK_MAGIC.decode(),pack_magic=PACK_MAGIC.decode(),entry_offset_wrap_flag=hex(WRAP_FLAG),
        dynamic_PRS_members=optimized,
        word_wrap={'font_sha256':digest(font),'target_width':TARGET_WIDTH,'maximum_pen_width':PEN_WIDTH,
            **dict(totals),'forced_word_breaks':0,'special_control_fallbacks':fallbacks,
            'whitespace':'Automatic line breaks replace spaces in compiled presentation only; all other glyph/control bytes and original FE boundaries retained',
            'working_translation_rows':'unchanged','native_verification':'pending','live_verification':'pending'})
    if inline_proof:
        component['word_wrap'].update(inline_control_commands_reflowed=len(inline_cases),
            inline_FC_subtypes=[hex(v) for v in sorted(INLINE_FC)],
            inline_control_proof_sha256=digest((ROOT/'work/output/0.1.12/inline-control-native-test.json').read_bytes()),
            inline_scope='Native parser/dispatch/cursor comparison; glyph drawing and effect/GPU callees are bounded stubs')
    manifest=copy.deepcopy(json.loads((base/'font4x-patch.json').read_text('utf-8')))
    manifest.update(version=version,previous_build='0.1.12' if inline_proof else '0.1.11',status='measured story word wrapping candidate; native/live checks pending')
    manifest['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    manifest['files']['D_SCE.AFS']['target_sha256']=digest(archive)
    manifest['scenario'].update(version=version,archive_sha256=digest(archive),word_wrap=component['word_wrap'],
        bank_magic=BANK_MAGIC.decode(),pack_magic=PACK_MAGIC.decode(),entry_offset_wrap_flag=hex(WRAP_FLAG))
    files={'1ST_READ.BIN':exe,'WIN00.AFS':(base/'WIN00.AFS').read_bytes(),'D_SCE.AFS':bytes(archive)}
    for path in (base/'text').iterdir():
        if path.is_file():files['text/'+path.name]=path.read_bytes()
    files['text/D_SCE.AFS']=bytes(archive)
    files['text/scenario-component-report.json']=json.dumps(component,indent=2).encode()
    for name in ('library-native-test.json','library-patch-report.json','archive-repack-report.json','FONT-LICENSE.txt','genei-font-report.json'):
        files[name]=(base/name).read_bytes()
    if inline_proof:
        tested=ROOT/'work/output/0.1.12'
        for name in ('inline-control-native-test.json','battle-english-native-test.json','genei-font-native-test.json','genei-surface-native-test.json'):
            raw=(tested/name).read_bytes();proof=json.loads(raw)
            assert proof['executable_sha256']==digest(exe)
            files[name]=raw
        assert files['WIN00.AFS']==(tested/'WIN00.AFS').read_bytes()
        for name in ('D_NAMES.BIN','D_BMESS.BIN'):
            assert files['text/'+name]==(tested/'text'/name).read_bytes()
        manifest['native_proof_reuse']={'tested_executable_version':'0.1.12','exact_executable_sha256':digest(exe),
            'font_names_library_battle':'Byte-exact; native proofs retain their original tested versions',
            'story_component':'Changed; fresh loader/lookup/formatter/pagination checks required'}
    return files,manifest,component,patch


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true')
    ap.add_argument('--version',default=VERSION,choices=['0.1.12','0.1.13']);args=ap.parse_args()
    files,manifest,component,patch=compose(version=args.version)
    print(json.dumps({k:v for k,v in component.items() if k not in ('members','working_file_sha256','source_member_sha256','word_wrap')},indent=2))
    print('Wrapping:',json.dumps({k:v for k,v in component['word_wrap'].items() if k!='special_control_fallbacks'},indent=2))
    print('Executable:',json.dumps(patch))
    if not args.write:print('DRY RUN: no candidate files written');return
    out=ROOT/'work/output'/args.version;out.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
    (out/'scenario-patch-report.json').write_text(json.dumps(patch,indent=2)+'\n','utf-8')
    cp=ROOT/'CHANGELOG.md';old=cp.read_text('utf-8')
    entry='''## 0.1.12 — measured ordinary-story word wrapping

- Reflowed 50,107 complete English story commands using the integrated GenEi advance tables, targeting a 240-logical-pixel line with four pixels reserved for ink/shadow overhang. 40,193 automatic breaks replace compiled spaces. No current ordinary word requires splitting; no non-space glyph, mode, FC operand or original FE boundary is discarded. Working translation rows and all 447 original VM prefixes remain byte-exact.
- A high bit in the bank lookup offset marks prewrapped streams; the native hook clears it before pointer arithmetic and uses a wider legacy formatter budget solely to preserve the precomputed word breaks. Original three-line pagination and source-byte VM advancement remain native. RBS2/RBSCEN02 distinguish this component format. All 166 special-display-control commands retain their original formatter behavior until their geometry is decoded; held original commands stay untranslated.
- Added bit-cost dynamic PRS parsing with bounded match search for four members near sector boundaries. Their decoded bytes remain exact, recovering four sectors and fitting the complete rebuilt archive into its original extent with 208 spare bytes. No translation is shortened to meet the archive limit.
- Candidate archive/executable prepared for native verification. GenEi glyphs, font renderer, ordered WIN00 layout, menu/name/library/battle payloads and allocations are retained. Packaging, live fit, special-control layout, full VM coverage, held passages, independent meaning review and remaining image UI/movie text are unfinished. Original dump/prior builds unchanged; no release.

'''
    if args.version=='0.1.13':
        entry='''## 0.1.13 — word wrapping for inline-effect dialogue

- Extended font-measured wrapping to all 50,273 complete English story commands, including the 166 previously excluded inline-effect/control commands. Original working rows, all non-space glyph/control operands, original FE boundaries and all 447 VM prefixes remain intact. The 503 held rows remain untranslated; no new draft credit is claimed.
- Native parser/handler comparison covers all 166 commands: original and reflowed text consume the same complete FC operands and dispatch identical effect arguments/resume states, with reflowed cursors inside the 236-pixel pen width and three-line window. Glyph drawing and effect/GPU callees are bounded stubs; actual callback behavior, timing and gameplay remain unverified.
- Executable, GenEi font, WIN00 layout, name/menu/library/battle bytes and allocations are byte-exact 0.1.12. Their proofs retain the original tested version after exact hash checks. Rebuilt story archive, loader/lookup/formatter regressions, packaging and live validation remain separate required checks. Original dump/prior builds unchanged; no release.

'''
        if '## 0.1.13 —' not in old:cp.write_text(old.replace('## 0.1.12 —',entry+'## 0.1.12 —',1),'utf-8')
    elif '## 0.1.12 —' not in old:cp.write_text(old.replace('## 0.1.11 —',entry+'## 0.1.11 —',1),'utf-8')
    print('Wrote word-wrapping candidate components:',out)


if __name__=='__main__':main()
