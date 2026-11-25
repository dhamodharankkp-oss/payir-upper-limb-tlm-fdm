"""
Configuration and Creality K1 Constraints for the 5 Individual Upper-Limb &
Shoulder-Girdle Bones (scapula, clavicle, humerus, ulna, radius).

Coordinate Convention (Blender Metric Millimeters, scale_length = 0.001):
  +X : Anatomical Right in the reference lineup (left-to-right: SCAPULA -> RADIUS)
  -X : Anatomical Left in the reference lineup
  -Y : Anterior / Camera-facing side in the front studio lineup
  +Y : Posterior / Back side
  +Z : Superior (Up), baseline near Z = 6.0 mm in lineup, Z = 0.0 mm on K1 print bed
"""

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = r"e:\AG\Blender"
SCRIPTS_DIR = r"e:\AG\Blender\scripts\upper_limb_5bones"
SKELETON_SCRIPTS_DIR = r"e:\AG\Blender\scripts\skeleton"
EXPORTS_DIR = r"e:\AG\Blender\exports\upper_limb_5bones"
PARTS_DIR = r"e:\AG\Blender\exports\upper_limb_5bones\parts"
PLATES_DIR = r"e:\AG\Blender\exports\upper_limb_5bones\plates"
GCODE_DIR = r"e:\AG\Blender\gcode\upper_limb_5bones"
RENDERS_DIR = r"e:\AG\Blender\renders"
MASTER_BLEND_PATH = r"e:\AG\Blender\upper_limb_5bones_master.blend"

# ---------------------------------------------------------------------------
# Creality K1 Printer Constraints (mm)
# ---------------------------------------------------------------------------
K1_BED_X_MM = 220.0
K1_BED_Y_MM = 220.0
K1_MAX_Z_MM = 250.0

SAFE_X_MM = 210.0
SAFE_Y_MM = 210.0
SAFE_Z_MM = 240.0

NOZZLE_DIAMETER_MM = 0.4
LAYER_HEIGHT_MM = 0.16

# ---------------------------------------------------------------------------
# Canonical 5 Individual Bone Parts
# ---------------------------------------------------------------------------
PART_NAMES = [
    "scapula",
    "clavicle",
    "humerus",
    "ulna",
    "radius",
]

# Lineup X centers (mm) matching the 5-bone reference image from left to right
LINEUP_X = {
    "scapula": -112.0,
    "clavicle": -50.0,
    "humerus": 0.0,
    "ulna": 48.0,
    "radius": 94.0,
}

# Optimal Creality K1 print orientations (Euler XYZ in degrees) to lay each bone
# flat on Z = 0.0 mm for stable horizontal FDM printing (no tall cantilevers).
PRINT_ORIENTATIONS_DEG = {
    "scapula": (-90.0, 0.0, 0.0),
    "clavicle": (-90.0, 0.0, 0.0),
    "humerus": (-90.0, 0.0, 0.0),
    "ulna": (-90.0, 0.0, 0.0),
    "radius": (-90.0, 0.0, 0.0),
}
