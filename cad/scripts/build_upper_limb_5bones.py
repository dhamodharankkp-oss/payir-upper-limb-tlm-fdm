# SPDX-License-Identifier: MIT
"""
Individual 3D-Printed Upper-Limb & Shoulder-Girdle Bones Builder (Blender 5.2).

Builds 5 standalone, watertight, single-shell osteological bone parts matching the
reference lineup silhouette and warm-ivory cortical finish:
  1. scapula  (X ~ -112 mm)
  2. clavicle (X ~  -50 mm)
  3. humerus  (X ~    0 mm)
  4. ulna     (X ~  +48 mm)
  5. radius   (X ~  +94 mm)

Outputs:
  - e:\\AG\\Blender\\upper_limb_5bones_master.blend
  - e:\\AG\\Blender\\renders\\upper_limb_5bones_lineup_front.png
  - e:\\AG\\Blender\\renders\\upper_limb_5bones_lineup_back34.png
  - e:\\AG\\Blender\\renders\\upper_limb_5bones_lineup_labeled.png
"""

import os
import sys
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


# ---------------------------------------------------------------------------
# Scene & Mesh Helpers
# ---------------------------------------------------------------------------

def reset_scene():
    """Clear scene and configure Blender metric millimeter units."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = 'MILLIMETERS'


def create_collection(name, parent=None):
    col = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(col)
    else:
        parent.children.link(col)
    return col


def _count_mesh_islands(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    visited = set()
    islands = 0
    for f in bm.faces:
        if f in visited:
            continue
        islands += 1
        stack = [f]
        visited.add(f)
        while stack:
            cur = stack.pop()
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf not in visited:
                        visited.add(nf)
                        stack.append(nf)
    bm.free()
    return islands


def _make_thick_lofted_plate(name, grid_pts, thickness_fn, col=None):
    """
    Build a watertight manifold curved slab from a (Nu x Nv) grid of 3D centerline
    points, offset symmetrically along local surface normals by +/- 0.5 * thickness.
    """
    nu = len(grid_pts)
    nv = len(grid_pts[0])
    pts = [[Vector(grid_pts[i][j]) for j in range(nv)] for i in range(nu)]

    normals = [[Vector((0.0, 1.0, 0.0)) for _ in range(nv)] for _ in range(nu)]
    for i in range(nu):
        i0 = max(0, i - 1)
        i1 = min(nu - 1, i + 1)
        for j in range(nv):
            j0 = max(0, j - 1)
            j1 = min(nv - 1, j + 1)
            du = pts[i1][j] - pts[i0][j]
            dv = pts[i][j1] - pts[i][j0]
            nrm = du.cross(dv)
            if nrm.length < 1e-6:
                nrm = Vector((0.0, 1.0, 0.0))
            else:
                nrm.normalize()
            normals[i][j] = nrm

    bm = bmesh.new()
    front = [[None] * nv for _ in range(nu)]
    back = [[None] * nv for _ in range(nu)]
    for i in range(nu):
        u_norm = i / max(nu - 1, 1)
        for j in range(nv):
            v_norm = j / max(nv - 1, 1)
            half_t = 0.5 * float(thickness_fn(u_norm, v_norm))
            p = pts[i][j]
            n = normals[i][j]
            front[i][j] = bm.verts.new(p + n * half_t)
            back[i][j] = bm.verts.new(p - n * half_t)

    for i in range(nu - 1):
        for j in range(nv - 1):
            bm.faces.new((front[i][j], front[i + 1][j], front[i + 1][j + 1], front[i][j + 1]))
            bm.faces.new((back[i][j], back[i][j + 1], back[i + 1][j + 1], back[i + 1][j]))

    for i in range(nu - 1):
        bm.faces.new((front[i][0], back[i][0], back[i + 1][0], front[i + 1][0]))
        bm.faces.new((front[i + 1][nv - 1], back[i + 1][nv - 1], back[i][nv - 1], front[i][nv - 1]))
    for j in range(nv - 1):
        bm.faces.new((front[0][j + 1], back[0][j + 1], back[0][j], front[0][j]))
        bm.faces.new((front[nu - 1][j], back[nu - 1][j], back[nu - 1][j + 1], front[nu - 1][j + 1]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    if col is not None:
        col.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def _finalize_organic_bone(
    part_name,
    pos_objs,
    cutters,
    voxel_size_mm,
    col,
    post_smooth_factor=0.60,
    post_smooth_iters=10,
):
    """
    Build watertight single-island bone part, then apply organic CorrectiveSmooth
    after negative boolean cuts so fossae, grooves, and notches blend naturally.
    """
    obj = jm.finalize_printable_part(
        part_name,
        positive_objs=pos_objs,
        negative_cutters=cutters,
        voxel_size_mm=voxel_size_mm,
        target_col=col,
    )

    if post_smooth_iters > 0:
        temp_link = jm._ensure_in_view_layer(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        smooth = obj.modifiers.new(name="OrganicBoneSmooth", type='CORRECTIVE_SMOOTH')
        smooth.factor = float(post_smooth_factor)
        smooth.iterations = int(post_smooth_iters)
        smooth.smooth_type = 'LENGTH_WEIGHTED'
        smooth.use_only_smooth = True
        bpy.ops.object.modifier_apply(modifier=smooth.name)

        if temp_link:
            bpy.context.scene.collection.objects.unlink(obj)

        nm, lv = jm._sanitize_bmesh_manifold(obj, keep_single_island=True, merge_dist=2e-3)
        if nm != 0 or lv != 0:
            jm._apply_voxel_remesh(obj, voxel_size_mm=max(0.20, voxel_size_mm * 0.9), smooth_factor=0.35, smooth_iters=4)
            jm._sanitize_bmesh_manifold(obj, keep_single_island=True, merge_dist=2e-3)

    for poly in obj.data.polygons:
        poly.use_smooth = True
    jm.verify_part_manifold(obj)
    return obj


# ---------------------------------------------------------------------------
# 1. Scapula (X ~ -112 mm, Z ~ 25..103 mm)
# ---------------------------------------------------------------------------

def build_scapula(col):
    """
    Build standalone anatomical Scapula matching the dorsal-oblique reference:
      - Smooth curved triangular blade with shallow infraspinous & supraspinous fossae
      - Seamless medial border, rounded single-tip inferior angle & muscular lateral border
      - Diagonal scapular spine rising organically from medial blade into broad acromion
      - Hooked coracoid process peeking above superior neck
      - Lateral pear-shaped glenoid cavity with smooth shallow articular dish
    """
    pos = []
    cutters = []

    # 1a. Curved Triangular Scapular Blade (5x5 organic plate)
    blade_grid = [
        # Row 0 (superior crest)
        [
            (-127.8, 1.0, 93.0),
            (-122.0, 1.1, 93.4),
            (-115.2, 1.2, 91.2),
            (-107.8, 1.3, 88.2),
            (-100.2, 1.1, 86.4),
        ],
        # Row 1 (spine base)
        [
            (-134.5, 0.8, 80.5),
            (-125.0, 1.5, 80.5),
            (-115.2, 1.8, 80.2),
            (-105.0, 1.6, 79.8),
            (-96.2,  0.8, 79.2),
        ],
        # Row 2 (mid-upper infraspinous fossa)
        [
            (-134.0, 0.7, 62.5),
            (-125.5, 1.8, 62.5),
            (-116.5, 2.2, 62.5),
            (-108.2, 1.8, 62.5),
            (-100.8, 0.7, 62.0),
        ],
        # Row 3 (mid-lower blade)
        [
            (-128.8, 0.7, 45.0),
            (-123.5, 1.6, 45.0),
            (-118.2, 1.8, 45.0),
            (-113.2, 1.4, 45.0),
            (-109.2, 0.5, 44.5),
        ],
        # Row 4 (rounded inferior angle apex)
        [
            (-121.6, 0.6, 28.2),
            (-120.7, 0.8, 27.6),
            (-119.7, 0.9, 27.2),
            (-118.6, 0.8, 27.5),
            (-117.6, 0.5, 28.5),
        ],
    ]
    pos.append(_make_thick_lofted_plate(
        "Scapula_Blade",
        blade_grid,
        thickness_fn=lambda u, v: 3.4 + 0.7 * math.sin(math.pi * v) + 0.6 * (1.0 - u) * v,
        col=col,
    ))

    # 1b. Softly blended Medial (Vertebral) Border (flush, no picture-frame step)
    pos.append(jm.create_swept_bone_tube(
        "Scapula_MedialBorder",
        [
            (-127.6, 0.8, 93.0),
            (-133.2, 0.6, 86.2),
            (-135.0, 0.5, 78.0),
            (-134.2, 0.5, 62.0),
            (-129.0, 0.5, 45.0),
            (-123.0, 0.5, 32.0),
            (-119.8, 0.5, 27.4),
        ],
        radii_x=[2.0, 2.1, 2.3, 2.2, 2.1, 2.2, 2.4],
        radii_y=[1.8, 1.9, 2.1, 2.0, 1.9, 2.0, 2.1],
        col=col,
        segments=16,
    ))

    # 1c. Unified Rounded Inferior Angle (eliminates any notch at bottom tip)
    pos.append(jm.create_ellipsoid(
        "Scapula_InferiorAngle",
        center=(-119.6, 0.4, 27.4),
        rx=3.8,
        ry=2.4,
        rz=3.6,
        rot_euler=(0.0, math.radians(-12.0), 0.0),
        col=col,
    ))

    # 1d. Muscular Lateral (Axillary) Border
    pos.append(jm.create_swept_bone_tube(
        "Scapula_LateralBorder",
        [
            (-119.5, 0.4, 27.6),
            (-115.0, -0.1, 34.5),
            (-109.0, -0.4, 45.5),
            (-103.2, -0.4, 57.5),
            (-98.4,  -0.2, 68.5),
            (-94.8,   0.1, 77.5),
        ],
        radii_x=[2.6, 2.8, 3.0, 3.3, 3.5, 3.9],
        radii_y=[2.4, 2.6, 2.8, 3.0, 3.2, 3.6],
        col=col,
        segments=16,
    ))

    # 1e. Smooth Superior Border & Supraspinous Crest
    pos.append(jm.create_swept_bone_tube(
        "Scapula_SuperiorBorder",
        [
            (-127.8, 0.9, 93.0),
            (-122.0, 1.0, 94.0),
            (-115.5, 1.0, 91.8),
            (-108.5, 1.0, 88.2),
            (-101.2, 1.0, 86.5),
            (-95.5,  0.8, 85.0),
        ],
        radii_x=[2.0, 2.1, 2.0, 1.9, 2.1, 2.8],
        radii_y=[1.9, 2.0, 1.9, 1.8, 2.1, 2.8],
        col=col,
        segments=14,
    ))

    # 1f. Organic Triangular Scapular Spine & Broad Acromion
    #     Starts flush from the medial spine triangle and rises seamlessly toward -Y
    pos.append(jm.create_swept_bone_tube(
        "Scapula_Spine",
        [
            (-134.8, 0.2, 79.0),    # Medial root flush with vertebral border
            (-127.0, -1.8, 80.6),
            (-117.2, -3.8, 83.4),
            (-107.0, -4.6, 87.4),
            (-97.8,  -4.4, 92.6),
            (-90.6,  -3.4, 98.2),
            (-85.8,  -2.0, 102.2),  # Acromial lateral tip
        ],
        radii_x=[1.8, 2.7, 3.3, 3.8, 4.3, 5.0, 3.8],
        radii_y=[1.6, 2.5, 3.1, 3.4, 3.4, 2.9, 2.4],
        col=col,
        segments=18,
    ))
    # Wedge connecting spine crest smoothly down into blade
    pos.append(jm.create_swept_bone_tube(
        "Scapula_SpineRootWeb",
        [
            (-130.0, -0.4, 79.5),
            (-120.0, -1.5, 81.2),
            (-110.0, -2.0, 83.5),
            (-100.0, -1.6, 85.0),
            (-94.2,  -0.4, 82.0),
        ],
        radii_x=[2.6, 3.2, 3.5, 3.6, 3.8],
        radii_y=[2.2, 2.6, 2.8, 3.0, 3.2],
        col=col,
        segments=14,
    ))
    pos.append(jm.create_ellipsoid(
        "Scapula_AcromionPaddle",
        center=(-89.0, -2.8, 99.6),
        rx=6.2,
        ry=2.5,
        rz=4.2,
        rot_euler=(math.radians(-18.0), math.radians(-38.0), math.radians(12.0)),
        col=col,
    ))

    # 1g. Glenoid Cavity & Neck
    pos.append(jm.create_ellipsoid(
        "Scapula_GlenoidHead",
        center=(-93.2, 0.2, 81.0),
        rx=4.8,
        ry=4.6,
        rz=7.2,
        rot_euler=(0.0, math.radians(-12.0), 0.0),
        col=col,
    ))
    cutters.append(jm.create_ellipsoid(
        "Scapula_GlenoidDishCutter",
        center=(-88.4, -0.4, 81.2),
        rx=2.7,
        ry=3.4,
        rz=5.0,
        rot_euler=(0.0, math.radians(-12.0), 0.0),
        col=col,
    ))

    # 1h. Hooked Coracoid Process (stout base blending smoothly into upper glenoid neck)
    pos.append(jm.create_swept_bone_tube(
        "Scapula_Coracoid",
        [
            (-96.2, 0.8, 84.5),
            (-98.2, 0.6, 90.8),
            (-97.5, -0.4, 96.4),
            (-95.4, -1.6, 98.0),
        ],
        radii_x=[3.8, 3.2, 2.7, 2.3],
        radii_y=[3.5, 3.0, 2.6, 2.2],
        col=col,
        segments=14,
    ))

    # 1i. Gentle Infraspinous Fossa Depression (shallow soft scoop, smoothed post-boolean)
    cutters.append(jm.create_ellipsoid(
        "Scapula_InfraspinousScoop",
        center=(-119.5, -4.4, 60.5),
        rx=9.2,
        ry=2.6,
        rz=13.5,
        col=col,
    ))

    return _finalize_organic_bone(
        "scapula",
        pos_objs=pos,
        cutters=cutters,
        voxel_size_mm=0.28,
        col=col,
        post_smooth_factor=0.60,
        post_smooth_iters=10,
    )


# ---------------------------------------------------------------------------
# 2. Clavicle (X ~ -50 mm, Z ~ 15..101 mm)
# ---------------------------------------------------------------------------

def build_clavicle(col):
    """
    Build standalone anatomical Clavicle oriented vertically in the S-curve pose:
      - Broad flared sternal end at bottom (Z ~ 15..23 mm)
      - Smooth double S-curved shaft
      - Widened flattened acromial head curving up-right at top (Z ~ 95..101 mm)
    """
    pos = []
    cutters = []

    clav_pts = [
        (-49.6, 0.0, 17.5),   # Sternal base
        (-47.6, -0.2, 29.0),  # Lower convexity (right)
        (-49.5, 0.0, 42.0),   # Lower inflection
        (-53.2, 0.0, 56.0),   # Mid-upper transition
        (-55.6, -0.1, 70.0),  # Upper convexity (left)
        (-54.6, 0.0, 83.5),   # Upper-lateral taper
        (-50.2, -0.2, 94.5),  # Acromial curve neck
        (-45.8, -0.3, 98.4),  # Acromial tip
    ]
    pos.append(jm.create_swept_bone_tube(
        "Clavicle_Shaft",
        clav_pts,
        radii_x=[5.0, 3.6, 3.4, 3.3, 3.4, 3.6, 4.1, 4.6],
        radii_y=[4.2, 3.3, 3.1, 3.1, 3.2, 3.2, 3.0, 2.7],
        col=col,
        segments=20,
        samples_per_seg=6,
    ))

    # Broad flared sternal pedestal (smooth organic blend, no sharp hole)
    pos.append(jm.create_ellipsoid(
        "Clavicle_SternalLobeLeft",
        center=(-52.2, -0.3, 18.2),
        rx=4.0,
        ry=3.7,
        rz=3.5,
        rot_euler=(0.0, math.radians(15.0), 0.0),
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Clavicle_SternalLobeRight",
        center=(-46.8, -0.2, 17.0),
        rx=3.8,
        ry=3.5,
        rz=3.2,
        rot_euler=(0.0, math.radians(-12.0), 0.0),
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Clavicle_SternalCore",
        center=(-49.4, -0.2, 18.0),
        rx=5.0,
        ry=4.0,
        rz=3.6,
        col=col,
    ))
    cutters.append(jm.create_ellipsoid(
        "Clavicle_SternalSaddle",
        center=(-49.8, -0.2, 13.4),
        rx=2.4,
        ry=2.6,
        rz=1.5,
        col=col,
    ))

    # Widened acromial head curving right
    pos.append(jm.create_ellipsoid(
        "Clavicle_AcromialHead",
        center=(-45.8, -0.2, 98.4),
        rx=5.0,
        ry=2.9,
        rz=3.6,
        rot_euler=(0.0, math.radians(-26.0), 0.0),
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Clavicle_ConoidTubercle",
        center=(-52.6, 1.2, 90.2),
        rx=2.5,
        ry=2.0,
        rz=2.8,
        col=col,
    ))

    return _finalize_organic_bone(
        "clavicle",
        pos_objs=pos,
        cutters=cutters,
        voxel_size_mm=0.24,
        col=col,
        post_smooth_factor=0.60,
        post_smooth_iters=10,
    )


# ---------------------------------------------------------------------------
# 3. Humerus (X ~ 0 mm, Z ~ 6..111 mm)
# ---------------------------------------------------------------------------

def build_humerus(col):
    """
    Build standalone anatomical Humerus matching the anterior reference silhouette:
      - Smooth proximal head, greater tubercle, prominent anterior lesser tubercle &
        gentle bicipital valley (no harsh cut slot)
      - Graceful concave trumpet-bell distal flare into epicondyles
      - Continuous sculpted distal capitulum/trochlea articular spool
      - Softly blended coronoid, radial & olecranon fossae
    """
    pos = []
    cutters = []

    # 3a. Graceful Concave-Flared Humeral Shaft
    pos.append(jm.create_swept_bone_tube(
        "Humerus_Shaft",
        [
            (0.0,  0.0, 96.5),   # Surgical neck
            (-0.4, 0.0, 78.0),   # Upper diaphysis
            (-0.6, -0.2, 60.0),  # Mid-diaphysis / deltoid region
            (-0.2, 0.0, 42.0),   # Narrow waist
            (-0.1, 0.1, 29.0),   # Beginning of concave supracondylar flare
            (0.1,  0.2, 19.5),   # Mid distal flare
            (0.2,  0.2, 13.2),   # Distal condylar bridge
        ],
        radii_x=[6.2, 4.5, 4.5, 4.0, 4.4, 6.2, 8.8],
        radii_y=[5.6, 4.3, 4.3, 3.8, 3.6, 3.5, 3.3],
        col=col,
        segments=24,
        samples_per_seg=6,
    ))

    # 3b. Proximal Humeral Head, Greater & Lesser Tubercles (soft organic bicipital valley)
    pos.append(jm.create_ellipsoid(
        "Humerus_Head",
        center=(2.4, 0.6, 102.6),
        rx=7.9,
        ry=7.4,
        rz=8.6,
        rot_euler=(0.0, math.radians(20.0), 0.0),
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Humerus_GreaterTubercle",
        center=(-4.8, -0.7, 101.4),
        rx=4.5,
        ry=4.6,
        rz=5.8,
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Humerus_LesserTubercle",
        center=(-0.6, -4.6, 99.8),
        rx=3.1,
        ry=2.9,
        rz=3.7,
        col=col,
    ))
    # Very shallow, soft bicipital groove scoop between greater & lesser tubercles
    cutters.append(jm.create_ellipsoid(
        "Humerus_BicipitalScoopCutter",
        center=(-3.2, -5.8, 98.2),
        rx=1.5,
        ry=1.8,
        rz=4.8,
        rot_euler=(0.0, math.radians(-8.0), 0.0),
        col=col,
    ))

    # 3c. Subtle Deltoid Tuberosity & Anterior Ridge
    pos.append(jm.create_swept_bone_tube(
        "Humerus_DeltoidCrest",
        [
            (-1.6, -2.2, 78.0),
            (-1.8, -2.5, 62.0),
            (-0.5, -2.1, 44.0),
        ],
        radii_x=[2.0, 2.3, 1.7],
        radii_y=[2.0, 2.1, 1.6],
        col=col,
        segments=14,
    ))

    # 3d. Curved Concave Supracondylar Ridges, Epicondyles & Smooth Distal Condylar Block
    pos.append(jm.create_swept_bone_tube(
        "Humerus_LateralSupracondylar",
        [
            (-2.8, 0.1, 31.0),
            (-4.8, 0.2, 22.0),
            (-8.8, 0.2, 13.2),
        ],
        radii_x=[2.3, 2.5, 3.2],
        radii_y=[2.3, 2.4, 2.8],
        col=col,
        segments=16,
    ))
    pos.append(jm.create_ellipsoid(
        "Humerus_LateralEpicondyle",
        center=(-9.4, 0.2, 13.0),
        rx=3.2,
        ry=3.0,
        rz=3.4,
        col=col,
    ))
    pos.append(jm.create_swept_bone_tube(
        "Humerus_MedialSupracondylar",
        [
            (2.8, 0.2, 31.0),
            (5.0, 0.3, 22.0),
            (9.4, 0.4, 13.6),
        ],
        radii_x=[2.3, 2.6, 3.4],
        radii_y=[2.3, 2.4, 2.9],
        col=col,
        segments=16,
    ))
    pos.append(jm.create_ellipsoid(
        "Humerus_MedialEpicondyle",
        center=(10.2, 0.4, 13.6),
        rx=3.5,
        ry=3.1,
        rz=3.8,
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Humerus_DistalCondyleBridge",
        center=(0.2, 0.0, 13.2),
        rx=9.0,
        ry=3.3,
        rz=3.6,
        col=col,
    ))

    # 3e. Continuous Sculpted Distal Capitulum + Trochlea Articular Spool
    pos.append(jm.create_swept_bone_tube(
        "Humerus_TrochleaCapitulumSpool",
        [
            (-7.4, -0.4, 11.4),
            (-4.4, -0.9, 9.5),
            (-1.2, -0.7, 9.7),
            (1.6,  -0.7, 9.4),
            (4.3,  -0.6, 8.7),
            (7.4,  -0.1, 11.2),
        ],
        radii_x=[2.8, 3.4, 2.9, 3.1, 3.5, 2.8],
        radii_y=[2.8, 3.7, 3.1, 3.3, 3.7, 2.8],
        col=col,
        segments=20,
        samples_per_seg=5,
    ))

    # 3f. Softly Recessed Coronoid, Radial & Olecranon Fossae
    cutters.append(jm.create_ellipsoid(
        "Humerus_CoronoidFossaCutter",
        center=(1.2, -4.6, 15.8),
        rx=3.0,
        ry=2.0,
        rz=2.5,
        col=col,
    ))
    cutters.append(jm.create_ellipsoid(
        "Humerus_RadialFossaCutter",
        center=(-3.5, -4.4, 16.0),
        rx=2.3,
        ry=1.7,
        rz=2.0,
        col=col,
    ))
    cutters.append(jm.create_ellipsoid(
        "Humerus_OlecranonFossaCutter",
        center=(0.4, 4.6, 15.8),
        rx=4.2,
        ry=2.4,
        rz=3.2,
        col=col,
    ))

    return _finalize_organic_bone(
        "humerus",
        pos_objs=pos,
        cutters=cutters,
        voxel_size_mm=0.25,
        col=col,
        post_smooth_factor=0.65,
        post_smooth_iters=12,
    )


# ---------------------------------------------------------------------------
# 4. Ulna (X ~ +48 mm, Z ~ 6..107 mm)
# ---------------------------------------------------------------------------

def build_ulna(col):
    """
    Build standalone anatomical Ulna matching the reference silhouette:
      - Cohesive proximal olecranon & coronoid metaphysis blending into shaft
      - Softly sculpted C-shaped trochlear notch facing right (+X)
      - Tapered triangular shaft with subtle anterior longitudinal crest
      - Clean distal ulnar head & pointed ulnar styloid process
    """
    pos = []
    cutters = []

    # 4a. Proximal Olecranon Block & Shaft
    pos.append(jm.create_swept_bone_tube(
        "Ulna_Shaft",
        [
            (47.0, 0.2, 105.0),  # Olecranon top
            (47.2, 0.2, 96.5),   # Olecranon body behind trochlear notch
            (48.2, 0.0, 86.5),   # Coronoid/ulnar tuberosity base
            (48.8, 0.0, 68.0),   # Upper-mid shaft
            (48.6, 0.0, 48.0),   # Mid shaft
            (48.0, 0.0, 28.0),   # Distal tapering shaft
            (48.0, 0.0, 12.2),   # Distal ulnar neck/head
        ],
        radii_x=[4.6, 5.2, 4.8, 3.8, 3.3, 2.9, 3.2],
        radii_y=[4.2, 4.7, 4.6, 3.8, 3.4, 2.9, 3.1],
        col=col,
        segments=20,
        samples_per_seg=5,
    ))
    pos.append(jm.create_ellipsoid(
        "Ulna_OlecranonCap",
        center=(47.2, 0.2, 105.0),
        rx=4.8,
        ry=4.1,
        rz=2.2,
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Ulna_OlecranonBeak",
        center=(50.4, -0.3, 103.0),
        rx=2.8,
        ry=3.2,
        rz=2.5,
        col=col,
    ))
    # Smooth tapered coronoid bridge blending into upper shaft
    pos.append(jm.create_swept_bone_tube(
        "Ulna_CoronoidBridge",
        [
            (52.4, -0.6, 90.4),
            (50.8, -0.5, 86.2),
            (48.6, -0.3, 79.0),
        ],
        radii_x=[3.3, 3.8, 3.4],
        radii_y=[3.2, 3.6, 3.4],
        col=col,
        segments=16,
    ))
    pos.append(jm.create_swept_bone_tube(
        "Ulna_AnteriorCrest",
        [
            (48.2, -2.3, 84.0),
            (48.8, -2.2, 64.0),
            (48.3, -1.9, 42.0),
            (47.9, -1.5, 22.0),
        ],
        radii_x=[2.0, 1.7, 1.5, 1.3],
        radii_y=[2.0, 1.8, 1.6, 1.4],
        col=col,
        segments=14,
    ))

    # 4b. Softly Sculpted Trochlear Notch Cutter
    cutters.append(jm.create_ellipsoid(
        "Ulna_TrochlearNotchCutter",
        center=(53.4, -0.6, 96.8),
        rx=4.4,
        ry=5.4,
        rz=4.2,
        col=col,
    ))

    # 4c. Clean Distal Ulnar Head & Pointed Styloid Process
    pos.append(jm.create_ellipsoid(
        "Ulna_DistalHead",
        center=(48.2, 0.0, 11.4),
        rx=3.6,
        ry=3.3,
        rz=3.0,
        col=col,
    ))
    pos.append(jm.create_swept_bone_tube(
        "Ulna_Styloid",
        [
            (47.2, 0.1, 11.6),
            (47.0, 0.1, 8.4),
            (47.1, 0.1, 6.5),
        ],
        radii_x=[2.2, 1.7, 1.2],
        radii_y=[2.2, 1.7, 1.2],
        col=col,
        segments=14,
    ))
    cutters.append(jm.create_ellipsoid(
        "Ulna_DistalNotchCutter",
        center=(49.6, -1.2, 7.6),
        rx=1.8,
        ry=2.2,
        rz=1.5,
        col=col,
    ))

    return _finalize_organic_bone(
        "ulna",
        pos_objs=pos,
        cutters=cutters,
        voxel_size_mm=0.24,
        col=col,
        post_smooth_factor=0.62,
        post_smooth_iters=11,
    )


# ---------------------------------------------------------------------------
# 5. Radius (X ~ +94 mm, Z ~ 6..105 mm)
# ---------------------------------------------------------------------------

def build_radius(col):
    """
    Build standalone anatomical Radius matching the exact reference silhouette:
      - Rounded proximal radial head with shallow superior fovea dish
      - Constricted neck & distinct annular collar ring right beneath the head
      - Smoothly blended radial tuberosity ridge below the neck
      - Tapered curved shaft flaring gracefully into broad distal epiphysis
      - Downward radial styloid tip on left & arched carpal/ulnar notch on right
    """
    pos = []
    cutters = []

    # 5a. Proximal Radial Head & Annular Collar Ring
    pos.append(jm.create_ellipsoid(
        "Radius_Head",
        center=(94.2, 0.0, 99.2),
        rx=6.0,
        ry=5.6,
        rz=5.4,
        col=col,
    ))
    cutters.append(jm.create_ellipsoid(
        "Radius_HeadFoveaCutter",
        center=(94.2, 0.0, 105.0),
        rx=3.8,
        ry=3.8,
        rz=1.3,
        col=col,
    ))
    pos.append(jm.create_ellipsoid(
        "Radius_AnnularCollar",
        center=(94.2, 0.0, 91.6),
        rx=5.3,
        ry=4.8,
        rz=1.8,
        col=col,
    ))

    # 5b. Radial Shaft & Smoothly Tapered Radial Tuberosity
    pos.append(jm.create_swept_bone_tube(
        "Radius_Shaft",
        [
            (94.2, 0.0, 96.5),   # Neck core
            (94.2, 0.0, 90.0),   # Below collar
            (94.2, 0.0, 81.5),   # Tuberosity zone
            (93.8, 0.0, 62.0),   # Upper-mid bowed waist
            (93.5, 0.0, 42.0),   # Mid-lower shaft
            (93.8, 0.0, 22.0),   # Distal widening metaphysis
            (94.2, 0.0, 12.2),   # Distal epiphysis
        ],
        radii_x=[3.7, 3.9, 4.1, 3.4, 3.5, 4.6, 6.2],
        radii_y=[3.7, 3.8, 3.9, 3.3, 3.4, 3.7, 4.3],
        col=col,
        segments=20,
        samples_per_seg=5,
    ))
    pos.append(jm.create_swept_bone_tube(
        "Radius_TuberosityRidge",
        [
            (94.6, -0.3, 86.8),
            (96.6, -0.7, 81.8),
            (94.6, -0.3, 76.0),
        ],
        radii_x=[2.6, 3.0, 2.5],
        radii_y=[2.6, 2.9, 2.4],
        col=col,
        segments=16,
    ))
    pos.append(jm.create_swept_bone_tube(
        "Radius_AnteriorRidge",
        [
            (93.6, -2.0, 78.0),
            (93.1, -1.9, 50.0),
            (93.2, -2.2, 22.0),
        ],
        radii_x=[1.7, 1.5, 1.8],
        radii_y=[1.8, 1.6, 1.9],
        col=col,
        segments=14,
    ))

    # 5c. Distal Radial Epiphysis, Radial Styloid Process & Dorsal Lister's Tubercle
    pos.append(jm.create_ellipsoid(
        "Radius_DistalEpiphysis",
        center=(94.2, 0.0, 12.6),
        rx=6.5,
        ry=4.4,
        rz=4.2,
        col=col,
    ))
    pos.append(jm.create_swept_bone_tube(
        "Radius_StyloidProcess",
        [
            (91.0, -0.2, 14.0),
            (90.5, -0.2, 9.4),
            (90.9, -0.2, 6.8),
        ],
        radii_x=[3.1, 2.3, 1.5],
        radii_y=[3.0, 2.3, 1.5],
        col=col,
        segments=14,
    ))
    pos.append(jm.create_ellipsoid(
        "Radius_ListersTubercle",
        center=(94.0, 3.8, 12.6),
        rx=1.8,
        ry=1.6,
        rz=2.8,
        col=col,
    ))
    cutters.append(jm.create_ellipsoid(
        "Radius_DistalCarpalArchCutter",
        center=(96.2, -0.2, 6.8),
        rx=3.8,
        ry=3.8,
        rz=2.6,
        col=col,
    ))

    return _finalize_organic_bone(
        "radius",
        pos_objs=pos,
        cutters=cutters,
        voxel_size_mm=0.24,
        col=col,
        post_smooth_factor=0.62,
        post_smooth_iters=11,
    )


# ---------------------------------------------------------------------------
# Material, Studio Lighting & Renders
# ---------------------------------------------------------------------------

def assign_bone_coord_attribute(obj):
    mesh = obj.data
    n_verts = len(mesh.vertices)
    if n_verts < 4:
        return
    coords = np.empty(n_verts * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    pts = coords.reshape((n_verts, 3))

    centered = pts - pts.mean(axis=0, keepdims=True)
    cov = np.cov(centered.T)
    _, eigvecs = np.linalg.eigh(cov)
    basis = np.column_stack((eigvecs[:, 0], eigvecs[:, 1], eigvecs[:, 2])).astype(np.float32)
    bone_pts = centered @ basis

    if "BoneCoord" in mesh.attributes:
        mesh.attributes.remove(mesh.attributes["BoneCoord"])
    attr = mesh.attributes.new(name="BoneCoord", type='FLOAT_VECTOR', domain='POINT')
    attr.data.foreach_set("vector", bone_pts.ravel())


def create_bone_material():
    existing = bpy.data.materials.get("Skeleton_Bone_Mat")
    if existing is not None:
        return existing

    mat = bpy.data.materials.new(name="Skeleton_Bone_Mat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.52
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.28

    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "BoneCoord"

    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.6, 1.6, 0.45)

    noise_coarse = nt.nodes.new("ShaderNodeTexNoise")
    noise_coarse.inputs["Scale"].default_value = 1.4
    noise_coarse.inputs["Detail"].default_value = 7.0
    noise_coarse.inputs["Roughness"].default_value = 0.65

    noise_fine = nt.nodes.new("ShaderNodeTexNoise")
    noise_fine.inputs["Scale"].default_value = 5.5
    noise_fine.inputs["Detail"].default_value = 5.0
    noise_fine.inputs["Roughness"].default_value = 0.60

    mix_tex = nt.nodes.new("ShaderNodeMix")
    mix_tex.data_type = 'FLOAT'
    mix_tex.inputs["Factor"].default_value = 0.40

    # Warm cream/beige-ivory osteological bone finish matching reference image
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.24
    ramp.color_ramp.elements[0].color = (0.83, 0.72, 0.54, 1.0)
    elem_mid = ramp.color_ramp.elements.new(0.55)
    elem_mid.color = (0.92, 0.83, 0.66, 1.0)
    ramp.color_ramp.elements[2].position = 0.86
    ramp.color_ramp.elements[2].color = (0.96, 0.90, 0.77, 1.0)

    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = 10
    ao.inputs["Distance"].default_value = 7.0

    ao_ramp = nt.nodes.new("ShaderNodeValToRGB")
    ao_ramp.color_ramp.elements[0].position = 0.14
    ao_ramp.color_ramp.elements[0].color = (0.55, 0.44, 0.30, 1.0)
    ao_ramp.color_ramp.elements[1].position = 0.86
    ao_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)

    mix_ao = nt.nodes.new("ShaderNodeMix")
    mix_ao.data_type = 'RGBA'
    mix_ao.blend_type = 'MULTIPLY'
    mix_ao.inputs["Factor"].default_value = 0.84

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.11
    bump.inputs["Distance"].default_value = 0.18

    nt.links.new(attr.outputs["Vector"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise_coarse.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise_fine.inputs["Vector"])
    nt.links.new(noise_coarse.outputs["Fac"], mix_tex.inputs["A"])
    nt.links.new(noise_fine.outputs["Fac"], mix_tex.inputs["B"])
    nt.links.new(mix_tex.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ao.outputs["AO"], ao_ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mix_ao.inputs["A"])
    nt.links.new(ao_ramp.outputs["Color"], mix_ao.inputs["B"])
    nt.links.new(mix_ao.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(mix_tex.outputs["Result"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def apply_bone_material(parts):
    mat = create_bone_material()
    for obj in parts:
        assign_bone_coord_attribute(obj)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for poly in obj.data.polygons:
            poly.use_smooth = True


def _setup_white_bg_compositor(scene):
    scene.render.film_transparent = True
    ng = bpy.data.node_groups.new("StudioWhiteBG", 'CompositorNodeTree')
    scene.compositing_node_group = ng
    ng.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')

    rl = ng.nodes.new("CompositorNodeRLayers")
    ao = ng.nodes.new("CompositorNodeAlphaOver")
    ao.inputs["Background"].default_value = (1.0, 1.0, 1.0, 1.0)
    out = ng.nodes.new("NodeGroupOutput")

    ng.links.new(rl.outputs["Image"], ao.inputs["Foreground"])
    ng.links.new(ao.outputs["Image"], out.inputs["Image"])


def _add_area_light(name, loc, target, energy, size, color, col):
    ld = bpy.data.lights.new(name=name, type='AREA')
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name=name, object_data=ld)
    col.objects.link(lo)
    lo.location = Vector(loc)
    lo.rotation_euler = (Vector(target) - lo.location).to_track_quat('-Z', 'Y').to_euler()
    return lo


def _add_shadow_catcher_floor(z_mm, col):
    """Add a shadow-catcher strip directly under the bones (Y in [-25, +75])."""
    bm = bmesh.new()
    v0 = bm.verts.new((-220.0, -25.0, z_mm))
    v1 = bm.verts.new((180.0, -25.0, z_mm))
    v2 = bm.verts.new((180.0, 75.0, z_mm))
    v3 = bm.verts.new((-220.0, 75.0, z_mm))
    bm.faces.new((v0, v1, v2, v3))
    mesh = bpy.data.meshes.new("StudioFloor_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    floor = bpy.data.objects.new("StudioFloor", mesh)
    col.objects.link(floor)
    floor.is_shadow_catcher = True
    return floor


def _create_label_text(text, x_pos, z_pos, col):
    cdata = bpy.data.curves.new(name=f"Label_{text}_Curve", type='FONT')
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
    obj = bpy.data.objects.new(f"Label_{text}", cdata)
    col.objects.link(obj)
    # Place clearly in front of the shadow-catcher floor (Y = -36 mm) so rays never hit floor first
    obj.location = Vector((x_pos, -36.0, z_pos))
    obj.rotation_euler = Euler((math.radians(90.0), 0.0, 0.0), 'XYZ')
    return obj


def render_studio_lineup(parts, front_path, back_path, labeled_path):
    os.makedirs(os.path.dirname(front_path), exist_ok=True)
    scene = bpy.context.scene
    studio_col = create_collection("Studio_Setup")

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

    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.98, 0.98, 0.98, 1.0)
        bg.inputs["Strength"].default_value = 0.50

    _setup_white_bg_compositor(scene)

    xs, zs = [], []
    for obj in parts:
        for c in obj.bound_box:
            w = obj.matrix_world @ Vector(c)
            xs.append(w.x)
            zs.append(w.z)
    x_mid = 0.5 * (min(xs) + max(xs))
    z_floor = min(zs) - 0.5

    floor_obj = _add_shadow_catcher_floor(z_floor, studio_col)

    target = Vector((x_mid, 0.0, 56.0))
    _add_area_light("Studio_Key_TopLeft", (-220.0, -300.0, 260.0), target, energy=30.0, size=200.0, color=(1.0, 0.98, 0.94), col=studio_col)
    _add_area_light("Studio_Fill_Right", (240.0, -280.0, 90.0), target, energy=11.0, size=320.0, color=(0.98, 0.99, 1.0), col=studio_col)
    _add_area_light("Studio_Back_Key", (120.0, 320.0, 180.0), target, energy=22.0, size=280.0, color=(1.0, 0.99, 0.96), col=studio_col)

    cam_data = bpy.data.cameras.new("LineupCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 288.0
    cam_data.clip_start = 1.0
    cam_data.clip_end = 5000.0
    cam_obj = bpy.data.objects.new("LineupCam", cam_data)
    studio_col.objects.link(cam_obj)
    scene.camera = cam_obj

    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'

    # 1. Clean front orthographic studio lineup
    front_target = Vector((x_mid, 0.0, 56.0))
    cam_obj.location = Vector((x_mid, -450.0, 72.0))
    cam_obj.rotation_euler = (front_target - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = front_path
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Saved front lineup: {front_path}")

    # 2. Labeled front lineup (adds SCAPULA, CLAVICLE, HUMERUS, ULNA, RADIUS labels below)
    labels_col = create_collection("Studio_Labels", studio_col)
    label_specs = [
        ("SCAPULA", -112.0),
        ("CLAVICLE", -50.0),
        ("HUMERUS", 0.0),
        ("ULNA", 48.0),
        ("RADIUS", 94.0),
    ]
    label_objs = [_create_label_text(txt, xpos, z_floor - 5.2, labels_col) for txt, xpos in label_specs]
    front_labeled_target = Vector((x_mid, 0.0, 51.0))
    cam_obj.location = Vector((x_mid, -450.0, 67.0))
    cam_obj.rotation_euler = (front_labeled_target - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = labeled_path
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Saved labeled lineup: {labeled_path}")

    for lo in label_objs:
        lo.hide_render = True
        lo.hide_viewport = True

    # 3. Back 3/4 view showing posterior surfaces
    floor_obj.hide_render = True
    cam_data.ortho_scale = 285.0
    back_target = Vector((x_mid, 0.0, 58.0))
    cam_obj.location = Vector((x_mid + 165.0, 420.0, 120.0))
    cam_obj.rotation_euler = (back_target - cam_obj.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = back_path
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Saved back 3/4 lineup: {back_path}")

    return studio_col


# ---------------------------------------------------------------------------
# Main Build Entry Point
# ---------------------------------------------------------------------------

def build_all_5_bones():
    reset_scene()
    col = create_collection("Upper_Limb_5_Bones")

    builders = {
        "scapula": build_scapula,
        "clavicle": build_clavicle,
        "humerus": build_humerus,
        "ulna": build_ulna,
        "radius": build_radius,
    }

    parts = []
    for name in cfg.PART_NAMES:
        obj = builders[name](col)
        stat = jm.verify_part_manifold(obj)
        islands = _count_mesh_islands(obj)
        assert islands == 1, f"{name}: expected 1 connected island, got {islands}"
        print(
            f"[PART-OK] {name}: verts={stat['verts']}, faces={stat['faces']}, "
            f"nm={stat['non_manifold_edges']}, lv={stat['loose_verts']}, "
            f"islands={islands}, dims={stat['dimensions_mm']} mm, min_z={stat['min_z_mm']}"
        )
        parts.append(obj)

    apply_bone_material(parts)

    front_path = os.path.join(cfg.RENDERS_DIR, "upper_limb_5bones_lineup_front.png")
    back_path = os.path.join(cfg.RENDERS_DIR, "upper_limb_5bones_lineup_back34.png")
    labeled_path = os.path.join(cfg.RENDERS_DIR, "upper_limb_5bones_lineup_labeled.png")
    render_studio_lineup(parts, front_path, back_path, labeled_path)

    os.makedirs(os.path.dirname(cfg.MASTER_BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=cfg.MASTER_BLEND_PATH)
    print(f"[INFO] Saved master blend file: {cfg.MASTER_BLEND_PATH}")
    return parts


if __name__ == "__main__":
    build_all_5_bones()
