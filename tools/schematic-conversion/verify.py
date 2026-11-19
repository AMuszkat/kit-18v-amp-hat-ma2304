#!/usr/bin/env python3
"""Check the converted schematic against the board.

  * designator parity (schematic symbols vs board footprints)
  * net comparison, net by net, by pad set (the board lost most net names in the
    Altium PCB import, so only the pad sets are meaningful)
  * vendor-text scan of the schematics

Usage: BOARD=<board.kicad_pcb> verify.py <root.netlist.xml> [schematic-dir]
"""
import collections
import os
import re
import sys
import xml.etree.ElementTree as ET

VENDOR = ('Infineon', 'Merus', 'Neubiberg', 'Am Campeon', 'MA12070X')


def match_block(s, i):
    depth = 0
    for m in re.finditer(r'[()]', s[i:]):
        depth += 1 if m.group(0) == '(' else -1
        if depth == 0:
            return i + m.end()
    return len(s)


def board(path):
    s = open(path, encoding='utf-8').read()
    refs, nets = set(), collections.defaultdict(set)
    for m in re.finditer(r'\n\t\(footprint ', s):
        end = match_block(s, m.start() + 1)
        blk = s[m.start():end]
        r = re.search(r'\(property "Reference" "([^"]*)"', blk)
        ref = r.group(1) if r else ''
        if ref.strip():
            refs.add(ref)
        for pm in re.finditer(r'\n\t\t\(pad ', blk):
            pend = match_block(blk, pm.start() + 1)
            pblk = blk[pm.start():pend]
            num = re.match(r'\n\t\t\(pad "([^"]*)"', pblk)
            net = re.search(r'\(net "([^"]*)"\)', pblk)
            if num and net and ref.strip():
                nets[net.group(1)].add((ref, num.group(1)))
    return refs, nets


def schematic(xmlpath):
    root = ET.parse(xmlpath).getroot()
    nets, refs = {}, set()
    for net in root.iter('net'):
        v = frozenset((n.get('ref'), n.get('pin')) for n in net.findall('node')
                      if not (n.get('ref') or '').startswith('#'))
        if v:
            nets[net.get('name')] = v
        for r, _ in v:
            refs.add(r)
    return refs, nets


def main():
    xml = sys.argv[1]
    sdir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(xml))
    board_path = os.environ.get(
        'BOARD', os.path.join(sdir, 'kit_18v_amp_hat_ma2304.kicad_pcb'))
    ok = True

    brefs, bnets = board(board_path)
    srefs, snets = schematic(xml)
    print('designator parity')
    print(f'  board footprints       : {len(brefs)}')
    print(f'  schematic symbols      : {len(srefs)}')
    print(f'  in schematic, not board: {sorted(srefs - brefs) or "none"}')
    print(f'  on board, not schematic: {sorted(brefs - srefs) or "none"}')
    if srefs - brefs or brefs - srefs:
        ok = False

    print()
    print('netlist')
    bss = {frozenset(v) for v in bnets.values()}
    matched = [n for n, v in bnets.items() if v in bss and v in set(snets.values())]
    print(f'  board nets {len(bnets)}, schematic nets {len(snets)}')
    print(f'  board nets with an identical schematic pad set: '
          f'{len(matched)}/{len(bnets)}')
    extra = [n for n, v in snets.items()
             if len(v) >= 2 and v not in bss]
    print(f'  schematic multi-pad nets without a board match: {extra or "none"}')
    if len(matched) != len(bnets) or extra:
        ok = False

    print()
    print('de-branding')
    bad = []
    for fn in sorted(os.listdir(sdir)):
        if fn.endswith('.kicad_sch'):
            t = open(os.path.join(sdir, fn), encoding='utf-8', errors='ignore').read()
            for w in VENDOR:
                if re.search(w, t, re.I):
                    bad.append(f'{fn}:{w}')
    print(f'  vendor text found: {bad or "none"}')
    if bad:
        ok = False

    print()
    print('RESULT:', 'OK' if ok else 'PROBLEMS FOUND')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
