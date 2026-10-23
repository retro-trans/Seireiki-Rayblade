"""Prepare 0.7.0 public docs and private Retro Trans build config. Dry first."""
import argparse,json,hashlib,subprocess
from pathlib import Path
from build_bitmap_font import ROOT

VERSION='0.7.0';BASE=ROOT/'work/output/0.1.44';REPO='retro-trans/Seireiki-Rayblade'
OUT=ROOT/'work/output/release-0.7.0'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def config(commit):
    patches=[];files=[]
    for i in (3,5):
        name=f'Seireiki Rayblade (Japan) (Track {i}).bin';edition=f'Japan / Track {i} raw MODE1-2352'
        patches.append({'patch':f'Rayblade-English-v{VERSION}-Track{i:02d}.xdelta','edition':edition,
            'language':'en','source_version':'original','source_format':'bin','target_format':'bin',
            'source':str(ROOT/name),'target':str(BASE/'disc'/name)})
        files.append({'edition':edition,'output_name':name})
    patches.append({'patch':f'Rayblade-English-v{VERSION}-GDI.xdelta','edition':'Japan / Disc descriptor',
        'language':'en','source_version':'original','source_format':'cue','target_format':'gdi',
        'source':str(ROOT/'Seireiki Rayblade (Japan).cue'),
        'target':str(BASE/'disc/Rayblade English Test 0.1.44.gdi')})
    files.append({'edition':'Japan / Disc descriptor','output_name':f'Seireiki Rayblade English v{VERSION}.gdi'})
    copies=[{'name':f'Seireiki Rayblade (Japan) (Track {i}).bin',
        'source':str(ROOT/f'Seireiki Rayblade (Japan) (Track {i}).bin')} for i in (1,2,4)]
    return {'game_id':'seireiki-rayblade','game_name':'Seireiki Rayblade','platform':'Dreamcast',
        'version':VERSION,'source_commit':commit,'patches':patches,'solutions':[
            {'id':'japan-disc','name':'Complete English Dreamcast disc','edition':'Japan (T-42201M)',
             'language':'en','files':files,'copy_files':copies}]}


README='''# Seireiki Rayblade — translation project

Tools for translating **Seireiki Rayblade** (Dreamcast, Japanese edition, **T-42201M**), plus the English translation built with them.

## Contribute

The translation is a work in progress. Bug reports, Japanese-to-English proofreading and route playtesting are welcome. Include the release version, chapter/location and a screenshot when reporting a problem.

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)** · [Report an issue](https://github.com/retro-trans/Seireiki-Rayblade/issues)

## Play it

The first public release is **[v0.7.0](https://github.com/retro-trans/Seireiki-Rayblade/releases/tag/v0.7.0)**. It packages local build 0.1.44: story and battle English drafts, character/unit library text, native interface and image translations, integrated original Skies Latin glyphs, whole-word dialogue wrapping and the latest menu/map-label repairs.

**This is an unfinished translation, not a claim of complete proofreading or complete route coverage.** There are 503 held/untranslated story rows. Some unsupported original text can display fallback marks with the Latin-only font. The latest map and menu artwork still needs fresh-boot in-game confirmation. Version 0.7.0 is a release identifier, not a completion percentage.

### Apply

**The easiest way:** [Retro Trans](https://github.com/retro-trans/retro-trans-tools) provides a desktop interface for applying the complete patch set. Use version **0.4.1 or later**, refresh its catalog, choose **Automatic**, and select the folder containing your original five BIN tracks and `Seireiki Rayblade (Japan).cue`. Select v0.7.0 and click **Patch**. It verifies all inputs, applies all three patches, and copies the three unchanged tracks into a new complete folder. Choose the new `.gdi` in Flycast.

This release uses a verified **multi-file solution**. An unpacked BIN/CUE set matching the published hashes is required. Automatic CHD extraction/recompression for this GD-ROM layout is not supported. A different dump, track split, region, or local English build does not become compatible merely by renaming it.

**Other ways:** [DeltaPatcher](https://github.com/marco-calautti/DeltaPatcher) or [xdelta3](https://github.com/jmacd/xdelta) can apply each delta manually:

| Original input | Patch | Output |
|---|---|---|
| Japanese Track 3 | `Rayblade-English-v0.7.0-Track03.xdelta` | Patched Track 3, keeping its original filename |
| Japanese Track 5 | `Rayblade-English-v0.7.0-Track05.xdelta` | Patched Track 5, keeping its original filename |
| Original Japanese CUE | `Rayblade-English-v0.7.0-GDI.xdelta` | `Seireiki Rayblade English v0.7.0.gdi` |

Create a new output folder. Apply the three deltas and copy original **Tracks 1, 2 and 4** into it unchanged. The result must contain all five BIN tracks plus the new GDI. Do not rename individual tracks: the GDI references their exact filenames. The tiny GDI delta converts your original CUE into the verified boot descriptor; it is part of the complete solution.

```powershell
xdelta3 -d -s "Seireiki Rayblade (Japan) (Track 3).bin" Rayblade-English-v0.7.0-Track03.xdelta "English/Seireiki Rayblade (Japan) (Track 3).bin"
xdelta3 -d -s "Seireiki Rayblade (Japan) (Track 5).bin" Rayblade-English-v0.7.0-Track05.xdelta "English/Seireiki Rayblade (Japan) (Track 5).bin"
xdelta3 -d -s "Seireiki Rayblade (Japan).cue" Rayblade-English-v0.7.0-GDI.xdelta "English/Seireiki Rayblade English v0.7.0.gdi"
```

Source and output hashes are supplied with the release. Keep source verification enabled. No upgrade patches from unpublished 0.1.x local builds are provided.

### Sharper text

The patch integrates the original **Skies of Arcadia USA Dreamcast Latin glyphs**, with variable spacing, consistent baselines and their four alpha levels. Every font texture stays at or below 1024 pixels per dimension. Map names use a 1024×256 alpha atlas with brighter lettering and a dark edge. These changes are in the game assets; an emulator texture pack is not required.

The target for current visual testing is **Flycast**. Original Dreamcast hardware compatibility has not been established. Fresh-boot the GDI and load an ordinary in-game memory-card save after updating; emulator save states can retain older executable and graphics data.

## Check the translation

The English-only files in `work/translation/en/` preserve source row IDs and fingerprints. The glossary in `work/glossary/` records names, terms and evidence. Compare against text extracted locally from your own Japanese disc; the original script is not stored in Git.

See **[TRANSLATING.md](TRANSLATING.md)** for the edit/export workflow and **[docs/translation-status.json](docs/translation-status.json)** for measured coverage, review holds and validation limits. A drafted row is not the same as a human-proofread row.

## Translate it

Fork the repository to improve the English or begin another language. Preserve source IDs, placeholders, effect codes and conditional library branches. Do not edit game statistics or scenario logic to make text fit. Start with [TRANSLATING.md](TRANSLATING.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## What is here

| Path | Contents |
|---|---|
| `tools/` | Disc/text extraction, codecs, font and image builders, native checks and local patch packagers |
| `work/translation/en/` | English-only translation and presentation exports |
| `work/glossary/` | Names, terminology, source references and decisions |
| `docs/` | Format research, layout records, coverage and validation evidence |
| `AGENTS.md`, `BASE_RULES.md` | Project layout and translation rules |
| `CHANGELOG.md` | Local build history and public release changes |
| `VERSION` | Current public release version |

Original discs, extracted Japanese scripts, font binaries, build outputs, incoming reference files and local runtime captures are excluded. Scripts expect locally extracted source data and, in some cases, earlier local build stages. This repository is not a one-command rebuild from only the English JSON files.

## Using these tools

Use Python 3.12 or later. Core image/native-analysis tools use NumPy, Pillow and Capstone; movie tools additionally require FFmpeg and other optional analysis dependencies. Most mutation tools default to a dry run; inspect its output before using `--write`.

```powershell
python tools/disc_inventory.py
python tools/strip_jp.py
python tools/strip_jp.py --write
```

The source disc's CUE belongs at the project root; extracted scripts stay under ignored `work/source/`. Read each tool's help and documented local prerequisites. Release patches are built and round-trip checked with the shared [Retro Trans release standard](https://github.com/retro-trans/retro-trans-tools/blob/main/docs/RELEASE_STANDARD.md).

## Do not sell this

This fan patch is free. Do not sell the patch, pre-patched game images, loaded memory cards or consoles, or access through paywalls or ad-gated downloads. You need your own copy of the Japanese game. No complete original or translated game images are distributed here.

## Credits

- Project direction and playtesting: [binhlt0402](https://github.com/binhlt0402).
- Translation drafts, editing, tooling and reverse engineering: AI-assisted work with Codex/OpenAI under the project lead's direction.
- Latin glyph pixels: the original *Skies of Arcadia* USA Dreamcast game font (SEGA/Overworks). This project grants no new license to that game artwork; no standalone game font binary is included.
- Five protected non-ASCII marks retain the [GenEi Latin](https://okoneya.jp/font/genei-latin.html) subset. See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) for its SIL Open Font License notices.
- Patch application and release verification: [Retro Trans Tools](https://github.com/retro-trans/retro-trans-tools), using xdelta3.
- *Seireiki Rayblade* and its original game assets belong to their respective rights holders. This is an unofficial fan project.

## Status

The release contains machine-generated English drafts that have been edited and tested incrementally. It is not a hand translation by a fluent translator, and no whole-game human proofreading count is claimed. Full route completion, independent meaning review, held passages, long-session behavior and some live layout checks remain unfinished. The release notes distinguish byte-level/native checks from actual gameplay testing.
'''

NOTES='''English translation **work in progress** for **Seireiki Rayblade**, Dreamcast Japanese edition **T-42201M**.

Version **v0.7.0** is the first public release, packaging the cumulative local **0.1.44** build. It includes the current English drafts, integrated Skies font, dialogue reflow, native UI/image translations and recent menu/map readability repairs. It does **not** claim that every line, route or screen has been independently reviewed.

### Apply

**The easiest way:** [Retro Trans](https://github.com/retro-trans/retro-trans-tools) **0.4.1 or later** can apply the complete verified multi-file solution. Refresh its catalog, choose **Automatic**, select the original BIN/CUE folder or `Seireiki Rayblade (Japan).cue`, choose v0.7.0 and click **Patch**. It checks all inputs and saves a new folder containing five verified BIN tracks and the English GDI.

Use an unpacked five-track Japanese dump matching `SOURCE-HASHES-v0.7.0.txt`. GD-ROM/multi-track CHD conversion is not supported by this release contract. Other dumps and local test versions are not interchangeable.

**Other ways:** [DeltaPatcher](https://github.com/marco-calautti/DeltaPatcher) or [xdelta3](https://github.com/jmacd/xdelta) accepts the same deltas. Create a new output folder and apply all three:

| Your original input | Patch |
|---|---|
| Track 3 | `Rayblade-English-v0.7.0-Track03.xdelta` |
| Track 5 | `Rayblade-English-v0.7.0-Track05.xdelta` |
| `Seireiki Rayblade (Japan).cue` | `Rayblade-English-v0.7.0-GDI.xdelta` |

Keep the patched track filenames unchanged. Copy original Tracks **1, 2 and 4** into the new folder, and save the descriptor result as **`Seireiki Rayblade English v0.7.0.gdi`**. The final folder contains all five tracks plus that GDI. The descriptor delta creates a verified GDI from your exact original CUE; it is not optional in the Automatic solution. Open the GDI in Flycast.

See the repository [README](https://github.com/retro-trans/Seireiki-Rayblade#apply) and `README-v0.7.0.txt` for manual commands. Source/output hashes and validation records are included. Do not disable source checksum verification. There are no upgrade patches from unpublished 0.1.x builds.

### What is included in v0.7.0

* **Story and battle English drafts.** Includes the current source-linked translations and consistent character/place/mech terminology. There are **503 held/untranslated story rows**; the release is not a complete, fully proofread translation.
* **Character and unit library.** Includes English profile text, conditional branches, scrolling/layout fixes and repaired shared scratch/header handling.
* **Integrated original Skies font.** Latin-only variable spacing, preserved glyph pixels/four alpha levels and consistent baselines. Every font texture stays within 1024 pixels per dimension. No emulator replacement pack is needed.
* **Whole-word dialogue wrapping.** Reflows translated story, embedded and battle dialogue while preserving words, effects, pauses and explicit pages.
* **Native interface and image work.** Includes menus, battle labels, chapter cards, album captions, credits, demo/movie captions and the cumulative translated native graphics.
* **Recent menu repairs.** Wider action, counter-order and reaction menus; balanced help wrapping; extended Mission Objectives heading; compact status/weapon fields and memory-card slot labels.
* **Sharper world-map names.** Rebuilds all ten place labels using the original Skies masks in a 1024×256 alpha atlas, bright cream fill and a thin dark edge. Preserves terrain and marker artwork. Adds 512 KiB of texture storage.

### Testing and known limitations

The source and target disc sets have been checked at the byte level. Each release delta is decoded from its exact original input and compared against the complete target SHA-256. The cumulative local build also passed all fourteen payload re-extractions, changed-sector EDC/ECC checks and the full 1,188,856,032-byte track preservation comparison. Native checks cover affected text/font, archive loading geometry and map texture metadata; fixture boundaries are documented in the validation record.

**Live gameplay remains incomplete.** The newest map labels and menus need fresh-boot confirmation of texture upload, VRAM behavior, blending, cursor/highlights and overlaps. Full-route testing, independent Japanese meaning review and long-session stability are unfinished. Original Dreamcast hardware compatibility is unverified; Flycast is the current test target. Held original text can display fallback marks with the Latin-only font.

Fresh-boot the new GDI and load an ordinary in-game memory-card save. Emulator save states can retain an earlier executable and artwork. This release packages local 0.1.44; it makes no claim to include future source-only edits.

### What's included

Three bare `.xdelta` patches; canonical `BUILD-MANIFEST.json`, `VALIDATION.json` and `SHA256SUMS.txt`; source/output hash lists; this readme, changelog, game-validation record and font notices. The manifest declares the complete disc solution, exact inputs, unchanged tracks and all verified outputs. No complete game tracks, ISO, CHD or standalone extracted font are included.

### How it was translated

This is a **machine translation**, produced with large language models and then edited. Codex/OpenAI assisted the translation drafts, tooling and reverse engineering under the project lead's direction. It has not had complete independent human Japanese-to-English proofreading. Names and terminology are tracked in the project glossary with source references.

### Acknowledgements

Original Latin glyph pixels come from *Skies of Arcadia* USA Dreamcast (SEGA/Overworks). Five protected non-ASCII marks retain GenEi Latin masks under the included SIL Open Font License notices. Thank you to the original game/font creators and the xdelta3 and Retro Trans Tools projects. This project grants no license to the original game artwork.

### Source code

The automatically generated **Source code (zip)** is the repository snapshot at this tag. It contains tools, English-only translation exports, glossary and research records; it is separate from the playable patch assets. Local original game data, Japanese script dumps, font binaries, runtime captures and prior build stages are excluded. Apply the `.xdelta` files to your own disc set to play.

### Contribute

Bug reports, proofreading and playtesting are welcome:

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)** · [Issues](https://github.com/retro-trans/Seireiki-Rayblade/issues)

---

No complete game images are included. Apply the patches to a copy you own. The patch is free: do not sell it or anything made with it.
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--config',action='store_true');a=ap.parse_args()
    if a.config:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();v=config(commit)
        print('Plan:',len(v['patches']),'deltas; full five-track output plus generated GDI; commit',commit)
        if not a.write:print('DRY RUN: no private build config.');return
        OUT.mkdir(parents=True,exist_ok=True);(OUT/'release-local.json').write_text(json.dumps(v,indent=2)+'\n','utf-8');return
    report=json.loads((BASE/'english-disc-report.json').read_text('utf-8'));assert report['validation']['reextracted_files']=='all 14 exact'
    notices=(BASE/'FONT-LICENSE.txt').read_text('utf-8');notices=notices[notices.index('Rayblade Latin HD bitmap subset'):]
    notices='Seireiki Rayblade English v0.7.0 font notices\n\nOriginal Skies USA Dreamcast Latin glyph pixels: SEGA/Overworks game artwork. No new license is granted; no standalone game font binary is distributed.\n\nThe following notices apply to the five retained GenEi non-ASCII marks. Historical supplied-bitmap ASCII glyphs have been superseded.\n\n'+notices
    translating='''# Translating and reviewing Rayblade

Start with `BASE_RULES.md` and `AGENTS.md`. English working exports live under `work/translation/en/`; source-linked names and terms live under `work/glossary/`.

Use your own Japanese Dreamcast disc. Source text extraction is local to ignored `work/source/`. Do not commit a Japanese script dump. Names and short UI terms may remain in the glossary. Keep original row IDs, fingerprints, placeholders, inline controls and conditional library branches.

Read surrounding rows before changing speaker direction, gender or pronouns. Flag uncertain meanings. Distinguish drafting, independent meaning review, native/structural validation and live playtesting. Do not count one as another. `docs/translation-status.json` records current holds and limitations.

The working bilingual JSON is intentionally ignored. `python tools/strip_jp.py` audits the English-only export without writing; inspect it, then use `--write`. Commit only those `*.en.json` exports. Importing an export back into a local bilingual workspace must match its source IDs and fingerprints; do not invent a new fingerprint to bypass a mismatch.

Build scripts are incremental research tools with local source/prior-stage prerequisites. Read their help and records before running. Keep test discs in `work/output/`, UI evidence in `work/ui/`, and incoming files in `incoming/`. Test from a fresh boot and ordinary in-game save, preserving controls and gameplay data. Never publish a full game disc.
'''
    contributing='''# Contributing

Report the public version, emulator/version, chapter or location, route and steps to reproduce. Attach a screenshot and quote the English line. Recheck after a fresh boot with a normal in-game save; save states can preserve older code or graphics.

For proofreading, compare your own Japanese source and examine the surrounding conversation. Include source row IDs when possible. Separate a clear meaning error from a different but valid wording. Do not upload complete game files or Japanese script dumps.

For code/layout changes, follow `AGENTS.md` and `BASE_RULES.md`, preserve game controls/statistics, run relevant native/structural checks, and state what still needs live testing. Read `TRANSLATING.md` before changing exports. Public releases require explicit maintainer authorization and must pass the Retro Trans manifest/round-trip contract.

Discussion: https://discord.gg/MssepShjmB
'''
    updates={ROOT/'README.md':README,ROOT/'TRANSLATING.md':translating,ROOT/'CONTRIBUTING.md':contributing,
        ROOT/'THIRD_PARTY_NOTICES.txt':notices,ROOT/'docs/releases/v0.7.0.md':NOTES}
    print('Plan: README modeled on SRW-Z; release notes with Apply/changes/testing/assets/translation/credits/source/contribution sections.')
    print('Write:',[str(p.relative_to(ROOT)) for p in updates]);print('Release: WIP; 503 held story rows; latest payloads exact local0.1.44.')
    if not a.write:print('DRY RUN: no public docs.');return
    for p,text in updates.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,'utf-8')
    changes=ROOT/'CHANGELOG.md';old=changes.read_text('utf-8');heading='## 0.7.0 — first public release'
    assert heading not in old
    note=heading+'\n\n- Publishes the verified cumulative local 0.1.44 payloads as v0.7.0. Game track bytes are unchanged from that local build.\n- Adds a public README and release notes modeled on retro-trans/SRW-Z, English-only source exports, current font notices and a Retro Trans Tools schema-v2 complete-disc release. Tracks 3/5 are patched, Tracks 1/2/4 copied unchanged, and a descriptor delta converts the original CUE to the verified English GDI.\n- Release remains a work in progress: 503 held/untranslated story rows, independent review, complete routes and newest live map/menu/VRAM checks remain unfinished. Native and preservation evidence is not described as full gameplay testing.\n- No complete game tracks, extracted Japanese scripts, standalone game fonts or local captures are included in the public repository/release. Every public delta must pass full source-to-target SHA-256 round-trip verification before publication.\n\n'
    changes.write_text(old.replace('# Change log\n\n','# Change log\n\n'+note,1),'utf-8')


if __name__=='__main__':main()
