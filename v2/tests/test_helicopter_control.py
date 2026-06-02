import math
import os
import sys
import unittest
from unittest import mock

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0, os.path.join(base_dir, "..", "plugin", "helicopter_instructor", "autopilot")
)
sys.path.insert(0, os.path.join(base_dir, "..", "plugin", "helicopter_instructor"))
sys.path.insert(0, os.path.join(base_dir, "..", "plugin"))

# Mock xp, xp_imgui, and imgui modules before importing PI_helicopter_instructor
mock_xp = mock.MagicMock()
mock_xp_imgui = mock.MagicMock()
mock_imgui = mock.MagicMock()
sys.modules["xp"] = mock_xp
sys.modules["xp_imgui"] = mock_xp_imgui
sys.modules["imgui"] = mock_imgui

from helicopter_instructor.autopilot import helicopter_control
from helicopter_instructor import config
import PI_helicopter_instructor

# Local module level definitions to keep test compatibility without breaking style
wrap_180 = helicopter_control.wrap_180
PID = helicopter_control.PID
CoordinateTransformer = helicopter_control.CoordinateTransformer
HoverAutopilotController = helicopter_control.HoverAutopilotController
MODE_HOVER = helicopter_control.MODE_HOVER
MODE_CRUISE = helicopter_control.MODE_CRUISE
PythonInterface = PI_helicopter_instructor.PythonInterface
MagicMock = mock.MagicMock
patch = mock.patch


class TestHelicopterControl(unittest.TestCase):

    def test_wrap_180(self):
        # Basic bounds
        self.assertAlmostEqual(wrap_180(0.0), 0.0)
        self.assertAlmostEqual(
            wrap_180(180.0), -180.0
        )  # Modulo behavior: 180 % 360 - 180 = -180
        self.assertAlmostEqual(wrap_180(-180.0), -180.0)
        self.assertAlmostEqual(wrap_180(90.0), 90.0)
        self.assertAlmostEqual(wrap_180(-90.0), -90.0)

        # Beyond 180
        self.assertAlmostEqual(wrap_180(190.0), -170.0)
        self.assertAlmostEqual(wrap_180(-190.0), 170.0)
        self.assertAlmostEqual(wrap_180(370.0), 10.0)
        self.assertAlmostEqual(wrap_180(-370.0), -10.0)

    def test_pid_proportional(self):
        pid = PID(kp=2.0, ki=0.0, kd=0.0, output_min=-10.0, output_max=10.0)
        output = pid.update(error=3.0, dt=0.1)
        self.assertAlmostEqual(output, 6.0)

    def test_pid_derivative_error(self):
        # kd = 1.5, error goes from 2.0 to 4.0 in 0.1s -> derivative term = 1.5 * (4 - 2) / 0.1 = 30.0
        pid = PID(kp=0.0, ki=0.0, kd=1.5, output_min=-50.0, output_max=50.0)
        output1 = pid.update(
            error=2.0, dt=0.1
        )  # first update, last_error initialized to 0.0
        output2 = pid.update(error=4.0, dt=0.1)
        self.assertAlmostEqual(output2, 30.0)

    def test_pid_derivative_rate(self):
        # Using rate instead of error diff (derivative on feedback)
        # Output should be -kd * rate
        pid = PID(kp=0.0, ki=0.0, kd=1.5, output_min=-50.0, output_max=50.0)
        output = pid.update(error=10.0, dt=0.1, rate=4.0)
        self.assertAlmostEqual(output, -6.0)

    def test_pid_integral_clamping(self):
        # Test integral accumulation and windup prevention
        # ki = 2.0. Error = 1.0, dt = 0.5. Integrator becomes 0.5. i_term = 1.0.
        # Clamp limits output to 0.8.
        pid = PID(kp=0.0, ki=2.0, kd=0.0, output_min=-0.8, output_max=0.8)
        output1 = pid.update(error=1.0, dt=0.5)
        self.assertAlmostEqual(output1, 0.8)

        # Because we hit the clamp, the update function should undo the integral addition
        # so integral remains 0.0, not 0.5.
        self.assertAlmostEqual(pid.integral, 0.0)

    def test_coordinate_transformer_facing_north(self):
        # Facing North (heading = 0)
        # target_x = 10, target_z = -5, current = 0 -> delta_x = 10 (East), delta_z = -5 (North)
        # Forward is North, which is -Z, so fwd_err should be +5.
        # Right is East, which is +X, so right_err should be +10.
        fwd, right = CoordinateTransformer.rotate_local_to_body_error(
            delta_x=10.0, delta_z=-5.0, heading_deg=0.0
        )
        self.assertAlmostEqual(fwd, 5.0)
        self.assertAlmostEqual(right, 10.0)

    def test_coordinate_transformer_facing_east(self):
        # Facing East (heading = 90)
        # delta_x = 10 (East), delta_z = -5 (North)
        # Forward is East (+X), so fwd_err should be +10.
        # Right is South (+Z), so right_err should be -5 (since North is to the left).
        fwd, right = CoordinateTransformer.rotate_local_to_body_error(
            delta_x=10.0, delta_z=-5.0, heading_deg=90.0
        )
        self.assertAlmostEqual(fwd, 10.0)
        self.assertAlmostEqual(right, -5.0)

    def test_coordinate_transformer_velocity(self):
        # Facing North (heading = 0)
        # vx = 3.0 (East), vz = 4.0 (South) -> v_east = 3, v_north = -4
        # v_forward should be -4 (moving backward), v_right should be 3 (moving right)
        fwd, right = CoordinateTransformer.rotate_local_to_body_velocity(
            vx=3.0, vz=4.0, heading_deg=0.0
        )
        self.assertAlmostEqual(fwd, -4.0)
        self.assertAlmostEqual(right, 3.0)

    def test_autopilot_controller_init(self):
        controller = HoverAutopilotController()
        self.assertIsNotNone(controller.pos_lat_pid)
        self.assertIsNotNone(controller.vel_lat_pid)
        self.assertIsNotNone(controller.pos_lon_pid)
        self.assertIsNotNone(controller.vel_lon_pid)
        self.assertIsNotNone(controller.att_roll_pid)
        self.assertIsNotNone(controller.att_pitch_pid)

    def test_autopilot_controller_hover_signs(self):
        controller = HoverAutopilotController()
        # Engage autopilot at (0, 0, 0) heading 0, collective 0.5
        controller.engage(x=0.0, y=0.0, z=0.0, psi=0.0, collective=0.5)
        controller.roll_active = True
        controller.pitch_active = True
        controller.yaw_active = True
        controller.collective_active = True

        # Test 1: Pitch control direction when target is ahead
        # target_z = 0. We drift backward, so current z = 2.0 (South).
        # delta_z = 0.0 - 2.0 = -2.0 (target is 2m North / ahead).
        # We expect a forward error of +2.0m.
        # To go forward, we want target pitch to be negative (nose down).
        # The att_pitch_pid will see negative target pitch - 0 current pitch = negative error -> negative pitch command.
        state = {
            "x": 0.0,
            "y": 0.0,
            "z": 2.0,  # 2m South
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "phi": 0.0,
            "theta": 0.0,
            "psi": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
        }
        outputs = controller.update(dt=0.02, state=state)
        self.assertTrue(
            outputs["pitch"] < 0.0,
            f"Expected pitch command to be negative (nose down), got {outputs['pitch']}",
        )
        self.assertAlmostEqual(outputs["debug"]["fwd_err"], 2.0)
        self.assertTrue(outputs["debug"]["target_pitch"] < 0.0)

        # Test 2: Roll control direction when target is to the right
        # target_x = 0. We drift left, so current x = -2.0 (West).
        # delta_x = 0.0 - (-2.0) = 2.0 (target is 2m East / right).
        # We expect a right error of +2.0m.
        # We want to roll right (positive phi_target) to accelerate East.
        state = {
            "x": -2.0,
            "y": 0.0,
            "z": 0.0,  # 2m West
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "phi": 0.0,
            "theta": 0.0,
            "psi": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
        }
        outputs = controller.update(dt=0.02, state=state)
        self.assertTrue(
            outputs["roll"] > 0.0,
            f"Expected roll command to be positive (roll right), got {outputs['roll']}",
        )
        self.assertAlmostEqual(outputs["debug"]["lat_err"], 2.0)
        self.assertTrue(outputs["debug"]["target_roll"] > 0.0)

        # Test 3: Collective control direction when target is higher
        # target_y = 0. We drift down, so current y = -2.0.
        # alt_err = 0 - (-2) = +2.0m.
        # We expect collective to increase above 0.5 hover feedforward.
        state = {
            "x": 0.0,
            "y": -2.0,
            "z": 0.0,  # 2m low
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "phi": 0.0,
            "theta": 0.0,
            "psi": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
        }
        outputs = controller.update(dt=0.02, state=state)
        self.assertTrue(
            outputs["collective"] > 0.5,
            f"Expected collective to increase above 0.5, got {outputs['collective']}",
        )

    def test_reset_position_hold_pids_clears_cyclic_state(self):
        """reset_position_hold_pids() zeros integral and last_error for all
        six cyclic PIDs (pos/vel/att on both lateral and longitudinal axes).
        """
        controller = HoverAutopilotController()
        controller.engage(x=0.0, y=0.0, z=0.0, psi=0.0, collective=0.5)
        controller.roll_active = True
        controller.pitch_active = True

        # Use a small error (0.5 m) that stays well below the pos PID output
        # saturation limit (±5 m/s) so the anti-windup does not undo the
        # integral step and the integral can grow across frames.
        state = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.5,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "phi": 0.0,
            "theta": 0.0,
            "psi": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
        }
        for _ in range(50):
            controller.update(dt=0.02, state=state)

        # Confirm integrals and last_errors are non-zero before the reset.
        self.assertNotAlmostEqual(controller.pos_lon_pid.integral, 0.0)
        self.assertNotAlmostEqual(controller.pos_lon_pid.last_error, 0.0)

        controller.reset_position_hold_pids()

        # All six cyclic PID integrals and last_errors must be zero.
        for pid in (
            controller.pos_lat_pid,
            controller.vel_lat_pid,
            controller.att_roll_pid,
            controller.pos_lon_pid,
            controller.vel_lon_pid,
            controller.att_pitch_pid,
        ):
            self.assertAlmostEqual(pid.integral, 0.0, msg=f"{pid} integral not reset")
            self.assertAlmostEqual(
                pid.last_error, 0.0, msg=f"{pid} last_error not reset"
            )

    def test_reset_position_hold_pids_leaves_yaw_and_altitude_intact(self):
        """reset_position_hold_pids() must not disturb yaw or altitude PIDs.

        In Phase 4 the VFI controls yaw and collective throughout; those PIDs
        track the correct hover state and must survive the override reset.
        """
        controller = HoverAutopilotController()
        controller.engage(x=0.0, y=0.0, z=0.0, psi=0.0, collective=0.5)
        controller.yaw_active = True
        controller.collective_active = True

        # Accumulate some integral on yaw and altitude.
        state = {
            "x": 0.0,
            "y": -2.0,
            "z": 0.0,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "phi": 0.0,
            "theta": 0.0,
            "psi": 10.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
        }
        for _ in range(20):
            controller.update(dt=0.02, state=state)

        yaw_integral_before = controller.yaw_pid.integral
        alt_integral_before = controller.alt_pid.integral

        # Confirm they actually accumulated something worth preserving.
        self.assertNotAlmostEqual(yaw_integral_before, 0.0)
        self.assertNotAlmostEqual(alt_integral_before, 0.0)

        controller.reset_position_hold_pids()

        self.assertAlmostEqual(
            controller.yaw_pid.integral,
            yaw_integral_before,
            msg="yaw_pid integral must not be touched by " "reset_position_hold_pids()",
        )
        self.assertAlmostEqual(
            controller.alt_pid.integral,
            alt_integral_before,
            msg="alt_pid integral must not be touched by " "reset_position_hold_pids()",
        )

    def test_reset_position_hold_pids_safe_on_fresh_controller(self):
        """Calling reset_position_hold_pids() on a freshly constructed
        controller (no prior update() calls) must be a no-op and not raise.
        """
        controller = HoverAutopilotController()
        controller.reset_position_hold_pids()  # must not raise

        for pid in (
            controller.pos_lat_pid,
            controller.vel_lat_pid,
            controller.att_roll_pid,
            controller.pos_lon_pid,
            controller.vel_lon_pid,
            controller.att_pitch_pid,
        ):
            self.assertAlmostEqual(pid.integral, 0.0)
            self.assertAlmostEqual(pid.last_error, 0.0)


class TestAutopilotPlugin(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        mock_xp.reset_mock()
        mock_xp_imgui.reset_mock()

        # Set default return value to avoid unpacking errors during initialization
        mock_xp.getNthAircraftModel.return_value = (None, None)
        mock_xp.getScreenBoundsGlobal.return_value = (0, 1080, 1920, 0)

        # Instantiate PythonInterface
        self.plugin = PythonInterface()
        # Mock dataref handles
        self.plugin.dref_paused = "mock_paused_dataref"
        self.plugin.dref_local_x = "mock_x"
        self.plugin.dref_local_y = "mock_y"
        self.plugin.dref_local_z = "mock_z"
        self.plugin.dref_local_vx = "mock_vx"
        self.plugin.dref_local_vy = "mock_vy"
        self.plugin.dref_local_vz = "mock_vz"
        self.plugin.dref_phi = "mock_phi"
        self.plugin.dref_theta = "mock_theta"
        self.plugin.dref_psi = "mock_psi"
        self.plugin.dref_P = "mock_P"
        self.plugin.dref_Q = "mock_Q"
        self.plugin.dref_R = "mock_R"
        self.plugin.dref_y_agl = "mock_y_agl"

        # Setup mock return values for getData datarefs
        def mock_get_datad(dref):
            return 0.0

        def mock_get_dataf(dref):
            if dref == "mock_y_agl":
                return 10.0
            return 0.0

        def mock_get_datai(dref):
            if dref == "mock_paused_dataref":
                return self.is_paused_val
            return 0

        mock_xp.getDatad.side_effect = mock_get_datad
        mock_xp.getDataf.side_effect = mock_get_dataf
        mock_xp.getDatai.side_effect = mock_get_datai

        self.is_paused_val = 0
        self.plugin.ap_enabled = True
        self.plugin.use_flaps_collective = False

    def test_flight_loop_callback_when_paused(self):
        # Set pause state to 1 (paused)
        self.is_paused_val = 1

        # Call flight loop callback
        result = self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=1, ref_con=None
        )

        # Verify it returns early (0.02)
        self.assertEqual(result, 0.02)

        # Verify that getDatad was NOT called
        mock_xp.getDatad.assert_not_called()

    def test_flight_loop_callback_unpaused_normal_dt(self):
        # Set pause state to 0 (unpaused)
        self.is_paused_val = 0

        # Mock controller update
        self.plugin.controller.update = MagicMock(
            return_value={
                "roll": 0.1,
                "pitch": 0.2,
                "yaw": 0.3,
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
        )

        # Mock hardware scanner
        self.plugin.get_hardware_inputs = MagicMock(
            return_value={"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "collective": 0.5}
        )

        # Call flight loop callback with normal dt
        result = self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=1, ref_con=None
        )

        self.assertEqual(result, 0.02)
        # Verify update was called with dt = 0.02
        self.plugin.controller.update.assert_called_once()
        args, kwargs = self.plugin.controller.update.call_args
        self.assertAlmostEqual(args[0], 0.02)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("json.load")
    def test_load_gains_new_format(self, mock_json_load, mock_open, mock_exists):
        mock_exists.return_value = True
        # Mock new format gains
        mock_json_load.return_value = {
            "pos_lat": [1.1, 1.2, 1.3],
            "vel_lat": [2.1, 2.2, 2.3],
            "att_roll": [3.1, 3.2, 3.3],
            "pos_lon": [4.1, 4.2, 4.3],
            "vel_lon": [5.1, 5.2, 5.3],
            "att_pitch": [6.1, 6.2, 6.3],
            "yaw": [7.1, 7.2, 7.3],
            "alt": [8.1, 8.2, 8.3],
            "vspeed": [9.1, 9.2, 9.3],
            "hover_feedforward": 0.45,
        }

        self.plugin.load_gains()

        self.assertAlmostEqual(self.plugin.controller.pos_lat_pid.kp, 1.1)
        self.assertAlmostEqual(self.plugin.controller.vel_lat_pid.kp, 2.1)
        self.assertAlmostEqual(self.plugin.controller.pos_lon_pid.kp, 4.1)
        self.assertAlmostEqual(self.plugin.controller.vel_lon_pid.kp, 5.1)
        self.assertAlmostEqual(self.plugin.controller.hover_feedforward, 0.45)

    def test_xplugin_draw_callback_registration(self):
        # Reset mock
        mock_xp.createWindowEx.reset_mock()
        mock_xp.destroyWindow.reset_mock()

        # Test start registration
        self.plugin.XPluginStart()
        self.assertEqual(mock_xp.createWindowEx.call_count, 2)

        # Test stop unregistration
        self.plugin.XPluginStop()
        self.assertEqual(mock_xp.destroyWindow.call_count, 2)

    def test_draw_osd_early_exit_conditions(self):
        # 1. OSD is disabled (show_osd = False)
        # Should return 1 immediately and not call screen bounds regardless of ap_enabled
        self.plugin.ap_enabled = True
        self.plugin.show_osd = False
        mock_xp.getWindowGeometry.reset_mock()
        result = self.plugin.draw_osd(None, None)
        self.assertEqual(result, 1)
        mock_xp.getWindowGeometry.assert_not_called()

        self.plugin.ap_enabled = False
        self.plugin.show_osd = False
        mock_xp.getWindowGeometry.reset_mock()
        result = self.plugin.draw_osd(None, None)
        self.assertEqual(result, 1)
        mock_xp.getWindowGeometry.assert_not_called()

    def test_draw_osd_rendering_calls(self):
        # Autopilot engaged, OSD enabled
        self.plugin.ap_enabled = True
        self.plugin.show_osd = True

        # Mock window dimensions (left, top, right, bottom)
        mock_xp.getWindowGeometry.return_value = (100, 350, 650, 100)

        # Reset drawing mock calls
        mock_xp.drawTranslucentDarkBox.reset_mock()
        mock_xp.drawString.reset_mock()
        mock_xp.setGraphicsState.reset_mock()

        result = self.plugin.draw_osd(self.plugin.osd_window, None)

        self.assertEqual(result, 1)
        # Verify background box bounds
        mock_xp.drawTranslucentDarkBox.assert_called_once()
        # Verify graphics state is set
        mock_xp.setGraphicsState.assert_any_call(0, 1, 0, 0, 1, 0, 0)
        # Verify text elements are drawn
        self.assertTrue(mock_xp.drawString.call_count >= 3)

    def test_draw_alt_bar_rendering_calls(self):
        self.plugin.show_alt_bar = True
        self.plugin.instructor.phase = 2
        mock_xp.getWindowGeometry.return_value = (100, 350, 180, 100)

        mock_xp.drawTranslucentDarkBox.reset_mock()
        mock_xp.drawString.reset_mock()
        mock_xp.setGraphicsState.reset_mock()

        result = self.plugin.draw_alt_bar(self.plugin.alt_bar_window, None)

        self.assertEqual(result, 1)
        mock_xp.drawTranslucentDarkBox.assert_called_once()
        mock_xp.setGraphicsState.assert_any_call(0, 1, 0, 0, 1, 0, 0)
        self.assertTrue(mock_xp.drawString.call_count >= 3)

    def test_cmd_handler_osd_toggle(self):
        self.plugin.show_osd = True

        # Call toggle command handler with phase 0 (CommandBegin) -> Toggles to False
        self.plugin.cmd_handler_osd_toggle(None, 0, None)
        self.assertFalse(self.plugin.show_osd)

        # Call toggle command handler with phase 0 -> Toggles to True
        self.plugin.cmd_handler_osd_toggle(None, 0, None)
        self.assertTrue(self.plugin.show_osd)

    def test_cmd_handler_alt_bar_toggle(self):
        self.plugin.show_alt_bar = True

        # Call toggle command handler with phase 0 -> Toggles to False
        self.plugin.cmd_handler_alt_bar_toggle(None, 0, None)
        self.assertFalse(self.plugin.show_alt_bar)

        # Call toggle command handler with phase 0 -> Toggles to True
        self.plugin.cmd_handler_alt_bar_toggle(None, 0, None)
        self.assertTrue(self.plugin.show_alt_bar)

    def test_get_gains_filepath_custom_aircraft(self):
        mock_xp.getNthAircraftModel.return_value = (
            "Bell_206.acf",
            "/path/to/Bell_206.acf",
        )
        filepath = config.get_gains_filepath(self.plugin.plugin_dir)
        self.assertTrue(filepath.endswith("autopilot_gains_Bell_206.json"))

    def test_get_gains_filepath_special_characters(self):
        mock_xp.getNthAircraftModel.return_value = (
            "Cessna-172SP (Custom).acf",
            "/path/to/Cessna-172SP (Custom).acf",
        )
        filepath = config.get_gains_filepath(self.plugin.plugin_dir)
        # Non-alphanumeric/underscore characters should be replaced with underscores
        self.assertTrue(filepath.endswith("autopilot_gains_Cessna_172SP__Custom_.json"))

    def test_get_gains_filepath_fallback_exception(self):
        mock_xp.getNthAircraftModel.side_effect = Exception("X-Plane error")
        filepath = config.get_gains_filepath(self.plugin.plugin_dir)
        self.assertTrue(filepath.endswith("autopilot_gains.json"))
        # Reset side effect
        mock_xp.getNthAircraftModel.side_effect = None

    def test_xplugin_receive_message_plane_loaded(self):
        self.plugin.load_gains = MagicMock()

        # Trigger message 102 for user plane (param 0) -> should load gains
        self.plugin.XPluginReceiveMessage(None, 102, 0)
        self.plugin.load_gains.assert_called_once()

        self.plugin.load_gains.reset_mock()
        # Trigger message 102 for AI plane (param 1) -> should NOT load gains
        self.plugin.XPluginReceiveMessage(None, 102, 1)
        self.plugin.load_gains.assert_not_called()

    def test_cmd_handler_instructor_toggle(self):
        self.plugin.ap_enabled = False
        self.plugin.cmd_handler_instructor_toggle(None, 0, None)
        self.assertTrue(self.plugin.ap_enabled)

        self.plugin.cmd_handler_instructor_toggle(None, 0, None)
        self.assertFalse(self.plugin.ap_enabled)

    def test_cmd_handler_phase_navigation(self):
        self.plugin.instructor.phase = 1

        # Test next phase
        self.plugin.cmd_handler_next_phase(None, 0, None)
        self.assertEqual(self.plugin.instructor.phase, 2)

        # Test prev phase
        self.plugin.cmd_handler_prev_phase(None, 0, None)
        self.assertEqual(self.plugin.instructor.phase, 1)

    def test_hardware_input_scanning_decoding(self):
        self.plugin.dref_joystick_axis_assignments = "mock_assignments"
        self.plugin.dref_joy_mapped_axis_value = "mock_mapped"

        # Set up mock assignments: index 10 is Roll (2), index 15 is Pitch (1), index 20 is Yaw (3), index 25 is Collective (5)
        def mock_get_datavi(dref, array_out, offset=0, count=-1):
            if count < 0:
                count = 100
            array_out.extend([0] * count)
            array_out[10] = 2  # Roll
            array_out[15] = 1  # Pitch
            array_out[20] = 3  # Yaw
            array_out[25] = 5  # Collective
            return count

        # Set up mock physical values: Roll = 0.2, Pitch = -0.3, Yaw = 0.4, Collective = 0.6 (maps to (0.6 + 1.0)/2 = 0.8)
        def mock_get_datavf(dref, array_out, offset=0, count=-1):
            if count < 0:
                count = 100
            array_out.extend([0.0] * count)
            array_out[10] = 0.2
            array_out[15] = -0.3
            array_out[20] = 0.4
            array_out[25] = 0.6
            return count

        mock_xp.getDatavi.side_effect = mock_get_datavi
        mock_xp.getDatavf.side_effect = mock_get_datavf

        hw = self.plugin.get_hardware_inputs()

        self.assertAlmostEqual(hw["roll"], 0.2)
        self.assertAlmostEqual(hw["pitch"], -0.3)
        self.assertAlmostEqual(hw["yaw"], 0.4)
        self.assertAlmostEqual(hw["collective"], 0.8)  # Scaled!

    def test_hardware_input_scanning_multi_axis(self):
        self.plugin.dref_joystick_axis_assignments = "mock_assignments"
        self.plugin.dref_joy_mapped_axis_value = "mock_mapped"

        # Multiple devices:
        # Index 10: Yaw (3), value = 0.5 (deflected)
        # Index 20: Yaw (3), value = 0.0 (un-deflected twist grip)
        # Index 12: Pitch (1), value = 0.0 (un-deflected stick)
        # Index 15: Pitch (1), value = -0.7 (deflected stick)
        # Index 30: Roll (2), value = -0.2 (deflected)
        # Index 35: Roll (2), value = 0.8 (larger deflection)
        # Index 25: Collective (5), value = 0.6
        def mock_get_datavi(dref, array_out, offset=0, count=-1):
            if count < 0:
                count = 100
            array_out.extend([0] * count)
            array_out[10] = 3  # Yaw
            array_out[20] = 3  # Yaw
            array_out[12] = 1  # Pitch
            array_out[15] = 1  # Pitch
            array_out[30] = 2  # Roll
            array_out[35] = 2  # Roll
            array_out[25] = 5  # Collective
            return count

        def mock_get_datavf(dref, array_out, offset=0, count=-1):
            if count < 0:
                count = 100
            array_out.extend([0.0] * count)
            array_out[10] = 0.5
            array_out[20] = 0.0
            array_out[12] = 0.0
            array_out[15] = -0.7
            array_out[30] = -0.2
            array_out[35] = 0.8
            array_out[25] = 0.6
            return count

        mock_xp.getDatavi.side_effect = mock_get_datavi
        mock_xp.getDatavf.side_effect = mock_get_datavf

        hw = self.plugin.get_hardware_inputs()

        self.assertAlmostEqual(hw["yaw"], 0.5)  # Chooses 0.5 over 0.0
        self.assertAlmostEqual(hw["pitch"], -0.7)  # Chooses -0.7 over 0.0
        self.assertAlmostEqual(hw["roll"], 0.8)  # Chooses 0.8 over -0.2
        self.assertAlmostEqual(hw["collective"], 0.8)  # Scaled!

    def test_hardware_input_scanning_high_indices(self):
        self.plugin.dref_joystick_axis_assignments = "mock_assignments"
        self.plugin.dref_joy_mapped_axis_value = "mock_mapped"

        # Hardware devices assigned at indices > 100:
        # Index 120: Yaw (3), value = 0.6
        # Index 150: Pitch (1), value = -0.4
        # Index 210: Roll (2), value = 0.5
        # Index 325: Collective (5), value = 0.8 (maps to (0.8+1)/2 = 0.9)
        def mock_get_datavi(dref, array_out, offset=0, count=-1):
            if count < 0:
                count = 500
            array_out.extend([0] * count)
            if count > 120:
                array_out[120] = 3  # Yaw
            if count > 150:
                array_out[150] = 1  # Pitch
            if count > 210:
                array_out[210] = 2  # Roll
            if count > 325:
                array_out[325] = 5  # Collective
            return count

        def mock_get_datavf(dref, array_out, offset=0, count=-1):
            if count < 0:
                count = 500
            array_out.extend([0.0] * count)
            if count > 120:
                array_out[120] = 0.6
            if count > 150:
                array_out[150] = -0.4
            if count > 210:
                array_out[210] = 0.5
            if count > 325:
                array_out[325] = 0.8
            return count

        mock_xp.getDatavi.side_effect = mock_get_datavi
        mock_xp.getDatavf.side_effect = mock_get_datavf

        hw = self.plugin.get_hardware_inputs()

        self.assertAlmostEqual(hw["yaw"], 0.6)
        self.assertAlmostEqual(hw["pitch"], -0.4)
        self.assertAlmostEqual(hw["roll"], 0.5)
        self.assertAlmostEqual(hw["collective"], 0.9)

    def _make_vfi_output(self):
        """Returns a minimal valid controller.update() return value."""
        return {
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

    def test_override_snaps_target_before_controller_update(self):
        """controller.update() receives the override target, not the old one.

        When drift_recovery_active is True at frame start (set in a prior
        frame), the PRE-STEP A block must write override_target_x/z into
        controller.target_x/z before controller.update() is called.  This
        prevents the PID cascade from seeing a stale large position error on
        recovery frames.
        """
        # Place the original hover target 50 m away.
        self.plugin.controller.target_x = 50.0
        self.plugin.controller.target_z = 50.0

        # Simulate instructor already in OVERRIDE with a live drift recovery.
        self.plugin.instructor.system_state = "OVERRIDE"
        self.plugin.instructor.drift_recovery_active = True
        self.plugin.instructor.override_target_x = 1.0  # near current position
        self.plugin.instructor.override_target_y = None
        self.plugin.instructor.override_target_z = 2.0

        # Record the target_x seen by each controller.update() call.
        seen_targets = []
        real_update = self.plugin.controller.update

        def capturing_update(dt, state):
            seen_targets.append(self.plugin.controller.target_x)
            return self._make_vfi_output()

        self.plugin.controller.update = capturing_update
        self.plugin.get_hardware_inputs = MagicMock(
            return_value={"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "collective": 0.5}
        )

        self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=1, ref_con=None
        )

        self.assertEqual(len(seen_targets), 1)
        self.assertAlmostEqual(
            seen_targets[0],
            1.0,
            msg="controller.update() must see the override target (1.0), "
            "not the stale 50 m target.",
        )

    def test_cyclic_pids_reset_on_student_to_override_transition(self):
        """reset_position_hold_pids() fires on STUDENT_FLIGHT → OVERRIDE.

        Safety overrides are the highest-urgency path: the state flips inside
        instructor.update() (Step C), so the check in the POST-C4 re-read
        block must catch it via last_system_state == STUDENT_FLIGHT.
        """
        self.plugin.controller.update = MagicMock(return_value=self._make_vfi_output())
        self.plugin.get_hardware_inputs = MagicMock(
            return_value={"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "collective": 0.5}
        )
        self.plugin.controller.reset_position_hold_pids = MagicMock()

        # --- Frame 1: STUDENT_FLIGHT → OVERRIDE (inside instructor.update) ---
        self.plugin.last_system_state = "STUDENT_FLIGHT"
        self.plugin.instructor.system_state = "STUDENT_FLIGHT"

        def override_on_call(dt, telemetry, hardware, vfi_inputs):
            self.plugin.instructor.system_state = "OVERRIDE"
            self.plugin.instructor.drift_recovery_active = True
            self.plugin.instructor.override_target_x = 0.0
            self.plugin.instructor.override_target_y = None
            self.plugin.instructor.override_target_z = 0.0
            return vfi_inputs

        self.plugin.instructor.update = override_on_call
        self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=1, ref_con=None
        )
        self.assertEqual(
            self.plugin.controller.reset_position_hold_pids.call_count,
            1,
            "Expected exactly one PID reset on the STUDENT→OVERRIDE frame.",
        )

        # --- Frame 2: already in OVERRIDE — no further reset ---
        self.plugin.instructor.update = lambda dt, tel, hw, vfi: vfi
        self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=2, ref_con=None
        )
        self.assertEqual(
            self.plugin.controller.reset_position_hold_pids.call_count,
            1,
            "reset_position_hold_pids() must not fire again on subsequent "
            "OVERRIDE frames.",
        )

    def test_cyclic_pids_reset_on_manual_phase_change(self):
        """reset_position_hold_pids() fires when a manual phase change puts
        the instructor into SYNCING between frames.

        The command handler calls set_phase() / initiate_handoff() outside the
        flight loop, so on the next frame last_system_state is STUDENT_FLIGHT
        but curr_state (read after Step C) is already SYNCING.
        """
        self.plugin.controller.update = MagicMock(return_value=self._make_vfi_output())
        self.plugin.get_hardware_inputs = MagicMock(
            return_value={"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "collective": 0.5}
        )
        self.plugin.controller.reset_position_hold_pids = MagicMock()

        # Simulate: previous frame was STUDENT_FLIGHT; a command handler has
        # already flipped the instructor to SYNCING before this frame runs.
        self.plugin.last_system_state = "STUDENT_FLIGHT"
        self.plugin.instructor.system_state = "SYNCING"

        # instructor.update() in SYNCING just returns vfi_inputs.
        self.plugin.instructor.update = lambda dt, tel, hw, vfi: vfi

        self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=1, ref_con=None
        )
        self.assertEqual(
            self.plugin.controller.reset_position_hold_pids.call_count,
            1,
            "Expected one PID reset when manual phase change caused "
            "STUDENT→SYNCING between frames.",
        )

    def test_cyclic_pids_reset_on_automatic_phase_advance(self):
        """reset_position_hold_pids() fires when the automatic phase advance
        flips state to SYNCING inside STEP C4 (within the same frame).

        On the transition frame Step C still returns STUDENT_FLIGHT; STEP C4
        then calls initiate_handoff(), setting state to SYNCING.  The check
        after the STEP C4 re-read must fire because last_system_state is
        STUDENT_FLIGHT and the final curr_state is SYNCING.
        """
        self.plugin.controller.update = MagicMock(return_value=self._make_vfi_output())
        self.plugin.get_hardware_inputs = MagicMock(
            return_value={"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "collective": 0.5}
        )
        self.plugin.controller.reset_position_hold_pids = MagicMock()

        # Previous frame was STUDENT_FLIGHT.
        self.plugin.last_system_state = "STUDENT_FLIGHT"
        self.plugin.instructor.system_state = "STUDENT_FLIGHT"
        self.plugin.instructor.phase = 4

        # instructor.update() still returns STUDENT_FLIGHT this frame, but
        # sets transition_pending so STEP C4 advances the phase.
        def student_with_pending_transition(dt, telemetry, hardware, vfi):
            self.plugin.instructor.transition_pending = True
            self.plugin.instructor.transition_target_phase = 5
            self.plugin.instructor.training_complete = False
            return {k: hardware[k] for k in hardware}

        self.plugin.instructor.update = student_with_pending_transition

        self.plugin.flight_loop_callback(
            last_call=0.02, elapsed_time=0.02, counter=1, ref_con=None
        )

        # After STEP C4, state must be SYNCING and reset must have fired.
        self.assertEqual(
            self.plugin.instructor.system_state,
            "SYNCING",
            "STEP C4 must have advanced the instructor to SYNCING.",
        )
        self.assertEqual(
            self.plugin.controller.reset_position_hold_pids.call_count,
            1,
            "Expected one PID reset on the automatic phase-advance frame.",
        )


class TestHoverTargetAdjustment(unittest.TestCase):

    def setUp(self):
        mock_xp.reset_mock()
        mock_xp_imgui.reset_mock()
        mock_xp.getNthAircraftModel.return_value = (None, None)
        mock_xp.getScreenBoundsGlobal.return_value = (0, 1080, 1920, 0)
        self.plugin = PythonInterface()

        # Mock dataref and return values
        self.plugin.dref_prop_ratio_all = "mock_prop_ratio_all"

        def mock_get_dataf(dref):
            if dref == "mock_prop_ratio_all":
                return 0.6
            return 0.0

        mock_xp.getDataf.side_effect = mock_get_dataf

        self.plugin.controller.target_x = 0.0
        self.plugin.controller.target_y = 10.0
        self.plugin.controller.target_z = 0.0
        self.plugin.controller.target_psi = 0.0

    def test_adjust_hover_target_forward_north(self):
        # Heading = 0.0 (North)
        # Shift forward 5m -> target_z should decrease by 5.0 (since North is -Z)
        self.plugin.adjust_hover_target(forward=5.0)
        self.assertAlmostEqual(self.plugin.controller.target_z, -5.0)
        self.assertAlmostEqual(self.plugin.controller.target_x, 0.0)

    def test_adjust_hover_target_right_east_facing(self):
        # Heading = 90.0 (East)
        # Shift right 3m -> East is +X, when facing East, right is South (+Z)
        self.plugin.controller.target_psi = 90.0
        self.plugin.adjust_hover_target(right=3.0)
        self.assertAlmostEqual(self.plugin.controller.target_x, 0.0)
        self.assertAlmostEqual(self.plugin.controller.target_z, 3.0)

    def test_adjust_hover_target_up_down_heading(self):
        self.plugin.adjust_hover_target(up=2.5, heading=15.0)
        self.assertAlmostEqual(self.plugin.controller.target_y, 12.5)
        self.assertAlmostEqual(self.plugin.controller.target_psi, 15.0)

    def test_reset_target_to_current(self):
        # Mock get_current_state
        state = {
            "x": 12.0,
            "y": 34.0,
            "z": 56.0,
            "psi": 78.0,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "phi": 0.0,
            "theta": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
        }
        self.plugin.get_current_state = MagicMock(return_value=state)
        mock_xp.getDataf.return_value = 0.6  # collective

        self.plugin.ui_controller.reset_target_to_current()

        self.assertAlmostEqual(self.plugin.controller.target_x, 12.0)
        self.assertAlmostEqual(self.plugin.controller.target_y, 34.0)
        self.assertAlmostEqual(self.plugin.controller.target_z, 56.0)
        self.assertAlmostEqual(self.plugin.controller.target_psi, 78.0)
        self.assertAlmostEqual(self.plugin.controller.hover_feedforward, 0.6)


if __name__ == "__main__":
    unittest.main()
