# OSF Preregistration Protocol

**Title**: Low-Cost FDM Fabrication of an Age-Scaled Pediatric Upper-Limb Osteology Teaching-Learning Material (TLM) Kit: Slicer Infill Ablation and Build-Orientation Validation on a Desktop CoreXY Printer  
**Authors**:
1. **Dr. Preethi L Xavier** ([LinkedIn](https://www.linkedin.com/in/preethi-l-xavier-48242b37b/)) — *Conceptualization, Anatomical & TLM Pedagogical Design* (Physician & Independent TLM Designer)
2. **Dhamodaran KKP** ([ORCID: 0009-0002-1777-0573](https://orcid.org/0009-0002-1777-0573)) — *CAD, FDM Fabrication, Slicer Ablation & Data Curation*, Ideapattrai – Makerspace, Aarvam Learning Lab (for Payir Health Initiatives / Payir Trust TLM)  
**Date Drafted**: 2026-11-25  
**Repository**: `https://github.com/dhamodharankkp-oss/payir-upper-limb-tlm-fdm`

---

## 1. Study Information

### 1.1 Background & Motivation
Hands-on anatomical Teaching-Learning Materials (TLM) are essential for community health education and primary/middle-school STEM classrooms, yet commercial pediatric osteology sets are cost-prohibitive for rural and low-resource schools served by **Payir Health Initiatives (Payir Trust)**. Desktop Fused Deposition Modeling (FDM) offers a low-cost local fabrication route at community makerspaces such as **Ideapattrai – Makerspace, Aarvam Learning Lab**, but curved organic long bones present two well-known fabrication bottlenecks:
1. Default slicer vertical-shell rules (`ensure_vertical_shell_thickness`) convert sloped bone interiors into dense internal solid infill (`>50%`), inflating print time, filament cost, and thermal warping.
2. Slender curved bones (`190–240 mm` length) exhibit poor bed-contact-to-height ratios when tilted, or require heavy support removal along anatomical condyles when printed flat.

### 1.2 Research Questions & Hypotheses
- **RQ1 (Slicer Infill Ablation)**: How does disabling `ensure_vertical_shell_thickness` and `detect_narrow_internal_solid_infill` affect the internal solid-infill fraction, sparse-infill fraction, and total filament extrusion across curved upper-limb bones?
  - **H1**: Disabling both rules reduces `Internal solid infill` extrusion fraction to `< 5%` across all 5 upper-limb bones (`scapula`, `clavicle`, `humerus`, `ulna`, `radius`) while preserving surface integrity when paired with `5` top / `4` bottom layers and `20%` gyroid infill.
- **RQ2 (Build Orientation)**: On the `240 mm` Age 8–9 wire-articulated Humerus, how do `flat45` (single-piece `45°` diagonal with `tree_slim` supports), `tilt40` (single-piece `40°` bed tilt with `8 mm` brim), and `split-pin` (`halfA` + `halfB` zero-support halves with `Ø1.85 mm` filament alignment pegs) compare on print completion rate, print time, filament mass, and dimensional accuracy?
  - **H2**: `split-pin` and `flat45` achieve higher completion reliability than `tilt40` (which fails via bed detachment due to `< 4 mm²` humeral-head contact area), while maintaining shaft/length dimensional error within `±0.5 mm`.
- **RQ3 (Classroom Wire-Tunnel Durability)**: Do modeled `Ø2.4 mm` Z-axis wire tunnels sliced with `4` wall loops (`1.68 mm` solid sleeve) allow smooth pass-through of `16–18 AWG` wire without wall cracking during classroom assembly?

---

## 2. Design Plan

### 2.1 Study Type
Engineering hardware validation & within-CAD/within-printer experimental study (computational G-code audit + physical FDM print trials).

### 2.2 Independent Variables
1. **Bone Geometry** (5 levels): `scapula`, `clavicle`, `humerus`, `ulna`, `radius`
2. **Scale / Kit Variant** (3 levels): `poster`, `1:2` desktop (`realbone_1to2`), `1:1` adult (`realbone_1to1`), plus pediatric TLM kits (`5yr_1to1`, `8to9yr_wire`)
3. **Build Orientation (Age 8–9 Humerus)** (3 levels): `flat45`, `tilt40`, `split-pin`
4. **Slicer Vertical-Shell Rule**: `sparse-optimized` (`ensure_vertical_shell_thickness = none`, `detect_narrow_internal_solid_infill = 0`) vs. baseline comparison.

### 2.3 Fixed Hardware, Software & Material Controls
- **Printer**: Creality K1 (CoreXY, Klipper firmware, `220 × 220 × 250 mm` build volume, textured PEI build plate, `0.4 mm` brass nozzle)
- **Slicer**: OrcaSlicer `2.5.1` (and Creality Print `7.x` CLI for automated G-code `;TYPE:` audit)
- **Material**: Generic `1.75 mm` PLA (white/ivory, single spool lot per replicate batch), `210 °C` nozzle, `60 °C` bed
- **Core Process Settings**: `0.16 mm` base layer height (+ documented Variable Layer Height on curved crowns), `Arachne` wall generator, `3` walls (`4` walls for wire-articulated classroom kits), `5` top / `4` bottom shell layers, `20%` gyroid infill, `60 mm/s` outer wall speed.

---

## 3. Sampling & Measurement Plan

### 3.1 Computational Audit (Completed — `v0.1.0`)
- All 17 G-code jobs (`poster`, `1:2`, `1:1`, and `5-bone` plates) parsed line-by-line for `;TYPE:` extrusion lengths and mid-plane (`Z = 4.52 mm`) cross-sections (`data/raw/gcode_infill_report.json`).
- All 7 Age 8–9 wire-articulated STLs and 5 `1:2` / `1:1` STLs verified for watertightness (`non_manifold_edges == 0`, `loose_verts == 0`, `degenerate_faces == 0`, `fits_K1 == True`).

### 3.2 Physical Replicate Protocol (`v1.0.0` Extension)
- **Sample Size**: `N = 3` physical prints per orientation (`flat45`, `tilt40`, `split-pin`) for the Age 8–9 Humerus (`9` total humerus runs) + `N = 3` runs of `plate_02_forearm_shoulder_8to9yr.stl`.
- **Measurements per Run**:
  1. `completion_status` (`complete` / `detached` / `spaghetti` / `warped`)
  2. `actual_print_time_min` (from Klipper/printer screen)
  3. `actual_mass_g` (`0.1 g` digital scale, post-support removal)
  4. `measured_length_mm`, `measured_midshaft_mm`, `measured_wire_hole_mm` (`0.01 mm` digital caliper, mean of 3 readings)
  5. `surface_finish_score` (`1–5` photographic rubric, 1 = severe underside scarring/pinholes, 5 = smooth uniform cortical finish)

---

## 4. Analysis Plan
- Reproducible Python script (`analysis/analyze_study.py`) computes descriptive statistics (mean, SD, min/max) of extrusion percentages, dimensional error (`measured - CAD`), and completion rates across orientations.
- All raw CSVs, JSONs, and generated `300 DPI` figures are archived on Zenodo with a versioned DOI linked to ORCID `0009-0002-1777-0573`.
