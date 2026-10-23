"""Record verified 0.1.40 build, UI witnesses, comparison and changelog. Dry first."""
import argparse
import json
import shutil
import numpy as np
from PIL import Image,ImageDraw

from build_memory_album_patch import ROOT, OUT, VERSION, PRIOR, compose, digest
from build_album_caption_overlay import compose as album


def read(path): return json.loads(path.read_text('utf-8'))


def prepare():
    out=ROOT/'work/output'/VERSION
    files,decoded,recipe,component,names_report=compose()
    report=read(out/'english-disc-report.json');proof=read(out/'memory-album-native-test.json')
    assert report['validation']['reextracted_files']=='all 14 exact'
    assert report['validation']['changed_sector_EDC_ECC']=='pass'
    assert report['validation']['unrelated_track_bytes']=='all unchanged'
    assert report['validation']['track_bytes_compared']==1188856032
    assert digest((out/'memory-album-native-test.json').read_bytes())==report['memory_album_proof_sha256']
    for name,record in report['files'].items():
        path=out/('text/'+name if name in ('D_NAMES.BIN','D_BMESS.BIN') else name)
        raw=path.read_bytes();assert digest(raw)==record['sha256'] and len(raw)==record['size']
    assert all(report['files'][name]['sha256']==digest(raw) for name,raw in files.items())
    assert proof['geometry']['native_bounds_and_normalized_UVs']=='pass'
    summary={'version':VERSION,'source_build':PRIOR,'date':'2026-10-24',
        'status':'Local test build packaged and offline gates pass; fresh-boot UI/album testing pending',
        'disc':f'work/output/{VERSION}/disc/Rayblade English Test {VERSION}.gdi',
        'memory_card_changes':component['memory_card_changes'],
        'album':{k:component[k] for k in ('captions','protected_photos','protected_Coming_Soon_cells',
            'caption_texture_dimensions','caption_textures','caption_pixel_size','logical_caption_size',
            'new_caption_texture_bytes','method','font_source','sprite_UV_units')},
        'files':report['files'],'proof':f'work/output/{VERSION}/memory-album-native-test.json',
        'proof_sha256':report['memory_album_proof_sha256'],
        'dispatch_cases':1356,'geometry_cases':448,'UI_cases':23,'archive_lookup_cases':251,
        'PRS_streams':36,'native_limits':proof['limits'],'validation':report['validation'],
        'sector_substitutions':report['new_changed_sectors'],
        'translation_counts_unchanged':True,'release':False,
        'user_feedback_on_previous_font':'User said the original Skies port looks great; current screenshots identify slot/header overflow and low-detail album captions.'}
    status=read(ROOT/'docs/translation-status.json')
    status.update(version=VERSION,stage='Compact memory-card UI and high-detail album captions packaged locally; live testing and full translation review pending')
    status['latest_memory_album_build']=summary
    archive_doc=read(ROOT/'docs/native-archive-layout.json')
    archive_doc['archives']['ALBUM.AFS']={'current_build':VERSION,'archive_sha256':digest(files['ALBUM.AFS']),
        'member_count':251,'native_lookups':'All 251 offsets/sector lengths match physical layout',
        'evidence':summary['proof'],'unchanged_fullsize_members':214,
        'added_caption_texture_members':[243,244,245,246,247,248,249],
        'manifest_member_before_after':[243,250]}
    archive_doc['latest_album_caption_update']=summary['disc']
    ui={'version':VERSION,'logical_game_size':[320,240],
        'screenshots':[
            {'file':'memory-slot-before.png','source_clipboard':'86619735-f261-4ca6-8e88-596da5a19ad3',
             'elements':[{'id':'names.g00.192/193','box':[34,50,248,28],'ink_limit_x':248},
                         {'id':'names.g00.223','box':[98,82,112,138],'ink_limit_x':104}],
             'fix':'Compact prompts and eight distinct Port A - Slot 1 style choices; boxes retained'},
            {'file':'load-header-before.png','source_clipboard':'3848d3d1-14d0-4bde-9f50-03e801532034',
             'elements':[{'id':'names.g00.208/209 + names.g00.210/211','box':[170,26,112,28]}],
             'fix':'Compact dynamically selected port/slot labels; load/save header controls retained'},
            {'file':'album-before.png','source_clipboard':'941c4425-c8fa-4906-8ccf-e3b7dc636b7f',
             'elements':[{'id':'album.214.064..071','card_size':[64,72],'photo_size':[64,48],
                          'caption_size':[64,24],'caption_texture_pixels':[192,72]}],
             'fix':'Separate three-times-detail original Skies caption textures; original photos retained'}],
        'geometry_precision':'Existing box positions estimated from supplied screenshot; caption geometry read from exact native DAT records',
        'parser_cases':proof['UI_cases'],'caption_records':component['records'],
        'comparison':'album-caption-comparison.png; diagnostic composition, not a runtime screenshot'}
    note=f'''## {VERSION} — memory-card fit and sharper album captions

- Shortened memory-card prompts and labels to fit the existing boxes. All eight choices show their complete port and slot number (for example, Port A - Slot 1); the load/save header uses the same compact labels. Kept the save/load action and eight-free-block requirement. No memory-card geometry or gameplay change.
- Replaced the 203 low-detail baked album captions with separate 192×72-pixel caption sprites drawn at 64×24 logical pixels. Uses original Skies 12×24 glyph shapes and four coverage levels, variable advances and a shared baseline. Seven 1024×512 lossless four-color VQ textures add 931,840 bytes of texture memory. All 224 photos, 21 placeholder cards and original full-size artwork remain exact; no emulator texture replacement. Original 224 sprite records stay intact; appended 224 caption records, expanded the gallery texture list from 28 to 35 and moved the filename-only manifest from member 243 to 250. All original picture member IDs remain fixed. Used the native normalized 256-unit UV grid for the larger textures.
- Passed 1,356 bounded native dispatch cases, all 448 native Ninja pre-transform geometry/UV cases, original and expanded native registration/relocation, 251 native archive lookups, seven native VQ texture-info cases and pixel-exact VQ decoding, 23 memory-card UI parser cases, and 36 actual native PRS streams with output/ABI/guard checks. PRS inputs, outputs and executable are identical across the uncompressed DAT UV correction; the earlier pass and its actual identities are retained explicitly. Draw submission, async I/O and UI context use documented fixtures. GPU depth/alpha, actual navigation and total live VRAM occupancy remain pending.
- Packaged {report['new_changed_sectors']:,} sector substitutions over 0.1.39. All fourteen payloads re-extract exactly, changed-sector EDC/ECC passes and all 1,188,856,032 track bytes compare exactly outside declared edits. Eleven other payloads remain exact 0.1.39, including the normal font, story and library. Historical native reports retain their actual tested executable hashes. No story translation or independent meaning-review credit, release or replacement of prior builds.
- Fresh-boot the 0.1.40 GDI and check memory-card selection, load/save headers and Memory Album paging. In-game saves can be used; emulator save states can retain the previous code/textures. The Japanese album title artwork is outside this caption fix.

'''
    return summary,[(ROOT/'docs/memory-album-layout.json',summary),(ROOT/'docs/translation-status.json',status),
                    (ROOT/'docs/native-archive-layout.json',archive_doc),(ROOT/f'work/ui/{VERSION}/layout.json',ui)],note


def preview():
    _,_,component,_,pages,images=album()
    cells=read(ROOT/'work/ui/asset-audit/ALBUM/captions/rectangles.json')['rectangles']
    records={r['sprite']:r for r in component['records']}
    canvas=Image.new('RGB',(1112,700),'#20242b');draw=ImageDraw.Draw(canvas)
    draw.text((18,10),'Offline caption comparison at equal card size; not a Flycast screenshot',fill='white')
    for section,label in enumerate(('0.1.39: captions baked into 64 x 24 bands','0.1.40: original Skies pixels, 192 x 72 caption textures')):
        ybase=35+section*330;draw.text((18,ybase),label,fill='white')
        for n in range(4):
            sprite=64+n;row=cells[sprite];x,y,u,v=row['source_box']
            old=images[row['texture_member']][y:v,x:u]
            rgb=np.stack([((old>>s)&31)*255//31 for s in (10,5,0)],axis=-1).astype(np.uint8)
            card=Image.fromarray(rgb).resize((256,288),Image.Resampling.BILINEAR)
            if section:
                r=records[sprite];a,b,c,d=r['source_box'];plane=pages[r['font_page']][b:d,a:c]
                band=Image.fromarray(np.array([239,156,66,0],np.uint8)[plane]).convert('RGB')
                card.paste(band.resize((256,96),Image.Resampling.BILINEAR),(0,192))
            canvas.paste(card,(18+n*274,ybase+23))
    return canvas


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true')
    args=ap.parse_args();summary,updates,note=prepare()
    print('Verified build',VERSION,';',summary['sector_substitutions'],'sector edits; 203 captions; 8 slot labels.')
    print('Will record:',[str(p.relative_to(ROOT)) for p,_ in updates]);print(note.splitlines()[:4])
    if not args.write: print('DRY RUN: no records or screenshots written.');return
    for path,value in updates:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n','utf-8')
    folder=ROOT/f'work/ui/{VERSION}'
    for clip,name in [('86619735-f261-4ca6-8e88-596da5a19ad3','memory-slot-before.png'),
                      ('3848d3d1-14d0-4bde-9f50-03e801532034','load-header-before.png'),
                      ('941c4425-c8fa-4906-8ccf-e3b7dc636b7f','album-before.png')]:
        shutil.copyfile(f'C:/Users/Binh/AppData/Local/Temp/codex-clipboard-{clip}.png',folder/name)
    preview().save(folder/'album-caption-comparison.png')
    changes=ROOT/'CHANGELOG.md';old=changes.read_text('utf-8')
    if note.splitlines()[0] not in old: changes.write_text(old.replace('# Change log\n\n','# Change log\n\n'+note,1),'utf-8')
    print('Build records, UI witnesses and changelog written.')


if __name__ == '__main__': main()
