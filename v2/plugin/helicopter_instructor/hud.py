"""HUD overlay (OSD and altitude bar) for Helicopter Flight Instructor."""

import math

import xp

from helicopter_instructor import virtual_instructor
from helicopter_instructor.envelope_limits import LIMIT_ALT_GREEN_M, LIMIT_ALT_ORANGE_M

# Try importing PyOpenGL once at the module level to avoid costly imports/searches on every frame
try:
    from OpenGL.GL import (
        glPushMatrix, glPopMatrix, glScalef,
        glBegin, glEnd, glVertex2f, glColor4f, glLineWidth,
        GL_LINES, GL_LINE_LOOP, GL_TRIANGLE_FAN,
        glEnable, glDisable, GL_CULL_FACE
    )
    GL_AVAILABLE = True
except ImportError:
    GL_AVAILABLE = False


# --- HUD Style & Color Constants ---
COLOR_WHITE = (1.0, 1.0, 1.0)
COLOR_GREY = (0.5, 0.5, 0.5)
COLOR_DARK_GREY = (0.4, 0.4, 0.4)
COLOR_LIGHT_GREY = (0.85, 0.85, 0.85)

COLOR_RED = (1.0, 0.2, 0.2)
COLOR_GREEN = (0.1, 0.9, 0.1)
COLOR_ORANGE = (1.0, 0.5, 0.0)

# Colors for specific states/roles
COLOR_TITLE = COLOR_LIGHT_GREY
COLOR_VFI = COLOR_LIGHT_GREY
COLOR_FALLBACK_ARROW = (1.0, 0.8, 0.0)

# Altitude bar band colors (RGBA)
ALT_BAND_OPACITY = 0.4
COLOR_ALT_BAND_RED = (1.0, 0.1, 0.1, ALT_BAND_OPACITY)
COLOR_ALT_BAND_ORANGE = (1.0, 0.6, 0.0, ALT_BAND_OPACITY)
COLOR_ALT_BAND_GREEN = (0.0, 1.0, 0.3, ALT_BAND_OPACITY)

# Line width constants
LINE_WIDTH_DEFAULT = 1.5
LINE_WIDTH_SLOT_TRACK = 1.0

# Layout configurations
COLLECTIVE_TRACK_HEIGHT = 75
PEDALS_TRACK_WIDTH = 140
CYCLIC_STICK_SCALE = 75.0
CYCLIC_STICK_HALF_SIZE = 40

ALT_BAR_HEIGHT = 420
ALT_BAR_WIDTH = 24


class HUDViewModel(object):
    """Stateless Data Transfer Object (DTO) containing telemetry and configuration for the HUD overlay."""

    def __init__(self, **kwargs):
        """Initializes the HUDViewModel with arbitrary keyword arguments."""
        for k, v in kwargs.items():
            setattr(self, k, v)


def draw_osd(view_model, window_id):
    """Draws the OSD HUD graphics including flight telemetry and matching guide.

    Args:
        view_model: A HUDViewModel instance.
        window_id: The X-Plane window ID.

    Returns:
        A tuple of (draw_success_code, new_visibility_state).
    """
    # Sync visibility state in case user closed window using native button
    new_show_osd = view_model.show_osd
    if view_model.osd_window:
        new_show_osd = (xp.getWindowIsVisible(view_model.osd_window) != 0)

    if not new_show_osd:
        return 1, new_show_osd

    # Use cached PyOpenGL availability
    gl_available = GL_AVAILABLE

    if gl_available:
        glPushMatrix()
        glScalef(2.0, 2.0, 1.0)

    # Helper function to automatically adjust drawing coordinates under scale
    def draw_string_scaled(color, x, y, text, font_id=xp.Font_Proportional):
        if gl_available:
            xp.drawString(
                color, int(x / 2.0), int(y / 2.0), text, fontID=font_id
            )
        else:
            xp.drawString(color, x, y, text, fontID=font_id)

    def draw_box_scaled(left, top, right, bottom):
        if gl_available:
            xp.drawTranslucentDarkBox(
                int(left / 2.0), int(top / 2.0),
                int(right / 2.0), int(bottom / 2.0)
            )
        else:
            xp.drawTranslucentDarkBox(left, top, right, bottom)

    def draw_vector_circle_scaled(
        color, center_x_val, center_y_val, radius, num_segments=32,
        fill=False
    ):
        if not gl_available:
            return
        cx_scaled = center_x_val / 2.0
        cy_scaled = center_y_val / 2.0
        r_scaled = radius / 2.0

        glColor4f(
            color[0], color[1], color[2],
            1.0 if len(color) < 4 else color[3]
        )

        if fill:
            glBegin(GL_TRIANGLE_FAN)
            glVertex2f(cx_scaled, cy_scaled)
            for segment in range(num_segments + 1):
                theta = 2.0 * 3.1415926 * segment / num_segments
                x = cx_scaled + r_scaled * math.cos(theta)
                y = cy_scaled + r_scaled * math.sin(theta)
                glVertex2f(x, y)
            glEnd()
        else:
            glLineWidth(1.5)
            glBegin(GL_LINE_LOOP)
            for segment in range(num_segments):
                theta = 2.0 * 3.1415926 * segment / num_segments
                x = cx_scaled + r_scaled * math.cos(theta)
                y = cy_scaled + r_scaled * math.sin(theta)
                glVertex2f(x, y)
            glEnd()

    def draw_vector_line_scaled(
        color, start_x, start_y, end_x, end_y, line_width=1.5
    ):
        if not gl_available:
            return
        x1_scaled = start_x / 2.0
        y1_scaled = start_y / 2.0
        x2_scaled = end_x / 2.0
        y2_scaled = end_y / 2.0

        glColor4f(
            color[0], color[1], color[2],
            1.0 if len(color) < 4 else color[3]
        )
        glLineWidth(line_width)
        glBegin(GL_LINES)
        glVertex2f(x1_scaled, y1_scaled)
        glVertex2f(x2_scaled, y2_scaled)
        glEnd()

    def draw_vector_rect_scaled(
        color, left, top, right, bottom, line_width=1.5, fill=False
    ):
        if not gl_available:
            return
        l_scaled = left / 2.0
        t_scaled = top / 2.0
        r_scaled = right / 2.0
        b_scaled = bottom / 2.0

        glColor4f(
            color[0], color[1], color[2],
            1.0 if len(color) < 4 else color[3]
        )

        if fill:
            glBegin(GL_TRIANGLE_FAN)
            glVertex2f(l_scaled, t_scaled)
            glVertex2f(r_scaled, t_scaled)
            glVertex2f(r_scaled, b_scaled)
            glVertex2f(l_scaled, b_scaled)
            glEnd()
        else:
            glLineWidth(line_width)
            glBegin(GL_LINE_LOOP)
            glVertex2f(l_scaled, t_scaled)
            glVertex2f(r_scaled, t_scaled)
            glVertex2f(r_scaled, b_scaled)
            glVertex2f(l_scaled, b_scaled)
            glEnd()

    # Get dynamic window geometry (user-draggable and positionable)
    box_left, box_top, box_right, box_bottom = xp.getWindowGeometry(
        window_id
    )
    center_x = (box_left + box_right) / 2.0
    box_width = box_right - box_left
    box_height = box_top - box_bottom

    # Prepare telemetry for OSD checks
    state = view_model.state
    y_agl = view_model.y_agl
    telemetry = {
        'phi': state['phi'],
        'theta': state['theta'],
        'psi': state['psi'],
        'P': state['P'],
        'Q': state['Q'],
        'R': state['R'],
        'vx': state['vx'],
        'vy': state['vy'],
        'vz': state['vz'],
        'y_agl': y_agl,
        'x': state['x'],
        'z': state['z'],
        'target_x': view_model.target_x,
        'target_z': view_model.target_z
    }

    # Draw translucent background card (below title bar)
    draw_box_scaled(box_left, box_top - 25, box_right, box_bottom)
    xp.setGraphicsState(0, 1, 0, 0, 1, 0, 0)

    # Color definitions
    color_title = COLOR_TITLE
    color_white = COLOR_WHITE
    color_orange = COLOR_ORANGE
    color_green = COLOR_GREEN
    color_red = COLOR_RED
    color_vfi = COLOR_VFI
    draw_vfi = (view_model.system_state != "STUDENT_FLIGHT")

    y_cursor = box_top - 45

    # 1. Main Title (Shortened to fit frame overlaps)
    title_str = "Helicopter Flight Instructor"
    if not view_model.ap_enabled:
        title_str = "Helicopter Flight Instructor (STANDBY)"
    draw_string_scaled(
        color_title, box_left + 20, y_cursor, title_str,
        font_id=xp.Font_Proportional
    )

    # 2. Phase Details
    y_cursor -= 22
    phase_str = (
        f"PHASE {view_model.phase}: "
        f"{virtual_instructor.PHASE_NAMES[view_model.phase]}"
    )
    draw_string_scaled(
        color_white, box_left + 20, y_cursor, phase_str,
        font_id=xp.Font_Proportional
    )

    # 3. System state
    y_cursor -= 22
    draw_string_scaled(
        color_white, box_left + 20, y_cursor, "SYSTEM STATUS:",
        font_id=xp.Font_Proportional
    )

    state_str = view_model.system_state
    state_color = color_title
    state_label = "ACTIVE"

    if not view_model.ap_enabled:
        state_color = color_orange
        state_label = "STANDBY (DISENGAGED)"
    elif state_str == "VFI_FLIGHT":
        state_color = color_title
        state_label = "AUTO HOVER ACTIVE"
    elif state_str == "SYNCING":
        state_color = color_orange
        ratio = (
            view_model.sync_timer /
            view_model.sync_hold_duration
        )
        state_label = f"ALIGNING CONTROLS... ({int(ratio * 100)}%)"
    elif state_str == "STUDENT_FLIGHT":
        state_color = color_green
        state_label = "STUDENT IN CONTROL"
    elif state_str == "OVERRIDE":
        state_color = color_red
        state_label = "TAKEBACK TAKEOVER ACTIVE!"
    elif state_str == "RECOVERY_HOLD":
        state_color = color_title
        time_left = int(view_model.recovery_timer)
        state_label = f"STABILIZING HOVER... ({time_left}s)"

    draw_string_scaled(
        state_color, box_left + 230, y_cursor, state_label,
        font_id=xp.Font_Proportional
    )

    # --- 3b. Student Performance Metrics ---
    if view_model.ap_enabled and view_model.system_state == "STUDENT_FLIGHT":
        y_cursor -= 22
        draw_string_scaled(
            color_white, box_left + 20, y_cursor, "STABILITY GRADE:",
            font_id=xp.Font_Proportional
        )
        grade_str = f"{view_model.envelope} (Stability: {int(view_model.overall_score)}%)"
        grade_color = color_green if view_model.envelope in ["Excellent", "Good"] else color_red
        draw_string_scaled(
            grade_color, box_left + 230, y_cursor, grade_str,
            font_id=xp.Font_Proportional
        )

        # Dynamic Coaching tip
        if view_model.coaching_tips:
            y_cursor -= 22
            tip_str = f"INSTRUCTOR TIP: {view_model.coaching_tips}"
            draw_string_scaled(
                color_white, box_left + 20, y_cursor, tip_str,
                font_id=xp.Font_Proportional
            )

    # 4. CAPTION/SUBTITLE ANNOUNCEMENT (Large visual banner centered)
    if view_model.hud_caption:
        y_cursor -= 26
        caption_color = color_white
        if "I HAVE" in view_model.hud_caption:
            caption_color = color_red
        elif "YOU HAVE" in view_model.hud_caption:
            caption_color = color_green
        elif "PREPARE" in view_model.hud_caption:
            caption_color = color_orange

        # Estimated width of proportional font: about 8.5 pixels per char
        cap_len = len(view_model.hud_caption) + 6  # plus brackets
        est_width = cap_len * 8.5
        cap_x = int(center_x - est_width / 2.0)
        draw_string_scaled(
            caption_color, cap_x, y_cursor,
            f">> {view_model.hud_caption} <<",
            font_id=xp.Font_Proportional
        )

    # --- OSD HELPER GRAPHICS (Always visible) ---
    y_graph_base = box_bottom + 35

    # --- 1. Vertical Collective Slider ---
    col_x = box_left + 65
    col_y = y_graph_base
    col_height = COLLECTIVE_TRACK_HEIGHT

    vfi_coll_y = int(
        col_y + view_model.last_commands["collective"] * col_height
    )
    phys_coll_y = int(
        col_y + view_model.last_hardware_inputs["collective"] * col_height
    )

    # Over-controlling visual warning state (solid red when overcontrolled, representing Over-Controlling Index (OCI))
    oci = view_model.oci

    if gl_available:
        # 1. Disable texturing and lighting
        xp.setGraphicsState(0, 0, 0, 0, 1, 0, 0)

        # Draw vertical slot track outline (width 8 pixels)
        col_slot_color = COLOR_DARK_GREY
        if oci.get("collective", 0.0) > 0.8:
            col_slot_color = COLOR_RED
        draw_vector_rect_scaled(
            col_slot_color, col_x - 4, col_y + col_height,
            col_x + 4, col_y, line_width=LINE_WIDTH_SLOT_TRACK
        )

        # Draw central horizontal tick inside (neutral / center collective)
        draw_vector_line_scaled(
            COLOR_DARK_GREY, col_x - 4, col_y + col_height / 2.0,
            col_x + 4, col_y + col_height / 2.0, line_width=LINE_WIDTH_SLOT_TRACK
        )

        # Set dynamic deflection indicator color
        coll_color = COLOR_ORANGE  # Bright orange
        if view_model.sync_locked["collective"]:
            coll_color = COLOR_GREEN  # Bright green

        # Draw VFI target acceptable range as a hollow green rectangle
        if draw_vfi:
            col_tolerance_px = view_model.match_tolerance * col_height
            col_rect_h = 3.0 + col_tolerance_px
            draw_vector_rect_scaled(
                COLOR_GREEN, col_x - 8.0, vfi_coll_y + col_rect_h,
                col_x + 8.0, vfi_coll_y - col_rect_h, line_width=LINE_WIDTH_DEFAULT,
                fill=False
            )

        # Draw Student physical collective input as a solid rectangle
        draw_vector_rect_scaled(
            coll_color, col_x - 8.0, phys_coll_y + 3.0,
            col_x + 8.0, phys_coll_y - 3.0, fill=True
        )

        # Restore state for labels
        xp.setGraphicsState(0, 1, 0, 0, 1, 0, 0)
    else:
        # Draw vertical scale ticks fallback
        for h in range(0, col_height + 1, 15):
            draw_string_scaled(
                COLOR_GREY, col_x, col_y + h - 4, "-",
                font_id=xp.Font_Proportional
            )

        # Draw fallback pointers only when OpenGL is not available
        if draw_vfi:
            draw_string_scaled(
                color_vfi, col_x - 20, vfi_coll_y - 4, "►",
                font_id=xp.Font_Proportional
            )
        draw_string_scaled(
            COLOR_FALLBACK_ARROW, col_x + 12, phys_coll_y - 4, "◄",
            font_id=xp.Font_Proportional
        )

    # Label (consistently aligned below the vertical track)
    draw_string_scaled(
        color_white, col_x - 42, col_y - 22, "COLLECTIVE",
        font_id=xp.Font_Proportional
    )

    # --- 2. Horizontal Pedals Slider ---
    ped_x = box_left + 195
    ped_y = y_graph_base + 35
    ped_width = PEDALS_TRACK_WIDTH

    vfi_yaw_x = int(
        ped_x + ped_width / 2.0 +
        view_model.last_commands["yaw"] * (ped_width / 2.0)
    )
    phys_yaw_x = int(
        ped_x + ped_width / 2.0 +
        view_model.last_hardware_inputs["yaw"] * (ped_width / 2.0)
    )

    if gl_available:
        # 1. Disable texturing and lighting
        xp.setGraphicsState(0, 0, 0, 0, 1, 0, 0)

        # Draw horizontal slot track outline (height 8 pixels)
        ped_slot_color = COLOR_DARK_GREY
        if oci.get("yaw", 0.0) > 0.8:
            ped_slot_color = COLOR_RED
        draw_vector_rect_scaled(
            ped_slot_color, ped_x, ped_y + 4,
            ped_x + ped_width, ped_y - 4, line_width=LINE_WIDTH_SLOT_TRACK
        )

        # Draw vertical center tick (neutral rudder)
        draw_vector_line_scaled(
            COLOR_DARK_GREY, ped_x + ped_width / 2.0, ped_y - 4,
            ped_x + ped_width / 2.0, ped_y + 4, line_width=LINE_WIDTH_SLOT_TRACK
        )

        # Set dynamic pedals deflection indicator color
        yaw_color = COLOR_ORANGE  # Bright orange
        if view_model.sync_locked["yaw"]:
            yaw_color = COLOR_GREEN  # Bright green

        # Draw VFI target acceptable range as a hollow green rectangle
        if draw_vfi:
            ped_scale = ped_width / 2.0
            ped_tolerance_px = view_model.match_tolerance * ped_scale
            ped_rect_w = 3.0 + ped_tolerance_px
            draw_vector_rect_scaled(
                COLOR_GREEN, vfi_yaw_x - ped_rect_w, ped_y + 8.0,
                vfi_yaw_x + ped_rect_w, ped_y - 8.0, line_width=LINE_WIDTH_DEFAULT,
                fill=False
            )

        # Draw Student physical rudder input as a solid filled rectangle
        draw_vector_rect_scaled(
            yaw_color, phys_yaw_x - 3.0, ped_y + 8.0,
            phys_yaw_x + 3.0, ped_y - 8.0, fill=True
        )

        # Restore state for labels
        xp.setGraphicsState(0, 1, 0, 0, 1, 0, 0)
    else:
        # Draw background bar scale fallback
        draw_string_scaled(
            COLOR_GREY, ped_x - 15, ped_y - 4, "L [==============] R",
            font_id=xp.Font_Proportional
        )

        # Draw fallback pointers only when OpenGL is not available
        if draw_vfi:
            draw_string_scaled(
                color_vfi, vfi_yaw_x - 6, ped_y + 12, "▼",
                font_id=xp.Font_Proportional
            )
        draw_string_scaled(
            COLOR_FALLBACK_ARROW, phys_yaw_x - 6, ped_y - 18, "▲",
            font_id=xp.Font_Proportional
        )

    # Label (consistently aligned below the horizontal track)
    draw_string_scaled(
        color_white, ped_x + ped_width // 2 - 32, ped_y - 36, "PEDALS",
        font_id=xp.Font_Proportional
    )

    # --- 3. 2D Stick Matching Crosshair ---
    cross_x = box_left + 440
    cross_y = y_graph_base + 35
    half_size = CYCLIC_STICK_HALF_SIZE

    # Draw physical stick position scaled to stick scale
    stick_scale = CYCLIC_STICK_SCALE
    stick_x = int(
        cross_x + view_model.last_hardware_inputs["roll"] * stick_scale
    )
    stick_y = int(
        cross_y - view_model.last_hardware_inputs["pitch"] * stick_scale
    )

    # Draw target VFI position scaled to stick scale
    vfi_x = int(cross_x + view_model.last_commands["roll"] * stick_scale)
    vfi_y = int(cross_y - view_model.last_commands["pitch"] * stick_scale)

    # Dynamic stick deflection pointer color
    stick_color = COLOR_ORANGE  # Bright orange
    if (view_model.sync_locked["roll"] and
            view_model.sync_locked["pitch"]):
        stick_color = COLOR_GREEN  # Bright green

    cyclic_overcontrolled = max(oci.get("roll", 0.0), oci.get("pitch", 0.0)) > 1.0
    if cyclic_overcontrolled:
        stick_color = COLOR_RED

    if gl_available:
        # 1. Disable texturing and lighting
        xp.setGraphicsState(0, 0, 0, 0, 1, 0, 0)

        # 2. Disable face culling to ensure solid filled circles are drawn
        glDisable(GL_CULL_FACE)

        # 3. Draw central target crosshair lines in green
        draw_vector_line_scaled(
            COLOR_GREEN, cross_x - 12, cross_y,
            cross_x + 12, cross_y, line_width=LINE_WIDTH_SLOT_TRACK
        )
        draw_vector_line_scaled(
            COLOR_GREEN, cross_x, cross_y - 12,
            cross_x, cross_y + 12, line_width=LINE_WIDTH_SLOT_TRACK
        )

        # 4. Draw a hollow circle at the dynamic VFI target position
        ball_radius = 4.0
        tolerance_px = view_model.match_tolerance * stick_scale
        target_circle_radius = ball_radius + tolerance_px

        if draw_vfi:
            draw_vector_circle_scaled(
                COLOR_GREEN, vfi_x, vfi_y, target_circle_radius,
                fill=False
            )

        # 5. Draw the physical stick position as a solid filled circle
        draw_vector_circle_scaled(
            stick_color, stick_x, stick_y, ball_radius, fill=True
        )

        # 6. Restore face culling and graphics state
        glEnable(GL_CULL_FACE)
        xp.setGraphicsState(0, 1, 0, 0, 1, 0, 0)
    else:
        # Fallback text character drawing if OpenGL is not available
        if draw_vfi:
            draw_string_scaled(
                COLOR_GREEN, vfi_x - 5, vfi_y - 5, "○",
                font_id=xp.Font_Proportional
            )
        draw_string_scaled(
            COLOR_GREEN, cross_x - 5, cross_y + half_size - 5, "┬",
            font_id=xp.Font_Proportional
        )
        draw_string_scaled(
            COLOR_GREEN, cross_x - 5, cross_y - half_size - 5, "┴",
            font_id=xp.Font_Proportional
        )
        draw_string_scaled(
            stick_color, stick_x - 5, stick_y - 5, "●",
            font_id=xp.Font_Proportional
        )

    # Label (consistently aligned below the cyclic crosshair box)
    draw_string_scaled(
        color_white, cross_x - 28, cross_y - half_size - 20, "CYCLIC",
        font_id=xp.Font_Proportional
    )

    if gl_available:
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glPopMatrix()

    return 1, new_show_osd


def draw_alt_bar(view_model, window_id):
    """Draws a vertical altitude guidance bar in the alt-bar window.

    Args:
        view_model: A HUDViewModel instance.
        window_id: The X-Plane window ID.

    Returns:
        A tuple of (draw_success_code, new_visibility_state).
    """
    # Sync visibility state in case user closed window using native close button
    new_show_alt_bar = view_model.show_alt_bar
    if view_model.alt_bar_window:
        new_show_alt_bar = (
            xp.getWindowIsVisible(view_model.alt_bar_window) != 0
        )

    # Only show when autopilot is enabled and Lesson collective is STUDENT
    is_student_coll = (
        virtual_instructor.PHASE_CONFIGS[
            view_model.phase
        ]["collective"] == "STUDENT"
    )
    active_visible = (
        new_show_alt_bar and view_model.ap_enabled and is_student_coll
    )

    if not active_visible:
        return 1, new_show_alt_bar

    # Use cached PyOpenGL availability
    gl_available = GL_AVAILABLE

    if gl_available:
        glPushMatrix()
        glScalef(2.0, 2.0, 1.0)

    # Helper function to automatically adjust drawing coordinates under scale
    def draw_string_scaled(color, x, y, text, font_id=xp.Font_Proportional):
        if gl_available:
            xp.drawString(
                color, int(x / 2.0), int(y / 2.0), text, fontID=font_id
            )
        else:
            xp.drawString(color, x, y, text, fontID=font_id)

    def draw_box_scaled(left, top, right, bottom):
        if gl_available:
            xp.drawTranslucentDarkBox(
                int(left / 2.0), int(top / 2.0),
                int(right / 2.0), int(bottom / 2.0)
            )
        else:
            xp.drawTranslucentDarkBox(left, top, right, bottom)

    def draw_vector_rect_scaled(
        color, left, top, right, bottom, line_width=1.5, fill=False
    ):
        if not gl_available:
            return
        l_scaled = left / 2.0
        t_scaled = top / 2.0
        r_scaled = right / 2.0
        b_scaled = bottom / 2.0

        glColor4f(
            color[0], color[1], color[2],
            1.0 if len(color) < 4 else color[3]
        )

        if fill:
            glBegin(GL_TRIANGLE_FAN)
            glVertex2f(l_scaled, t_scaled)
            glVertex2f(r_scaled, t_scaled)
            glVertex2f(r_scaled, b_scaled)
            glVertex2f(l_scaled, b_scaled)
            glEnd()
        else:
            glLineWidth(line_width)
            glBegin(GL_LINE_LOOP)
            glVertex2f(l_scaled, t_scaled)
            glVertex2f(r_scaled, t_scaled)
            glVertex2f(r_scaled, b_scaled)
            glVertex2f(l_scaled, b_scaled)
            glEnd()

    def draw_vector_line_scaled(
        color, start_x, start_y, end_x, end_y, line_width=1.5
    ):
        if not gl_available:
            return
        x1_scaled = start_x / 2.0
        y1_scaled = start_y / 2.0
        x2_scaled = end_x / 2.0
        y2_scaled = end_y / 2.0

        glColor4f(
            color[0], color[1], color[2],
            1.0 if len(color) < 4 else color[3]
        )
        glLineWidth(line_width)
        glBegin(GL_LINES)
        glVertex2f(x1_scaled, y1_scaled)
        glVertex2f(x2_scaled, y2_scaled)
        glEnd()

    # Get dynamic window geometry
    box_left, box_top, box_right, box_bottom = xp.getWindowGeometry(
        window_id
    )

    # Draw translucent dark background card inside window bounds
    draw_box_scaled(box_left, box_top, box_right, box_bottom)
    xp.setGraphicsState(0, 1, 0, 0, 1, 0, 0)

    # Dynamic layout coordinates centered in window bounds
    alt_x = (box_left + box_right) / 2.0
    alt_y = box_bottom + 70
    alt_height = ALT_BAR_HEIGHT

    def alt_to_y(alt_val):
        clamped = max(0.0, min(12.0, alt_val))
        return alt_y + (clamped / 12.0) * alt_height

    y_agl = view_model.y_agl
    current_agl_y = int(alt_to_y(y_agl))

    if gl_available:
        # Disable texturing and lighting
        xp.setGraphicsState(0, 0, 0, 0, 1, 0, 0)

        # Fill safety zone bands at configured opacity
        width = ALT_BAR_WIDTH
        green_top = 6.0 + LIMIT_ALT_GREEN_M
        green_bottom = 6.0 - LIMIT_ALT_GREEN_M
        orange_top = 6.0 + LIMIT_ALT_ORANGE_M
        orange_bottom = 6.0 - LIMIT_ALT_ORANGE_M

        # Red bottom: 0.0m to orange_bottom
        draw_vector_rect_scaled(
            COLOR_ALT_BAND_RED, alt_x - width / 2, alt_to_y(orange_bottom),
            alt_x + width / 2, alt_to_y(0.0), fill=True
        )
        # Orange bottom: orange_bottom to green_bottom
        draw_vector_rect_scaled(
            COLOR_ALT_BAND_ORANGE, alt_x - width / 2, alt_to_y(green_bottom),
            alt_x + width / 2, alt_to_y(orange_bottom), fill=True
        )
        # Green middle: green_bottom to green_top
        draw_vector_rect_scaled(
            COLOR_ALT_BAND_GREEN, alt_x - width / 2, alt_to_y(green_top),
            alt_x + width / 2, alt_to_y(green_bottom), fill=True
        )
        # Orange top: green_top to orange_top
        draw_vector_rect_scaled(
            COLOR_ALT_BAND_ORANGE, alt_x - width / 2, alt_to_y(orange_top),
            alt_x + width / 2, alt_to_y(green_top), fill=True
        )
        # Red top: orange_top to 12.0m
        draw_vector_rect_scaled(
            COLOR_ALT_BAND_RED, alt_x - width / 2, alt_to_y(12.0),
            alt_x + width / 2, alt_to_y(orange_top), fill=True
        )

        # Outer frame outline
        draw_vector_rect_scaled(
            COLOR_DARK_GREY, alt_x - width / 2, alt_y + alt_height,
            alt_x + width / 2, alt_y, line_width=LINE_WIDTH_SLOT_TRACK, fill=False
        )

        # Target altitude (6.0m) central tick mark
        draw_vector_line_scaled(
            COLOR_LIGHT_GREY, alt_x - width / 2, alt_to_y(6.0),
            alt_x + width / 2, alt_to_y(6.0), line_width=LINE_WIDTH_SLOT_TRACK
        )

        # Current AGL cursor as a solid white rectangle (height 4px, width 20px)
        draw_vector_rect_scaled(
            COLOR_WHITE, alt_x - width / 2, current_agl_y + 2,
            alt_x + width / 2, current_agl_y - 2, fill=True
        )

        xp.setGraphicsState(0, 1, 0, 0, 1, 0, 0)
    else:
        # Fallback when OpenGL is not available
        for h in range(0, alt_height + 1, 15):
            draw_string_scaled(
                COLOR_GREY, alt_x, alt_y + h - 4, "-",
                font_id=xp.Font_Proportional
            )
        draw_string_scaled(
            COLOR_WHITE, alt_x + 12, current_agl_y - 4, "◄",
            font_id=xp.Font_Proportional
        )

    # Centered label below the scale
    draw_string_scaled(
        COLOR_WHITE, alt_x - 13, box_bottom + 25, "ALT",
        font_id=xp.Font_Proportional
    )
    if gl_available:
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glPopMatrix()

    return 1, new_show_alt_bar
