"""Remove the logo parts from a STEP model, keeping every other part and its colours.

    ~/miniforge3/bin/python tools/strip_logo.py <model.step> <name text>

Used once on 3dmodels/IRFHM4226TRPBF.step to drop the vendor-logo parts.

Removes every assembly component (and its free shape) whose name contains the
given text, then writes the file back with XCAF so colours and names survive.
"""
import sys

from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader, STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

path, needle = sys.argv[1], sys.argv[2]
doc = TDocStd_Document(TCollection_ExtendedString("doc"))
r = STEPCAFControl_Reader()
r.SetColorMode(True)
r.SetNameMode(True)
if r.ReadFile(path) != IFSelect_RetDone or not r.Transfer(doc):
    sys.exit(f"cannot read {path}")
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())


def name(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else ""


removed, protos = [], []


def walk(label):
    kids = TDF_LabelSequence()
    st.GetComponents_s(label, kids, False)
    for i in range(1, kids.Length() + 1):
        c = kids.Value(i)
        ref = c
        if st.IsReference_s(c):
            from OCP.TDF import TDF_Label
            ref = TDF_Label()
            st.GetReferredShape_s(c, ref)
        if needle in name(c) or needle in name(ref):
            removed.append(name(c) or name(ref))
            st.RemoveComponent(c)
            if ref != c:
                protos.append(ref)
        elif st.IsAssembly_s(ref):
            walk(ref)


free = TDF_LabelSequence()
st.GetFreeShapes(free)
for i in range(1, free.Length() + 1):
    walk(free.Value(i))
st.UpdateAssemblies()
for ref in protos:                       # the logo's own shape definition goes too
    if not ref.IsNull() and st.IsShape_s(ref):
        st.RemoveShape(ref, True)
st.UpdateAssemblies()
if not removed:
    sys.exit(f"nothing named '{needle}' in {path}")
w = STEPCAFControl_Writer()
w.SetColorMode(True)
w.SetNameMode(True)
w.Transfer(doc, STEPControl_AsIs)
if w.Write(path) != IFSelect_RetDone:
    sys.exit(f"cannot write {path}")
print(f"{path}: removed {len(removed)} part(s): {sorted(set(removed))}")
