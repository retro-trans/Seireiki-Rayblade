"""Validate English prose while preserving exact, source-proven opaque labels.

The model code's U+30FC is a literal part of its displayed identifier. This is
not a general allowance for kana or for changing that mark to an ASCII hyphen.
Returned text is for validation only; the saved English remains untouched.
"""
import re

OPAQUE_LABELS=('03K\u30fc01',)
JAPANESE=re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')


def checked_english_prose(source,english):
    """Return a checking copy with exact source labels removed, or reject it."""
    checked=english
    for label in OPAQUE_LABELS:
        boundary=re.compile(r'(?<![\w\u30fc-])'+re.escape(label)+r'(?![\w\u30fc-])')
        # Japanese prose adjoins the source identifier without word spaces;
        # only its ASCII/model-code boundary is significant on that side.
        source_pattern=re.compile(r'(?<![A-Za-z0-9_\u30fc-])'+re.escape(label)+r'(?![A-Za-z0-9_\u30fc-])')
        source_count=len(source_pattern.findall(source))
        english_count=len(boundary.findall(english))
        if source_count!=english_count or english.count(label)!=english_count:
            raise ValueError('Opaque source label changed, duplicated, omitted or invented')
        checked=boundary.sub('',checked)
    if JAPANESE.search(checked):
        raise ValueError('Japanese prose in English draft')
    return checked
