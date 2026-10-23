"""Record verified all-dialogue reflow, exact-font specimen and changelog. Dry first."""
import argparse,json,shutil
from PIL import Image,ImageDraw
import numpy as np
from build_dialogue_reflow import ROOT,OUT,VERSION,PRIOR,digest
from build_antialias_font import font_bytes
from test_outline_font import legacy_mask


def read(path):return json.loads(path.read_text('utf-8'))


def prepare():
    out=ROOT/'work/output'/VERSION;disc=read(out/'english-disc-report.json')
    component=read(OUT/'component-report.json');proof=read(out/'dialogue-reflow-native-test.json')
    assert disc['validation']['reextracted_files']=='all 14 exact'
    assert disc['validation']['changed_sector_EDC_ECC']=='pass' and disc['validation']['unrelated_track_bytes']=='all unchanged'
    assert disc['validation']['track_bytes_compared']==1188856032
    assert disc['dialogue_reflow_proof_sha256']==digest((out/'dialogue-reflow-native-test.json').read_bytes())
    for name,row in disc['files'].items():
        raw=(out/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)).read_bytes()
        assert len(raw)==row['size'] and digest(raw)==row['sha256']
    summary={'version':VERSION,'source_build':PRIOR,'date':'2026-10-24',
        'status':'All inserted English dialogue reflowed; local package and offline native gates pass; live reading-flow test pending',
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        'story':component['story'],'embedded':component['embedded'],'battle':component['battle'],
        'font_sha256':component['font_sha256'],'maximum_pen_width':proof['maximum_pen_width'],
        'samples':component['samples'],'files':disc['files'],'validation':disc['validation'],
        'native_proof':f'work/output/{VERSION}/dialogue-reflow-native-test.json',
        'native_proof_sha256':disc['dialogue_reflow_proof_sha256'],'native_limits':proof['limits'],
        'sector_substitutions':disc['new_changed_sectors'],'wording_changes':0,'new_translation_credit':0,
        'held_source_commands':'unchanged; no translation or reflow applied','release':False}
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,stage='Current-font reflow of all inserted English dialogue packaged locally; live testing and translation review pending')
    status['latest_dialogue_reflow_build']=summary
    archive=read(ROOT/'docs/native-archive-layout.json')
    archive['archives']['D_SCE.AFS']={'current_build':VERSION,'archive_sha256':disc['files']['D_SCE.AFS']['sha256'],
        'member_count':448,'native_lookups':'All 448 offsets/sector lengths match physical layout',
        'source_VM_prefixes':'all 447 exact','evidence':summary['native_proof']}
    ui={'version':VERSION,'reported_command':'scenario.s_002.o00526','source_screenshot':'dialogue-before.png',
        'logical_viewport':{'text_left':64,'pen_width':236,'line_height':16,'lines_per_page':3},
        'font_source':'Original Skies font; font and renderer unchanged from 0.1.40',
        'samples':component['samples'],'comparison':'dialogue-flow-comparison.png; decoded-font diagnostic, not an in-game screenshot'}
    policy={'version':VERSION,'font_sha256':component['font_sha256'],'pen_width':236,'texture_dimension_cap':1024,
        'apply_to':'All inserted English story, embedded and battle dialogue',
        'source_rows':'Retain original rows and wording; reflow compiled presentation only',
        'line_policy':'Join obsolete single line breaks; preserve double-break paragraphs and original FE page breaks',
        'word_policy':'Wrap at spaces using measured advances; never force word splitting',
        'controls':'Preserve every non-layout operand in exact relative order; three-line automatic pagination',
        'implementation':'tools/dialogue_reflow.py','build':'tools/build_dialogue_reflow.py'}
    note=f'''## {VERSION} — reflow all inserted English dialogue for the current font

- Replaced obsolete single line breaks with measured whole-word wrapping at the current Skies font's 236-logical-pixel pen width. Audited all 50,273 story commands, all 13 embedded commands and all 5,516 battle selection spans. Changed 29,671 story commands, 12 embedded commands and 1,420 battle spans; other layouts already matched. The reported Forzen speech no longer isolates “it threatened” or “destruction,” on their own lines.
- Preserved every word and non-layout glyph/control operand, explicit original FE page break, blank paragraph, pause/effect order, original VM prefix/address, selection condition, random choice, alias and working translation row. Normal story pagination remains native. Added one automatic page turn to a battle message that otherwise occupied four lines, matching the native formatter's three-line rule. No forced mid-word splits, wording edits, new translation credit or changes to held source commands.
- Fresh checks pass all 50,273 native bank lookups, 448 archive member lookups, representative native story loading/formatting/VM witnesses, all 166 inline-effect comparisons, 52 cold/warm embedded formatter/VM cases, 6,034 battle selections, 128 battle roots, 256 battle workspace cases and native battle PRS. Every inserted stream is audited for measured width, word/control preservation and source fingerprints. Battle outputs are checked after branch concatenation; all battle pages fit three lines. Bounded I/O, allocation/cache, glyph/effect/GPU and RNG fixtures and selective native formatting retain their documented limits. Live reading flow, callback timing and whole-game navigation remain pending.
- Packaged {disc['new_changed_sectors']:,} sector substitutions over 0.1.40. All fourteen payloads re-extract exactly, changed-sector EDC/ECC passes and complete 1,188,856,032-byte track comparison preserves unrelated bytes. Eleven other payloads, including the Skies font, library, memory-card labels, album captions, UI artwork and movies, remain exact. Executable instructions remain unchanged; only existing embedded English payload slots differ. Historical proofs keep their actual tested executable identities. No public release or prior-build replacement.
- Fresh-boot the 0.1.41 GDI and load a normal in-game save to test story/battle pages. Emulator save states can retain old compiled dialogue.

'''
    return summary,[(ROOT/'docs/dialogue-reflow.json',summary),(ROOT/'docs/translation-status.json',status),
        (ROOT/'docs/native-archive-layout.json',archive),(ROOT/f'work/ui/{VERSION}/dialogue-layout.json',ui),
        (ROOT/'work/translation/en/dialogue-layouts-current.en.json',policy)],note


def preview():
    sample=next(s for s in read(OUT/'component-report.json')['samples'] if s['id']=='scenario.s_002.o00526')
    font=font_bytes((ROOT/'work/output'/PRIOR/'WIN00.AFS').read_bytes())[1]
    from build_font4x_patch import MEDIUM
    canvas=Image.new('RGBA',(1040,540),'#17191d');draw=ImageDraw.Draw(canvas)
    draw.text((24,10),'Decoded-font layout comparison; not a Flycast screenshot',fill='white')
    for n,(label,lines) in enumerate([
        ('0.1.40 - reported page with obsolete breaks',sample['before'].split('\n')[6:9]),
        ('0.1.41 - reflowed continuation page',sample['after'].split('\n')[3:6])]):
        base=42+n*246;draw.text((24,base),label,fill='white')
        for y,text in enumerate(lines):
            x=0
            for ch in text:
                mask=Image.fromarray(legacy_mask(font,ch,False))
                ink=Image.new('RGBA',mask.size,'white');ink.putalpha(mask)
                canvas.alpha_composite(ink,(24+x*4,base+25+y*64));x+=font[0xa0+MEDIUM.index(ch)]
    return canvas.convert('RGB')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    summary,updates,note=prepare()
    print('Verified',VERSION,';',summary['sector_substitutions'],'sector edits; all inserted English dialogue.')
    print('Records:',[str(p.relative_to(ROOT)) for p,_ in updates]);print(note.splitlines()[:3])
    if not args.write:print('DRY RUN: no records or previews written.');return
    for path,value in updates:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n','utf-8')
    folder=ROOT/f'work/ui/{VERSION}'
    shutil.copyfile('C:/Users/Binh/AppData/Local/Temp/codex-clipboard-32da064a-0a22-4261-b10b-d32fb4864a3d.png',folder/'dialogue-before.png')
    preview().save(folder/'dialogue-flow-comparison.png')
    path=ROOT/'CHANGELOG.md';old=path.read_text('utf-8')
    if note.splitlines()[0] not in old:path.write_text(old.replace('# Change log\n\n','# Change log\n\n'+note,1),'utf-8')
    agents=ROOT/'AGENTS.md';old=agents.read_text('utf-8')
    preference='- Dialogue layout: reflow compiled presentation for all translated story, embedded and battle dialogue using the current font widths. Join obsolete single line breaks, wrap whole words, and preserve wording, blank paragraphs, explicit page breaks and pause/effect controls. Keep working translation rows intact. Current implementation: tools/dialogue_reflow.py (236 logical pen pixels); record: docs/dialogue-reflow.json.'
    if preference not in old:agents.write_text(old.rstrip()+'\n'+preference+'\n','utf-8')
    print('Recorded dialogue policy, exact-font comparison, build status and changelog.')


if __name__=='__main__':main()
