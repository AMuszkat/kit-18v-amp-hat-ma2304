#!/usr/bin/env python3
"""De-brand a converted KiCad schematic: neutral title block, no vendor image.

The Altium sheets carry the vendor's title block (company name and the original
reference-design title) and an embedded vendor-logo bitmap. The board is shipped
de-branded, so the schematic must match: this drops the embedded image node,
rewrites the `title_block` to the project's own neutral one, blanks any
MANUFACTURER / COMPANY field that names the vendor, and removes the Altium
title-block text items the importer turned into free `(text ...)` objects —
the `${PRJ_*}` placeholders and their static labels. Design notes are `text_box`
objects and are kept.

Usage: debrand_sch.py <sheet.kicad_sch> <title> [rev]
"""
import re
import sys

VENDOR_PROP = re.compile(
    r'(\(property "(?:MANUFACTURER|COMPANY|MFR|MFR_NAME|VENDOR)" )'
    r'"[^"]*(?:Infineon|Merus)[^"]*"', re.I)

# static labels of the Altium A3/A4 title block
TITLE_TEXT = {
    'sheet', 'of', 'size:', 'date:', 'rev.', 'rev', 'title', 'file:',
    'approved', 'drawn', 'checked', 'engineer', 'author', 'author:',
    'document name', 'document number', 'time:', 'variant', 'rel.',
    'svn revision:', 'a3', 'a4', 'a2', 'a1', 'a0',
}


def find_node(s, start):
    """Return the end index (exclusive) of the s-expr node starting at `start`."""
    depth = 0
    i = start
    in_str = False
    while i < len(s):
        c = s[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError('unbalanced node')


def drop_images(s):
    n = 0
    while True:
        i = s.find('\t(image\n')
        if i < 0:
            break
        j = find_node(s, i + 1)
        while j < len(s) and s[j] == '\n':
            j += 1
        s = s[:i] + s[j:]
        n += 1
    return s, n


def set_title_block(s, title, rev):
    i = s.find('\t(title_block\n')
    if i < 0:
        return s, False
    j = find_node(s, i + 1)
    block = ('\t(title_block\n'
             f'\t\t(title "{title}")\n'
             f'\t\t(rev "{rev}")\n'
             '\t)')
    return s[:i] + block + s[j:], True


TEXT_START = re.compile(r'\n\t\(text "')


def _text_content(s, paren):
    """The unescaped string of the `(text "…")` node whose '(' is at `paren`."""
    k = paren + len('(text "')
    buf = []
    while k < len(s):
        c = s[k]
        if c == '\\':
            buf.append(s[k:k + 2])
            k += 2
            continue
        if c == '"':
            break
        buf.append(c)
        k += 1
    return ''.join(buf)


def drop_titleblock_texts(s):
    """Remove `(text ...)` items left over from the Altium sheet template."""
    out, i, n = [], 0, 0
    while i < len(s):
        m = TEXT_START.search(s, i)
        if not m:
            out.append(s[i:])
            break
        paren = m.start() + 2
        node_end = find_node(s, paren)
        content = _text_content(s, paren)
        if content.startswith('$') or content.strip().lower() in TITLE_TEXT:
            out.append(s[i:m.start()])
            i = node_end
            n += 1
        else:
            out.append(s[i:node_end])
            i = node_end
    return ''.join(out), n


def main():
    path, title = sys.argv[1], sys.argv[2]
    rev = sys.argv[3] if len(sys.argv) > 3 else 'V1.0'
    s = open(path, encoding='utf-8').read()
    s, imgs = drop_images(s)
    s, texts = drop_titleblock_texts(s)
    s, tb = set_title_block(s, title, rev)
    s, nvendor = VENDOR_PROP.subn(r'\1""', s)
    open(path, 'w', encoding='utf-8').write(s)
    print(f'  {path}: dropped {imgs} image(s), {texts} title-block text item(s), '
          f'title block {"set" if tb else "absent"}, {nvendor} vendor field(s) cleared')


if __name__ == '__main__':
    main()
