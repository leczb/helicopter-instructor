"""Automated unit tests for the student performance metrics evaluator."""

import os
import sys
import unittest

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0, os.path.join(base_dir, "..", "plugin", "helicopter_instructor", "autopilot")
)
sys.path.insert(0, os.path.join(base_dir, "..", "plugin", "helicopter_instructor"))
sys.path.insert(0, os.path.join(base_dir, "..", "plugin"))

# pyrefly: ignore [missing-import]
from helicopter_instructor import envelope_limits

# pyrefly: ignore [missing-import]
from helicopter_instructor import constants
from helicopter_instructor import metrics
from helicopter_instructor.enums import ControlAxis
from helicopter_instructor.enums import Envelope

PerformanceMetricsEvaluator = metrics.PerformanceMetricsEvaluator
M_S_TO_FT_MIN = constants.M_S_TO_FT_MIN


class TestPerformanceMetricsEvaluator(unittest.TestCase):
    """Tests the PerformanceMetricsEvaluator metrics engine."""

    def setUp(self):
        """Initializes the evaluator and nominal states for each test."""
        self.metrics = PerformanceMetricsEvaluator()
        self.nominal_telemetry = {
            "phi": 0.0,
            "theta": 0.0,
            "psi": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "y_agl": 6.0,
            "x": 100.0,
            "z": 200.0,
            "target_x": 100.0,
            "target_z": 200.0,
            "target_psi": 0.0,
        }
        self.nominal_inputs = {
            ControlAxis.ROLL: 0.0,
            ControlAxis.PITCH: 0.0,
            ControlAxis.YAW: 0.0,
            ControlAxis.COLLECTIVE: 0.5,
        }

    def test_initial_state(self):
        """Verifies evaluator initializes with correct nominal defaults."""
        self.assertEqual(len(self.metrics.history), 0)
        self.assertEqual(self.metrics.precision_score, 100.0)
        self.assertEqual(self.metrics.smoothness_score, 100.0)
        self.assertEqual(self.metrics.overall_score, 100.0)
        self.assertEqual(self.metrics.envelope, Envelope.EXCELLENT)
        self.assertEqual(self.metrics.safety_proximity, 0.0)
        self.assertFalse(self.metrics.was_student_flying_last_frame)

    def test_session_state_duration_and_takeovers(self):
        """Verifies session calculations (time, takeovers)."""
        # Active student flight accumulates flight time
        self.metrics.update(0.5, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertEqual(self.metrics.current_flight_time, 0.5)
        self.assertEqual(self.metrics.longest_flight_time, 0.5)
        self.assertEqual(self.metrics.total_takeovers, 0)
        self.assertTrue(self.metrics.was_student_flying_last_frame)

        # Transition to VFI flight resets current flight duration and logs takeover
        self.metrics.update(0.1, self.nominal_telemetry, self.nominal_inputs, False, 6)
        self.assertEqual(self.metrics.current_flight_time, 0.0)
        self.assertEqual(self.metrics.longest_flight_time, 0.5)
        self.assertEqual(self.metrics.total_takeovers, 1)
        self.assertFalse(self.metrics.was_student_flying_last_frame)

    def test_oci_smoothness_under_jerky_inputs(self):
        """Verifies over-controlling OCI index reacts to input velocities."""
        # 1. Nominal inputs: OCI should remain zero
        self.metrics.update(0.02, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertEqual(self.metrics.oci[ControlAxis.ROLL], 0.0)

        # 2. Sudden jerky input on roll: from 0.0 to 0.4 in 20ms
        jerky_inputs = {
            ControlAxis.ROLL: 0.4,
            ControlAxis.PITCH: 0.0,
            ControlAxis.YAW: 0.0,
            ControlAxis.COLLECTIVE: 0.5,
        }
        # velocity = 0.4 / 0.02 = 20.0
        # OCI_roll = 0.05 * 20.0 = 1.0
        self.metrics.update(0.02, self.nominal_telemetry, jerky_inputs, True, 6)
        self.assertAlmostEqual(self.metrics.oci[ControlAxis.ROLL], 1.0)
        self.assertTrue(self.metrics.smoothness_score < 100.0)

    def test_precision_scoring_pedals_only_phase(self):
        """Verifies precision score is selective to pedals in Phase 1."""
        # Phase 1: Yaw pedals only. Drift and alt errors must be ignored.
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "x": 250.0,  # Huge horizontal drift (150 meters)
                "y_agl": 20.0,  # Huge altitude error (14 meters)
                "psi": 15.0,  # Heading error = 15 deg (limit 30 deg -> 50% score)
                "target_psi": 0.0,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 1)
        # Precision score must ignore alt/drift and equal heading score (100% since 15.0 deg < 30.0 deg green)
        self.assertAlmostEqual(self.metrics.precision_score, 100.0)

    def test_precision_scoring_collective_only_phase(self):
        """Verifies precision score is selective to collective in Phase 2."""
        # Phase 2: Collective only.
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "psi": 90.0,  # Huge heading error (90 deg)
                "x": 250.0,  # Huge drift
                "y_agl": 7.5,  # Alt error = 1.5m (limit 3.0m -> 50% score)
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 2)
        # Precision score must ignore drift/yaw and equal altitude score (100% since 1.5m < 2.0m green)
        self.assertAlmostEqual(self.metrics.precision_score, 100.0)

    def test_precision_scoring_cyclic_only_phase(self):
        """Verifies precision score is selective to cyclic in Phase 4."""
        # Phase 4: Cyclic only.
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "psi": 90.0,  # Huge heading error
                "y_agl": 15.0,  # Huge alt error
                "x": 107.5,  # Drift = 7.5m (limit 15.0m -> 50% score)
                "z": 200.0,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 4)
        # Precision score must ignore yaw/collective and equal drift score (100% since 7.5m < 15.0m green)
        self.assertAlmostEqual(self.metrics.precision_score, 100.0)

    def test_precision_scoring_drift_speed(self):
        """Verifies drift speed precision component scoring."""
        # 1. Inside green zone (speed = 0.4 m/s <= 0.5 m/s) -> 100% score
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "vx": 0.4,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 4)
        # Drift distance is 0.0 (100%), drift speed is 0.4 (100%) -> 100% total
        self.assertAlmostEqual(self.metrics.precision_score, 100.0)

        # 2. Outside orange limit (speed = 2.5 m/s >= 2.0 m/s) -> 0% score component
        telemetry.update(
            {
                "vx": 2.5,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 4)
        # Drift distance is 0.0 (100%), drift speed is 2.5 (0%) -> average is 50%
        self.assertAlmostEqual(self.metrics.precision_score, 50.0)

    def test_precision_scoring_vert_speed(self):
        """Verifies vertical speed precision component scoring."""
        # 1. Inside green zone (|vy| = 0.1 m/s <= 0.2 m/s) -> 100% vert_speed_score
        telemetry = self.nominal_telemetry.copy()
        telemetry.update({"vy": 0.1})
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 2)
        # Altitude err is 0.0 (100%), vert speed is 0.1 (100%) -> 100% total
        self.assertAlmostEqual(self.metrics.precision_score, 100.0)

        # 2. Outside orange limit (|vy| = 1.0 m/s >= 0.8 m/s) -> 0% vert_speed_score
        telemetry.update({"vy": 1.0})
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 2)
        # Altitude err is 0.0 (100%), vert speed is 1.0 (0%) -> average is 50%
        self.assertAlmostEqual(self.metrics.precision_score, 50.0)

        # 3. Midpoint (|vy| = 0.5 m/s -> halfway between 0.2 and 0.8 -> 50% component)
        telemetry.update({"vy": 0.5})
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 2)
        # Altitude err is 0.0 (100%), vert speed is 0.5 (50%) -> average is 75%
        self.assertAlmostEqual(self.metrics.precision_score, 75.0)

    def test_precision_scoring_ramped_penalties(self):
        """Verifies ramped precision penalties apply outside green zones."""
        # 1. Heading and yaw speed components outside green zone.
        #    Heading err = 45 deg (halfway between 30 and 60 -> 50% comp_hdg)
        #    Yaw speed = 6.0 deg/s (green=4.0, orange=10.0 -> (6-4)/(10-4)=33.3%
        #    penalty -> 66.7% yaw_speed_score)
        #    Raw precision = (50% + 66.7%) / 2 = 58.33%
        #    Stationkeeping factor = comp_hdg / 100 = 0.5
        #    Scaled precision score = 58.33 * 0.5 = 29.17%
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "psi": 45.0,
                "target_psi": 0.0,
                "R": 6.0,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 1)
        self.assertAlmostEqual(self.metrics.precision_score, 29.1666667, places=4)

        # 2. Altitude and vert speed components outside green zone.
        #    Alt err = 3.0m (halfway -> 50% deviation)
        #    Vert speed = 0.5 m/s (halfway -> 50% raw speed component)
        #    Raw precision = (50% + 50%) / 2 = 50.0%
        #    Scaled precision score = 50.0 * (50 / 100) = 25.0%
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "y_agl": 9.0,
                "vy": 0.5,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 2)
        self.assertAlmostEqual(self.metrics.precision_score, 25.0)

        # 3. Drift component outside green zone.
        #    Drift = 30.0m (halfway -> 50% deviation)
        #    Drift speed = 1.25 m/s (halfway -> 50% raw speed component)
        #    Raw precision = (50% + 50%) / 2 = 50.0%
        #    Scaled precision score = 50.0 * (50 / 100) = 25.0%
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "x": 130.0,
                "z": 200.0,
                "vx": 1.25,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 4)
        self.assertAlmostEqual(self.metrics.precision_score, 25.0)

    def test_sliding_window_excellent_envelope(self):
        """Verifies Excellent grade when sliding window holds stable state."""
        # Populate history with 10 Excellent frames (ratio = 100% > 60% limit)
        for _ in range(10):
            frame = {
                "telemetry": dict(self.nominal_telemetry),
                "inputs": dict(self.nominal_inputs),
                "oci": {
                    ControlAxis.ROLL: 0.1,
                    ControlAxis.PITCH: 0.1,
                    ControlAxis.YAW: 0.05,
                    ControlAxis.COLLECTIVE: 0.0,
                },
            }
            self.metrics.history.append(frame)

        self.metrics._evaluate_proficiency_envelope(6)
        self.assertEqual(self.metrics.envelope, Envelope.EXCELLENT)

    def test_sliding_window_unstable_envelope(self):
        """Verifies Unstable grade when window contains significant errors."""
        # Populate history with frames containing severe drift (50m > 45m limit)
        unstable_telemetry = self.nominal_telemetry.copy()
        unstable_telemetry.update({"x": 150.0})  # 50m drift

        for i in range(10):
            frame = {
                "telemetry": unstable_telemetry if i < 3 else self.nominal_telemetry,
                "inputs": dict(self.nominal_inputs),
                "oci": {
                    ControlAxis.ROLL: 0.0,
                    ControlAxis.PITCH: 0.0,
                    ControlAxis.YAW: 0.0,
                    ControlAxis.COLLECTIVE: 0.0,
                },
            }
            self.metrics.history.append(frame)

        # 3 unstable frames out of 10 = 30% unstable ratio (> 15% limit)
        self.metrics._evaluate_proficiency_envelope(6)
        self.assertEqual(self.metrics.envelope, Envelope.UNSTABLE)

    def test_jerk_feedback_warnings(self):
        """Verifies that OCI threshold jerks prompt warning WAV cues."""
        # Prevent update() from overwriting manually mocked OCI calculations
        self.metrics._calculate_smoothness_index = lambda dt, inputs: None

        # Phase 6: All controls. We trigger a cyclic over-control (OCI > 1.0)
        # We simulate the OCI roll being maintained at 1.1.
        self.metrics.oci[ControlAxis.ROLL] = 1.1

        # Timer counts up with dt = 0.5s. Below 1.5s -> no trigger yet
        self.metrics.update(0.5, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertEqual(len(self.metrics.audio_queue), 0)

        # Exceeding 1.5s -> trigger "Relax cyclic.wav"
        self.metrics.update(1.1, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertEqual(len(self.metrics.audio_queue), 1)
        self.assertEqual(self.metrics.audio_queue[0], "Relax cyclic.wav")

        # Clear audio queue
        self.metrics.audio_queue.clear()

        # Cooldown prevents immediate re-triggering of the same warning
        self.metrics.oci[ControlAxis.ROLL] = 1.2
        self.metrics.update(2.0, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertEqual(len(self.metrics.audio_queue), 0)

    def test_altitude_direction_specific_warnings(self):
        """Verifies low vs high altitude cues trigger appropriately."""
        # 1. Test "We are too low.wav"
        low_alt_telem = self.nominal_telemetry.copy()
        low_alt_telem["y_agl"] = 3.5  # < 4.0m (green zone lower edge)

        self.metrics.update(1.6, low_alt_telem, self.nominal_inputs, True, 6)
        self.assertIn("We are too low.wav", self.metrics.audio_queue)
        self.assertNotIn("We are too high.wav", self.metrics.audio_queue)

        self.metrics.audio_queue.clear()
        self.metrics.audio_cooldowns["We are too low.wav"] = 0.0
        self.metrics.was_in_warning_zone = False

        # 2. Test "We are too high.wav"
        high_alt_telem = self.nominal_telemetry.copy()
        high_alt_telem["y_agl"] = 8.5  # > 8.0m (green zone upper edge)

        self.metrics.update(1.6, high_alt_telem, self.nominal_inputs, True, 6)
        self.assertIn("We are too high.wav", self.metrics.audio_queue)
        self.assertNotIn("We are too low.wav", self.metrics.audio_queue)

    def test_praise_cues(self):
        """Verifies praise audio cues trigger on good metrics."""
        # 1. Pedal Master: error < 5 deg and yaw rate < 3 deg/s for 15 seconds
        self.metrics.pedal_praise_timer = 14.5
        telemetry = self.nominal_telemetry.copy()
        telemetry.update({"psi": 2.0, "target_psi": 0.0, "R": 1.0})

        self.metrics.update(0.6, telemetry, self.nominal_inputs, True, 6)
        self.assertIn("Great pedals.wav", self.metrics.audio_queue)

        self.metrics.audio_queue.clear()

        # 2. Nice Recovery: had warning, returned to green zone (precision >= 85)
        self.metrics.was_in_warning_zone = True
        self.metrics.precision_score = 90.0
        self.metrics._check_feedback_triggers(0.1, telemetry, 6)
        self.assertIn("Nice recovery.wav", self.metrics.audio_queue)

    def test_perfect_hover_praise_cue(self):
        """Verifies Perfect praise cue triggers after stable excellent hover."""
        # Prevent update() from overwriting manually mocked envelope evaluations
        self.metrics._evaluate_proficiency_envelope = lambda phase: None

        self.metrics.envelope = Envelope.EXCELLENT
        self.metrics.perfect_hover_timer = 9.5

        # 1. Excellent envelope for 0.6s -> triggers Perfect.wav
        self.metrics.update(0.6, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertIn("Perfect.wav", self.metrics.audio_queue)
        self.assertEqual(self.metrics.perfect_hover_timer, 0.0)
        self.assertEqual(self.metrics.audio_cooldowns["Perfect.wav"], 30.0)

        self.metrics.audio_queue.clear()

        # 2. Resets timer if envelope is Good, not Excellent
        self.metrics.envelope = Envelope.GOOD
        self.metrics.perfect_hover_timer = 5.0
        self.metrics.update(0.1, self.nominal_telemetry, self.nominal_inputs, True, 6)
        self.assertEqual(self.metrics.perfect_hover_timer, 0.0)

        # 3. Resets timer when student is not flying
        self.metrics.perfect_hover_timer = 5.0
        self.metrics.update(0.1, self.nominal_telemetry, self.nominal_inputs, False, 6)
        self.assertEqual(self.metrics.perfect_hover_timer, 0.0)

    def test_praise_blocked_by_drift_speed(self):
        """Verifies praise is blocked/reset when drift speed is > 1.0 m/s."""
        # 1. Block Perfect hover praise
        self.metrics._evaluate_proficiency_envelope = lambda phase: None
        self.metrics.envelope = Envelope.EXCELLENT
        self.metrics.perfect_hover_timer = 9.5

        # Telemetry with high drift speed (vx = 1.0, vz = 1.0 -> speed = sqrt(2) ~ 1.41 m/s > 1.0)
        fast_drift_telemetry = dict(self.nominal_telemetry)
        fast_drift_telemetry["vx"] = 1.0
        fast_drift_telemetry["vz"] = 1.0

        self.metrics.update(0.6, fast_drift_telemetry, self.nominal_inputs, True, 6)
        # Should NOT trigger Perfect.wav and should reset timer to 0.0
        self.assertNotIn("Perfect.wav", self.metrics.audio_queue)
        self.assertEqual(self.metrics.perfect_hover_timer, 0.0)

        # 2. Block Pedal Master praise
        self.metrics.pedal_praise_timer = 14.5
        # Heading deviation < 5, yaw rate < 3, but high drift speed
        self.metrics.update(0.6, fast_drift_telemetry, self.nominal_inputs, True, 6)
        self.assertNotIn("Great pedals.wav", self.metrics.audio_queue)
        self.assertEqual(self.metrics.pedal_praise_timer, 0.0)

        # 3. Block Smooth Hands praise
        self.metrics.cyclic_praise_timer = 29.5
        self.metrics.precision_score = 90.0
        self.metrics.update(0.6, fast_drift_telemetry, self.nominal_inputs, True, 6)
        self.assertNotIn("Smooth cyclic.wav", self.metrics.audio_queue)
        self.assertEqual(self.metrics.cyclic_praise_timer, 0.0)

        # 4. Block Nice Recovery praise
        self.metrics.audio_queue.clear()
        self.metrics.was_in_warning_zone = True
        self.metrics.precision_score = 90.0
        self.metrics.update(0.1, fast_drift_telemetry, self.nominal_inputs, True, 6)
        self.assertNotIn("Nice recovery.wav", self.metrics.audio_queue)

    def test_nice_recovery_takeover_and_warning_conditions(self):
        """Verifies Nice Recovery is blocked by takeover and active warnings."""
        # 1. Test takeover resets warning zone flag and timers
        self.metrics.was_in_warning_zone = True
        self.metrics.drift_warning_timer = 2.0
        self.metrics.jerk_timers["cyclic"] = 1.0

        # When student is not active, all should be reset
        self.metrics.update(0.1, self.nominal_telemetry, self.nominal_inputs, False, 6)
        self.assertFalse(self.metrics.was_in_warning_zone)
        self.assertEqual(self.metrics.drift_warning_timer, 0.0)
        self.assertEqual(self.metrics.jerk_timers["cyclic"], 0.0)

        # 2. Test Nice Recovery blocked while still in active drift warning
        self.metrics.was_in_warning_zone = True
        # Set telemetry with drift of 8.0 meters (limit is MARGIN_DRIFT_LIMIT = 7.0m)
        drift_telemetry = self.nominal_telemetry.copy()
        drift_telemetry.update(
            {
                "x": 108.0,
                "z": 200.0,
            }
        )
        # Mock precision_score to >= 85.0 to isolate the warning check
        self.metrics.precision_score = 90.0
        self.metrics.drift_speed = 0.5

        self.metrics.update(0.1, drift_telemetry, self.nominal_inputs, True, 6)
        # Should NOT trigger because drift (8.0m) > MARGIN_DRIFT_LIMIT (7.0m)
        self.assertNotIn("Nice recovery.wav", self.metrics.audio_queue)
        self.assertTrue(self.metrics.was_in_warning_zone)

        # 3. Test Nice Recovery blocked while still in active altitude warning
        self.metrics.audio_queue.clear()
        self.metrics.was_in_warning_zone = True
        # Set telemetry with altitude error (y_agl = 3.5m, limit low is 4.0m)
        alt_telemetry = self.nominal_telemetry.copy()
        alt_telemetry.update(
            {
                "y_agl": 3.5,
            }
        )
        self.metrics.precision_score = 90.0
        self.metrics.drift_speed = 0.5

        self.metrics.update(0.1, alt_telemetry, self.nominal_inputs, True, 6)
        # Should NOT trigger because altitude < MARGIN_ALT_LOW
        self.assertNotIn("Nice recovery.wav", self.metrics.audio_queue)
        self.assertTrue(self.metrics.was_in_warning_zone)

        # 4. Test Nice Recovery triggers when back in warning-free zone
        self.metrics.audio_queue.clear()
        # Set telemetry in warning-free zone (drift = 5.0m, alt = 6.0m)
        recovered_telemetry = self.nominal_telemetry.copy()
        recovered_telemetry.update(
            {
                "x": 105.0,
                "z": 200.0,
                "y_agl": 6.0,
            }
        )
        self.metrics.precision_score = 90.0
        self.metrics.drift_speed = 0.5

        self.metrics.update(0.1, recovered_telemetry, self.nominal_inputs, True, 6)
        # Should trigger now
        self.assertIn("Nice recovery.wav", self.metrics.audio_queue)
        self.assertFalse(self.metrics.was_in_warning_zone)

    def test_perfect_praise_yaw_rate_limit(self):
        """Verifies Perfect praise yaw rate limit of 4.0 deg/s in all phases."""
        self.metrics.history.clear()

        # 1. Populate history with frames having high yaw rate (> 4.0 deg/s limit)
        unstable_telemetry = self.nominal_telemetry.copy()
        unstable_telemetry.update({"R": 4.5})
        for _ in range(10):
            frame = {
                "telemetry": unstable_telemetry,
                "inputs": dict(self.nominal_inputs),
                "oci": {
                    ControlAxis.ROLL: 0.1,
                    ControlAxis.PITCH: 0.1,
                    ControlAxis.YAW: 0.05,
                    ControlAxis.COLLECTIVE: 0.0,
                },
            }
            self.metrics.history.append(frame)

        # Evaluate envelope -> should not be Excellent since yaw rate > 4.0 limit
        self.metrics._evaluate_proficiency_envelope(6)
        self.assertNotEqual(self.metrics.envelope, Envelope.EXCELLENT)

        # 2. Populate history with frames having low yaw rate (< 4.0 deg/s limit)
        self.metrics.history.clear()
        excellent_telemetry = self.nominal_telemetry.copy()
        excellent_telemetry.update({"R": 1.5})
        for _ in range(10):
            frame = {
                "telemetry": excellent_telemetry,
                "inputs": dict(self.nominal_inputs),
                "oci": {
                    ControlAxis.ROLL: 0.1,
                    ControlAxis.PITCH: 0.1,
                    ControlAxis.YAW: 0.05,
                    ControlAxis.COLLECTIVE: 0.0,
                },
            }
            self.metrics.history.append(frame)

        # Evaluate envelope -> should be Excellent
        self.metrics._evaluate_proficiency_envelope(6)
        self.assertEqual(self.metrics.envelope, Envelope.EXCELLENT)

    def test_envelope_evaluation_ignores_vfi_controlled_axes(self):
        """Verifies envelope ignores errors/OCI on VFI-controlled axes in Phase 1."""
        self.metrics.history.clear()

        # Populate history with frames having high roll OCI (1.8 > 1.5 limit) and high drift (50.0m > 45.0m limit)
        # but otherwise nominal yaw (pedal) metrics.
        unstable_vfi_telemetry = self.nominal_telemetry.copy()
        unstable_vfi_telemetry.update(
            {
                "x": 150.0,  # 50m drift (ignored in Phase 1)
            }
        )
        for _ in range(10):
            frame = {
                "telemetry": unstable_vfi_telemetry,
                "inputs": dict(self.nominal_inputs),
                "oci": {
                    ControlAxis.ROLL: 1.8,  # Jerky roll cyclic (ignored in Phase 1)
                    ControlAxis.PITCH: 0.1,
                    ControlAxis.YAW: 0.05,
                    ControlAxis.COLLECTIVE: 0.0,
                },
            }
            self.metrics.history.append(frame)

        # Evaluate envelope in Phase 1 -> should be Excellent (as yaw is excellent and cyclic is ignored)
        self.metrics._evaluate_proficiency_envelope(1)
        self.assertEqual(self.metrics.envelope, Envelope.EXCELLENT)

        # In Phase 6 (all axes under student control), the same frames must be Unstable
        self.metrics._evaluate_proficiency_envelope(6)
        self.assertEqual(self.metrics.envelope, Envelope.UNSTABLE)

    def test_gated_precision_speeds_and_scores_when_not_student_controlled(self):
        """Verifies speeds and scores are forced to 0/100 when VFI-controlled."""
        # Phase 1: only pedals/yaw is student-controlled.
        # Set telemetry with massive drift speed (vx = 2.0) and vertical speed (vy = 1.0)
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "vx": 2.0,
                "vy": 1.0,
            }
        )
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 1)
        # Drift speed and vertical speed must be forced to 0.0, and their scores to 100.0
        self.assertEqual(self.metrics.drift_speed, 0.0)
        self.assertEqual(self.metrics.drift_speed_score, 100.0)
        self.assertEqual(self.metrics.vert_speed, 0.0)
        self.assertEqual(self.metrics.vert_speed_score, 100.0)

    def test_static_deviation_scales_down_rates_and_smoothness(self):
        """Verifies large heading error in Phase 1 yields score near 0%."""
        telemetry = self.nominal_telemetry.copy()
        telemetry.update(
            {
                "psi": 59.0,  # Heading near 60.0 degree limit (3.3% score)
                "target_psi": 0.0,
                "R": 0.0,  # Perfect rate
            }
        )
        # Hardware inputs are nominal and static (0 OCI)
        self.metrics.update(0.02, telemetry, self.nominal_inputs, True, 1)
        # Precision and overall scores are scaled down to near 0%.
        # Smoothness remains unscaled and honest (100.0%).
        self.assertAlmostEqual(self.metrics.precision_score, 1.7222222)
        self.assertAlmostEqual(self.metrics.smoothness_score, 100.0)
        self.assertAlmostEqual(self.metrics.overall_score, 2.3666667)


if __name__ == "__main__":
    unittest.main()
