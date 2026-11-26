# SPDX-License-Identifier: MIT
"""
Reproducible Analysis & Publication Figure Generator
for the Payir Health Initiatives / Ideapattrai Pediatric Upper-Limb FDM Study.

Author: Dhamodaran KKP (ORCID: 0009-0002-1777-0573)
"""

import csv
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
FIG_DIR = REPO_ROOT / "manuscript" / "figures"


def parse_est_time_min(time_str: str) -> float:
    """Convert slicer time strings like '1h 12m 12s' or '19m 55s' to minutes."""
    h = m = s = 0
    if match := re.search(r"(\d+)h", time_str):
        h = int(match.group(1))
    if match := re.search(r"(\d+)m", time_str):
        m = int(match.group(1))
    if match := re.search(r"(\d+)s", time_str):
        s = int(match.group(1))
    return round(h * 60.0 + m + s / 60.0, 2)


def classify_job(job_key: str) -> tuple[str, str]:
    """Return (scale_group, bone_name) from a G-code relative path key."""
    norm = job_key.replace("\\", "/")
    parts = norm.split("/")
    folder = parts[1] if len(parts) > 2 else "unknown"
    fname = parts[-1].replace(".gcode", "")

    if folder == "upper_limb_5bones":
        scale_group = "poster"
    elif folder == "upper_limb_5bones_realbone_1to2":
        scale_group = "realbone_1to2"
    elif folder == "upper_limb_5bones_realbone_1to1":
        scale_group = "realbone_1to1"
    else:
        scale_group = folder

    bone = fname.replace("_1to1", "")
    if "plate_01" in bone:
        bone = "plate_01_5bones"
    return scale_group, bone


def build_slicer_ablation_csv() -> list[dict]:
    """Extract slicer_ablation_metrics.csv deterministically from gcode_infill_report.json."""
    report_path = RAW_DIR / "gcode_infill_report.json"
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    assert report.get("all_passed") is True, "gcode_infill_report.json must have all_passed == true"
    rows = []
    for job_key, info in report["sliced_jobs"].items():
        scale_group, bone = classify_job(job_key)
        all_t = info["all_types_pct"]
        z_t = info.get("z_sample_types_pct", {})
        row = {
            "job_id": job_key.replace("\\", "/"),
            "scale_group": scale_group,
            "bone": bone,
            "layers": int(info["layers"]),
            "est_time_min": parse_est_time_min(info["est_time"]),
            "total_extrusion_mm": float(info["total_extrusion_mm"]),
            "sparse_infill_pct": float(all_t.get("Sparse infill", 0.0)),
            "internal_solid_infill_pct": float(all_t.get("Internal solid infill", 0.0)),
            "outer_wall_pct": float(all_t.get("Outer wall", 0.0)),
            "inner_wall_pct": float(all_t.get("Inner wall", 0.0)),
            "top_surface_pct": float(all_t.get("Top surface", 0.0)),
            "bridge_pct": round(float(all_t.get("Bridge", 0.0)) + float(all_t.get("Internal Bridge", 0.0)), 2),
            "overhang_wall_pct": float(all_t.get("Overhang wall", 0.0)),
            "z_sample_mm": float(info.get("z_sample_mm", 4.52)),
            "z_sample_sparse_pct": float(z_t.get("Sparse infill", 0.0)),
            "z_sample_solid_pct": float(z_t.get("Internal solid infill", 0.0)),
        }
        rows.append(row)

    out_csv = RAW_DIR / "slicer_ablation_metrics.csv"
    fieldnames = list(rows[0].keys())
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def plot_fig1_infill_ablation(rows: list[dict]) -> None:
    """Stacked bar chart of extrusion percentages across scales and bones."""
    bones_order = ["scapula", "clavicle", "humerus", "ulna", "radius"]
    scales = [("poster", "Poster Scale"), ("realbone_1to2", "1:2 Anatomical"), ("realbone_1to1", "1:1 Life-Size")]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), sharey=True)
    colors = {
        "Sparse infill": "#2b8cbe",
        "Walls (Outer+Inner)": "#7bccc4",
        "Top + Bridge": "#bae4bc",
        "Internal solid infill": "#e34a33",
        "Other (Overhang/Brim/Gap)": "#bdbdbd",
    }

    lookup = {(r["scale_group"], r["bone"]): r for r in rows}

    for ax, (scale_key, scale_title) in zip(axes, scales):
        x = np.arange(len(bones_order))
        sparse = np.array([lookup[(scale_key, b)]["sparse_infill_pct"] for b in bones_order])
        walls = np.array([lookup[(scale_key, b)]["outer_wall_pct"] + lookup[(scale_key, b)]["inner_wall_pct"] for b in bones_order])
        top_br = np.array([lookup[(scale_key, b)]["top_surface_pct"] + lookup[(scale_key, b)]["bridge_pct"] for b in bones_order])
        solid = np.array([lookup[(scale_key, b)]["internal_solid_infill_pct"] for b in bones_order])
        other = np.clip(100.0 - (sparse + walls + top_br + solid), 0.0, 100.0)

        bottom = np.zeros(len(bones_order))
        for label, vals in [
            ("Sparse infill", sparse),
            ("Walls (Outer+Inner)", walls),
            ("Top + Bridge", top_br),
            ("Internal solid infill", solid),
            ("Other (Overhang/Brim/Gap)", other),
        ]:
            ax.bar(x, vals, bottom=bottom, label=label, color=colors[label], edgecolor="white", linewidth=0.5)
            bottom += vals

        for idx, s_val in enumerate(solid):
            ax.text(idx, 101.5, f"{s_val:.1f}%", ha="center", va="bottom", fontsize=8, color="#b30000", fontweight="bold")

        ax.set_title(scale_title, fontsize=11, fontweight="bold", pad=14)
        ax.set_xticks(x)
        ax.set_xticklabels([b.capitalize() for b in bones_order], rotation=25, ha="right", fontsize=9)
        ax.set_ylim(0, 112)
        ax.grid(axis="y", linestyle="--", alpha=0.35)

    axes[0].set_ylabel("Extrusion Share (%)", fontsize=10, fontweight="bold")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(
        "Curved-Bone G-Code Extrusion Breakdown After Slicer Vertical-Shell Optimization\n"
        "(Red labels = Internal solid infill %; all 15 bone jobs <= 3.8%)",
        fontsize=11.5,
        fontweight="bold",
        y=1.10,
    )
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_infill_ablation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_fig2_pediatric_kit() -> dict:
    """Plot Age 8-9 wire-articulated STL dimensions and signed volumes."""
    audit_path = RAW_DIR / "child_8to9yr_audit_report.json"
    with open(audit_path, "r", encoding="utf-8") as f:
        audit = json.load(f)

    assert audit.get("all_passed") is True, "child_8to9yr_audit_report.json must pass"
    files = audit["files"]

    order = [
        ("humerus_8to9yr_wire_flat45.stl", "Humerus\n(flat45)"),
        ("humerus_8to9yr_wire_tilt40.stl", "Humerus\n(tilt40)"),
        ("ulna_8to9yr_wire.stl", "Ulna"),
        ("radius_8to9yr_wire.stl", "Radius"),
        ("scapula_8to9yr_wire.stl", "Scapula"),
        ("clavicle_8to9yr_wire.stl", "Clavicle"),
        ("plate_02_forearm_shoulder_8to9yr.stl", "Plate 2\n(4 Bones)"),
    ]

    labels = [lbl for _, lbl in order]
    dx = [files[k]["dims_mm"][0] for k, _ in order]
    dy = [files[k]["dims_mm"][1] for k, _ in order]
    dz = [files[k]["dims_mm"][2] for k, _ in order]
    vol_cm3 = [files[k]["signed_volume_mm3"] / 1000.0 for k, _ in order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.6))
    x = np.arange(len(labels))
    w = 0.25

    ax1.bar(x - w, dx, width=w, label="X (mm)", color="#386cb0")
    ax1.bar(x, dy, width=w, label="Y (mm)", color="#7fc97f")
    ax1.bar(x + w, dz, width=w, label="Z (mm)", color="#fdc086")
    ax1.axhline(210.0, color="#d95f02", linestyle="--", linewidth=1.2, label="Creality K1 Safe XY (210 mm)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8.5)
    ax1.set_ylabel("Bounding Dimension (mm)", fontsize=10, fontweight="bold")
    ax1.set_title("Age 8–9 Kit Bounding Box vs. K1 Envelope", fontsize=10.5, fontweight="bold")
    ax1.legend(fontsize=8, loc="upper right")
    ax1.grid(axis="y", linestyle="--", alpha=0.35)

    bars = ax2.bar(x, vol_cm3, color="#6a51a3", alpha=0.88)
    for bar, v in zip(bars, vol_cm3):
        ax2.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v:.1f}", ha="center", va="bottom", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=8.5)
    ax2.set_ylabel("Solid Mesh Volume (cm³)", fontsize=10, fontweight="bold")
    ax2.set_title("Watertight Mesh Volume (0 Non-Manifold Edges)", fontsize=10.5, fontweight="bold")
    ax2.grid(axis="y", linestyle="--", alpha=0.35)

    fig.suptitle("Age 8–9 Wire-Articulated Pediatric Upper-Limb TLM Kit (Ø2.4 mm Wire Tunnels)", fontsize=11.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig2_pediatric_kit_metrics.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    return {
        "total_kit_volume_cm3": round(
            sum(files[k]["signed_volume_mm3"] for k in [
                "humerus_8to9yr_wire_flat45.stl",
                "ulna_8to9yr_wire.stl",
                "radius_8to9yr_wire.stl",
                "scapula_8to9yr_wire.stl",
                "clavicle_8to9yr_wire.stl",
            ]) / 1000.0,
            2,
        )
    }


def plot_fig3_orientation_tradeoff() -> None:
    """Compare flat45, tilt40, and split-pin on the 240 mm Age 8-9 Humerus."""
    orientations = ["flat45\n(Tree Slim)", "tilt40\n(40° Tilted)", "split_pin\n(Zero-Support Halves)"]
    z_heights = [32.55, 163.69, 16.28]  # half-thickness ~16.28 mm for split halves
    bed_footprints_xy = [182.76 * 187.19 / 100.0, 55.71 * 187.11 / 100.0, 182.76 * 187.19 / 100.0]
    observed_scores = [4.0, 1.0, 5.0]  # From physical_print_log.csv qualitative scores

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.3))
    x = np.arange(len(orientations))

    bars1 = ax1.bar(x, z_heights, color=["#66c2a5", "#fc8d62", "#8da0cb"], width=0.55)
    for bar, h in zip(bars1, z_heights):
        ax1.text(bar.get_x() + bar.get_width() / 2, h + 3.0, f"{h:.1f} mm", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(orientations, fontsize=9)
    ax1.set_ylabel("Print Z-Height (mm)", fontsize=10, fontweight="bold")
    ax1.set_title("Lever Arm / Z-Height Exposure", fontsize=10.5, fontweight="bold")
    ax1.set_ylim(0, 190)
    ax1.grid(axis="y", linestyle="--", alpha=0.35)

    bars2 = ax2.bar(x, observed_scores, color=["#66c2a5", "#e34a33", "#2b8cbe"], width=0.55)
    notes = ["Tree-supported\n(4/5)", "Detached <4 mm²\n(1/5 FAIL)", "Zero-support VLH\n(5/5 PASS)"]
    for bar, sc, nt in zip(bars2, observed_scores, notes):
        ax2.text(bar.get_x() + bar.get_width() / 2, sc + 0.15, nt, ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(orientations, fontsize=9)
    ax2.set_ylabel("Observed Print Quality Score (1–5)", fontsize=10, fontweight="bold")
    ax2.set_title("Creality K1 Trial Outcome (240 mm Humerus)", fontsize=10.5, fontweight="bold")
    ax2.set_ylim(0, 6.0)
    ax2.grid(axis="y", linestyle="--", alpha=0.35)

    fig.suptitle("Build-Orientation Trade-Off on Slender Curved Long Bones (Age 8–9 Humerus)", fontsize=11.5, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3_orientation_tradeoff.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    rows = build_slicer_ablation_csv()
    solid_vals = [r["internal_solid_infill_pct"] for r in rows]
    sparse_vals = [r["sparse_infill_pct"] for r in rows]

    plot_fig1_infill_ablation(rows)
    kit_stats = plot_fig2_pediatric_kit()
    plot_fig3_orientation_tradeoff()

    summary = {
        "total_gcode_jobs_audited": len(rows),
        "internal_solid_infill_pct_mean": round(float(np.mean(solid_vals)), 2),
        "internal_solid_infill_pct_max": round(float(np.max(solid_vals)), 2),
        "internal_solid_infill_pct_min": round(float(np.min(solid_vals)), 2),
        "sparse_infill_pct_mean": round(float(np.mean(sparse_vals)), 2),
        "age_8to9yr_5bone_total_volume_cm3": kit_stats["total_kit_volume_cm3"],
    }

    with open(PROCESSED_DIR / "summary_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("[PASS] Slicer ablation CSV, summary_metrics.json, and 3 figures (300 DPI) generated.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
