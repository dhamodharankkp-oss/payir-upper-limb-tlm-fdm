r"""
Exports the 240 mm Age 8-9 Humerus as two flat, zero-support, 45-deg K1-fitted halves
with 3x Ø1.85 mm filament-peg alignment sockets:
  - humerus_8to9yr_wire_split_halfA.stl
  - humerus_8to9yr_wire_split_halfB.stl
"""

import math
import os
import sys

sys.path.insert(0, r"e:\AG\Blender\scripts\tools")
import bmesh
import bpy
import stl_repair_and_prep as srp

OUT_DIR = r"e:\AG\Blender\exports\upper_limb_5bones\child_8to9yr_articulated"
SRC_FLAT45 = os.path.join(OUT_DIR, "humerus_8to9yr_wire_flat45.stl")


def clean_slivers(obj):
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


def main():
    srp.clear_scene()
    obj = srp.import_stl(SRC_FLAT45)
    obj.rotation_euler = (0.0, 0.0, math.radians(-45.0))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(rotation=True)
    srp.center_and_ground(obj)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    coords = [v.co for v in bm.verts]
    z_mid = 0.5 * (min(c.z for c in coords) + max(c.z for c in coords))
    bm.free()

    pegs = srp._find_peg_locations(obj, z_mid, 1.85, 4.0)
    top_half = srp._bisect_half(obj, "HalfA_Top", z_mid, keep_top=True)
    bot_half = srp._bisect_half(obj, "HalfB_Bottom", z_mid, keep_top=False)
    srp._cut_peg_sockets(top_half, pegs, z_mid, 1.85, is_top=True)
    srp._cut_peg_sockets(bot_half, pegs, z_mid, 1.85, is_top=False)
    bpy.data.objects.remove(obj, do_unlink=True)

    # Flip bottom half 180 deg around Y so its cut face lies flat on Z=0
    bot_half.rotation_euler = (0.0, math.pi, 0.0)
    bpy.ops.object.select_all(action="DESELECT")
    bot_half.select_set(True)
    bpy.context.view_layer.objects.active = bot_half
    bpy.ops.object.transform_apply(rotation=True)

    exported = []
    for half, fname in [
        (top_half, "humerus_8to9yr_wire_split_halfA.stl"),
        (bot_half, "humerus_8to9yr_wire_split_halfB.stl"),
    ]:
        clean_slivers(half)
        half.rotation_euler = (0.0, 0.0, math.radians(45.0))
        bpy.ops.object.select_all(action="DESELECT")
        half.select_set(True)
        bpy.context.view_layer.objects.active = half
        bpy.ops.object.transform_apply(rotation=True)
        srp.center_and_ground(half)
        out_p = os.path.join(OUT_DIR, fname)
        srp.export_stl(half, out_p)
        exported.append((fname, out_p))

    for fname, out_p in exported:
        srp.clear_scene()
        reimp = srp.import_stl(out_p)
        aud = srp.audit_mesh(reimp)
        print(
            f"[SPLIT] {fname} | pegs={len(pegs)} | dims={aud['dims_mm']} | "
            f"nm={aud['non_manifold_edges']} | lv={aud['loose_verts']} | "
            f"degen={aud['degenerate_faces']} | min_z={aud['min_z_mm']} | fits_K1={aud['fits_K1']}"
        )


if __name__ == "__main__":
    main()
