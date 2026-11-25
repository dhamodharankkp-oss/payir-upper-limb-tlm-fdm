"""
Create custom K1 sparse-infill process profile, benchmark parts/clavicle.stl
against default Creality K1 profiles at Z = 4.60 mm, slice all 17 STLs
(poster, 1:2, 1:1) using CrealityPrint.exe --cli, and audit G-code ;TYPE: stats.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile


CREALITY_PRINT = r"C:\Program Files\Creality\Creality Print 7.3\CrealityPrint.exe"
PROFILE_ROOT = r"C:\Program Files\Creality\Creality Print 7.3\resources\profiles\Creality"
MACHINE_JSON = os.path.join(PROFILE_ROOT, "machine", "Creality K1 0.4 nozzle.json")
PROC_016_JSON = os.path.join(PROFILE_ROOT, "process", "0.16mm Standard @Creality K1 0.4 nozzle.json")
PROC_020_JSON = os.path.join(PROFILE_ROOT, "process", "0.20mm Standard @Creality K1 0.4 nozzle.json")
FILAMENT_JSON = os.path.join(PROFILE_ROOT, "filament", "Generic PLA @Creality K1 0.4 nozzle.json")

EXPORT_ROOT = r"e:\AG\Blender\exports\upper_limb_5bones"
CUSTOM_PROC_JSON = os.path.join(EXPORT_ROOT, "k1_sparse_infill_process.json")

SLICE_JOBS = [
    # Poster set
    (os.path.join(EXPORT_ROOT, "parts", "scapula.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones\scapula.gcode"),
    (os.path.join(EXPORT_ROOT, "parts", "clavicle.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones\clavicle.gcode"),
    (os.path.join(EXPORT_ROOT, "parts", "humerus.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones\humerus.gcode"),
    (os.path.join(EXPORT_ROOT, "parts", "ulna.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones\ulna.gcode"),
    (os.path.join(EXPORT_ROOT, "parts", "radius.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones\radius.gcode"),
    (os.path.join(EXPORT_ROOT, "plates", "plate_01_upper_limb_5bones.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones\plate_01_upper_limb_5bones.gcode"),
    # Real-bone 1:2 set
    (os.path.join(EXPORT_ROOT, "realbone_1to2", "scapula.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\scapula.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to2", "clavicle.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\clavicle.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to2", "humerus.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\humerus.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to2", "ulna.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\ulna.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to2", "radius.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\radius.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to2", "plate_01_realbone_1to2_5bones.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to2\plate_01_realbone_1to2_5bones.gcode"),
    # Real-bone 1:1 life-size set
    (os.path.join(EXPORT_ROOT, "realbone_1to1_lifesize", "scapula_1to1.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to1\scapula_1to1.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to1_lifesize", "clavicle_1to1.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to1\clavicle_1to1.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to1_lifesize", "humerus_1to1.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to1\humerus_1to1.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to1_lifesize", "ulna_1to1.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to1\ulna_1to1.gcode"),
    (os.path.join(EXPORT_ROOT, "realbone_1to1_lifesize", "radius_1to1.stl"), r"e:\AG\Blender\gcode\upper_limb_5bones_realbone_1to1\radius_1to1.gcode"),
]


def create_custom_process_json():
    with open(PROC_016_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["name"] = "0.16mm Sparse-Infill Solid Bone @Creality K1 0.4 nozzle"
    data["ensure_vertical_shell_thickness"] = "none"
    data["top_shell_layers"] = "3"
    data["bottom_shell_layers"] = "3"
    data["top_shell_thickness"] = "0"
    data["bottom_shell_thickness"] = "0"
    data["wall_loops"] = "2"
    data["sparse_infill_density"] = "15%"
    data["sparse_infill_pattern"] = "grid"
    data["minimum_sparse_infill_area"] = "5"
    data["detect_narrow_internal_solid_infill"] = "0"
    os.makedirs(os.path.dirname(CUSTOM_PROC_JSON), exist_ok=True)
    with open(CUSTOM_PROC_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Created custom process profile: {CUSTOM_PROC_JSON}")


def slice_stl(stl_path, out_gcode, proc_json):
    os.makedirs(os.path.dirname(out_gcode), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            CREALITY_PRINT,
            "--cli",
            "--slice", "0",
            "--need-gcode-file",
            "--outputdir", tmp,
            "--load-settings", f"{MACHINE_JSON};{proc_json}",
            "--load-filaments", FILAMENT_JSON,
            stl_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        plate_gc = os.path.join(tmp, "plate_1.gcode")
        if res.returncode != 0 or not os.path.exists(plate_gc):
            raise RuntimeError(f"CrealityPrint failed for {stl_path}: rc={res.returncode}\n{res.stderr}\n{res.stdout}")
        shutil.copy2(plate_gc, out_gcode)


def audit_gcode(gcode_path, target_z=4.60):
    has_config_end = False
    cur_type = "UNKNOWN"
    cur_z = 0.0
    totals = {}
    slice_totals = {}
    slice_z_used = None
    best_dz = 999.0
    est_time = ""
    fil_g = ""
    layers = 0

    # First find closest layer Z to target_z
    z_values = []
    with open(gcode_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(";Z:"):
                try:
                    z_values.append(float(line[3:].strip()))
                except ValueError:
                    pass
            elif "; CONFIG_BLOCK_END" in line:
                has_config_end = True
            elif line.startswith("; total layers count ="):
                layers = int(line.split("=")[1].strip())
            elif line.startswith("; estimated printing time"):
                est_time = line.split("=", 1)[1].strip()
            elif line.startswith("; total filament weight"):
                fil_g = line.split("=", 1)[1].strip()

    for zv in z_values:
        if abs(zv - target_z) < best_dz:
            best_dz = abs(zv - target_z)
            slice_z_used = zv

    with open(gcode_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith(";Z:"):
                try:
                    cur_z = float(line[3:].strip())
                except ValueError:
                    pass
            elif line.startswith(";TYPE:"):
                cur_type = line[6:].strip()
            elif line.startswith("G1 ") and " E" in line and (" X" in line or " Y" in line):
                e_val = 0.0
                for tok in line.split():
                    if tok.startswith("E"):
                        try:
                            e_val = float(tok[1:])
                        except ValueError:
                            e_val = 0.0
                if e_val > 0.0:
                    totals[cur_type] = totals.get(cur_type, 0.0) + e_val
                    if slice_z_used is not None and abs(cur_z - slice_z_used) < 1e-4:
                        slice_totals[cur_type] = slice_totals.get(cur_type, 0.0) + e_val

    tot_e = sum(totals.values()) or 1.0
    st_e = sum(slice_totals.values()) or 1.0
    pct_all = {k: round(100.0 * v / tot_e, 1) for k, v in sorted(totals.items(), key=lambda x: -x[1])}
    pct_z = {k: round(100.0 * v / st_e, 1) for k, v in sorted(slice_totals.items(), key=lambda x: -x[1])}
    return {
        "has_config_block_end": has_config_end,
        "layers": layers,
        "est_time": est_time,
        "filament_g": fil_g,
        "total_extrusion_mm": round(tot_e, 1),
        "all_types_pct": pct_all,
        "z_sample_mm": slice_z_used,
        "z_sample_types_pct": pct_z,
    }


def main():
    create_custom_process_json()
    report = {"benchmarks_parts_clavicle": {}, "sliced_jobs": {}, "all_passed": True}

    clav_stl = os.path.join(EXPORT_ROOT, "parts", "clavicle.stl")
    print("\n=== Benchmarking parts/clavicle.stl at Z ~ 4.60 mm ===")
    with tempfile.TemporaryDirectory() as tmp:
        for label, pj in [
            ("default_0.20mm", PROC_020_JSON),
            ("default_0.16mm", PROC_016_JSON),
            ("custom_sparse_0.16mm", CUSTOM_PROC_JSON),
        ]:
            tmp_gc = os.path.join(tmp, f"{label}.gcode")
            slice_stl(clav_stl, tmp_gc, pj)
            au = audit_gcode(tmp_gc, target_z=4.60)
            report["benchmarks_parts_clavicle"][label] = au
            z_pct = au["z_sample_types_pct"]
            print(
                f"  [{label}] total Sparse={au['all_types_pct'].get('Sparse infill', 0.0)}% | "
                f"at Z={au['z_sample_mm']:.2f}mm -> Sparse={z_pct.get('Sparse infill', 0.0)}%, "
                f"InternalSolid={z_pct.get('Internal solid infill', 0.0)}%, "
                f"InternalBridge={z_pct.get('Internal Bridge', 0.0)}%"
            )

    print("\n=== Slicing All 17 STLs with k1_sparse_infill_process.json ===")
    for stl_p, gc_p in SLICE_JOBS:
        slice_stl(stl_p, gc_p, CUSTOM_PROC_JSON)
        au = audit_gcode(gc_p, target_z=4.60)
        rel_gc = os.path.relpath(gc_p, r"e:\AG\Blender")
        report["sliced_jobs"][rel_gc] = au
        sp_all = au["all_types_pct"].get("Sparse infill", 0.0)
        sp_z = au["z_sample_types_pct"].get("Sparse infill", 0.0)
        sol_z = au["z_sample_types_pct"].get("Internal solid infill", 0.0)
        br_z = au["z_sample_types_pct"].get("Internal Bridge", 0.0)
        ok = au["has_config_block_end"] and sp_all >= 20.0 and sp_z >= 25.0 and br_z == 0.0
        if not ok:
            report["all_passed"] = False
        print(
            f"  {rel_gc}: layers={au['layers']} time={au['est_time']} | "
            f"Sparse_all={sp_all}% | Z={au['z_sample_mm']:.2f}: Sparse={sp_z}%, Solid={sol_z}%, Bridge={br_z}% | ok={ok}"
        )

    rep_path = os.path.join(EXPORT_ROOT, "gcode_infill_report.json")
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved report: {rep_path} | all_passed={report['all_passed']}")
    if not report["all_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
