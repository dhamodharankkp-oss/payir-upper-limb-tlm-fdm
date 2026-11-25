# Data Dictionary

All tabular datasets are stored in UTF-8 CSV format under `data/raw/` and `data/processed/`.

---

## 1. `data/raw/slicer_ablation_metrics.csv`
Derived deterministically from `data/raw/gcode_infill_report.json` (Creality Print CLI `;TYPE:` extrusion audit).

| Column | Type | Unit | Description |
| --- | --- | --- | --- |
| `job_id` | string | — | Relative G-code path identifier |
| `scale_group` | string | — | `poster`, `realbone_1to2`, or `realbone_1to1` |
| `bone` | string | — | `scapula`, `clavicle`, `humerus`, `ulna`, `radius`, or `plate_01_5bones` |
| `layers` | integer | count | Total sliced layers |
| `est_time_min` | float | min | Slicer-estimated print duration |
| `total_extrusion_mm` | float | mm | Total filament extruded |
| `sparse_infill_pct` | float | % | Percentage of total extrusion classified as `Sparse infill` |
| `internal_solid_infill_pct` | float | % | Percentage classified as `Internal solid infill` |
| `outer_wall_pct` | float | % | Percentage classified as `Outer wall` |
| `inner_wall_pct` | float | % | Percentage classified as `Inner wall` |
| `top_surface_pct` | float | % | Percentage classified as `Top surface` |
| `bridge_pct` | float | % | Combined `Bridge` + `Internal Bridge` extrusion percentage |
| `overhang_wall_pct` | float | % | Percentage classified as `Overhang wall` |
| `z_sample_mm` | float | mm | Mid-shaft cross-section Z height (`4.52 mm`) |
| `z_sample_sparse_pct` | float | % | `Sparse infill` % at `Z = 4.52 mm` |
| `z_sample_solid_pct` | float | % | `Internal solid infill` % at `Z = 4.52 mm` |

---

## 2. `data/raw/physical_print_log.csv`
Physical Creality K1 print trials conducted at **Ideapattrai – Makerspace, Aarvam Learning Lab** for **Payir Health Initiatives (Payir Trust)**.

| Column | Type | Unit | Description |
| --- | --- | --- | --- |
| `run_id` | string | — | Unique trial identifier (e.g., `K1-2026-001`) |
| `date` | ISO-8601 | YYYY-MM-DD | Date of print |
| `part_name` | string | — | STL/plate name |
| `scale_group` | string | — | `realbone_1to2`, `child_5yr`, `child_8to9yr` |
| `orientation` | string | — | `flat0`, `flat45`, `tilt40`, `split_pin` |
| `slicer_profile` | string | — | OrcaSlicer `2.5.1` process preset name |
| `wall_loops` | integer | count | Perimeter wall count |
| `layer_height_mm` | float | mm | Base layer height (note `VLH` if variable layer height enabled) |
| `bed_contact_note` | string | — | Bed adhesion / contact geometry observation |
| `completion_status` | string | — | `complete`, `detached`, `spaghetti`, `aborted`, or `pending` |
| `actual_time_min` | float | min | Measured print duration (blank if `pending`/failed early) |
| `actual_mass_g` | float | g | Post-support mass on `0.1 g` scale |
| `cad_length_mm` | float | mm | Nominal CAD bounding length |
| `measured_length_mm` | float | mm | Caliper-measured length (`0.01 mm`) |
| `measured_wire_hole_mm` | float | mm | Caliper-measured `Ø2.4 mm` tunnel clearance |
| `surface_finish_score` | integer | 1–5 | Visual/tactile finish score (`1` poor, `5` clean) |
| `notes` | string | — | Failure mode or qualitative observation |
