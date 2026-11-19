"""Render-only STEP models, made with CadQuery.

    ~/miniforge3/bin/python gen_models.py <out dir>

standoff_m2p5x11.step  M2.5 x 11 nylon hex standoff, 5 mm across flats, under
                       the board (model z 0 = board top; the board is 1.555 mm).
                       A render prop: the design does not specify standoffs.
u1_body.step           MP3428AGL body: 3.0 x 4.0 mm (from the land pattern),
                       0.9 mm high -- height ASSUMED.
l1_body.step           MPX1D0840 molded inductor: 8.5 x 8.0 mm (from the
                       footprint outline), 4.0 mm high -- height ASSUMED --
                       with its two end terminals.

Each solid is named with a material prefix (NYLON_ / EPOXY_ / MOLDED_ / TIN_)
that the Blender scene reads.  Every file is re-imported and must come back as
valid, non-empty solids: KiCad's GLB export silently skips a model it cannot read.
"""
import sys
from pathlib import Path

import cadquery as cq

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
BOARD = 1.555


def standoff():
    af, length, bore = 5.0, 11.0, 2.2
    z0 = -BOARD - length
    hexa = (cq.Workplane("XY").workplane(offset=z0)
            .polygon(6, af / 0.8660254).extrude(length).edges("|Z").fillet(0.22))
    turned = (cq.Workplane("XY").workplane(offset=z0).circle(af / 0.8660254 / 2).extrude(length)
              .faces(">Z or <Z").chamfer(0.4))
    hole = cq.Workplane("XY").workplane(offset=z0 - 1).circle(bore / 2).extrude(length + 2)
    return hexa.intersect(turned).cut(hole)


def u1():
    w, l, h = 3.0, 4.0, 0.9
    body = (cq.Workplane("XY").workplane(offset=0.02).rect(w, l).extrude(h)
            .edges("|Z").fillet(0.05).faces(">Z").edges().fillet(0.04))
    dimple = cq.Workplane("XY").workplane(offset=0.02 + h).center(-0.95, 1.45).circle(0.18).extrude(-0.03)
    return body.cut(dimple)


def l1():
    w, d, h = 8.5, 8.0, 4.0
    body = (cq.Workplane("XY").workplane(offset=0.05).rect(w - 0.3, d).extrude(h - 0.05)
            .edges("|Z").fillet(0.3).faces(">Z").edges().fillet(0.25))
    terms = None
    for sx in (-1, 1):
        t = (cq.Workplane("XY").center(sx * (w / 2 - 0.15), 0).rect(0.3, 3.2).extrude(1.6))
        terms = t if terms is None else terms.union(t)
    return body, terms


def write(name, parts):
    path = out / name
    asm = cq.Assembly(name=Path(name).stem)
    for label, part, colour in parts:
        asm.add(part, name=label, color=cq.Color(*colour))
    asm.export(str(path), exportType="STEP")
    back = cq.importers.importStep(str(path))
    solids = back.solids().vals()
    vol = sum(s.Volume() for s in solids)
    if len(solids) < len(parts) or vol <= 0 or not all(s.isValid() for s in solids):
        sys.exit(f"{name}: re-import is not valid (solids={len(solids)}, volume={vol})")
    print(f"{name}: {len(solids)} solid(s), {vol:.2f} mm3")


write("standoff_m2p5x11.step", [("NYLON_standoff", standoff(), (0.93, 0.92, 0.88))])
write("u1_body.step", [("EPOXY_u1", u1(), (0.04, 0.04, 0.045))])
body, terms = l1()
write("l1_body.step", [("MOLDED_l1", body, (0.16, 0.16, 0.17)), ("TIN_l1", terms, (0.8, 0.8, 0.78))])
