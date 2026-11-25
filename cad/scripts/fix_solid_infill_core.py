"""
Rebuild the 5 upper-limb bone meshes (scapula, clavicle, humerus, ulna, radius)
with full-bodied solid cores and flat bed-grounded posterior contact so that
FDM slicers (Creality Print K1 default 0.20/0.16 mm AND custom sparse-infill
profiles) generate continuous Sparse Infill inside perimeter walls along the
entire shaft/blade instead of filling thin arched shafts with solid shells.

Updates and verifies:
  1. Poster-scale set:
       - upper_limb_5bones_master.blend
       - exports/upper_limb_5bones/parts/{scapula,clavicle,humerus,ulna,radius}.stl
       - exports/upper_limb_5bones/plates/plate_01_upper_limb_5bones.stl
       - exports/upper_limb_5bones/upper_limb_5bones_lineup.stl
       - exports/upper_limb_5bones/validation_report.json
  2. True-anatomical 1:2 & 1:1 sets + individual blends:
       - upper_limb_5bones_realbone_master.blend
       - exports/upper_limb_5bones/realbone_1to2/{scapula,clavicle,humerus,ulna,radius,plate_01_realbone_1to2_5bones}.stl
       - exports/upper_limb_5bones/realbone_1to1_lifesize/{scapula,clavicle,humerus,ulna,radius}_1to1.stl
       - exports/upper_limb_5bones/blend_individual/{scapula,clavicle,humerus,ulna,radius}.blend
       - exports/upper_limb_5bones/realbone_validation_report.json
"""

import json
import math
import os
import sys

import bmesh
import bpy
import mathutils
import numpy as np


ROOT = r"e:\AG\Blender"
EXPORT_ROOT = os.path.join(ROOT, "exports", "upper_limb_5bones")

BONE_NAMES = ["scapula", "clavicle", "humerus", "ulna", "radius"]

# Uniform scale from 1:2 anatomical set to 1:1 adult life-size fits K1 220x220 bed
SCALE_1TO1 = 1.6874
DIAGONAL_ROT_1TO1 = {
    "scapula": 0.0,
    "clavicle": 0.0,
    "humerus": math.radians(45.0),
    "ulna": math.radians(45.0),
    "radius": math.radians(45.0),
}

POSTER_SPECS = {
    "scapula": {
        "min_shaft_dx": None,
        "max_x_scale": 1.0,
        "z_scale": 1.12,
        "z_lift": 4.2,
        "grid_step": 0.36,
        "voxel_size": 0.30,
        "plinth_frac": 0.58,
    },
    "clavicle": {
        "min_shaft_dx": 9.8,
        "max_x_scale": 1.45,
        "z_scale": 1.38,
        "z_lift": 2.2,
        "grid_step": 0.30,
        "voxel_size": 0.28,
        "plinth_frac": 0.58,
    },
    "humerus": {
        "min_shaft_dx": 10.6,
        "max_x_scale": 1.35,
        "z_scale": 1.14,
        "z_lift": 1.8,
        "grid_step": 0.34,
        "voxel_size": 0.28,
        "plinth_frac": 0.58,
    },
    "ulna": {
        "min_shaft_dx": 9.8,
        "max_x_scale": 1.62,
        "z_scale": 1.34,
        "z_lift": 2.0,
        "grid_step": 0.30,
        "voxel_size": 0.28,
        "plinth_frac": 0.58,
    },
    "radius": {
        "min_shaft_dx": 9.8,
        "max_x_scale": 1.45,
        "z_scale": 1.24,
        "z_lift": 2.0,
        "grid_step": 0.30,
        "voxel_size": 0.28,
        "plinth_frac": 0.58,
    },
}

REALBONE_1TO2_SPECS = {
    "scapula": {
        "min_shaft_dx": None,
        "max_x_scale": 1.0,
        "z_scale": 1.12,
        "z_lift": 4.2,
        "grid_step": 0.36,
        "voxel_size": 0.30,
        "plinth_frac": 0.58,
    },
    "clavicle": {
        "min_shaft_dx": 9.6,
        "max_x_scale": 1.62,
        "z_scale": 1.45,
        "z_lift": 2.2,
        "grid_step": 0.28,
        "voxel_size": 0.26,
        "plinth_frac": 0.58,
    },
    "humerus": {
        "min_shaft_dx": 12.6,
        "max_x_scale": 1.15,
        "z_scale": 1.02,
        "z_lift": 0.6,
        "grid_step": 0.38,
        "voxel_size": 0.30,
        "plinth_frac": 0.56,
    },
    "ulna": {
        "min_shaft_dx": 10.4,
        "max_x_scale": 1.35,
        "z_scale": 1.16,
        "z_lift": 1.8,
        "grid_step": 0.32,
        "voxel_size": 0.28,
        "plinth_frac": 0.58,
    },
    "radius": {
        "min_shaft_dx": 10.4,
        "max_x_scale": 1.25,
        "z_scale": 1.12,
        "z_lift": 1.6,
        "grid_step": 0.32,
        "voxel_size": 0.28,
        "plinth_frac": 0.58,
    },
}


def mesh_stats(obj):
    """Compute manifold, island, volume, and bounding stats for a mesh object."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    degen_faces = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    vol = bm.calc_volume(signed=True)

    # Count connected vertex components
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

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    nv, nf = len(bm.verts), len(bm.faces)
    bm.free()

    return {
        "verts": nv,
        "tris": nf,
        "non_manifold_edges": non_manifold,
        "loose_verts": loose_verts,
        "degenerate_faces": degen_faces,
        "islands": islands,
        "signed_volume_mm3": round(float(vol), 2),
        "bounds_mm": {
            "x": [round(min(xs), 3), round(max(xs), 3)],
            "y": [round(min(ys), 3), round(max(ys), 3)],
            "z": [round(min(zs), 3), round(max(zs), 3)],
        },
        "dims_mm": {
            "dx": round(max(xs) - min(xs), 2),
            "dy": round(max(ys) - min(ys), 2),
            "dz": round(max(zs) - min(zs), 2),
        },
    }


def flatten_bed_bottom_clean(obj, cut_z=0.22):
    """Slice cleanly at Z = cut_z, cap bottom polygon(s), shift down to Z = 0.0."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Ensure there are verts below cut_z; if not, just shift min_z -> 0
    min_z = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= min_z

    geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(
        bm,
        geom=geom,
        dist=1e-5,
        plane_co=(0.0, 0.0, cut_z),
        plane_no=(0.0, 0.0, 1.0),
        clear_inner=True,
        clear_outer=False,
    )

    bm.edges.ensure_lookup_table()
    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if boundary_edges:
        bmesh.ops.triangle_fill(
            bm,
            edges=boundary_edges,
            use_beauty=True,
        )

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    for v in bm.verts:
        v.co.z -= cut_z
        if abs(v.co.z) < 1e-4:
            v.co.z = 0.0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def solidify_and_ground_bed_object(obj, spec):
    """
    Given a bone object already oriented in print-bed space (X width, Y length,
    Z >= 0 vertical height off bed, centered XY at 0), thicken narrow shafts,
    boost vertical Z headroom, union a grounded bed plinth down to Z=0,
    voxel-remesh + smooth, and flatten the bottom cleanly on Z = 0.0.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    # 1. Optional gentle longitudinal shaft X widening preserving S-curve center
    if spec["min_shaft_dx"] is not None:
        ys = [v.co.y for v in bm.verts]
        ymin, ymax = min(ys), max(ys)
        nbins = 64
        bins_x = [[] for _ in range(nbins)]
        for v in bm.verts:
            bi = min(nbins - 1, max(0, int((v.co.y - ymin) / (ymax - ymin + 1e-6) * nbins)))
            bins_x[bi].append(v.co.x)
        xc = [0.5 * (min(b) + max(b)) if b else 0.0 for b in bins_x]
        dx = [(max(b) - min(b)) if b else spec["min_shaft_dx"] for b in bins_x]
        for _ in range(5):
            xc = [xc[0]] + [0.25 * xc[i - 1] + 0.5 * xc[i] + 0.25 * xc[i + 1] for i in range(1, nbins - 1)] + [xc[-1]]
            dx = [dx[0]] + [0.25 * dx[i - 1] + 0.5 * dx[i] + 0.25 * dx[i + 1] for i in range(1, nbins - 1)] + [dx[-1]]
        for v in bm.verts:
            t = (v.co.y - ymin) / (ymax - ymin + 1e-6) * (nbins - 1)
            i0 = min(nbins - 2, max(0, int(t)))
            f = t - i0
            c = xc[i0] * (1.0 - f) + xc[i0 + 1] * f
            w = dx[i0] * (1.0 - f) + dx[i0 + 1] * f
            sx = max(1.0, min(spec["max_x_scale"], spec["min_shaft_dx"] / max(w, 1e-3)))
            v.co.x = c + sx * (v.co.x - c)

    # 2. Lift and boost vertical height Z
    min_z0 = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z = (v.co.z - min_z0) * spec["z_scale"] + spec["z_lift"]

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    bpy.context.view_layer.update()

    # 3. Raycast XY silhouette grid to construct watertight bed-grounded plinth
    deps = bpy.context.evaluated_depsgraph_get()
    bvh = mathutils.bvhtree.BVHTree.FromObject(obj, deps)
    bb = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xmin = min(c.x for c in bb) - 1.0
    xmax = max(c.x for c in bb) + 1.0
    ymin = min(c.y for c in bb) - 1.0
    ymax = max(c.y for c in bb) + 1.0

    step = spec["grid_step"]
    xs = np.arange(xmin, xmax + step, step)
    ys_g = np.arange(ymin, ymax + step, step)
    nx, ny = len(xs), len(ys_g)

    z_top = np.full((nx, ny), -1.0)
    z_bot = np.full((nx, ny), -1.0)
    inside = np.zeros((nx, ny), dtype=bool)
    for ix, gx in enumerate(xs):
        for iy, gy in enumerate(ys_g):
            lt, _, _, _ = bvh.ray_cast((float(gx), float(gy), 200.0), (0.0, 0.0, -1.0), 400.0)
            lb, _, _, _ = bvh.ray_cast((float(gx), float(gy), -200.0), (0.0, 0.0, 1.0), 400.0)
            if lt and lb and lt.z > lb.z + 0.2:
                inside[ix, iy] = True
                z_top[ix, iy] = lt.z
                z_bot[ix, iy] = lb.z

    # Erode 1 ring so plinth tucks cleanly under rounded equator walls
    eroded = inside.copy()
    eroded[1:-1, 1:-1] = (
        inside[1:-1, 1:-1]
        & inside[:-2, 1:-1]
        & inside[2:, 1:-1]
        & inside[1:-1, :-2]
        & inside[1:-1, 2:]
    )
    eroded[0, :] = False
    eroded[-1, :] = False
    eroded[:, 0] = False
    eroded[:, -1] = False

    bm_p = bmesh.new()
    bot_v = {}
    top_v = {}
    frac = spec["plinth_frac"]
    for ix in range(1, nx):
        for iy in range(1, ny):
            if eroded[ix - 1, iy - 1]:
                for dx_i, dy_i in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    key = (ix - 1 + dx_i, iy - 1 + dy_i)
                    if key not in bot_v:
                        gx, gy = float(xs[key[0]]), float(ys_g[key[1]])
                        nbrs_t = [
                            z_top[a, b]
                            for a in range(max(0, key[0] - 1), min(nx, key[0] + 2))
                            for b in range(max(0, key[1] - 1), min(ny, key[1] + 2))
                            if inside[a, b]
                        ]
                        nbrs_b = [
                            z_bot[a, b]
                            for a in range(max(0, key[0] - 1), min(nx, key[0] + 2))
                            for b in range(max(0, key[1] - 1), min(ny, key[1] + 2))
                            if inside[a, b]
                        ]
                        zt = sum(nbrs_t) / len(nbrs_t) if nbrs_t else 8.0
                        zb = sum(nbrs_b) / len(nbrs_b) if nbrs_b else 3.0
                        z_ceil = max(zb + 1.6, frac * zt + (1.0 - frac) * zb)
                        # Extend slightly below 0 so bisect at +0.22 cuts a flat base cleanly
                        bot_v[key] = bm_p.verts.new((gx, gy, -0.35))
                        top_v[key] = bm_p.verts.new((gx, gy, float(z_ceil)))

    bm_p.verts.ensure_lookup_table()
    for ix in range(nx - 1):
        for iy in range(ny - 1):
            if eroded[ix, iy]:
                k00, k10, k11, k01 = (ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)
                bm_p.faces.new((top_v[k00], top_v[k10], top_v[k11], top_v[k01]))
                bm_p.faces.new((bot_v[k00], bot_v[k01], bot_v[k11], bot_v[k10]))
                if ix == 0 or not eroded[ix - 1, iy]:
                    bm_p.faces.new((bot_v[k00], top_v[k00], top_v[k01], bot_v[k01]))
                if ix + 1 >= nx - 1 or not eroded[ix + 1, iy]:
                    bm_p.faces.new((bot_v[k10], bot_v[k11], top_v[k11], top_v[k10]))
                if iy == 0 or not eroded[ix, iy - 1]:
                    bm_p.faces.new((bot_v[k00], bot_v[k10], top_v[k10], top_v[k00]))
                if iy + 1 >= ny - 1 or not eroded[ix, iy + 1]:
                    bm_p.faces.new((bot_v[k01], top_v[k01], top_v[k11], bot_v[k11]))

    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    mesh_p = bpy.data.meshes.new("tmp_plinth")
    bm_p.to_mesh(mesh_p)
    bm_p.free()
    obj_p = bpy.data.objects.new("tmp_plinth", mesh_p)
    bpy.context.collection.objects.link(obj_p)

    # 4. Join original anatomical mesh + plinth and Voxel Remesh + Smooth
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    obj_p.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()

    rm = obj.modifiers.new("Remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = spec["voxel_size"]
    rm.adaptivity = 0.0
    bpy.ops.object.modifier_apply(modifier="Remesh")

    sm = obj.modifiers.new("Smooth", "CORRECTIVE_SMOOTH")
    sm.iterations = 12
    sm.smooth_type = "LENGTH_WEIGHTED"
    sm.rest_source = "ORCO"
    bpy.ops.object.modifier_apply(modifier="Smooth")

    # 5. Slice bottom cleanly at Z=0.0 without degenerate triangles, center XY=0
    flatten_bed_bottom_clean(obj, cut_z=0.55)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    mz = min(zs)
    for v in bm.verts:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= mz
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def copy_mesh_to_upright_lineup_object(bed_obj, lineup_obj, orig_x_center, orig_z_min):
    """
    Copy solidified bed-space mesh back into the upright studio lineup object,
    preserving material slots, X-slot placement, anterior facing -Y, and base Z.
    """
    mats = list(lineup_obj.data.materials)

    bm = bmesh.new()
    bm.from_mesh(bed_obj.data)
    zs = [v.co.z for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    half_z = 0.5 * (max(zs) + min(zs))
    ymin = min(ys)

    # Rotate +90° around X: (x_anat, y_anat, z_anat) = (x_bed, -z_bed, y_bed)
    for v in bm.verts:
        xb, yb, zb = v.co.x, v.co.y, v.co.z
        v.co.x = orig_x_center + xb
        v.co.y = half_z - zb
        v.co.z = orig_z_min + (yb - ymin)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(lineup_obj.data)
    bm.free()

    lineup_obj.data.materials.clear()
    for m in mats:
        if m is not None:
            lineup_obj.data.materials.append(m)
    lineup_obj.data.update()


def make_bed_copy_from_upright(upright_obj, name):
    """Create a temporary flat print-bed object (-90° around X) from an upright object."""
    bm = bmesh.new()
    bm.from_mesh(upright_obj.data)
    # Transform upright (X, Y, Z) -> bed (x=X, y=Z, z=-Y) centered XY, min_z=0
    for v in bm.verts:
        xa, ya, za = v.co.x, v.co.y, v.co.z
        v.co.x = xa
        v.co.y = za
        v.co.z = -ya
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    mz = min(zs)
    for v in bm.verts:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= mz
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_bed_tmp")
    bm.to_mesh(mesh)
    bm.free()
    bed_obj = bpy.data.objects.new(name + "_bed_tmp", mesh)
    bpy.context.collection.objects.link(bed_obj)
    return bed_obj


def export_single_stl(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)


def verify_stl_roundtrip(path):
    """Import exported STL back into a temp object and compute full manifold/island checks."""
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.wm.stl_import(filepath=path)
    imp = bpy.context.active_object
    st = mesh_stats(imp)
    bpy.data.objects.remove(imp, do_unlink=True)
    ok = (
        st["non_manifold_edges"] == 0
        and st["loose_verts"] == 0
        and st["degenerate_faces"] == 0
        and st["islands"] == 1
        and st["signed_volume_mm3"] > 0.0
        and abs(st["bounds_mm"]["z"][0]) <= 0.01
    )
    st["passed"] = ok
    return st


def build_plate_stl(bed_objs, out_path, gap_mm=8.5):
    """Arrange all 5 flat bed-oriented bones in a single build plate STL centered X=0, min_z=0."""
    widths = [o.dimensions.x for o in bed_objs]
    lengths = [o.dimensions.y for o in bed_objs]
    total_w = sum(widths) + gap_mm * (len(bed_objs) - 1)
    max_len = max(lengths)

    bm_all = bmesh.new()
    cur_x = -0.5 * total_w
    for o in bed_objs:
        w = o.dimensions.x
        l = o.dimensions.y
        bm_part = bmesh.new()
        bm_part.from_mesh(o.data)
        dx_shift = (cur_x + 0.5 * w)
        dy_shift = -0.5 * max_len + 0.5 * l
        for v in bm_part.verts:
            v.co.x += dx_shift
            v.co.y += dy_shift
        tmp_m = bpy.data.meshes.new("tmp_plate_part")
        bm_part.to_mesh(tmp_m)
        bm_part.free()
        bm_all.from_mesh(tmp_m)
        bpy.data.meshes.remove(tmp_m)
        cur_x += w + gap_mm

    bmesh.ops.recalc_face_normals(bm_all, faces=bm_all.faces)
    mesh_plate = bpy.data.meshes.new("tmp_plate_mesh")
    bm_all.to_mesh(mesh_plate)
    bm_all.free()
    plate_obj = bpy.data.objects.new("tmp_plate_obj", mesh_plate)
    bpy.context.collection.objects.link(plate_obj)
    export_single_stl(plate_obj, out_path)
    st = mesh_stats(plate_obj)
    bpy.data.objects.remove(plate_obj, do_unlink=True)
    bpy.data.meshes.remove(mesh_plate)
    return st


def process_poster_set():
    print("\n=== STEP 1A: Rebuilding Poster Set (upper_limb_5bones_master.blend) ===")
    master_blend = os.path.join(ROOT, "upper_limb_5bones_master.blend")
    bpy.ops.wm.open_mainfile(filepath=master_blend)

    bed_objs = []
    report = {"set": "poster_scale", "parts": {}, "all_passed": True}

    for name in BONE_NAMES:
        upright_obj = bpy.data.objects[name]
        vs = [v.co for v in upright_obj.data.vertices]
        orig_xc = 0.5 * (min(v.x for v in vs) + max(v.x for v in vs))
        orig_zmin = min(v.z for v in vs)

        bed_obj = make_bed_copy_from_upright(upright_obj, f"{name}_poster")
        solidify_and_ground_bed_object(bed_obj, POSTER_SPECS[name])
        copy_mesh_to_upright_lineup_object(bed_obj, upright_obj, orig_xc, orig_zmin)

        stl_path = os.path.join(EXPORT_ROOT, "parts", f"{name}.stl")
        export_single_stl(bed_obj, stl_path)
        st = verify_stl_roundtrip(stl_path)
        report["parts"][name] = st
        if not st["passed"]:
            report["all_passed"] = False
        print(f"  poster/{name}.stl -> dims={st['dims_mm']} vol={st['signed_volume_mm3']} passed={st['passed']}")
        bed_objs.append(bed_obj)

    # Export combined plate STL
    plate_path = os.path.join(EXPORT_ROOT, "plates", "plate_01_upper_limb_5bones.stl")
    plate_st = build_plate_stl(bed_objs, plate_path, gap_mm=8.5)
    plate_st["passed"] = plate_st["non_manifold_edges"] == 0 and plate_st["islands"] == 5 and plate_st["signed_volume_mm3"] > 0
    report["plate_01_upper_limb_5bones"] = plate_st
    print(f"  poster/plate_01 -> dims={plate_st['dims_mm']} islands={plate_st['islands']} passed={plate_st['passed']}")

    # Export upright lineup STL
    lineup_path = os.path.join(EXPORT_ROOT, "upper_limb_5bones_lineup.stl")
    bpy.ops.object.select_all(action="DESELECT")
    for name in BONE_NAMES:
        bpy.data.objects[name].select_set(True)
    bpy.ops.wm.stl_export(filepath=lineup_path, export_selected_objects=True)

    # Clean up temporary bed objects before saving master blend
    for bo in bed_objs:
        m = bo.data
        bpy.data.objects.remove(bo, do_unlink=True)
        bpy.data.meshes.remove(m)

    bpy.ops.wm.save_as_mainfile(filepath=master_blend)

    val_path = os.path.join(EXPORT_ROOT, "validation_report.json")
    with open(val_path, "w") as f:
        json.dump(report, f, indent=2)
    return report


def process_realbone_sets():
    print("\n=== STEP 1B: Rebuilding Real-Bone 1:2, 1:1 & Individual Blends ===")
    master_blend = os.path.join(ROOT, "upper_limb_5bones_realbone_master.blend")
    bpy.ops.wm.open_mainfile(filepath=master_blend)

    bed_objs = []
    report = {"set": "realbone_anatomical", "parts_1to2": {}, "parts_1to1": {}, "all_passed": True}

    bone_mat = bpy.data.materials.get("Skeleton_Bone_Mat")

    for name in BONE_NAMES:
        upright_obj = bpy.data.objects[name]
        vs = [v.co for v in upright_obj.data.vertices]
        orig_xc = 0.5 * (min(v.x for v in vs) + max(v.x for v in vs))
        orig_zmin = min(v.z for v in vs)

        bed_obj = make_bed_copy_from_upright(upright_obj, f"{name}_rb")
        solidify_and_ground_bed_object(bed_obj, REALBONE_1TO2_SPECS[name])
        copy_mesh_to_upright_lineup_object(bed_obj, upright_obj, orig_xc, orig_zmin)

        # Export 1:2 STL
        stl_1to2 = os.path.join(EXPORT_ROOT, "realbone_1to2", f"{name}.stl")
        export_single_stl(bed_obj, stl_1to2)
        st2 = verify_stl_roundtrip(stl_1to2)
        report["parts_1to2"][name] = st2
        if not st2["passed"]:
            report["all_passed"] = False
        print(f"  1:2/{name}.stl -> dims={st2['dims_mm']} vol={st2['signed_volume_mm3']} passed={st2['passed']}")

        # Export 1:1 life-size STL (uniformly scaled + rotated for K1 220x220 bed if long)
        bm1 = bmesh.new()
        bm1.from_mesh(bed_obj.data)
        rot_z = mathutils.Matrix.Rotation(DIAGONAL_ROT_1TO1[name], 3, "Z")
        for v in bm1.verts:
            v.co = rot_z @ (v.co * SCALE_1TO1)
        xs = [v.co.x for v in bm1.verts]
        ys = [v.co.y for v in bm1.verts]
        zs = [v.co.z for v in bm1.verts]
        cx, cy, mz = 0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys)), min(zs)
        for v in bm1.verts:
            v.co.x -= cx
            v.co.y -= cy
            v.co.z -= mz
        bmesh.ops.recalc_face_normals(bm1, faces=bm1.faces)
        mesh1 = bpy.data.meshes.new(f"{name}_1to1_tmp")
        bm1.to_mesh(mesh1)
        bm1.free()
        obj1 = bpy.data.objects.new(f"{name}_1to1_tmp", mesh1)
        bpy.context.collection.objects.link(obj1)

        stl_1to1 = os.path.join(EXPORT_ROOT, "realbone_1to1_lifesize", f"{name}_1to1.stl")
        export_single_stl(obj1, stl_1to1)
        st1 = verify_stl_roundtrip(stl_1to1)
        fits_k1 = st1["dims_mm"]["dx"] <= 216.0 and st1["dims_mm"]["dy"] <= 216.0
        st1["fits_k1_bed_220x220"] = fits_k1
        if not st1["passed"] or not fits_k1:
            report["all_passed"] = False
        report["parts_1to1"][name] = st1
        print(f"  1:1/{name}_1to1.stl -> dims={st1['dims_mm']} fits_K1={fits_k1} passed={st1['passed']}")
        bpy.data.objects.remove(obj1, do_unlink=True)
        bpy.data.meshes.remove(mesh1)

        bed_objs.append(bed_obj)

    # Combined 1:2 K1 plate STL
    plate_1to2 = os.path.join(EXPORT_ROOT, "realbone_1to2", "plate_01_realbone_1to2_5bones.stl")
    pst = build_plate_stl(bed_objs, plate_1to2, gap_mm=8.5)
    pst["passed"] = pst["non_manifold_edges"] == 0 and pst["islands"] == 5 and pst["signed_volume_mm3"] > 0
    report["plate_01_realbone_1to2_5bones"] = pst
    print(f"  1:2/plate_01 -> dims={pst['dims_mm']} islands={pst['islands']} passed={pst['passed']}")

    # Remove temp bed objs before saving realbone master blend
    for bo in bed_objs:
        m = bo.data
        bpy.data.objects.remove(bo, do_unlink=True)
        bpy.data.meshes.remove(m)

    bpy.ops.wm.save_as_mainfile(filepath=master_blend)

    # Write individual standalone .blend files for each bone (flat bed 1:2 oriented + Skeleton_Bone_Mat)
    blend_dir = os.path.join(EXPORT_ROOT, "blend_individual")
    os.makedirs(blend_dir, exist_ok=True)
    for name in BONE_NAMES:
        stl_in = os.path.join(EXPORT_ROOT, "realbone_1to2", f"{name}.stl")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 0.001
        bpy.ops.wm.stl_import(filepath=stl_in)
        o = bpy.context.active_object
        o.name = name
        o.data.name = name
        mat = bpy.data.materials.new("Skeleton_Bone_Mat")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.855, 0.775, 0.635, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.58
        o.data.materials.append(mat)
        out_blend = os.path.join(blend_dir, f"{name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        print(f"  Saved individual blend: {out_blend}")

    val_path = os.path.join(EXPORT_ROOT, "realbone_validation_report.json")
    with open(val_path, "w") as f:
        json.dump(report, f, indent=2)
    return report


def main():
    r_poster = process_poster_set()
    r_real = process_realbone_sets()
    if not r_poster["all_passed"] or not r_real["all_passed"]:
        print("ERROR: Validation failed!", file=sys.stderr)
        sys.exit(1)
    print("\nALL 5 BONES ACROSS POSTER, 1:2, 1:1 & BLENDS REBUILT AND PASSED!")


if __name__ == "__main__":
    main()
