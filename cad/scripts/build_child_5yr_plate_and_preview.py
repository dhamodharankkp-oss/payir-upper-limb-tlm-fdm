"""
Builds the combined 5-year-old child 1:1 K1 print plate (plate_01_child_5yr_5bones.stl)
and renders visual verification previews of:
  1. All 5 child_5yr_1to1 bones on the 220x220 mm Creality K1 bed
  2. humerus_5yr_tilt40.stl and humerus_5yr_split_pin.stl on the K1 bed
"""

import json
import math
import os
import shutil

import bmesh
import bpy
from mathutils import Vector

OUT_DIR = r"e:\AG\Blender\exports\upper_limb_5bones\child_5yr_1to1"
ARTIFACT_DIR = r"C:\Users\Aarvam\.gemini\antigravity\brain\fbaf947b-8d63-4d1f-a41e-a2cca64aef30"


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_stl(path: str, name: str):
    bpy.ops.wm.stl_import(filepath=path)
    obj = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.select_get()][0]
    obj.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def get_bbox(obj):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mn = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    mx = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    return mn, mx, mx - mn


def add_k1_bed():
    # 220 x 220 mm dark PEI bed plate at Z = -0.5 mm (top at Z = 0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -0.5))
    bed = bpy.context.active_object
    bed.name = "K1_Bed_220x220"
    bed.scale = (220.0, 220.0, 1.0)
    bpy.ops.object.transform_apply(scale=True)

    mat = bpy.data.materials.new("PEI_Bed")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.06, 0.07, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    bed.data.materials.append(mat)

    # Border frame lines at +/- 110 mm
    bpy.ops.mesh.primitive_plane_add(size=222.0, location=(0.0, 0.0, -0.95))
    rim = bpy.context.active_object
    rim.name = "K1_Bed_Rim"
    rmat = bpy.data.materials.new("Bed_Rim")
    rmat.use_nodes = True
    rmat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.18, 0.45, 0.85, 1.0)
    rim.data.materials.append(rmat)
    return bed


def make_bone_material(name="BonePLA", color=(0.90, 0.88, 0.83, 1.0)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.38
    return mat


def setup_render(cam_loc, cam_target, out_png: str, res_x=1280, res_y=900):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.filepath = out_png

    # Soft studio world
    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.14, 0.16, 0.20, 1.0)
    bg.inputs["Strength"].default_value = 0.9

    # Key & fill area lights
    bpy.ops.object.light_add(type="AREA", location=(140.0, -140.0, 220.0))
    key = bpy.context.active_object
    key.data.energy = 80000.0
    key.data.size = 180.0
    key.rotation_euler = (math.radians(35), math.radians(15), math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-150.0, 120.0, 180.0))
    fill = bpy.context.active_object
    fill.data.energy = 45000.0
    fill.data.size = 200.0
    fill.rotation_euler = (math.radians(-30), math.radians(-20), math.radians(-145))

    # Camera
    bpy.ops.object.camera_add(location=cam_loc)
    cam = bpy.context.active_object
    direction = Vector(cam_target) - Vector(cam_loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 45.0
    cam.data.clip_end = 2000.0
    scene.camera = cam

    bpy.ops.render.render(write_still=True)


def build_plate_and_render():
    clear_scene()
    parts_order = [
        ("humerus", "humerus_5yr.stl"),
        ("ulna", "ulna_5yr.stl"),
        ("radius", "radius_5yr.stl"),
        ("scapula", "scapula_5yr.stl"),
        ("clavicle", "clavicle_5yr.stl"),
    ]

    objs = {}
    for key, fname in parts_order:
        obj = import_stl(os.path.join(OUT_DIR, fname), key)
        # Ensure longest horizontal span is along X for tidy row packing
        mn, mx, dims = get_bbox(obj)
        if dims.y > dims.x:
            obj.rotation_euler = (0.0, 0.0, math.pi * 0.5)
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(rotation=True)
        objs[key] = obj

    # Pack into clean rows along Y inside 220x220 mm:
    # Row 1: humerus (190 mm)
    # Row 2: ulna (158 mm)
    # Row 3: radius (145 mm)
    # Row 4: scapula (92 mm) + clavicle (82 mm) side-by-side in X!
    gap = 8.0
    row_specs = [
        [objs["humerus"]],
        [objs["ulna"]],
        [objs["radius"]],
        [objs["scapula"], objs["clavicle"]],
    ]

    row_heights = []
    for row in row_specs:
        # Place side-by-side in X, centered at X=0
        widths = [get_bbox(o)[2].x for o in row]
        total_w = sum(widths) + gap * (len(row) - 1)
        cur_x = -0.5 * total_w
        max_h = 0.0
        for o, w in zip(row, widths):
            mn, mx, dims = get_bbox(o)
            cx = 0.5 * (mn.x + mx.x)
            cy = 0.5 * (mn.y + mx.y)
            o.location.x += (cur_x + 0.5 * w) - cx
            o.location.y += -cy
            o.location.z += -mn.z
            cur_x += w + gap
            max_h = max(max_h, dims.y)
        row_heights.append(max_h)

    total_y = sum(row_heights) + gap * (len(row_specs) - 1)
    cur_y = -0.5 * total_y
    for row, rh in zip(row_specs, row_heights):
        target_y = cur_y + 0.5 * rh
        for o in row:
            o.location.y += target_y
        cur_y += rh + gap

    bpy.ops.object.select_all(action="DESELECT")
    for o in objs.values():
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs["humerus"]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Export combined plate STL
    plate_path = os.path.join(OUT_DIR, "plate_01_child_5yr_5bones.stl")
    bpy.ops.wm.stl_export(
        filepath=plate_path,
        export_selected_objects=True,
        ascii_format=False,
    )

    # Compute plate bbox
    all_coords = [o.matrix_world @ v.co for o in objs.values() for v in o.data.vertices]
    plate_dims = [
        round(max(c.x for c in all_coords) - min(c.x for c in all_coords), 2),
        round(max(c.y for c in all_coords) - min(c.y for c in all_coords), 2),
        round(max(c.z for c in all_coords) - min(c.z for c in all_coords), 2),
    ]
    print(f"[child_5yr_plate] dims={plate_dims} mm | fits_K1={plate_dims[0] <= 216 and plate_dims[1] <= 216}")

    # Assign bone PLA material & add K1 bed for render
    bone_mat = make_bone_material()
    for o in objs.values():
        o.data.materials.append(bone_mat)
    add_k1_bed()

    png_plate = os.path.join(OUT_DIR, "child_5yr_1to1_k1_plate.png")
    setup_render((0.0, -230.0, 260.0), (0.0, 0.0, 5.0), png_plate)
    shutil.copy2(png_plate, os.path.join(ARTIFACT_DIR, "child_5yr_1to1_k1_plate.png"))


def render_humerus_modes():
    clear_scene()
    tilt = import_stl(os.path.join(OUT_DIR, "humerus_5yr_tilt40.stl"), "Humerus_Tilt40")
    sp = import_stl(os.path.join(OUT_DIR, "humerus_5yr_split_pin.stl"), "Humerus_SplitPin")

    # Separate them on the K1 bed for clear side-by-side inspection
    # Put split-pin toward -Y and tilt40 toward +Y
    sp.location.y = -48.0
    tilt.location.y = 52.0
    bpy.ops.object.select_all(action="DESELECT")
    tilt.select_set(True)
    sp.select_set(True)
    bpy.ops.object.transform_apply(location=True)

    tilt.data.materials.append(make_bone_material("TiltPLA", (0.92, 0.88, 0.80, 1.0)))
    sp.data.materials.append(make_bone_material("SplitPLA", (0.84, 0.90, 0.95, 1.0)))
    add_k1_bed()

    png_modes = os.path.join(OUT_DIR, "humerus_5yr_tilt40_and_splitpin.png")
    setup_render((150.0, -210.0, 195.0), (0.0, 0.0, 35.0), png_modes)
    shutil.copy2(png_modes, os.path.join(ARTIFACT_DIR, "humerus_5yr_tilt40_and_splitpin.png"))


if __name__ == "__main__":
    build_plate_and_render()
    render_humerus_modes()
    print("OK: Plate exported and both verification previews rendered.")
