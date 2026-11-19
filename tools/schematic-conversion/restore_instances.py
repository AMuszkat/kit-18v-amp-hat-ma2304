#!/usr/bin/env python3
"""Restore per-instance reference designators after a KiCad `sch downgrade`.

`kicad-cli sch downgrade --target "KiCad 10.0"` (nightly 10.99) rewrites the
file with a fresh root UUID and flattens every symbol instance's reference back
to the base value, so the two instances of the amplifier sheet both end up
called `CflyA0` — an unannotated design whose netlist has duplicate refs.

This walks every `(instances ...)` block in the root sheet and in every sheet it
references and rewrites the references:

  * a symbol placed in the amplifier sheet gets the board's own channel suffix:
    `X` on the AMP_CH1 path -> `X_1`, on the AMP_CH2 path -> `X_2`;
  * the root sheet's own path keeps the base reference;
  * unannotated power symbols (`#PWR?`) are numbered `#PWR0nnn` and then
    suffixed per channel the same way.

Usage: restore_instances.py <root.kicad_sch>
"""
import os
import re
import sys

REF_RE = re.compile(r'\(reference "([^"]*)"\)')
PATH_RE = re.compile(r'\(path "([^"]+)"')
BLOCK_RE = re.compile(r'\(instances\b.*?\n\t\t\)', re.S)


def channel_suffix(name):
    """AMP_CH1 -> _1, any other sheet -> _<name>."""
    m = re.match(r'AMP_CH(\d+)$', name)
    return '_' + m.group(1) if m else '_' + name


def main(root_path):
    root = open(root_path, encoding='utf-8').read()
    sheet_by_uuid = {}
    for m in re.finditer(r'\(sheet\n', root):
        blk = root[m.start():m.start() + 1400]
        name = re.search(r'\(property "Sheetname" "([^"]*)"', blk)
        uid = re.search(r'\(uuid "([^"]*)"', blk)
        if name and uid:
            sheet_by_uuid[uid.group(1)] = channel_suffix(name.group(1))

    files = [root_path]
    seen = set()
    for fn in re.findall(r'\(property "Sheetfile" "([^"]*)"', root):
        if fn in seen:
            continue
        seen.add(fn)
        p = os.path.join(os.path.dirname(root_path), fn)
        if os.path.exists(p):
            files.append(p)

    counter = [0]

    def fix(text):
        def repl(m):
            block = m.group(0)
            refs = REF_RE.findall(block)
            paths = PATH_RE.findall(block)
            if not refs or not paths:
                return block
            base = refs[0]
            if '?' in base:
                counter[0] += 1
                base = f'#PWR0{counter[0]:03d}'
            new_block = block
            for i, path in enumerate(paths):
                u = path.rsplit('/', 1)[-1]
                old = refs[i] if i < len(refs) else refs[-1]
                newr = base + sheet_by_uuid[u] if u in sheet_by_uuid else base
                if newr != old:
                    new_block = new_block.replace(
                        f'(reference "{old}")', f'(reference "{newr}")', 1)
            return new_block
        return BLOCK_RE.sub(repl, text)

    total = 0
    for p in files:
        s = open(p, encoding='utf-8').read()
        refs_before = REF_RE.findall(s)
        s2 = fix(s)
        changed = sum(1 for a, b in zip(refs_before, REF_RE.findall(s2)) if a != b)
        open(p, 'w', encoding='utf-8').write(s2)
        total += changed
        print(f"  {os.path.basename(p)}: {changed} instance reference(s) rewritten")
    print(f"  total: {total}, power symbols numbered: {counter[0]}")


if __name__ == '__main__':
    main(sys.argv[1])
