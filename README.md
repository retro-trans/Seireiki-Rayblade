# Seireiki Rayblade — translation project

Tools for translating **Seireiki Rayblade** (Dreamcast, Japanese edition, **T-42201M**), plus the English translation built with them.

## Contribute

The translation is a work in progress. Bug reports, Japanese-to-English proofreading and route playtesting are welcome. Include the release version, chapter/location and a screenshot when reporting a problem.

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)** · [Report an issue](https://github.com/retro-trans/Seireiki-Rayblade/issues)

## Play it

The current release is **[v0.7.11](https://github.com/retro-trans/Seireiki-Rayblade/releases/tag/v0.7.11)**. It adds selectable Native/HD Skies lettering at true 640×480 output, fixes movie sizing, restores separate story choices, improves map labels, fits long weapon/movie names, repairs Trust help and SP signs, translates 33 room-map tags and sizes location headers to their actual lettering. VGA support and original Japanese opening/demo content are retained. See the [release notes](docs/releases/v0.7.11.md).

**This is an unfinished translation, not a claim of complete proofreading or complete route coverage.** There are 503 held/untranslated story rows. Some unsupported original text can display fallback marks with the Latin-only font. Latest UI/hardware appearance still needs testing. [Stage 6 text corruption (issue #1)](https://github.com/retro-trans/Seireiki-Rayblade/issues/1) remains unresolved, and one room tag remains unidentified. Version 0.7.11 is a release identifier, not a completion percentage.

### Apply

**The easiest way:** [Retro Trans](https://github.com/retro-trans/retro-trans-tools) provides a desktop interface for applying the complete patch set. Use version **0.4.1 or later**, refresh its catalog, choose **Automatic**, and select the folder containing your original five BIN tracks and `Seireiki Rayblade (Japan).cue`. Select v0.7.11 and click **Patch**. It verifies all inputs, applies all three patches, and copies the three unchanged tracks into a new complete folder. Choose the new `.gdi` in Flycast.

This release uses a verified **multi-file solution**. An unpacked BIN/CUE set matching the published hashes is required. Automatic CHD extraction/recompression for this GD-ROM layout is not supported. A different dump, track split, region, or local English build does not become compatible merely by renaming it.

**Other ways:** [DeltaPatcher](https://github.com/marco-calautti/DeltaPatcher) or [xdelta3](https://github.com/jmacd/xdelta) can apply each delta manually:

| Original input | Patch | Output |
|---|---|---|
| Japanese Track 3 | `Rayblade-English-v0.7.11-Track03.xdelta` | Patched Track 3, keeping its original filename |
| Japanese Track 5 | `Rayblade-English-v0.7.11-Track05.xdelta` | Patched Track 5, keeping its original filename |
| Original Japanese CUE | `Rayblade-English-v0.7.11-GDI.xdelta` | `Seireiki Rayblade English v0.7.11.gdi` |

Create a new output folder. Apply the three deltas and copy original **Tracks 1, 2 and 4** into it unchanged. The result must contain all five BIN tracks plus the new GDI. Do not rename individual tracks: the GDI references their exact filenames. The tiny GDI delta converts your original CUE into the verified boot descriptor; it is part of the complete solution.

```powershell
xdelta3 -d -s "Seireiki Rayblade (Japan) (Track 3).bin" Rayblade-English-v0.7.11-Track03.xdelta "English/Seireiki Rayblade (Japan) (Track 3).bin"
xdelta3 -d -s "Seireiki Rayblade (Japan) (Track 5).bin" Rayblade-English-v0.7.11-Track05.xdelta "English/Seireiki Rayblade (Japan) (Track 5).bin"
xdelta3 -d -s "Seireiki Rayblade (Japan).cue" Rayblade-English-v0.7.11-GDI.xdelta "English/Seireiki Rayblade English v0.7.11.gdi"
```

Source and output hashes are supplied with the release. Keep source verification enabled. No upgrade patches from unpublished 0.1.x local builds are provided.

### Sharper text

The patch integrates the original **Skies of Arcadia USA Dreamcast Latin glyphs**, with variable spacing, consistent baselines and their four alpha levels. Every font texture stays at or below 1024 pixels per dimension. Map names use a 512×128 alpha atlas with native-scale lettering and a thin dark edge. Native is the cold-boot default: title-screen **X selects Native**, **Y selects HD**, until reset. The native main source cell is 12×24 pixels, with an 8×16 compact cell, rendered in a true 640×480 framebuffer. These changes are in the game assets; an emulator texture pack is not required.

The target for current visual testing is **Flycast**. Original Dreamcast hardware compatibility has not been established. Fresh-boot the GDI and load an ordinary in-game memory-card save after updating; emulator save states can retain older executable and graphics data.

### VGA support and original movies

**0.7.11** retains the retail VGA video changes from [Rolly (SEGA-SKY)'s patch v1.0](https://segasky.itch.io/seireiki-rayblade-vga-patch-for-sega-dreamcast), plus the VGA boot flag. Flycast cold-boot telemetry confirms 640×480 progressive VGA timing and a separate composite boot reaches the TV path. Physical Dreamcast VGA/NTSC/PAL and full non-VGA regression testing remain necessary. Original region selection and translated disc artwork are retained. See [the integration record](docs/vga-support.json).

Both modified movies, `MOV055.SFD` (opening) and `MOV072.SFD` (demo), are restored byte-for-byte from the original Japanese disc. Added English subtitles, captions and movie title/UI edits are removed. Their original video, audio and timing are preserved without re-encoding. Movie drawing now fills a centered 640×384 area in the 640×480 framebuffer; English gameplay text and the font remain intact.

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
- VGA video patch: [Rolly (SEGA-SKY), retail v1.0](https://segasky.itch.io/seireiki-rayblade-vga-patch-for-sega-dreamcast). English-build integration and checks by this project.
- *Seireiki Rayblade* and its original game assets belong to their respective rights holders. This is an unofficial fan project.

## Status

The release contains machine-generated English drafts that have been edited and tested incrementally. It is not a hand translation by a fluent translator, and no whole-game human proofreading count is claimed. Full route completion, independent meaning review, held passages, long-session behavior and some live layout checks remain unfinished. The release notes distinguish byte-level/native checks from actual gameplay testing.
