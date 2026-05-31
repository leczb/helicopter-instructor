import math
import os
import sys
import unittest

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0,
    os.path.join(
        base_dir, '..', 'plugin', 'helicopter_instructor', 'autopilot'
    )
)
sys.path.insert(
    0, os.path.join(base_dir, '..', 'plugin', 'helicopter_instructor')
)
sys.path.insert(0, os.path.join(base_dir, '..', 'plugin'))

from helicopter_instructor import virtual_instructor

VirtualInstructor = virtual_instructor.VirtualInstructor
PHASE_CONFIGS = virtual_instructor.PHASE_CONFIGS
M_S_TO_FT_MIN = virtual_instructor.M_S_TO_FT_MIN

class TestVirtualInstructor(unittest.TestCase):
    
    def setUp(self):
        self.instructor = VirtualInstructor()
        # Default nominal state where everything is safe
        self.nominal_telemetry = {
            'phi': 0.0,
            'theta': 0.0,
            'psi': 0.0,
            'P': 0.0,
            'Q': 0.0,
            'R': 0.0,
            'vx': 0.0,
            'vz': 0.0,
            'vy': 0.0,
            'y_agl': 5.0
        }
        # Hardware inputs (student)
        self.hardware = {
            'roll': 0.0,
            'pitch': 0.0,
            'yaw': 0.0,
            'collective': 0.5
        }
        # VFI inputs (autopilot)
        self.vfi = {
            'roll': 0.05,
            'pitch': -0.03,
            'yaw': 0.01,
            'collective': 0.55
        }

    def test_init_state(self):
        self.assertEqual(self.instructor.phase, 1)
        self.assertEqual(self.instructor.system_state, "VFI_FLIGHT")
        for axis in ["roll", "pitch", "yaw", "collective"]:
            self.assertEqual(self.instructor.control_assignment[axis], "VFI")

    def test_initiate_handoff_phase1(self):
        # Phase 1: Yaw Pedals Only
        self.instructor.phase = 1
        self.instructor.initiate_handoff()
        
        self.assertEqual(self.instructor.system_state, "SYNCING")
        self.assertEqual(self.instructor.control_assignment["roll"], "VFI")
        self.assertEqual(self.instructor.control_assignment["pitch"], "VFI")
        self.assertEqual(self.instructor.control_assignment["collective"], "VFI")
        self.assertEqual(self.instructor.control_assignment["yaw"], "VFI") # VFI flies yaw until synced
        
        self.assertTrue(self.instructor.sync_locked["roll"])
        self.assertTrue(self.instructor.sync_locked["pitch"])
        self.assertTrue(self.instructor.sync_locked["collective"])
        self.assertFalse(self.instructor.sync_locked["yaw"]) # Needs syncing

    def test_synchronization_lock_success(self):
        # Phase 1: Yaw is student
        self.instructor.phase = 1
        self.instructor.initiate_handoff()
        
        # Physical yaw is 0.0. VFI target yaw is 0.01.
        # Delta = 0.01 <= 0.04 tolerance -> Matched!
        self.vfi["yaw"] = 0.01
        self.hardware["yaw"] = 0.0
        
        # First update: 200ms -> timer = 0.2. Still syncing.
        out = self.instructor.update(0.2, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "SYNCING")
        self.assertTrue(self.instructor.sync_locked["yaw"]) # Real-time match indicator is True because within tolerance
        self.assertEqual(self.instructor.control_assignment["yaw"], "VFI") # Flight authority is NOT yet student
        self.assertEqual(out["yaw"], self.vfi["yaw"]) # Still VFI output during syncing
        
        # Second update: 400ms -> timer = 0.6 >= 0.5s -> Sync lock matches and transitions to STUDENT_FLIGHT
        # But this transition frame still returns VFI input for aerodynamic smoothness.
        out = self.instructor.update(0.4, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "STUDENT_FLIGHT")
        self.assertEqual(self.instructor.control_assignment["yaw"], "STUDENT")
        self.assertTrue(self.instructor.sync_locked["yaw"])
        self.assertEqual(out["yaw"], self.vfi["yaw"]) 
        
        # Third update: subsequent frame. Output should now be student's hardware deflection!
        out = self.instructor.update(0.02, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertEqual(out["yaw"], self.hardware["yaw"])

    def test_synchronization_drift_resets_timer(self):
        # Phase 1: Yaw is student
        self.instructor.phase = 1
        self.instructor.initiate_handoff()
        
        # Hardware matches at first
        self.hardware["yaw"] = 0.01
        self.vfi["yaw"] = 0.01
        self.instructor.update(0.3, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertEqual(self.instructor.sync_timer, 0.3)
        
        # Hardware drifts away: delta = 0.05 > 0.04
        self.hardware["yaw"] = 0.06
        self.instructor.update(0.1, self.nominal_telemetry, self.hardware, self.vfi)
        
        # Timer should be reset to 0.0 and state remains SYNCING
        self.assertEqual(self.instructor.sync_timer, 0.0)
        self.assertEqual(self.instructor.system_state, "SYNCING")

    def test_safety_envelope_triggers_hard_override(self):
        # Student flying Phase 1
        self.instructor.phase = 1
        self.instructor.system_state = "STUDENT_FLIGHT"
        self.instructor.control_assignment["yaw"] = "STUDENT"
        
        # Telemetry is safe
        self.assertFalse(self.instructor.check_safety_limits(self.nominal_telemetry))
        
        # Test 1: Pitch attitude exceeds 15 deg (e.g. 15.5)
        # Use an unstable rate or roll to keep it in OVERRIDE state during process_recovery
        telem = self.nominal_telemetry.copy()
        telem['theta'] = -15.5
        telem['phi'] = 10.0 # Make attitude unstable to prevent instant recovery hold
        
        self.assertTrue(self.instructor.check_safety_limits(telem))
        
        # Update should trigger hard override and keep in OVERRIDE due to unstable roll
        out = self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "OVERRIDE")
        self.assertEqual(self.instructor.control_assignment["yaw"], "VFI") # Stripped student authority
        self.assertEqual(out["yaw"], self.vfi["yaw"]) # Returns VFI stabilization

    def test_ground_agl_safety_trigger(self):
        # Student flying Phase 1
        self.instructor.phase = 1
        self.instructor.system_state = "STUDENT_FLIGHT"
        self.instructor.control_assignment["yaw"] = "STUDENT"
        
        # AGL falls to 1.8 meters (< 2.0 limit)
        telem = self.nominal_telemetry.copy()
        telem['y_agl'] = 1.8
        telem['phi'] = 10.0 # Make attitude unstable to prevent instant recovery hold
        
        self.assertTrue(self.instructor.check_safety_limits(telem))
        
        # Check update initiates takeover and remains in OVERRIDE due to unstable attitude
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "OVERRIDE")
        self.assertEqual(self.instructor.control_assignment["yaw"], "VFI")
        
        # Reset state for high AGL test
        self.instructor.system_state = "STUDENT_FLIGHT"
        self.instructor.control_assignment["yaw"] = "STUDENT"
        
        # AGL climbs to 12.0 meters (> 10.0 limit)
        telem_high = self.nominal_telemetry.copy()
        telem_high['y_agl'] = 12.0
        telem_high['phi'] = 10.0
        
        self.assertTrue(self.instructor.check_safety_limits(telem_high))
        self.instructor.update(0.02, telem_high, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "OVERRIDE")
        self.assertEqual(self.instructor.control_assignment["yaw"], "VFI")

    def test_soft_intervention_blending_pitch(self):
        # Phase 4: Cyclic is student
        self.instructor.phase = 4
        self.instructor.system_state = "STUDENT_FLIGHT"
        self.instructor.control_assignment["roll"] = "STUDENT"
        self.instructor.control_assignment["pitch"] = "STUDENT"
        
        # Telemetry pitch is safe (5.0 deg <= 10.0 inner boundary) -> 0.0 blending weight
        telem = self.nominal_telemetry.copy()
        telem['theta'] = 5.0
        
        weights = self.instructor.get_blending_weights(telem)
        self.assertEqual(weights["pitch"], 0.0)
        
        # Telemetry pitch is in buffer zone (12.0 deg).
        # Proportional delta = (12 - 10) / 5 = 0.4.
        # omega_pitch = 0.4 * 0.5 = 0.2.
        telem['theta'] = 12.0
        weights = self.instructor.get_blending_weights(telem)
        self.assertAlmostEqual(weights["pitch"], 0.2)
        
        # Test blending output calculation:
        # VFI pitch cmd = -0.03. Student hardware pitch cmd = 0.25.
        # Blended = omega * VFI + (1 - omega) * Student = 0.2 * (-0.03) + 0.8 * 0.25 = -0.006 + 0.20 = 0.194
        self.hardware["pitch"] = 0.25
        out = self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertAlmostEqual(out["pitch"], 0.194)

    def test_ground_drift_affects_both_cyclic_axes(self):
        # Phase 4: Cyclic is student
        self.instructor.phase = 4
        self.instructor.system_state = "STUDENT_FLIGHT"
        self.instructor.control_assignment["roll"] = "STUDENT"
        self.instructor.control_assignment["pitch"] = "STUDENT"
        
        # Ground speed is 10.0 knots (inner 8.0, outer 12.0)
        # Delta = (10 - 8) / 4 = 0.5.
        # omega = 0.5 * 0.5 = 0.25.
        # Both roll and pitch blending weights should be 0.25!
        telem = self.nominal_telemetry.copy()
        # 10 knots in m/s = 10 / 1.94384 = 5.1444
        telem['vx'] = 5.1444
        telem['vz'] = 0.0
        
        weights = self.instructor.get_blending_weights(telem)
        self.assertAlmostEqual(weights["roll"], 0.25, places=3)
        self.assertAlmostEqual(weights["pitch"], 0.25, places=3)

    def test_recovery_hold_and_reset_loop(self):
        # Trigger takeover
        self.instructor.phase = 1
        self.instructor.system_state = "STUDENT_FLIGHT"
        self.instructor.control_assignment["yaw"] = "STUDENT"
        
        telem = self.nominal_telemetry.copy()
        telem['phi'] = 16.0 # Exceeds limit
        
        # 1. Update -> triggers takeover, sets state to OVERRIDE (keeps it there because phi=16 is unstable)
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "OVERRIDE")
        self.assertEqual(self.instructor.control_assignment["yaw"], "VFI")
        
        # 2. Update with unstable telemetry -> should remain in OVERRIDE
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "OVERRIDE")
        
        # 3. Update with stable telemetry -> should transition to RECOVERY_HOLD
        stable_telem = self.nominal_telemetry.copy() # Safe (phi=0, theta=0, vx=0, vz=0, vy=0)
        self.instructor.update(0.02, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "RECOVERY_HOLD")
        self.assertAlmostEqual(self.instructor.recovery_timer, 3.0)
        
        # 4. Update in RECOVERY_HOLD -> counts down
        self.instructor.update(1.0, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "RECOVERY_HOLD")
        self.assertAlmostEqual(self.instructor.recovery_timer, 2.0)
        
        # 5. Countdown expires -> transitions back to SYNCING
        self.instructor.update(2.1, stable_telem, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "SYNCING")
        self.assertEqual(self.instructor.sync_timer, 0.0)

    def test_positive_vertical_speed_limits(self):
        # 1. Hard Takeover: Climbing exceeds +300 ft/min (e.g. 310 ft/min)
        # vy_m_s = 310 / M_S_TO_FT_MIN
        telem = self.nominal_telemetry.copy()
        telem['vy'] = 310.0 / M_S_TO_FT_MIN
        
        self.assertTrue(self.instructor.check_safety_limits(telem))
        
        # 2. Soft Blending: Climbing at 250 ft/min (within +200 to +300 range)
        # Proportional delta = (250 - 200) / 100 = 0.5.
        # omega_collective = 0.5 * 0.5 = 0.25.
        telem_soft = self.nominal_telemetry.copy()
        telem_soft['vy'] = 250.0 / M_S_TO_FT_MIN
        
        self.assertFalse(self.instructor.check_safety_limits(telem_soft))
        weights = self.instructor.get_blending_weights(telem_soft)
        self.assertAlmostEqual(weights["collective"], 0.25)

    def test_hover_safety_distance_takeover(self):
        # 1. Fallback case: lack of coordinates in telemetry does not trigger takeover
        telem_no_coords = self.nominal_telemetry.copy()
        self.assertFalse(self.instructor.check_safety_limits(telem_no_coords))
        
        # 2. Inside boundary / exact center (drift = 0m)
        telem = self.nominal_telemetry.copy()
        telem.update({'x': 10.0, 'z': 20.0, 'target_x': 10.0, 'target_z': 20.0})
        self.assertFalse(self.instructor.check_safety_limits(telem))
        
        # 3. Exactly at the safety limit (drift = 45m, using 27-36-45 right triangle)
        # dist = sqrt(27^2 + 36^2) = 45.0m
        telem.update({'x': 37.0, 'z': 56.0})
        self.assertFalse(self.instructor.check_safety_limits(telem))
        
        # 4. Out of bounds (drift = 45.06m > 45.0m)
        telem.update({'x': 37.1, 'z': 56.0})
        self.assertTrue(self.instructor.check_safety_limits(telem))

    def test_hover_soft_blending_drift(self):
        # 1. Exactly at inner soft boundary (drift = 30m, using 18-24-30 right triangle)
        telem = self.nominal_telemetry.copy()
        telem.update({'x': 18.0, 'z': 24.0, 'target_x': 0.0, 'target_z': 0.0})
        weights = self.instructor.get_blending_weights(telem)
        self.assertEqual(weights["roll"], 0.0)
        self.assertEqual(weights["pitch"], 0.0)
        
        # 2. Inside the soft blending zone (drift = 37.5m, moving straight on the x axis)
        # dist = 37.5m
        # omega = ((37.5 - 30.0) / 15.0) * 0.5 = 0.25
        telem.update({'x': 37.5, 'z': 0.0})
        weights = self.instructor.get_blending_weights(telem)
        self.assertAlmostEqual(weights["roll"], 0.25)
        self.assertAlmostEqual(weights["pitch"], 0.25)
        
        # 3. Exactly at the outer safety limit (drift = 45.0m, moving straight on the x axis)
        # dist = 45.0m
        # omega = ((45.0 - 30.0) / 15.0) * 0.5 = 0.50
        telem.update({'x': 45.0, 'z': 0.0})
        weights = self.instructor.get_blending_weights(telem)
        self.assertAlmostEqual(weights["roll"], 0.50)
        self.assertAlmostEqual(weights["pitch"], 0.50)

    def test_hover_fallback_robustness(self):
        # Verify that lacking coordinate keys in telemetry is handled gracefully
        telem = self.nominal_telemetry.copy()
        if 'x' in telem: del telem['x']
        if 'z' in telem: del telem['z']
        
        # Should not raise any KeyError exceptions
        self.assertFalse(self.instructor.check_safety_limits(telem))
        weights = self.instructor.get_blending_weights(telem)
        self.assertEqual(weights["roll"], 0.0)
        self.assertEqual(weights["pitch"], 0.0)

    def test_safety_takeover_target_override_and_restore(self):
        # 1. Student is flying and is at target coordinates target_x = 10, target_z = 20
        self.instructor.system_state = "STUDENT_FLIGHT"
        telem = self.nominal_telemetry.copy()
        telem.update({'x': 10.0, 'z': 20.0, 'target_x': 10.0, 'target_z': 20.0})
        
        # 2. Helicopter drifts past safety radius: current x = 57.0, z = 20.0 -> drift = 47.0m > 45.0m
        telem.update({'x': 57.0, 'phi': 5.0})
        
        # This should trigger emergency stabilization takeover
        self.instructor.update(0.02, telem, self.hardware, self.vfi)
        
        self.assertEqual(self.instructor.system_state, "OVERRIDE")
        self.assertTrue(self.instructor.drift_recovery_active)
        self.assertEqual(self.instructor.original_target_x, 10.0)
        self.assertEqual(self.instructor.original_target_z, 20.0)
        self.assertEqual(self.instructor.override_target_x, 57.0)
        self.assertEqual(self.instructor.override_target_z, 20.0)
        
        # 3. In the subsequent frames, the OSD coordinates and target are updated.
        # Now telemetry comes in stable (phi=0, theta=0, vy=0, ground speed=0)
        stable_telem = self.nominal_telemetry.copy()
        stable_telem.update({'x': 57.0, 'z': 20.0, 'target_x': 57.0, 'target_z': 20.0})
        
        self.instructor.update(0.02, stable_telem, self.hardware, self.vfi)
        
        # It should transition to RECOVERY_HOLD, clear recovery active, and raise was_drift_recovery_active
        self.assertEqual(self.instructor.system_state, "RECOVERY_HOLD")
        self.assertFalse(self.instructor.drift_recovery_active)
        self.assertTrue(self.instructor.was_drift_recovery_active)
        self.assertIsNone(self.instructor.override_target_x)
        self.assertIsNone(self.instructor.override_target_z)

    def test_heading_safety_limits(self):
        # 1. Heading error = 15 deg (Green Zone)
        telem_green = self.nominal_telemetry.copy()
        telem_green.update({'psi': 15.0, 'target_psi': 0.0})
        self.assertFalse(self.instructor.check_safety_limits(telem_green))
        self.assertEqual(self.instructor.heading_zone, "green")
        
        # 2. Heading error = 45 deg (Orange Zone)
        telem_orange = self.nominal_telemetry.copy()
        telem_orange.update({'psi': 315.0, 'target_psi': 0.0}) # -45 deg error -> 45 wrapped
        self.assertFalse(self.instructor.check_safety_limits(telem_orange))
        self.assertEqual(self.instructor.heading_zone, "orange")
        
        # 3. Heading error = 75 deg (Red Zone / Unsafe)
        telem_red = self.nominal_telemetry.copy()
        telem_red.update({'psi': 75.0, 'target_psi': 0.0})
        self.assertTrue(self.instructor.check_safety_limits(telem_red))
        self.assertEqual(self.instructor.heading_zone, "red")

    def test_cyclic_circular_synchronization_success(self):
        # Phase 4: Cyclic (roll and pitch) are student controlled
        self.instructor.phase = 4
        self.instructor.initiate_handoff()
        
        self.assertEqual(self.instructor.system_state, "SYNCING")
        self.assertFalse(self.instructor.sync_locked["roll"])
        self.assertFalse(self.instructor.sync_locked["pitch"])
        
        # Set inputs within circular tolerance (Euclidean distance <= 0.04)
        # Roll error = 0.02, Pitch error = 0.02
        # Euclidean distance = sqrt(0.02^2 + 0.02^2) = 0.0283 <= 0.04
        self.vfi["roll"] = 0.12
        self.hardware["roll"] = 0.10
        self.vfi["pitch"] = -0.08
        self.hardware["pitch"] = -0.10
        
        # First update: 200ms -> still syncing but cyclic axes should show locked/aligned
        self.instructor.update(0.2, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "SYNCING")
        self.assertTrue(self.instructor.sync_locked["roll"])
        self.assertTrue(self.instructor.sync_locked["pitch"])
        
        # Second update: 400ms -> total 600ms >= 500ms sync duration -> transitions to STUDENT_FLIGHT
        self.instructor.update(0.4, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertEqual(self.instructor.system_state, "STUDENT_FLIGHT")
        self.assertEqual(self.instructor.control_assignment["roll"], "STUDENT")
        self.assertEqual(self.instructor.control_assignment["pitch"], "STUDENT")

    def test_cyclic_circular_synchronization_boundary(self):
        # Phase 4: Cyclic (roll and pitch) are student controlled
        self.instructor.phase = 4
        self.instructor.initiate_handoff()
        
        # Case A: Inside the circular tolerance (3% roll error, 2% pitch error)
        # Dist = sqrt(0.03^2 + 0.02^2) = 0.036 <= 0.04
        self.vfi["roll"] = 0.13
        self.hardware["roll"] = 0.10
        self.vfi["pitch"] = -0.08
        self.hardware["pitch"] = -0.10
        
        self.instructor.update(0.2, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertTrue(self.instructor.sync_locked["roll"])
        self.assertTrue(self.instructor.sync_locked["pitch"])
        
        # Reset handoff to try Case B
        self.instructor.initiate_handoff()
        
        # Case B: Outside the circular tolerance but inside the square box
        # Roll error = 0.03 (<= 0.04 limit), Pitch error = 0.03 (<= 0.04 limit)
        # However, Euclidean distance is sqrt(0.03^2 + 0.03^2) = 0.0424 > 0.04!
        self.vfi["roll"] = 0.13
        self.hardware["roll"] = 0.10
        self.vfi["pitch"] = -0.07
        self.hardware["pitch"] = -0.10
        
        self.instructor.update(0.2, self.nominal_telemetry, self.hardware, self.vfi)
        self.assertFalse(self.instructor.sync_locked["roll"])
        self.assertFalse(self.instructor.sync_locked["pitch"])
        self.assertEqual(self.instructor.sync_timer, 0.0)

if __name__ == '__main__':
    unittest.main()
