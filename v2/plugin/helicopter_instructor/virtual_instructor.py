import math

from helicopter_instructor.envelope_limits import (
    LIMIT_HDG_GREEN_DEG,
    LIMIT_HDG_ORANGE_DEG,
    LIMIT_DRIFT_ORANGE_M,
    LIMIT_DRIFT_RED_M,
    LIMIT_RECOVERY_ALT_RATE_M_S,
    LIMIT_RECOVERY_SPEED_M_S,
)

# Conversion constants
M_S_TO_KNOTS = 1.94384
M_S_TO_FT_MIN = 196.8504

# Seconds of continuous Excellent rating required before phase advance
PHASE_EXCELLENT_REQUIRED_S = 35.0

# Total number of training phases
MAX_PHASE = 6

# Phase configs mapping (1 to 6)
# Defines which axes are STUDENT-controlled vs VFI-controlled
PHASE_CONFIGS = {
    1: {"roll": "VFI", "pitch": "VFI", "yaw": "STUDENT", "collective": "VFI"},
    2: {"roll": "VFI", "pitch": "VFI", "yaw": "VFI", "collective": "STUDENT"},
    3: {"roll": "VFI", "pitch": "VFI", "yaw": "STUDENT", "collective": "STUDENT"},
    4: {"roll": "STUDENT", "pitch": "STUDENT", "yaw": "VFI", "collective": "VFI"},
    5: {"roll": "STUDENT", "pitch": "STUDENT", "yaw": "STUDENT", "collective": "VFI"},
    6: {"roll": "STUDENT", "pitch": "STUDENT", "yaw": "STUDENT", "collective": "STUDENT"}
}

# Human-readable phase names mapping (1 to 6)
PHASE_NAMES = {
    1: "PEDALS ONLY (YAW)",
    2: "COLLECTIVE ONLY (ALTITUDE)",
    3: "COLLECTIVE + PEDALS",
    4: "CYCLIC ONLY (ROLL/PITCH)",
    5: "CYCLIC + PEDALS",
    6: "ALL THREE CONTROLS (FULL HANDOVER)"
}

class VirtualInstructor(object):
    """Core Virtual Flight Instructor (VFI) curriculum and safety logic.

    Implements a 6-phase building-block curriculum, anti-jerk synchronization,
    AGL safety monitoring, and a post-takeover recovery sequence.
    """

    def __init__(self):
        """Initializes the virtual instructor state and configuration."""
        self.phase = 1
        self.last_envelope = None
        self.excellent_timer = 0.0
        # Set by maybe_advance_phase() when the student has held Excellent
        # for PHASE_EXCELLENT_REQUIRED_S seconds. The plugin flight loop reads
        # this flag and orchestrates the audio/state transition sequence,
        # then resets it.
        self.transition_pending = False
        self.transition_target_phase = None
        # Set to True when phase 6 is mastered; prevents further advancement.
        self.training_complete = False
        # States: VFI_FLIGHT, SYNCING, STUDENT_FLIGHT, OVERRIDE, RECOVERY_HOLD
        self.system_state = "VFI_FLIGHT"

        # Dead-zone matching window configuration
        self.match_tolerance = 0.04  # ±4% matching window
        self.sync_timer = 0.0
        self.sync_hold_duration = 0.5  # Must align for 500ms

        # Recovery timing
        self.recovery_timer = 0.0
        self.recovery_hold_duration = 3.0  # Stable hold for 3 seconds

        # Hovering safety distance configurations (bounding circle)
        self.hover_soft_radius = LIMIT_DRIFT_ORANGE_M  # Caution zone boundary starts
        self.hover_safety_radius = LIMIT_DRIFT_RED_M  # Hard override takeover starts

        # Active control assignments (starts all VFI-controlled)
        self.control_assignment = {
            "roll": "VFI",
            "pitch": "VFI",
            "yaw": "VFI",
            "collective": "VFI",
        }
        self.sync_locked = {
            "roll": False,
            "pitch": False,
            "yaw": False,
            "collective": False,
        }

        # Subtitles / visual announcements queue
        self.hud_caption = ""
        self.hud_caption_timer = 0.0

        # Drift-based stabilization takeover state
        self.drift_recovery_active = False
        self.was_drift_recovery_active = False
        self.original_target_x = None
        self.original_target_y = None
        self.original_target_z = None
        self.override_target_x = None
        self.override_target_y = None
        self.override_target_z = None

        # Heading Safety Zone Detection ("green", "orange", or "red")
        self.heading_zone = "green"

    def set_hud_caption(self, text, duration=3.0):
        """Sets a visual caption/subtitle to be shown on the OSD HUD."""
        self.hud_caption = text
        self.hud_caption_timer = duration

    def set_phase(self, phase_num):
        """Manually overrides the curriculum phase.

        Args:
            phase_num: The target curriculum phase number (1 to 6).
        """
        if phase_num in PHASE_CONFIGS:
            self.phase = phase_num
            # If the student is already flying, we should shift to syncing the
            # new phase controls
            if self.system_state in ["STUDENT_FLIGHT", "SYNCING"]:
                self.initiate_handoff()
            else:
                self.set_hud_caption(f"PHASE {self.phase} SELECTED")

    def initiate_handoff(self):
        """Triggers the handoff sequence for the current phase."""
        self.system_state = "SYNCING"
        self.sync_timer = 0.0

        # Determine target axes that belong to the student in this phase
        phase_config = PHASE_CONFIGS[self.phase]
        for axis in self.control_assignment:
            # Re-initialize syncing locks. If an axis belongs to VFI, it's
            # immediately "synced" (no sync needed)
            if phase_config[axis] == "VFI":
                self.control_assignment[axis] = "VFI"
                self.sync_locked[axis] = True
            else:
                # VFI holds flight authority during matching
                self.control_assignment[axis] = "VFI"
                self.sync_locked[axis] = False

        self.set_hud_caption("PREPARE TO TAKE THE CONTROLS", duration=4.0)

    def update(self, dt, telemetry, hardware, vfi_inputs):
        """Main update execution loop called every frame at 50Hz.

        Args:
            dt: Time step in seconds.
            telemetry: Dict containing current flight states:
              'phi', 'theta', 'psi', 'P', 'Q', 'R', 'vx', 'vz', 'vy', 'y_agl',
              'x', 'z', 'target_x', 'target_z'.
            hardware: Dict containing raw pilot inputs:
              { 'roll', 'pitch', 'yaw', 'collective' }.
            vfi_inputs: Dict containing calculated VFI commands:
              { 'roll', 'pitch', 'yaw', 'collective' }.

        Returns:
            Dict containing active deflection outputs injected into X-Plane:
            { 'roll', 'pitch', 'yaw', 'collective' }.
        """
        # Update caption timer
        if self.hud_caption_timer > 0.0:
            self.hud_caption_timer -= dt
            if self.hud_caption_timer <= 0.0:
                self.hud_caption = ""

        # 1. RUN SAFETY AND ENVELOPE CHECKS IF STUDENT HAS OR IS TAKING CONTROLS
        if self.system_state in ["STUDENT_FLIGHT", "SYNCING"]:
            x = telemetry.get('x', None)
            y = telemetry.get('y', None)
            z = telemetry.get('z', None)
            target_x = telemetry.get('target_x', None)
            target_y = telemetry.get('target_y', None)
            target_z = telemetry.get('target_z', None)

            # Check if any safety limit is violated
            is_unsafe = self.check_safety_limits(telemetry)

            if is_unsafe:
                # Capture current position as the temporary stabilization hover
                # target
                if (
                    x is not None
                    and y is not None
                    and z is not None
                    and target_x is not None
                    and target_y is not None
                    and target_z is not None
                ):
                    self.drift_recovery_active = True
                    self.original_target_x = target_x
                    self.original_target_y = target_y
                    self.original_target_z = target_z
                    self.override_target_x = x
                    self.override_target_y = y
                    self.override_target_z = z
                self.trigger_hard_override()
                self.set_hud_caption(
                    "I HAVE THE CONTROLS - STABILIZING", duration=4.0
                )
                return self.process_recovery(dt, vfi_inputs, telemetry)

        # 2. STATE MACHINE ROUTING
        if self.system_state == "VFI_FLIGHT":
            # 100% VFI flying
            return vfi_inputs

        elif self.system_state == "SYNCING":
            return self.process_synchronization(dt, hardware, vfi_inputs)

        elif self.system_state == "STUDENT_FLIGHT":
            # Check for automatic phase advancement before routing inputs.
            self.maybe_advance_phase(dt)
            return self.process_student_inputs(telemetry, hardware, vfi_inputs)

        elif self.system_state == "OVERRIDE":
            # Direct recovery execution
            return self.process_recovery(dt, vfi_inputs, telemetry)

        elif self.system_state == "RECOVERY_HOLD":
            # Stage 3: slowly move recovery targets horizontally and vertically towards original
            if self.drift_recovery_active:
                self._update_recovery_targets(dt)
            else:
                # Timer only counts down after the target has fully returned
                self.recovery_timer -= dt
                if self.recovery_timer <= 0.0:
                    self.set_hud_caption(
                        "AIRCRAFT STABLE. PREPARE TO SYNC.", duration=4.0
                    )
                    self.initiate_handoff()
            return vfi_inputs

        return vfi_inputs

    def check_safety_limits(self, telemetry):
        """Checks structural/aerodynamic hazard boundaries.

        Args:
            telemetry: Dict containing current flight states.

        Returns:
            True if any safety limit is violated, False otherwise.
        """
        # Pitch limit (+-15 degrees)
        if abs(telemetry.get('theta', 0.0)) > 15.0:
            return True
        # Roll limit (+-15 degrees)
        if abs(telemetry.get('phi', 0.0)) > 15.0:
            return True
        # Yaw rate limit (+-30 deg/sec)
        if abs(telemetry.get('R', 0.0)) > 30.0:
            return True

        # Vertical speed: sinking > 300 ft/min or climbing > 300 ft/min
        vy_m_s = telemetry.get('vy', 0.0)
        vspeed_ft_min = vy_m_s * M_S_TO_FT_MIN
        if vspeed_ft_min < -300.0 or vspeed_ft_min > 300.0:
            return True

        # Ground speed drift > 12 knots
        vx = telemetry.get('vx', 0.0)
        vz = telemetry.get('vz', 0.0)
        gs_m_s = math.sqrt(vx**2 + vz**2)
        gs_knots = gs_m_s * M_S_TO_KNOTS
        if gs_knots > 12.0:
            return True

        # Terrain height (AGL) < 2.0 meters or > 10.0 meters
        y_agl = telemetry.get('y_agl', 10.0)
        if y_agl < 2.0 or y_agl > 10.0:
            return True

        # Heading Safety Zone Detection
        # (+-0..green green, +-green..orange orange, outside orange red/unsafe)
        psi = telemetry.get('psi', None)
        target_psi = telemetry.get('target_psi', None)
        if psi is not None and target_psi is not None:
            err = (target_psi - psi + 180.0) % 360.0 - 180.0
            abs_err = abs(err)
            if abs_err <= LIMIT_HDG_GREEN_DEG:
                self.heading_zone = "green"
            elif abs_err <= LIMIT_HDG_ORANGE_DEG:
                self.heading_zone = "orange"
            else:
                self.heading_zone = "red"
                return True
        else:
            self.heading_zone = "green"

        # Hovering safety distance from target (default: 45 meters)
        x = telemetry.get('x', None)
        z = telemetry.get('z', None)
        target_x = telemetry.get('target_x', None)
        target_z = telemetry.get('target_z', None)
        if (
            x is not None
            and z is not None
            and target_x is not None
            and target_z is not None
        ):
            dist = math.sqrt((x - target_x)**2 + (z - target_z)**2)
            if dist > self.hover_safety_radius:
                return True

        return False

    def process_synchronization(self, dt, hardware, vfi_inputs):
        """Monitors physical controls until they match active VFI commands.

        Args:
            dt: Time step in seconds.
            hardware: Dict containing raw pilot inputs.
            vfi_inputs: Dict containing calculated VFI commands.

        Returns:
            Dict containing control command outputs.
        """
        phase_config = PHASE_CONFIGS[self.phase]
        all_matched = True

        # Check if cyclic controls are student-controlled in this phase
        cyclic_student = (
            phase_config["roll"] == "STUDENT"
            and phase_config["pitch"] == "STUDENT"
        )

        # Check cyclic as a circular 2D distance
        if cyclic_student:
            cyclic_dist = math.sqrt(
                (hardware["roll"] - vfi_inputs["roll"])**2
                + (hardware["pitch"] - vfi_inputs["pitch"])**2
            )
            if cyclic_dist <= self.match_tolerance:
                self.sync_locked["roll"] = True
                self.sync_locked["pitch"] = True
            else:
                self.sync_locked["roll"] = False
                self.sync_locked["pitch"] = False
                all_matched = False
        else:
            self.sync_locked["roll"] = True
            self.sync_locked["pitch"] = True

        # Check other axes individually (yaw, collective)
        for axis in ["yaw", "collective"]:
            if phase_config[axis] == "STUDENT":
                delta = abs(hardware[axis] - vfi_inputs[axis])
                if delta <= self.match_tolerance:
                    self.sync_locked[axis] = True
                else:
                    self.sync_locked[axis] = False
                    all_matched = False
            else:
                # Immediately locked if not under student control
                self.sync_locked[axis] = True

        if all_matched:
            self.sync_timer += dt
            if self.sync_timer >= self.sync_hold_duration:
                # Synchronization lock succeeded!
                # Hot-swap authority to student
                for axis in ["roll", "pitch", "yaw", "collective"]:
                    if phase_config[axis] == "STUDENT":
                        self.control_assignment[axis] = "STUDENT"

                self.system_state = "STUDENT_FLIGHT"
                self.set_hud_caption("YOU HAVE THE CONTROLS", duration=3.0)
        else:
            # Reset timer if any axis drifts out of the matching dead-zone
            self.sync_timer = 0.0

        # Return VFI inputs during matching to prevent visual jumps
        return vfi_inputs

    def maybe_advance_phase(self, dt):
        """Tracks Excellent envelope duration and signals a phase transition.

        Should be called every frame while in STUDENT_FLIGHT. When the student
        has maintained an Excellent proficiency envelope for at least
        PHASE_EXCELLENT_REQUIRED_S seconds, sets ``transition_pending = True``
        and ``transition_target_phase`` to the next phase number (or to the
        current phase if training is already complete) for the plugin to act on.

        Args:
            dt: Time step in seconds.
        """
        if self.training_complete or self.transition_pending:
            return

        if self.last_envelope == "Excellent":
            self.excellent_timer += dt
        else:
            self.excellent_timer = 0.0

        if self.excellent_timer >= PHASE_EXCELLENT_REQUIRED_S:
            self.excellent_timer = 0.0
            self.transition_pending = True
            if self.phase < MAX_PHASE:
                self.transition_target_phase = self.phase + 1
            else:
                # Already on the final phase; signal completion.
                self.transition_target_phase = self.phase
                self.training_complete = True

    def process_student_inputs(self, telemetry, hardware, vfi_inputs):
        """Processes flight inputs without blending, routing full authority to student on active axes.

        Args:
            telemetry: Dict containing current flight states.
            hardware: Dict containing raw pilot inputs.
            vfi_inputs: Dict containing calculated VFI commands.

        Returns:
            Dict containing final control commands.
        """
        output = {}
        for axis in ["roll", "pitch", "yaw", "collective"]:
            if self.control_assignment[axis] == "STUDENT":
                output[axis] = hardware[axis]
            else:
                output[axis] = vfi_inputs[axis]
        return output

    def _update_recovery_targets(self, dt):
        """Updates recovery target interpolation horizontally and vertically."""
        if not self.drift_recovery_active:
            return

        # 1. Update override_target_y (vertical)
        y_arrived = True
        if self.override_target_y is not None and self.original_target_y is not None:
            diff_y = self.original_target_y - self.override_target_y
            step_y = LIMIT_RECOVERY_ALT_RATE_M_S * dt
            if abs(diff_y) <= step_y:
                self.override_target_y = self.original_target_y
            else:
                self.override_target_y += math.copysign(step_y, diff_y)
                y_arrived = False

        # 2. Update override_target_x and override_target_z (horizontal)
        xz_arrived = True
        if (
            self.override_target_x is not None
            and self.original_target_x is not None
            and self.override_target_z is not None
            and self.original_target_z is not None
        ):
            dx = self.original_target_x - self.override_target_x
            dz = self.original_target_z - self.override_target_z
            dist = math.sqrt(dx**2 + dz**2)
            step_xz = LIMIT_RECOVERY_SPEED_M_S * dt
            if dist <= step_xz:
                self.override_target_x = self.original_target_x
                self.override_target_z = self.original_target_z
            else:
                ratio = step_xz / dist
                self.override_target_x += dx * ratio
                self.override_target_z += dz * ratio
                xz_arrived = False

        # 3. If completely arrived, clear the override states
        if y_arrived and xz_arrived:
            self.was_drift_recovery_active = True
            self.drift_recovery_active = False
            self.override_target_x = None
            self.override_target_y = None
            self.override_target_z = None
            self.set_hud_caption(
                "AIRCRAFT STABLE. RESTORING HOVER TARGET.",
                duration=4.0,
            )

    def trigger_hard_override(self):
        """Instantly severs user authority and starts the recovery state."""
        self.system_state = "OVERRIDE"
        # Revoke all student authority immediately
        for axis in self.control_assignment:
            self.control_assignment[axis] = "VFI"
            self.sync_locked[axis] = False

        self.set_hud_caption("I HAVE THE CONTROLS", duration=4.0)

    def process_recovery(self, dt, vfi_inputs, telemetry):
        """Executes a 5-step stabilization and hold sequence.

        Args:
            dt: Time step in seconds.
            vfi_inputs: Dict containing calculated VFI commands.
            telemetry: Dict containing current flight states.

        Returns:
            Dict containing control deflection commands.
        """
        # Step 1: Sever State - Already handled by trigger_hard_override setting
        # assignments to VFI.

        # Step 2: Attitude stabilization is handled naturally by returning VFI
        # inputs, which command maximum cyclic corrections to drive pitch and
        # roll to 0.

        # Step 3: Altitude & Yaw stabilization dampening
        # Collective is adjusted to establish positive vertical lift, and yaw
        # to damp spin. This is already handled by VFI controller update loop
        # outputs!

        # Stage 2 & 3: slowly move both vertical and horizontal hover targets back immediately
        if self.drift_recovery_active:
            self._update_recovery_targets(dt)

        # Step 4: Check if aircraft is stable to begin the cool-down hold.
        # Definitions of stable: pitch & roll < 2 degrees, sinking rate
        # arrested (> -50 ft/min), ground speed < 1.0 knot, and altitude
        # error is small.
        phi = abs(telemetry.get('phi', 0.0))
        theta = abs(telemetry.get('theta', 0.0))
        vy = telemetry.get('vy', 0.0) * M_S_TO_FT_MIN
        vx = telemetry.get('vx', 0.0)
        vz = telemetry.get('vz', 0.0)
        gs_knots = math.sqrt(vx**2 + vz**2) * M_S_TO_KNOTS

        is_stable = (phi < 2.0 and theta < 2.0 and vy > -50.0 and gs_knots < 1.0)

        if self.system_state == "OVERRIDE":
            if is_stable:
                # Transition to Step 4: Cool-down Hold for 3 seconds / Target Translation
                self.system_state = "RECOVERY_HOLD"
                self.recovery_timer = self.recovery_hold_duration

        # Return VFI inputs
        return vfi_inputs
