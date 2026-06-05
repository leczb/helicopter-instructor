import math
import os
import sys
import unittest

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0,
    os.path.join(
        base_dir, "..", "plugin", "helicopter_instructor", "autopilot"
    ),
)
sys.path.insert(
    0, os.path.join(base_dir, "..", "plugin", "helicopter_instructor")
)
sys.path.insert(0, os.path.join(base_dir, "..", "plugin"))

# pyrefly: ignore [missing-import]
from helicopter_instructor import constants
from helicopter_instructor import virtual_instructor
from helicopter_instructor.enums import Authority
from helicopter_instructor.enums import CaptionStyle
from helicopter_instructor.enums import Envelope
from helicopter_instructor.enums import HeadingZone
from helicopter_instructor.enums import VFIState
from helicopter_instructor.enums import ControlAxis

VirtualInstructor = virtual_instructor.VirtualInstructor
PHASE_CONFIGS = virtual_instructor.PHASE_CONFIGS
M_S_TO_FT_MIN = constants.M_S_TO_FT_MIN


class TestVirtualInstructor(unittest.TestCase):

    def setUp(self):
        self.instructor = VirtualInstructor()
        self.nominal_telemetry = {
            "phi": 0.0,
            "theta": 0.0,
            "psi": 0.0,
            "P": 0.0,
            "Q": 0.0,
            "R": 0.0,
            "vx": 0.0,
            "vz": 0.0,
            "vy": 0.0,
            "y_agl": 5.0,
            "y": 5.0,
            "target_y": 5.0,
        }
        # Hardware inputs (student)
        self.hardware = {
            ControlAxis.ROLL: 0.0,
            ControlAxis.PITCH: 0.0,
            ControlAxis.YAW: 0.0,
            ControlAxis.COLLECTIVE: 0.5,
        }
        # VFI inputs (autopilot)
        self.vfi = {
            ControlAxis.ROLL: 0.05,
            ControlAxis.PITCH: -0.03,
            ControlAxis.YAW: 0.01,
            ControlAxis.COLLECTIVE: 0.55,
        }

    def test_init_state(self):
        self.assertEqual(self.instructor.phase, 1)
        self.assertEqual(self.instructor.system_state, VFIState.VFI_FLIGHT)
        for axis in ControlAxis:
            self.assertEqual(
                self.instructor.control_assignment[axis], Authority.VFI
            )

    def test_initiate_handoff_phase1(self):
        # Phase 1: Yaw Pedals Only
        self.instructor.phase = 1
        self.instructor.initiate_handoff()

        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.ROLL], Authority.VFI
        )
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.PITCH], Authority.VFI
        )
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.COLLECTIVE],
            Authority.VFI
        )
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW], Authority.VFI,
        )  # VFI flies yaw until synced

        self.assertTrue(self.instructor.sync_locked[ControlAxis.ROLL])
        self.assertTrue(self.instructor.sync_locked[ControlAxis.PITCH])
        self.assertTrue(self.instructor.sync_locked[ControlAxis.COLLECTIVE])
        # Needs syncing
        self.assertFalse(self.instructor.sync_locked[ControlAxis.YAW])

    def test_synchronization_lock_success(self):
        # Phase 1: Yaw is student
        self.instructor.phase = 1
        self.instructor.initiate_handoff()

        # Physical yaw is 0.0. VFI target yaw is 0.01.
        # Delta = 0.01 <= 0.04 tolerance -> Matched!
        self.vfi[ControlAxis.YAW] = 0.01
        self.hardware[ControlAxis.YAW] = 0.0

        # First update: 200ms -> timer = 0.2. Still syncing.
        out = self.instructor.update(
            0.2, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)
        self.assertTrue(
            self.instructor.sync_locked[ControlAxis.YAW]
        )  # Real-time match indicator is True because within tolerance
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW], Authority.VFI,
        )  # Flight authority is NOT yet student
        # Still VFI output during syncing
        self.assertEqual(out[ControlAxis.YAW], self.vfi[ControlAxis.YAW])

        # Second update: 400ms -> timer = 0.6 >= 0.5s -> transitions
        # to STUDENT_FLIGHT. But this transition frame still returns VFI input
        # for aerodynamic smoothness.
        out = self.instructor.update(
            0.4, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertEqual(self.instructor.system_state, VFIState.STUDENT_FLIGHT)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW],
            Authority.STUDENT
        )
        self.assertTrue(self.instructor.sync_locked[ControlAxis.YAW])
        self.assertEqual(out[ControlAxis.YAW], self.vfi[ControlAxis.YAW])

        # Third update: subsequent frame. Output is student's deflection!
        out = self.instructor.update(
            0.02, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertEqual(out[ControlAxis.YAW], self.hardware[ControlAxis.YAW])

    def test_synchronization_drift_resets_timer(self):
        # Phase 1: Yaw is student
        self.instructor.phase = 1
        self.instructor.initiate_handoff()

        # Hardware matches at first
        self.hardware[ControlAxis.YAW] = 0.01
        self.vfi[ControlAxis.YAW] = 0.01
        self.instructor.update(
            0.3, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertEqual(self.instructor.sync_timer, 0.3)

        # Hardware drifts away: delta = 0.05 > 0.04
        self.hardware[ControlAxis.YAW] = 0.06
        self.instructor.update(
            0.1, self.nominal_telemetry, self.hardware, self.vfi
        )

        # Timer should be reset to 0.0 and state remains SYNCING
        self.assertEqual(self.instructor.sync_timer, 0.0)
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)

    def test_safety_envelope_triggers_hard_override(self):
        # Student flying Phase 1
        self.instructor.phase = 1
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.control_assignment[ControlAxis.YAW] = Authority.STUDENT

        # Telemetry is safe
        self.assertFalse(
            self.instructor.check_safety_limits(self.nominal_telemetry)
        )

        # Test 1: Pitch attitude exceeds 15 deg (e.g. 15.5)
        # Use an unstable rate or roll to keep in OVERRIDE during recovery
        telem = self.nominal_telemetry.copy()
        telem["theta"] = -15.5
        # Make attitude unstable to prevent instant recovery hold
        telem["phi"] = 10.0

        self.assertTrue(self.instructor.check_safety_limits(telem))

        # Update triggers hard override and keeps in OVERRIDE
        out = self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW], Authority.VFI,
        )  # Stripped student authority
        # Returns VFI stabilization
        self.assertEqual(out[ControlAxis.YAW], self.vfi[ControlAxis.YAW])

    def test_ground_agl_safety_trigger(self):
        # Student flying Phase 1
        self.instructor.phase = 1
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.control_assignment[ControlAxis.YAW] = Authority.STUDENT

        # AGL falls to 1.8 meters (< 2.0 limit)
        telem = self.nominal_telemetry.copy()
        telem["y_agl"] = 1.8
        # Make attitude unstable to prevent instant recovery hold
        telem["phi"] = 10.0

        self.assertTrue(self.instructor.check_safety_limits(telem))

        # Check update initiates takeover and remains in OVERRIDE
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW], Authority.VFI
        )

        # Reset state for high AGL test
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.control_assignment[ControlAxis.YAW] = Authority.STUDENT

        # AGL climbs to 12.0 meters (> 10.0 limit)
        telem_high = self.nominal_telemetry.copy()
        telem_high["y_agl"] = 12.0
        telem_high["phi"] = 10.0

        self.assertTrue(self.instructor.check_safety_limits(telem_high))
        self.instructor.update(0.02, telem_high, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW], Authority.VFI
        )

    def test_student_flight_direct_routing(self):
        # Phase 4: Cyclic is student
        self.instructor.phase = 4
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.control_assignment[ControlAxis.ROLL] = Authority.STUDENT
        self.instructor.control_assignment[
            ControlAxis.PITCH
        ] = Authority.STUDENT

        telem = self.nominal_telemetry.copy()
        telem["theta"] = 12.0  # In caution zone

        self.hardware[ControlAxis.PITCH] = 0.25
        out = self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertAlmostEqual(out[ControlAxis.PITCH], 0.25)

    def test_recovery_hold_and_reset_loop(self):
        # Trigger takeover
        self.instructor.phase = 1
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.control_assignment[ControlAxis.YAW] = Authority.STUDENT

        telem = self.nominal_telemetry.copy()
        telem["phi"] = 16.0  # Exceeds limit

        # 1. Update -> triggers takeover, sets state to OVERRIDE
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.YAW], Authority.VFI
        )

        # 2. Update with unstable telemetry -> should remain in OVERRIDE
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)

        # 3. Update with stable telemetry -> should transition to RECOVERY_HOLD
        stable_telem = (
            self.nominal_telemetry.copy()
        )  # Safe (phi=0, theta=0, vx=0, vz=0, vy=0)
        self.instructor.update(0.02, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.RECOVERY_HOLD)
        self.assertAlmostEqual(self.instructor.recovery_timer, 3.0)

        # 4. Update in RECOVERY_HOLD -> counts down
        self.instructor.update(1.0, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.RECOVERY_HOLD)
        self.assertAlmostEqual(self.instructor.recovery_timer, 2.0)

        # 5. Countdown expires -> transitions back to SYNCING
        self.instructor.update(2.1, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)
        self.assertEqual(self.instructor.sync_timer, 0.0)

    def test_positive_vertical_speed_limits(self):
        # 1. Hard Takeover: Climbing exceeds +300 ft/min (e.g. 310 ft/min)
        # vy_m_s = 310 / M_S_TO_FT_MIN
        telem = self.nominal_telemetry.copy()
        telem["vy"] = 310.0 / M_S_TO_FT_MIN

        self.assertTrue(self.instructor.check_safety_limits(telem))

    def test_hover_safety_distance_takeover(self):
        # 1. Fallback: lack of telemetry coordinates does not trigger takeover
        telem_no_coords = self.nominal_telemetry.copy()
        self.assertFalse(self.instructor.check_safety_limits(telem_no_coords))

        # 2. Inside boundary / exact center (drift = 0m)
        telem = self.nominal_telemetry.copy()
        telem.update({"x": 10.0, "z": 20.0, "target_x": 10.0, "target_z": 20.0})
        self.assertFalse(self.instructor.check_safety_limits(telem))

        # 3. Exactly at safety limit (drift = 45m, using 27-36-45 triangle)
        # dist = sqrt(27^2 + 36^2) = 45.0m
        telem.update({"x": 37.0, "z": 56.0})
        self.assertFalse(self.instructor.check_safety_limits(telem))

        # 4. Out of bounds (drift = 45.06m > 45.0m)
        telem.update({"x": 37.1, "z": 56.0})
        self.assertTrue(self.instructor.check_safety_limits(telem))

    def test_hover_fallback_robustness(self):
        # Verify that lacking coordinate keys in telemetry is handled gracefully
        telem = self.nominal_telemetry.copy()
        if "x" in telem:
            del telem["x"]
        if "z" in telem:
            del telem["z"]

        # Should not raise any KeyError exceptions
        self.assertFalse(self.instructor.check_safety_limits(telem))

    def test_safety_takeover_target_override_and_restore(self):
        # 1. Student flying at target x = 10, y = 6.0, z = 20
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        telem = self.nominal_telemetry.copy()
        telem.update(
            {
                "x": 10.0,
                "y": 4.0,
                "z": 20.0,
                "target_x": 10.0,
                "target_y": 6.0,
                "target_z": 20.0,
            }
        )

        # 2. Helicopter drifts past safety radius (drift = 47.0m > 45.0m)
        telem.update({"x": 57.0, "phi": 5.0})

        # This triggers takeover. First frame immediately starts target move.
        # override_target_y: 4.0 + 1.0 * 0.02 = 4.02
        # override_target_x: 57.0 - 2.0 * 0.02 = 56.96
        self.instructor.update(0.02, telem, self.hardware, self.vfi)

        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertTrue(self.instructor.drift_recovery_active)
        self.assertEqual(self.instructor.original_target_x, 10.0)
        self.assertEqual(self.instructor.original_target_y, 6.0)
        self.assertEqual(self.instructor.original_target_z, 20.0)
        self.assertAlmostEqual(self.instructor.override_target_x, 56.96)
        self.assertAlmostEqual(self.instructor.override_target_y, 4.02)
        self.assertEqual(self.instructor.override_target_z, 20.0)

        # 3. Stage 2 & 3 Settlement: Target y moves at 1 m/s, x at 2 m/s
        # 1.0s elapsed -> moves y by 1.0m, x by 2.0m
        self.instructor.update(1.0, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertTrue(self.instructor.drift_recovery_active)
        self.assertAlmostEqual(self.instructor.override_target_x, 54.96)
        self.assertAlmostEqual(self.instructor.override_target_y, 5.02)

        # Another 1.0s elapsed -> moves y by 1.0m (clamps to 6.0), x by 2.0m
        # We pass stable telemetry so it transitions to RECOVERY_HOLD
        stable_telem = self.nominal_telemetry.copy()
        stable_telem.update(
            {
                "x": 57.0,
                "y": 6.0,
                "z": 20.0,
                "target_x": 57.0,
                "target_y": 6.0,
                "target_z": 20.0,
            }
        )
        self.instructor.update(1.0, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.RECOVERY_HOLD)
        self.assertTrue(self.instructor.drift_recovery_active)
        self.assertAlmostEqual(self.instructor.override_target_x, 52.96)
        self.assertEqual(self.instructor.override_target_y, 6.0)

        # 4. Target translation in RECOVERY_HOLD
        # 10.0 seconds elapsed -> moves x by 20.0m (52.96 -> 32.96)
        self.instructor.update(10.0, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.RECOVERY_HOLD)
        self.assertTrue(self.instructor.drift_recovery_active)
        self.assertAlmostEqual(self.instructor.override_target_x, 32.96)

        # 22.0 seconds elapsed -> remaining distance fully covered
        self.instructor.update(22.0, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, VFIState.RECOVERY_HOLD)
        self.assertFalse(self.instructor.drift_recovery_active)
        self.assertTrue(self.instructor.was_drift_recovery_active)
        self.assertIsNone(self.instructor.override_target_x)
        self.assertIsNone(self.instructor.override_target_y)
        self.assertIsNone(self.instructor.override_target_z)

    def test_heading_safety_limits(self):
        # 1. Heading error = 15 deg (Green Zone)
        telem_green = self.nominal_telemetry.copy()
        telem_green.update({"psi": 15.0, "target_psi": 0.0})
        self.assertFalse(self.instructor.check_safety_limits(telem_green))
        self.assertEqual(self.instructor.heading_zone, HeadingZone.GREEN)

        # 2. Heading error = 45 deg (Orange Zone)
        telem_orange = self.nominal_telemetry.copy()
        telem_orange.update(
            {"psi": 315.0, "target_psi": 0.0}
        )  # -45 deg error -> 45 wrapped
        self.assertFalse(self.instructor.check_safety_limits(telem_orange))
        self.assertEqual(self.instructor.heading_zone, HeadingZone.ORANGE)

        # 3. Heading error = 75 deg (Red Zone / Unsafe)
        telem_red = self.nominal_telemetry.copy()
        telem_red.update({"psi": 75.0, "target_psi": 0.0})
        self.assertTrue(self.instructor.check_safety_limits(telem_red))
        self.assertEqual(self.instructor.heading_zone, HeadingZone.RED)

    def test_cyclic_circular_synchronization_success(self):
        # Phase 4: Cyclic (roll and pitch) are student controlled
        self.instructor.phase = 4
        self.instructor.initiate_handoff()

        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)
        self.assertFalse(self.instructor.sync_locked[ControlAxis.ROLL])
        self.assertFalse(self.instructor.sync_locked[ControlAxis.PITCH])

        # Set inputs within circular tolerance (Euclidean distance <= 0.04)
        # Roll error = 0.02, Pitch error = 0.02
        # Euclidean distance = sqrt(0.02^2 + 0.02^2) = 0.0283 <= 0.04
        self.vfi[ControlAxis.ROLL] = 0.12
        self.hardware[ControlAxis.ROLL] = 0.10
        self.vfi[ControlAxis.PITCH] = -0.08
        self.hardware[ControlAxis.PITCH] = -0.10

        # First update: 200ms -> still syncing
        self.instructor.update(
            0.2, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)
        self.assertTrue(self.instructor.sync_locked[ControlAxis.ROLL])
        self.assertTrue(self.instructor.sync_locked[ControlAxis.PITCH])

        # Second update: 400ms -> transitions to STUDENT_FLIGHT
        self.instructor.update(
            0.4, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertEqual(self.instructor.system_state, VFIState.STUDENT_FLIGHT)
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.ROLL],
            Authority.STUDENT
        )
        self.assertEqual(
            self.instructor.control_assignment[ControlAxis.PITCH],
            Authority.STUDENT
        )

    def test_cyclic_circular_synchronization_boundary(self):
        # Phase 4: Cyclic (roll and pitch) are student controlled
        self.instructor.phase = 4
        self.instructor.initiate_handoff()

        # Case A: Inside the circular tolerance (3% roll error, 2% pitch error)
        # Dist = sqrt(0.03^2 + 0.02^2) = 0.036 <= 0.04
        self.vfi[ControlAxis.ROLL] = 0.13
        self.hardware[ControlAxis.ROLL] = 0.10
        self.vfi[ControlAxis.PITCH] = -0.08
        self.hardware[ControlAxis.PITCH] = -0.10

        self.instructor.update(
            0.2, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertTrue(self.instructor.sync_locked[ControlAxis.ROLL])
        self.assertTrue(self.instructor.sync_locked[ControlAxis.PITCH])

        # Reset handoff to try Case B
        self.instructor.initiate_handoff()

        # Case B: Outside the circular tolerance but inside the square box
        # Roll error = 0.03 (<= 0.04 limit), Pitch error = 0.03 (<= 0.04 limit)
        # However, Euclidean distance is sqrt(0.03^2 + 0.03^2) = 0.0424 > 0.04!
        self.vfi[ControlAxis.ROLL] = 0.13
        self.hardware[ControlAxis.ROLL] = 0.10
        self.vfi[ControlAxis.PITCH] = -0.07
        self.hardware[ControlAxis.PITCH] = -0.10

        self.instructor.update(
            0.2, self.nominal_telemetry, self.hardware, self.vfi
        )
        self.assertFalse(self.instructor.sync_locked[ControlAxis.ROLL])
        self.assertFalse(self.instructor.sync_locked[ControlAxis.PITCH])
        self.assertEqual(self.instructor.sync_timer, 0.0)


class TestMaybeAdvancePhase(unittest.TestCase):
    """Tests for automatic phase progression via maybe_advance_phase."""

    def setUp(self):
        self.instructor = VirtualInstructor()
        self.instructor._system_state = VFIState.STUDENT_FLIGHT

    def test_excellent_timer_accumulates(self):
        """Excellent envelope increments timer without triggering transition."""
        self.instructor.last_envelope = Envelope.EXCELLENT
        self.instructor.maybe_advance_phase(10.0)
        self.assertAlmostEqual(self.instructor.excellent_timer, 10.0)
        self.assertFalse(self.instructor.transition_pending)

    def test_non_excellent_resets_timer(self):
        """Non-Excellent envelope resets the excellent timer."""
        self.instructor.last_envelope = Envelope.EXCELLENT
        self.instructor.maybe_advance_phase(15.0)
        self.assertAlmostEqual(self.instructor.excellent_timer, 15.0)

        self.instructor.last_envelope = Envelope.GOOD
        self.instructor.maybe_advance_phase(5.0)
        self.assertAlmostEqual(self.instructor.excellent_timer, 0.0)
        self.assertFalse(self.instructor.transition_pending)

    def test_twenty_five_seconds_sets_transition_pending(self):
        """25 s of Excellent sets transition_pending for a mid-course phase."""
        self.instructor.phase = 3
        self.instructor.last_envelope = Envelope.EXCELLENT

        # Accumulate just under the threshold
        self.instructor.maybe_advance_phase(24.9)
        self.assertFalse(self.instructor.transition_pending)

        # Cross the threshold
        self.instructor.maybe_advance_phase(0.2)
        self.assertTrue(self.instructor.transition_pending)
        self.assertEqual(self.instructor.transition_target_phase, 4)
        self.assertFalse(self.instructor.training_complete)
        # Timer should be reset after firing
        self.assertAlmostEqual(self.instructor.excellent_timer, 0.0)

    def test_final_phase_sets_training_complete(self):
        """Completing phase 6 sets training_complete instead of advancing."""
        self.instructor.phase = 6
        self.instructor.last_envelope = Envelope.EXCELLENT

        self.instructor.maybe_advance_phase(25.1)
        self.assertTrue(self.instructor.transition_pending)
        self.assertTrue(self.instructor.training_complete)
        # transition_target_phase stays at 6 (no phase 7)
        self.assertEqual(self.instructor.transition_target_phase, 6)

    def test_transition_does_not_fire_twice(self):
        """Once transition_pending is set, further calls are no-ops."""
        self.instructor.phase = 2
        self.instructor.last_envelope = Envelope.EXCELLENT

        self.instructor.maybe_advance_phase(26.0)
        self.assertTrue(self.instructor.transition_pending)
        target_before = self.instructor.transition_target_phase

        # Further Excellent time should not change state
        self.instructor.last_envelope = Envelope.EXCELLENT
        self.instructor.maybe_advance_phase(60.0)
        self.assertEqual(self.instructor.transition_target_phase, target_before)

    def test_training_complete_blocks_further_transitions(self):
        """After training_complete is set, maybe_advance_phase is a no-op."""
        self.instructor.phase = 6
        self.instructor.training_complete = True
        self.instructor.last_envelope = Envelope.EXCELLENT

        self.instructor.maybe_advance_phase(60.0)
        self.assertFalse(self.instructor.transition_pending)
        self.assertAlmostEqual(self.instructor.excellent_timer, 0.0)


class TestStateTransitions(unittest.TestCase):
    """Tests for transition validation, properties, and events."""

    def setUp(self):
        self.instructor = VirtualInstructor()

    def test_valid_transitions(self):
        """Transitions in the valid table should succeed."""
        # VFI_FLIGHT -> SYNCING
        self.instructor.system_state = VFIState.SYNCING
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)

        # SYNCING -> STUDENT_FLIGHT
        self.instructor.system_state = VFIState.STUDENT_FLIGHT
        self.assertEqual(self.instructor.system_state, VFIState.STUDENT_FLIGHT)

        # STUDENT_FLIGHT -> OVERRIDE
        self.instructor.system_state = VFIState.OVERRIDE
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)

        # OVERRIDE -> RECOVERY_HOLD
        self.instructor.system_state = VFIState.RECOVERY_HOLD
        self.assertEqual(self.instructor.system_state, VFIState.RECOVERY_HOLD)

        # RECOVERY_HOLD -> SYNCING
        self.instructor.system_state = VFIState.SYNCING
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)

    def test_invalid_transition_raises_error(self):
        """Illegal transitions should raise ValueError."""
        # Initial is VFI_FLIGHT. Transition to STUDENT_FLIGHT is invalid.
        with self.assertRaises(ValueError):
            self.instructor.system_state = VFIState.STUDENT_FLIGHT

    def test_reset_to_vfi_flight(self):
        """reset_to_vfi_flight should reset authority and state."""
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.control_assignment[ControlAxis.ROLL] = Authority.STUDENT
        self.instructor.sync_locked[ControlAxis.ROLL] = True

        self.instructor.reset_to_vfi_flight()
        self.assertEqual(self.instructor.system_state, VFIState.VFI_FLIGHT)
        for axis in ControlAxis:
            self.assertEqual(
                self.instructor.control_assignment[axis], Authority.VFI
            )
            self.assertFalse(self.instructor.sync_locked[axis])

    def test_update_result_events(self):
        """update() should return UpdateResult containing events."""
        # Set state to STUDENT_FLIGHT via private field
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.last_envelope = Envelope.EXCELLENT

        # Force phase advance (Excellent duration threshold)
        self.instructor.phase = 3
        # Tick the instructor to trigger auto phase advance
        telemetry = {
            "x": 10.0, "y": 6.0, "z": 20.0,
            "target_x": 10.0, "target_y": 6.0, "target_z": 20.0,
            "phi": 0.0, "theta": 0.0, "psi": 0.0, "R": 0.0,
            "vx": 0.0, "vz": 0.0, "vy": 0.0, "y_agl": 6.0
        }
        hardware = {
            ControlAxis.ROLL: 0.0, ControlAxis.PITCH: 0.0,
            ControlAxis.YAW: 0.0, ControlAxis.COLLECTIVE: 0.0
        }
        vfi = hardware.copy()

        # Call update with large dt to exceed threshold
        res = self.instructor.update(40.0, telemetry, hardware, vfi)

        # Check result is a dict and has events
        self.assertTrue(isinstance(res, dict))
        self.assertTrue(hasattr(res, "events"))
        # Should contain StateChangedEvent to VFI_FLIGHT,
        # then StateChangedEvent to SYNCING, and PhaseAdvancedEvent to 4
        from helicopter_instructor.virtual_instructor import (
            PhaseAdvancedEvent, StateChangedEvent
        )
        phase_events = [
            e for e in res.events if isinstance(e, PhaseAdvancedEvent)
        ]
        self.assertEqual(len(phase_events), 1)
        self.assertEqual(phase_events[0].from_phase, 3)
        self.assertEqual(phase_events[0].to_phase, 4)
        self.assertFalse(phase_events[0].is_final)

    def test_set_hud_caption_style(self):
        """Verifies set_hud_caption saves text, duration, and style."""
        self.instructor.set_hud_caption(
            "TEST CAPTION", duration=5.0, style=CaptionStyle.DANGER
        )
        self.assertEqual(self.instructor.hud_caption, "TEST CAPTION")
        self.assertEqual(self.instructor.hud_caption_timer, 5.0)
        self.assertEqual(self.instructor.hud_caption_style, CaptionStyle.DANGER)

    def test_excellent_timer_resets_on_student_flight_transition(self):
        """Verifies excellent_timer reset on STUDENT_FLIGHT transition."""
        self.instructor.excellent_timer = 15.0
        # Transition path: VFI_FLIGHT -> SYNCING -> STUDENT_FLIGHT
        self.instructor.system_state = VFIState.SYNCING
        self.instructor.system_state = VFIState.STUDENT_FLIGHT
        self.assertEqual(self.instructor.excellent_timer, 0.0)

    def test_celebrating_state_flow(self):
        """Verifies VFIState.CELEBRATING flow during transition."""
        # Start in STUDENT_FLIGHT
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.phase = 3
        # Set all axes to STUDENT control in phase 3
        self.instructor.control_assignment[ControlAxis.YAW] = Authority.STUDENT
        self.instructor.control_assignment[
            ControlAxis.COLLECTIVE
        ] = Authority.STUDENT

        # Simulate Excellent duration to trigger transition pending
        self.instructor.last_envelope = Envelope.EXCELLENT
        self.instructor.maybe_advance_phase(25.0)
        self.assertTrue(self.instructor.transition_pending)

        # Call update() to process the pending transition
        telemetry = {
            "x": 10.0, "y": 6.0, "z": 20.0,
            "target_x": 10.0, "target_y": 6.0, "target_z": 20.0,
            "phi": 0.0, "theta": 0.0, "psi": 0.0, "R": 0.0,
            "vx": 0.0, "vz": 0.0, "vy": 0.0, "y_agl": 6.0
        }
        hardware = {
            ControlAxis.ROLL: 0.1, ControlAxis.PITCH: 0.2,
            ControlAxis.YAW: 0.3, ControlAxis.COLLECTIVE: 0.4
        }
        vfi = {
            ControlAxis.ROLL: -0.1, ControlAxis.PITCH: -0.2,
            ControlAxis.YAW: -0.3, ControlAxis.COLLECTIVE: -0.4
        }

        # Update should transition from STUDENT_FLIGHT to CELEBRATING
        res = self.instructor.update(0.02, telemetry, hardware, vfi)
        self.assertEqual(self.instructor.system_state, VFIState.CELEBRATING)

        # Check student retains control during CELEBRATING state
        self.assertEqual(res[ControlAxis.YAW], hardware[ControlAxis.YAW])
        self.assertEqual(
            res[ControlAxis.COLLECTIVE], hardware[ControlAxis.COLLECTIVE]
        )
        # VFI keeps control of VFI axes
        self.assertEqual(res[ControlAxis.ROLL], vfi[ControlAxis.ROLL])
        self.assertEqual(res[ControlAxis.PITCH], vfi[ControlAxis.PITCH])

        # Resolve celebration by calling advance_phase
        self.instructor.advance_phase(next_phase=4, is_final=False)
        # Should reset state to SYNCING for new phase
        self.assertEqual(self.instructor.system_state, VFIState.SYNCING)
        self.assertEqual(self.instructor.phase, 4)

    def test_celebrating_safety_breach(self):
        """Verifies safety breach during CELEBRATING triggers OVERRIDE."""
        self.instructor._system_state = VFIState.CELEBRATING
        self.instructor.transition_in_progress = True
        # Set student axes to trigger safety checks override
        self.instructor.control_assignment[ControlAxis.YAW] = Authority.STUDENT

        # Telemetry with a critical safety violation (e.g. extreme pitch)
        telemetry = {
            "x": 10.0, "y": 6.0, "z": 20.0,
            "target_x": 10.0, "target_y": 6.0, "target_z": 20.0,
            "phi": 0.0, "theta": 45.0, "psi": 0.0, "R": 0.0,
            "vx": 0.0, "vz": 0.0, "vy": 0.0, "y_agl": 6.0
        }
        hardware = {
            ControlAxis.ROLL: 0.1, ControlAxis.PITCH: 0.2,
            ControlAxis.YAW: 0.3, ControlAxis.COLLECTIVE: 0.4
        }
        vfi = {
            ControlAxis.ROLL: -0.1, ControlAxis.PITCH: -0.2,
            ControlAxis.YAW: -0.3, ControlAxis.COLLECTIVE: -0.4
        }

        res = self.instructor.update(0.02, telemetry, hardware, vfi)
        self.assertEqual(self.instructor.system_state, VFIState.OVERRIDE)
        self.assertFalse(self.instructor.transition_in_progress)

    def test_set_phase_resets_to_vfi_flight(self):
        """set_phase resets state to VFI_FLIGHT instead of syncing."""
        self.instructor._system_state = VFIState.STUDENT_FLIGHT
        self.instructor.phase = 1

        # Manually set phase to 2
        self.instructor.set_phase(2)

        self.assertEqual(self.instructor.system_state, VFIState.VFI_FLIGHT)
        self.assertEqual(self.instructor.phase, 2)


if __name__ == "__main__":
    unittest.main()
