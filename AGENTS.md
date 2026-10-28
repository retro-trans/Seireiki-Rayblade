** Organize folder like this **
work - work folder
    output - contains the file for testing (iso, zip, etc...)
    glossary - contains the one or many json files for glossary
    ui - contains screenshot of actual UI element ingame with label on screenshot if possible, contains files (json,py,...) describe the coordinate, width and height, id and other attributes
    translation/<language code> - contains the target translation of ui element or dialogues or anything that need translation
docs - documents
tools - any tools help with translation
incoming - outside files that need agent to look into

** SOME RULES **
- Avoid contains extensive Japanese scripts (UI elements is fine)
- Identified each build with version 0.x.y (start at 0.1.0)
- Always write change log
- If user told you to remember anything write it down here, make sure to ask user if the new one conflict with old one
- Be conscious of subscription limit before creating sub-agents

** REMEMBER **
- Runtime font policy (2026-10-28): the user removed HD mode. Use only the original Skies Native (1x) font; do not restore the HD bank or a title-screen font selector.
- Font priority: use a sharper Latin-only variable-width font integrated into the game. Do not use emulator texture replacement. Keep every font texture at or below 1024 pixels per dimension; Japanese glyph slots are not required in the new font.
- Font selection: on 2026-10-23 the user explicitly superseded the supplied bitmap with the original Skies of Arcadia USA Dreamcast Latin font from E:\Games. Decode its 12 x 24 VQ glyphs using tools/analyze_skies_font.py; preserve original pixel shapes and four alpha levels, with variable advances and a consistent scale/baseline. Do not stretch individual letters or reconstruct outlines. Build integration: tools/build_skies_font_patch.py; source/proof record: docs/skies-font-port.json. The supplied atlas at incoming/fonts/user-bitmap/dialogue-atlas.png and GenEi remain historical dependencies; five protected non-ASCII marks still use GenEi.
- Do not create or publish a GitHub release until the user explicitly requests a release for that build. Translation and local builds do not imply release permission.
- Public release upgrade patches must go from the last public release to the new release, not from an intervening local test build. Confirm the latest published version before packaging the public upgrade.
- Every new github release must work with [Retro Trans Tools](https://github.com/retro-trans/retro-trans-tools).
- Japanese script text must never be committed to git. Keeping it in local working files is fine: `.gitignore` covers `work/source/` and the translation working files. Commit only the `*.en.json` copies written by `tools/strip_jp.py` (run it before committing). Names and UI terms in Japanese are allowed.
- Dialogue layout: reflow compiled presentation for all translated story, embedded and battle dialogue using the current font widths. Join obsolete single line breaks, wrap whole words, and preserve wording, blank paragraphs, explicit page breaks and pause/effect controls. Keep working translation rows intact. Current implementation: tools/dialogue_reflow.py (236 logical pen pixels); record: docs/dialogue-reflow.json.
