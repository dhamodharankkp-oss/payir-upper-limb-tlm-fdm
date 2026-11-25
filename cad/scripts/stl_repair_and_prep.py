r"""
Reusable, product-agnostic STL Repair & Creality K1 Print-Prep CLI (Blender 5.2).

Usage:
  blender.exe --background --python e:\AG\Blender\scripts\tools\stl_repair_and_prep.py -- \
    --input <in.stl> --output <out.stl> \
    --profile <organic_slender|mechanical_precision|flat_enclosure> \
    [--mode flat|tilt40|split-pin] \
    [--scale 1.0] [--target-length 190.0] \
    [--keep-largest-island] [--voxel-repair 0.25] [--tilt-angle 40.0]
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

DEFAULT_PROFILES_PATH = (
    r"e:\AG\Blender\.agents\skills\creality-k1-3dprint-workflow"
    r"\references\product_profiles.json"
)


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    p = argparse.ArgumentParser(description="STL Repair & Creality K1 Print-Prep CLI")
    p.add_argument("--input", required=True, help="Input STL file path")
    p.add_argument("--output", required=True, help="Output STL file path")
    p.add_argument(
        "--profile",
        default="organic_slender",
        help="Product profile key in product_profiles.json",
    )
    p.add_argument(
        "--profiles-json",
        default=DEFAULT_PROFILES_PATH,
        help="Path to product_profiles.json",
    )
    p.add_argument(
        "--mode",
        choices=["flat", "tilt40", "split-pin"],
        default=None,
        help="Print orientation/prep mode (defaults to profile default)",
    )
    p.add_argument("--scale", type=float, default=1.0, help="Uniform scale multiplier")
    p.add_argument(
        "--target-length",
        type=float,
        default=None,
        help="Scale uniformly so longest bounding-box dimension equals this mm value",
    )
    p.add_argument(
        "--keep-largest-island",
        action="store_true",
        help="Remove stray disconnected fragments, keeping only the largest island",
    )
    p.add_argument(
        "--voxel-repair",
        type=float,
        default=None,
        help="Force voxel remesh size in mm (only when profile allows voxel repair)",
    )
    p.add_argument(
        "--tilt-angle",
        type=float,
        default=None,
        help="Override tilt angle in degrees for tilt40 mode",
    )
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_stl(filepath: str):
    bpy.ops.wm.stl_import(filepath=filepath)
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        raise RuntimeError(f"No mesh objects imported from {filepath}")
    if len(objs) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()
    obj = objs[0]
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def export_stl(obj, filepath: str):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(
        filepath=filepath,
        export_selected_objects=True,
        ascii_format=False,
    )


def count_islands(bm: bmesh.types.BMesh) -> int:
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
                other = e.other_vert(cur)
                if other.index not in visited:
                    visited.add(other.index)
                    stack.append(other)
    return islands


def audit_mesh(obj, max_safe_xy: float = 216.0, max_safe_z: float = 246.0) -> dict:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()

    non_manifold_edges = sum(1 for e in bm.edges if not e.is_manifold)
    loose_verts = sum(1 for v in bm.verts if len(v.link_edges) == 0)
    degenerate_faces = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    islands = count_islands(bm) if len(bm.verts) > 0 else 0
    signed_volume = float(bm.calc_volume(signed=True))

    coords = [obj.matrix_world @ v.co for v in bm.verts]
    if coords:
        min_v = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
        max_v = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
        dims = max_v - min_v
    else:
        min_v = max_v = dims = Vector((0.0, 0.0, 0.0))

    verts_n = len(bm.verts)
    faces_n = len(bm.faces)
    bm.free()

    fits_k1 = (
        dims.x <= max_safe_xy
        and dims.y <= max_safe_xy
        and dims.z <= max_safe_z
    )
    return {
        "verts": verts_n,
        "faces": faces_n,
        "non_manifold_edges": non_manifold_edges,
        "loose_verts": loose_verts,
        "degenerate_faces": degenerate_faces,
        "islands": islands,
        "signed_volume_mm3": round(signed_volume, 3),
        "bbox_min_mm": [round(min_v.x, 3), round(min_v.y, 3), round(min_v.z, 3)],
        "bbox_max_mm": [round(max_v.x, 3), round(max_v.y, 3), round(max_v.z, 3)],
        "dims_mm": [round(dims.x, 3), round(dims.y, 3), round(dims.z, 3)],
        "min_z_mm": round(min_v.z, 4),
        "fits_K1": fits_k1,
    }


def keep_largest_island_bm(bm: bmesh.types.BMesh) -> int:
    bm.verts.index_update()
    visited = set()
    components = []
    for v in bm.verts:
        if v.index in visited:
            continue
        comp = []
        stack = [v]
        visited.add(v.index)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for e in cur.link_edges:
                other = e.other_vert(cur)
                if other.index not in visited:
                    visited.add(other.index)
                    stack.append(other)
        components.append(comp)
    if len(components) <= 1:
        return 0
    components.sort(key=len, reverse=True)
    to_delete = [v for comp in components[1:] for v in comp]
    bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
    return len(components) - 1


def repair_mesh(obj, profile_cfg: dict, keep_largest: bool, voxel_override: float | None):
    actions = []
    pre = audit_mesh(obj)
    already_clean = (
        pre["non_manifold_edges"] == 0
        and pre["loose_verts"] == 0
        and pre["degenerate_faces"] == 0
        and pre["signed_volume_mm3"] > 0
        and (not keep_largest or pre["islands"] == 1)
    )

    if already_clean and voxel_override is None:
        actions.append("already_watertight_no_topology_mutation")
        return actions

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    if keep_largest:
        removed_islands = keep_largest_island_bm(bm)
        if removed_islands > 0:
            actions.append(f"removed_{removed_islands}_small_islands")

    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    loose_v = [v for v in bm.verts if len(v.link_edges) == 0]
    if loose_v:
        bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
        actions.append(f"deleted_{len(loose_v)}_loose_verts")

    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])

    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if boundary_edges:
        bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
        actions.append(f"filled_holes_from_{len(boundary_edges)}_boundary_edges")

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    non_tri = [f for f in bm.faces if len(f.verts) > 3]
    if non_tri:
        bmesh.ops.triangulate(bm, faces=non_tri)

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    actions.append("topology_preserving_repair")

    mid = audit_mesh(obj)
    needs_voxel = (
        mid["non_manifold_edges"] > 0
        or mid["signed_volume_mm3"] <= 0
        or voxel_override is not None
    )

    if needs_voxel:
        if not profile_cfg.get("allow_voxel_repair_fallback", False):
            actions.append("voxel_fallback_blocked_by_profile_preserve_sharp_edges")
            return actions

        voxel_size = voxel_override or float(profile_cfg.get("default_voxel_size_mm", 0.25))
        remesh = obj.modifiers.new(name="VoxelRepair", type="REMESH")
        remesh.mode = "VOXEL"
        remesh.voxel_size = voxel_size
        remesh.use_smooth_shade = True

        smooth_iters = int(profile_cfg.get("corrective_smooth_iterations", 4))
        smooth_factor = float(profile_cfg.get("corrective_smooth_factor", 0.45))
        if smooth_iters > 0:
            cs = obj.modifiers.new(name="CorrectiveSmooth", type="CORRECTIVE_SMOOTH")
            cs.factor = smooth_factor
            cs.iterations = smooth_iters
            cs.rest_source = "ORCO"

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)

        actions.append(f"voxel_remesh_{voxel_size}mm_with_corrective_smooth")

    return actions


def center_and_ground(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    coords = [v.co for v in bm.verts]
    min_x = min(c.x for c in coords)
    max_x = max(c.x for c in coords)
    min_y = min(c.y for c in coords)
    max_y = max(c.y for c in coords)
    min_z = min(c.z for c in coords)
    shift = Vector((-(min_x + max_x) * 0.5, -(min_y + max_y) * 0.5, -min_z))
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=shift)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def apply_uniform_scale(obj, scale_factor: float):
    if abs(scale_factor - 1.0) < 1e-7:
        return
    obj.scale = (scale_factor, scale_factor, scale_factor)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def prep_tilt40(obj, tilt_angle_deg: float):
    """
    Tilt the longest horizontal axis by tilt_angle_deg with the heavier/wider end DOWN
    on the build plate (Z = 0) for single-piece organic prints with minimal overhang scarring.
    """
    center_and_ground(obj)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    coords = [v.co for v in bm.verts]
    span_x = max(c.x for c in coords) - min(c.x for c in coords)
    span_y = max(c.y for c in coords) - min(c.y for c in coords)

    # Determine principal horizontal axis (0=X, 1=Y)
    if span_x >= span_y:
        # Compare mass/cross-section at negative X vs positive X ends (outer 20%)
        min_x = min(c.x for c in coords)
        max_x = max(c.x for c in coords)
        neg_pts = [c for c in coords if c.x <= min_x + 0.20 * span_x]
        pos_pts = [c for c in coords if c.x >= max_x - 0.20 * span_x]
        neg_spread = (
            (max(c.y for c in neg_pts) - min(c.y for c in neg_pts))
            * (max(c.z for c in neg_pts) - min(c.z for c in neg_pts))
            if neg_pts
            else 0.0
        )
        pos_spread = (
            (max(c.y for c in pos_pts) - min(c.y for c in pos_pts))
            * (max(c.z for c in pos_pts) - min(c.z for c in pos_pts))
            if pos_pts
            else 0.0
        )
        # Rotate around Y: negative angle lifts +X (keeps -X down); positive angle lifts -X (keeps +X down)
        rad = math.radians(tilt_angle_deg)
        rot_y = -rad if neg_spread >= pos_spread else rad
        mat = Matrix.Rotation(rot_y, 4, "Y")
    else:
        min_y = min(c.y for c in coords)
        max_y = max(c.y for c in coords)
        neg_pts = [c for c in coords if c.y <= min_y + 0.20 * span_y]
        pos_pts = [c for c in coords if c.y >= max_y - 0.20 * span_y]
        neg_spread = (
            (max(c.x for c in neg_pts) - min(c.x for c in neg_pts))
            * (max(c.z for c in neg_pts) - min(c.z for c in neg_pts))
            if neg_pts
            else 0.0
        )
        pos_spread = (
            (max(c.x for c in pos_pts) - min(c.x for c in pos_pts))
            * (max(c.z for c in pos_pts) - min(c.z for c in pos_pts))
            if pos_pts
            else 0.0
        )
        rad = math.radians(tilt_angle_deg)
        rot_x = rad if neg_spread >= pos_spread else -rad
        mat = Matrix.Rotation(rot_x, 4, "X")

    bmesh.ops.transform(bm, matrix=mat, verts=bm.verts[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    center_and_ground(obj)


def _bisect_half(src_obj, name: str, z_mid: float, keep_top: bool):
    mesh_copy = src_obj.data.copy()
    half_obj = bpy.data.objects.new(name, mesh_copy)
    bpy.context.collection.objects.link(half_obj)

    bm = bmesh.new()
    bm.from_mesh(half_obj.data)
    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        dist=1e-5,
        plane_co=Vector((0.0, 0.0, z_mid)),
        plane_no=Vector((0.0, 0.0, 1.0)),
        use_snap_center=False,
        clear_outer=not keep_top,
        clear_inner=keep_top,
    )
    # Cap open cut boundary cleanly
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if boundary_edges:
        bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)
    non_tri = [f for f in bm.faces if len(f.verts) > 3]
    if non_tri:
        bmesh.ops.triangulate(bm, faces=non_tri)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(half_obj.data)
    bm.free()
    half_obj.data.update()
    return half_obj


def _find_peg_locations(obj, z_mid: float, peg_dia: float, peg_depth: float):
    """
    Find 2-3 safe interior peg (x, y, safe_depth) locations along the longest horizontal axis
    at the z_mid cut plane where cross-section width and thickness allow clean sockets.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    coords = [v.co for v in bm.verts]
    bm.free()

    min_x = min(c.x for c in coords)
    max_x = max(c.x for c in coords)
    min_y = min(c.y for c in coords)
    max_y = max(c.y for c in coords)
    span_x = max_x - min_x
    span_y = max_y - min_y
    along_x = span_x >= span_y

    # Try 3 candidate fractions along the length (0.18, 0.50, 0.82), then fallback to 2
    candidates = [0.20, 0.50, 0.80]
    band = max(span_x, span_y) * 0.06
    pegs = []

    for frac in candidates:
        if along_x:
            target = min_x + frac * span_x
            slice_pts = [c for c in coords if abs(c.x - target) <= band]
            if len(slice_pts) < 8:
                continue
            ys = [c.y for c in slice_pts]
            zs = [c.z for c in slice_pts]
            width = max(ys) - min(ys)
            cy = 0.5 * (min(ys) + max(ys))
            top_avail = max(zs) - z_mid
            bot_avail = z_mid - min(zs)
            safe_depth = min(peg_depth, top_avail - 1.4, bot_avail - 1.4)
            if width >= peg_dia + 2.6 and safe_depth >= 1.8:
                pegs.append((target, cy, safe_depth))
        else:
            target = min_y + frac * span_y
            slice_pts = [c for c in coords if abs(c.y - target) <= band]
            if len(slice_pts) < 8:
                continue
            xs = [c.x for c in slice_pts]
            zs = [c.z for c in slice_pts]
            width = max(xs) - min(xs)
            cx = 0.5 * (min(xs) + max(xs))
            top_avail = max(zs) - z_mid
            bot_avail = z_mid - min(zs)
            safe_depth = min(peg_depth, top_avail - 1.4, bot_avail - 1.4)
            if width >= peg_dia + 2.6 and safe_depth >= 1.8:
                pegs.append((cx, target, safe_depth))

    return pegs


def _cut_peg_sockets(half_obj, pegs, z_mid: float, peg_dia: float, is_top: bool):
    if not pegs:
        return
    radius = peg_dia * 0.5
    for idx, (px, py, depth) in enumerate(pegs):
        # Extend 0.6 mm past z_mid so boolean cut breaks the cap cleanly
        total_h = depth + 0.6
        cz = (z_mid + depth * 0.5 - 0.3) if is_top else (z_mid - depth * 0.5 + 0.3)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=radius,
            depth=total_h,
            location=(px, py, cz),
        )
        cyl = bpy.context.active_object
        cyl.name = f"PegCutter_{idx}"

        mod = half_obj.modifiers.new(name=f"PegBool_{idx}", type="BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cyl

        bpy.ops.object.select_all(action="DESELECT")
        half_obj.select_set(True)
        bpy.context.view_layer.objects.active = half_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

        bpy.data.objects.remove(cyl, do_unlink=True)


def prep_split_pin(obj, profile_cfg: dict):
    """
    Bisect mesh horizontally at mid-Z, add Ø1.85 mm filament peg alignment sockets,
    lay both cut faces flat on Z = 0 side-by-side for zero-support printing.
    """
    center_and_ground(obj)
    sp_cfg = profile_cfg.get("split_pin", {})
    peg_dia = float(sp_cfg.get("peg_diameter_mm", 1.85))
    peg_depth = float(sp_cfg.get("peg_depth_mm", 4.0))
    half_gap = float(sp_cfg.get("half_gap_mm", 8.0))

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    coords = [v.co for v in bm.verts]
    span_x = max(c.x for c in coords) - min(c.x for c in coords)
    span_y = max(c.y for c in coords) - min(c.y for c in coords)
    min_z = min(c.z for c in coords)
    max_z = max(c.z for c in coords)
    bm.free()

    z_mid = 0.5 * (min_z + max_z)
    pegs = _find_peg_locations(obj, z_mid, peg_dia, peg_depth)

    top_half = _bisect_half(obj, "TopHalf", z_mid, keep_top=True)
    bot_half = _bisect_half(obj, "BottomHalf", z_mid, keep_top=False)

    _cut_peg_sockets(top_half, pegs, z_mid, peg_dia, is_top=True)
    _cut_peg_sockets(bot_half, pegs, z_mid, peg_dia, is_top=False)

    # Remove original unsplit object
    bpy.data.objects.remove(obj, do_unlink=True)

    # Flip bottom half 180 deg so its cut face also lies flat on Z = 0
    if span_x >= span_y:
        bot_half.rotation_euler = (math.pi, 0.0, 0.0)
    else:
        bot_half.rotation_euler = (0.0, math.pi, 0.0)

    bpy.ops.object.select_all(action="DESELECT")
    bot_half.select_set(True)
    bpy.context.view_layer.objects.active = bot_half
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    center_and_ground(top_half)
    center_and_ground(bot_half)

    # Separate side-by-side along the shorter horizontal axis
    top_info = audit_mesh(top_half)
    bot_info = audit_mesh(bot_half)
    if span_x >= span_y:
        offset_y = 0.5 * (top_info["dims_mm"][1] + bot_info["dims_mm"][1]) + half_gap
        top_half.location.y = -offset_y * 0.5
        bot_half.location.y = offset_y * 0.5
    else:
        offset_x = 0.5 * (top_info["dims_mm"][0] + bot_info["dims_mm"][0]) + half_gap
        top_half.location.x = -offset_x * 0.5
        bot_half.location.x = offset_x * 0.5

    bpy.ops.object.select_all(action="DESELECT")
    top_half.select_set(True)
    bot_half.select_set(True)
    bpy.context.view_layer.objects.active = top_half
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()

    combined = bpy.context.active_object
    combined.name = "SplitPinPrepared"

    # Clean up any sliver/degenerate triangles introduced by exact boolean cuts
    bm = bmesh.new()
    bm.from_mesh(combined.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
    non_tri = [f for f in bm.faces if len(f.verts) > 3]
    if non_tri:
        bmesh.ops.triangulate(bm, faces=non_tri)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(combined.data)
    bm.free()
    combined.data.update()

    center_and_ground(combined)
    return combined, len(pegs)


def main():
    args = parse_args()
    with open(args.profiles_json, "r", encoding="utf-8") as f:
        registry = json.load(f)

    if args.profile not in registry["profiles"]:
        raise ValueError(
            f"Unknown profile '{args.profile}'. Available: {list(registry['profiles'].keys())}"
        )

    printer_cfg = registry["printer"]
    profile_cfg = registry["profiles"][args.profile]
    mode = args.mode or profile_cfg.get("default_mode", "flat")

    if mode not in profile_cfg.get("supported_modes", ["flat"]):
        raise ValueError(
            f"Mode '{mode}' is not supported by profile '{args.profile}' "
            f"(supported: {profile_cfg.get('supported_modes')})"
        )

    clear_scene()
    obj = import_stl(args.input)
    pre_audit = audit_mesh(obj, printer_cfg["max_safe_xy_mm"])

    repair_actions = repair_mesh(
        obj, profile_cfg, args.keep_largest_island, args.voxel_repair
    )

    # Apply uniform scaling (--target-length takes precedence if specified)
    applied_scale = args.scale
    if args.target_length is not None:
        cur_audit = audit_mesh(obj, printer_cfg["max_safe_xy_mm"])
        cur_max = max(cur_audit["dims_mm"])
        if cur_max <= 0:
            raise RuntimeError("Mesh has zero dimension; cannot scale to target length.")
        applied_scale = args.target_length / cur_max
    apply_uniform_scale(obj, applied_scale)

    peg_count = 0
    if mode == "flat":
        center_and_ground(obj)
    elif mode == "tilt40":
        angle = args.tilt_angle or float(profile_cfg.get("tilt_angle_deg", 40.0))
        prep_tilt40(obj, angle)
    elif mode == "split-pin":
        obj, peg_count = prep_split_pin(obj, profile_cfg)

    export_stl(obj, args.output)

    # Round-trip verification
    clear_scene()
    reimported = import_stl(args.output)
    post_audit = audit_mesh(reimported, printer_cfg["max_safe_xy_mm"])

    expected_islands = 2 if mode == "split-pin" else 1
    passed = (
        post_audit["non_manifold_edges"] == 0
        and post_audit["loose_verts"] == 0
        and post_audit["degenerate_faces"] == 0
        and post_audit["signed_volume_mm3"] > 0
        and abs(post_audit["min_z_mm"]) <= 0.01
        and post_audit["fits_K1"]
    )

    report = {
        "input": os.path.abspath(args.input),
        "output": os.path.abspath(args.output),
        "profile": args.profile,
        "mode": mode,
        "applied_scale": round(applied_scale, 6),
        "peg_sockets_per_half": peg_count,
        "recommended_orcaslicer_preset": profile_cfg["recommended_orcaslicer_presets"].get(mode),
        "repair_actions": repair_actions,
        "pre_audit": pre_audit,
        "post_audit_roundtrip": post_audit,
        "expected_islands": expected_islands,
        "passed": passed,
    }

    out_path = Path(args.output)
    report_path = out_path.with_name(out_path.stem + "_repair_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(
        f"[stl_repair_and_prep] {out_path.name} | profile={args.profile} | mode={mode} | "
        f"dims={post_audit['dims_mm']} | nm={post_audit['non_manifold_edges']} | "
        f"lv={post_audit['loose_verts']} | islands={post_audit['islands']} | "
        f"pegs={peg_count} | fits_K1={post_audit['fits_K1']} | PASS={passed}"
    )


if __name__ == "__main__":
    main()
