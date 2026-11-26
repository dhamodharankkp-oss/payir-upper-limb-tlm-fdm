# SPDX-License-Identifier: MIT
r"""
Reusable OrcaSlicer 2.5.1 Multi-Plate .3mf Project Builder.

Reads a JSON project manifest and packages:
  - Multiple Creality K1 (220x220 mm) plates with placed STL meshes
  - Embedded process/printer/filament settings (Metadata/project_settings.config)
  - Multi-plate layout (Metadata/model_settings.config)
  - Populated Project tab metadata (Title, HTML Description, Designer, Thumbnails, Model Pictures)

Usage:
  & "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" `
    "e:\AG\Blender\scripts\tools\build_orcaslicer_3mf_project.py" --manifest "<manifest.json>"
"""

import argparse
import datetime
import html
import json
import os
import struct
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image


def read_binary_stl(stl_path: str):
    """Fast binary STL reader returning deduplicated (vertices, triangles, bbox_min, bbox_max)."""
    with open(stl_path, "rb") as f:
        header = f.read(80)
        count_bytes = f.read(4)
        if len(count_bytes) < 4:
            raise ValueError(f"Invalid STL file: {stl_path}")
        tri_count = struct.unpack("<I", count_bytes)[0]
        raw = f.read(tri_count * 50)
        if len(raw) < tri_count * 50:
            raise ValueError(f"Truncated binary STL: {stl_path}")

    dtype = np.dtype([
        ("normal", "<f4", (3,)),
        ("v", "<f4", (3, 3)),
        ("attr", "<u2"),
    ])
    arr = np.frombuffer(raw, dtype=dtype, count=tri_count)
    pts = arr["v"].reshape(-1, 3)

    # Deduplicate vertices cleanly at 1e-6 mm precision and drop any degenerate tris
    rounded = np.round(pts, 6)
    _, unique_idx, inv_idx = np.unique(
        rounded, axis=0, return_index=True, return_inverse=True
    )
    # Preserve deterministic vertex order
    order = np.argsort(unique_idx)
    remap = np.empty_like(order)
    remap[order] = np.arange(len(order))

    verts = pts[unique_idx[order]]
    tris = remap[inv_idx].reshape(-1, 3)
    valid = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    tris = tris[valid]

    bmin = verts.min(axis=0)
    bmax = verts.max(axis=0)
    return verts, tris, bmin, bmax


def build_object_model_xml(obj_id: int, verts: np.ndarray, tris: np.ndarray) -> str:
    """Builds a 3D/Objects/object_N.model XML string."""
    u = str(uuid.uuid4())
    v_lines = [
        f'     <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>'
        for x, y, z in verts
    ]
    t_lines = [
        f'     <triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}"/>'
        for a, b, c in tris
    ]
    return "\n".join([
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" requiredextensions="p">',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        " <resources>",
        f'  <object id="{obj_id}" p:UUID="{u}" type="model">',
        "   <mesh>",
        "    <vertices>",
        *v_lines,
        "    </vertices>",
        "    <triangles>",
        *t_lines,
        "    </triangles>",
        "   </mesh>",
        "  </object>",
        " </resources>",
        "</model>",
    ])


def build_root_3dmodel_xml(manifest: dict, items: list[dict]) -> str:
    """Builds 3D/3dmodel.model with Project tab metadata + component references."""
    today = datetime.date.today().isoformat()
    title = html.escape(manifest.get("title", "3D Print Project"))
    desc = html.escape(manifest.get("description_html", ""))
    designer = html.escape(manifest.get("designer", "Aarvam"))
    profile_title = html.escape(manifest.get("profile_title", "Creality K1 (0.4mm)"))
    license_name = html.escape(manifest.get("license", "CC-BY-NC-SA"))

    obj_blocks = []
    build_items = []
    for it in items:
        comp_uuid = str(uuid.uuid4())
        obj_uuid = str(uuid.uuid4())
        tx, ty, tz = it["translate"]
        transform = f"1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}"
        obj_blocks.append(
            f'  <object id="{it["root_obj_id"]}" p:UUID="{obj_uuid}" type="model">\n'
            f'   <components>\n'
            f'    <component p:path="/3D/Objects/object_{it["mesh_obj_id"]}.model" objectid="{it["mesh_obj_id"]}" p:UUID="{comp_uuid}" transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n'
            f'   </components>\n'
            f'  </object>'
        )
        build_items.append(
            f'  <item objectid="{it["root_obj_id"]}" p:UUID="{uuid.uuid4()}" transform="{transform}" printable="1" />'
        )

    return "\n".join([
        "<?xml version='1.0' encoding='UTF-8'?>",
        '<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" unit="millimeter" xml:lang="en-US" requiredextensions="p" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">',
        ' <metadata name="Application">OrcaSlicer-02.5.1.0</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        f' <metadata name="CreationDate">{today}</metadata>',
        f' <metadata name="ModificationDate">{today}</metadata>',
        f' <metadata name="Title">{title}</metadata>',
        f' <metadata name="Description">{desc}</metadata>',
        f' <metadata name="Designer">{designer}</metadata>',
        f' <metadata name="ProfileTitle">{profile_title}</metadata>',
        f' <metadata name="License">{license_name}</metadata>',
        ' <metadata name="Origin">original</metadata>',
        ' <metadata name="Thumbnail_Middle">/Auxiliaries/.thumbnails/thumbnail_middle.png</metadata>',
        ' <metadata name="Thumbnail_Small">/Auxiliaries/.thumbnails/thumbnail_small.png</metadata>',
        " <resources>",
        *obj_blocks,
        " </resources>",
        " <build>",
        *build_items,
        " </build>",
        "</model>",
    ])


def build_model_settings_xml(plates: list[dict], items: list[dict]) -> str:
    """Builds Metadata/model_settings.config defining objects, parts, and multi-plate layout."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]

    for it in items:
        lines.extend([
            f'  <object id="{it["root_obj_id"]}">',
            f'    <metadata key="name" value="{html.escape(it["name"])}"/>',
            '    <metadata key="extruder" value="1"/>',
            f'    <metadata face_count="{it["face_count"]}"/>',
            f'    <part id="{it["part_id"]}" subtype="normal_part">',
            f'      <metadata key="name" value="{html.escape(it["name"])}"/>',
            '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
            '      <metadata key="source_object_id" value="0"/>',
            '      <metadata key="source_volume_id" value="0"/>',
            '      <metadata key="source_offset_x" value="0"/>',
            '      <metadata key="source_offset_y" value="0"/>',
            '      <metadata key="source_offset_z" value="0"/>',
            f'      <mesh_stat face_count="{it["face_count"]}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
            "    </part>",
            "  </object>",
        ])

    for p_idx, plate in enumerate(plates, start=1):
        plate_name = html.escape(plate.get("name", f"Plate {p_idx}"))
        plate_items = [it for it in items if it["plate_id"] == p_idx]
        lines.extend([
            "  <plate>",
            f'    <metadata key="plater_id" value="{p_idx}"/>',
            f'    <metadata key="plater_name" value="{plate_name}"/>',
            '    <metadata key="locked" value="false"/>',
        ])
        for idx, it in enumerate(plate_items, start=1):
            lines.extend([
                "    <model_instance>",
                f'      <metadata key="object_id" value="{it["root_obj_id"]}"/>',
                '      <metadata key="instance_id" value="0"/>',
                f'      <metadata key="identify_id" value="{p_idx * 100 + idx}"/>',
                "    </model_instance>",
            ])
        lines.append("  </plate>")

    lines.append("  <assemble>")
    for it in items:
        tx, ty, tz = it["translate"]
        lines.append(
            f'   <assemble_item object_id="{it["root_obj_id"]}" instance_id="0" '
            f'transform="1 0 0 0 1 0 0 0 1 {tx:.6f} {ty:.6f} {tz:.6f}" offset="0 0 0" />'
        )
    lines.append("  </assemble>")
    lines.append("</config>")
    return "\n".join(lines)


def build_project_settings_json(manifest: dict) -> str:
    """Merges base OrcaSlicer preset JSON + manifest overrides into Metadata/project_settings.config."""
    settings = {}
    base_preset = manifest.get("base_process_preset")
    if base_preset and os.path.exists(base_preset):
        with open(base_preset, "r", encoding="utf-8") as f:
            settings.update(json.load(f))

    # Remove process-preset-only metadata keys, keep slicer parameters
    for k in ["type", "name", "from", "inherits", "is_custom_defined", "compatible_printers"]:
        settings.pop(k, None)

    settings["printer_settings_id"] = manifest.get(
        "printer_settings_id", "Creality K1 (0.4 nozzle) - Copy"
    )
    settings["print_settings_id"] = manifest.get(
        "print_settings_id", "K1 Organic - 40deg Tilted Tree (0.16mm)"
    )
    settings["filament_settings_id"] = [
        manifest.get("filament_settings_id", "Generic PLA @Creality")
    ]
    settings["curr_bed_type"] = "Textured PEI Plate"
    # Prevent OrcaSlicer relative-E error when loading K1 machine preset
    settings.setdefault("before_layer_change_gcode", ";BEFORE_LAYER_CHANGE\nG92 E0\n;[layer_z]\n")
    settings.setdefault("layer_change_gcode", ";AFTER_LAYER_CHANGE\n;[layer_z]\n")
    settings.update(manifest.get("process_overrides", {}))
    return json.dumps(settings, indent=4)


def make_thumbnail_bytes(img_path: str, max_size: tuple[int, int]) -> bytes:
    import io
    with Image.open(img_path) as im:
        im = im.convert("RGBA")
        im.thumbnail(max_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()


def build_3mf(manifest_path: str):
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    out_3mf = manifest["output_3mf"]
    os.makedirs(os.path.dirname(os.path.abspath(out_3mf)), exist_ok=True)

    # K1 bed is 220x220 mm; OrcaSlicer lays out multi-plate grids in 3 columns
    # with 1.2x bed pitch (264 mm in +X, -264 mm in -Y per row)
    bed_w = float(manifest.get("bed_width", 220.0))
    bed_h = float(manifest.get("bed_height", 220.0))
    bed_cx = float(manifest.get("bed_center_x", bed_w * 0.5))
    bed_cy = float(manifest.get("bed_center_y", bed_h * 0.5))
    plate_cols = int(manifest.get("plate_cols", 3))
    pitch_x = bed_w * 1.2
    pitch_y = bed_h * 1.2

    items = []
    object_models = {}
    rels_targets = []

    next_id = 1
    for p_idx, plate in enumerate(manifest["plates"], start=1):
        col = (p_idx - 1) % plate_cols
        row = (p_idx - 1) // plate_cols
        plate_cx = bed_cx + col * pitch_x
        plate_cy = bed_cy - row * pitch_y

        for obj_spec in plate["objects"]:
            stl_path = obj_spec["stl"]
            verts, tris, bmin, bmax = read_binary_stl(stl_path)

            # Center mesh locally around XY=0, Z=0 so placement transform is exact
            cx = 0.5 * (bmin[0] + bmax[0])
            cy = 0.5 * (bmin[1] + bmax[1])
            cz = bmin[2]
            verts_local = verts - np.array([cx, cy, cz], dtype=np.float32)

            mesh_id = next_id
            root_id = next_id + 1
            part_id = next_id + 2
            next_id += 3

            # Place on this plate's world bed center + local offset
            px = plate_cx + float(obj_spec.get("offset_x", 0.0))
            py = plate_cy + float(obj_spec.get("offset_y", 0.0))
            pz = 0.5 * float(bmax[2] - bmin[2])  # assembly z-center

            object_models[f"3D/Objects/object_{mesh_id}.model"] = build_object_model_xml(
                mesh_id, verts_local, tris
            )
            rels_targets.append(f"/3D/Objects/object_{mesh_id}.model")
            items.append({
                "name": obj_spec.get("name", Path(stl_path).stem),
                "plate_id": p_idx,
                "mesh_obj_id": mesh_id,
                "root_obj_id": root_id,
                "part_id": part_id,
                "face_count": int(len(tris)),
                "vert_count": int(len(verts_local)),
                "translate": (px, py, 0.0),
                "assemble_z": pz,
            })

    content_types = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>',
        ' <Default Extension="png" ContentType="image/png"/>',
        ' <Default Extension="gcode" ContentType="text/x.gcode"/>',
        "</Types>",
    ])

    root_rels = "\n".join([
        "<?xml version='1.0' encoding='UTF-8'?>",
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />',
        ' <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_3mf.png" Id="rel-2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" />',
        ' <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_middle.png" Id="rel-4" Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-middle" />',
        ' <Relationship Target="/Auxiliaries/.thumbnails/thumbnail_small.png" Id="rel-5" Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-small" />',
        "</Relationships>",
    ])

    model_rels_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for i, tgt in enumerate(rels_targets, start=1):
        model_rels_lines.append(
            f' <Relationship Target="{tgt}" Id="rel-{i}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        )
    model_rels_lines.append("</Relationships>")
    model_rels = "\n".join(model_rels_lines)

    root_model = build_root_3dmodel_xml(manifest, items)
    model_settings = build_model_settings_xml(manifest["plates"], items)
    project_settings = build_project_settings_json(manifest)

    with zipfile.ZipFile(out_3mf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("3D/3dmodel.model", root_model)
        z.writestr("3D/_rels/3dmodel.model.rels", model_rels)
        for path_in_zip, xml_str in object_models.items():
            z.writestr(path_in_zip, xml_str)
        z.writestr("Metadata/model_settings.config", model_settings)
        z.writestr("Metadata/project_settings.config", project_settings)

        # Thumbnails & Project Tab pictures
        cover = manifest.get("cover_image")
        if cover and os.path.exists(cover):
            z.writestr("Auxiliaries/.thumbnails/thumbnail_3mf.png", make_thumbnail_bytes(cover, (512, 512)))
            z.writestr("Auxiliaries/.thumbnails/thumbnail_middle.png", make_thumbnail_bytes(cover, (512, 512)))
            z.writestr("Auxiliaries/.thumbnails/thumbnail_small.png", make_thumbnail_bytes(cover, (256, 256)))

        for pic_path in manifest.get("model_pictures", []):
            if os.path.exists(pic_path):
                z.write(pic_path, f"Auxiliaries/Model Pictures/{os.path.basename(pic_path)}")

    # Self-verify XML, JSON, and archive integrity
    with zipfile.ZipFile(out_3mf, "r") as z:
        ET.fromstring(z.read("[Content_Types].xml"))
        ET.fromstring(z.read("_rels/.rels"))
        ET.fromstring(z.read("3D/3dmodel.model"))
        ET.fromstring(z.read("3D/_rels/3dmodel.model.rels"))
        ET.fromstring(z.read("Metadata/model_settings.config"))
        json.loads(z.read("Metadata/project_settings.config"))

    print(f"OK: Built & verified {out_3mf} | plates={len(manifest['plates'])} | objects={len(items)}")
    for it in items:
        print(f"  Plate {it['plate_id']} | {it['name']:30s} | verts={it['vert_count']} | faces={it['face_count']} | pos={it['translate']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, help="Path to project manifest JSON")
    args = p.parse_args()
    build_3mf(args.manifest)


if __name__ == "__main__":
    main()
