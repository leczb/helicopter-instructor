"""Telemetry and pilot control input metrics evaluator.

This module provides real-time calculations for student pilot precision,
control smoothness (using the Over-Controlling Index, or OCI), safety envelope
margins, proficiency grading, and verbal/visual training cues.
"""

import collections
import math

from helicopter_instructor.virtual_instructor import PHASE_CONFIGS

# Conversion Constants
M_S_TO_KNOTS = 1.94384
M_S_TO_FT_MIN = 196.8504

# Symbolic audio cue constants to avoid raw filenames
SOUND_RELAX_CYCLIC = "Relax cyclic.wav"
SOUND_STEADY_PEDALS = "Steady pedals.wav"
SOUND_SMOOTH_COLLECTIVE = "Smooth collective.wav"
SOUND_CORRECT_DRIFT = "Correct the drift.wav"
SOUND_WE_ARE_TOO_HIGH = "We are too high.wav"
SOUND_WE_ARE_TOO_LOW = "We are too low.wav"
SOUND_NICE_RECOVERY = "Nice recovery.wav"
SOUND_GREAT_PEDALS = "Great pedals.wav"
SOUND_SMOOTH_CYCLIC = "Smooth cyclic.wav"
SOUND_PERFECT = "Perfect.wav"

from helicopter_instructor.envelope_limits import (
    LIMIT_HDG_GREEN_DEG,
    LIMIT_HDG_ORANGE_DEG,
    LIMIT_ALT_GREEN_M,
    LIMIT_ALT_ORANGE_M,
    LIMIT_DRIFT_GREEN_M,
    LIMIT_DRIFT_RED_M,
    LIMIT_DRIFT_SPEED_GREEN_M_S,
    LIMIT_DRIFT_SPEED_ORANGE_M_S,
    LIMIT_VERT_SPEED_GREEN_M_S,
    LIMIT_VERT_SPEED_ORANGE_M_S,
)

# Safety and Performance warning margin constants
# Warn as soon as the student exits the green zone (target 6.0m ± LIMIT_ALT_GREEN_M)
MARGIN_ALT_LOW = 6.0 - LIMIT_ALT_GREEN_M   # Lower green edge: 4.0m AGL
MARGIN_ALT_HIGH = 6.0 + LIMIT_ALT_GREEN_M  # Upper green edge: 8.0m AGL
# Warn as soon as the student gets near the edge of the green zone
MARGIN_DRIFT_LIMIT = LIMIT_DRIFT_GREEN_M - 8.0
MARGIN_OCI_CYCLIC = 1.0       # Cyclic OCI warning threshold
MARGIN_OCI_PEDAL = 0.8        # Pedals OCI warning threshold
MARGIN_OCI_COLLECTIVE = 0.8   # Collective OCI warning threshold

# Green Zone (Excellent) performance thresholds for precision scoring
GREEN_ZONE_HDG_DEG = LIMIT_HDG_GREEN_DEG
GREEN_ZONE_ALT_M = LIMIT_ALT_GREEN_M
GREEN_ZONE_DRIFT_M = LIMIT_DRIFT_GREEN_M
GREEN_ZONE_DRIFT_SPEED_M_S = LIMIT_DRIFT_SPEED_GREEN_M_S
GREEN_ZONE_VERT_SPEED_M_S = LIMIT_VERT_SPEED_GREEN_M_S

# Limit thresholds for 0% precision score calculation
LIMIT_HDG_DEG = LIMIT_HDG_ORANGE_DEG
LIMIT_ALT_M = LIMIT_ALT_ORANGE_M
LIMIT_DRIFT_M = LIMIT_DRIFT_RED_M
LIMIT_DRIFT_SPEED_M_S = LIMIT_DRIFT_SPEED_ORANGE_M_S
LIMIT_VERT_SPEED_M_S = LIMIT_VERT_SPEED_ORANGE_M_S



class PerformanceMetricsEvaluator(object):
    """Evaluates pilot performance based on telemetry and control smoothness.

    Maintains a 60-second sliding window of flight telemetry at 50Hz and
    calculates precision, smoothness (via the Over-Controlling Index, or OCI),
    safety, and coaching triggers.
    """

    def __init__(self):
        """Initializes the metrics evaluator instance."""
        # raw 50Hz telemetry frame circular buffer (last 60s -> 3,000 samples)
        self.history = collections.deque(maxlen=3000)

        # Smoothness Tracking (Exponential Moving Average of input velocities,
        # representing the Over-Controlling Index (OCI))
        self.last_inputs = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "collective": 0.5,
        }
        self.oci = {
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "collective": 0.0,
        }
        self.ema_alpha = 0.05  # ~0.4s response window

        # Hysteresis and warning timers (duration tracking before triggering)
        self.jerk_timers = {
            "cyclic": 0.0,
            "yaw": 0.0,
            "collective": 0.0,
        }
        self.drift_warning_timer = 0.0
        self.high_alt_warning_timer = 0.0
        self.low_alt_warning_timer = 0.0

        # Audio cooldown timers to prevent repeating warning cues too quickly
        self.audio_cooldowns = {
            SOUND_RELAX_CYCLIC: 0.0,
            SOUND_STEADY_PEDALS: 0.0,
            SOUND_SMOOTH_COLLECTIVE: 0.0,
            SOUND_CORRECT_DRIFT: 0.0,
            SOUND_WE_ARE_TOO_HIGH: 0.0,
            SOUND_WE_ARE_TOO_LOW: 0.0,
            SOUND_NICE_RECOVERY: 0.0,
            SOUND_GREAT_PEDALS: 0.0,
            SOUND_SMOOTH_CYCLIC: 0.0,
            SOUND_PERFECT: 0.0,
        }

        # Active verbal cue queue
        self.audio_queue = []

        # Training Session Summary Statistics
        self.longest_flight_time = 0.0
        self.current_flight_time = 0.0
        self.total_takeovers = 0
        self.total_drift_sum = 0.0
        self.drift_count = 0
        self.was_student_flying_last_frame = False

        # Live Display Metrics (updated every frame)
        self.precision_score = 100.0
        self.smoothness_score = 100.0
        self.overall_score = 100.0
        self.envelope = "Excellent"
        self.safety_proximity = 0.0
        self.drift_speed = 0.0
        self.drift_speed_score = 100.0
        self.vert_speed = 0.0
        self.vert_speed_score = 100.0
        self.coaching_tips = "Keep controls steady to begin hover evaluation."

        # Praise specific state tracking
        self.pedal_praise_timer = 0.0
        self.cyclic_praise_timer = 0.0
        self.perfect_hover_timer = 0.0
        self.was_in_warning_zone = False

    def pop_audio_queue(self):
        """Pops and returns the next pending audio WAV file in the queue.

        Returns:
            String filename if queue has items, otherwise None.
        """
        if self.audio_queue:
            return self.audio_queue.pop(0)
        return None

    def update(self, dt, telemetry, hardware_inputs, is_student_flying, phase):
        """Updates metrics, sliding buffer, scores, and triggers feedback.

        Args:
            dt: Time step in seconds.
            telemetry: Dict of flight states.
            hardware_inputs: Dict of student inputs.
            is_student_flying: True if student has control authority.
            phase: Current curriculum lesson phase (1 to 6).
        """
        # 1. Update cooldown timers
        for sound in self.audio_cooldowns:
            if self.audio_cooldowns[sound] > 0.0:
                self.audio_cooldowns[sound] = max(0.0, self.audio_cooldowns[sound] - dt)

        # 2. Track Takeovers and flight duration
        self._track_session_state(dt, is_student_flying)

        # 3. Calculate OCI (Over-controlling index)
        self._calculate_smoothness_index(dt, hardware_inputs)

        # If student isn't active, skip sliding buffer updates and warnings
        if not is_student_flying:
            self.history.clear()
            self.precision_score = 100.0
            self.smoothness_score = 100.0
            self.overall_score = 100.0
            self.safety_proximity = 0.0
            self.envelope = "Excellent"
            self.coaching_tips = "VFI has control. Prepare to sync controls."
            self.pedal_praise_timer = 0.0
            self.cyclic_praise_timer = 0.0
            self.perfect_hover_timer = 0.0
            self.jerk_timers["cyclic"] = 0.0
            self.jerk_timers["yaw"] = 0.0
            self.jerk_timers["collective"] = 0.0
            self.drift_warning_timer = 0.0
            self.low_alt_warning_timer = 0.0
            self.high_alt_warning_timer = 0.0
            self.was_in_warning_zone = False
            return

        # 4. Append current telemetry and hardware state to 60-second window
        state_snapshot = {
            "telemetry": dict(telemetry),
            "inputs": dict(hardware_inputs),
            "oci": dict(self.oci),
        }
        self.history.append(state_snapshot)

        # 5. Evaluate current frame scores
        self._evaluate_frame_performance(telemetry, phase)

        # 6. sliding window statistics & proficiency envelope
        self._evaluate_proficiency_envelope()

        # 7. Check for immediate warning triggers and praise cues
        self._check_feedback_triggers(dt, telemetry, phase)

        # 8. Generate dynamic text coaching advice
        self._generate_coaching_tips(phase)

    def _track_session_state(self, dt, is_student_flying):
        """Monitors overall flight session durations and takeover transitions.

        Args:
            dt: Time step in seconds.
            is_student_flying: True if student currently has flight authority.
        """
        if is_student_flying:
            self.current_flight_time += dt
            if self.current_flight_time > self.longest_flight_time:
                self.longest_flight_time = self.current_flight_time
        else:
            # Detect takeover transition
            if self.was_student_flying_last_frame:
                self.total_takeovers += 1
            self.current_flight_time = 0.0

        self.was_student_flying_last_frame = is_student_flying

    def _calculate_smoothness_index(self, dt, inputs):
        """Calculates input velocities and updates EMA-based OCI values.

        Args:
            dt: Time step in seconds.
            inputs: Raw student hardware deflections.
        """
        if dt <= 0.0:
            return

        for axis in ["roll", "pitch", "yaw", "collective"]:
            curr_val = inputs.get(axis, 0.0)
            prev_val = self.last_inputs.get(axis, curr_val)
            self.last_inputs[axis] = curr_val

            # Input velocity per second
            velocity = abs(curr_val - prev_val) / dt

            # Apply Exponential Moving Average (EMA) filter
            self.oci[axis] = (self.ema_alpha * velocity) + (
                (1.0 - self.ema_alpha) * self.oci[axis]
            )

    def _evaluate_frame_performance(self, telemetry, phase):
        """Computes instantaneous precision, smoothness and safety scores.

        Args:
            telemetry: Dict of flight states.
            phase: Current curriculum lesson phase.
        """
        phase_config = PHASE_CONFIGS.get(phase, {})

        # Compute drift speed in m/s and corresponding score component
        vx = telemetry.get("vx", 0.0)
        vz = telemetry.get("vz", 0.0)
        self.drift_speed = math.sqrt(vx**2 + vz**2)
        if self.drift_speed <= GREEN_ZONE_DRIFT_SPEED_M_S:
            self.drift_speed_score = 100.0
        else:
            self.drift_speed_score = max(
                0.0,
                100.0 * (1.0 - (
                    (self.drift_speed - GREEN_ZONE_DRIFT_SPEED_M_S) /
                    (LIMIT_DRIFT_SPEED_M_S - GREEN_ZONE_DRIFT_SPEED_M_S)
                ))
            )

        # Compute vertical speed in m/s and corresponding score component
        self.vert_speed = abs(telemetry.get("vy", 0.0))
        if self.vert_speed <= GREEN_ZONE_VERT_SPEED_M_S:
            self.vert_speed_score = 100.0
        else:
            self.vert_speed_score = max(
                0.0,
                100.0 * (1.0 - (
                    (self.vert_speed - GREEN_ZONE_VERT_SPEED_M_S) /
                    (LIMIT_VERT_SPEED_M_S - GREEN_ZONE_VERT_SPEED_M_S)
                ))
            )

        # --- A. Precision Scoring ---
        prec_components = []

        # Heading component (Yaw)
        if phase_config.get("yaw") == "STUDENT":
            psi = telemetry.get("psi")
            t_psi = telemetry.get("target_psi")
            if psi is not None and t_psi is not None:
                err = abs(((t_psi - psi + 180.0) % 360.0) - 180.0)
                # Within green zone = 100% score (no penalty)
                if err <= GREEN_ZONE_HDG_DEG:
                    comp = 100.0
                else:
                    # Ramps up penalty outside green zone to LIMIT_HDG_DEG
                    comp = max(
                        0.0,
                        100.0 * (1.0 - (
                            (err - GREEN_ZONE_HDG_DEG) /
                            (LIMIT_HDG_DEG - GREEN_ZONE_HDG_DEG)
                        ))
                    )
                prec_components.append(comp)

        # Altitude component (Collective)
        if phase_config.get("collective") == "STUDENT":
            y_agl = telemetry.get("y_agl")
            if y_agl is not None:
                err = abs(y_agl - 6.0)
                # Within green zone = 100% score (no penalty)
                if err <= GREEN_ZONE_ALT_M:
                    comp = 100.0
                else:
                    # Ramps up penalty outside green zone to LIMIT_ALT_M
                    comp = max(
                        0.0,
                        100.0 * (1.0 - (
                            (err - GREEN_ZONE_ALT_M) /
                            (LIMIT_ALT_M - GREEN_ZONE_ALT_M)
                        ))
                    )
                prec_components.append(comp)

        # Drift component (Cyclic roll/pitch)
        cyclic_active = (
            phase_config.get("roll") == "STUDENT"
            and phase_config.get("pitch") == "STUDENT"
        )
        if cyclic_active:
            x = telemetry.get("x")
            z = telemetry.get("z")
            tx = telemetry.get("target_x")
            tz = telemetry.get("target_z")
            if x is not None and z is not None and tx is not None and tz is not None:
                drift = math.sqrt((x - tx)**2 + (z - tz)**2)
                # Track drift stats
                self.total_drift_sum += drift
                self.drift_count += 1

                # Within green zone = 100% score (no penalty)
                if drift <= GREEN_ZONE_DRIFT_M:
                    comp = 100.0
                else:
                    # Ramps up penalty outside green zone to LIMIT_DRIFT_M
                    comp = max(
                        0.0,
                        100.0 * (1.0 - (
                            (drift - GREEN_ZONE_DRIFT_M) /
                            (LIMIT_DRIFT_M - GREEN_ZONE_DRIFT_M)
                        ))
                    )
                prec_components.append(comp)

                # Drift speed component (ground velocity)
                prec_components.append(self.drift_speed_score)

        # Vertical speed component (climb/descent rate) — gated on collective
        if phase_config.get("collective") == "STUDENT":
            prec_components.append(self.vert_speed_score)

        if prec_components:
            self.precision_score = sum(prec_components) / len(prec_components)
        else:
            self.precision_score = 100.0

        # --- B. Smoothness Scoring ---
        smooth_components = []
        for axis in ["roll", "pitch", "yaw", "collective"]:
            if phase_config.get(axis) == "STUDENT":
                # Jerk threshold limit = 1.0 (OCI)
                score = max(0.0, 100.0 * (1.0 - self.oci[axis]))
                smooth_components.append(score)

        if smooth_components:
            self.smoothness_score = sum(smooth_components) / len(smooth_components)
        else:
            self.smoothness_score = 100.0

        # --- C. Safety Envelope Proximity ---
        theta = abs(telemetry.get("theta", 0.0))
        phi = abs(telemetry.get("phi", 0.0))
        yaw_rate = abs(telemetry.get("R", 0.0))
        vy = abs(telemetry.get("vy", 0.0)) * M_S_TO_FT_MIN

        x = telemetry.get("x")
        z = telemetry.get("z")
        tx = telemetry.get("target_x")
        tz = telemetry.get("target_z")
        drift = 0.0
        if x is not None and z is not None and tx is not None and tz is not None:
            drift = math.sqrt((x - tx)**2 + (z - tz)**2)

        prox_pitch = theta / 15.0
        prox_roll = phi / 15.0
        prox_yaw_rate = yaw_rate / 30.0
        prox_vy = vy / 300.0
        prox_drift = drift / 45.0

        self.safety_proximity = (
            max(
                prox_pitch,
                prox_roll,
                prox_yaw_rate,
                prox_vy,
                prox_drift,
            )
            * 100.0
        )

        # --- D. Overall Weighted Score ---
        self.overall_score = (self.precision_score * 0.6) + (
            self.smoothness_score * 0.4
        )

    def _evaluate_proficiency_envelope(self):
        """Grades performance (Excellent/Good/Unstable) over sliding window."""
        if not self.history:
            self.envelope = "Excellent"
            return

        total_samples = len(self.history)
        unstable_count = 0
        excellent_count = 0

        for frame in self.history:
            telemetry = frame["telemetry"]
            oci = frame["oci"]

            # Precision metrics
            x = telemetry.get("x")
            z = telemetry.get("z")
            tx = telemetry.get("target_x")
            tz = telemetry.get("target_z")
            drift = 0.0
            if x is not None and z is not None and tx is not None and tz is not None:
                drift = math.sqrt((x - tx)**2 + (z - tz)**2)

            y_agl = telemetry.get("y_agl", 6.0)
            alt_err = abs(y_agl - 6.0)

            psi = telemetry.get("psi")
            t_psi = telemetry.get("target_psi")
            hdg_err = 0.0
            if psi is not None and t_psi is not None:
                hdg_err = abs(((t_psi - psi + 180.0) % 360.0) - 180.0)

            # Drift Speed
            vx = telemetry.get("vx", 0.0)
            vz = telemetry.get("vz", 0.0)
            frame_drift_speed = math.sqrt(vx**2 + vz**2)

            # Vertical Speed
            frame_vert_speed = abs(telemetry.get("vy", 0.0))

            # Smoothness
            max_oci = max(oci.values())

            # Evaluate envelope category
            if (
                drift > LIMIT_DRIFT_M
                or alt_err > LIMIT_ALT_M
                or hdg_err > LIMIT_HDG_DEG
                or max_oci > 1.5
                or frame_drift_speed > LIMIT_DRIFT_SPEED_M_S
                or frame_vert_speed > LIMIT_VERT_SPEED_M_S
            ):
                unstable_count += 1
            elif (
                drift < GREEN_ZONE_DRIFT_M
                and alt_err < GREEN_ZONE_ALT_M
                and hdg_err < GREEN_ZONE_HDG_DEG
                and frame_drift_speed < GREEN_ZONE_DRIFT_SPEED_M_S
                and frame_vert_speed < GREEN_ZONE_VERT_SPEED_M_S
                and oci.get("roll", 0.0) < 0.3
                and oci.get("pitch", 0.0) < 0.3
                and oci.get("yaw", 0.0) < 0.2
            ):
                excellent_count += 1

        # Classify based on dominant window characteristics
        unstable_ratio = float(unstable_count) / total_samples
        excellent_ratio = float(excellent_count) / total_samples

        if unstable_ratio > 0.15:
            self.envelope = "Unstable"
        elif excellent_ratio > 0.60:
            self.envelope = "Excellent"
        else:
            self.envelope = "Good"

    def _check_feedback_triggers(self, dt, telemetry, phase):
        """Monitors trigger durations and cues instructional warning/praise.

        Args:
            dt: Time step in seconds.
            telemetry: Dict of flight states.
            phase: Current curriculum lesson phase.
        """
        phase_config = PHASE_CONFIGS.get(phase, {})

        # --- A. IMMEDIATE LEARNING FEEDBACK (WARNINGS) ---

        # 1. Jerky Cyclic (Roll or Pitch OCI > limit)
        cyclic_student = (
            phase_config.get("roll") == "STUDENT"
            and phase_config.get("pitch") == "STUDENT"
        )
        if cyclic_student:
            max_cyclic_oci = max(self.oci["roll"], self.oci["pitch"])
            if max_cyclic_oci > MARGIN_OCI_CYCLIC:
                self.jerk_timers["cyclic"] += dt
                if (
                    self.jerk_timers["cyclic"] >= 1.5
                    and self.audio_cooldowns[SOUND_RELAX_CYCLIC] == 0.0
                ):
                    self.audio_queue.append(SOUND_RELAX_CYCLIC)
                    self.audio_cooldowns[SOUND_RELAX_CYCLIC] = 10.0
                    self.jerk_timers["cyclic"] = 0.0
            else:
                self.jerk_timers["cyclic"] = 0.0
        else:
            self.jerk_timers["cyclic"] = 0.0

        # 2. Jerky Pedals (Yaw OCI > limit)
        if phase_config.get("yaw") == "STUDENT":
            if self.oci["yaw"] > MARGIN_OCI_PEDAL:
                self.jerk_timers["yaw"] += dt
                if (
                    self.jerk_timers["yaw"] >= 1.5
                    and self.audio_cooldowns[SOUND_STEADY_PEDALS] == 0.0
                ):
                    self.audio_queue.append(SOUND_STEADY_PEDALS)
                    self.audio_cooldowns[SOUND_STEADY_PEDALS] = 10.0
                    self.jerk_timers["yaw"] = 0.0
            else:
                self.jerk_timers["yaw"] = 0.0
        else:
            self.jerk_timers["yaw"] = 0.0

        # 3. Jerky Collective (Collective OCI > limit)
        if phase_config.get("collective") == "STUDENT":
            if self.oci["collective"] > MARGIN_OCI_COLLECTIVE:
                self.jerk_timers["collective"] += dt
                if (
                    self.jerk_timers["collective"] >= 1.5
                    and self.audio_cooldowns[SOUND_SMOOTH_COLLECTIVE] == 0.0
                ):
                    self.audio_queue.append(SOUND_SMOOTH_COLLECTIVE)
                    self.audio_cooldowns[SOUND_SMOOTH_COLLECTIVE] = 10.0
                    self.jerk_timers["collective"] = 0.0
            else:
                self.jerk_timers["collective"] = 0.0
        else:
            self.jerk_timers["collective"] = 0.0

        # 4. Drift Warning (Drift > limit and increasing)
        if cyclic_active := cyclic_student:
            x = telemetry.get("x")
            z = telemetry.get("z")
            tx = telemetry.get("target_x")
            tz = telemetry.get("target_z")
            if x is not None and z is not None and tx is not None and tz is not None:
                drift = math.sqrt((x - tx)**2 + (z - tz)**2)

                if drift > MARGIN_DRIFT_LIMIT:
                    self.drift_warning_timer += dt
                    if (
                        self.drift_warning_timer >= 2.0
                        and self.audio_cooldowns[SOUND_CORRECT_DRIFT] == 0.0
                    ):
                        self.audio_queue.append(SOUND_CORRECT_DRIFT)
                        self.audio_cooldowns[SOUND_CORRECT_DRIFT] = 15.0
                        self.drift_warning_timer = 0.0
                        self.was_in_warning_zone = True
                else:
                    self.drift_warning_timer = 0.0
        else:
            self.drift_warning_timer = 0.0

        # 5. Altitude warnings (Too High vs Too Low)
        if phase_config.get("collective") == "STUDENT":
            y_agl = telemetry.get("y_agl")
            if y_agl is not None:
                # Too Low (AGL < MARGIN_ALT_LOW)
                if y_agl < MARGIN_ALT_LOW:
                    self.low_alt_warning_timer += dt
                    if (
                        self.low_alt_warning_timer >= 1.5
                        and self.audio_cooldowns[SOUND_WE_ARE_TOO_LOW] == 0.0
                    ):
                        self.audio_queue.append(SOUND_WE_ARE_TOO_LOW)
                        self.audio_cooldowns[SOUND_WE_ARE_TOO_LOW] = 10.0
                        self.low_alt_warning_timer = 0.0
                        self.was_in_warning_zone = True
                else:
                    self.low_alt_warning_timer = 0.0

                # Too High (AGL > MARGIN_ALT_HIGH)
                if y_agl > MARGIN_ALT_HIGH:
                    self.high_alt_warning_timer += dt
                    if (
                        self.high_alt_warning_timer >= 1.5
                        and self.audio_cooldowns[SOUND_WE_ARE_TOO_HIGH] == 0.0
                    ):
                        self.audio_queue.append(SOUND_WE_ARE_TOO_HIGH)
                        self.audio_cooldowns[SOUND_WE_ARE_TOO_HIGH] = 10.0
                        self.high_alt_warning_timer = 0.0
                        self.was_in_warning_zone = True
                else:
                    self.high_alt_warning_timer = 0.0
        else:
            self.low_alt_warning_timer = 0.0
            self.high_alt_warning_timer = 0.0

        # --- B. POSITIVE REINFORCEMENT (PRAISE CUES) ---

        # 1. "Pedal Master" (heading steady, low rate, and low drift speed)
        if phase_config.get("yaw") == "STUDENT":
            psi = telemetry.get("psi")
            t_psi = telemetry.get("target_psi")
            yaw_rate = abs(telemetry.get("R", 0.0))
            if psi is not None and t_psi is not None:
                err = abs(((t_psi - psi + 180.0) % 360.0) - 180.0)
                if err < 5.0 and yaw_rate < 3.0 and self.drift_speed <= 1.0:
                    self.pedal_praise_timer += dt
                    if (
                        self.pedal_praise_timer >= 15.0
                        and self.audio_cooldowns[SOUND_GREAT_PEDALS] == 0.0
                    ):
                        self.audio_queue.append(SOUND_GREAT_PEDALS)
                        self.audio_cooldowns[SOUND_GREAT_PEDALS] = 30.0
                        self.pedal_praise_timer = 0.0
                else:
                    self.pedal_praise_timer = 0.0
            else:
                self.pedal_praise_timer = 0.0
        else:
            self.pedal_praise_timer = 0.0

        # 2. "Smooth Hands" (Cyclic OCI steady, low drift speed)
        if cyclic_student:
            max_cyclic_oci = max(self.oci["roll"], self.oci["pitch"])
            if max_cyclic_oci < 0.2 and self.precision_score >= 70.0 and self.drift_speed <= 1.0:
                self.cyclic_praise_timer += dt
                if (
                    self.cyclic_praise_timer >= 30.0
                    and self.audio_cooldowns[SOUND_SMOOTH_CYCLIC] == 0.0
                ):
                    self.audio_queue.append(SOUND_SMOOTH_CYCLIC)
                    self.audio_cooldowns[SOUND_SMOOTH_CYCLIC] = 30.0
                    self.cyclic_praise_timer = 0.0
            else:
                self.cyclic_praise_timer = 0.0
        else:
            self.cyclic_praise_timer = 0.0

        # Check if the student is currently violating any warning thresholds
        violating_warning = False
        if cyclic_student:
            x = telemetry.get("x")
            z = telemetry.get("z")
            tx = telemetry.get("target_x")
            tz = telemetry.get("target_z")
            if (
                x is not None
                and z is not None
                and tx is not None
                and tz is not None
            ):
                drift = math.sqrt((x - tx)**2 + (z - tz)**2)
                if drift > MARGIN_DRIFT_LIMIT:
                    violating_warning = True

        if phase_config.get("collective") == "STUDENT":
            y_agl = telemetry.get("y_agl")
            if y_agl is not None:
                if y_agl < MARGIN_ALT_LOW or y_agl > MARGIN_ALT_HIGH:
                    violating_warning = True

        # 3. "Nice recovery" (Returning to target at stable drift speed)
        if (
            self.was_in_warning_zone
            and not violating_warning
            and self.precision_score >= 85.0
            and self.drift_speed <= 1.0
        ):
            if self.audio_cooldowns[SOUND_NICE_RECOVERY] == 0.0:
                self.audio_queue.append(SOUND_NICE_RECOVERY)
                self.audio_cooldowns[SOUND_NICE_RECOVERY] = 30.0
            self.was_in_warning_zone = False

        # 4. "Perfect" stable hover reinforcement (when student maintains Excellent envelope and low drift speed for 10.0s)
        if self.envelope == "Excellent" and self.drift_speed <= 1.0:
            self.perfect_hover_timer += dt
            if (
                self.perfect_hover_timer >= 10.0
                and self.audio_cooldowns[SOUND_PERFECT] == 0.0
            ):
                self.audio_queue.append(SOUND_PERFECT)
                self.audio_cooldowns[SOUND_PERFECT] = 30.0
                self.perfect_hover_timer = 0.0
        else:
            self.perfect_hover_timer = 0.0

    def _generate_coaching_tips(self, phase):
        """Generates contextual coaching guidance based on active errors.

        Args:
            phase: Current curriculum lesson phase.
        """
        phase_config = PHASE_CONFIGS.get(phase, {})

        # Active axes help
        tips = []

        # 1. Cyclic over-controlling advice
        cyclic_student = (
            phase_config.get("roll") == "STUDENT"
            and phase_config.get("pitch") == "STUDENT"
        )
        if cyclic_student:
            if max(self.oci["roll"], self.oci["pitch"]) > 0.8:
                tips.append("Cyclic inputs too large. Make tiny, 1-millimeter tweaks and wait for the aircraft response.")

        # 2. Pedal over-controlling advice
        if phase_config.get("yaw") == "STUDENT":
            if self.oci["yaw"] > 0.6:
                tips.append("Avoid rapidly pumping pedals. Push gently and hold to damp yaw rotation.")

        # 3. Collective altitude advice
        if phase_config.get("collective") == "STUDENT":
            if self.oci["collective"] > 0.6:
                tips.append("Altitude corrections should be smooth. Collective changes require corresponding pedal compensation.")

        # 4. Success tips
        if not tips:
            if self.precision_score >= 90.0:
                tips.append("Excellent station-keeping. Keep looking ahead and hold this nominal attitude.")
            else:
                tips.append("Steady, tiny adjustments. Anticipate drift rather than chasing it.")

        self.coaching_tips = tips[0] if tips else "Keep wings level."

    def get_average_drift(self):
        """Returns the mean horizontal drift during this session.

        Returns:
            Float value representing average drift in meters.
        """
        if self.drift_count > 0:
            return self.total_drift_sum / self.drift_count
        return 0.0
