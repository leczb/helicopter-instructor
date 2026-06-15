"""ImGui User Interface submodule for Helicopter Flight Instructor."""

# pyrefly: ignore [missing-import]
import imgui

from helicopter_instructor import virtual_instructor
from helicopter_instructor.enums import Authority
from helicopter_instructor.enums import ControlAxis
from helicopter_instructor.enums import Envelope
from helicopter_instructor.enums import UpdateStatus
from helicopter_instructor.enums import VFIState

# Symbolic curriculum phase constants to avoid magic numbers
PHASE_PEDALS_ONLY = 1
PHASE_COLLECTIVE_ONLY = 2
PHASE_COLLECTIVE_PEDALS = 3
PHASE_CYCLIC_ONLY = 4
PHASE_CYCLIC_PEDALS = 5
PHASE_ALL_CONTROLS = 6


def draw_window(ui_controller, window_id, ref_con):
    """ImGui Drawing callback for the Instructor Control Panel.

    Args:
        ui_controller: The PluginUIController instance.
        window_id: The ImGui window ID handle.
        ref_con: Reference constant pointer.
    """
    imgui.text_disabled(f"Version {ui_controller.version}")

    # Draw background update checker status
    update_status = ui_controller.update_status
    if update_status == UpdateStatus.CHECKING:
        imgui.same_line()
        imgui.text_disabled(" (Checking for updates...)")
    elif update_status == UpdateStatus.UPDATE_AVAILABLE:
        imgui.same_line()
        imgui.text_colored(" (Update Available!)", 0.2, 0.8, 0.2, 1.0)
        imgui.same_line()
        if imgui.button(f"Get v{ui_controller.latest_version}"):
            ui_controller.open_update_url()
    elif update_status == UpdateStatus.UP_TO_DATE:
        imgui.same_line()
        imgui.text_disabled(" (Up to date)")
    elif update_status == UpdateStatus.ERROR:
        imgui.same_line()
        imgui.text_disabled(" (Update check failed)")
        imgui.same_line()
        if imgui.button("Retry"):
            ui_controller.trigger_update_check()

    # --- Collapsing Header: Master Control ---
    imgui.push_style_color(imgui.COLOR_HEADER, 0.1, 0.5, 0.3, 1.0)
    imgui.push_style_color(imgui.COLOR_HEADER_HOVERED, 0.2, 0.6, 0.4, 1.0)
    imgui.push_style_color(imgui.COLOR_HEADER_ACTIVE, 0.05, 0.4, 0.2, 1.0)

    # Master Engage
    clicked, new_ap_enabled = imgui.checkbox(
        "MASTER INSTRUCTOR ENGAGE", ui_controller.ap_enabled
    )
    if clicked:
        ui_controller.ap_enabled = new_ap_enabled

    imgui.separator()

    # --- Lesson Progression Curriculum Panel ---
    imgui.text("Hover Training Curriculum:")
    imgui.spacing()

    # Display active phase banner
    imgui.text_colored(
        f"Phase {ui_controller.phase}: "
        f"{virtual_instructor.PHASE_NAMES[ui_controller.phase]}",
        0.9,
        0.7,
        0.1,
        1.0,
    )

    # Curriculum Phase Buttons
    if imgui.button("<- Prev Phase"):
        if ui_controller.phase > PHASE_PEDALS_ONLY:
            ui_controller.set_phase(ui_controller.phase - 1)
    imgui.same_line()
    if imgui.button("Next Phase ->"):
        if ui_controller.phase < PHASE_ALL_CONTROLS:
            ui_controller.set_phase(ui_controller.phase + 1)

    imgui.spacing()
    if imgui.button("Trigger lesson Handoff"):
        if ui_controller.ap_enabled:
            ui_controller.initiate_handoff()

    imgui.spacing()
    changed, new_show_hud = imgui.checkbox(
        "Show Interactive HUD overlay on screen", ui_controller.show_hud
    )
    if changed:
        ui_controller.show_hud = new_show_hud

    if ui_controller.show_hud:
        imgui.indent()
        changed_dbg, new_show_dbg = imgui.checkbox(
            "Show Excellent Criteria Debug Info",
            ui_controller.show_envelope_debug
        )
        if changed_dbg:
            ui_controller.show_envelope_debug = new_show_dbg
        imgui.unindent()

    imgui.spacing()
    changed_alt, new_show_alt_bar = imgui.checkbox(
        "Show Standalone Altitude Safety Bar", ui_controller.show_alt_bar
    )
    if changed_alt:
        ui_controller.show_alt_bar = new_show_alt_bar

    imgui.spacing()
    # Toggle 3D visual boundaries in world
    changed_3d, new_show_3d_boundaries = imgui.checkbox(
        "Show 3D Hover Boundaries in World", ui_controller.show_3d_boundaries
    )
    if changed_3d:
        ui_controller.show_3d_boundaries = new_show_3d_boundaries

    if ui_controller.show_3d_boundaries:
        imgui.indent()
        changed_disks, new_show_3d_disks = imgui.checkbox(
            "Show Distance Safety Disks", ui_controller.show_3d_disks
        )
        if changed_disks:
            ui_controller.show_3d_disks = new_show_3d_disks

        changed_arcs, new_show_3d_arcs = imgui.checkbox(
            "Show Heading Safety Arcs", ui_controller.show_3d_arcs
        )
        if changed_arcs:
            ui_controller.show_3d_arcs = new_show_3d_arcs
        imgui.unindent()

    imgui.separator()

    # --- Real-Time VFI Status display ---
    expanded, _ = imgui.collapsing_header(
        "Instructor Status", flags=imgui.TREE_NODE_DEFAULT_OPEN
    )
    if expanded:
        imgui.text("System State: ")
        imgui.same_line()
        state_str = ui_controller.system_state
        if state_str == VFIState.VFI_FLIGHT:
            imgui.text_colored("VFI AUTO-HOVER", 0.2, 0.6, 1.0, 1.0)
        elif state_str == VFIState.SYNCING:
            imgui.text_colored("SYNCHRONIZING...", 1.0, 0.6, 0.1, 1.0)
        elif state_str == VFIState.STUDENT_FLIGHT:
            imgui.text_colored("STUDENT FLYING", 0.1, 0.9, 0.1, 1.0)
        elif state_str == VFIState.OVERRIDE:
            imgui.text_colored("HARD TAKEOVER ACTIVE!", 1.0, 0.2, 0.2, 1.0)
        elif state_str == VFIState.RECOVERY_HOLD:
            imgui.text_colored("STABILIZING COOL-DOWN...", 0.9, 0.5, 0.2, 1.0)

        imgui.spacing()
        # Table of axes and active authority
        imgui.columns(3, "authority_columns")
        imgui.set_column_width(0, 150)
        imgui.set_column_width(1, 150)
        imgui.set_column_width(2, 150)

        imgui.text("Control Axis")
        imgui.next_column()
        imgui.text("Authority")
        imgui.next_column()
        imgui.text("Matched Status")
        imgui.next_column()
        imgui.separator()

        def draw_axis_row(name, axis_key):
            imgui.text(name)
            imgui.next_column()
            auth = ui_controller.get_axis_authority(axis_key)
            if auth == Authority.STUDENT:
                imgui.text_colored("STUDENT", 0.1, 0.9, 0.1, 1.0)
            else:
                imgui.text_colored("VFI", 0.2, 0.6, 1.0, 1.0)
            imgui.next_column()

            matched = ui_controller.get_axis_sync_locked(axis_key)
            if matched:
                imgui.text_colored("SYNCHRONIZED", 0.1, 0.9, 0.1, 1.0)
            else:
                imgui.text_colored("NOT ALIGNED", 1.0, 0.4, 0.1, 1.0)
            imgui.next_column()

        draw_axis_row("Roll Cyclic L/R", ControlAxis.ROLL)
        draw_axis_row("Pitch Cyclic F/B", ControlAxis.PITCH)
        draw_axis_row("Anti-Torque Pedals", ControlAxis.YAW)
        draw_axis_row("Collective Altitude", ControlAxis.COLLECTIVE)

        imgui.columns(1)

        # Hover Drift and AGL Altitude telemetry
        imgui.separator()

        # Hover Drift
        drift_m = ui_controller.get_drift_m()
        safety_rad = ui_controller.hover_safety_radius
        soft_rad = ui_controller.hover_soft_radius
        drift_str = f"Hover Drift: {drift_m:.2f} m / {safety_rad:.1f} m"
        if drift_m > safety_rad:
            imgui.text_colored(
                drift_str + " (UNSAFE - TAKEOVER LIMIT!)", 1.0, 0.2, 0.2, 1.0
            )
        elif drift_m > soft_rad:
            imgui.text_colored(
                drift_str + " (WARNING - SOFT INTERVENTION)", 1.0, 0.6, 0.0, 1.0
            )
        else:
            imgui.text_colored(
                drift_str + " (SAFE - NORMAL)", 0.1, 0.9, 0.1, 1.0
            )

        # AGL Altitude
        y_agl = ui_controller.get_y_agl()
        agl_str = f"AGL Altitude: {y_agl:.2f} m / 6.0 m"
        if y_agl < 2.0 or y_agl > 10.0:
            imgui.text_colored(
                agl_str + " (UNSAFE - TAKEOVER LIMIT!)", 1.0, 0.2, 0.2, 1.0
            )
        elif y_agl < 4.0 or y_agl > 8.0:
            imgui.text_colored(
                agl_str + " (WARNING - SOFT INTERVENTION)", 1.0, 0.6, 0.0, 1.0
            )
        else:
            imgui.text_colored(agl_str + " (SAFE - NORMAL)", 0.1, 0.9, 0.1, 1.0)

    # --- Collapsing Header: Performance Metrics Panel ---
    expanded, _ = imgui.collapsing_header(
        "Performance Metrics", flags=imgui.TREE_NODE_DEFAULT_OPEN
    )
    if expanded:
        metrics = ui_controller._plugin.metrics

        # Stability Envelope Grade
        imgui.text("Proficiency Envelope: ")
        imgui.same_line()
        envelope_str = metrics.envelope
        if envelope_str == Envelope.EXCELLENT:
            imgui.text_colored("EXCELLENT HOVER", 0.1, 0.9, 0.1, 1.0)
        elif envelope_str == Envelope.GOOD:
            imgui.text_colored("GOOD HOVER", 0.9, 0.6, 0.1, 1.0)
        else:
            imgui.text_colored(
                "UNSTABLE / OVER-CONTROLLING", 1.0, 0.2, 0.2, 1.0
            )

        # Overall Score progress bar
        imgui.spacing()
        imgui.text("Overall Stability Score:")
        imgui.progress_bar(
            metrics.overall_score / 100.0,
            size=(0, 24),
            overlay=f"{int(metrics.overall_score)}%",
        )

        # Precision, Smoothness & Drift Speed sub-scores (individual lines)
        imgui.spacing()
        imgui.text("Precision (Station-keeping):")
        imgui.progress_bar(
            metrics.precision_score / 100.0,
            size=(0, 20),
            overlay=f"{int(metrics.precision_score)}%",
        )

        imgui.spacing()
        imgui.text("Smoothness (Calm Inputs):")
        imgui.progress_bar(
            metrics.smoothness_score / 100.0,
            size=(0, 20),
            overlay=f"{int(metrics.smoothness_score)}%",
        )

        imgui.spacing()
        imgui.text("Drift Speed Stability:")
        imgui.progress_bar(
            metrics.drift_speed_score / 100.0,
            size=(0, 20),
            overlay=f"{int(metrics.drift_speed_score)}%",
        )

        imgui.spacing()
        imgui.text("Vertical Speed Stability:")
        imgui.progress_bar(
            metrics.vert_speed_score / 100.0,
            size=(0, 20),
            overlay=f"{int(metrics.vert_speed_score)}%",
        )

        imgui.spacing()
        imgui.text("Yaw Rate Stability:")
        imgui.progress_bar(
            metrics.yaw_speed_score / 100.0,
            size=(0, 20),
            overlay=f"{int(metrics.yaw_speed_score)}%",
        )

        # OCI Table
        imgui.spacing()
        imgui.text("Axis Over-Controlling Indices (OCI):")
        imgui.columns(2, "oci_columns")
        imgui.set_column_width(0, 180)
        imgui.set_column_width(1, 270)

        imgui.text("Control Axis")
        imgui.next_column()
        imgui.text("Over-Controlling (OCI)")
        imgui.next_column()
        imgui.separator()

        def draw_oci_row(axis_label, oci_val, threshold):
            imgui.text(axis_label)
            imgui.next_column()
            clamped = max(0.0, min(1.0, oci_val))
            if oci_val > threshold:
                imgui.push_style_color(
                    imgui.COLOR_PLOT_HISTOGRAM, 1.0, 0.4, 0.1, 1.0
                )
            else:
                imgui.push_style_color(
                    imgui.COLOR_PLOT_HISTOGRAM, 0.1, 0.7, 0.2, 1.0
                )
            imgui.progress_bar(
                clamped,
                size=(220, 20),
                overlay=f"{oci_val:.2f} / {threshold:.1f}",
            )
            imgui.pop_style_color(1)
            imgui.next_column()

        draw_oci_row("Cyclic Roll L/R", metrics.oci[ControlAxis.ROLL], 1.0)
        draw_oci_row("Cyclic Pitch F/B", metrics.oci[ControlAxis.PITCH], 1.0)
        draw_oci_row("Anti-Torque Pedals", metrics.oci[ControlAxis.YAW], 0.8)
        draw_oci_row(
            "Collective Altitude",
            metrics.oci[ControlAxis.COLLECTIVE],
            0.8,
        )
        imgui.columns(1)

        # Session Stats
        imgui.spacing()
        imgui.separator()
        imgui.text("Training Session Statistics:")
        imgui.text(
            f"  Longest Student Flight: {metrics.longest_flight_time:.1f} s"
        )
        imgui.text(f"  Total Safety Takeovers: {metrics.total_takeovers}")
        imgui.text(
            f"  Average Target Drift: {metrics.get_average_drift():.2f} m"
        )
        imgui.text(f"  Current Drift Speed: {metrics.drift_speed:.2f} m/s")
        imgui.text(f"  Current Vertical Speed: {metrics.vert_speed:.2f} m/s")
        imgui.text(f"  Current Yaw Rate: {metrics.yaw_speed:.2f} deg/s")

        # Instructor Coaching Advice
        imgui.spacing()
        imgui.text_colored("INSTRUCTOR COACHING ADVICE:", 0.9, 0.7, 0.1, 1.0)
        imgui.text_wrapped(metrics.coaching_tips)

    # --- Collapsing Header: Hover Target Adjustment Panel ---
    expanded, _ = imgui.collapsing_header("Hover Target Adjustment")
    if expanded:
        imgui.text("Current Target coordinates:")
        imgui.text(f"  Target X (East): {ui_controller.target_x:.2f} m")
        imgui.text(f"  Target Z (South): {ui_controller.target_z:.2f} m")
        imgui.text(f"  Target Altitude: {ui_controller.target_y:.2f} m")
        imgui.text(f"  Target Heading: {ui_controller.target_psi:.1f} deg")
        imgui.spacing()

        imgui.text("Incremental Adjustments:")

        # Longitudinal (Forward/Backward)
        imgui.text("Longitudinal:  ")
        imgui.same_line()
        if imgui.button("Shift Fwd 1m"):
            ui_controller.adjust_hover_target(forward=1.0)
        imgui.same_line()
        if imgui.button("Shift Back 1m"):
            ui_controller.adjust_hover_target(forward=-1.0)

        # Lateral (Left/Right)
        imgui.text("Lateral:       ")
        imgui.same_line()
        if imgui.button("Shift Left 1m"):
            ui_controller.adjust_hover_target(right=-1.0)
        imgui.same_line()
        if imgui.button("Shift Right 1m"):
            ui_controller.adjust_hover_target(right=1.0)

        # Vertical (Altitude Up/Down)
        imgui.text("Altitude:      ")
        imgui.same_line()
        if imgui.button("Altitude +0.5m"):
            ui_controller.adjust_hover_target(up=0.5)
        imgui.same_line()
        if imgui.button("Altitude -0.5m"):
            ui_controller.adjust_hover_target(up=-0.5)

        # Heading (Rotate Left/Right)
        imgui.text("Heading:       ")
        imgui.same_line()
        if imgui.button("Rotate Left 5 deg"):
            ui_controller.adjust_hover_target(heading=-5.0)
        imgui.same_line()
        if imgui.button("Rotate Right 5 deg"):
            ui_controller.adjust_hover_target(heading=5.0)

        imgui.spacing()
        if imgui.button("Set Target to Current Position"):
            ui_controller.reset_target_to_current()
        imgui.spacing()

    # --- Collapsing Header: PID Gains Tuning Panel ---
    expanded, _ = imgui.collapsing_header("PID Gains Tuning")
    if expanded:
        gains = ui_controller.get_gains()
        gains_changed = False

        if imgui.begin_tab_bar("pid_gains_tabs"):

            tab_roll = imgui.begin_tab_item("Roll (Lateral)")
            if tab_roll.selected:
                imgui.text("Outer Loop: Position -> Target Velocity")
                changed1, gains.pos_lat.kp = imgui.slider_float(
                    "Kp Pos Roll", gains.pos_lat.kp, 0.0, 3.0
                )
                changed2, gains.pos_lat.ki = imgui.slider_float(
                    "Ki Pos Roll", gains.pos_lat.ki, 0.0, 0.5
                )

                imgui.text("Mid Loop: Velocity -> Target Attitude")
                changed3, gains.vel_lat.kp = imgui.slider_float(
                    "Kp Vel Roll", gains.vel_lat.kp, 0.0, 5.0
                )
                changed4, gains.vel_lat.ki = imgui.slider_float(
                    "Ki Vel Roll", gains.vel_lat.ki, 0.0, 0.5
                )

                imgui.text("Inner Loop: Attitude -> Cyclic Output")
                changed5, gains.att_roll.kp = imgui.slider_float(
                    "Kp Att Roll", gains.att_roll.kp, 0.0, 0.2
                )
                changed6, gains.att_roll.ki = imgui.slider_float(
                    "Ki Att Roll", gains.att_roll.ki, 0.0, 0.05
                )
                changed7, gains.att_roll.kd = imgui.slider_float(
                    "Kd Att Roll", gains.att_roll.kd, 0.0, 0.1
                )
                if (
                    changed1
                    or changed2
                    or changed3
                    or changed4
                    or changed5
                    or changed6
                    or changed7
                ):
                    gains_changed = True
                imgui.end_tab_item()

            tab_pitch = imgui.begin_tab_item("Pitch (Longitudinal)")
            if tab_pitch.selected:
                imgui.text("Outer Loop: Position -> Target Velocity")
                changed1, gains.pos_lon.kp = imgui.slider_float(
                    "Kp Pos Pitch", gains.pos_lon.kp, 0.0, 3.0
                )
                changed2, gains.pos_lon.ki = imgui.slider_float(
                    "Ki Pos Pitch", gains.pos_lon.ki, 0.0, 0.5
                )

                imgui.text("Mid Loop: Velocity -> Target Attitude")
                changed3, gains.vel_lon.kp = imgui.slider_float(
                    "Kp Vel Pitch", gains.vel_lon.kp, 0.0, 5.0
                )
                changed4, gains.vel_lon.ki = imgui.slider_float(
                    "Ki Vel Pitch", gains.vel_lon.ki, 0.0, 0.5
                )

                imgui.text("Inner Loop: Attitude -> Cyclic Output")
                changed5, gains.att_pitch.kp = imgui.slider_float(
                    "Kp Att Pitch", gains.att_pitch.kp, 0.0, 0.2
                )
                changed6, gains.att_pitch.ki = imgui.slider_float(
                    "Ki Att Pitch", gains.att_pitch.ki, 0.0, 0.05
                )
                changed7, gains.att_pitch.kd = imgui.slider_float(
                    "Kd Att Pitch", gains.att_pitch.kd, 0.0, 0.1
                )
                if (
                    changed1
                    or changed2
                    or changed3
                    or changed4
                    or changed5
                    or changed6
                    or changed7
                ):
                    gains_changed = True
                imgui.end_tab_item()

            tab_yaw = imgui.begin_tab_item("Yaw (Pedals)")
            if tab_yaw.selected:
                imgui.text("Heading Control Loop -> Pedal Output")
                changed1, gains.yaw.kp = imgui.slider_float(
                    "Kp Yaw", gains.yaw.kp, 0.0, 0.1
                )
                changed2, gains.yaw.ki = imgui.slider_float(
                    "Ki Yaw", gains.yaw.ki, 0.0, 0.02
                )
                changed3, gains.yaw.kd = imgui.slider_float(
                    "Kd Yaw", gains.yaw.kd, 0.0, 0.05
                )
                if changed1 or changed2 or changed3:
                    gains_changed = True
                imgui.end_tab_item()

            tab_alt = imgui.begin_tab_item("Collective (Alt)")
            if tab_alt.selected:
                imgui.text("Outer Loop: Altitude -> Vertical Speed")
                changed1, gains.alt.kp = imgui.slider_float(
                    "Kp Alt", gains.alt.kp, 0.0, 2.0
                )
                changed2, gains.alt.ki = imgui.slider_float(
                    "Ki Alt", gains.alt.ki, 0.0, 0.1
                )

                imgui.text("Inner Loop: VSpeed -> Collective Output")
                changed3, gains.vspeed.kp = imgui.slider_float(
                    "Kp VSpeed", gains.vspeed.kp, 0.0, 0.5
                )
                changed4, gains.vspeed.ki = imgui.slider_float(
                    "Ki VSpeed", gains.vspeed.ki, 0.0, 0.1
                )
                changed5, gains.vspeed.kd = imgui.slider_float(
                    "Kd VSpeed", gains.vspeed.kd, 0.0, 0.02
                )

                changed6, gains.hover_feedforward = imgui.slider_float(
                    "Hover Feedforward",
                    gains.hover_feedforward,
                    0.0,
                    1.0,
                )
                if (
                    changed1 or changed2 or changed3 or changed4 or
                    changed5 or changed6
                ):
                    gains_changed = True
                imgui.end_tab_item()

            imgui.end_tab_bar()

        if gains_changed:
            ui_controller.set_gains(gains)

        imgui.spacing()
        if imgui.button("Save Gains"):
            ui_controller.save_gains()
        imgui.same_line()
        if imgui.button("Load Gains"):
            ui_controller.load_gains()

    imgui.pop_style_color(3)
