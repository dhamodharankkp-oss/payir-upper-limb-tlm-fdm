r"""
Builds the Age 8-9 (240 mm humerus) wire-articulated classroom upper-limb kit
for Creality K1 (0.4 mm, 220x220x250 mm bed):
  - Scales all 5 natural rounded bones to pediatric 8-9 yr proportions
  - Cuts reinforced Ø2.4 mm anatomical wire tunnels at every joint + stand-mount holes
  - Exports individual STLs, humerus tilt40 & flat45, Plate 2 (ulna+radius+scapula+clavicle)
  - Performs round-trip STL verification and renders visual inspection previews
"""

import json
import math
import os
import shutil

import bmesh
import bpy
from mathutils import Matrix, Vector

SRC_DIR = r"e:\AG\Blender\exports\upper_limb_5bones\realbone_1to2"
OUT_DIR = r"e:\AG\Blender\exports\upper_limb_5bones\child_8to9yr_articulated"
ARTIFACT_DIR = r"C:\Users\Aarvam\.gemini\antigravity\brain\fbaf947b-8d63-4d1f-a41e-a2cca64aef30"

HOLE_DIAMETER_MM = 2.4
HOLE_RADIUS_MM = HOLE_DIAMETER_MM * 0.5
MAX_SAFE_XY = 216.0
MAX_SAFE_Z = 246.0

# Exact pediatric Age 8-9 targets and anatomical Ø2.4 mm Z-axis wire tunnels (in centered bone XY)
BONE_SPECS = {
    "humerus": {
        "target_length_mm": 240.0,
        "holes": [
            {"label": "Shoulder (Humeral Head)", "x": 0.0, "y": 100.0},
            {"label": "Elbow Medial (Trochlea -> Ulna)", "x": -12.0, "y": -104.0},
            {"label": "Elbow Lateral (Capitulum -> Radius)", "x": 12.0, "y": -104.0},
        ],
    },
    "ulna": {
        "target_length_mm": 195.0,
        "holes": [
            {"label": "Elbow (Trochlear Notch -> Humerus)", "x": -2.0, "y": 84.0},
            {"label": "Wrist (Distal Radioulnar -> Radius)", "x": -1.0, "y": -84.0},
        ],
    },
    "radius": {
        "target_length_mm": 180.0,
        "holes": [
            {"label": "Elbow (Radial Head -> Humerus)", "x": 0.0, "y": 78.0},
            {"label": "Wrist (Distal Radioulnar -> Ulna)", "x": 0.0, "y": -78.0},
        ],
    },
    "scapula": {
        "target_length_mm": 116.0,
        "holes": [
            {"label": "AC Joint (Acromion -> Clavicle)", "x": 27.0, "y": 50.0},
            {"label": "Shoulder (Glenoid Neck -> Humerus)", "x": 24.0, "y": 25.0},
            {"label": "Classroom Stand Mount (Superior-Medial)", "x": -22.0, "y": 28.0},
        ],
    },
    "clavicle": {
        "target_length_mm": 104.0,
        "holes": [
            {"label": "AC Joint (Lateral -> Scapula)", "x": 2.5, "y": 44.0},
            {"label": "Classroom Stand Mount (Medial)", "x": 0.6, "y": -44.0},
        ],
    },
}


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_stl(path: str, name: str = "Mesh"):
    bpy.ops.wm.stl_import(filepath=path)
    obj = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.select_get()][0]
    obj.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def export_stl(objs, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, ascii_format=False)


def center_and_ground(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    coords = [v.co for v in bm.verts]
    min_x, max_x = min(c.x for c in coords), max(c.x for c in coords)
    min_y, max_y = min(c.y for c in coords), max(c.y for c in coords)
    min_z = min(c.z for c in coords)
    shift = Vector((-(min_x + max_x) * 0.5, -(min_y + max_y) * 0.5, -min_z))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=shift)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def get_bbox(obj):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    return mn, mx, mx - mn


def audit_mesh(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()

    nm = sum(1 for e in bm.edges if not e.is_manifold)
    lv = sum(1 for v in bm.verts if len(v.link_edges) == 0)
    degen = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    vol = float(bm.calc_volume(signed=True))

    visited = set()
    islands = 0
    for v in bm.verts:
        if v.index in visited:
            continue
        islands += 1
        stack = [v]
        visited.add(v.index)
        while stack:
            cur = stack.pop()
            for e in cur.link_edges:
                o = e.other_vert(cur)
                if o.index not in visited:
                    visited.add(o.index)
                    stack.append(o)

    coords = [obj.matrix_world @ v.co for v in bm.verts]
    mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    dims = mx - mn
    bm.free()

    fits = dims.x <= MAX_SAFE_XY and dims.y <= MAX_SAFE_XY and dims.z <= MAX_SAFE_Z
    return {
        "dims_mm": [round(dims.x, 2), round(dims.y, 2), round(dims.z, 2)],
        "min_z_mm": round(mn.z, 4),
        "non_manifold_edges": nm,
        "loose_verts": lv,
        "degenerate_faces": degen,
        "islands": islands,
        "signed_volume_mm3": round(vol, 2),
        "fits_K1": fits,
        "passed": (nm == 0 and lv == 0 and degen == 0 and vol > 0 and abs(mn.z) <= 0.01 and fits),
    }


def cut_wire_holes(obj, holes):
    mn, mx, dims = get_bbox(obj)
    cut_height = dims.z + 20.0
    cz = 0.5 * (mn.z + mx.z)

    for idx, h in enumerate(holes):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32,
            radius=HOLE_RADIUS_MM,
            depth=cut_height,
            location=(h["x"], h["y"], cz),
        )
        cyl = bpy.context.active_object
        cyl.name = f"WireHoleCutter_{idx}"

        mod = obj.modifiers.new(name=f"WireHoleBool_{idx}", type="BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cyl

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

        bpy.data.objects.remove(cyl, do_unlink=True)

    # Clean up any sliver faces introduced by boolean
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-4)
    bmesh.ops.dissolve_degenerate(bm, dist=5e-4, edges=bm.edges[:])
    non_tri = [f for f in bm.faces if len(f.verts) > 3]
    if non_tri:
        bmesh.ops.triangulate(bm, faces=non_tri)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def build_individual_bones():
    os.makedirs(OUT_DIR, exist_ok=True)
    audit_results = {}

    for name, spec in BONE_SPECS.items():
        clear_scene()
        obj = import_stl(os.path.join(SRC_DIR, f"{name}.stl"), name)
        center_and_ground(obj)

        _, _, dims = get_bbox(obj)
        scale = spec["target_length_mm"] / max(dims)
        obj.scale = (scale, scale, scale)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(scale=True)
        center_and_ground(obj)

        cut_wire_holes(obj, spec["holes"])
        center_and_ground(obj)

        if name == "humerus":
            # 1) Save unrotated working copy for assembly render (internal only)
            raw_path = os.path.join(OUT_DIR, "_humerus_8to9yr_wire_straight.stl")
            export_stl(obj, raw_path)

            # 2) Export flat45 (fits K1 220x220 bed in 1 piece!)
            flat45_obj = obj.copy()
            flat45_obj.data = obj.data.copy()
            bpy.context.collection.objects.link(flat45_obj)
            flat45_obj.rotation_euler = (0.0, 0.0, math.radians(45.0))
            bpy.ops.object.select_all(action="DESELECT")
            flat45_obj.select_set(True)
            bpy.context.view_layer.objects.active = flat45_obj
            bpy.ops.object.transform_apply(rotation=True)
            center_and_ground(flat45_obj)
            p_flat45 = os.path.join(OUT_DIR, "humerus_8to9yr_wire_flat45.stl")
            export_stl(flat45_obj, p_flat45)

            # 3) Export tilt40 (proximal +Y head DOWN on Z=0, 40 deg tilt -> fits straight!)
            tilt_obj = obj.copy()
            tilt_obj.data = obj.data.copy()
            bpy.context.collection.objects.link(tilt_obj)
            # Rotate -40 deg around X so +Y (proximal head) stays down and -Y (distal condyles) rises up
            tilt_obj.rotation_euler = (math.radians(-40.0), 0.0, 0.0)
            bpy.ops.object.select_all(action="DESELECT")
            tilt_obj.select_set(True)
            bpy.context.view_layer.objects.active = tilt_obj
            bpy.ops.object.transform_apply(rotation=True)
            center_and_ground(tilt_obj)
            p_tilt = os.path.join(OUT_DIR, "humerus_8to9yr_wire_tilt40.stl")
            export_stl(tilt_obj, p_tilt)

            # Round-trip audit both humerus exports
            for fname in ["humerus_8to9yr_wire_flat45.stl", "humerus_8to9yr_wire_tilt40.stl"]:
                clear_scene()
                reimp = import_stl(os.path.join(OUT_DIR, fname), fname)
                res = audit_mesh(reimp)
                audit_results[fname] = res
                print(f"[8-9yr] {fname:36s} | dims={res['dims_mm']} | nm={res['non_manifold_edges']} | degen={res['degenerate_faces']} | fits_K1={res['fits_K1']} | PASS={res['passed']}")
        else:
            fname = f"{name}_8to9yr_wire.stl"
            fpath = os.path.join(OUT_DIR, fname)
            export_stl(obj, fpath)

            clear_scene()
            reimp = import_stl(fpath, fname)
            res = audit_mesh(reimp)
            audit_results[fname] = res
            print(f"[8-9yr] {fname:36s} | dims={res['dims_mm']} | nm={res['non_manifold_edges']} | degen={res['degenerate_faces']} | fits_K1={res['fits_K1']} | PASS={res['passed']}")

    return audit_results


def build_plate2_forearm_shoulder(audit_results):
    """Packs ulna, radius, scapula, clavicle cleanly on one 220x220 K1 plate."""
    clear_scene()
    names = ["ulna", "radius", "scapula", "clavicle"]
    objs = {}
    for n in names:
        o = import_stl(os.path.join(OUT_DIR, f"{n}_8to9yr_wire.stl"), n)
        # Rotate 90 deg so longest span is along X for tidy row packing
        mn, mx, dims = get_bbox(o)
        if dims.y > dims.x:
            o.rotation_euler = (0.0, 0.0, math.pi * 0.5)
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.transform_apply(rotation=True)
        center_and_ground(o)
        objs[n] = o

    gap = 9.0
    rows = [
        [objs["ulna"]],
        [objs["radius"]],
        [objs["scapula"]],
        [objs["clavicle"]],
    ]

    row_heights = []
    for row in rows:
        widths = [get_bbox(o)[2].x for o in row]
        total_w = sum(widths) + gap * (len(row) - 1)
        cur_x = -0.5 * total_w
        max_h = 0.0
        for o, w in zip(row, widths):
            mn, mx, dims = get_bbox(o)
            o.location.x += (cur_x + 0.5 * w) - 0.5 * (mn.x + mx.x)
            o.location.y += -0.5 * (mn.y + mx.y)
            o.location.z += -mn.z
            cur_x += w + gap
            max_h = max(max_h, dims.y)
        row_heights.append(max_h)

    total_y = sum(row_heights) + gap * (len(rows) - 1)
    cur_y = -0.5 * total_y
    for row, rh in zip(rows, row_heights):
        ty = cur_y + 0.5 * rh
        for o in row:
            o.location.y += ty
        cur_y += rh + gap

    bpy.ops.object.select_all(action="DESELECT")
    for o in objs.values():
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs["ulna"]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    plate2_name = "plate_02_forearm_shoulder_8to9yr.stl"
    plate2_path = os.path.join(OUT_DIR, plate2_name)
    export_stl(list(objs.values()), plate2_path)

    # Round-trip audit
    clear_scene()
    reimp = import_stl(plate2_path, plate2_name)
    res = audit_mesh(reimp)
    audit_results[plate2_name] = res
    print(f"[8-9yr] {plate2_name:36s} | dims={res['dims_mm']} | nm={res['non_manifold_edges']} | degen={res['degenerate_faces']} | fits_K1={res['fits_K1']} | PASS={res['passed']}")


def make_mat(name, color, rough=0.38, metallic=0.0):
    mat = bpy.data.materials.new(name)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def setup_studio_and_render(cam_loc, cam_target, out_png: str, res_x=1280, res_y=920):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.filepath = out_png

    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.14, 0.16, 0.20, 1.0)
    bg.inputs["Strength"].default_value = 0.95

    bpy.ops.object.light_add(type="AREA", location=(180.0, -180.0, 260.0))
    k = bpy.context.active_object
    k.data.energy = 110000.0
    k.data.size = 200.0
    k.rotation_euler = (math.radians(35), math.radians(15), math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-180.0, 160.0, 220.0))
    f = bpy.context.active_object
    f.data.energy = 60000.0
    f.data.size = 220.0
    f.rotation_euler = (math.radians(-30), math.radians(-20), math.radians(-145))

    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    cam.rotation_euler = (Vector(cam_target) - Vector(cam_loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 45.0
    cam.data.clip_end = 3000.0
    scene.camera = cam
    bpy.ops.render.render(write_still=True)


def render_wire_hole_assembly_preview():
    """Renders all 5 Age 8-9 bones in a clean visual layout with bright copper wire pins showing every Ø2.4 mm hole."""
    clear_scene()
    bone_mat = make_mat("BonePLA", (0.91, 0.89, 0.84, 1.0), rough=0.36)
    wire_mat = make_mat("CopperWire", (0.92, 0.42, 0.12, 1.0), rough=0.25, metallic=0.85)
    stand_mat = make_mat("StandBluePin", (0.15, 0.55, 0.95, 1.0), rough=0.25, metallic=0.6)

    # Place all 5 bones cleanly across X so every single joint hole is crystal clear
    layout = [
        ("scapula", "scapula_8to9yr_wire.stl", (-130.0, 45.0)),
        ("clavicle", "clavicle_8to9yr_wire.stl", (-130.0, -65.0)),
        ("humerus", "_humerus_8to9yr_wire_straight.stl", (-20.0, 0.0)),
        ("ulna", "ulna_8to9yr_wire.stl", (65.0, -10.0)),
        ("radius", "radius_8to9yr_wire.stl", (120.0, -15.0)),
    ]

    for name, fname, (ox, oy) in layout:
        o = import_stl(os.path.join(OUT_DIR, fname), name)
        o.location = (ox, oy, 0.0)
        o.data.materials.append(bone_mat)

        # Add glowing indicator pin through each hole so user & Preethi Anni can verify exact placement
        for h in BONE_SPECS[name]["holes"]:
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=24,
                radius=1.1,
                depth=42.0,
                location=(ox + h["x"], oy + h["y"], 16.0),
            )
            pin = bpy.context.active_object
            pin.data.materials.append(stand_mat if "Stand" in h["label"] else wire_mat)

    # Matte tabletop
    bpy.ops.mesh.primitive_plane_add(size=700.0, location=(0.0, 0.0, -0.5))
    floor = bpy.context.active_object
    floor.data.materials.append(make_mat("DeskMat", (0.08, 0.09, 0.11, 1.0), rough=0.65))

    out_png = os.path.join(OUT_DIR, "child_8to9yr_wire_holes_assembly.png")
    setup_studio_and_render((0.0, -240.0, 440.0), (-5.0, -5.0, 10.0), out_png)
    shutil.copy2(out_png, os.path.join(ARTIFACT_DIR, "child_8to9yr_wire_holes_assembly.png"))


def render_k1_plates_preview():
    """Renders Plate 1 (Humerus tilt40) and Plate 2 (Forearm + Shoulder) on side-by-side 220x220 K1 beds."""
    clear_scene()
    bone_mat = make_mat("BonePLA", (0.91, 0.89, 0.84, 1.0), rough=0.36)
    bed_mat = make_mat("PEI_Bed", (0.06, 0.07, 0.09, 1.0), rough=0.55)
    rim_mat = make_mat("BedRim", (0.18, 0.45, 0.85, 1.0), rough=0.4)

    for bx in [-130.0, 130.0]:
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(bx, 0.0, -0.5))
        b = bpy.context.active_object
        b.scale = (220.0, 220.0, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        b.data.materials.append(bed_mat)

        bpy.ops.mesh.primitive_plane_add(size=223.0, location=(bx, 0.0, -0.95))
        r = bpy.context.active_object
        r.data.materials.append(rim_mat)

    p1 = import_stl(os.path.join(OUT_DIR, "humerus_8to9yr_wire_tilt40.stl"), "Plate1_Humerus_Tilt40")
    p1.location.x = -130.0
    p1.data.materials.append(bone_mat)

    p2 = import_stl(os.path.join(OUT_DIR, "plate_02_forearm_shoulder_8to9yr.stl"), "Plate2_4Bones")
    p2.location.x = 130.0
    p2.data.materials.append(bone_mat)

    out_png = os.path.join(OUT_DIR, "child_8to9yr_k1_plates_preview.png")
    setup_studio_and_render((0.0, -520.0, 440.0), (0.0, 0.0, 35.0), out_png, res_x=1400, res_y=840)
    shutil.copy2(out_png, os.path.join(ARTIFACT_DIR, "child_8to9yr_k1_plates_preview.png"))


def main():
    audit_results = build_individual_bones()
    build_plate2_forearm_shoulder(audit_results)

    report_path = os.path.join(OUT_DIR, "child_8to9yr_audit_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "age_group": "8-9 years (240 mm humerus)",
                "wire_hole_diameter_mm": HOLE_DIAMETER_MM,
                "all_passed": all(r["passed"] for r in audit_results.values()),
                "files": audit_results,
            },
            f,
            indent=2,
        )

    render_wire_hole_assembly_preview()
    render_k1_plates_preview()

    # Clean up internal straight humerus helper file (keep only K1-ready files)
    tmp_straight = os.path.join(OUT_DIR, "_humerus_8to9yr_wire_straight.stl")
    if os.path.exists(tmp_straight):
        os.remove(tmp_straight)

    print("ALL_PASSED:", all(r["passed"] for r in audit_results.values()))


if __name__ == "__main__":
    main()
