# Seireiki Rayblade — translation project

Tools for translating **Seireiki Rayblade** (Dreamcast, Japanese edition, **T-42201M**), plus the English translation built with them.

## Contribute

The translation is a work in progress. Bug reports, Japanese-to-English proofreading and route playtesting are welcome. Include the release version, chapter/location and a screenshot when reporting a problem.

**[discord.gg/nZBZfTDfCP](https://discord.gg/nZBZfTDfCP)** · [Report an issue](https://github.com/retro-trans/Seireiki-Rayblade/issues)

## Play it

The current release is **[v0.7.50](https://github.com/retro-trans/Seireiki-Rayblade/releases/tag/v0.7.50)**. It repairs the reported New Game and mission-dialogue black screens on Dreamcast/GDEMU/VGA and combines the existing emulator fixes. The tested Native **1× font**, graphics-memory repairs, battle display, loading placement and fullscreen movies are retained. See the [release notes](docs/releases/v0.7.50.md).

**This is an unfinished translation.** There are 503 held/untranslated story rows, unsupported original text can show fallback marks, and one room tag remains unidentified. Full routes and extended sessions remain unverified. The long Chapter 6 save label can overlap its “In Battle” label, and [Stage 9 CG issue #5](https://github.com/retro-trans/Seireiki-Rayblade/issues/5) remains open. A version number is not a completion percentage.

### Apply

This release uses **DCP**, with one patch for each supported input. Download the [current Retro Trans Tools for Windows](https://github.com/retro-trans/retro-trans-tools/releases/latest); Automatic DCP discovery requires **0.5.20 or later**.

| Input | Patch |
|---|---|
| Original Japanese CUE/BIN | `Rayblade-English-v0.7.50.dcp` |
| Exact public 0.7.23 English GDI | `Rayblade-English-v0.7.23-to-v0.7.50-upgrade.dcp` |

For the original game, refresh the catalog and choose **Automatic**, or select the image and full patch in the **DCP** tab. For a public 0.7.23 GDI, use the **DCP** tab and upgrade patch; Automatic does not recognize that older offset-based GDI layout.

Choose **GDI** output and a new folder. Keep the rebuilt GDI and **all generated tracks** together. On GDEMU, replace the complete game folder. Cold-boot and load a normal VMU save; do not resume an old emulator save state.

The upgrade is **0.7.23 → 0.7.50**. Other releases and local diagnostics must use the full patch with original Japanese input. Keep input verification enabled. DCP rebuilds the disc layout and verifies all game files, boot code and original CD audio; raw output-track hashes need not match older images. No per-track xdelta operations are needed. The ZIP downloads include the same DCPs with installation instructions and notices.

### Sharper text

The patch integrates the original **Skies of Arcadia USA Dreamcast Latin glyphs**, with variable spacing, consistent baselines and their four alpha levels. Every font texture stays at or below 1024 pixels per dimension. Map names use a 512×128 alpha atlas with native-scale lettering and a thin dark edge. Only the Native **1×** font is included; the HD bank and title-screen selector have been removed. The native main source cell is 12×24 pixels, with an 8×16 compact cell, rendered in a true 640×480 framebuffer. These changes are in the game assets; an emulator texture pack is not required.

The combined 0.7.50 build is reported working on **Dreamcast/GDEMU/VGA**. Flycast remains the emulator test target; full routes and other hardware/video setups are not certified. Fresh-boot the GDI and load an ordinary in-game memory-card save after updating; emulator save states can retain older executable and graphics data.

### VGA support and original movies

**0.7.50** retains the retail VGA video changes from [Rolly (SEGA-SKY)'s patch v1.0](https://segasky.itch.io/seireiki-rayblade-vga-patch-for-sega-dreamcast), plus the VGA boot flag. Flycast cold-boot telemetry confirms 640×480 progressive VGA timing and a separate composite boot reaches the TV path. The tested Dreamcast/GDEMU/VGA setup now has a passing report; NTSC/PAL and full non-VGA regression testing remain necessary. Original region selection and translated disc artwork are retained. See [the integration record](docs/vga-support.json).

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
- Patch application and release verification: [Retro Trans Tools](https://github.com/retro-trans/retro-trans-tools), using the Universal Dreamcast Patcher DCP engine for current releases (xdelta3 for historical releases).
- VGA video patch: [Rolly (SEGA-SKY), retail v1.0](https://segasky.itch.io/seireiki-rayblade-vga-patch-for-sega-dreamcast). English-build integration and checks by this project.
- *Seireiki Rayblade* and its original game assets belong to their respective rights holders. This is an unofficial fan project.

## Status

The release contains machine-generated English drafts that have been edited and tested incrementally. It is not a hand translation by a fluent translator, and no whole-game human proofreading count is claimed. Full route completion, independent meaning review, held passages, long-session behavior and some live layout checks remain unfinished. The release notes distinguish byte-level/native checks from actual gameplay testing.
