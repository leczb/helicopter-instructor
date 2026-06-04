import logging
import math

from helicopter_instructor.enums import Authority
from helicopter_instructor.enums import CaptionStyle
from helicopter_instructor.enums import ControlAxis
from helicopter_instructor.enums import Envelope
from helicopter_instructor.enums import HeadingZone
from helicopter_instructor.enums import VFIState

from helicopter_instructor.envelope_limits import (
    LIMIT_HDG_GREEN_DEG,
    LIMIT_HDG_ORANGE_DEG,
    LIMIT_DRIFT_ORANGE_M,
    LIMIT_DRIFT_RED_M,
    LIMIT_RECOVERY_ALT_RATE_M_S,
    LIMIT_RECOVERY_SPEED_M_S,
    LIMIT_ATTITUDE_DEG,
    LIMIT_YAW_RATE_DEG_S,
    LIMIT_VSPEED_FT_MIN,
    LIMIT_GS_KNOTS,
    LIMIT_AGL_MIN_M,
    LIMIT_AGL_MAX_M,
    LIMIT_RECOVERY_ATTITUDE_DEG,
    LIMIT_RECOVERY_SINK_FT_MIN,
    LIMIT_RECOVERY_GS_KNOTS,
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
    1: {
        ControlAxis.ROLL: Authority.VFI,
        ControlAxis.PITCH: Authority.VFI,
        ControlAxis.YAW: Authority.STUDENT,
        ControlAxis.COLLECTIVE: Authority.VFI,
    },
    2: {
        ControlAxis.ROLL: Authority.VFI,
        ControlAxis.PITCH: Authority.VFI,
        ControlAxis.YAW: Authority.VFI,
        ControlAxis.COLLECTIVE: Authority.STUDENT,
    },
    3: {
        ControlAxis.ROLL: Authority.VFI,
        ControlAxis.PITCH: Authority.VFI,
        ControlAxis.YAW: Authority.STUDENT,
        ControlAxis.COLLECTIVE: Authority.STUDENT,
    },
    4: {
        ControlAxis.ROLL: Authority.STUDENT,
        ControlAxis.PITCH: Authority.STUDENT,
        ControlAxis.YAW: Authority.VFI,
        ControlAxis.COLLECTIVE: Authority.VFI,
    },
    5: {
        ControlAxis.ROLL: Authority.STUDENT,
        ControlAxis.PITCH: Authority.STUDENT,
        ControlAxis.YAW: Authority.STUDENT,
        ControlAxis.COLLECTIVE: Authority.VFI,
    },
    6: {
        ControlAxis.ROLL: Authority.STUDENT,
        ControlAxis.PITCH: Authority.STUDENT,
        ControlAxis.YAW: Authority.STUDENT,
        ControlAxis.COLLECTIVE: Authority.STUDENT,
    },
}

# Human-readable phase names mapping (1 to 6)
PHASE_NAMES = {
    1: "PEDALS ONLY (YAW)",
    2: "COLLECTIVE ONLY (ALTITUDE)",
    3: "COLLECTIVE + PEDALS",
    4: "CYCLIC ONLY (ROLL/PITCH)",
    5: "CYCLIC + PEDALS",
    6: "ALL THREE CONTROLS (FULL HANDOVER)",
}

log = logging.getLogger("helicopter_instructor")


class VFIEvent(object):
    """Base class for all virtual instructor state machine events."""
    pass


class PhaseAdvancedEvent(VFIEvent):
    """Triggered when a training phase is automatically completed.

    Attributes:
        from_phase: The curriculum phase number before the transition.
        to_phase: The curriculum phase number after the transition.
        is_final: True if phase 6 was completed and training is now finished.
    """

    def __init__(self, from_phase, to_phase, is_final):
        self.from_phase = from_phase
        self.to_phase = to_phase
        self.is_final = is_final


class StateChangedEvent(VFIEvent):
    """Triggered when the state machine transitions between states.

    Attributes:
        from_state: The state before the transition.
        to_state: The state after the transition.
    """

    def __init__(self, from_state, to_state):
        self.from_state = from_state
        self.to_state = to_state


class UpdateResult(dict):
    """A dictionary subclass that holds calculated commands and transition events.

    Behaves exactly like a dict for backward compatibility with existing tests
    and callers, but exposes an `events` attribute.
    """

    def __init__(self, commands, events):
        super(UpdateResult, self).__init__(commands)
        self.events = events


# Valid state transitions for validation
_VALID_TRANSITIONS = {
    VFIState.VFI_FLIGHT: {VFIState.SYNCING, VFIState.VFI_FLIGHT},
    VFIState.SYNCING: {
        VFIState.STUDENT_FLIGHT,
        VFIState.OVERRIDE,
        VFIState.VFI_FLIGHT,
        VFIState.SYNCING,
    },
    VFIState.STUDENT_FLIGHT: {
        VFIState.OVERRIDE,
        VFIState.VFI_FLIGHT,
        VFIState.SYNCING,
    },
    VFIState.OVERRIDE: {VFIState.RECOVERY_HOLD, VFIState.VFI_FLIGHT},
    VFIState.RECOVERY_HOLD: {VFIState.SYNCING, VFIState.VFI_FLIGHT},
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
        self._system_state = VFIState.VFI_FLIGHT
        self._events = []

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
            ControlAxis.ROLL: Authority.VFI,
            ControlAxis.PITCH: Authority.VFI,
            ControlAxis.YAW: Authority.VFI,
            ControlAxis.COLLECTIVE: Authority.VFI,
        }
        self.sync_locked = {
            ControlAxis.ROLL: False,
            ControlAxis.PITCH: False,
            ControlAxis.YAW: False,
            ControlAxis.COLLECTIVE: False,
        }

        # Subtitles / visual announcements queue
        self.hud_caption = ""
        self.hud_caption_timer = 0.0
        self.hud_caption_style = CaptionStyle.INFO

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
        self.heading_zone = HeadingZone.GREEN

    @property
    def system_state(self):
        """Gets the current state of the Virtual Flight Instructor."""
        return self._system_state

    @system_state.setter
    def system_state(self, new_state):
        """Sets the state of the VFI and validates the transition.

        Args:
            new_state: The target VFIState.

        Raises:
            TypeError: If new_state is not a VFIState.
            ValueError: If the transition from current state is not allowed.
        """
        if not isinstance(new_state, VFIState):
            raise TypeError(
                f"State must be a VFIState enum, got {type(new_state)}"
            )
        old_state = self._system_state
        if old_state != new_state:
            valid_targets = _VALID_TRANSITIONS.get(old_state, set())
            if new_state not in valid_targets:
                raise ValueError(
                    f"Invalid transition: {old_state} -> {new_state}"
                )
            self._system_state = new_state
            if new_state == VFIState.STUDENT_FLIGHT:
                self.excellent_timer = 0.0
            log.info(f"VFI state transition: {old_state.name} -> {new_state.name}")
            self._emit_event(StateChangedEvent(old_state, new_state))

    def reset_to_vfi_flight(self):
        """Resets the instructor back to full VFI flight authority."""
        self.system_state = VFIState.VFI_FLIGHT
        for axis in self.control_assignment:
            self.control_assignment[axis] = Authority.VFI
            self.sync_locked[axis] = False

    def _emit_event(self, event):
        """Emits an event to be picked up by update()."""
        self._events.append(event)

    def set_hud_caption(self, text, duration=3.0, style=CaptionStyle.INFO):
        """Sets a visual banner/subtitle to be shown on the HUD.

        Args:
            text: The text string to display.
            duration: Time in seconds to display the banner.
            style: The color style (CaptionStyle).
        """
        self.hud_caption = text
        self.hud_caption_timer = duration
        self.hud_caption_style = style

    def set_phase(self, phase_num):
        """Manually overrides the curriculum phase.

        Args:
            phase_num: The target curriculum phase number (1 to 6).
        """
        if phase_num in PHASE_CONFIGS:
            old_phase = self.phase
            self.phase = phase_num
            log.info(
                f"Lesson phase manually set: Phase {old_phase} ({PHASE_NAMES[old_phase]}) -> "
                f"Phase {phase_num} ({PHASE_NAMES[phase_num]})"
            )
            # If the student is already flying, we should shift to syncing the
            # new phase controls
            if self.system_state in (
                VFIState.STUDENT_FLIGHT,
                VFIState.SYNCING,
            ):
                self.initiate_handoff()
            else:
                self.set_hud_caption(f"PHASE {self.phase} SELECTED")

    def initiate_handoff(self):
        """Triggers the handoff sequence for the current phase."""
        self.system_state = VFIState.SYNCING
        self.sync_timer = 0.0

        # Determine target axes that belong to the student in this phase
        phase_config = PHASE_CONFIGS[self.phase]
        student_axes = []
        for axis in self.control_assignment:
            # Re-initialize syncing locks. If an axis belongs to VFI, it's
            # immediately "synced" (no sync needed)
            if phase_config[axis] == Authority.VFI:
                self.control_assignment[axis] = Authority.VFI
                self.sync_locked[axis] = True
            else:
                # VFI holds flight authority during matching
                self.control_assignment[axis] = Authority.VFI
                self.sync_locked[axis] = False
                student_axes.append(axis.name)

        log.info(
            f"Handoff sequence initiated for Phase {self.phase} ({PHASE_NAMES[self.phase]}). "
            f"Student must synchronize hardware for axes: {student_axes}."
        )

        self.set_hud_caption(
            "PREPARE TO TAKE THE CONTROLS",
            duration=4.0,
            style=CaptionStyle.WARNING,
        )

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

        # Collect and clear any events that accumulated between frames
        events = list(self._events)
        self._events.clear()

        # 1. RUN SAFETY AND ENVELOPE CHECKS IF STUDENT HAS OR IS TAKING CONTROLS
        if self.system_state in (
            VFIState.STUDENT_FLIGHT,
            VFIState.SYNCING,
        ):
            x = telemetry.get("x", None)
            y = telemetry.get("y", None)
            z = telemetry.get("z", None)
            target_x = telemetry.get("target_x", None)
            target_y = telemetry.get("target_y", None)
            target_z = telemetry.get("target_z", None)

            # Check if any safety limit is violated
            breach_reason = self.get_safety_breach_reason(telemetry)

            if breach_reason is not None:
                # Log detailed safety breach reasons (triggered exactly once on state transition)
                log.warning(
                    f"Safety Override Triggered: {breach_reason} | Telemetry snapshot: "
                    f"pitch={telemetry.get('theta', 0.0):.1f}°, "
                    f"roll={telemetry.get('phi', 0.0):.1f}°, "
                    f"yaw_rate={telemetry.get('R', 0.0):.1f}°/s, "
                    f"vspeed={telemetry.get('vy', 0.0) * M_S_TO_FT_MIN:.1f} ft/min, "
                    f"agl={telemetry.get('y_agl', 0.0):.1f}m"
                )

                # Capture current position as the temporary stabilization hover target
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
                    "I HAVE THE CONTROLS - STABILIZING",
                    duration=4.0,
                    style=CaptionStyle.DANGER,
                )
                return UpdateResult(
                    self.process_recovery(dt, vfi_inputs, telemetry),
                    events + self._events,
                )

        # 2. STATE MACHINE ROUTING
        if self.system_state == VFIState.VFI_FLIGHT:
            # 100% VFI flying
            return UpdateResult(vfi_inputs, events + self._events)

        elif self.system_state == VFIState.SYNCING:
            return UpdateResult(
                self.process_synchronization(dt, hardware, vfi_inputs),
                events + self._events,
            )

        elif self.system_state == VFIState.STUDENT_FLIGHT:
            # Check for automatic phase advancement before routing inputs.
            self.maybe_advance_phase(dt)
            if self.transition_pending:
                self.transition_pending = False
                next_phase = self.transition_target_phase
                is_final = self.training_complete

                # Take back control & transition
                self.reset_to_vfi_flight()
                if is_final:
                    self._emit_event(
                        PhaseAdvancedEvent(self.phase, self.phase, is_final=True)
                    )
                else:
                    old_phase = self.phase
                    self.phase = next_phase
                    self.initiate_handoff()
                    self._emit_event(
                        PhaseAdvancedEvent(old_phase, next_phase, is_final=False)
                    )
                # Since we transitioned, return VFI inputs
                return UpdateResult(vfi_inputs, events + self._events)

            return UpdateResult(
                self.process_student_inputs(telemetry, hardware, vfi_inputs),
                events + self._events,
            )

        elif self.system_state == VFIState.OVERRIDE:
            # Direct recovery execution
            return UpdateResult(
                self.process_recovery(dt, vfi_inputs, telemetry),
                events + self._events,
            )

        elif self.system_state == VFIState.RECOVERY_HOLD:
            # Stage 3: slowly move recovery targets horizontally and vertically towards original
            if self.drift_recovery_active:
                self._update_recovery_targets(dt)
            else:
                # Timer only counts down after the target has fully returned
                self.recovery_timer -= dt
                if self.recovery_timer <= 0.0:
                    self.set_hud_caption(
                        "AIRCRAFT STABLE. PREPARE TO SYNC.",
                        duration=4.0,
                        style=CaptionStyle.WARNING,
                    )
                    self.initiate_handoff()
            return UpdateResult(vfi_inputs, events + self._events)

        return UpdateResult(vfi_inputs, events + self._events)

    def get_safety_breach_reason(self, telemetry):
        """Checks structural/aerodynamic hazard boundaries and returns the breach reason.

        Args:
            telemetry: Dict containing current flight states.

        Returns:
            A string describing the first breached limit, or None if safe.
        """
        # Pitch limit (+-15 degrees)
        pitch = telemetry.get("theta", 0.0)
        if abs(pitch) > LIMIT_ATTITUDE_DEG:
            return f"Pitch attitude {pitch:.1f}° exceeded limit of ±{LIMIT_ATTITUDE_DEG}°"

        # Roll limit (+-15 degrees)
        roll = telemetry.get("phi", 0.0)
        if abs(roll) > LIMIT_ATTITUDE_DEG:
            return f"Roll attitude {roll:.1f}° exceeded limit of ±{LIMIT_ATTITUDE_DEG}°"

        # Yaw rate limit (+-30 deg/sec)
        yaw_rate = telemetry.get("R", 0.0)
        if abs(yaw_rate) > LIMIT_YAW_RATE_DEG_S:
            return f"Yaw rate {yaw_rate:.1f}°/s exceeded limit of ±{LIMIT_YAW_RATE_DEG_S}°/s"

        # Vertical speed: sinking > 300 ft/min or climbing > 300 ft/min
        vy_m_s = telemetry.get("vy", 0.0)
        vspeed_ft_min = vy_m_s * M_S_TO_FT_MIN
        if vspeed_ft_min < -LIMIT_VSPEED_FT_MIN:
            return f"Sink rate {vspeed_ft_min:.1f} ft/min exceeded limit of {LIMIT_VSPEED_FT_MIN} ft/min"
        if vspeed_ft_min > LIMIT_VSPEED_FT_MIN:
            return f"Climb rate {vspeed_ft_min:.1f} ft/min exceeded limit of {LIMIT_VSPEED_FT_MIN} ft/min"

        # Ground speed drift > 12 knots
        vx = telemetry.get("vx", 0.0)
        vz = telemetry.get("vz", 0.0)
        gs_m_s = math.sqrt(vx**2 + vz**2)
        gs_knots = gs_m_s * M_S_TO_KNOTS
        if gs_knots > LIMIT_GS_KNOTS:
            return f"Ground speed {gs_knots:.1f} knots exceeded limit of {LIMIT_GS_KNOTS} knots"

        # Terrain height (AGL) < 2.0 meters or > 10.0 meters
        y_agl = telemetry.get("y_agl", 10.0)
        if y_agl < LIMIT_AGL_MIN_M:
            return f"Altitude {y_agl:.1f}m AGL below minimum limit of {LIMIT_AGL_MIN_M}m"
        if y_agl > LIMIT_AGL_MAX_M:
            return f"Altitude {y_agl:.1f}m AGL above maximum limit of {LIMIT_AGL_MAX_M}m"

        # Heading Safety Zone Detection
        psi = telemetry.get("psi", None)
        target_psi = telemetry.get("target_psi", None)
        if psi is not None and target_psi is not None:
            err = (target_psi - psi + 180.0) % 360.0 - 180.0
            abs_err = abs(err)
            if abs_err > LIMIT_HDG_ORANGE_DEG:
                return f"Heading error {abs_err:.1f}° exceeded safety limit of {LIMIT_HDG_ORANGE_DEG}°"

        # Hovering safety distance from target (default: 45 meters)
        x = telemetry.get("x", None)
        z = telemetry.get("z", None)
        target_x = telemetry.get("target_x", None)
        target_z = telemetry.get("target_z", None)
        if (
            x is not None
            and z is not None
            and target_x is not None
            and target_z is not None
        ):
            dist = math.sqrt((x - target_x) ** 2 + (z - target_z) ** 2)
            if dist > self.hover_safety_radius:
                return f"Horizontal drift distance {dist:.1f}m exceeded safety limit of {self.hover_safety_radius}m"

        return None

    def check_safety_limits(self, telemetry):
        """Checks structural/aerodynamic hazard boundaries.

        Args:
            telemetry: Dict containing current flight states.

        Returns:
            True if any safety limit is violated, False otherwise.
        """
        # Maintain the side-effect of setting self.heading_zone
        psi = telemetry.get("psi", None)
        target_psi = telemetry.get("target_psi", None)
        if psi is not None and target_psi is not None:
            err = (target_psi - psi + 180.0) % 360.0 - 180.0
            abs_err = abs(err)
            if abs_err <= LIMIT_HDG_GREEN_DEG:
                self.heading_zone = HeadingZone.GREEN
            elif abs_err <= LIMIT_HDG_ORANGE_DEG:
                self.heading_zone = HeadingZone.ORANGE
            else:
                self.heading_zone = HeadingZone.RED
        else:
            self.heading_zone = HeadingZone.GREEN

        return self.get_safety_breach_reason(telemetry) is not None

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
            phase_config[ControlAxis.ROLL] == Authority.STUDENT
            and phase_config[ControlAxis.PITCH] == Authority.STUDENT
        )

        # Check cyclic as a circular 2D distance
        if cyclic_student:
            cyclic_dist = math.sqrt(
                (hardware[ControlAxis.ROLL] - vfi_inputs[ControlAxis.ROLL]) ** 2
                + (hardware[ControlAxis.PITCH] - vfi_inputs[ControlAxis.PITCH]) ** 2
            )
            if cyclic_dist <= self.match_tolerance:
                if not self.sync_locked[ControlAxis.ROLL]:
                    log.info("Cyclic axes (ROLL/PITCH) synchronized (hardware matched VFI targets).")
                self.sync_locked[ControlAxis.ROLL] = True
                self.sync_locked[ControlAxis.PITCH] = True
            else:
                self.sync_locked[ControlAxis.ROLL] = False
                self.sync_locked[ControlAxis.PITCH] = False
                all_matched = False
        else:
            self.sync_locked[ControlAxis.ROLL] = True
            self.sync_locked[ControlAxis.PITCH] = True

        # Check other axes individually (yaw, collective)
        for axis in [ControlAxis.YAW, ControlAxis.COLLECTIVE]:
            if phase_config[axis] == Authority.STUDENT:
                delta = abs(hardware[axis] - vfi_inputs[axis])
                if delta <= self.match_tolerance:
                    if not self.sync_locked[axis]:
                        log.info(f"Axis {axis.name} synchronized (hardware matched VFI target).")
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
                student_axes = []
                for axis in ControlAxis:
                    if phase_config[axis] == Authority.STUDENT:
                        self.control_assignment[axis] = Authority.STUDENT
                        student_axes.append(axis.name)

                log.info(f"Control synchronization complete. Handed authority for {student_axes} to STUDENT.")
                self.system_state = VFIState.STUDENT_FLIGHT
                self.set_hud_caption(
                    "YOU HAVE THE CONTROLS",
                    duration=3.0,
                    style=CaptionStyle.SUCCESS,
                )
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

        if self.last_envelope == Envelope.EXCELLENT:
            self.excellent_timer += dt
        else:
            self.excellent_timer = 0.0

        if self.excellent_timer >= PHASE_EXCELLENT_REQUIRED_S:
            self.excellent_timer = 0.0
            self.transition_pending = True
            if self.phase < MAX_PHASE:
                self.transition_target_phase = self.phase + 1
                log.info(
                    f"Student completed Phase {self.phase} by holding Excellent envelope "
                    f"for {PHASE_EXCELLENT_REQUIRED_S}s. Advancing to Phase {self.phase + 1}."
                )
            else:
                # Already on the final phase; signal completion.
                self.transition_target_phase = self.phase
                self.training_complete = True
                log.info(
                    f"Student completed final Phase {self.phase} by holding Excellent envelope "
                    f"for {PHASE_EXCELLENT_REQUIRED_S}s. Curriculum complete!"
                )

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
        for axis in ControlAxis:
            if self.control_assignment[axis] == Authority.STUDENT:
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
        self.system_state = VFIState.OVERRIDE
        # Revoke all student authority immediately
        for axis in self.control_assignment:
            self.control_assignment[axis] = Authority.VFI
            self.sync_locked[axis] = False

        self.set_hud_caption(
            "I HAVE THE CONTROLS",
            duration=4.0,
            style=CaptionStyle.DANGER,
        )

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
        phi = abs(telemetry.get("phi", 0.0))
        theta = abs(telemetry.get("theta", 0.0))
        vy = telemetry.get("vy", 0.0) * M_S_TO_FT_MIN
        vx = telemetry.get("vx", 0.0)
        vz = telemetry.get("vz", 0.0)
        gs_knots = math.sqrt(vx**2 + vz**2) * M_S_TO_KNOTS

        is_stable = (
            phi < LIMIT_RECOVERY_ATTITUDE_DEG
            and theta < LIMIT_RECOVERY_ATTITUDE_DEG
            and vy > LIMIT_RECOVERY_SINK_FT_MIN
            and gs_knots < LIMIT_RECOVERY_GS_KNOTS
        )

        if self.system_state == VFIState.OVERRIDE:
            if is_stable:
                # Transition to Step 4: Cool-down Hold for 3 seconds / Target Translation
                self.system_state = VFIState.RECOVERY_HOLD
                self.recovery_timer = self.recovery_hold_duration

        # Return VFI inputs
        return vfi_inputs

