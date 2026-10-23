# Translating and reviewing Rayblade

Start with `BASE_RULES.md` and `AGENTS.md`. English working exports live under `work/translation/en/`; source-linked names and terms live under `work/glossary/`.

Use your own Japanese Dreamcast disc. Source text extraction is local to ignored `work/source/`. Do not commit a Japanese script dump. Names and short UI terms may remain in the glossary. Keep original row IDs, fingerprints, placeholders, inline controls and conditional library branches.

Read surrounding rows before changing speaker direction, gender or pronouns. Flag uncertain meanings. Distinguish drafting, independent meaning review, native/structural validation and live playtesting. Do not count one as another. `docs/translation-status.json` records current holds and limitations.

The working bilingual JSON is intentionally ignored. `python tools/strip_jp.py` audits the English-only export without writing; inspect it, then use `--write`. Commit only those `*.en.json` exports. Importing an export back into a local bilingual workspace must match its source IDs and fingerprints; do not invent a new fingerprint to bypass a mismatch.

Build scripts are incremental research tools with local source/prior-stage prerequisites. Read their help and records before running. Keep test discs in `work/output/`, UI evidence in `work/ui/`, and incoming files in `incoming/`. Test from a fresh boot and ordinary in-game save, preserving controls and gameplay data. Never publish a full game disc.
