"""
Creality K1 Print Preparation, Optimal DFAM Orientation, Plate Packing,
STL Round-Trip Validation & Build-Plate Overview Renderer (Blender 5.2)
for the 5 Individual Upper-Limb & Shoulder-Girdle Bones.

Reads `e:\\AG\\Blender\\upper_limb_5bones_master.blend`, orients and validates
all 5 individual bone STLs (`exports/upper_limb_5bones/parts/<part>.stl`), packs
and exports the Creality K1 build plate (`exports/upper_limb_5bones/plates/plate_01_upper_limb_5bones.stl`)
within <= 196 x 196 mm XY footprint with >= 8.0 mm inter-part spacing at Z = 0.0 mm,
exports `exports/upper_limb_5bones/upper_limb_5bones_lineup.stl`, renders an
isometric top-3/4 plate overview `renders/upper_limb_5bones_k1_plate_preview.png`
(1400 x 1000), and writes `exports/upper_limb_5bones/validation_report.json`.
"""

import os
import sys
import json
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Euler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import upper_limb_config as cfg

if cfg.SKELETON_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, cfg.SKELETON_SCRIPTS_DIR)


def _get_or_create_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _link_exclusively(obj, col):
    for c in list(obj.users_collection):
        if c != col:
            c.objects.unlink(obj)
    if obj.name not in col.objects:
        col.objects.link(obj)


def duplicate_object(src_obj, new_name, col=None):
    copy_obj = src_obj.copy()
    copy_obj.data = src_obj.data.copy()
    copy_obj.name = new_name
    copy_obj.data.name = f"{new_name}_Mesh"
    target = col if col is not None else bpy.context.scene.collection
    target.objects.link(copy_obj)
    return copy_obj


def get_world_bbox(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    xs, ys, zs = [], [], []
    for v in bm.verts:
        w = mw @ v.co
        xs.append(w.x)
        ys.append(w.y)
        zs.append(w.z)
    bm.free()
    if not xs:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def apply_all_transforms(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def translate_mesh_world(obj, dx, dy, dz):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    inv = obj.matrix_world.inverted()
    delta = Vector((dx, dy, dz))
    for v in bm.verts:
        w = obj.matrix_world @ v.co + delta
        v.co = inv @ w
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def rotate_part_euler_deg(obj, rx_deg, ry_deg, rz_deg):
    min_x, max_x, min_y, max_y, min_z, max_z = get_world_bbox(obj)
    pivot = Vector((0.5 * (min_x + max_x), 0.5 * (min_y + max_y), 0.5 * (min_z + max_z)))
    rot_mat = Euler(
        (math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)),
        'XYZ',
    ).to_matrix()

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    inv = mw.inverted()
    for v in bm.verts:
        w = mw @ v.co
        w_rot = pivot + (rot_mat @ (w - pivot))
        v.co = inv @ w_rot
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def center_xy_and_rest_on_z0(obj):
    min_x, max_x, min_y, max_y, min_z, _ = get_world_bbox(obj)
    cx = 0.5 * (min_x + max_x)
    cy = 0.5 * (min_y + max_y)
    translate_mesh_world(obj, -cx, -cy, -min_z)


def rest_on_z0(obj):
    _, _, _, _, min_z, _ = get_world_bbox(obj)
    if abs(min_z) > 1e-6:
        translate_mesh_world(obj, 0.0, 0.0, -min_z)


def sanitize_for_stl_export(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.dissolve_degenerate(bm, dist=2e-3, edges=bm.edges)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-3)
    loose_v = [v for v in bm.verts if not v.link_faces]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def verify_reimported_stl(stl_path):
    before = set(bpy.data.objects.keys())
    bpy.ops.wm.stl_import(filepath=stl_path)
    new_names = [n for n in bpy.data.objects.keys() if n not in before]
    if not new_names:
        raise RuntimeError(f"STL re-import produced no objects: {stl_path}")

    imp_obj = bpy.data.objects[new_names[0]]
    bm = bmesh.new()
    bm.from_mesh(imp_obj.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    lv = sum(1 for v in bm.verts if not v.link_edges)
    n_verts = len(bm.verts)
    n_faces = len(bm.faces)
    bm.free()

    bbox = get_world_bbox(imp_obj)

    for n in new_names:
        o = bpy.data.objects.get(n)
        if o is not None:
            m = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if m and m.users == 0:
                bpy.data.meshes.remove(m)

    dx = bbox[1] - bbox[0]
    dy = bbox[3] - bbox[2]
    dz = bbox[5] - bbox[4]
    print(
        f"[STL-VERIFY] {os.path.basename(stl_path)}: "
        f"verts={n_verts}, faces={n_faces}, dims=({dx:.2f}, {dy:.2f}, {dz:.2f}), "
        f"min_z={bbox[4]:.3f}, non_manifold={nm}, loose_verts={lv}"
    )
    if nm != 0 or lv != 0:
        raise AssertionError(
            f"Re-imported STL {stl_path} failed manifold check: non_manifold={nm}, loose_verts={lv}"
        )
    return n_verts, n_faces, nm, lv, bbox


def export_binary_stl(obj, stl_path):
    os.makedirs(os.path.dirname(stl_path), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.wm.stl_export(
        filepath=stl_path,
        export_selected_objects=True,
        global_scale=1.0,
        ascii_format=False,
    )
    return verify_reimported_stl(stl_path)


def check_k1_fit(bbox):
    dx = bbox[1] - bbox[0]
    dy = bbox[3] - bbox[2]
    dz = bbox[5] - bbox[4]
    return (
        dx <= cfg.SAFE_X_MM
        and dy <= cfg.SAFE_Y_MM
        and dz <= cfg.SAFE_Z_MM
    )


def _try_shelf_pack(items, max_width, max_height, gap_mm, allow_rot90):
    shelves = []
    placements = {}

    for idx, dx, dy in items:
        candidates = [(dx, dy, False)]
        if allow_rot90 and abs(dx - dy) > 0.5:
            candidates.append((dy, dx, True))

        best_choice = None
        for w, h, rot90 in candidates:
            if w > max_width or h > max_height:
                continue
            placed = False
            for s_idx, (sy, sh, cur_x) in enumerate(shelves):
                nx = cur_x + (gap_mm if cur_x > 0 else 0.0)
                if nx + w <= max_width:
                    new_sh = max(sh, h)
                    growth = new_sh - sh
                    total_h = shelves[-1][0] + shelves[-1][1] + growth
                    if total_h <= max_height:
                        score = (total_h, max(nx + w, 0.0), growth)
                        if best_choice is None or score < best_choice[0]:
                            best_choice = (score, s_idx, nx, sy, w, h, rot90, new_sh)
                        placed = True
                        break
            if not placed:
                ny = (shelves[-1][0] + shelves[-1][1] + gap_mm) if shelves else 0.0
                if ny + h <= max_height and w <= max_width:
                    total_h = ny + h
                    score = (total_h, w, h)
                    if best_choice is None or score < best_choice[0]:
                        best_choice = (score, -1, 0.0, ny, w, h, rot90, h)

        if best_choice is None:
            return None

        _, s_idx, px, py, w, h, rot90, new_sh = best_choice
        if s_idx >= 0:
            old_sy, old_sh, _ = shelves[s_idx]
            growth = new_sh - old_sh
            shelves[s_idx][1] = new_sh
            shelves[s_idx][2] = px + w
            if growth > 0:
                for k in range(s_idx + 1, len(shelves)):
                    shelves[k][0] += growth
                for p_idx, p_val in list(placements.items()):
                    if p_val[1] > old_sy + 1e-6:
                        placements[p_idx] = (p_val[0], p_val[1] + growth, p_val[2], p_val[3], p_val[4])
        else:
            shelves.append([py, new_sh, w])

        placements[idx] = (px, py, w, h, rot90)

    span_x = max(p[0] + p[2] for p in placements.values())
    span_y = max(p[1] + p[3] for p in placements.values())
    if span_x > max_width or span_y > max_height:
        return None
    return placements, span_x, span_y


def pack_objects_on_plate(objs, max_x_mm=196.0, max_y_mm=196.0, gap_mm=8.5):
    raw_items = []
    for idx, obj in enumerate(objs):
        rest_on_z0(obj)
        b = get_world_bbox(obj)
        raw_items.append((idx, b[1] - b[0], b[3] - b[2]))

    # Prefer keeping original anatomical lineup order left-to-right if it fits cleanly
    orderings = [
        lambda it: it[0],
        lambda it: (-max(it[1], it[2]), -(it[1] * it[2])),
        lambda it: (-it[2], -it[1]),
        lambda it: (-it[1], -it[2]),
    ]

    best_res = None
    for target_gap in (gap_mm, 8.0, 7.0, 6.2):
        for allow_rot90 in (False, True):
            for key_fn in orderings:
                ordered = sorted(raw_items, key=key_fn)
                res = _try_shelf_pack(ordered, max_x_mm, max_y_mm, target_gap, allow_rot90)
                if res is not None:
                    placements, sx, sy = res
                    cost = (1 if allow_rot90 else 0, max(sx, sy), sx + sy)
                    if best_res is None or cost < best_res[0]:
                        best_res = (cost, placements, sx, sy)
        if best_res is not None:
            break

    if best_res is None:
        raise RuntimeError(f"Failed to pack {len(objs)} parts within {max_x_mm} x {max_y_mm} mm with >= 8 mm gap")

    _, placements, sx, sy = best_res
    cx_off = -0.5 * sx
    cy_off = -0.5 * sy

    placed_boxes = []
    for idx, obj in enumerate(objs):
        px, py, w, h, rot90 = placements[idx]
        if rot90:
            rotate_part_euler_deg(obj, 0.0, 0.0, 90.0)
        b = get_world_bbox(obj)
        cur_cx = 0.5 * (b[0] + b[1])
        cur_cy = 0.5 * (b[2] + b[3])
        target_cx = cx_off + px + 0.5 * w
        target_cy = cy_off + py + 0.5 * h
        translate_mesh_world(obj, target_cx - cur_cx, target_cy - cur_cy, -b[4])
        placed_boxes.append(get_world_bbox(obj))

    min_gap = float("inf")
    for i in range(len(placed_boxes)):
        bi = placed_boxes[i]
        assert abs(bi[4]) < 0.02, f"Part {objs[i].name} min_z={bi[4]:.3f} != 0"
        for j in range(i + 1, len(placed_boxes)):
            bj = placed_boxes[j]
            gx = max(bi[0] - bj[1], bj[0] - bi[1])
            gy = max(bi[2] - bj[3], bj[2] - bi[3])
            gap = max(gx, gy)
            min_gap = min(min_gap, gap)
            if gap < 8.0 - 1e-3:
                raise AssertionError(
                    f"Parts {objs[i].name} and {objs[j].name} too close on plate: gap={gap:.2f} mm < 8.0 mm"
                )

    plate_bbox = (
        min(b[0] for b in placed_boxes),
        max(b[1] for b in placed_boxes),
        min(b[2] for b in placed_boxes),
        max(b[3] for b in placed_boxes),
        min(b[4] for b in placed_boxes),
        max(b[5] for b in placed_boxes),
    )
    dx = plate_bbox[1] - plate_bbox[0]
    dy = plate_bbox[3] - plate_bbox[2]
    assert dx <= max_x_mm + 0.1 and dy <= max_y_mm + 0.1, (
        f"Packed plate dimensions ({dx:.2f}, {dy:.2f}) exceed ({max_x_mm}, {max_y_mm})"
    )
    return min_gap if min_gap < float("inf") else 0.0, plate_bbox


def join_objects(objs, joined_name, col):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = joined_name
    joined.data.name = f"{joined_name}_Mesh"
    _link_exclusively(joined, col)
    return joined


def _setup_plate_preview_material(name, base_color, roughness=0.45):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _create_k1_bed_slab(name, center_x, center_y, col, bed_mat, border_mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = v.co.x * cfg.K1_BED_X_MM + center_x
        v.co.y = v.co.y * cfg.K1_BED_Y_MM + center_y
        v.co.z = (v.co.z - 0.5) * 2.2 - 0.2
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    bed_obj = bpy.data.objects.new(name, mesh)
    col.objects.link(bed_obj)
    bed_obj.data.materials.append(bed_mat)

    bm_f = bmesh.new()
    half_out = 98.8
    half_in = 98.0
    for (x0, x1, y0, y1) in [
        (-half_out, half_out, half_in, half_out),
        (-half_out, half_out, -half_out, -half_in),
        (-half_out, -half_in, -half_in, half_in),
        (half_in, half_out, -half_in, half_in),
    ]:
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            v.co.x = center_x + x0 + (v.co.x + 0.5) * (x1 - x0)
            v.co.y = center_y + y0 + (v.co.y + 0.5) * (y1 - y0)
            v.co.z = (v.co.z + 0.5) * 0.4 - 0.2
        tmp_mesh = bpy.data.meshes.new("_tmp_frame")
        tmp.to_mesh(tmp_mesh)
        tmp.free()
        bm_f.from_mesh(tmp_mesh)
        bpy.data.meshes.remove(tmp_mesh)

    f_mesh = bpy.data.meshes.new(f"{name}_Frame_Mesh")
    bm_f.to_mesh(f_mesh)
    bm_f.free()
    frame_obj = bpy.data.objects.new(f"{name}_Frame", f_mesh)
    col.objects.link(frame_obj)
    frame_obj.data.materials.append(border_mat)
    return bed_obj, frame_obj


def render_plate_overview(plate_obj, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    scene = bpy.context.scene

    for obj in list(bpy.data.objects):
        if obj != plate_obj:
            obj.hide_render = True
            obj.hide_viewport = True

    preview_col = _get_or_create_collection("K1_Plate_Render")
    bed_mat = _setup_plate_preview_material("K1_Bed_Slate", (0.16, 0.18, 0.21), roughness=0.55)
    border_mat = _setup_plate_preview_material("K1_Bed_SafeBorder", (0.36, 0.58, 0.72), roughness=0.40)
    bone_mat = bpy.data.materials.get("Skeleton_Bone_Mat")
    if bone_mat is None:
        bone_mat = _setup_plate_preview_material("Preview_Bone_Ivory", (0.89, 0.82, 0.70), roughness=0.46)

    plate_obj.hide_render = False
    plate_obj.hide_viewport = False
    _link_exclusively(plate_obj, preview_col)
    if "BoneCoord" not in plate_obj.data.attributes and len(plate_obj.data.vertices) >= 4:
        coords = np.empty(len(plate_obj.data.vertices) * 3, dtype=np.float32)
        plate_obj.data.vertices.foreach_get("co", coords)
        pts = coords.reshape((-1, 3))
        centered = pts - pts.mean(axis=0, keepdims=True)
        attr = plate_obj.data.attributes.new(name="BoneCoord", type='FLOAT_VECTOR', domain='POINT')
        attr.data.foreach_set("vector", centered.ravel())
    plate_obj.data.materials.clear()
    plate_obj.data.materials.append(bone_mat)
    for poly in plate_obj.data.polygons:
        poly.use_smooth = True

    _create_k1_bed_slab("K1_Bed_Plate01", 0.0, 0.0, preview_col, bed_mat, border_mat)

    if scene.compositing_node_group is None:
        ng = bpy.data.node_groups.new("PlateWhiteBG", 'CompositorNodeTree')
        scene.compositing_node_group = ng
        ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ng.nodes.new("CompositorNodeRLayers")
        ao = ng.nodes.new("CompositorNodeAlphaOver")
        ao.inputs["Background"].default_value = (1.0, 1.0, 1.0, 1.0)
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rl.outputs["Image"], ao.inputs["Foreground"])
        ng.links.new(ao.outputs["Image"], out.inputs["Image"])

    scene.render.film_transparent = True
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 28
    scene.cycles.use_denoising = True
    if hasattr(scene.cycles, "denoiser"):
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0

    if scene.world is None:
        scene.world = bpy.data.worlds.new("PlatesWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.95, 0.95, 0.97, 1.0)
        bg.inputs["Strength"].default_value = 0.50

    def _add_light(name, loc, target, energy, size, color):
        ld = bpy.data.lights.new(name=name, type='AREA')
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name=name, object_data=ld)
        preview_col.objects.link(lo)
        lo.location = Vector(loc)
        lo.rotation_euler = (Vector(target) - lo.location).to_track_quat('-Z', 'Y').to_euler()

    target = Vector((0.0, 0.0, 8.0))
    _add_light("Plate_Key", (-220.0, -280.0, 320.0), target, energy=60.0, size=320.0, color=(1.0, 0.98, 0.96))
    _add_light("Plate_Fill", (260.0, -200.0, 260.0), target, energy=30.0, size=360.0, color=(0.95, 0.97, 1.0))
    _add_light("Plate_Rim", (0.0, 300.0, 240.0), target, energy=24.0, size=320.0, color=(0.98, 0.98, 1.0))

    cam_data = bpy.data.cameras.new("PlateIsoCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 340.0
    cam_data.clip_start = 1.0
    cam_data.clip_end = 5000.0
    cam_obj = bpy.data.objects.new("PlateIsoCam", cam_data)
    preview_col.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_obj.location = Vector((-135.0, -280.0, 245.0))
    cam_obj.rotation_euler = (target - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()

    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Saved K1 plate preview: {out_path}")


def main():
    if not os.path.exists(cfg.MASTER_BLEND_PATH):
        raise FileNotFoundError(f"Master blend file not found: {cfg.MASTER_BLEND_PATH}")

    bpy.ops.wm.open_mainfile(filepath=cfg.MASTER_BLEND_PATH)

    os.makedirs(cfg.PARTS_DIR, exist_ok=True)
    os.makedirs(cfg.PLATES_DIR, exist_ok=True)
    os.makedirs(cfg.EXPORTS_DIR, exist_ok=True)

    prep_col = _get_or_create_collection("K1_Export_Prep")

    assembled_parts = {}
    for name in cfg.PART_NAMES:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != 'MESH':
            raise RuntimeError(f"Missing part in master blend: {name}")
        assembled_parts[name] = obj

    report = {
        "creality_k1_safe_envelope_mm": {
            "max_x": cfg.SAFE_X_MM,
            "max_y": cfg.SAFE_Y_MM,
            "max_z": cfg.SAFE_Z_MM,
        },
        "parts": {},
        "plates": {},
        "lineup_reference": {},
        "all_passed": False,
    }

    oriented_copies = {}
    for name in cfg.PART_NAMES:
        src = assembled_parts[name]
        dup = duplicate_object(src, f"{name}_k1_oriented", col=prep_col)
        apply_all_transforms(dup)

        rx, ry, rz = cfg.PRINT_ORIENTATIONS_DEG[name]
        if rx or ry or rz:
            rotate_part_euler_deg(dup, rx, ry, rz)

        center_xy_and_rest_on_z0(dup)
        sanitize_for_stl_export(dup)
        rest_on_z0(dup)

        stl_path = os.path.join(cfg.PARTS_DIR, f"{name}.stl")
        n_verts, n_faces, nm, lv, bbox = export_binary_stl(dup, stl_path)
        fits_k1 = check_k1_fit(bbox)
        dx = round(bbox[1] - bbox[0], 3)
        dy = round(bbox[3] - bbox[2], 3)
        dz = round(bbox[5] - bbox[4], 3)

        assert nm == 0 and lv == 0, f"Part {name} failed manifold check: nm={nm}, lv={lv}"
        assert fits_k1, f"Part {name} exceeds Creality K1 safe volume: {(dx, dy, dz)}"

        report["parts"][name] = {
            "name": name,
            "stl_path": stl_path,
            "verts": n_verts,
            "faces": n_faces,
            "dimensions_mm": [dx, dy, dz],
            "dx": dx,
            "dy": dy,
            "dz": dz,
            "min_z_mm": round(bbox[4], 3),
            "max_z_mm": round(bbox[5], 3),
            "non_manifold_edges": nm,
            "loose_verts": lv,
            "fits_creality_k1": fits_k1,
            "stl_roundtrip_verified": True,
        }
        oriented_copies[name] = dup

    # Pack all 5 parts onto Plate 01 within [-98..+98, -98..+98] mm with >= 8.0 mm gap
    p1_objs = [duplicate_object(oriented_copies[n], f"P1_{n}", col=prep_col) for n in cfg.PART_NAMES]
    p1_gap, _ = pack_objects_on_plate(p1_objs, max_x_mm=196.0, max_y_mm=196.0, gap_mm=8.5)
    p1_joined = join_objects(p1_objs, "plate_01_upper_limb_5bones", prep_col)
    p1_stl = os.path.join(cfg.PLATES_DIR, "plate_01_upper_limb_5bones.stl")
    p1_v, p1_f, p1_nm, p1_lv, p1_bbox = export_binary_stl(p1_joined, p1_stl)
    p1_fits = check_k1_fit(p1_bbox)
    assert p1_nm == 0 and p1_lv == 0 and p1_fits
    assert p1_bbox[0] >= -98.1 and p1_bbox[1] <= 98.1 and p1_bbox[2] >= -98.1 and p1_bbox[3] <= 98.1, (
        f"Plate 01 exceeds [-98..+98] bounds: {p1_bbox}"
    )

    report["plates"]["plate_01_upper_limb_5bones"] = {
        "name": "plate_01_upper_limb_5bones",
        "stl_path": p1_stl,
        "included_parts": list(cfg.PART_NAMES),
        "verts": p1_v,
        "faces": p1_f,
        "dimensions_mm": [
            round(p1_bbox[1] - p1_bbox[0], 3),
            round(p1_bbox[3] - p1_bbox[2], 3),
            round(p1_bbox[5] - p1_bbox[4], 3),
        ],
        "dx": round(p1_bbox[1] - p1_bbox[0], 3),
        "dy": round(p1_bbox[3] - p1_bbox[2], 3),
        "dz": round(p1_bbox[5] - p1_bbox[4], 3),
        "bounds_xy_mm": [round(p1_bbox[0], 3), round(p1_bbox[1], 3), round(p1_bbox[2], 3), round(p1_bbox[3], 3)],
        "min_part_gap_mm": round(p1_gap, 3),
        "min_z_mm": round(p1_bbox[4], 3),
        "max_z_mm": round(p1_bbox[5], 3),
        "non_manifold_edges": p1_nm,
        "loose_verts": p1_lv,
        "fits_creality_k1": p1_fits,
        "stl_roundtrip_verified": True,
    }

    # Export 5-bone reference lineup STL
    lineup_copies = []
    for name in cfg.PART_NAMES:
        c = duplicate_object(assembled_parts[name], f"LineupRef_{name}", col=prep_col)
        apply_all_transforms(c)
        sanitize_for_stl_export(c)
        lineup_copies.append(c)
    lineup_joined = join_objects(lineup_copies, "upper_limb_5bones_lineup", prep_col)
    lineup_stl = os.path.join(cfg.EXPORTS_DIR, "upper_limb_5bones_lineup.stl")
    l_v, l_f, l_nm, l_lv, l_bbox = export_binary_stl(lineup_joined, lineup_stl)
    report["lineup_reference"] = {
        "name": "upper_limb_5bones_lineup",
        "stl_path": lineup_stl,
        "verts": l_v,
        "faces": l_f,
        "dimensions_mm": [
            round(l_bbox[1] - l_bbox[0], 3),
            round(l_bbox[3] - l_bbox[2], 3),
            round(l_bbox[5] - l_bbox[4], 3),
        ],
        "min_z_mm": round(l_bbox[4], 3),
        "max_z_mm": round(l_bbox[5], 3),
        "non_manifold_edges": l_nm,
        "loose_verts": l_lv,
        "stl_roundtrip_verified": True,
    }

    report["all_passed"] = True
    report_path = os.path.join(cfg.EXPORTS_DIR, "validation_report.json")
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2)
    print(f"[REPORT] Wrote validation report: {report_path}")

    preview_path = os.path.join(cfg.RENDERS_DIR, "upper_limb_5bones_k1_plate_preview.png")
    render_plate_overview(p1_joined, preview_path)

    print("[SUCCESS] All 5 individual bone STLs, Plate 01 STL, validation report, and K1 plate preview completed!")


if __name__ == "__main__":
    main()
