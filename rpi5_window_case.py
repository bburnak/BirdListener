"""
Raspberry Pi 5 Window-Mount Case — Blender Python Generator
============================================================
Usage:  Open Blender → Scripting tab → Open this file → Run Script
        The case model will appear in the 3D viewport.

Design: A 3D-printable case that suction-cup-mounts to a window.
        Two Pi Camera Module 2 boards face outward through the glass
        toward a bird feeder.  The Pi 5 sits inside, accessible from
        the room side.  An optional mesh grille covers the open top.

Author: Auto-generated parametric design
Date:   2026-03-16
"""

import bpy
import bmesh
import math
from mathutils import Vector

# ──────────────────────────────────────────────────────────────────────
# 0.  PARAMETRIC CONSTANTS  (all dimensions in mm)
# ──────────────────────────────────────────────────────────────────────

# --- Raspberry Pi 5 board ---
PI_BOARD_W       = 85.0    # width  (X)
PI_BOARD_H       = 56.0    # height (Y)
PI_BOARD_T       = 1.4     # PCB thickness
PI_MOUNT_HOLE_D  = 2.7     # M2.5 through-hole diameter
PI_MOUNT_RECT_W  = 58.0    # mounting-hole rectangle width
PI_MOUNT_RECT_H  = 49.0    # mounting-hole rectangle height
PI_MOUNT_OFFSET  = 3.5     # hole centre offset from board edge
PI_MAX_COMP_H    = 20.0    # tallest component above PCB bottom

# --- Pi Camera Module 2 ---
CAM_BOARD_W      = 25.0    # width  (X)
CAM_BOARD_H      = 24.0    # height (Y)
CAM_BOARD_T      = 1.0     # PCB thickness
CAM_TOTAL_H      = 9.0     # board + lens module height
CAM_MOUNT_RECT_W = 21.0    # mounting-hole rectangle width
CAM_MOUNT_RECT_H = 12.5    # mounting-hole rectangle height
CAM_MOUNT_HOLE_D = 2.0     # M2 hole diameter
CAM_LENS_D       = 8.0     # lens module diameter (square, but we use ⌀ for cutout)
CAM_SPACING      = 30.0    # centre-to-centre distance between two cameras (X)

# --- Suction cups ---
SC_COUNT         = 4
SC_STEM_D        = 6.0     # M6 threaded-stem inner diameter
SC_BOSS_OD       = 12.0    # boss outer diameter
SC_BOSS_H        = 5.0     # boss protrusion height
SC_INSET         = 10.0    # boss centre inset from case edge

# --- Case geometry ---
WALL_T           = 3.0     # wall / back-plate thickness
CASE_DEPTH       = 38.0    # total depth from back plate to mesh top (Z into room)
CASE_PAD         = 4.0     # padding around Pi board on each side
CASE_W           = PI_BOARD_W + 2 * CASE_PAD  # external width  (X) → 93
CASE_H           = PI_BOARD_H + 2 * CASE_PAD  # external height (Y) → 64 (slightly adjusted)

# --- Pi standoffs (interior, from back plate inner face) ---
PI_STANDOFF_H    = 14.0    # height from back-plate interior → gives clearance over camera (9 mm) + ribbon
PI_STANDOFF_OD   = 6.0     # outer diameter
PI_STANDOFF_ID   = 3.8     # hole for M2.5 heat-set insert

# --- Camera standoffs ---
CAM_STANDOFF_H   = 3.0     # short posts to hold camera board off back plate
CAM_STANDOFF_OD  = 4.5     # outer diameter
CAM_STANDOFF_ID  = 2.0     # M2 hole

# --- Connector cutouts (approximate, on side walls) ---
# Right wall (USB / Ethernet side when Pi GPIO is along top)
USB_A_CUTOUT_W   = 16.0    # width of dual USB-A opening
USB_A_CUTOUT_H   = 16.0    # height
ETH_CUTOUT_W     = 16.5
ETH_CUTOUT_H     = 14.0

# Left wall (power / HDMI / SD)
USBC_CUTOUT_W    = 10.0
USBC_CUTOUT_H    = 4.0
HDMI_CUTOUT_W    = 8.0
HDMI_CUTOUT_H    = 4.0
HDMI_SPACING     = 14.0    # centre-to-centre of two micro-HDMI
SD_CUTOUT_W      = 14.0
SD_CUTOUT_H      = 3.0

# Ribbon cable slots in bottom wall
RIBBON_SLOT_W    = 17.0
RIBBON_SLOT_H    = 3.0

# --- Mesh grille ---
MESH_HOLE_D      = 3.0
MESH_PITCH       = 5.5     # centre-to-centre
MESH_T           = 2.0     # grille thickness
SNAP_TAB_W       = 8.0
SNAP_TAB_D       = 1.5     # depth of snap tab overhang
SNAP_TAB_H       = 3.0     # height

# --- Tolerances ---
FIT_TOL          = 0.3     # press-fit tolerance

# ──────────────────────────────────────────────────────────────────────
# 1.  HELPERS
# ──────────────────────────────────────────────────────────────────────

def clear_scene():
    """Remove all mesh objects so re-running the script is clean."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in bpy.data.collections:
        if col.name != "Scene Collection" and not col.users:
            bpy.data.collections.remove(col)

def new_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col

def set_active(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

def add_box(name, size, location, collection=None):
    """Add a box mesh (size = (x, y, z)) centred at location."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(scale=True)
    if collection:
        # move from default to target collection
        for c in obj.users_collection:
            c.objects.unlink(obj)
        collection.objects.link(obj)
    return obj

def add_cylinder(name, radius, depth, location, vertices=64, collection=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    if collection:
        for c in obj.users_collection:
            c.objects.unlink(obj)
        collection.objects.link(obj)
    return obj

def bool_op(target, tool, operation='DIFFERENCE'):
    """Apply a boolean modifier and delete the tool object."""
    mod = target.modifiers.new(name=f"Bool_{tool.name}", type='BOOLEAN')
    mod.operation = operation
    mod.object = tool
    mod.solver = 'FAST'
    set_active(target)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)

def mm(val):
    """Convert mm to Blender units (we work in mm — set scene unit scale)."""
    return val  # 1 BU = 1 mm when scene unit scale = 0.001


# ──────────────────────────────────────────────────────────────────────
# 2.  SCENE SETUP
# ──────────────────────────────────────────────────────────────────────

clear_scene()

# Set scene to metric millimetres
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
bpy.context.scene.unit_settings.length_unit = 'MILLIMETERS'

col_case  = new_collection("Case_Body")
col_mesh  = new_collection("Mesh_Grille")

# Coordinate system:
#   X → case width  (left-right when facing the window)
#   Y → case height (up-down)
#   Z → depth into room (Z=0 = outer back-plate face against glass,
#                          Z=CASE_DEPTH = room-facing open top)

# ──────────────────────────────────────────────────────────────────────
# 3.  BACK PLATE  (the slab that sits against the window)
# ──────────────────────────────────────────────────────────────────────

bp = add_box(
    "BackPlate",
    size=(CASE_W, CASE_H, WALL_T),
    location=(CASE_W / 2, CASE_H / 2, WALL_T / 2),
    collection=col_case,
)

# ──────────────────────────────────────────────────────────────────────
# 4.  SUCTION-CUP BOSSES  (exterior — negative Z side of back plate)
# ──────────────────────────────────────────────────────────────────────

sc_positions = [
    (SC_INSET,            SC_INSET,            -SC_BOSS_H / 2),
    (CASE_W - SC_INSET,   SC_INSET,            -SC_BOSS_H / 2),
    (SC_INSET,            CASE_H - SC_INSET,   -SC_BOSS_H / 2),
    (CASE_W - SC_INSET,   CASE_H - SC_INSET,   -SC_BOSS_H / 2),
]

for i, pos in enumerate(sc_positions):
    boss = add_cylinder(f"SC_Boss_{i}", SC_BOSS_OD / 2, SC_BOSS_H, pos, collection=col_case)
    # Union boss to back plate
    bool_op(bp, boss, 'UNION')

    # Cut the M6 through-hole (goes through boss + back plate)
    hole = add_cylinder(
        f"SC_Hole_{i}", SC_STEM_D / 2, SC_BOSS_H + WALL_T + 2,
        (pos[0], pos[1], -SC_BOSS_H / 2),
        collection=col_case,
    )
    bool_op(bp, hole, 'DIFFERENCE')

# ──────────────────────────────────────────────────────────────────────
# 5.  CAMERA LENS CUTOUTS  (two circular holes through back plate)
# ──────────────────────────────────────────────────────────────────────

# Cameras centred horizontally, placed in lower half of case to stay
# close to the Pi's CSI connectors (bottom edge of the board).
cam_centre_y = CASE_H * 0.35   # slightly below centre
cam_cx_left  = CASE_W / 2 - CAM_SPACING / 2
cam_cx_right = CASE_W / 2 + CAM_SPACING / 2

lens_cutout_r = (CAM_LENS_D + 2) / 2  # 1 mm clearance ring

for cx in (cam_cx_left, cam_cx_right):
    cutter = add_cylinder(
        "LensCut", lens_cutout_r, WALL_T + 2,
        (cx, cam_centre_y, WALL_T / 2),
        collection=col_case,
    )
    # Rotate cylinder so it cuts along Z
    bool_op(bp, cutter, 'DIFFERENCE')

# ──────────────────────────────────────────────────────────────────────
# 6.  CAMERA MODULE 2 STANDOFFS  (interior of back plate)
# ──────────────────────────────────────────────────────────────────────

def add_cam_standoffs(cx, cy, tag):
    """Add 4 standoff posts for one Camera Module 2 at (cx, cy)."""
    half_w = CAM_MOUNT_RECT_W / 2
    half_h = CAM_MOUNT_RECT_H / 2
    for j, (dx, dy) in enumerate([(-half_w, -half_h), (half_w, -half_h),
                                   (-half_w,  half_h), (half_w,  half_h)]):
        px, py = cx + dx, cy + dy
        pz = WALL_T + CAM_STANDOFF_H / 2
        post = add_cylinder(f"CamPost_{tag}_{j}", CAM_STANDOFF_OD / 2, CAM_STANDOFF_H, (px, py, pz), collection=col_case)
        bool_op(bp, post, 'UNION')
        # Screw hole
        hole = add_cylinder(f"CamHole_{tag}_{j}", CAM_STANDOFF_ID / 2, CAM_STANDOFF_H + 2, (px, py, pz), collection=col_case)
        bool_op(bp, hole, 'DIFFERENCE')

add_cam_standoffs(cam_cx_left,  cam_centre_y, "L")
add_cam_standoffs(cam_cx_right, cam_centre_y, "R")

# ──────────────────────────────────────────────────────────────────────
# 7.  RASPBERRY PI 5 STANDOFFS
# ──────────────────────────────────────────────────────────────────────

# Pi board origin (lower-left corner) relative to case interior
pi_origin_x = (CASE_W - PI_BOARD_W) / 2   # centred in X
pi_origin_y = (CASE_H - PI_BOARD_H) / 2   # centred in Y

pi_hole_positions = [
    (pi_origin_x + PI_MOUNT_OFFSET,                    pi_origin_y + PI_MOUNT_OFFSET),
    (pi_origin_x + PI_MOUNT_OFFSET + PI_MOUNT_RECT_W,  pi_origin_y + PI_MOUNT_OFFSET),
    (pi_origin_x + PI_MOUNT_OFFSET,                    pi_origin_y + PI_MOUNT_OFFSET + PI_MOUNT_RECT_H),
    (pi_origin_x + PI_MOUNT_OFFSET + PI_MOUNT_RECT_W,  pi_origin_y + PI_MOUNT_OFFSET + PI_MOUNT_RECT_H),
]

for i, (hx, hy) in enumerate(pi_hole_positions):
    pz = WALL_T + PI_STANDOFF_H / 2
    post = add_cylinder(f"PiPost_{i}", PI_STANDOFF_OD / 2, PI_STANDOFF_H, (hx, hy, pz), collection=col_case)
    bool_op(bp, post, 'UNION')
    hole = add_cylinder(f"PiHole_{i}", PI_STANDOFF_ID / 2, PI_STANDOFF_H + 2, (hx, hy, pz), collection=col_case)
    bool_op(bp, hole, 'DIFFERENCE')

# ──────────────────────────────────────────────────────────────────────
# 8.  SIDE WALLS
# ──────────────────────────────────────────────────────────────────────

inner_depth = CASE_DEPTH - WALL_T  # wall height from top of back plate to open face

# Bottom wall (Y = 0 face)
wall_bottom = add_box(
    "Wall_Bottom",
    size=(CASE_W, WALL_T, inner_depth),
    location=(CASE_W / 2, WALL_T / 2, WALL_T + inner_depth / 2),
    collection=col_case,
)
bool_op(bp, wall_bottom, 'UNION')

# Top wall (Y = CASE_H face)
wall_top = add_box(
    "Wall_Top",
    size=(CASE_W, WALL_T, inner_depth),
    location=(CASE_W / 2, CASE_H - WALL_T / 2, WALL_T + inner_depth / 2),
    collection=col_case,
)
bool_op(bp, wall_top, 'UNION')

# Left wall (X = 0 face)  — Power / HDMI / SD side
wall_left = add_box(
    "Wall_Left",
    size=(WALL_T, CASE_H - 2 * WALL_T, inner_depth),
    location=(WALL_T / 2, CASE_H / 2, WALL_T + inner_depth / 2),
    collection=col_case,
)
bool_op(bp, wall_left, 'UNION')

# Right wall (X = CASE_W face) — USB-A / Ethernet side
wall_right = add_box(
    "Wall_Right",
    size=(WALL_T, CASE_H - 2 * WALL_T, inner_depth),
    location=(CASE_W - WALL_T / 2, CASE_H / 2, WALL_T + inner_depth / 2),
    collection=col_case,
)
bool_op(bp, wall_right, 'UNION')

# ──────────────────────────────────────────────────────────────────────
# 9.  CONNECTOR CUTOUTS IN SIDE WALLS
# ──────────────────────────────────────────────────────────────────────

# Pi board sits at Z = WALL_T + PI_STANDOFF_H  (bottom of PCB)
pi_pcb_z = WALL_T + PI_STANDOFF_H

# --- Right wall cutouts (X = CASE_W) : USB-A stack + Ethernet ---
# USB-A ports on Pi 5 are at the "right edge" when GPIO is along top.
# Two stacked dual-USB ports sit roughly in the upper portion.
# Vertical positions are relative to the PCB bottom.

# USB-A top stack (USB 3.0)
usb3_cy = pi_origin_y + PI_BOARD_H - 11.0   # ~11 mm from top edge of board
usb3_cz = pi_pcb_z + 8.0                     # centre of USB-A connector above PCB
usb3_cut = add_box(
    "USB3_Cut",
    size=(WALL_T + 2, USB_A_CUTOUT_W, USB_A_CUTOUT_H),
    location=(CASE_W - WALL_T / 2, usb3_cy, usb3_cz),
    collection=col_case,
)
bool_op(bp, usb3_cut, 'DIFFERENCE')

# USB-A bottom stack (USB 2.0)
usb2_cy = pi_origin_y + PI_BOARD_H - 29.0
usb2_cz = pi_pcb_z + 8.0
usb2_cut = add_box(
    "USB2_Cut",
    size=(WALL_T + 2, USB_A_CUTOUT_W, USB_A_CUTOUT_H),
    location=(CASE_W - WALL_T / 2, usb2_cy, usb2_cz),
    collection=col_case,
)
bool_op(bp, usb2_cut, 'DIFFERENCE')

# Ethernet
eth_cy = pi_origin_y + PI_BOARD_H - 45.5
eth_cz = pi_pcb_z + 7.0
eth_cut = add_box(
    "Eth_Cut",
    size=(WALL_T + 2, ETH_CUTOUT_W, ETH_CUTOUT_H),
    location=(CASE_W - WALL_T / 2, eth_cy, eth_cz),
    collection=col_case,
)
bool_op(bp, eth_cut, 'DIFFERENCE')

# --- Left wall cutouts (X = 0) : USB-C power, 2× micro-HDMI, microSD ---

# USB-C power (bottom-left corner of board)
usbc_cy = pi_origin_y + 8.0
usbc_cz = pi_pcb_z + 2.0
usbc_cut = add_box(
    "USBC_Cut",
    size=(WALL_T + 2, USBC_CUTOUT_W, USBC_CUTOUT_H),
    location=(WALL_T / 2, usbc_cy, usbc_cz),
    collection=col_case,
)
bool_op(bp, usbc_cut, 'DIFFERENCE')

# Micro-HDMI 0 (left-most, near USB-C)
hdmi0_cy = pi_origin_y + 21.0
hdmi0_cz = pi_pcb_z + 2.0
hdmi0_cut = add_box(
    "HDMI0_Cut",
    size=(WALL_T + 2, HDMI_CUTOUT_W, HDMI_CUTOUT_H),
    location=(WALL_T / 2, hdmi0_cy, hdmi0_cz),
    collection=col_case,
)
bool_op(bp, hdmi0_cut, 'DIFFERENCE')

# Micro-HDMI 1
hdmi1_cy = hdmi0_cy + HDMI_SPACING
hdmi1_cz = pi_pcb_z + 2.0
hdmi1_cut = add_box(
    "HDMI1_Cut",
    size=(WALL_T + 2, HDMI_CUTOUT_W, HDMI_CUTOUT_H),
    location=(WALL_T / 2, hdmi1_cy, hdmi1_cz),
    collection=col_case,
)
bool_op(bp, hdmi1_cut, 'DIFFERENCE')

# microSD slot (bottom edge of board, left side)
sd_cy = pi_origin_y + 2.0
sd_cz = pi_pcb_z - 1.0  # SD slot is slightly below PCB centre plane
sd_cut = add_box(
    "SD_Cut",
    size=(WALL_T + 2, SD_CUTOUT_W, SD_CUTOUT_H),
    location=(WALL_T / 2, sd_cy, sd_cz),
    collection=col_case,
)
bool_op(bp, sd_cut, 'DIFFERENCE')

# --- Bottom wall: ribbon cable pass-through slots ---
# Two slots for the Standard-to-Mini FPC cables from cameras to Pi CSI ports.
# Pi 5 CSI connectors are on the bottom edge of the board.

ribbon_z = pi_pcb_z + 1.5  # just above PCB for cable clearance

# CSI 0 (left connector)
rib0_cx = pi_origin_x + 23.0  # approx position of CAM0 connector
rib0_cut = add_box(
    "Ribbon0_Cut",
    size=(RIBBON_SLOT_W, WALL_T + 2, RIBBON_SLOT_H),
    location=(rib0_cx, WALL_T / 2, ribbon_z),
    collection=col_case,
)
bool_op(bp, rib0_cut, 'DIFFERENCE')

# CSI 1 (right connector)
rib1_cx = pi_origin_x + 45.0
rib1_cut = add_box(
    "Ribbon1_Cut",
    size=(RIBBON_SLOT_W, WALL_T + 2, RIBBON_SLOT_H),
    location=(rib1_cx, WALL_T / 2, ribbon_z),
    collection=col_case,
)
bool_op(bp, rib1_cut, 'DIFFERENCE')

# --- Top wall: GPIO access slot ---
gpio_cx = pi_origin_x + PI_BOARD_W - 3.5 - 25.4  # GPIO header ~25.4 mm from right edge
gpio_cut = add_box(
    "GPIO_Cut",
    size=(52.0, WALL_T + 2, 8.0),
    location=(CASE_W / 2, CASE_H - WALL_T / 2, pi_pcb_z + 5.0),
    collection=col_case,
)
bool_op(bp, gpio_cut, 'DIFFERENCE')

# ──────────────────────────────────────────────────────────────────────
# 10.  CABLE ROUTING CHANNELS  (shallow grooves on back-plate interior)
# ──────────────────────────────────────────────────────────────────────

# Each channel runs from camera position down to the bottom wall
# where the ribbon slots are.  We model them as shallow rectangular
# subtractions from the back-plate interior surface.

channel_depth = 2.0   # how deep into the back plate
channel_w     = 17.0  # ribbon width

for cam_cx, rib_cx in [(cam_cx_left, rib0_cx), (cam_cx_right, rib1_cx)]:
    # Vertical segment: from camera Y down to bottom wall
    seg_h = cam_centre_y - WALL_T - CAM_MOUNT_RECT_H / 2
    if seg_h > 0:
        chan = add_box(
            "CableChannel",
            size=(channel_w, seg_h, channel_depth),
            location=(cam_cx, WALL_T + seg_h / 2, WALL_T + channel_depth / 2),
            collection=col_case,
        )
        bool_op(bp, chan, 'DIFFERENCE')

    # Small horizontal jog if camera X ≠ ribbon X
    jog_len = abs(cam_cx - rib_cx)
    if jog_len > 1:
        mid_x = (cam_cx + rib_cx) / 2
        jog = add_box(
            "CableJog",
            size=(jog_len + channel_w, channel_w, channel_depth),
            location=(mid_x, WALL_T + 4.0, WALL_T + channel_depth / 2),
            collection=col_case,
        )
        bool_op(bp, jog, 'DIFFERENCE')

# ──────────────────────────────────────────────────────────────────────
# 11.  VENTILATION HOLES IN SIDE WALLS
# ──────────────────────────────────────────────────────────────────────

# Add a row of small vent holes to the left and right walls for airflow.
vent_d = 3.0
vent_spacing = 7.0
vent_z_start = WALL_T + inner_depth * 0.4
vent_z_end   = WALL_T + inner_depth * 0.85

for vy in [CASE_H * 0.3, CASE_H * 0.5, CASE_H * 0.7]:
    vz = vent_z_start
    while vz < vent_z_end:
        # Right wall vent
        rv = add_cylinder("VentR", vent_d / 2, WALL_T + 2, (CASE_W - WALL_T / 2, vy, vz), vertices=16, collection=col_case)
        # Rotate to punch through X-facing wall
        rv.rotation_euler = (0, math.radians(90), 0)
        bpy.context.view_layer.update()
        bool_op(bp, rv, 'DIFFERENCE')

        # Left wall vent
        lv = add_cylinder("VentL", vent_d / 2, WALL_T + 2, (WALL_T / 2, vy, vz), vertices=16, collection=col_case)
        lv.rotation_euler = (0, math.radians(90), 0)
        bpy.context.view_layer.update()
        bool_op(bp, lv, 'DIFFERENCE')

        vz += vent_spacing

# ──────────────────────────────────────────────────────────────────────
# 12.  MESH GRILLE  (room-facing cover — separate object)
# ──────────────────────────────────────────────────────────────────────

# Solid panel
grille_inner_w = CASE_W - 2 * WALL_T + 2 * FIT_TOL
grille_inner_h = CASE_H - 2 * WALL_T + 2 * FIT_TOL
grille_z = CASE_DEPTH + MESH_T / 2

grille = add_box(
    "MeshGrille",
    size=(CASE_W, CASE_H, MESH_T),
    location=(CASE_W / 2, CASE_H / 2, grille_z),
    collection=col_mesh,
)

# Punch ventilation holes in a grid pattern
margin = 6.0  # keep solid border
x_start = margin
y_start = margin
x_end = CASE_W - margin
y_end = CASE_H - margin

gx = x_start
while gx < x_end:
    gy = y_start
    while gy < y_end:
        gh = add_cylinder(
            "GrillHole", MESH_HOLE_D / 2, MESH_T + 2,
            (gx, gy, grille_z),
            vertices=6,  # hexagonal holes for aesthetics
            collection=col_mesh,
        )
        bool_op(grille, gh, 'DIFFERENCE')
        gy += MESH_PITCH
    gx += MESH_PITCH

# Add snap-fit tabs on edges of grille (small protrusions that hook inside walls)
tab_positions = [
    # (x, y, rotation_z) — on each edge, midpoint
    (CASE_W / 2,  WALL_T / 2,       0),            # bottom edge
    (CASE_W / 2,  CASE_H - WALL_T / 2, 0),         # top edge
    (WALL_T / 2,       CASE_H / 2,  math.radians(90)),  # left edge
    (CASE_W - WALL_T / 2, CASE_H / 2, math.radians(90)),  # right edge
]

for tx, ty, tr in tab_positions:
    tab = add_box(
        "SnapTab",
        size=(SNAP_TAB_W, SNAP_TAB_D, SNAP_TAB_H),
        location=(tx, ty, CASE_DEPTH - SNAP_TAB_H / 2),
        collection=col_mesh,
    )
    if tr != 0:
        tab.rotation_euler = (0, 0, tr)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        set_active(tab)
        bpy.ops.object.transform_apply(rotation=True)
    bool_op(grille, tab, 'UNION')

# ──────────────────────────────────────────────────────────────────────
# 13.  INTERNAL LEDGE FOR GRILLE  (snap-tab receivers)
# ──────────────────────────────────────────────────────────────────────

# Small inward ledge at the top of each wall for the grille to rest on
ledge_depth  = 1.5
ledge_height = MESH_T + 0.5  # slightly taller than grille thickness

for side in ['bottom', 'top', 'left', 'right']:
    if side == 'bottom':
        lx, ly = CASE_W / 2, WALL_T + ledge_depth / 2
        lw, lh = CASE_W - 2 * WALL_T, ledge_depth
    elif side == 'top':
        lx, ly = CASE_W / 2, CASE_H - WALL_T - ledge_depth / 2
        lw, lh = CASE_W - 2 * WALL_T, ledge_depth
    elif side == 'left':
        lx, ly = WALL_T + ledge_depth / 2, CASE_H / 2
        lw, lh = ledge_depth, CASE_H - 2 * WALL_T
    else:  # right
        lx, ly = CASE_W - WALL_T - ledge_depth / 2, CASE_H / 2
        lw, lh = ledge_depth, CASE_H - 2 * WALL_T

    lz = CASE_DEPTH - ledge_height / 2
    ledge = add_box(
        f"Ledge_{side}",
        size=(lw, lh, ledge_height),
        location=(lx, ly, lz),
        collection=col_case,
    )
    bool_op(bp, ledge, 'UNION')

# ──────────────────────────────────────────────────────────────────────
# 14.  FINAL CLEANUP & ORIGIN
# ──────────────────────────────────────────────────────────────────────

# Set origins to geometry centre
for obj in list(col_case.objects) + list(col_mesh.objects):
    bpy.ops.object.select_all(action='DESELECT')
    set_active(obj)
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

# Select the case body
bpy.ops.object.select_all(action='DESELECT')
set_active(bp)

# Zoom viewport to fit
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for region in area.regions:
            if region.type == 'WINDOW':
                with bpy.context.temp_override(area=area, region=region):
                    bpy.ops.view3d.view_all()
                break

# ──────────────────────────────────────────────────────────────────────
# 15.  OPTIONAL STL EXPORT
# ──────────────────────────────────────────────────────────────────────

def export_stl(filepath: str = "//rpi5_window_case.stl", selection_only: bool = False):
    """
    Export the case to STL.  Call from Blender's Python console:
        import rpi5_window_case
        rpi5_window_case.export_stl()
    Or just run:  bpy.ops.wm.stl_export(filepath=...)
    """
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.wm.stl_export(
        filepath=bpy.path.abspath(filepath),
        export_selected_objects=selection_only,
        global_scale=1.0,
        ascii_format=False,
    )
    print(f"Exported STL to {filepath}")


print("=" * 60)
print("  RPi 5 Window-Mount Case generated successfully!")
print(f"  Case outer dimensions: {CASE_W:.0f} × {CASE_H:.0f} × {CASE_DEPTH:.0f} mm")
print(f"  Two Camera Module 2 mounts (side-by-side, {CAM_SPACING:.0f} mm apart)")
print(f"  4 × 40 mm suction cup mounts (M6 through-hole)")
print(f"  Open top with snap-fit mesh grille")
print("  ")
print("  To export STL, run in Blender console:")
print("    exec(open('rpi5_window_case.py').read()); export_stl()")
print("=" * 60)
