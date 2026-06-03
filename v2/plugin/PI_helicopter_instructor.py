"""X-Plane entrypoint plugin for the Helicopter Flight Instructor."""

import collections
import math
import os

import importlib

# pyrefly: ignore [missing-import]
import xp

# pyrefly: ignore [missing-import]
import xp_imgui

from helicopter_instructor import audio
from helicopter_instructor import config
from helicopter_instructor import envelope_limits
from helicopter_instructor import graphics
from helicopter_instructor import hud
from helicopter_instructor import metrics
from helicopter_instructor import ui
from helicopter_instructor import virtual_instructor
from helicopter_instructor.autopilot import helicopter_control
from helicopter_instructor.virtual_instructor import M_S_TO_FT_MIN, M_S_TO_KNOTS

# Explicitly reload submodules to prevent caching issues during X-Plane plugin reloads
importlib.reload(audio)
importlib.reload(config)
importlib.reload(envelope_limits)
importlib.reload(graphics)
importlib.reload(hud)
importlib.reload(metrics)
importlib.reload(ui)
importlib.reload(virtual_instructor)
importlib.reload(helicopter_control)

# Symbolic curriculum phase constants to avoid magic numbers
PHASE_PEDALS_ONLY = 1
PHASE_COLLECTIVE_ONLY = 2
PHASE_COLLECTIVE_PEDALS = 3
PHASE_CYCLIC_ONLY = 4
PHASE_CYCLIC_PEDALS = 5
PHASE_ALL_CONTROLS = 6

# Symbolic audio cue constants to avoid raw filenames
SOUND_I_HAVE_CONTROL = "I have control.wav"
SOUND_GET_READY = "Get ready to take control.wav"
SOUND_YOU_HAVE_PEDALS = "You have the pedals.wav"
SOUND_YOU_HAVE_COLLECTIVE = "You have the collective.wav"
SOUND_YOU_HAVE_COLLECTIVE_PEDALS = "You have the collective and the pedals.wav"
SOUND_YOU_HAVE_CYCLIC = "You have the cyclic.wav"
SOUND_YOU_HAVE_CYCLIC_PEDALS = "You have the cyclic and the pedals.wav"
SOUND_YOU_HAVE_ALL = "You have all controls.wav"
SOUND_PERFECT = "Perfect.wav"

# New metrics-driven audio cues
SOUND_RELAX_CYCLIC = "Relax cyclic.wav"
SOUND_STEADY_PEDALS = "Steady pedals.wav"
SOUND_SMOOTH_COLLECTIVE = "Smooth collective.wav"
SOUND_CORRECT_DRIFT = "Correct the drift.wav"
SOUND_WE_ARE_TOO_HIGH = "We are too high.wav"
SOUND_WE_ARE_TOO_LOW = "We are too low.wav"
SOUND_NICE_RECOVERY = "Nice recovery.wav"
SOUND_GREAT_PEDALS = "Great pedals.wav"
SOUND_SMOOTH_CYCLIC = "Smooth cyclic.wav"

# Phase progression audio cues
SOUND_PHASE_TRANSITION = "Phase transition.wav"
# Template: format with phase number (e.g. "Phase 1 intro.wav")
SOUND_PHASE_INTRO_TEMPLATE = "Phase {} intro.wav"
SOUND_TRAINING_COMPLETE = "Now you know how to hover.wav"

# X-Plane Plugin Message IDs
MSG_PLANE_LOADED = 102
PLANE_USER_IDX = 0


class PluginUIController(object):
    """Facade / Presenter class that exposes properties and actions for ui.py."""

    def __init__(self, plugin):
        """Initializes the PluginUIController instance.

        Args:
            plugin: The PythonInterface instance.
        """
        self._plugin = plugin

    @property
    def version(self):
        return self._plugin.version

    @property
    def ap_enabled(self):
        return self._plugin.ap_enabled

    @ap_enabled.setter
    def ap_enabled(self, value):
        if value != self._plugin.ap_enabled:
            if value:
                state = self._plugin.get_current_state()
                curr_collective = xp.getDataf(self._plugin.dref_prop_ratio_all)
                # Set initial hover height setpoint to exactly 6.0m AGL
                y_agl = (
                    xp.getDataf(self._plugin.dref_y_agl)
                    if self._plugin.dref_y_agl
                    else 10.0
                )
                target_alt = state["y"] - y_agl + 6.0
                self._plugin.controller.engage(
                    state["x"], target_alt, state["z"], state["psi"], curr_collective
                )
                self._plugin.instructor.system_state = "VFI_FLIGHT"
                self._plugin.instructor.control_assignment = {
                    "roll": "VFI",
                    "pitch": "VFI",
                    "yaw": "VFI",
                    "collective": "VFI",
                }
                self._plugin.instructor.set_hud_caption("VFI ENGAGED - AUTO HOVER")
                self._plugin.ap_enabled = True
                self._plugin.play_sound(SOUND_I_HAVE_CONTROL, clear_queue=True)
                # Queue the intro for the current phase so the student learns
                # what they are about to practice. This also ensures Phase 1
                # intro is played on first engagement (there is no preceding
                # phase to trigger it automatically).
                phase = self._plugin.instructor.phase
                self._plugin.play_sound(SOUND_PHASE_INTRO_TEMPLATE.format(phase))
            else:
                self._plugin.ap_enabled = False
                self._plugin.release_all_overrides()
                self._plugin.instructor.system_state = "VFI_FLIGHT"
                self._plugin.instructor.set_hud_caption("INSTRUCTOR DISENGAGED")

    @property
    def phase(self):
        return self._plugin.instructor.phase

    def set_phase(self, phase_num):
        self._plugin.instructor.set_phase(phase_num)

    def initiate_handoff(self):
        self._plugin.instructor.initiate_handoff()

    @property
    def show_hud(self):
        return self._plugin.show_hud

    @show_hud.setter
    def show_hud(self, value):
        self._plugin.show_hud = value
        if self._plugin.hud_window:
            xp.setWindowIsVisible(self._plugin.hud_window, 1 if value else 0)

    @property
    def show_alt_bar(self):
        return self._plugin.show_alt_bar

    @show_alt_bar.setter
    def show_alt_bar(self, value):
        self._plugin.show_alt_bar = value
        if self._plugin.alt_bar_window:
            xp.setWindowIsVisible(self._plugin.alt_bar_window, 1 if value else 0)

    @property
    def show_3d_boundaries(self):
        return self._plugin.show_3d_boundaries

    @show_3d_boundaries.setter
    def show_3d_boundaries(self, value):
        self._plugin.show_3d_boundaries = value

    @property
    def show_3d_disks(self):
        return self._plugin.show_3d_disks

    @show_3d_disks.setter
    def show_3d_disks(self, value):
        self._plugin.show_3d_disks = value

    @property
    def show_3d_arcs(self):
        return self._plugin.show_3d_arcs

    @show_3d_arcs.setter
    def show_3d_arcs(self, value):
        self._plugin.show_3d_arcs = value

    @property
    def show_envelope_debug(self):
        return self._plugin.show_envelope_debug

    @show_envelope_debug.setter
    def show_envelope_debug(self, value):
        self._plugin.show_envelope_debug = value

    @property
    def system_state(self):
        return self._plugin.instructor.system_state

    def get_axis_authority(self, axis_key):
        return self._plugin.instructor.control_assignment[axis_key]

    def get_axis_sync_locked(self, axis_key):
        return self._plugin.instructor.sync_locked[axis_key]

    def get_drift_m(self):
        state = self._plugin.get_current_state()
        return math.sqrt(
            (state["x"] - self._plugin.controller.target_x) ** 2
            + (state["z"] - self._plugin.controller.target_z) ** 2
        )

    @property
    def hover_safety_radius(self):
        return self._plugin.instructor.hover_safety_radius

    @property
    def hover_soft_radius(self):
        return self._plugin.instructor.hover_soft_radius

    def get_y_agl(self):
        return xp.getDataf(self._plugin.dref_y_agl) if self._plugin.dref_y_agl else 10.0

    def get_gains(self):
        return self._plugin.controller.get_gains()

    def set_gains(self, gains):
        self._plugin.controller.set_gains(gains)

    def save_gains(self):
        self._plugin.save_gains()

    def load_gains(self):
        self._plugin.load_gains()

    @property
    def target_x(self):
        return self._plugin.controller.target_x

    @property
    def target_y(self):
        return self._plugin.controller.target_y

    @property
    def target_z(self):
        return self._plugin.controller.target_z

    @property
    def target_psi(self):
        return self._plugin.controller.target_psi

    def adjust_hover_target(self, forward=0.0, right=0.0, up=0.0, heading=0.0):
        self._plugin.adjust_hover_target(forward, right, up, heading)

    def reset_target_to_current(self):
        state = self._plugin.get_current_state()
        curr_collective = xp.getDataf(self._plugin.dref_prop_ratio_all)
        self._plugin.controller.engage(
            state["x"], state["y"], state["z"], state["psi"], curr_collective
        )
        self._plugin.instructor.drift_recovery_active = False
        self._plugin.instructor.original_target_x = None
        self._plugin.instructor.original_target_y = None
        self._plugin.instructor.original_target_z = None
        self._plugin.instructor.override_target_x = None
        self._plugin.instructor.override_target_y = None
        self._plugin.instructor.override_target_z = None
        self._plugin.instructor.set_hud_caption(
            "HOVER TARGET RESET TO CURRENT POSITION"
        )


class PythonInterface(object):
    """X-Plane Plugin Interface class."""

    def __init__(self):
        """Initializes the PythonInterface plugin instance."""
        self.version = "2.1.50"
        self.Name = "Helicopter Virtual Flight Instructor"
        self.Sig = "hu.lecz.helicopter.instructor"
        self.Desc = (
            "Version {self.version} - An intelligent virtual flight instructor that helps you learn "
            f"how to hover a helicopter."
        )

        # Core VFI (Virtual Flight Instructor) States
        self.ap_enabled = False
        self.controller = helicopter_control.HoverAutopilotController()
        self.instructor = virtual_instructor.VirtualInstructor()
        self.metrics = metrics.PerformanceMetricsEvaluator()

        # Directories and Managers
        self.plugin_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "helicopter_instructor"
        )
        self.audio = audio.AudioManager(self.plugin_dir)
        self.audio_queue = []
        self.audio_playback_timer = 0.0
        self.last_played_sound = None
        self.graphics = graphics.GraphicsAssetManager(self.plugin_dir)
        self.ui_controller = PluginUIController(self)

        # Custom view state flags
        self.show_3d_boundaries = True
        self.show_3d_disks = True
        self.show_3d_arcs = True
        self.show_hud = True
        self.show_alt_bar = True
        self.show_envelope_debug = False

        # Configuration
        self.use_flaps_collective = True

        # UI & Menu handles
        self.menu_id = None
        self.window = None
        self.hud_window = None
        self.alt_bar_window = None

        # Dataref handles
        self.dref_local_x = None
        self.dref_local_y = None
        self.dref_local_z = None
        self.dref_local_vx = None
        self.dref_local_vy = None
        self.dref_local_vz = None
        self.dref_phi = None
        self.dref_theta = None
        self.dref_psi = None
        self.dref_P = None
        self.dref_Q = None
        self.dref_R = None
        self.dref_y_agl = None

        self.dref_override_roll = None
        self.dref_override_pitch = None
        self.dref_override_yaw = None
        self.dref_yoke_pitch = None
        self.dref_yoke_roll = None
        self.dref_yoke_heading = None

        self.dref_prop_ratio_all = None
        self.dref_override_collective = None
        self.dref_prop_ratio = None
        self.dref_override_throttles = None
        self.dref_flap_ratio = None
        self.dref_paused = None
        self.dref_g_side = None

        # Hardware joystick input datarefs (Anti-Jerk Scanning)
        self.dref_joystick_axis_assignments = None
        self.dref_joy_mapped_axis_value = None

        # Cache of last outputs for display
        self.last_commands = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "collective": 0.5,
            "debug": {
                "fwd_err": 0.0,
                "lat_err": 0.0,
                "alt_err": 0.0,
                "yaw_err": 0.0,
                "target_v_fwd": 0.0,
                "target_v_lat": 0.0,
                "target_v_vert": 0.0,
                "target_pitch": 0.0,
                "target_roll": 0.0,
                "v_fwd": 0.0,
                "v_lat": 0.0,
            },
        }

        self.last_hardware_inputs = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "collective": 0.5,
        }

        self.last_final_commands = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "collective": 0.5,
        }

        # Raw hardware scan diagnostics
        self.last_count_assign = 0
        self.last_count_mapped = 0
        self.last_raw_assignments = []
        self.last_raw_mapped_values = []

        # Custom command handles
        self.cmd_instructor_toggle = None
        self.cmd_hud_toggle = None
        self.cmd_alt_bar_toggle = None
        self.cmd_next_phase = None
        self.cmd_prev_phase = None
        self.cmd_handoff_trigger = None
        self.cmd_hover_forward = None
        self.cmd_hover_backward = None
        self.cmd_hover_left = None
        self.cmd_hover_right = None
        self.cmd_hover_up = None
        self.cmd_hover_down = None
        self.cmd_hover_heading_left = None
        self.cmd_hover_heading_right = None
        self.cmd_hover_reset_current = None

    def XPluginStart(self):
        """Called by X-Plane when the plugin is started."""
        # 1. Find all required datarefs
        self.dref_local_x = xp.findDataRef("sim/flightmodel/position/local_x")
        self.dref_local_y = xp.findDataRef("sim/flightmodel/position/local_y")
        self.dref_local_z = xp.findDataRef("sim/flightmodel/position/local_z")
        self.dref_local_vx = xp.findDataRef("sim/flightmodel/position/local_vx")
        self.dref_local_vy = xp.findDataRef("sim/flightmodel/position/local_vy")
        self.dref_local_vz = xp.findDataRef("sim/flightmodel/position/local_vz")
        self.dref_phi = xp.findDataRef("sim/flightmodel/position/phi")
        self.dref_theta = xp.findDataRef("sim/flightmodel/position/theta")
        self.dref_psi = xp.findDataRef("sim/flightmodel/position/psi")
        self.dref_P = xp.findDataRef("sim/flightmodel/position/P")
        self.dref_Q = xp.findDataRef("sim/flightmodel/position/Q")
        self.dref_R = xp.findDataRef("sim/flightmodel/position/R")
        self.dref_y_agl = xp.findDataRef("sim/flightmodel/position/y_agl")

        self.dref_override_roll = xp.findDataRef(
            "sim/operation/override/override_joystick_roll"
        )
        self.dref_override_pitch = xp.findDataRef(
            "sim/operation/override/override_joystick_pitch"
        )
        self.dref_override_yaw = xp.findDataRef(
            "sim/operation/override/override_joystick_heading"
        )
        self.dref_yoke_pitch = xp.findDataRef("sim/cockpit2/controls/yoke_pitch_ratio")
        self.dref_yoke_roll = xp.findDataRef("sim/cockpit2/controls/yoke_roll_ratio")
        self.dref_yoke_heading = xp.findDataRef(
            "sim/cockpit2/controls/yoke_heading_ratio"
        )

        self.dref_prop_ratio_all = xp.findDataRef(
            "sim/cockpit2/engine/actuators/prop_ratio_all"
        )
        self.dref_override_collective = xp.findDataRef(
            "sim/operation/override/override_prop_pitch"
        )
        self.dref_prop_ratio = xp.findDataRef(
            "sim/cockpit2/engine/actuators/prop_ratio"
        )
        self.dref_override_throttles = xp.findDataRef(
            "sim/operation/override/override_throttles"
        )
        self.dref_flap_ratio = xp.findDataRef(
            "sim/cockpit2/controls/flap_handle_request_ratio"
        )
        self.dref_paused = xp.findDataRef("sim/time/paused")
        self.dref_g_side = xp.findDataRef("sim/flightmodel/forces/g_side")

        # Raw hardware input scanning datarefs
        self.dref_joystick_axis_assignments = xp.findDataRef(
            "sim/joystick/joystick_axis_assignments"
        )
        self.dref_joy_mapped_axis_value = xp.findDataRef(
            "sim/joystick/joy_mapped_axis_value"
        )

        # 2. Try loading PID gains from JSON
        self.load_gains()

        # 3. Create the ImGui control window
        # Positioning: left=150, top=750, right=650, bottom=250 (500x500 window)
        self.window = xp_imgui.Window(
            left=150,
            top=750,
            right=650,
            bottom=250,
            visible=1,
            draw=self.draw_window,
            refCon=self,
        )
        self.window.setTitle("Helicopter Flight Instructor")

        # 4. Create the menu item
        def menu_handler(menu_refcon, item_refcon):
            if item_refcon == "toggle_window":
                curr_visible = xp.getWindowIsVisible(self.window.windowID)
                xp.setWindowIsVisible(self.window.windowID, 1 - curr_visible)

        self.menu_id = xp.createMenu(
            "Helicopter Instructor", None, 0, menu_handler, None
        )
        xp.appendMenuItem(self.menu_id, "Toggle Control Panel", "toggle_window")

        # 5. Register flight loop callback at 50Hz (every 0.02s)
        xp.registerFlightLoopCallback(self.flight_loop_callback, 0.02, self)

        # 5b. Create draggable HUD Window
        left_scr, top_scr, right_scr, bottom_scr = xp.getScreenBoundsGlobal()
        center_scr_x = (left_scr + right_scr) / 2.0

        init_w = 550
        init_h = 270
        init_left = int(center_scr_x - init_w / 2.0)
        init_right = int(center_scr_x + init_w / 2.0)
        init_top = int(top_scr - 30)
        init_bottom = int(init_top - init_h)

        def draw_hud_cb(window_id, refcon):
            self.draw_hud(window_id, refcon)

        def dummy_mouse_cb(window_id, x, y, is_down, refcon):
            return 0

        def dummy_key_cb(window_id, key, flags, v_key, refcon, losing_focus):
            pass

        def dummy_cursor_cb(window_id, x, y, refcon):
            return xp.CursorDefault

        def dummy_wheel_cb(window_id, x, y, wheel, clicks, refcon):
            return 0

        self.hud_window = xp.createWindowEx(
            [
                init_left,  # 1. Left coordinate (in boxels)
                init_top,  # 2. Top coordinate (in boxels)
                init_right,  # 3. Right coordinate (in boxels)
                init_bottom,  # 4. Bottom coordinate (in boxels)
                1 if self.show_hud else 0,  # 5. Visibility state
                draw_hud_cb,  # 6. Window drawing callback
                dummy_mouse_cb,  # 7. Mouse click callback
                dummy_key_cb,  # 8. Keyboard key callback
                dummy_cursor_cb,  # 9. Mouse cursor callback
                dummy_wheel_cb,  # 10. Mouse scroll callback
                self,  # 11. Refcon custom pointer
                xp.WindowDecorationNone,  # 12. Completely borderless
                xp.WindowLayerFloatingWindows,  # 13. Floating window layer
                None,  # 14. Right-click callback
            ]
        )

        # 5c. Create standalone vertical altitude safety bar window
        init_alt_w = 80
        init_alt_h = 500
        init_alt_right = int(right_scr - 50)
        init_alt_left = int(init_alt_right - init_alt_w)
        center_scr_y = (top_scr + bottom_scr) / 2.0
        init_alt_top = int(center_scr_y + init_alt_h / 2.0)
        init_alt_bottom = int(init_alt_top - init_alt_h)

        def draw_alt_bar_cb(window_id, refcon):
            self.draw_alt_bar(window_id, refcon)

        self.alt_bar_window = xp.createWindowEx(
            [
                init_alt_left,  # 1. Left coordinate (in boxels)
                init_alt_top,  # 2. Top coordinate (in boxels)
                init_alt_right,  # 3. Right coordinate (in boxels)
                init_alt_bottom,  # 4. Bottom coordinate (in boxels)
                1 if self.show_alt_bar else 0,  # 5. Visibility state
                draw_alt_bar_cb,  # 6. Window drawing callback
                dummy_mouse_cb,  # 7. Mouse click callback
                dummy_key_cb,  # 8. Keyboard key callback
                dummy_cursor_cb,  # 9. Mouse cursor callback
                dummy_wheel_cb,  # 10. Mouse scroll callback
                self,  # 11. Refcon custom pointer
                xp.WindowDecorationNone,  # 12. Completely borderless
                xp.WindowLayerFloatingWindows,  # 13. Floating window layer
                None,  # 14. Right-click callback
            ]
        )

        # 6. Create custom commands for key/button mapping
        self.cmd_instructor_toggle = xp.createCommand(
            "helicopter_instructor/instructor_toggle",
            "Helicopter Instructor: Toggle Master Engage",
        )
        self.cmd_hud_toggle = xp.createCommand(
            "helicopter_instructor/hud_toggle", "Helicopter Instructor: Toggle HUD"
        )
        self.cmd_alt_bar_toggle = xp.createCommand(
            "helicopter_instructor/alt_bar_toggle",
            "Helicopter Instructor: Toggle Altitude Bar",
        )
        self.cmd_next_phase = xp.createCommand(
            "helicopter_instructor/next_phase",
            "Helicopter Instructor: Advance to Next Lesson Phase",
        )
        self.cmd_prev_phase = xp.createCommand(
            "helicopter_instructor/prev_phase",
            "Helicopter Instructor: Return to Previous Lesson Phase",
        )
        self.cmd_handoff_trigger = xp.createCommand(
            "helicopter_instructor/handoff_trigger",
            "Helicopter Instructor: Trigger Control Handoff",
        )
        self.cmd_hover_forward = xp.createCommand(
            "helicopter_instructor/hover_forward",
            "Helicopter Instructor: Shift Hover Target Forward 1m",
        )
        self.cmd_hover_backward = xp.createCommand(
            "helicopter_instructor/hover_backward",
            "Helicopter Instructor: Shift Hover Target Backward 1m",
        )
        self.cmd_hover_left = xp.createCommand(
            "helicopter_instructor/hover_left",
            "Helicopter Instructor: Shift Hover Target Left 1m",
        )
        self.cmd_hover_right = xp.createCommand(
            "helicopter_instructor/hover_right",
            "Helicopter Instructor: Shift hover target right 1m",
        )
        self.cmd_hover_up = xp.createCommand(
            "helicopter_instructor/hover_up",
            "Helicopter Instructor: Increase hover target altitude 0.5m",
        )
        self.cmd_hover_down = xp.createCommand(
            "helicopter_instructor/hover_down",
            "Helicopter Instructor: Decrease hover target altitude 0.5m",
        )
        self.cmd_hover_heading_left = xp.createCommand(
            "helicopter_instructor/hover_heading_left",
            "Helicopter Instructor: Adjust hover target heading left 5 deg",
        )
        self.cmd_hover_heading_right = xp.createCommand(
            "helicopter_instructor/hover_heading_right",
            "Helicopter Instructor: Adjust hover target heading right 5 deg",
        )
        self.cmd_hover_reset_current = xp.createCommand(
            "helicopter_instructor/hover_set_current",
            "Helicopter Instructor: Set the current location as the hover target",
        )

        # Preload all audio assets into memory cache to prevent runtime disk stutters
        try:
            self.audio.preload_sounds()
        except Exception as preload_err:
            xp.log(f"Failed to preload audio assets: {str(preload_err)}")

        xp.log("Plugin started successfully.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        """Called by X-Plane when the plugin is stopped."""
        # 1. Unregister flight loop callback and destroy HUD window
        xp.unregisterFlightLoopCallback(self.flight_loop_callback, self)
        if self.hud_window:
            xp.destroyWindow(self.hud_window)
        if self.alt_bar_window:
            xp.destroyWindow(self.alt_bar_window)

        # 2. Make sure overrides are released
        self.release_all_overrides()

        # 3. Destroy UI Window and Menu
        if self.window:
            self.window.delete()
        if self.menu_id:
            xp.destroyMenu(self.menu_id)

        xp.log("Plugin stopped.")

    def XPluginEnable(self):
        """Called by X-Plane when the plugin is enabled."""
        xp.log("XPluginEnable called.")
        # Register command handlers
        if self.cmd_instructor_toggle:
            xp.registerCommandHandler(
                self.cmd_instructor_toggle, self.cmd_handler_instructor_toggle, 1, None
            )
        if self.cmd_hud_toggle:
            xp.registerCommandHandler(
                self.cmd_hud_toggle, self.cmd_handler_hud_toggle, 1, None
            )
        if self.cmd_alt_bar_toggle:
            xp.registerCommandHandler(
                self.cmd_alt_bar_toggle, self.cmd_handler_alt_bar_toggle, 1, None
            )
        if self.cmd_next_phase:
            xp.registerCommandHandler(
                self.cmd_next_phase, self.cmd_handler_next_phase, 1, None
            )
        if self.cmd_prev_phase:
            xp.registerCommandHandler(
                self.cmd_prev_phase, self.cmd_handler_prev_phase, 1, None
            )
        if self.cmd_handoff_trigger:
            xp.registerCommandHandler(
                self.cmd_handoff_trigger, self.cmd_handler_handoff_trigger, 1, None
            )

        def reg_cmd(cmd, handler):
            if cmd:
                xp.registerCommandHandler(cmd, handler, 1, None)

        reg_cmd(self.cmd_hover_forward, self.cmd_handler_hover_forward)
        reg_cmd(self.cmd_hover_backward, self.cmd_handler_hover_backward)
        reg_cmd(self.cmd_hover_left, self.cmd_handler_hover_left)
        reg_cmd(self.cmd_hover_right, self.cmd_handler_hover_right)
        reg_cmd(self.cmd_hover_up, self.cmd_handler_hover_up)
        reg_cmd(self.cmd_hover_down, self.cmd_handler_hover_down)
        reg_cmd(self.cmd_hover_heading_left, self.cmd_handler_hover_heading_left)
        reg_cmd(self.cmd_hover_heading_right, self.cmd_handler_hover_heading_right)
        reg_cmd(self.cmd_hover_reset_current, self.cmd_handler_hover_reset_current)

        # Load and instantiate 3D Vulkan/Metal-native wireframe objects
        self.load_objects()

        return 1

    def XPluginDisable(self):
        """Called by X-Plane when the plugin is disabled."""
        xp.log("XPluginDisable called.")
        # Release overrides when disabled
        self.release_all_overrides()
        self.ap_enabled = False

        # Unload and destroy 3D instances
        try:
            self.graphics.unload_objects()
        except Exception as err:
            xp.log(f"Failed to clean up 3D instances: {str(err)}")

        # Unregister command handlers
        if self.cmd_instructor_toggle:
            xp.unregisterCommandHandler(
                self.cmd_instructor_toggle, self.cmd_handler_instructor_toggle, 1, None
            )
        if self.cmd_hud_toggle:
            xp.unregisterCommandHandler(
                self.cmd_hud_toggle, self.cmd_handler_hud_toggle, 1, None
            )
        if self.cmd_alt_bar_toggle:
            xp.unregisterCommandHandler(
                self.cmd_alt_bar_toggle, self.cmd_handler_alt_bar_toggle, 1, None
            )
        if self.cmd_next_phase:
            xp.unregisterCommandHandler(
                self.cmd_next_phase, self.cmd_handler_next_phase, 1, None
            )
        if self.cmd_prev_phase:
            xp.unregisterCommandHandler(
                self.cmd_prev_phase, self.cmd_handler_prev_phase, 1, None
            )
        if self.cmd_handoff_trigger:
            xp.unregisterCommandHandler(
                self.cmd_handoff_trigger, self.cmd_handler_handoff_trigger, 1, None
            )

        def unreg_cmd(cmd, handler):
            if cmd:
                xp.unregisterCommandHandler(cmd, handler, 1, None)

        unreg_cmd(self.cmd_hover_forward, self.cmd_handler_hover_forward)
        unreg_cmd(self.cmd_hover_backward, self.cmd_handler_hover_backward)
        unreg_cmd(self.cmd_hover_left, self.cmd_handler_hover_left)
        unreg_cmd(self.cmd_hover_right, self.cmd_handler_hover_right)
        unreg_cmd(self.cmd_hover_up, self.cmd_handler_hover_up)
        unreg_cmd(self.cmd_hover_down, self.cmd_handler_hover_down)
        unreg_cmd(self.cmd_hover_heading_left, self.cmd_handler_hover_heading_left)
        unreg_cmd(self.cmd_hover_heading_right, self.cmd_handler_hover_heading_right)
        unreg_cmd(self.cmd_hover_reset_current, self.cmd_handler_hover_reset_current)

    def release_all_overrides(self):
        """Releases all overridden joystick and collective datarefs in X-Plane."""
        xp.setDatai(self.dref_override_roll, 0)
        xp.setDatai(self.dref_override_pitch, 0)
        xp.setDatai(self.dref_override_yaw, 0)
        if self.dref_override_collective:
            xp.setDatai(self.dref_override_collective, 0)
        if self.dref_override_throttles:
            xp.setDatai(self.dref_override_throttles, 0)

    def get_current_state(self):
        """Reads and returns the current aircraft flight state dictionary."""
        g_side_val = 0.0
        if self.dref_g_side:
            g_side_val = xp.getDataf(self.dref_g_side)
        return {
            "x": xp.getDatad(self.dref_local_x),
            "y": xp.getDatad(self.dref_local_y),
            "z": xp.getDatad(self.dref_local_z),
            "vx": xp.getDataf(self.dref_local_vx),
            "vy": xp.getDataf(self.dref_local_vy),
            "vz": xp.getDataf(self.dref_local_vz),
            "phi": xp.getDataf(self.dref_phi),
            "theta": xp.getDataf(self.dref_theta),
            "psi": xp.getDataf(self.dref_psi),
            "P": xp.getDataf(self.dref_P),
            "Q": xp.getDataf(self.dref_Q),
            "R": xp.getDataf(self.dref_R),
            "g_side": g_side_val,
        }

    def get_hardware_inputs(self):
        """Reads raw physical hardware stick deflections."""
        assignments = []
        count_assign = xp.getDatavi(self.dref_joystick_axis_assignments, assignments)
        assignments = assignments[:count_assign]

        mapped_values = []
        count_mapped = xp.getDatavf(self.dref_joy_mapped_axis_value, mapped_values)
        mapped_values = mapped_values[:count_mapped]

        # Save raw values to self for HUD dynamic engineering panel
        self.last_count_assign = count_assign
        self.last_count_mapped = count_mapped
        self.last_raw_assignments = list(assignments)
        self.last_raw_mapped_values = list(mapped_values)

        # Log warning if no axes are detected (throttled)
        if count_assign == 0 or count_mapped == 0:
            if not hasattr(self, "_log_throttle_counter"):
                self._log_throttle_counter = 0
            self._log_throttle_counter += 1
            if self._log_throttle_counter % 250 == 1:
                xp.log(
                    f"Joystick Warning: count_assign={count_assign}, "
                    f"count_mapped={count_mapped}. "
                    "Check X-Plane calibration."
                )

        hw = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "collective": 0.5}

        # Assignments mapping: 1=Pitch, 2=Roll, 3=Yaw, 5=Collective
        limit = min(len(assignments), len(mapped_values))
        for i in range(limit):
            func = assignments[i]
            val = mapped_values[i]
            if func == 1:
                if abs(val) > abs(hw["pitch"]):
                    hw["pitch"] = val
            elif func == 2:
                if abs(val) > abs(hw["roll"]):
                    hw["roll"] = val
            elif func == 3:
                if abs(val) > abs(hw["yaw"]):
                    hw["yaw"] = val
            elif func == 5:
                hw["collective"] = (val + 1.0) / 2.0

        # Smart per-axis fallback if assignments are not detected in X-Plane DataRef
        # Pitch: Fall back to standard Axis 1
        if hw["pitch"] == 0.0 and len(mapped_values) > 1:
            hw["pitch"] = mapped_values[1]

        # Roll: Fall back to standard Axis 2
        if hw["roll"] == 0.0 and len(mapped_values) > 2:
            hw["roll"] = mapped_values[2]

        # Yaw (Pedals): Fall back to standard Axis 3
        if hw["yaw"] == 0.0 and len(mapped_values) > 3:
            hw["yaw"] = mapped_values[3]

        # Collective: Always use the physical flaps axis input for collective control
        if self.use_flaps_collective:
            flap_input = xp.getDataf(self.dref_flap_ratio)
            hw["collective"] = max(0.0, min(1.0, flap_input))

        return hw

    def flight_loop_callback(self, last_call, elapsed_time, counter, ref_con):
        """Core flight loop callback executing control updates at 50Hz."""
        # 0. Check if simulator is paused
        if self.dref_paused and xp.getDatai(self.dref_paused) != 0:
            return 0.02

        # 1. Read aircraft state
        state = self.get_current_state()
        y_agl = xp.getDataf(self.dref_y_agl) if self.dref_y_agl else 10.0

        # Parse telemetry package
        telemetry = {
            "phi": state["phi"],
            "theta": state["theta"],
            "psi": state["psi"],
            "P": state["P"],
            "Q": state["Q"],
            "R": state["R"],
            "vx": state["vx"],
            "vy": state["vy"],
            "vz": state["vz"],
            "y_agl": y_agl,
            "x": state["x"],
            "y": state["y"],
            "z": state["z"],
            "target_x": self.controller.target_x,
            "target_y": self.controller.target_y,
            "target_z": self.controller.target_z,
            "target_psi": self.controller.target_psi,
        }

        if self.ap_enabled:
            # Sanitize dt to prevent integrator spikes during unpauses/reloads
            dt = last_call if (0.0 < last_call < 0.1) else 0.02

            # --- PRE-STEP A: Snap autopilot target to override position ---
            # This MUST run before controller.update() so that the PID cascade
            # always sees the correct hover target.  Running it after Step A
            # would mean the autopilot computes one full frame of commands
            # against a stale position error the instant an override fires,
            # producing a violent attitude jolt.
            if self.instructor.drift_recovery_active:
                self.controller.target_x = self.instructor.override_target_x
                if self.instructor.override_target_y is not None:
                    self.controller.target_y = self.instructor.override_target_y
                self.controller.target_z = self.instructor.override_target_z
            elif self.instructor.was_drift_recovery_active:
                # Recovery interpolation has finished: restore original target.
                self.controller.target_x = self.instructor.original_target_x
                if self.instructor.original_target_y is not None:
                    self.controller.target_y = self.instructor.original_target_y
                self.controller.target_z = self.instructor.original_target_z
                self.instructor.was_drift_recovery_active = False
                self.instructor.original_target_x = None
                self.instructor.original_target_y = None
                self.instructor.original_target_z = None

            # --- STEP A: Calculate stable VFI autopilot commands ---
            # To ensure stable outputs are always calculated for all axes,
            # we temporarily force all controller active flags to True.
            self.controller.roll_active = True
            self.controller.pitch_active = True
            self.controller.yaw_active = True
            self.controller.collective_active = True

            vfi_outputs = self.controller.update(dt, state)
            vfi_inputs = {
                "roll": vfi_outputs["roll"],
                "pitch": vfi_outputs["pitch"],
                "yaw": vfi_outputs["yaw"],
                "collective": vfi_outputs["collective"],
            }
            self.last_commands = vfi_outputs

            # --- STEP B: Read student's hardware inputs ---
            hardware_inputs = self.get_hardware_inputs()
            self.last_hardware_inputs = hardware_inputs

            # --- STEP C: Run VFI State Machine ---
            final_commands = self.instructor.update(
                dt, telemetry, hardware_inputs, vfi_inputs
            )
            self.last_final_commands = final_commands

            curr_state = self.instructor.system_state
            curr_phase = self.instructor.phase

            # Initialize tracking variables on first loop
            if not hasattr(self, "last_system_state"):
                self.last_system_state = curr_state
            if not hasattr(self, "last_phase"):
                self.last_phase = curr_phase

            # (PID reset is handled below, after STEP C4 re-read.)

            # --- STEP C2: Run Student Performance Metrics ---
            is_student_flying = curr_state == "STUDENT_FLIGHT"
            self.metrics.update(
                dt, telemetry, hardware_inputs, is_student_flying, curr_phase
            )

            # Feed current envelope grade back to instructor so that
            # maybe_advance_phase() can track Excellent duration.
            self.instructor.last_envelope = self.metrics.envelope

            # --- STEP C3: Play Pending Spoken Metrics Cues ---
            while True:
                sound_to_play = self.metrics.pop_audio_queue()
                if sound_to_play is None:
                    break
                self.play_sound(sound_to_play)

            # --- STEP C4: Handle automatic phase progression ---
            # transition_pending is set by VirtualInstructor.maybe_advance_phase()
            # after the student holds an Excellent rating for 30 seconds.
            auto_phase_transition = False
            if self.instructor.transition_pending:
                auto_phase_transition = True
                self.instructor.transition_pending = False
                next_phase = self.instructor.transition_target_phase
                is_final = self.instructor.training_complete

                # 1. Take back full VFI authority (clears student axis assignments).
                self.instructor.system_state = "VFI_FLIGHT"
                for axis in self.instructor.control_assignment:
                    self.instructor.control_assignment[axis] = "VFI"
                    self.instructor.sync_locked[axis] = False

                if is_final:
                    # 2a. Training complete — no next phase, so skip the
                    # transition jingle and play only the completion cue.
                    self.play_sound(SOUND_TRAINING_COMPLETE, clear_queue=True)
                else:
                    # 2b. Play "Phase transition.wav" then advance to the
                    # next phase and queue its intro audio.
                    self.play_sound(SOUND_PHASE_TRANSITION, clear_queue=True)
                    self.instructor.phase = next_phase
                    intro_sound = SOUND_PHASE_INTRO_TEMPLATE.format(next_phase)
                    self.play_sound(intro_sound)

                    # 3. Initiate the hand-off to the student for the new
                    #    phase.  This sets the state to SYNCING, which will
                    #    eventually trigger the normal "Get ready" /
                    #    "You have …" cues.
                    self.instructor.initiate_handoff()

            # Re-read state/phase after auto-transition may have changed them

            curr_state = self.instructor.system_state
            curr_phase = self.instructor.phase

            # --- Reset cyclic PIDs on any STUDENT_FLIGHT → * transition ---
            # Whenever the VFI reclaims cyclic authority from the student,
            # the position/velocity/attitude PID cascade may hold wound-up
            # integrals accumulated during student flight, producing a jolt
            # on the first VFI-commanded frame.  Resetting here covers all
            # three transition paths:
            #   • Safety override  (state set inside instructor.update())
            #   • Manual phase change  (command handler fired between frames)
            #   • Automatic phase advance  (state set inside STEP C4)
            # Placing the check after the STEP C4 re-read means curr_state
            # already reflects any within-frame state change, while
            # last_system_state always holds the previous frame's value.
            if (
                self.last_system_state == "STUDENT_FLIGHT"
                and curr_state != "STUDENT_FLIGHT"
            ):
                self.controller.reset_position_hold_pids()

            # Detect state and phase transitions to play audio announcements.
            # Skip if this was an automatic phase transition (audio already
            # scheduled above).
            phase_changed = curr_phase != self.last_phase
            state_changed = curr_state != self.last_system_state

            if not auto_phase_transition:
                if phase_changed:
                    # Manual phase change: instructor takes control and
                    # explains the new phase via its intro audio.
                    if curr_state in ["STUDENT_FLIGHT", "SYNCING"]:
                        self.play_sound(SOUND_I_HAVE_CONTROL, clear_queue=True)
                    self.play_sound(SOUND_PHASE_INTRO_TEMPLATE.format(curr_phase))
                elif state_changed:
                    if curr_state == "SYNCING":
                        if self.last_system_state == "STUDENT_FLIGHT":
                            self.play_sound(SOUND_I_HAVE_CONTROL, clear_queue=True)
                        else:
                            self.play_sound(SOUND_GET_READY)
                    elif curr_state == "STUDENT_FLIGHT":
                        phase = self.instructor.phase
                        if phase == PHASE_PEDALS_ONLY:
                            self.play_sound(SOUND_YOU_HAVE_PEDALS)
                        elif phase == PHASE_COLLECTIVE_ONLY:
                            self.play_sound(SOUND_YOU_HAVE_COLLECTIVE)
                        elif phase == PHASE_COLLECTIVE_PEDALS:
                            self.play_sound(SOUND_YOU_HAVE_COLLECTIVE_PEDALS)
                        elif phase == PHASE_CYCLIC_ONLY:
                            self.play_sound(SOUND_YOU_HAVE_CYCLIC)
                        elif phase == PHASE_CYCLIC_PEDALS:
                            self.play_sound(SOUND_YOU_HAVE_CYCLIC_PEDALS)
                        elif phase == PHASE_ALL_CONTROLS:
                            self.play_sound(SOUND_YOU_HAVE_ALL)
                    elif curr_state == "OVERRIDE":
                        self.play_sound(SOUND_I_HAVE_CONTROL, clear_queue=True)

            # Update persistent tracking state
            self.last_system_state = curr_state
            self.last_phase = curr_phase

            # --- STEP D: Perform Intelligent Control Routing ---
            # 1. Roll
            if self.instructor.control_assignment["roll"] == "STUDENT":
                xp.setDatai(self.dref_override_roll, 0)
            else:
                xp.setDatai(self.dref_override_roll, 1)
                xp.setDataf(self.dref_yoke_roll, final_commands["roll"])

            # 2. Pitch
            if self.instructor.control_assignment["pitch"] == "STUDENT":
                xp.setDatai(self.dref_override_pitch, 0)
            else:
                xp.setDatai(self.dref_override_pitch, 1)
                xp.setDataf(self.dref_yoke_pitch, final_commands["pitch"])

            # 3. Yaw
            if self.instructor.control_assignment["yaw"] == "STUDENT":
                xp.setDatai(self.dref_override_yaw, 0)
            else:
                xp.setDatai(self.dref_override_yaw, 1)
                xp.setDataf(self.dref_yoke_heading, final_commands["yaw"])

            # 4. Collective
            # Determine if collective injection is active (VFI is flying,
            # or flaps fallback is checked)
            inject_collective = (
                self.instructor.control_assignment["collective"] == "VFI"
                or self.use_flaps_collective
            )

            if inject_collective:
                coll_val = final_commands["collective"]
                props = [coll_val] * 8
                xp.setDatavf(self.dref_prop_ratio, props, 0, 8)
                xp.setDataf(self.dref_prop_ratio_all, coll_val)

            # Keep native governor active
            xp.setDatai(self.dref_override_collective, 0)
            xp.setDatai(self.dref_override_throttles, 0)

        else:
            # Instructor is disengaged -> Scan hardware inputs and cockpit
            # yoke values to keep HUD live!
            hardware_inputs = self.get_hardware_inputs()
            self.last_hardware_inputs = hardware_inputs

            roll_val = (
                xp.getDataf(self.dref_yoke_roll)
                if self.dref_yoke_roll
                else hardware_inputs["roll"]
            )
            pitch_val = (
                xp.getDataf(self.dref_yoke_pitch)
                if self.dref_yoke_pitch
                else hardware_inputs["pitch"]
            )
            yaw_val = (
                xp.getDataf(self.dref_yoke_heading)
                if self.dref_yoke_heading
                else hardware_inputs["yaw"]
            )
            coll_val = (
                xp.getDataf(self.dref_prop_ratio_all)
                if self.dref_prop_ratio_all
                else hardware_inputs["collective"]
            )

            self.last_final_commands = {
                "roll": roll_val,
                "pitch": pitch_val,
                "yaw": yaw_val,
                "collective": coll_val,
            }

            self.last_commands = {
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
                "collective": 0.5,
            }

            self.release_all_overrides()

            # --- Reset Performance Metrics Evaluator ---
            self.metrics.update(
                0.02, telemetry, hardware_inputs, False, self.instructor.phase
            )

        # --- Update 3D Object Instances ---
        try:
            # 2. Update Disks and Arcs centered on the hover target
            show_any = self.show_3d_boundaries and self.ap_enabled and self.controller
            if show_any:
                tx = (
                    self.instructor.original_target_x
                    if self.instructor.original_target_x is not None
                    else self.controller.target_x
                )
                tz = (
                    self.instructor.original_target_z
                    if self.instructor.original_target_z is not None
                    else self.controller.target_z
                )
                ground_y = state["y"] - y_agl
                ty = ground_y
                t_heading = self.controller.target_psi
            else:
                tx, ty, tz = 0.0, -9999.0, 0.0
                t_heading = 0.0

            draw_disks = (
                show_any
                and self.show_3d_disks
                and (self.instructor.phase >= PHASE_CYCLIC_ONLY)
            )
            draw_arcs = (
                show_any
                and self.show_3d_arcs
                and (
                    self.instructor.phase
                    in (
                        PHASE_PEDALS_ONLY,
                        PHASE_COLLECTIVE_PEDALS,
                        PHASE_CYCLIC_PEDALS,
                        PHASE_ALL_CONTROLS,
                    )
                )
            )

            self.graphics.set_instance_positions(
                tx=tx,
                ty=ty,
                tz=tz,
                t_heading=t_heading,
                draw_disks=draw_disks,
                draw_arcs=draw_arcs,
            )

            # Dynamic visibility for standalone altitude bar window
            # Only show the altitude box when user is in control of collective
            if self.alt_bar_window:
                is_student_coll = self.ap_enabled and (
                    virtual_instructor.PHASE_CONFIGS[self.instructor.phase][
                        "collective"
                    ]
                    == "STUDENT"
                )
                active_visible = 1 if (self.show_alt_bar and is_student_coll) else 0
                if xp.getWindowIsVisible(self.alt_bar_window) != active_visible:
                    xp.setWindowIsVisible(self.alt_bar_window, active_visible)
        except Exception as inst_err:
            if not hasattr(self, "_inst_update_failed_logged"):
                self._inst_update_failed_logged = True
                xp.log(f"Failed to update 3D instances. Exception: {str(inst_err)}")

        # --- Run Sequential Audio Playback Queue ---
        # Spaced out playbacks by tracking length of files and adding a 0.3s pause.
        loop_dt = last_call if (0.0 < last_call < 0.1) else 0.02
        if self.audio_playback_timer > 0.0:
            self.audio_playback_timer -= loop_dt

        if self.audio_playback_timer <= 0.0 and self.audio_queue:
            sound_to_play = self.audio_queue.pop(0)
            duration_s = self.audio.play_sound(sound_to_play)
            self.last_played_sound = sound_to_play
            self.audio_playback_timer = duration_s + 0.3

        return 0.02

    def draw_window(self, window_id, ref_con):
        """ImGui Drawing callback for the Instructor Control Panel."""
        ui.draw_window(self.ui_controller, window_id, ref_con)

    def save_gains(self):
        """Saves current PID gains to a local JSON file."""
        gains = self.controller.get_gains()
        config.save_gains(self.plugin_dir, gains)

    def load_gains(self):
        """Loads PID gains from a local JSON file."""
        gains = config.load_gains(self.plugin_dir)
        if gains:
            self.controller.set_gains(gains)

    def XPluginReceiveMessage(self, in_from_who, in_message, in_param):
        """Called by X-Plane when a message is received by the plugin."""
        if in_message == MSG_PLANE_LOADED and in_param == PLANE_USER_IDX:
            self.load_gains()

    # --- COMMAND HANDLERS ---
    # Note: cmd_phase represents the X-Plane command event state (0 = Begin, 1 = Continue, 2 = End),
    # NOT the curriculum lesson phase.
    def cmd_handler_instructor_toggle(self, command_ref, cmd_phase, refcon):
        """Handler for Master Engage toggle command."""
        if cmd_phase == 0:  # Trigger exactly once on button press (CommandBegin)
            self.ui_controller.ap_enabled = not self.ap_enabled
        return 1

    def cmd_handler_hud_toggle(self, command_ref, cmd_phase, refcon):
        """Toggles the HUD visibility."""
        if cmd_phase == 0:
            self.ui_controller.show_hud = not self.show_hud
        return 1

    def cmd_handler_alt_bar_toggle(self, command_ref, cmd_phase, refcon):
        """Toggles the altitude bar visibility."""
        if cmd_phase == 0:
            self.ui_controller.show_alt_bar = not self.show_alt_bar
        return 1

    def cmd_handler_next_phase(self, command_ref, cmd_phase, refcon):
        """Advances the lesson to the next phase."""
        if cmd_phase == 0 and self.instructor.phase < PHASE_ALL_CONTROLS:
            self.instructor.set_phase(self.instructor.phase + 1)
        return 1

    def cmd_handler_prev_phase(self, command_ref, cmd_phase, refcon):
        """Regresses the lesson to the previous phase."""
        if cmd_phase == 0 and self.instructor.phase > PHASE_PEDALS_ONLY:
            self.instructor.set_phase(self.instructor.phase - 1)
        return 1

    def cmd_handler_handoff_trigger(self, command_ref, cmd_phase, refcon):
        """Initiates the control handoff sequence if VFI is engaged."""
        if cmd_phase == 0 and self.ap_enabled:
            self.instructor.initiate_handoff()
        return 1

    def cmd_handler_hover_forward(self, command_ref, cmd_phase, refcon):
        """Shifts hover target forward by 1 meter."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=1.0, right=0.0, up=0.0, heading=0.0)
        return 1

    def cmd_handler_hover_backward(self, command_ref, cmd_phase, refcon):
        """Shifts hover target backward by 1 meter."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=-1.0, right=0.0, up=0.0, heading=0.0)
        return 1

    def cmd_handler_hover_left(self, command_ref, cmd_phase, refcon):
        """Shifts hover target left by 1 meter."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=0.0, right=-1.0, up=0.0, heading=0.0)
        return 1

    def cmd_handler_hover_right(self, command_ref, cmd_phase, refcon):
        """Shifts hover target right by 1 meter."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=0.0, right=1.0, up=0.0, heading=0.0)
        return 1

    def cmd_handler_hover_up(self, command_ref, cmd_phase, refcon):
        """Increases hover target altitude by 0.5 meters."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=0.0, right=0.0, up=0.5, heading=0.0)
        return 1

    def cmd_handler_hover_down(self, command_ref, cmd_phase, refcon):
        """Decreases hover target altitude by 0.5 meters."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=0.0, right=0.0, up=-0.5, heading=0.0)
        return 1

    def cmd_handler_hover_heading_left(self, command_ref, cmd_phase, refcon):
        """Adjusts hover target heading left by 5 degrees."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=0.0, right=0.0, up=0.0, heading=-5.0)
        return 1

    def cmd_handler_hover_heading_right(self, command_ref, cmd_phase, refcon):
        """Adjusts hover target heading right by 5 degrees."""
        if cmd_phase == 0:
            self.adjust_hover_target(forward=0.0, right=0.0, up=0.0, heading=5.0)
        return 1

    def cmd_handler_hover_reset_current(self, command_ref, cmd_phase, refcon):
        """Resets hover target to current position."""
        if cmd_phase == 0:
            self.ui_controller.reset_target_to_current()
        return 1

    def adjust_hover_target(self, forward=0.0, right=0.0, up=0.0, heading=0.0):
        """Adjusts the hover location target relative to the current target heading/altitude."""
        # Convert target heading to radians for coordinate rotation
        psi_rad = math.radians(self.controller.target_psi)
        cos_psi = math.cos(psi_rad)
        sin_psi = math.sin(psi_rad)

        # local coordinate change:
        # delta_x (East) = forward * sin_psi + right * cos_psi
        # delta_z (South) = -forward * cos_psi + right * sin_psi
        delta_x = forward * sin_psi + right * cos_psi
        delta_z = -forward * cos_psi + right * sin_psi

        self.controller.target_x += delta_x
        self.controller.target_z += delta_z
        self.controller.target_y += up

        # Adjust original/override targets by the same delta if they exist
        if self.instructor.original_target_x is not None:
            self.instructor.original_target_x += delta_x
        if self.instructor.original_target_y is not None:
            self.instructor.original_target_y += up
        if self.instructor.original_target_z is not None:
            self.instructor.original_target_z += delta_z

        if self.instructor.override_target_x is not None:
            self.instructor.override_target_x += delta_x
        if self.instructor.override_target_y is not None:
            self.instructor.override_target_y += up
        if self.instructor.override_target_z is not None:
            self.instructor.override_target_z += delta_z

        self.controller.target_psi = (self.controller.target_psi + heading) % 360.0

    def draw_hud(self, window_id, refcon):
        """Draws the HUD graphics including flight telemetry and matching guide."""
        state = self.get_current_state()
        y_agl = xp.getDataf(self.dref_y_agl) if self.dref_y_agl else 10.0

        telemetry = {
            "phi": state["phi"],
            "theta": state["theta"],
            "psi": state["psi"],
            "P": state["P"],
            "Q": state["Q"],
            "R": state["R"],
            "vx": state["vx"],
            "vy": state["vy"],
            "vz": state["vz"],
            "y_agl": y_agl,
            "x": state["x"],
            "z": state["z"],
            "target_x": self.controller.target_x,
            "target_z": self.controller.target_z,
        }

        view_model = hud.HUDViewModel(
            show_hud=self.show_hud,
            hud_window=self.hud_window,
            ap_enabled=self.ap_enabled,
            phase=self.instructor.phase,
            system_state=self.instructor.system_state,
            hud_caption=self.instructor.hud_caption,
            sync_timer=self.instructor.sync_timer,
            sync_hold_duration=self.instructor.sync_hold_duration,
            hover_safety_radius=self.instructor.hover_safety_radius,
            hover_soft_radius=self.instructor.hover_soft_radius,
            last_commands=self.last_commands,
            last_hardware_inputs=self.last_hardware_inputs,
            state=state,
            y_agl=y_agl,
            target_x=self.controller.target_x,
            target_z=self.controller.target_z,
            sync_locked=self.instructor.sync_locked,
            match_tolerance=self.instructor.match_tolerance,
            recovery_timer=self.instructor.recovery_timer,
            precision_score=self.metrics.precision_score,
            smoothness_score=self.metrics.smoothness_score,
            overall_score=self.metrics.overall_score,
            envelope=self.metrics.envelope,
            coaching_tips=self.metrics.coaching_tips,
            oci=self.metrics.oci,
            target_psi=self.controller.target_psi,
            yaw_speed=self.metrics.yaw_speed,
            yaw_speed_score=self.metrics.yaw_speed_score,
            show_envelope_debug=self.show_envelope_debug,
        )

        success, new_show_hud = hud.draw_hud(view_model, window_id)
        if new_show_hud is not None:
            self.show_hud = new_show_hud
        return success

    def draw_alt_bar(self, window_id, refcon):
        """Draws a vertical altitude guidance bar in the alt-bar window."""
        y_agl = xp.getDataf(self.dref_y_agl) if self.dref_y_agl else 10.0
        alt_view_model = hud.HUDViewModel(
            show_alt_bar=self.show_alt_bar,
            alt_bar_window=self.alt_bar_window,
            ap_enabled=self.ap_enabled,
            phase=self.instructor.phase,
            y_agl=y_agl,
        )

        success, new_show_alt_bar = hud.draw_alt_bar(alt_view_model, window_id)
        if new_show_alt_bar is not None:
            self.show_alt_bar = new_show_alt_bar
        return success

    def play_sound(self, filename, clear_queue=False):
        """Queues a WAV file to be played through FMOD sequentially.

        Silently suppresses duplicate play requests for the same sound if
        it is already actively playing to prevent audio glitching or rapid
        speech repetition.

        Args:
            filename: A string filename of the sound to be played.
            clear_queue: If True, clears all currently queued audio cues and
              resets the playback timer to play the new sound immediately.
        """
        # If the requested sound is currently playing, ignore it to prevent repetition/glitching
        if self.last_played_sound == filename and self.audio_playback_timer > 0.3:
            return

        if clear_queue:
            self.audio_queue = []
            self.audio_playback_timer = 0.0
            self.audio.stop_sound()

        if filename not in self.audio_queue:
            self.audio_queue.append(filename)

    def load_objects(self):
        """Generates and loads the 3D OBJ8 objects and creates instances."""
        self.graphics.load_objects(
            green_limit=envelope_limits.LIMIT_HDG_GREEN_DEG,
            orange_limit=envelope_limits.LIMIT_HDG_ORANGE_DEG,
        )
