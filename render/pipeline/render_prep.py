"""Render copy of the kit_18v_amp_hat_ma2304 board.  Run with the system Python (pcbnew):

    /usr/bin/python3 render_prep.py <project dir> <generated models dir> <out dir>

Copies the board and its 3dmodels/ into <out dir> and changes the COPY only:
  - the 4 unnamed M2.5 mounting-hole footprints get an M2.5 x 11 nylon standoff
    (a prop: the design names no standoffs);
  - U1 (MP3428AGL) and L1 (MPX1D0840) have no vendor model: they get generated
    bodies whose heights are ASSUMED (gen_models.py).
Writes <out dir>/render_info.json (mounting-hole centres, mm, KiCad frame) for
the Blender scene.  The source project is never written.
"""
import json
import shutil
import sys
from pathlib import Path

import pcbnew

NAME = "kit_18v_amp_hat_ma2304"
src, gen, out = (Path(a).resolve() for a in sys.argv[1:4])
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
shutil.copytree(src / "3dmodels", out / "3dmodels")
for f in gen.glob("*.step"):
    shutil.copy(f, out / "3dmodels" / f.name)
for ext in (".kicad_pcb", ".kicad_pro"):
    shutil.copy(src / (NAME + ext), out / (NAME + ext))

pcb = out / (NAME + ".kicad_pcb")
board = pcbnew.LoadBoard(str(pcb))


def model(path):
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = path
    return m


done = {"standoff": 0, "U1": 0, "L1": 0}
holes = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    pads = list(fp.Pads())
    if ref == "" and len(pads) == 1 and pads[0].GetDrillSize().x == pcbnew.FromMM(2.75):
        fp.Models().clear()
        fp.Models().push_back(model("${KIPRJMOD}/3dmodels/standoff_m2p5x11.step"))
        done["standoff"] += 1
        holes.append([pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)])
    elif ref in ("U1", "L1"):
        fp.Models().clear()
        fp.Models().push_back(model(f"${{KIPRJMOD}}/3dmodels/{ref.lower()}_body.step"))
        done[ref] += 1

if done != {"standoff": 4, "U1": 1, "L1": 1}:
    sys.exit(f"render_prep: unexpected board contents: {done}")
board.Save(str(pcb))
(out / "render_info.json").write_text(json.dumps({"holes": holes}))
print("render copy:", pcb, done)
