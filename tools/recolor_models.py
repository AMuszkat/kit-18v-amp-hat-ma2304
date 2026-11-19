"""Give the colourless STEP models in 3dmodels/ colours, in place.

    ~/miniforge3/bin/python tools/recolor_models.py 3dmodels

KiCad shows a STEP model without colours as plain white/grey, and its GLB export
writes such a model with no material at all.  Each solid gets a colour and a
name whose prefix the render's Blender scene reads (ALU_ / BLACK_ / TIN_ /
PLASTIC_).  Geometry is untouched.

- EEEFN1E821UL.step (Cpvdd04_x / Cpvdd14_x, 820 uF can): aluminium can, black
  base plate, tinned terminals -- split by solid.
- TE 282834-4 (Jout1/2) and TE 282837-2 (J_VEXT) terminal blocks: each is ONE
  fused solid, so the whole block is the light-grey housing colour (ASSUMED,
  as on the TAS5825M board); the render picks out the metal faces.
"""
import sys
from pathlib import Path

import cadquery as cq

d = Path(sys.argv[1])
ALU, BLACK, TIN, GREY = (0.80, 0.80, 0.80), (0.06, 0.06, 0.065), (0.80, 0.80, 0.78), (0.70, 0.71, 0.69)


def redo(name, roles):
    path = d / name
    solids = cq.importers.importStep(str(path)).solids().vals()
    solids.sort(key=lambda s: -s.Volume())
    if len(solids) != len(roles):
        sys.exit(f"{name}: expected {len(roles)} solids, found {len(solids)}")
    asm = cq.Assembly(name=path.stem)
    for i, (s, (label, colour)) in enumerate(zip(solids, roles)):
        asm.add(cq.Workplane().add(s), name=f"{label}_{i}", color=cq.Color(*colour))
    asm.export(str(path), exportType="STEP")
    back = cq.importers.importStep(str(path)).solids().vals()
    if len(back) != len(roles):
        sys.exit(f"{name}: re-import gave {len(back)} solids")
    print(f"{name}: {len(back)} solids recoloured")


# largest first: can, base plate, two terminals
redo("EEEFN1E821UL.step", [("ALU_can", ALU), ("BLACK_base", BLACK), ("TIN_term", TIN), ("TIN_term", TIN)])
redo("c-282834-4-c-3d.stp", [("PLASTIC_housing", GREY)])
redo("TE_282837-2.step", [("PLASTIC_housing", GREY)])
