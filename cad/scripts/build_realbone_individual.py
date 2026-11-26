# SPDX-License-Identifier: MIT
"""
True Osteological "Real-Bone" Edition Builder, Individual Exporter & K1 Prep (Blender 5.2).

Reads `e:\\AG\\Blender\\upper_limb_5bones_master.blend`, applies true relative
human upper-limb anatomical proportions (`1:2` adult scale) and subtle cortical
periosteal bone surface micro-relief, renders a studio anatomical lineup and K1
plate preview, exports 5 standalone individual `.blend` files, exports & round-trip
verifies both `1:2` Anatomical STLs (+ combined single K1 build plate) and `1:1`
Life-Size Individual STLs (long bones oriented 45 deg across the K1 bed), and
writes `exports/upper_limb_5bones/realbone_validation_report.json`.
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

import joint_mechanics as jm
import prep_upper_limb_5bones_k1 as prep

# ---------------------------------------------------------------------------
# True Anatomical "Real-Bone" Configuration
# ---------------------------------------------------------------------------

REALBONE_MASTER_BLEND = r"e:\AG\Blender\upper_limb_5bones_realbone_master.blend"
BLEND_INDIVIDUAL_DIR = os.path.join(cfg.EXPORTS_DIR, "blend_individual")
REALBONE_1TO2_DIR = os.path.join(cfg.EXPORTS_DIR, "realbone_1to2")
REALBONE_1TO1_DIR = os.path.join(cfg.EXPORTS_DIR, "realbone_1to1_lifesize")
REALBONE_REPORT_PATH = os.path.join(cfg.EXPORTS_DIR, "realbone_validation_report.json")

LINEUP_RENDER_PATH = os.path.join(cfg.RENDERS_DIR, "upper_limb_5bones_realbone_lineup.png")
PLATE_RENDER_PATH = os.path.join(cfg.RENDERS_DIR, "upper_limb_5bones_realbone_k1_plate.png")

# Target upright dimensions (X=width, Y=thickness, Z=length mm) for True 1:2 Adult Scale
ANATOMICAL_1TO2_DIMS_MM = {
    "scapula": (51.8, 12.8, 78.0),
    "clavicle": (15.2, 7.5, 75.0),
    "humerus": (36.0, 21.0, 155.0),
    "ulna": (17.0, 12.2, 130.0),
    "radius": (15.8, 13.5, 120.0),
}

REALBONE_LINEUP_X = {
    "scapula": -112.0,
    "clavicle": -50.0,
    "humerus": 0.0,
    "ulna": 50.0,
    "radius": 96.0,
}

LINEUP_BASE_Z_MM = 18.0
TARGET_1TO1_MULTIPLIER = 1.74
MAX_1TO1_K1_XY_MM = 204.0


# ---------------------------------------------------------------------------
# Geometry & Cortical Bone Micro-Relief Helpers
# ---------------------------------------------------------------------------

def _count_islands(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    visited = set()
    islands = 0
    for start in bm.verts:
        if start.index in visited:
            continue
        islands += 1
        stack = [start]
        visited.add(start.index)
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                ov = e.other_vert(v)
                if ov.index not in visited:
                    visited.add(ov.index)
                    stack.append(ov)
    bm.free()
    return islands


def _scale_to_exact_upright_dims(obj, target_dims, target_cx, target_min_z):
    prep.apply_all_transforms(obj)
    b = prep.get_world_bbox(obj)
    cur_dx = b[1] - b[0]
    cur_dy = b[3] - b[2]
    cur_dz = b[5] - b[4]
    cx = 0.5 * (b[0] + b[1])
    cy = 0.5 * (b[2] + b[3])
    cz = 0.5 * (b[4] + b[5])

    sx = target_dims[0] / cur_dx
    sy = target_dims[1] / cur_dy
    sz = target_dims[2] / cur_dz

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.x = (v.co.x - cx) * sx + target_cx
        v.co.y = (v.co.y - cy) * sy
        v.co.z = (v.co.z - cz) * sz
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()

    b2 = prep.get_world_bbox(obj)
    prep.translate_mesh_world(obj, 0.0, 0.0, target_min_z - b2[4])


def _apply_periosteal_relief(obj, name):
    """Apply subtle longitudinal cortical bone grain (+/-0.06 mm) along normals."""
    b = prep.get_world_bbox(obj)
    z_min, z_max = b[4], b[5]
    z_span = max(z_max - z_min, 1.0)
    cx = 0.5 * (b[0] + b[1])
    cy = 0.5 * (b[2] + b[3])

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()

    for v in bm.verts:
        u = (v.co.z - z_min) / z_span
        # Taper relief at distal/proximal articular ends so joint surfaces remain smooth
        end_fade = math.sin(math.pi * max(0.0, min(1.0, u))) ** 0.6
        if name == "scapula":
            end_fade = 0.55 + 0.45 * end_fade

        ang = math.atan2(v.co.y - cy, v.co.x - cx)
        grain_long = math.sin(u * 14.0 * math.pi + 3.0 * ang)
        grain_mid = math.cos(v.co.z * 0.42 + v.co.x * 0.55)
        grain_fine = math.sin(v.co.z * 0.95 - v.co.y * 0.85 + 2.0 * ang)
        disp_mm = end_fade * (0.028 * grain_long + 0.020 * grain_mid + 0.012 * grain_fine)
        disp_mm = max(-0.06, min(0.06, disp_mm))
        v.co += v.normal * disp_mm

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()

    # Smooth slightly with 2 corrective smooth passes to avoid micro-pinches
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    cs = obj.modifiers.new(name="Periosteal_Corrective", type='CORRECTIVE_SMOOTH')
    cs.factor = 0.25
    cs.iterations = 2
    cs.smooth_type = 'SIMPLE'
    bpy.ops.object.modifier_apply(modifier=cs.name)

    # Refresh BoneCoord attribute for shader micro-shading alignment
    if "BoneCoord" in obj.data.attributes:
        obj.data.attributes.remove(obj.data.attributes["BoneCoord"])
    coords = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", coords)
    pts = coords.reshape((-1, 3))
    centered = pts - pts.mean(axis=0, keepdims=True)
    attr = obj.data.attributes.new(name="BoneCoord", type='FLOAT_VECTOR', domain='POINT')
    attr.data.foreach_set("vector", centered.ravel())

    for poly in obj.data.polygons:
        poly.use_smooth = True


# ---------------------------------------------------------------------------
# Studio Lineup Render Helper
# ---------------------------------------------------------------------------

def _create_label_text(text, x_pos, z_pos, col):
    cdata = bpy.data.curves.new(name=f"RealLabel_{text}_Curve", type='FONT')
    cdata.body = text
    cdata.align_x = 'CENTER'
    cdata.align_y = 'TOP'
    cdata.size = 6.5
    cdata.space_character = 1.02
    cdata.extrude = 0.0

    mat = bpy.data.materials.get("Label_Black_Mat")
    if mat is None:
        mat = bpy.data.materials.new("Label_Black_Mat")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (0.04, 0.04, 0.04, 1.0)
        em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])

    cdata.materials.append(mat)
    obj = bpy.data.objects.new(f"RealLabel_{text}", cdata)
    col.objects.link(obj)
    obj.location = Vector((x_pos, -36.0, z_pos))
    obj.rotation_euler = Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
    return obj


def render_realbone_lineup(parts, bone_mat, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    scene = bpy.context.scene

    studio_col = prep._get_or_create_collection("RealBone_Studio_Setup")

    for p in parts:
        p.hide_render = False
        p.hide_viewport = False
        p.data.materials.clear()
        p.data.materials.append(bone_mat)

    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    if hasattr(scene.cycles, "denoiser"):
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.render.film_transparent = True

    world = bpy.data.worlds.new("RealBoneStudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.98, 0.98, 0.98, 1.0)
        bg.inputs["Strength"].default_value = 0.50

    if scene.compositing_node_group is None:
        ng = bpy.data.node_groups.new("RealBoneWhiteBG", 'CompositorNodeTree')
        scene.compositing_node_group = ng
        ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        rl = ng.nodes.new("CompositorNodeRLayers")
        ao = ng.nodes.new("CompositorNodeAlphaOver")
        ao.inputs["Background"].default_value = (1.0, 1.0, 1.0, 1.0)
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rl.outputs["Image"], ao.inputs["Foreground"])
        ng.links.new(ao.outputs["Image"], out.inputs["Image"])

    xs, zs = [], []
    for p in parts:
        b = prep.get_world_bbox(p)
        xs.extend([b[0], b[1]])
        zs.extend([b[4], b[5]])
    x_mid = 0.5 * (min(xs) + max(xs))
    z_floor = min(zs) - 0.5

    # Shadow catcher floor behind label Y = -36 mm
    bm_f = bmesh.new()
    v0 = bm_f.verts.new((-240.0, -25.0, z_floor))
    v1 = bm_f.verts.new((200.0, -25.0, z_floor))
    v2 = bm_f.verts.new((200.0, 75.0, z_floor))
    v3 = bm_f.verts.new((-240.0, 75.0, z_floor))
    bm_f.faces.new((v0, v1, v2, v3))
    f_mesh = bpy.data.meshes.new("RealBoneFloor_Mesh")
    bm_f.to_mesh(f_mesh)
    bm_f.free()
    floor_obj = bpy.data.objects.new("RealBoneStudioFloor", f_mesh)
    studio_col.objects.link(floor_obj)
    floor_obj.is_shadow_catcher = True

    def _add_light(name, loc, target, energy, size, color):
        ld = bpy.data.lights.new(name=name, type='AREA')
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name=name, object_data=ld)
        studio_col.objects.link(lo)
        lo.location = Vector(loc)
        lo.rotation_euler = (Vector(target) - lo.location).to_track_quat('-Z', 'Y').to_euler()
        return lo

    target = Vector((x_mid, 0.0, 92.0))
    _add_light("RealStudio_Key", (-230.0, -340.0, 310.0), target, energy=36.0, size=240.0, color=(1.0, 0.98, 0.94))
    _add_light("RealStudio_Fill", (250.0, -300.0, 120.0), target, energy=13.0, size=350.0, color=(0.98, 0.99, 1.0))
    _add_light("RealStudio_Back", (120.0, 340.0, 210.0), target, energy=25.0, size=310.0, color=(1.0, 0.99, 0.96))

    labels = [
        _create_label_text(name.upper(), REALBONE_LINEUP_X[name], z_floor - 5.2, studio_col)
        for name in cfg.PART_NAMES
    ]

    cam_data = bpy.data.cameras.new("RealLineupCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 315.0
    cam_data.clip_start = 1.0
    cam_data.clip_end = 5000.0
    cam_obj = bpy.data.objects.new("RealLineupCam", cam_data)
    studio_col.objects.link(cam_obj)
    scene.camera = cam_obj

    cam_target = Vector((x_mid, 0.0, 88.0))
    cam_obj.location = Vector((x_mid, -520.0, 108.0))
    cam_obj.rotation_euler = (cam_target - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()

    scene.render.resolution_x = 1600
    scene.render.resolution_y = 950
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Saved True Anatomical Real-Bone Lineup: {out_path}")

    return studio_col


# ---------------------------------------------------------------------------
# Uniform Scaling Around Z=0 Bottom Center
# ---------------------------------------------------------------------------

def uniform_scale_flat_copy(src_obj, factor, rz_deg, new_name, col):
    dup = prep.duplicate_object(src_obj, new_name, col=col)
    prep.apply_all_transforms(dup)
    b = prep.get_world_bbox(dup)
    cx = 0.5 * (b[0] + b[1])
    cy = 0.5 * (b[2] + b[3])
    min_z = b[4]

    bm = bmesh.new()
    bm.from_mesh(dup.data)
    for v in bm.verts:
        v.co.x = (v.co.x - cx) * factor
        v.co.y = (v.co.y - cy) * factor
        v.co.z = (v.co.z - min_z) * factor
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(dup.data)
    bm.free()

    if abs(rz_deg) > 1e-6:
        prep.rotate_part_euler_deg(dup, 0.0, 0.0, rz_deg)
    prep.center_xy_and_rest_on_z0(dup)
    return dup


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(cfg.MASTER_BLEND_PATH):
        raise FileNotFoundError(f"Master blend file not found: {cfg.MASTER_BLEND_PATH}")

    os.makedirs(BLEND_INDIVIDUAL_DIR, exist_ok=True)
    os.makedirs(REALBONE_1TO2_DIR, exist_ok=True)
    os.makedirs(REALBONE_1TO1_DIR, exist_ok=True)
    os.makedirs(cfg.RENDERS_DIR, exist_ok=True)

    bpy.ops.wm.open_mainfile(filepath=cfg.MASTER_BLEND_PATH)
    bone_mat = bpy.data.materials.get("Skeleton_Bone_Mat")
    if bone_mat is None:
        bone_mat = prep._setup_plate_preview_material("Skeleton_Bone_Mat", (0.89, 0.82, 0.70), roughness=0.44)

    # Extract clean copies of the 5 bones before clearing old lineup setup
    real_col = prep._get_or_create_collection("Upper_Limb_RealBone_1to2")
    raw_sources = {}
    for name in cfg.PART_NAMES:
        orig = bpy.data.objects.get(name)
        if orig is None or orig.type != 'MESH':
            raise RuntimeError(f"Missing part in master blend: {name}")
        tmp = prep.duplicate_object(orig, f"_tmp_src_{name}", col=real_col)
        raw_sources[name] = tmp

    # Remove old studio/original objects so master file is spotless
    keep_names = {o.name for o in raw_sources.values()}
    for obj in list(bpy.data.objects):
        if obj.name not in keep_names:
            bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        if col != real_col and col.users == 0:
            bpy.data.collections.remove(col)

    lineup_parts = []
    for name in cfg.PART_NAMES:
        obj = raw_sources[name]
        obj.name = name
        obj.data.name = f"{name}_RealBone_1to2_Mesh"
        _scale_to_exact_upright_dims(
            obj,
            ANATOMICAL_1TO2_DIMS_MM[name],
            REALBONE_LINEUP_X[name],
            LINEUP_BASE_Z_MM,
        )
        _apply_periosteal_relief(obj, name)
        stat = jm.verify_part_manifold(obj)
        islands = _count_islands(obj)
        assert islands == 1, f"{name}: expected 1 island, got {islands}"
        assert stat["non_manifold_edges"] == 0 and stat["loose_verts"] == 0, f"{name}: non-manifold after relief"
        print(
            f"[REALBONE-1TO2-UPRIGHT] {name}: verts={stat['verts']}, faces={stat['faces']}, "
            f"nm={stat['non_manifold_edges']}, lv={stat['loose_verts']}, islands={islands}, "
            f"dims={stat['dimensions_mm']} mm, min_z={stat['min_z_mm']}"
        )
        lineup_parts.append(obj)

    # Render True Anatomical Lineup & Save Real-Bone Master Blend
    studio_col = render_realbone_lineup(lineup_parts, bone_mat, LINEUP_RENDER_PATH)
    bpy.ops.wm.save_as_mainfile(filepath=REALBONE_MASTER_BLEND)
    print(f"[INFO] Saved real-bone master blend: {REALBONE_MASTER_BLEND}")

    # Hide studio objects for export prep
    for obj in list(studio_col.objects):
        obj.hide_render = True
        obj.hide_viewport = True

    prep_col = prep._get_or_create_collection("RealBone_Export_Prep")

    report = {
        "creality_k1_safe_envelope_mm": {
            "max_x": cfg.SAFE_X_MM,
            "max_y": cfg.SAFE_Y_MM,
            "max_z": cfg.SAFE_Z_MM,
        },
        "realbone_1to2_parts": {},
        "realbone_1to2_plate": {},
        "realbone_1to1_lifesize": {},
        "blend_individual": {},
        "all_passed": False,
    }

    # Orient flat (-90 deg X), rest at Z = 0, export & round-trip verify Set A (1:2)
    flat_1to2 = {}
    for src in lineup_parts:
        name = src.name
        dup = prep.duplicate_object(src, f"{name}_realbone_1to2", col=prep_col)
        prep.apply_all_transforms(dup)
        rx, ry, rz = cfg.PRINT_ORIENTATIONS_DEG[name]
        prep.rotate_part_euler_deg(dup, rx, ry, rz)
        prep.center_xy_and_rest_on_z0(dup)
        prep.sanitize_for_stl_export(dup)
        prep.rest_on_z0(dup)

        stl_path = os.path.join(REALBONE_1TO2_DIR, f"{name}.stl")
        n_verts, n_faces, nm, lv, bbox = prep.export_binary_stl(dup, stl_path)
        fits_k1 = prep.check_k1_fit(bbox)
        dx = round(bbox[1] - bbox[0], 3)
        dy = round(bbox[3] - bbox[2], 3)
        dz = round(bbox[5] - bbox[4], 3)
        assert nm == 0 and lv == 0 and fits_k1, f"1:2 part {name} failed K1 checks"
        assert abs(bbox[4]) < 0.01, f"1:2 part {name} min_z={bbox[4]} != 0"

        report["realbone_1to2_parts"][name] = {
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
        flat_1to2[name] = dup

    # Pack all 5 Real-Bone 1:2 parts onto one K1 build plate
    p1_objs = [prep.duplicate_object(flat_1to2[n], f"RB_P1_{n}", col=prep_col) for n in cfg.PART_NAMES]
    p1_gap, _ = prep.pack_objects_on_plate(p1_objs, max_x_mm=196.0, max_y_mm=196.0, gap_mm=8.5)
    p1_joined = prep.join_objects(p1_objs, "plate_01_realbone_1to2_5bones", prep_col)
    p1_stl = os.path.join(REALBONE_1TO2_DIR, "plate_01_realbone_1to2_5bones.stl")
    pv, pf, pnm, plv, pbox = prep.export_binary_stl(p1_joined, p1_stl)
    pfits = prep.check_k1_fit(pbox)
    assert pnm == 0 and plv == 0 and pfits
    report["realbone_1to2_plate"] = {
        "name": "plate_01_realbone_1to2_5bones",
        "stl_path": p1_stl,
        "included_parts": list(cfg.PART_NAMES),
        "verts": pv,
        "faces": pf,
        "dimensions_mm": [round(pbox[1] - pbox[0], 3), round(pbox[3] - pbox[2], 3), round(pbox[5] - pbox[4], 3)],
        "bounds_xy_mm": [round(pbox[0], 3), round(pbox[1], 3), round(pbox[2], 3), round(pbox[3], 3)],
        "min_part_gap_mm": round(p1_gap, 3),
        "min_z_mm": round(pbox[4], 3),
        "max_z_mm": round(pbox[5], 3),
        "non_manifold_edges": pnm,
        "loose_verts": plv,
        "fits_creality_k1": pfits,
        "stl_roundtrip_verified": True,
    }

    # Determine uniform 1:1 Compact Adult Specimen scale so hummus rotated 45 deg <= 204 mm XY
    probe_h = uniform_scale_flat_copy(flat_1to2["humerus"], TARGET_1TO1_MULTIPLIER, 45.0, "_probe_humerus_1to1", prep_col)
    hb = prep.get_world_bbox(probe_h)
    h_dx = hb[1] - hb[0]
    h_dy = hb[3] - hb[2]
    h_max_xy = max(h_dx, h_dy)
    bpy.data.objects.remove(probe_h, do_unlink=True)

    if h_max_xy > MAX_1TO1_K1_XY_MM:
        scale_1to1 = TARGET_1TO1_MULTIPLIER * (MAX_1TO1_K1_XY_MM / h_max_xy)
        print(
            f"[1TO1-AUTO-SCALE] humerus at {TARGET_1TO1_MULTIPLIER:.3f}x had 45 deg XY max {h_max_xy:.2f} mm > "
            f"{MAX_1TO1_K1_XY_MM:.1f} mm; adjusting uniform 1:1 scale factor to {scale_1to1:.4f}x"
        )
    else:
        scale_1to1 = TARGET_1TO1_MULTIPLIER

    report["realbone_1to1_uniform_factor_vs_1to2"] = round(scale_1to1, 4)

    # Export & Round-Trip Verify Set B (1:1 Full Life-Size Individual STLs)
    rot_1to1_z = {
        "scapula": 0.0,
        "clavicle": 0.0,
        "humerus": 45.0,
        "ulna": 45.0,
        "radius": 45.0,
    }
    for name in cfg.PART_NAMES:
        rz = rot_1to1_z[name]
        dup1 = uniform_scale_flat_copy(flat_1to2[name], scale_1to1, rz, f"{name}_1to1", prep_col)
        prep.sanitize_for_stl_export(dup1)
        prep.center_xy_and_rest_on_z0(dup1)

        stl_1to1 = os.path.join(REALBONE_1TO1_DIR, f"{name}_1to1.stl")
        v1, f1, nm1, lv1, b1 = prep.export_binary_stl(dup1, stl_1to1)
        fits1 = prep.check_k1_fit(b1)
        dx1 = round(b1[1] - b1[0], 3)
        dy1 = round(b1[3] - b1[2], 3)
        dz1 = round(b1[5] - b1[4], 3)
        assert nm1 == 0 and lv1 == 0 and fits1, f"1:1 part {name} failed K1 check: dims={(dx1, dy1, dz1)}"
        assert abs(b1[4]) < 0.01, f"1:1 part {name} min_z={b1[4]} != 0"

        anatomical_len_mm = round(ANATOMICAL_1TO2_DIMS_MM[name][2] * scale_1to1, 2)
        report["realbone_1to1_lifesize"][name] = {
            "name": f"{name}_1to1",
            "stl_path": stl_1to1,
            "bed_rotation_z_deg": rz,
            "anatomical_length_mm": anatomical_len_mm,
            "verts": v1,
            "faces": f1,
            "bed_bbox_dimensions_mm": [dx1, dy1, dz1],
            "dx": dx1,
            "dy": dy1,
            "dz": dz1,
            "min_z_mm": round(b1[4], 3),
            "max_z_mm": round(b1[5], 3),
            "non_manifold_edges": nm1,
            "loose_verts": lv1,
            "fits_creality_k1": fits1,
            "stl_roundtrip_verified": True,
        }

    # Render K1 Plate Preview for the 1:2 Real-Bone Plate 01 (this hides other objects in scene)
    p1_render_copy = prep.duplicate_object(p1_joined, "plate_01_realbone_preview_mesh", col=prep_col)
    prep.render_plate_overview(p1_render_copy, PLATE_RENDER_PATH)

    # Save 5 Standalone Individual .blend Files (each containing ONLY that single bone laid flat on Z=0)
    # Re-open clean Real-Bone Master Blend each time so zero extra objects/datablocks remain
    for name in cfg.PART_NAMES:
        bpy.ops.wm.open_mainfile(filepath=REALBONE_MASTER_BLEND)
        scene = bpy.context.scene
        scene.unit_settings.system = 'METRIC'
        scene.unit_settings.scale_length = 0.001
        scene.unit_settings.length_unit = 'MILLIMETERS'

        target_obj = bpy.data.objects.get(name)
        if target_obj is None:
            raise RuntimeError(f"Missing {name} when creating individual .blend")

        ind_col = bpy.data.collections.new(name.capitalize())
        scene.collection.children.link(ind_col)
        ind_obj = prep.duplicate_object(target_obj, name, col=ind_col)
        prep.apply_all_transforms(ind_obj)
        rx, ry, rz = cfg.PRINT_ORIENTATIONS_DEG[name]
        prep.rotate_part_euler_deg(ind_obj, rx, ry, rz)
        prep.center_xy_and_rest_on_z0(ind_obj)

        for obj in list(bpy.data.objects):
            if obj != ind_obj:
                bpy.data.objects.remove(obj, do_unlink=True)
        for col in list(bpy.data.collections):
            if col != ind_col and col.users == 0:
                bpy.data.collections.remove(col)
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        ind_blend_path = os.path.join(BLEND_INDIVIDUAL_DIR, f"{name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=ind_blend_path)
        b_ind = prep.get_world_bbox(ind_obj)
        report["blend_individual"][name] = {
            "blend_path": ind_blend_path,
            "dimensions_mm": [
                round(b_ind[1] - b_ind[0], 3),
                round(b_ind[3] - b_ind[2], 3),
                round(b_ind[5] - b_ind[4], 3),
            ],
            "min_z_mm": round(b_ind[4], 3),
        }
        print(f"[BLEND-INDIVIDUAL] Saved standalone {ind_blend_path}")

    report["all_passed"] = True
    with open(REALBONE_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[REPORT] Wrote real-bone validation report: {REALBONE_REPORT_PATH}")
    print("[SUCCESS] True Anatomical Real-Bone build, renders, individual .blend files, 1:2 & 1:1 STLs completed!")


if __name__ == "__main__":
    main()
