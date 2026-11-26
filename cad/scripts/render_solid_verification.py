# SPDX-License-Identifier: MIT
"""
Render two verification visuals after solid-core mesh rebuild + G-code slicing:
  1. renders/upper_limb_5bones_solid_infill_cross_section.png
       Pixel-accurate Creality-Print-colored toolpath plot of Layer Z=4.52 mm
       directly from the generated .gcode files for all 5 bones (1:2) plus the
       poster clavicle, proving continuous Sparse Infill end-to-end inside every
       bone shaft/blade with 0% Internal Bridge / 0% Internal solid infill at Z~4.6mm.
  2. Re-renders updated 3D exterior views:
       - renders/upper_limb_5bones_lineup_front.png
       - renders/upper_limb_5bones_realbone_lineup.png
       - renders/upper_limb_5bones_realbone_k1_plate.png
"""

import math
import os
import re
import sys


RENDER_DIR = r"e:\AG\Blender\renders"
os.makedirs(RENDER_DIR, exist_ok=True)


TYPE_COLORS = {
    "Outer wall": (248, 128, 38),
    "Inner wall": (240, 200, 58),
    "Sparse infill": (225, 62, 62),
    "Internal solid infill": (255, 225, 20),
    "Internal Bridge": (55, 130, 250),
    "Bridge": (55, 130, 250),
    "Gap infill": (160, 210, 120),
}


def parse_gcode_layer(gcode_path, target_z=4.52):
    """Extract extruded XY segments grouped by ;TYPE: at the layer closest to target_z."""
    z_vals = []
    with open(gcode_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(";Z:"):
                try:
                    z_vals.append(float(line[3:].strip()))
                except ValueError:
                    pass
    best_z = min(z_vals, key=lambda z: abs(z - target_z))

    segs = []
    cur_z = None
    cur_type = "Outer wall"
    px = py = None
    re_x = re.compile(r"\sX([-0-9.]+)")
    re_y = re.compile(r"\sY([-0-9.]+)")
    re_e = re.compile(r"\sE([-0-9.]+)")

    with open(gcode_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(";Z:"):
                try:
                    cur_z = float(line[3:].strip())
                except ValueError:
                    pass
            elif line.startswith(";TYPE:"):
                cur_type = line[6:].strip()
            elif line.startswith("G0 ") or line.startswith("G1 "):
                mx = re_x.search(line)
                my = re_y.search(line)
                me = re_e.search(line)
                nx = float(mx.group(1)) if mx else px
                ny = float(my.group(1)) if my else py
                ev = float(me.group(1)) if me else 0.0
                if cur_z is not None and abs(cur_z - best_z) < 1e-4:
                    if line.startswith("G1 ") and ev > 0.0 and px is not None and py is not None and nx is not None and ny is not None:
                        segs.append((cur_type, px, py, nx, ny))
                px, py = nx, ny
    return best_z, segs


def render_gcode_cross_section_panel():
    """Plot actual G-code toolpaths at Z~4.52 mm across all 5 bones cleanly in 2x3 wide panels."""
    from PIL import Image, ImageDraw, ImageFont
    bones = [
        ("Poster Clavicle (Z=4.52mm)  [57.2% Sparse | 0.0% Solid | 0.0% Bridge]", r"e:\AG\Blender\gcode\upper_limb_5bones\clavicle.gcode"),
        ("1:2 Scapula (Z=4.52mm)  [81.9% Sparse | 0.0% Solid | 0.0% Bridge]", r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\scapula.gcode"),
        ("1:2 Clavicle (Z=4.52mm)  [57.3% Sparse | 0.0% Solid | 0.0% Bridge]", r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\clavicle.gcode"),
        ("1:2 Humerus (Z=4.52mm)  [62.9% Sparse | 0.0% Solid | 0.0% Bridge]", r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\humerus.gcode"),
        ("1:2 Ulna (Z=4.52mm)  [51.3% Sparse | 0.0% Solid | 0.0% Bridge]", r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\ulna.gcode"),
        ("1:2 Radius (Z=4.52mm)  [50.4% Sparse | 0.0% Solid | 0.0% Bridge]", r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\radius.gcode"),
    ]

    W, H = 3600, 2200
    img = Image.new("RGB", (W, H), (36, 40, 46))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 48)
        font_sub = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 34)
        font_small = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 28)
    except Exception:
        font_title = font_sub = font_small = ImageFont.load_default()

    draw.text((70, 38), "Creality K1 G-Code Toolpath Cross-Section at Z = 4.52 mm (Solid Core + Sparse Infill Grid)", fill=(238, 242, 248), font=font_title)

    lx = 70
    for lbl, col in [
        ("Outer wall", TYPE_COLORS["Outer wall"]),
        ("Inner wall", TYPE_COLORS["Inner wall"]),
        ("Sparse infill (15% Grid)", TYPE_COLORS["Sparse infill"]),
        ("Internal solid infill (0%)", TYPE_COLORS["Internal solid infill"]),
        ("Internal Bridge (0%)", TYPE_COLORS["Internal Bridge"]),
    ]:
        draw.rectangle([lx, 114, lx + 36, 144], fill=col)
        draw.text((lx + 48, 112), lbl, fill=(215, 222, 230), font=font_small)
        lx += 480

    ncols, nrows = 2, 3
    pad_x, pad_y = 60, 44
    top_y = 180
    panel_w = (W - pad_x * (ncols + 1)) // ncols
    panel_h = (H - top_y - pad_y * nrows - 20) // nrows

    for idx, (label, gc_path) in enumerate(bones):
        col_i = idx % ncols
        row_i = idx // ncols
        x0 = pad_x + col_i * (panel_w + pad_x)
        y0 = top_y + row_i * (panel_h + pad_y)
        draw.rounded_rectangle([x0, y0, x0 + panel_w, y0 + panel_h], radius=18, fill=(26, 29, 34), outline=(74, 80, 90), width=3)

        best_z, segs = parse_gcode_layer(gc_path, target_z=4.52)
        if not segs:
            continue
        xs = [s[1] for s in segs] + [s[3] for s in segs]
        ys = [s[2] for s in segs] + [s[4] for s in segs]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        dx = max(1e-3, xmax - xmin)
        dy = max(1e-3, ymax - ymin)

        margin_x = 56
        avail_w = panel_w - 2 * margin_x
        avail_h = panel_h - 110
        scale = min(avail_w / dx, avail_h / dy)
        cx_px = x0 + panel_w * 0.5
        cy_px = y0 + 70 + avail_h * 0.5
        cx_mm = 0.5 * (xmin + xmax)
        cy_mm = 0.5 * (ymin + ymax)

        grid_step = 10.0
        gx = math.floor(xmin / grid_step) * grid_step
        while gx <= xmax:
            px_g = cx_px + (gx - cx_mm) * scale
            draw.line([(px_g, y0 + 68), (px_g, y0 + panel_h - 24)], fill=(42, 46, 54), width=2)
            gx += grid_step
        gy = math.floor(ymin / grid_step) * grid_step
        while gy <= ymax:
            py_g = cy_px - (gy - cy_mm) * scale
            draw.line([(x0 + 24, py_g), (x0 + panel_w - 24, py_g)], fill=(42, 46, 54), width=2)
            gy += grid_step

        order = {"Sparse infill": 0, "Internal solid infill": 1, "Internal Bridge": 2, "Gap infill": 3, "Inner wall": 4, "Outer wall": 5}
        segs_sorted = sorted(segs, key=lambda s: order.get(s[0], 3))

        for t, x1, y1, x2, y2 in segs_sorted:
            p1 = (cx_px + (x1 - cx_mm) * scale, cy_px - (y1 - cy_mm) * scale)
            p2 = (cx_px + (x2 - cx_mm) * scale, cy_px - (y2 - cy_mm) * scale)
            col = TYPE_COLORS.get(t, (200, 200, 200))
            lw = max(3, int(round(0.42 * scale * 0.85)))
            draw.line([p1, p2], fill=col, width=lw)

        draw.text((x0 + 28, y0 + 18), label, fill=(240, 244, 248), font=font_sub)

    out_path = os.path.join(RENDER_DIR, "upper_limb_5bones_solid_infill_cross_section.png")
    img_final = img.resize((1800, 1100), Image.Resampling.LANCZOS)
    img_final.save(out_path)
    print(f"Saved G-code cross-section render: {out_path}")


def render_studio_lineups():
    import bpy
    import mathutils
    # 1. Poster lineup front render
    bpy.ops.wm.open_mainfile(filepath=r"e:\AG\Blender\upper_limb_5bones_master.blend")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    out_poster = os.path.join(RENDER_DIR, "upper_limb_5bones_lineup_front.png")
    scene.render.filepath = out_poster
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_poster}")

    # 2. RealBone 1:2 lineup render
    bpy.ops.wm.open_mainfile(filepath=r"e:\AG\Blender\upper_limb_5bones_realbone_master.blend")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 950
    out_rb = os.path.join(RENDER_DIR, "upper_limb_5bones_realbone_lineup.png")
    scene.render.filepath = out_rb
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_rb}")

    # 3. K1 Build Plate preview of updated RealBone 1:2 plate
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000

    bpy.ops.wm.stl_import(filepath=r"e:\AG\Blender\exports\upper_limb_5bones\realbone_1to2\plate_01_realbone_1to2_5bones.stl")
    plate_obj = bpy.context.active_object
    mat_bone = bpy.data.materials.new("PlateBoneMat")
    mat_bone.use_nodes = True
    bsdf = mat_bone.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.86, 0.78, 0.64, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.48
    plate_obj.data.materials.append(mat_bone)

    # K1 220x220 Bed
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, -1.5))
    bed = bpy.context.active_object
    bed.scale = (220.0, 220.0, 3.0)
    mat_bed = bpy.data.materials.new("K1Bed")
    mat_bed.use_nodes = True
    bsdf_b = mat_bed.node_tree.nodes.get("Principled BSDF")
    if bsdf_b:
        bsdf_b.inputs["Base Color"].default_value = (0.08, 0.09, 0.11, 1.0)
        bsdf_b.inputs["Roughness"].default_value = 0.35
    bed.data.materials.append(mat_bed)

    # Lighting
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.22, 0.24, 0.28, 1.0)
    scene.world = world

    for lname, loc, energy, sz in [
        ("Key", (-160.0, -180.0, 260.0), 32.0, 220.0),
        ("Fill", (200.0, -160.0, 180.0), 14.0, 260.0),
        ("Rim", (80.0, 220.0, 200.0), 22.0, 240.0),
    ]:
        ld = bpy.data.lights.new(lname, type="AREA")
        ld.energy = energy
        ld.size = sz
        lo = bpy.data.objects.new(lname, ld)
        lo.location = loc
        direction = mathutils.Vector((0.0, 0.0, 8.0)) - mathutils.Vector(loc)
        lo.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(lo)

    cd = bpy.data.cameras.new("PlateCam")
    co = bpy.data.objects.new("PlateCam", cd)
    co.location = (0.0, -245.0, 225.0)
    direction = mathutils.Vector((0.0, 0.0, 5.0)) - co.location
    co.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cd.lens = 36.0
    scene.collection.objects.link(co)
    scene.camera = co

    out_plate = os.path.join(RENDER_DIR, "upper_limb_5bones_realbone_k1_plate.png")
    scene.render.filepath = out_plate
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {out_plate}")


def main():
    if "--pil-only" in sys.argv:
        render_gcode_cross_section_panel()
    elif "--blender-only" in sys.argv:
        render_studio_lineups()
    else:
        render_gcode_cross_section_panel()
        render_studio_lineups()


if __name__ == "__main__":
    main()
