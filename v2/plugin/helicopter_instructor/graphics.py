"""3D OBJ8 and PNG texture assets manager for Helicopter Flight Instructor."""

import math
import os
import shutil
import struct
import zlib

# pyrefly: ignore [missing-import]
import xp

from helicopter_instructor.envelope_limits import (
    LIMIT_DRIFT_GREEN_M,
    LIMIT_DRIFT_ORANGE_M,
    LIMIT_DRIFT_RED_M,
)


def generate_solid_png(filepath, r, g, b, alpha):
    """Generates a valid 2x2 RGBA PNG file programmatically.

    Args:
        filepath: The destination path for the PNG file.
        r: Red color component float [0.0, 1.0].
        g: Green color component float [0.0, 1.0].
        b: Blue color component float [0.0, 1.0].
        alpha: Alpha color component float [0.0, 1.0].
    """
    # PNG 8-byte signature
    png = bytearray([137, 80, 78, 71, 13, 10, 26, 10])

    def make_chunk(tag, data):
        length = struct.pack("!I", len(data))
        checksum = struct.pack("!I", zlib.crc32(tag + data))
        return length + tag + data + checksum

    # IHDR chunk: Width (2), Height (2), Bit depth (8),
    # Color type (6 = RGBA), Compression (0), Filter (0), Interlace (0)
    ihdr_data = struct.pack("!IIBBBBB", 2, 2, 8, 6, 0, 0, 0)
    png.extend(make_chunk(b"IHDR", ihdr_data))

    # IDAT chunk: raw image data with filter byte (0) before each scanline
    r_val = int(max(0, min(255, r * 255)))
    g_val = int(max(0, min(255, g * 255)))
    b_val = int(max(0, min(255, b * 255)))
    a_val = int(max(0, min(255, alpha * 255)))
    pixel = struct.pack("BBBB", r_val, g_val, b_val, a_val)

    # 2 rows of scanline: Filter byte + 2 pixels
    scanline = b"\x00" + pixel + pixel
    raw_data = scanline + scanline
    compressed_data = zlib.compress(raw_data)
    png.extend(make_chunk(b"IDAT", compressed_data))

    # IEND chunk
    png.extend(make_chunk(b"IEND", b""))

    with open(filepath, "wb") as f:
        f.write(png)


def write_flat_arc_obj_file(
    filepath,
    filename_base,
    inner_radius,
    outer_radius,
    color,
    start_angle_deg,
    end_angle_deg,
    num_segments=32,
    vertical_offset=0.03,
):
    """Generates a native X-Plane OBJ8 file for a flat horizontal arc.

    The arc lies on the ground (X-Z plane) between start_angle_deg
    and end_angle_deg.

    Args:
        filepath: Path to save the generated OBJ8 file.
        filename_base: Base filename of the texture to reference.
        inner_radius: Inner boundary radius.
        outer_radius: Outer boundary radius.
        color: A tuple/list of (r, g, b) float color values.
        start_angle_deg: Starting angle in degrees.
        end_angle_deg: Ending angle in degrees.
        num_segments: Subdivision segment count.
        vertical_offset: Height coordinate of the horizontal arc (meters above ground).
    """
    r, g, b = color
    total_vertices = 2 * (num_segments + 1)
    total_indices = 6 * num_segments

    lines = [
        "I",
        "800",
        "OBJ",
        "",
        f"TEXTURE {filename_base}.png",
        f"TEXTURE_LIT {filename_base}_LIT.png",
        "GLOBAL_no_shadow",
        "",
        f"POINT_COUNTS {total_vertices} 0 0 {total_indices}",
        "",
    ]

    # Calculate angular step
    angle_diff = end_angle_deg - start_angle_deg

    # 1. Define Triangle Vertices (VT)
    # Heading is clockwise from North (+Z is South, +X is East)
    for i in range(num_segments + 1):
        h_deg = start_angle_deg + (angle_diff * float(i) / float(num_segments))
        h_rad = math.radians(h_deg)
        sin_h = math.sin(h_rad)
        cos_h = math.cos(h_rad)

        # Normal points straight up
        nx = 0.0
        ny = 1.0
        nz = 0.0
        s = float(i) / float(num_segments)

        # Inner circle vertex (t = 0.0)
        x_in = inner_radius * sin_h
        z_in = -inner_radius * cos_h
        lines.append(
            f"VT {x_in:.4f} {vertical_offset:.4f} {z_in:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} {s:.4f} 0.0000"
        )

        # Outer circle vertex (t = 1.0)
        x_out = outer_radius * sin_h
        z_out = -outer_radius * cos_h
        lines.append(
            f"VT {x_out:.4f} {vertical_offset:.4f} {z_out:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} {s:.4f} 1.0000"
        )

    lines.append("")

    # 2. Generate the Index List
    indices = []
    for i in range(num_segments):
        # Triangle 1
        indices.append(2 * i)
        indices.append(2 * i + 1)
        indices.append(2 * (i + 1))

        # Triangle 2
        indices.append(2 * (i + 1))
        indices.append(2 * i + 1)
        indices.append(2 * (i + 1) + 1)

    # Write indices as IDX10/IDX blocks
    for i in range(0, total_indices, 10):
        chunk = indices[i : i + 10]
        if len(chunk) == 10:
            chunk_str = " ".join(map(str, chunk))
            lines.append(f"IDX10 {chunk_str}")
        else:
            for idx in chunk:
                lines.append(f"IDX {idx}")

    lines.append("")
    lines.append("ATTR_blend")
    lines.append("ATTR_no_cull")
    lines.append("ATTR_no_shadow")
    lines.append("ATTR_shadow_blend 1.0")
    lines.append(f"TRIS 0 {total_indices}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_flat_disk_obj_file(
    filepath, filename_base, inner_radius, outer_radius, color, num_segments
):
    """Generates a native X-Plane OBJ8 file for a flat shaded disk/annulus.

    The disk lies on the ground (X-Z plane) with textured alpha glow
    and dynamic light casting.

    Args:
        filepath: Path to save the generated OBJ8 file.
        filename_base: Base filename of the texture to reference.
        inner_radius: Inner boundary radius.
        outer_radius: Outer boundary radius.
        color: A tuple/list of (r, g, b) float color values.
        num_segments: Subdivision segment count.
    """
    r, g, b = color
    total_vertices = 2 * (num_segments + 1)
    total_indices = 6 * num_segments

    lines = [
        "I",
        "800",
        "OBJ",
        "",
        f"TEXTURE {filename_base}.png",
        f"TEXTURE_LIT {filename_base}_LIT.png",
        "GLOBAL_no_shadow",
        "",
        f"POINT_COUNTS {total_vertices} 0 0 {total_indices}",
        "",
    ]

    # Float slightly above ground level to avoid z-fighting (meters above ground)
    vertical_offset = 0.02

    # 1. Define Triangle Vertices (VT)
    # We define two concentric circles at the same height vertical_offset:
    # Inner circle (radius = inner_radius)
    # Outer circle (radius = outer_radius)
    # Normal points straight up (0, 1, 0)
    for i in range(num_segments + 1):
        theta = 2.0 * math.pi * float(i) / float(num_segments)
        nx = 0.0
        ny = 1.0
        nz = 0.0
        s = float(i) / float(num_segments)

        # Inner circle vertex (t = 0.0)
        x_in = inner_radius * math.cos(theta)
        z_in = inner_radius * math.sin(theta)
        lines.append(
            f"VT {x_in:.4f} {vertical_offset:.4f} {z_in:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} {s:.4f} 0.0000"
        )

        # Outer circle vertex (t = 1.0)
        x_out = outer_radius * math.cos(theta)
        z_out = outer_radius * math.sin(theta)
        lines.append(
            f"VT {x_out:.4f} {vertical_offset:.4f} {z_out:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} {s:.4f} 1.0000"
        )

    lines.append("")

    # 2. Generate the Index List
    # Form quads out of the inner and outer circle vertices
    indices = []
    for i in range(num_segments):
        # Triangle 1 (v0, v1, v2)
        indices.append(2 * i)
        indices.append(2 * i + 1)
        indices.append(2 * (i + 1))

        # Triangle 2 (v2, v1, v3)
        indices.append(2 * (i + 1))
        indices.append(2 * i + 1)
        indices.append(2 * (i + 1) + 1)

    # Write indices as IDX10/IDX blocks
    for i in range(0, total_indices, 10):
        chunk = indices[i : i + 10]
        if len(chunk) == 10:
            chunk_str = " ".join(map(str, chunk))
            lines.append(f"IDX10 {chunk_str}")
        else:
            for idx in chunk:
                lines.append(f"IDX {idx}")

    lines.append("")
    # Enable blending (translucency) and disable backface culling
    lines.append("ATTR_blend")
    lines.append("ATTR_no_cull")
    lines.append("ATTR_no_shadow")
    lines.append("ATTR_shadow_blend 1.0")

    # Add dynamic spill light in the center just above the ground
    y_light = 0.10
    light_size = outer_radius * 2.0
    lines.append(
        f"LIGHT_SPILL_CUSTOM 0.0000 {y_light:.4f} 0.0000 "
        f"{r:.3f} {g:.3f} {b:.3f} 1.0000 {light_size:.1f} 0.0000 -1.0000 "
        f"0.0000 1.0000 none"
    )

    lines.append(f"TRIS 0 {total_indices}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_spokes_obj_file(
    filepath, filename_base, num_spokes=8, spoke_length=45.0, spoke_width=0.1
):
    """Generates a native X-Plane OBJ8 file for spokes emanating from the center.

    Args:
        filepath: Path to save the generated OBJ8 file.
        filename_base: Base filename of the texture to reference.
        num_spokes: Number of spokes.
        spoke_length: Outer radius/length of each spoke.
        spoke_width: Width of each spoke.
    """
    total_vertices = 4 * num_spokes
    total_indices = 6 * num_spokes

    lines = [
        "I",
        "800",
        "OBJ",
        "",
        f"TEXTURE {filename_base}.png",
        f"TEXTURE_LIT {filename_base}_LIT.png",
        "GLOBAL_no_shadow",
        "",
        f"POINT_COUNTS {total_vertices} 0 0 {total_indices}",
        "",
    ]

    vertical_offset = 0.04
    w = spoke_width / 2.0

    # 1. Define Vertices (VT)
    for i in range(num_spokes):
        angle_deg = (360.0 / num_spokes) * i
        angle_rad = math.radians(angle_deg)
        sin_a = math.sin(angle_rad)
        cos_a = math.cos(angle_rad)

        # Perpendicular vector in X-Z plane
        px = cos_a
        pz = sin_a

        # Spoke direction vector is (sin_a, -cos_a)
        # Inner vertices at radius 0
        x_in1 = -w * px
        z_in1 = -w * pz
        x_in2 = w * px
        z_in2 = w * pz

        # Outer vertices at radius spoke_length
        x_out1 = spoke_length * sin_a - w * px
        z_out1 = -spoke_length * cos_a - w * pz
        x_out2 = spoke_length * sin_a + w * px
        z_out2 = -spoke_length * cos_a + w * pz

        # Normal points straight up
        nx, ny, nz = 0.0, 1.0, 0.0

        # Add 4 vertices for this spoke
        lines.append(
            f"VT {x_in1:.4f} {vertical_offset:.4f} {z_in1:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} 0.0000 0.0000"
        )
        lines.append(
            f"VT {x_in2:.4f} {vertical_offset:.4f} {z_in2:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} 1.0000 0.0000"
        )
        lines.append(
            f"VT {x_out1:.4f} {vertical_offset:.4f} {z_out1:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} 0.0000 1.0000"
        )
        lines.append(
            f"VT {x_out2:.4f} {vertical_offset:.4f} {z_out2:.4f} "
            f"{nx:.4f} {ny:.4f} {nz:.4f} 1.0000 1.0000"
        )

    lines.append("")

    # 2. Define Indices
    indices = []
    for i in range(num_spokes):
        base = 4 * i
        # Triangle 1 (counter-clockwise winding from above: inner-left -> outer-left -> inner-right)
        indices.append(base)
        indices.append(base + 2)
        indices.append(base + 1)
        # Triangle 2 (counter-clockwise winding from above: inner-right -> outer-left -> outer-right)
        indices.append(base + 1)
        indices.append(base + 2)
        indices.append(base + 3)

    # Write indices
    for i in range(0, total_indices, 10):
        chunk = indices[i : i + 10]
        if len(chunk) == 10:
            lines.append("IDX10 " + " ".join(map(str, chunk)))
        else:
            for idx in chunk:
                lines.append(f"IDX {idx}")

    lines.append("")
    lines.append("ATTR_blend")
    lines.append("ATTR_no_cull")
    lines.append("ATTR_no_shadow")
    lines.append("ATTR_shadow_blend 1.0")
    lines.append(f"TRIS 0 {total_indices}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class GraphicsAssetManager(object):
    """Manages programmatic 3D OBJ8 generation, loading, and positioning of world boundaries."""

    def __init__(self, plugin_dir):
        """Initializes the GraphicsAssetManager.

        Args:
            plugin_dir: The absolute path to the plugin directory.
        """
        self.plugin_dir = plugin_dir

        # OBJ8 handles
        self.obj_15m = None
        self.obj_30m = None
        self.obj_45m = None
        self.obj_arc_green = None
        self.obj_arc_orange_l = None
        self.obj_arc_orange_r = None
        self.obj_arc_red_l = None
        self.obj_arc_red_r = None
        self.obj_spokes = None
        self.obj_arc_target = None

        # 3D Instance pointers
        self.inst_15m = None
        self.inst_30m = None
        self.inst_45m = None
        self.inst_arc_green = None
        self.inst_arc_orange_l = None
        self.inst_arc_orange_r = None
        self.inst_arc_red_l = None
        self.inst_arc_red_r = None
        self.inst_spokes = None
        self.inst_arc_target = None

    def load_objects(self, green_limit=30.0, orange_limit=60.0):
        """Generates the 3D OBJ8 objects, loads them, and creates rendering instances."""
        # 1. Programmatically write the PNG textures and OBJ8 files
        try:
            gen_dir = os.path.join(self.plugin_dir, "assets", "generated")
            if os.path.exists(gen_dir):
                try:
                    shutil.rmtree(gen_dir)
                except Exception as wipe_err:
                    xp.log(
                        "Helicopter Flight Instructor Warning: Failed to wipe "
                        f"assets/generated folder: {str(wipe_err)}"
                    )
            os.makedirs(gen_dir, exist_ok=True)

            # Generate 2x2 solid color textures (daytime albedo at 15% alpha)
            generate_solid_png(
                os.path.join(gen_dir, "disk_15m_a15.png"), 0.0, 1.0, 0.3, 0.15
            )
            generate_solid_png(
                os.path.join(gen_dir, "disk_15m_a15_LIT.png"), 0.0, 1.0, 0.3, 0.15
            )

            generate_solid_png(
                os.path.join(gen_dir, "disk_30m_a15.png"), 1.0, 0.6, 0.0, 0.15
            )
            generate_solid_png(
                os.path.join(gen_dir, "disk_30m_a15_LIT.png"), 1.0, 0.6, 0.0, 0.15
            )

            generate_solid_png(
                os.path.join(gen_dir, "disk_45m_a15.png"), 1.0, 0.1, 0.1, 0.15
            )
            generate_solid_png(
                os.path.join(gen_dir, "disk_45m_a15_LIT.png"), 1.0, 0.1, 0.1, 0.15
            )

            # Generate solid white textures for spokes (0.8 alpha)
            generate_solid_png(
                os.path.join(gen_dir, "spokes_white.png"), 1.0, 1.0, 1.0, 0.8
            )
            generate_solid_png(
                os.path.join(gen_dir, "spokes_white_LIT.png"), 1.0, 1.0, 1.0, 0.8
            )

            # Generate disk OBJ8 files
            write_flat_disk_obj_file(
                os.path.join(gen_dir, "disk_15m.obj"),
                "disk_15m_a15",
                inner_radius=0.0,
                outer_radius=LIMIT_DRIFT_GREEN_M,
                color=(0.0, 1.0, 0.3),
                num_segments=64,
            )
            write_flat_disk_obj_file(
                os.path.join(gen_dir, "disk_30m.obj"),
                "disk_30m_a15",
                inner_radius=LIMIT_DRIFT_GREEN_M,
                outer_radius=LIMIT_DRIFT_ORANGE_M,
                color=(1.0, 0.6, 0.0),
                num_segments=64,
            )
            write_flat_disk_obj_file(
                os.path.join(gen_dir, "disk_45m.obj"),
                "disk_45m_a15",
                inner_radius=LIMIT_DRIFT_ORANGE_M,
                outer_radius=LIMIT_DRIFT_RED_M,
                color=(1.0, 0.1, 0.1),
                num_segments=64,
            )

            # Generate spokes OBJ8 file
            write_spokes_obj_file(
                os.path.join(gen_dir, "spokes.obj"),
                "spokes_white",
                num_spokes=8,
                spoke_length=LIMIT_DRIFT_RED_M,
                spoke_width=0.1,
            )

            # Generate target heading white arc (+/- 3 deg, color white, vertical_offset=0.04 to float on green arc)
            write_flat_arc_obj_file(
                os.path.join(gen_dir, "arc_target.obj"),
                "spokes_white",
                inner_radius=46.0,
                outer_radius=55.0,
                color=(1.0, 1.0, 1.0),
                start_angle_deg=-3.0,
                end_angle_deg=3.0,
                num_segments=8,
                vertical_offset=0.04,
            )

            # Generate flat arc OBJ8 files for heading limits
            write_flat_arc_obj_file(
                os.path.join(gen_dir, "arc_green.obj"),
                "disk_15m_a15",
                inner_radius=46.0,
                outer_radius=55.0,
                color=(0.0, 1.0, 0.3),
                start_angle_deg=-green_limit,
                end_angle_deg=green_limit,
                num_segments=32,
            )
            write_flat_arc_obj_file(
                os.path.join(gen_dir, "arc_orange_l.obj"),
                "disk_30m_a15",
                inner_radius=46.0,
                outer_radius=55.0,
                color=(1.0, 0.6, 0.0),
                start_angle_deg=-orange_limit,
                end_angle_deg=-green_limit,
                num_segments=16,
            )
            write_flat_arc_obj_file(
                os.path.join(gen_dir, "arc_orange_r.obj"),
                "disk_30m_a15",
                inner_radius=46.0,
                outer_radius=55.0,
                color=(1.0, 0.6, 0.0),
                start_angle_deg=green_limit,
                end_angle_deg=orange_limit,
                num_segments=16,
            )
            write_flat_arc_obj_file(
                os.path.join(gen_dir, "arc_red_l.obj"),
                "disk_45m_a15",
                inner_radius=46.0,
                outer_radius=55.0,
                color=(1.0, 0.1, 0.1),
                start_angle_deg=-180.0,
                end_angle_deg=-orange_limit,
                num_segments=64,
            )
            write_flat_arc_obj_file(
                os.path.join(gen_dir, "arc_red_r.obj"),
                "disk_45m_a15",
                inner_radius=46.0,
                outer_radius=55.0,
                color=(1.0, 0.1, 0.1),
                start_angle_deg=orange_limit,
                end_angle_deg=180.0,
                num_segments=64,
            )

            xp.log(
                "Helicopter Flight Instructor: Programmatic OBJ8 files "
                "and PNG textures generated successfully in assets/generated."
            )
        except Exception as err:
            xp.log(
                "Helicopter Flight Instructor: Failed to generate OBJ8 "
                f"files/textures. Exception: {str(err)}"
            )
            return

        # 2. Get relative path to X-Plane root
        res_idx = self.plugin_dir.find("Resources")
        if res_idx == -1:
            xp.log(
                "Helicopter Flight Instructor: Could not determine X-Plane "
                "root relative path."
            )
            return

        rel_dir = self.plugin_dir[res_idx:].replace("\\", "/")

        # 3. Load the objects and create instances
        try:
            self.obj_15m = xp.loadObject(f"{rel_dir}/assets/generated/disk_15m.obj")
            self.obj_30m = xp.loadObject(f"{rel_dir}/assets/generated/disk_30m.obj")
            self.obj_45m = xp.loadObject(f"{rel_dir}/assets/generated/disk_45m.obj")
            self.obj_spokes = xp.loadObject(f"{rel_dir}/assets/generated/spokes.obj")
            self.obj_arc_target = xp.loadObject(
                f"{rel_dir}/assets/generated/arc_target.obj"
            )

            self.obj_arc_green = xp.loadObject(
                f"{rel_dir}/assets/generated/arc_green.obj"
            )
            self.obj_arc_orange_l = xp.loadObject(
                f"{rel_dir}/assets/generated/arc_orange_l.obj"
            )
            self.obj_arc_orange_r = xp.loadObject(
                f"{rel_dir}/assets/generated/arc_orange_r.obj"
            )
            self.obj_arc_red_l = xp.loadObject(
                f"{rel_dir}/assets/generated/arc_red_l.obj"
            )
            self.obj_arc_red_r = xp.loadObject(
                f"{rel_dir}/assets/generated/arc_red_r.obj"
            )

            if self.obj_15m:
                self.inst_15m = xp.createInstance(self.obj_15m)
            if self.obj_30m:
                self.inst_30m = xp.createInstance(self.obj_30m)
            if self.obj_45m:
                self.inst_45m = xp.createInstance(self.obj_45m)
            if self.obj_spokes:
                self.inst_spokes = xp.createInstance(self.obj_spokes)
            if self.obj_arc_target:
                self.inst_arc_target = xp.createInstance(self.obj_arc_target)

            if self.obj_arc_green:
                self.inst_arc_green = xp.createInstance(self.obj_arc_green)
            if self.obj_arc_orange_l:
                self.inst_arc_orange_l = xp.createInstance(self.obj_arc_orange_l)
            if self.obj_arc_orange_r:
                self.inst_arc_orange_r = xp.createInstance(self.obj_arc_orange_r)
            if self.obj_arc_red_l:
                self.inst_arc_red_l = xp.createInstance(self.obj_arc_red_l)
            if self.obj_arc_red_r:
                self.inst_arc_red_r = xp.createInstance(self.obj_arc_red_r)

            xp.log(
                "Helicopter Flight Instructor: 3D Object instances "
                "created successfully under Vulkan/Metal."
            )
        except Exception as err:
            xp.log(
                "Helicopter Flight Instructor: Failed to load 3D objects "
                f"or create instances: {str(err)}"
            )

    def set_instance_positions(self, tx, ty, tz, t_heading, draw_disks, draw_arcs):
        """Positions disk and heading arc instances dynamically in the 3D world."""
        # Position disks
        dx, dy, dz = (tx, ty, tz) if draw_disks else (0.0, -9999.0, 0.0)
        if self.inst_15m:
            xp.instanceSetPosition(self.inst_15m, (dx, dy, dz, 0.0, 0.0, 0.0), None)
        if self.inst_30m:
            xp.instanceSetPosition(self.inst_30m, (dx, dy, dz, 0.0, 0.0, 0.0), None)
        if self.inst_45m:
            xp.instanceSetPosition(self.inst_45m, (dx, dy, dz, 0.0, 0.0, 0.0), None)

        # Position spokes (rotated clockwise by t_heading, sharing visibility with disks)
        sx, sy, sz = (tx, ty, tz) if draw_disks else (0.0, -9999.0, 0.0)
        sh = t_heading if draw_disks else 0.0
        if self.inst_spokes:
            xp.instanceSetPosition(self.inst_spokes, (sx, sy, sz, 0.0, sh, 0.0), None)

        # Position arcs
        ax, ay, az = (tx, ty, tz) if draw_arcs else (0.0, -9999.0, 0.0)
        ah = t_heading if draw_arcs else 0.0
        if self.inst_arc_green:
            xp.instanceSetPosition(
                self.inst_arc_green, (ax, ay, az, 0.0, ah, 0.0), None
            )
        if self.inst_arc_orange_l:
            xp.instanceSetPosition(
                self.inst_arc_orange_l, (ax, ay, az, 0.0, ah, 0.0), None
            )
        if self.inst_arc_orange_r:
            xp.instanceSetPosition(
                self.inst_arc_orange_r, (ax, ay, az, 0.0, ah, 0.0), None
            )
        if self.inst_arc_red_l:
            xp.instanceSetPosition(
                self.inst_arc_red_l, (ax, ay, az, 0.0, ah, 0.0), None
            )
        if self.inst_arc_red_r:
            xp.instanceSetPosition(
                self.inst_arc_red_r, (ax, ay, az, 0.0, ah, 0.0), None
            )

        # Position target heading arc (pointing straight forward, sharing visibility with arcs)
        if self.inst_arc_target:
            xp.instanceSetPosition(
                self.inst_arc_target, (ax, ay, az, 0.0, ah, 0.0), None
            )

    def unload_objects(self):
        """Destroys rendering instances and unloads OBJ8 files cleanly."""
        try:
            if self.inst_15m:
                xp.destroyInstance(self.inst_15m)
                self.inst_15m = None
            if self.inst_30m:
                xp.destroyInstance(self.inst_30m)
                self.inst_30m = None
            if self.inst_45m:
                xp.destroyInstance(self.inst_45m)
                self.inst_45m = None
            if self.inst_spokes:
                xp.destroyInstance(self.inst_spokes)
                self.inst_spokes = None
            if self.inst_arc_target:
                xp.destroyInstance(self.inst_arc_target)
                self.inst_arc_target = None

            if self.inst_arc_green:
                xp.destroyInstance(self.inst_arc_green)
                self.inst_arc_green = None
            if self.inst_arc_orange_l:
                xp.destroyInstance(self.inst_arc_orange_l)
                self.inst_arc_orange_l = None
            if self.inst_arc_orange_r:
                xp.destroyInstance(self.inst_arc_orange_r)
                self.inst_arc_orange_r = None
            if self.inst_arc_red_l:
                xp.destroyInstance(self.inst_arc_red_l)
                self.inst_arc_red_l = None
            if self.inst_arc_red_r:
                xp.destroyInstance(self.inst_arc_red_r)
                self.inst_arc_red_r = None

            if self.obj_15m:
                xp.unloadObject(self.obj_15m)
                self.obj_15m = None
            if self.obj_30m:
                xp.unloadObject(self.obj_30m)
                self.obj_30m = None
            if self.obj_45m:
                xp.unloadObject(self.obj_45m)
                self.obj_45m = None
            if self.obj_spokes:
                xp.unloadObject(self.obj_spokes)
                self.obj_spokes = None
            if self.obj_arc_target:
                xp.unloadObject(self.obj_arc_target)
                self.obj_arc_target = None

            if self.obj_arc_green:
                xp.unloadObject(self.obj_arc_green)
                self.obj_arc_green = None
            if self.obj_arc_orange_l:
                xp.unloadObject(self.obj_arc_orange_l)
                self.obj_arc_orange_l = None
            if self.obj_arc_orange_r:
                xp.unloadObject(self.obj_arc_orange_r)
                self.obj_arc_orange_r = None
            if self.obj_arc_red_l:
                xp.unloadObject(self.obj_arc_red_l)
                self.obj_arc_red_l = None
            if self.obj_arc_red_r:
                xp.unloadObject(self.obj_arc_red_r)
                self.obj_arc_red_r = None

            xp.log(
                "Helicopter Flight Instructor: 3D Object instances destroyed "
                "and unloaded cleanly."
            )
        except Exception as err:
            xp.log(
                "Helicopter Flight Instructor: Failed to clean up 3D "
                f"instances: {str(err)}"
            )
