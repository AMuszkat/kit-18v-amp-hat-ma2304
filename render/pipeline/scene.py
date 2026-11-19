"""Blender half of the kit_18v_amp_hat_ma2304 render.

    blender -b --factory-startup --python scene.py -- job.json

job.json: {"glb", "beauty", "matte", "holes"} plus optional overrides of the look
(px, samples, adaptive, device, view, fill, lens, lights, world, exposure,
mask_tint, mask_alpha, mask_rough, view_transform, skip_matte).  The defaults
below ARE the published look.  Procedural micro-finishes supply only sub-visible
surface grain; the board, silk and component detail remain real geometry.

Writes two RGBA PNGs of the same frame:
  beauty  Cycles, floor as shadow catcher: alpha = objects + floor shadow
  matte   the objects alone (floor hidden), low samples: alpha = object coverage
compose.py uses the pair to set the floor shadow's strength independently of
the board itself.
"""
import json
import math
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

job = json.load(open(sys.argv[sys.argv.index("--") + 1]))
MM = 0.001

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=job["glb"])
scene = bpy.context.scene


# ---- materials ----------------------------------------------------------------

def new_mat(name, colour, metallic=0.0, rough=0.5, **extra):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    for k, v in extra.items():
        b.inputs[k.replace("_", " ")].default_value = v
    return m


def srgb(*c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def microfinish(mat, roughness=None, bump_mm=0.0, scale=180.0, anisotropy=None):
    """Small-scale physical finish, not an image texture: roughness variation and
    a microscopic normal perturbation keep large surfaces from looking like CAD."""
    n, links = mat.node_tree.nodes, mat.node_tree.links
    b = n.get("Principled BSDF")
    tex = n.new("ShaderNodeTexCoord")
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.65
    links.new(tex.outputs["Generated"], noise.inputs["Vector"])
    if roughness:
        remap = n.new("ShaderNodeMapRange")
        remap.inputs["To Min"].default_value = roughness[0]
        remap.inputs["To Max"].default_value = roughness[1]
        links.new(noise.outputs["Fac"], remap.inputs["Value"])
        links.new(remap.outputs["Result"], b.inputs["Roughness"])
    if bump_mm:
        bump = n.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.16
        bump.inputs["Distance"].default_value = bump_mm * MM
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], b.inputs["Normal"])
    if anisotropy is not None and b.inputs.get("Anisotropic IOR Level"):
        b.inputs["Anisotropic IOR Level"].default_value = anisotropy


M = {
    "enig":     new_mat("enig", srgb(0.88, 0.74, 0.47), 1.0, 0.22),
    "solder":   new_mat("solder", srgb(0.82, 0.82, 0.81), 1.0, 0.24),
    "copper":   new_mat("copper_enig", srgb(0.88, 0.74, 0.47), 1.0, 0.30),   # all exposed copper is ENIG
    "silk":     new_mat("silk", srgb(0.93, 0.93, 0.91), 0.0, 0.62),
    "laminate": new_mat("fr4_edge", srgb(0.66, 0.64, 0.47), 0.0, 0.65),
    "tin":      new_mat("tin", srgb(0.82, 0.82, 0.80), 1.0, 0.30),
    "nickel":   new_mat("nickel", srgb(0.78, 0.77, 0.74), 1.0, 0.20),
    "steel":    new_mat("steel", srgb(0.74, 0.74, 0.73), 1.0, 0.28),
    "gold":     new_mat("gold", srgb(0.93, 0.73, 0.38), 1.0, 0.20),
    "ceramic":  new_mat("ceramic", srgb(0.48, 0.36, 0.25), 0.0, 0.45),
    "res_body": new_mat("resistor_body", srgb(0.06, 0.06, 0.065), 0.0, 0.45),
    "epoxy":    new_mat("epoxy", srgb(0.075, 0.075, 0.08), 0.0, 0.42, Specular_IOR_Level=0.45),
    "black":    new_mat("black_plastic", srgb(0.06, 0.06, 0.065), 0.0, 0.40),
    "ferrite":  new_mat("ferrite", srgb(0.07, 0.07, 0.072), 0.0, 0.62),
    "ferrite_g": new_mat("ferrite_grey", srgb(0.28, 0.28, 0.29), 0.0, 0.6),
    "grey_pl":  new_mat("grey_plastic", srgb(0.64, 0.65, 0.63), 0.0, 0.48),
    "nylon":    new_mat("nylon", srgb(0.95, 0.94, 0.91), 0.0, 0.42,
                        Subsurface_Weight=0.25, Subsurface_Scale=0.002),
    "button":   new_mat("button", srgb(0.86, 0.85, 0.82), 0.0, 0.5),
    "alumina":  new_mat("alumina", srgb(0.90, 0.89, 0.86), 0.0, 0.55),
    "molded":   new_mat("molded_inductor", srgb(0.20, 0.20, 0.21), 0.0, 0.6),
}

# Solder mask (top and bottom): KiCad's blue at alpha 0.83; make it a satin lacquer.
# Only the blue translucent board materials -- some vendor part models also come
# out with alpha 0 (the Vishay 0402 resistors) and are opaque parts, not mask.
MASKS = []
for mat in bpy.data.materials:
    b = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
    if not b:
        continue
    r, g, bl, _ = b.inputs["Base Color"].default_value
    if b.inputs["Alpha"].default_value < 0.9 and bl > r + 0.3:
        k = job.get("mask_tint", 0.40)
        b.inputs["Base Color"].default_value = (r * k, g * k, bl * k, 1)
        b.inputs["Alpha"].default_value = job.get("mask_alpha", 0.94)
        b.inputs["Roughness"].default_value = job.get("mask_rough", 0.5)
        b.inputs["Specular IOR Level"].default_value = 0.5
        MASKS.append(mat)
    elif b.inputs["Alpha"].default_value < 0.9:
        b.inputs["Alpha"].default_value = 1.0                  # opaque part


def part(o):
    """The footprint reference an object belongs to (its top empty under Node_0)."""
    p = o
    while p.parent and p.parent.name != "Node_0":
        p = p.parent
    return p.name.split(".")[0]


def base_colour(mat):
    b = mat.node_tree.nodes.get("Principled BSDF") if mat and mat.use_nodes else None
    return tuple(b.inputs["Base Color"].default_value[:3]) if b else (0, 0, 0)


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def classify(o, mat):
    """Material role for one slot of one object, from the part and object names
    first and the exported colour second."""
    ref, name = part(o), o.name.split(".")[0]
    c, L = base_colour(mat), lum(base_colour(mat))
    b = mat.node_tree.nodes.get("Principled BSDF")
    met = b.inputs["Metallic"].default_value if b else 1
    if ref.startswith("=>") or ref == "Node_0":            # the board itself
        # KiCad's GLB: the copper layers come out gold-coloured (under the mask),
        # the exposed-pad finish layer grey, 5 um above them.  Pads of an
        # assembled board are solder-coated; mounting rings get ENIG gold below.
        if met > 0.5 and c[2] < 0.2 * c[0]:
            return "copper"
        if met > 0.5:
            return "solder"
        if L > 0.8:
            return "silk"
        return "laminate"
    for prefix, role in (("NYLON_", "nylon"), ("EPOXY_", "epoxy"), ("NICKEL_", "nickel"),
                         ("PLASTIC_", "grey_pl"), ("ALU_", "alu"), ("BLACK_", "black"),
                         ("TIN_", "tin"), ("MOLDED_", "molded")):
        if name.startswith(prefix):
            return role
    if "Logo" in name or "logo" in name or name == "Vishay":   # vendor logos on part models
        return "HIDE"
    if name.startswith("6130xx"):                            # Wurth header pins
        return "gold"
    if name.startswith("6130"):                              # header housing
        return "black"
    if ref == "P1":                                          # 40-way socket, under the board
        if c[2] > c[0] + 0.15:
            return "gold"
        return "black" if L < 0.05 else "tin"
    if ref.startswith(("MA2304", "Q1", "U1")):
        return "tin" if L > 0.1 else "epoxy"
    if ref.startswith(("Cpvdd04", "Cpvdd14", "C5")):          # aluminium electrolytics
        return "alu" if L > 0.3 else "black"
    if ref.startswith("Lout"):                               # wire-wound chip inductors
        return "tin" if L > 0.3 else "ferrite"
    if ref.startswith("R"):
        if name == "body":
            return "alumina"                                 # Vishay model: substrate
        if name == "top":
            return "res_body"
        return "tin" if L > 0.3 else "res_body"
    if ref.startswith("C"):
        if L > 0.3 or (c[0] > 0.4 and abs(c[0] - c[2]) < 0.1):
            return "tin"
        return "ceramic"
    return "tin" if L > 0.3 else "black"


M["alu"] = new_mat("aluminium_can", srgb(0.72, 0.73, 0.74), 1.0, 0.32)
M["alu_top"] = new_mat("aluminium_can_top", srgb(0.58, 0.59, 0.60), 1.0, 0.52)
M["ceramic_dark"] = new_mat("ceramic_dark", srgb(0.12, 0.12, 0.12), 0.0, 0.5)
M["vent"] = new_mat("stamped_aluminium_vent", srgb(0.30, 0.31, 0.32), 1.0, 0.48)

# Real surface finishes: pale ENIG, softly brushed metal, moulded plastics and
# a satin lacquer with a separate clear coat.  All scales are sub-visible grain;
# the board's geometry and silkscreen still come exclusively from KiCad.
for key, rgb in {
    "enig": (0.86, 0.75, 0.52), "copper": (0.86, 0.75, 0.52),
    "gold": (0.86, 0.69, 0.37), "laminate": (0.50, 0.49, 0.36),
}.items():
    M[key].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*srgb(*rgb), 1)
for key, rough, bump, anis in (
    ("enig", (0.18, 0.25), 0.0003, 0.12), ("copper", (0.23, 0.31), 0.0004, 0.12),
    ("solder", (0.25, 0.34), 0.0006, 0.10), ("tin", (0.26, 0.35), 0.0005, 0.18),
    ("nickel", (0.19, 0.28), 0.0004, 0.28), ("steel", (0.25, 0.34), 0.0005, 0.20),
    ("gold", (0.20, 0.28), 0.0003, 0.18), ("alu", (0.29, 0.39), 0.0005, 0.38),
    ("alu_top", (0.48, 0.58), 0.0007, 0.22),
    ("ceramic", (0.43, 0.53), 0.0010, None), ("res_body", (0.42, 0.52), 0.0008, None),
    ("epoxy", (0.38, 0.47), 0.0008, None), ("black", (0.38, 0.47), 0.0012, None),
    ("ferrite", (0.56, 0.66), 0.0015, None), ("molded", (0.55, 0.65), 0.0015, None),
    ("grey_pl", (0.43, 0.53), 0.0018, None), ("nylon", (0.38, 0.47), 0.0012, None),
    ("alumina", (0.50, 0.60), 0.0008, None),
):
    microfinish(M[key], rough, bump, anisotropy=anis)
M["nylon"].node_tree.nodes["Principled BSDF"].inputs["Subsurface Weight"].default_value = 0.08
for mask in MASKS:
    b = mask.node_tree.nodes["Principled BSDF"]
    b.inputs["Specular IOR Level"].default_value = 0.32
    b.inputs["Coat Weight"].default_value = 0.08
    b.inputs["Coat Roughness"].default_value = 0.40
    microfinish(mask, (0.40, 0.47), 0.0008, scale=240)

hidden = []
for o in list(scene.objects):
    if o.type != "MESH":
        continue
    for slot in o.material_slots:
        if not slot.material or slot.material in MASKS:
            continue
        role = classify(o, slot.material)
        if role == "HIDE":
            hidden.append(o)
            break
        if role:
            slot.link = "OBJECT"
            slot.material = M[role]
for o in hidden:
    bpy.data.objects.remove(o)
print("HIDDEN", len(hidden))

# Terminal blocks are one fused solid each: pick out the metal.  Up-facing faces
# that form small islands sunk below the housing top are the screw heads at the
# pocket floors; faces below the board surface are the pins.
import bmesh  # noqa: E402

BOARD_TOP = job.get("board_top_mm", 1.555) * MM
for o in list(scene.objects):
    if o.type != "MESH" or not o.name.startswith("PLASTIC_housing"):
        continue
    o.data.materials.append(M["nickel"])
    o.data.materials.append(M["tin"])
    i_ni, i_sn = len(o.data.materials) - 2, len(o.data.materials) - 1
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    mw, rot = o.matrix_world, o.matrix_world.to_3x3().normalized()
    zmax = max((mw @ v.co).z for v in bm.verts)
    up = {f.index for f in bm.faces if (rot @ f.normal).z > 0.95
          and BOARD_TOP + 1.0 * MM < (mw @ f.calc_center_median()).z < zmax - 0.8 * MM}
    seen, screws, pins = set(), 0, 0
    for f0 in up:
        if f0 in seen:
            continue
        island, stack = [], [f0]
        seen.add(f0)
        while stack:
            f = bm.faces[stack.pop()]
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index in up and g.index not in seen:
                        seen.add(g.index)
                        stack.append(g.index)
        area = sum(f.calc_area() for f in island) * (mw.median_scale ** 2)
        if area < 9e-6:                                    # < 9 mm^2: a screw head
            for f in island:
                f.material_index = i_ni
            screws += 1
    for f in bm.faces:
        if (mw @ f.calc_center_median()).z < BOARD_TOP - 0.05 * MM:
            f.material_index = i_sn
            pins += 1
    bm.to_mesh(o.data)
    bm.free()
    print("TERMINAL", part(o), "screw heads", screws, "pin faces", pins)

# Mounting holes carry no paste: their rings stay bare ENIG.
HOLES = [(x * MM, -y * MM) for x, y in job.get("holes", [])]
for o in scene.objects:
    if o.type == "MESH" and any(sl.material == M["solder"] for sl in o.material_slots):
        o.data.materials.append(M["enig"])
        gi = len(o.material_slots) - 1
        mw, n = o.matrix_world, 0
        for poly in o.data.polygons:
            p = mw @ poly.center
            if any(math.hypot(p.x - hx, p.y - hy) < job.get("ring_r", 2.35) * MM for hx, hy in HOLES):
                poly.material_index = gi
                n += 1
        print("ENIG faces", o.name, n)


# No chip markings: the amplifier's exact marking (the silk says MA2304DN) and the
# MOSFET's (value IRFHM830, model IRFHM4226) are not certain enough to print.


def cap_vent(ref, rotation=0):
    """Model the shallow three-arm pressure-relief score in an electrolytic can."""
    root = bpy.data.objects.get(ref)
    if not root:
        return
    verts = [c.matrix_world @ v.co for c in root.children_recursive
             if c.type == "MESH" for v in c.data.vertices]
    if not verts:
        return
    ztop = max(p.z for p in verts)
    # The rolled can wall is brighter and more directional than its stamped lid.
    for ob in root.children_recursive:
        if ob.type != "MESH":
            continue
        ob.data = ob.data.copy()
        ob.data.materials.append(M["alu_top"])
        gi = len(ob.material_slots) - 1
        mw = ob.matrix_world
        rot = mw.to_3x3().normalized()
        for poly in ob.data.polygons:
            if (rot @ poly.normal).z > 0.80 and (mw @ poly.center).z > ztop - 0.08 * MM:
                poly.material_index = gi
    top = [p for p in verts if p.z > ztop - 0.04 * MM]
    x0, x1 = min(p.x for p in top), max(p.x for p in top)
    y0, y1 = min(p.y for p in top), max(p.y for p in top)
    radius = min(x1 - x0, y1 - y0) / 2
    if radius < 1.5 * MM:
        return
    centre = Vector(((x0 + x1) / 2, (y0 + y1) / 2, ztop + 0.003 * MM))
    cu = bpy.data.curves.new(f"vent_{ref}", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.013 * MM
    cu.bevel_resolution = 2
    for arm in range(3):
        angle = math.radians(rotation + arm * 120)
        direction = Vector((math.cos(angle), math.sin(angle), 0))
        spline = cu.splines.new("POLY")
        spline.points.add(1)
        for point, distance in zip(spline.points, (0.10 * radius, 0.60 * radius)):
            p = centre + direction * distance
            point.co = (*p, 1)
    ob = bpy.data.objects.new(cu.name, cu)
    scene.collection.objects.link(ob)
    cu.materials.append(M["vent"])


for i, ref in enumerate(("Cpvdd04_1", "Cpvdd04_2", "Cpvdd14_1", "Cpvdd14_2", "C5")):
    cap_vent(ref, 20 + i * 17)


# ---- extent -----------------------------------------------------------------------
bpy.context.view_layer.update()
meshes = [o for o in scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre, size = (lo + hi) / 2, (hi - lo).length
flat_coords = [c for p in pts for c in p]
print("EXTENT", [round(v / MM, 2) for v in lo], [round(v / MM, 2) for v in hi])

bpy.ops.mesh.primitive_plane_add(size=size * 40, location=(centre.x, centre.y, lo.z - 0.00002))
floor = bpy.context.active_object
floor.name = "floor"
floor.is_shadow_catcher = True


# ---- camera -------------------------------------------------------------------------
x, _, z = (float(v) for v in job.get("view", {}).get("rotate", "-38,0,62").split(","))
el, az = math.radians(90 - abs(x)), math.radians(-z)
direction = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.lens = job.get("lens", 85)
cam_data.clip_start, cam_data.clip_end = size * 0.01, size * 100
cam.location = centre + direction * size * 4
cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
cam_data.dof.use_dof = False
bpy.context.view_layer.update()


def frame(fill, px):
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    for _ in range(2):
        dg = bpy.context.evaluated_depsgraph_get()
        loc, _scale = cam.camera_fit_coords(dg, flat_coords)
        cam.location = loc
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(scene, cam, p) for p in pts]
        w = max(u.x for u in uv) - min(u.x for u in uv)
        h = max(u.y for u in uv) - min(u.y for u in uv)
        aspect = min(max(w * scene.render.resolution_x / (h * scene.render.resolution_y), 0.6), 2.6)
        rx = round(math.sqrt(px * aspect) / 8) * 8
        scene.render.resolution_x, scene.render.resolution_y = rx, round(rx / aspect / 8) * 8
    cam.location = centre + (cam.location - centre) / fill


frame(job.get("fill", 0.75), job.get("px", 16e6))


# ---- light ---------------------------------------------------------------------------
# A light tent: big soft key above-left of the camera, a broad fill from the camera's
# right, a rim from behind for edge highlights, and a white world for everything else.
cam_dir = (cam.location - centre).normalized()
cam_az = math.atan2(cam_dir.y, cam_dir.x)


def softbox(name, rel_az_deg, elev_deg, dist, spread, energy):
    a, e = cam_az + math.radians(rel_az_deg), math.radians(elev_deg)
    d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    data = bpy.data.lights.new(name, "AREA")
    # Energies were tuned on the TAS5825M board (scene diagonal 0.120 m); the lights
    # sit at distances proportional to the scene, so scale by size^2 to light any
    # board alike.
    data.shape = "RECTANGLE"
    data.size = size * spread
    data.size_y = size * spread * (0.28 if name == "rim" else 0.68)
    data.energy = energy * (size / job.get("ref_size", 0.12008)) ** 2
    ob = bpy.data.objects.new(name, data)
    ob.location = centre + d * size * dist
    ob.rotation_euler = (centre - ob.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(ob)
    return ob


L = job.get("lights", {})
# (azimuth from the camera, elevation, distance and size in scene diagonals, watts)
softbox("key", *L.get("key", (-48, 58, 2.2, 1.8, 1.8)))
softbox("fill", *L.get("fill", (55, 32, 2.4, 2.4, 0.36)))
softbox("rim", *L.get("rim", (160, 45, 2.2, 1.7, 0.75)))

world = bpy.data.worlds.new("tent")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (1, 1, 1, 1)
bg.inputs["Strength"].default_value = job.get("world", 0.18)
scene.world = world


# ---- render ----------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"


def pick_gpu(want):
    if want == "cpu":
        return "CPU (asked for)"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except Exception as err:                                # noqa: BLE001
        return f"CPU ({err})"
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except Exception:                                   # noqa: BLE001
            continue
        gpus = [d for d in prefs.devices if d.type == backend]
        if not gpus:
            continue
        for d in prefs.devices:
            d.use = d.type == backend or (d.type == "CPU" and want != "gpu")
        scene.cycles.device = "GPU"
        return f"{backend}: " + " + ".join(d.name for d in prefs.devices if d.use)
    return "CPU (no usable GPU)"


print("DEVICE", pick_gpu(job.get("device", "auto")))
scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = job.get("adaptive", 0.008)
scene.cycles.max_bounces = 12
scene.cycles.glossy_bounces = 6
scene.cycles.transmission_bounces = 8
scene.cycles.transparent_max_bounces = 16
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "16"
scene.view_settings.view_transform = job.get("view_transform", "Khronos PBR Neutral")
scene.view_settings.look = "None"
scene.view_settings.exposure = job.get("exposure", -0.6)   # the white backdrop is added later
scene.render.threads_mode = "AUTO"

scene.cycles.samples = job.get("samples", 320)
scene.render.filepath = job["beauty"]
bpy.ops.render.render(write_still=True)
print("BEAUTY", scene.render.resolution_x, scene.render.resolution_y)

if not job.get("skip_matte"):
    floor.hide_render = True
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.max_bounces = 0
    scene.render.filepath = job["matte"]
    bpy.ops.render.render(write_still=True)
    print("MATTE done")
