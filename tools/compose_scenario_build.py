"""Compose verified story candidate with inherited 0.1.6 components. Dry first."""
import argparse,copy,json
from build_font_patch import ROOT
from build_scenario_patch import candidate_executable
from build_scenario_translation import VERSION,digest


def compose():
    base=ROOT/'work/output/0.1.6';out=ROOT/'work/output'/VERSION
    manifest=json.loads((base/'font4x-patch.json').read_text('utf-8'))
    original_exe=(base/'1ST_READ.BIN').read_bytes();exe,patch=candidate_executable()
    assert digest(original_exe)==manifest['files']['1ST_READ.BIN']['target_sha256']
    assert (out/'1ST_READ.BIN').read_bytes()==exe
    archive=(out/'text/D_SCE.AFS').read_bytes()
    component=json.loads((out/'text/scenario-component-report.json').read_text('utf-8'))
    story=json.loads((out/'scenario-native-test.json').read_text('utf-8'))
    battle=json.loads((out/'battle-english-native-test.json').read_text('utf-8'))
    assert story['archive_sha256']==component['archive_sha256']==digest(archive)
    assert story['executable_sha256']==battle['executable_sha256']==digest(exe)
    assert story['native_lookup_cases']==component['english_commands']==50273
    assert battle['component_sha256']==manifest['battle']['decoded_sha256']
    assert battle['text_spans_witnessed']==5516 and battle['condition_outcomes_witnessed']==412
    for name,sha in component['working_file_sha256'].items():
        assert digest((ROOT/'work/translation/en/scenario'/name).read_bytes())==sha
    inherited=[]
    for hook in manifest['hooks']:
        off,length=hook['offset'],hook['length']
        assert exe[off:off+length]==original_exe[off:off+length],hook['purpose']
        inherited.append({'offset':hex(off),'bytes':length,'purpose':hook['purpose']})
    for lo,hi,label in [(0x6ac64,0x6b252,'original text parser'),(0x6bf00,0x6c32a,'library filter'),
        (0x10e9e,0x10ee4,'names loader'),(0x104b4,0x104b8,'shared library allocation')]:
        assert exe[lo:hi]==original_exe[lo:hi],label
        inherited.append({'offset':hex(lo),'bytes':hi-lo,'purpose':label})
    files={'1ST_READ.BIN':exe,'D_SCE.AFS':archive}
    for name,info in manifest['files'].items():
        if name=='1ST_READ.BIN':continue
        raw=(base/name).read_bytes();assert digest(raw)==info['target_sha256'];files[name]=raw
    copied={}
    for path in (base/'text').iterdir():
        if path.is_file():copied['text/'+path.name]=path.read_bytes()
    copied['library-native-test.json']=(base/'library-native-test.json').read_bytes()
    result=copy.deepcopy(manifest);result.update(version=VERSION,previous_build='0.1.6',
        status='local English story/menu/name/library/battle integration; gameplay/layout validation pending')
    result['files']['1ST_READ.BIN']['target_sha256']=digest(exe)
    result['files']['D_SCE.AFS']={'source_sha256':component['source_archive_sha256'],'target_sha256':digest(archive)}
    result['scenario']={k:v for k,v in component.items() if k not in
        ('members','working_file_sha256','source_member_sha256','checks','kind','pending')}
    result['scenario'].update(original_script_base=patch['original_script_base'],
        combined_heap_bytes=patch['combined_heap_bytes'],executable_sha256=digest(exe),
        source_prefixes='all 447 exact at original offsets/addresses',
        inherited_code_byte_checks=inherited,
        pending=['Actual file I/O, memory, cache and save/load checks','Event navigation and measured dialogue layout',
                 'Full VM text coverage, held passages and independent meaning review'])
    result['battle']['native_validation']={k:battle[k] for k in ['native_selection_cases','native_root_cases',
        'workspace_cases','SH4_selection_instructions','SH4_workspace_instructions','maximum_single_output_bytes']}
    return files,copied,result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    files,copied,manifest=compose()
    print('Composed:',json.dumps({name:{'bytes':len(raw),'sha256':digest(raw)} for name,raw in files.items()},indent=2))
    print('Inherited code byte checks:',len(manifest['scenario']['inherited_code_byte_checks']))
    print('Story:',manifest['scenario']['english_commands'],'English commands;',manifest['scenario']['held_rows'],'held rows; native proofs match executable.')
    if not args.write:print('DRY RUN: no composed components written.');return
    out=ROOT/'work/output'/VERSION
    for name,raw in {**files,**copied}.items():
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    (out/'font4x-patch.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
    print('Wrote composed local components; test disc still requires packaging.')


if __name__=='__main__':main()
