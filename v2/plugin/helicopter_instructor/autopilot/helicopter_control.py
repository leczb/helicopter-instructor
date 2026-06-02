import math


def wrap_180(angle_deg):
    """Wraps an angle in degrees to the range [-180, 180]."""
    return (angle_deg + 180.0) % 360.0 - 180.0


class PID(object):
    """A standard Proportional-Integral-Derivative controller.

    Supports derivative-on-feedback and output clamping.
    """

    def __init__(self, kp, ki, kd, output_min, output_max):
        """Initializes the PID controller with parameters and limits.

        Args:
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            output_min: Minimum allowable controller output limit.
            output_max: Maximum allowable controller output limit.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max

        self.integral = 0.0
        self.last_error = 0.0

    def update(self, error, dt, rate=None):
        """Updates the PID controller.

        Args:
            error: The current error value.
            dt: Time step in seconds.
            rate: If provided, this value (e.g. angular velocity) will be used
              for the derivative term to avoid derivative spikes (derivative
              on feedback).

        Returns:
            The calculated controller output deflection command.
        """
        if dt <= 0.0:
            return 0.0

        # Proportional term
        p_term = self.kp * error

        # Integral term with clamping anti-windup
        # We only accumulate integral if output isn't saturated or if the error
        # is moving back
        if self.ki > 0.0:
            self.integral += error * dt
            i_term = self.ki * self.integral
        else:
            self.integral = 0.0
            i_term = 0.0

        # Derivative term
        if rate is not None:
            # Derivative on feedback: rate is usually the derivative of the
            # process variable. Since Error = Setpoint - ProcessVariable, if
            # Setpoint is constant, d(Error)/dt = -d(ProcessVariable)/dt = -rate
            d_term = -self.kd * rate
        else:
            # Standard derivative of error
            d_term = self.kd * (error - self.last_error) / dt

        self.last_error = error

        output = p_term + i_term + d_term

        # Clamp output and handle anti-windup (prevent integral from growing
        # outside limits)
        if output > self.output_max:
            # If saturated positive, undo the last integral step if error is
            # positive
            if error > 0 and self.ki > 0.0:
                self.integral -= error * dt
                i_term = self.ki * self.integral
                output = p_term + i_term + d_term
            output = self.output_max
        elif output < self.output_min:
            # If saturated negative, undo the last integral step if error is
            # negative
            if error < 0 and self.ki > 0.0:
                self.integral -= error * dt
                i_term = self.ki * self.integral
                output = p_term + i_term + d_term
            output = self.output_min

        return output

    def reset(self):
        """Resets the controller integral state."""
        self.integral = 0.0
        self.last_error = 0.0


class PIDGains(object):
    """Holds a single set of Kp, Ki, Kd coefficients."""

    def __init__(self, kp=0.0, ki=0.0, kd=0.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def to_list(self):
        return [self.kp, self.ki, self.kd]

    @classmethod
    def from_list(cls, lst):
        if lst and len(lst) >= 3:
            return cls(lst[0], lst[1], lst[2])
        elif lst and len(lst) == 2:
            return cls(lst[0], lst[1], 0.0)
        return cls()


# --- Default Autopilot Gain Coefficients and Limits ---
# Hover Lateral (Roll) Axis
DEFAULT_KP_POS_LAT = 0.4
DEFAULT_KI_POS_LAT = 0.01
DEFAULT_KD_POS_LAT = 0.0
DEFAULT_MIN_POS_LAT = -5.0
DEFAULT_MAX_POS_LAT = 5.0

DEFAULT_KP_VEL_LAT = 1.5
DEFAULT_KI_VEL_LAT = 0.05
DEFAULT_KD_VEL_LAT = 0.0
DEFAULT_MIN_VEL_LAT = -12.0
DEFAULT_MAX_VEL_LAT = 12.0

DEFAULT_KP_ATT_ROLL = 0.04
DEFAULT_KI_ATT_ROLL = 0.005
DEFAULT_KD_ATT_ROLL = 0.015
DEFAULT_MIN_ATT_ROLL = -1.0
DEFAULT_MAX_ATT_ROLL = 1.0

# Hover Longitudinal (Pitch) Axis
DEFAULT_KP_POS_LON = 0.4
DEFAULT_KI_POS_LON = 0.01
DEFAULT_KD_POS_LON = 0.0
DEFAULT_MIN_POS_LON = -5.0
DEFAULT_MAX_POS_LON = 5.0

DEFAULT_KP_VEL_LON = 1.5
DEFAULT_KI_VEL_LON = 0.05
DEFAULT_KD_VEL_LON = 0.0
DEFAULT_MIN_VEL_LON = -12.0
DEFAULT_MAX_VEL_LON = 12.0

DEFAULT_KP_ATT_PITCH = 0.04
DEFAULT_KI_ATT_PITCH = 0.005
DEFAULT_KD_ATT_PITCH = 0.015
DEFAULT_MIN_ATT_PITCH = -1.0
DEFAULT_MAX_ATT_PITCH = 1.0

# Hover Heading (Yaw) Axis
DEFAULT_KP_YAW = 0.03
DEFAULT_KI_YAW = 0.002
DEFAULT_KD_YAW = 0.01
DEFAULT_MIN_YAW = -1.0
DEFAULT_MAX_YAW = 1.0

# Hover/Cruise Altitude (Collective) Axis
DEFAULT_KP_ALT = 0.5
DEFAULT_KI_ALT = 0.01
DEFAULT_KD_ALT = 0.0
DEFAULT_MIN_ALT = -2.5
DEFAULT_MAX_ALT = 2.5

DEFAULT_KP_VSPEED = 0.12
DEFAULT_KI_VSPEED = 0.04
DEFAULT_KD_VSPEED = 0.002
DEFAULT_MIN_VSPEED = -0.4
DEFAULT_MAX_VSPEED = 0.4

# Cruise Mode Specific Controllers
DEFAULT_KP_CRUISE_HDG = 1.5
DEFAULT_KI_CRUISE_HDG = 0.05
DEFAULT_KD_CRUISE_HDG = 0.0
DEFAULT_MIN_CRUISE_HDG = -25.0
DEFAULT_MAX_CRUISE_HDG = 25.0

DEFAULT_KP_CRUISE_VSPEED_PITCH = 3.0
DEFAULT_KI_CRUISE_VSPEED_PITCH = 0.1
DEFAULT_KD_CRUISE_VSPEED_PITCH = 0.0
DEFAULT_MIN_CRUISE_VSPEED_PITCH = -15.0
DEFAULT_MAX_CRUISE_VSPEED_PITCH = 15.0

DEFAULT_KP_CRUISE_YAW_TC = 0.5
DEFAULT_KI_CRUISE_YAW_TC = 0.1
DEFAULT_KD_CRUISE_YAW_TC = 0.02
DEFAULT_MIN_CRUISE_YAW_TC = -1.0
DEFAULT_MAX_CRUISE_YAW_TC = 1.0

# Feedforward Hover Power
DEFAULT_HOVER_FEEDFORWARD = 0.5


class AutopilotGains(object):
    """A structured container for all helicopter autopilot gains."""

    def __init__(self):
        self.pos_lat = PIDGains(
            DEFAULT_KP_POS_LAT, DEFAULT_KI_POS_LAT, DEFAULT_KD_POS_LAT
        )
        self.vel_lat = PIDGains(
            DEFAULT_KP_VEL_LAT, DEFAULT_KI_VEL_LAT, DEFAULT_KD_VEL_LAT
        )
        self.att_roll = PIDGains(
            DEFAULT_KP_ATT_ROLL, DEFAULT_KI_ATT_ROLL, DEFAULT_KD_ATT_ROLL
        )
        self.pos_lon = PIDGains(
            DEFAULT_KP_POS_LON, DEFAULT_KI_POS_LON, DEFAULT_KD_POS_LON
        )
        self.vel_lon = PIDGains(
            DEFAULT_KP_VEL_LON, DEFAULT_KI_VEL_LON, DEFAULT_KD_VEL_LON
        )
        self.att_pitch = PIDGains(
            DEFAULT_KP_ATT_PITCH, DEFAULT_KI_ATT_PITCH, DEFAULT_KD_ATT_PITCH
        )
        self.yaw = PIDGains(DEFAULT_KP_YAW, DEFAULT_KI_YAW, DEFAULT_KD_YAW)
        self.alt = PIDGains(DEFAULT_KP_ALT, DEFAULT_KI_ALT, DEFAULT_KD_ALT)
        self.vspeed = PIDGains(DEFAULT_KP_VSPEED, DEFAULT_KI_VSPEED, DEFAULT_KD_VSPEED)
        self.hover_feedforward = DEFAULT_HOVER_FEEDFORWARD

    def to_dict(self):
        """Converts gains to a standard dictionary representation for JSON serialization."""
        return {
            "pos_lat": self.pos_lat.to_list(),
            "vel_lat": self.vel_lat.to_list(),
            "att_roll": self.att_roll.to_list(),
            "pos_lon": self.pos_lon.to_list(),
            "vel_lon": self.vel_lon.to_list(),
            "att_pitch": self.att_pitch.to_list(),
            "yaw": self.yaw.to_list(),
            "alt": self.alt.to_list(),
            "vspeed": self.vspeed.to_list(),
            "hover_feedforward": self.hover_feedforward,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an AutopilotGains instance from a dictionary."""
        gains = cls()
        if not data:
            return gains

        def get_pid_gains(key):
            return PIDGains.from_list(data.get(key))

        gains.pos_lat = get_pid_gains("pos_lat")
        gains.vel_lat = get_pid_gains("vel_lat")
        gains.att_roll = get_pid_gains("att_roll")
        gains.pos_lon = get_pid_gains("pos_lon")
        gains.vel_lon = get_pid_gains("vel_lon")
        gains.att_pitch = get_pid_gains("att_pitch")
        gains.yaw = get_pid_gains("yaw")
        gains.alt = get_pid_gains("alt")
        gains.vspeed = get_pid_gains("vspeed")
        gains.hover_feedforward = data.get("hover_feedforward", 0.5)

        return gains


class CoordinateTransformer(object):
    """Handles coordinate rotations between X-Plane and body coordinates.

    Rotates between X-Plane's local OpenGL coordinates and the aircraft's
    body-relative coordinate system.
    """

    @staticmethod
    def rotate_local_to_body_error(delta_x, delta_z, heading_deg):
        """Rotates local OpenGL error differences to body-relative error.

        Args:
            delta_x: target_x - current_x (meters East).
            delta_z: target_z - current_z (meters South).
            heading_deg: Current true heading of aircraft in degrees.

        Returns:
            A tuple of (forward_error, right_error) in meters.
        """
        heading_rad = math.radians(heading_deg)
        cos_h = math.cos(heading_rad)
        sin_h = math.sin(heading_rad)

        # Local X-Plane: +X is East, +Z is South
        # Therefore: North is -Z, East is +X
        north_err = -delta_z
        east_err = delta_x

        # Rotate North/East into aircraft heading (clockwise angle from North)
        forward_error = north_err * cos_h + east_err * sin_h
        right_error = -north_err * sin_h + east_err * cos_h

        return forward_error, right_error

    @staticmethod
    def rotate_local_to_body_velocity(vx, vz, heading_deg):
        """Rotates local OpenGL velocities to body-relative velocity.

        Args:
            vx: local_vx (m/s East).
            vz: local_vz (m/s South).
            heading_deg: Current true heading of aircraft in degrees.

        Returns:
            A tuple of (v_forward, v_right) in m/s.
        """
        heading_rad = math.radians(heading_deg)
        cos_h = math.cos(heading_rad)
        sin_h = math.sin(heading_rad)

        # Local velocities
        v_east = vx
        v_north = -vz

        # Rotate
        v_forward = v_north * cos_h + v_east * sin_h
        v_right = -v_north * sin_h + v_east * cos_h

        return v_forward, v_right


MODE_HOVER = 0
MODE_CRUISE = 1


class HoverAutopilotController(object):
    """Manages nested PID controllers to achieve stable hover.

    Supports selective active/inactive axes in both hover and cruise flight.
    """

    def __init__(self):
        """Initializes the controller and its sub-PIDs."""
        # Flight Mode State
        self.flight_mode = MODE_HOVER

        # --- Hover Lateral (Roll) Controllers ---
        # lateral pos error (m) -> target lateral velocity (m/s)
        self.pos_lat_pid = PID(
            DEFAULT_KP_POS_LAT,
            DEFAULT_KI_POS_LAT,
            DEFAULT_KD_POS_LAT,
            DEFAULT_MIN_POS_LAT,
            DEFAULT_MAX_POS_LAT,
        )
        # lateral vel error (m/s) -> target roll angle (deg)
        self.vel_lat_pid = PID(
            DEFAULT_KP_VEL_LAT,
            DEFAULT_KI_VEL_LAT,
            DEFAULT_KD_VEL_LAT,
            DEFAULT_MIN_VEL_LAT,
            DEFAULT_MAX_VEL_LAT,
        )
        # roll error (deg) & roll rate (deg/s) -> cyclic deflection
        self.att_roll_pid = PID(
            DEFAULT_KP_ATT_ROLL,
            DEFAULT_KI_ATT_ROLL,
            DEFAULT_KD_ATT_ROLL,
            DEFAULT_MIN_ATT_ROLL,
            DEFAULT_MAX_ATT_ROLL,
        )

        # --- Hover Longitudinal (Pitch) Controllers ---
        # longitudinal pos error (m) -> target forward velocity (m/s)
        self.pos_lon_pid = PID(
            DEFAULT_KP_POS_LON,
            DEFAULT_KI_POS_LON,
            DEFAULT_KD_POS_LON,
            DEFAULT_MIN_POS_LON,
            DEFAULT_MAX_POS_LON,
        )
        # longitudinal vel error (m/s) -> target pitch angle (deg)
        self.vel_lon_pid = PID(
            DEFAULT_KP_VEL_LON,
            DEFAULT_KI_VEL_LON,
            DEFAULT_KD_VEL_LON,
            DEFAULT_MIN_VEL_LON,
            DEFAULT_MAX_VEL_LON,
        )
        # pitch error (deg) & pitch rate (deg/s) -> cyclic deflection
        self.att_pitch_pid = PID(
            DEFAULT_KP_ATT_PITCH,
            DEFAULT_KI_ATT_PITCH,
            DEFAULT_KD_ATT_PITCH,
            DEFAULT_MIN_ATT_PITCH,
            DEFAULT_MAX_ATT_PITCH,
        )

        # --- Hover Heading (Yaw) Controller ---
        # heading error (deg) & yaw rate (deg/s) -> rudder deflection
        self.yaw_pid = PID(
            DEFAULT_KP_YAW,
            DEFAULT_KI_YAW,
            DEFAULT_KD_YAW,
            DEFAULT_MIN_YAW,
            DEFAULT_MAX_YAW,
        )

        # --- Hover/Cruise Altitude (Collective) Controllers ---
        # alt error (m) -> target vertical speed (m/s)
        self.alt_pid = PID(
            DEFAULT_KP_ALT,
            DEFAULT_KI_ALT,
            DEFAULT_KD_ALT,
            DEFAULT_MIN_ALT,
            DEFAULT_MAX_ALT,
        )
        # vspeed error (m/s) -> collective delta
        self.vspeed_pid = PID(
            DEFAULT_KP_VSPEED,
            DEFAULT_KI_VSPEED,
            DEFAULT_KD_VSPEED,
            DEFAULT_MIN_VSPEED,
            DEFAULT_MAX_VSPEED,
        )

        # --- Cruise Mode Controllers ---
        # heading error (deg) -> target bank angle (deg)
        self.cruise_hdg_pid = PID(
            DEFAULT_KP_CRUISE_HDG,
            DEFAULT_KI_CRUISE_HDG,
            DEFAULT_KD_CRUISE_HDG,
            DEFAULT_MIN_CRUISE_HDG,
            DEFAULT_MAX_CRUISE_HDG,
        )
        # vertical speed error (m/s) -> target pitch angle (deg)
        self.cruise_vspeed_pitch_pid = PID(
            DEFAULT_KP_CRUISE_VSPEED_PITCH,
            DEFAULT_KI_CRUISE_VSPEED_PITCH,
            DEFAULT_KD_CRUISE_VSPEED_PITCH,
            DEFAULT_MIN_CRUISE_VSPEED_PITCH,
            DEFAULT_MAX_CRUISE_VSPEED_PITCH,
        )
        # lateral G-force (G) -> rudder pedal output (turn coordination)
        self.cruise_yaw_tc_pid = PID(
            DEFAULT_KP_CRUISE_YAW_TC,
            DEFAULT_KI_CRUISE_YAW_TC,
            DEFAULT_KD_CRUISE_YAW_TC,
            DEFAULT_MIN_CRUISE_YAW_TC,
            DEFAULT_MAX_CRUISE_YAW_TC,
        )

        # Active state flags
        self.roll_active = False
        self.pitch_active = False
        self.yaw_active = False
        self.collective_active = False

        # Setpoints (Local OpenGL Coordinates)
        self.target_x = 0.0
        self.target_y = 0.0
        self.target_z = 0.0
        self.target_psi = 0.0
        # Base collective to hover, updated on engagement
        self.hover_feedforward = 0.5

    def reset_position_hold_pids(self):
        """Resets the cyclic position, velocity and attitude PID controllers.

        Clears integral wind-up and stale derivative state for the lateral and
        longitudinal cascade (pos → vel → attitude).  Call this immediately
        after a safety override fires so that the first VFI-commanded frame
        uses a clean starting point.  Yaw and collective PIDs are intentionally
        left untouched because they were tracking correctly during student
        cyclic flight.
        """
        self.pos_lat_pid.reset()
        self.vel_lat_pid.reset()
        self.att_roll_pid.reset()
        self.pos_lon_pid.reset()
        self.vel_lon_pid.reset()
        self.att_pitch_pid.reset()

    def engage(self, x, y, z, psi, collective):
        """Engages the autopilot, capturing the current state as hover targets.

        Args:
            x: Current local X coordinate in meters.
            y: Current local Y coordinate in meters.
            z: Current local Z coordinate in meters.
            psi: Current heading in degrees.
            collective: Current collective input to use as base feedforward.
        """
        self.target_x = x
        self.target_y = y
        self.target_z = z
        self.target_psi = psi
        self.hover_feedforward = collective

        # Reset hover PIDs
        self.pos_lat_pid.reset()
        self.vel_lat_pid.reset()
        self.att_roll_pid.reset()

        self.pos_lon_pid.reset()
        self.vel_lon_pid.reset()
        self.att_pitch_pid.reset()

        self.yaw_pid.reset()

        self.alt_pid.reset()
        self.vspeed_pid.reset()

        # Reset cruise PIDs
        self.cruise_hdg_pid.reset()
        self.cruise_vspeed_pitch_pid.reset()
        self.cruise_yaw_tc_pid.reset()

    def get_gains(self):
        """Captures active PID coefficients into an AutopilotGains DTO."""
        gains = AutopilotGains()
        gains.pos_lat = PIDGains(
            self.pos_lat_pid.kp, self.pos_lat_pid.ki, self.pos_lat_pid.kd
        )
        gains.vel_lat = PIDGains(
            self.vel_lat_pid.kp, self.vel_lat_pid.ki, self.vel_lat_pid.kd
        )
        gains.att_roll = PIDGains(
            self.att_roll_pid.kp, self.att_roll_pid.ki, self.att_roll_pid.kd
        )
        gains.pos_lon = PIDGains(
            self.pos_lon_pid.kp, self.pos_lon_pid.ki, self.pos_lon_pid.kd
        )
        gains.vel_lon = PIDGains(
            self.vel_lon_pid.kp, self.vel_lon_pid.ki, self.vel_lon_pid.kd
        )
        gains.att_pitch = PIDGains(
            self.att_pitch_pid.kp, self.att_pitch_pid.ki, self.att_pitch_pid.kd
        )
        gains.yaw = PIDGains(self.yaw_pid.kp, self.yaw_pid.ki, self.yaw_pid.kd)
        gains.alt = PIDGains(self.alt_pid.kp, self.alt_pid.ki, self.alt_pid.kd)
        gains.vspeed = PIDGains(
            self.vspeed_pid.kp, self.vspeed_pid.ki, self.vspeed_pid.kd
        )
        gains.hover_feedforward = self.hover_feedforward
        return gains

    def set_gains(self, gains):
        """Safely maps AutopilotGains properties onto active PID controllers."""
        if not gains:
            return

        def apply_pid(pid, gains_obj):
            pid.kp = gains_obj.kp
            pid.ki = gains_obj.ki
            pid.kd = gains_obj.kd

        apply_pid(self.pos_lat_pid, gains.pos_lat)
        apply_pid(self.vel_lat_pid, gains.vel_lat)
        apply_pid(self.att_roll_pid, gains.att_roll)
        apply_pid(self.pos_lon_pid, gains.pos_lon)
        apply_pid(self.vel_lon_pid, gains.vel_lon)
        apply_pid(self.att_pitch_pid, gains.att_pitch)
        apply_pid(self.yaw_pid, gains.yaw)
        apply_pid(self.alt_pid, gains.alt)
        apply_pid(self.vspeed_pid, gains.vspeed)
        self.hover_feedforward = gains.hover_feedforward

    def update(self, dt, state):
        """Runs one step of the autopilot control loops.

        Args:
            dt: Time step in seconds.
            state: Dict containing current flight states:
              'x', 'y', 'z', 'vx', 'vy', 'vz', 'phi', 'theta', 'psi',
              'P', 'Q', 'R', 'g_side'.
              Angles in degrees.
              Angular rates in degrees/second.
              g_side in units of Gs.

        Returns:
            Dict containing calculated deflection commands (range -1.0 to 1.0,
            or 0.0 to 1.0 for collective):
            { 'roll', 'pitch', 'yaw', 'collective' }
        """
        # Synchronize target setpoints for inactive axes to match current state
        # (prevents jumps on engagement)
        if not self.roll_active:
            if self.flight_mode == MODE_CRUISE:
                self.target_psi = state["psi"]
            else:
                self.target_x = state["x"]
        if not self.pitch_active:
            if self.flight_mode == MODE_CRUISE:
                self.target_y = state["y"]
            else:
                self.target_z = state["z"]
        if not self.yaw_active:
            self.target_psi = state["psi"]
        if not self.collective_active:
            self.target_y = state["y"]

        # Extract angular rates
        roll_rate_deg_s = state["P"]
        pitch_rate_deg_s = state["Q"]
        yaw_rate_deg_s = state["R"]

        if self.flight_mode == MODE_CRUISE:
            # ==========================================
            # CRUISE MODE FLIGHT CONTROL LOOPS
            # ==========================================

            # --- Roll Axis: Heading Hold (using Roll Bank) ---
            yaw_err = wrap_180(self.target_psi - state["psi"])
            if self.roll_active:
                # Heading error -> target bank angle (degrees)
                target_roll = self.cruise_hdg_pid.update(yaw_err, dt)
                roll_cmd = self.att_roll_pid.update(
                    target_roll - state["phi"], dt, rate=roll_rate_deg_s
                )
            else:
                self.cruise_hdg_pid.reset()
                self.att_roll_pid.reset()
                target_roll = state["phi"]
                roll_cmd = 0.0

            # --- Pitch Axis: Altitude Hold (Alt on Pitch) ---
            alt_err = self.target_y - state["y"]
            if self.pitch_active:
                # Altitude error -> target vertical speed (m/s)
                target_v_vert = self.alt_pid.update(alt_err, dt)
                # Vertical speed error -> target pitch attitude (degrees)
                target_pitch = self.cruise_vspeed_pitch_pid.update(
                    target_v_vert - state["vy"], dt
                )
                pitch_cmd = self.att_pitch_pid.update(
                    target_pitch - state["theta"], dt, rate=pitch_rate_deg_s
                )
            else:
                self.alt_pid.reset()
                self.cruise_vspeed_pitch_pid.reset()
                self.att_pitch_pid.reset()
                target_v_vert = 0.0
                target_pitch = state["theta"]
                pitch_cmd = 0.0

            # --- Yaw Axis: Turn Coordination (Pedals) ---
            if self.yaw_active:
                # Nullify lateral force (keep slip-skid ball centered).
                # Positive g_side is rightward acceleration (skidding right),
                # countering requires left pedal (negative).
                g_side_err = 0.0 - state.get("g_side", 0.0)
                yaw_cmd = self.cruise_yaw_tc_pid.update(
                    g_side_err, dt, rate=yaw_rate_deg_s
                )
            else:
                self.cruise_yaw_tc_pid.reset()
                yaw_cmd = 0.0

            # --- Collective Axis: Manual/Constant power in cruise ---
            collective_cmd = self.hover_feedforward

            # Setup dummy values for hover debug variables
            fwd_err = 0.0
            lat_err = 0.0
            target_v_fwd = 0.0
            target_v_lat = 0.0
            v_fwd = 0.0
            v_lat = 0.0

        else:
            # ==========================================
            # HOVER MODE FLIGHT CONTROL LOOPS
            # ==========================================

            # Calculate coordinate differences in X-Plane OpenGL local system
            delta_x = self.target_x - state["x"]
            delta_z = self.target_z - state["z"]

            # 1. Transform position error to body-relative error (Forward/Right)
            fwd_err, lat_err = CoordinateTransformer.rotate_local_to_body_error(
                delta_x, delta_z, state["psi"]
            )

            # 2. Transform velocities to body-relative velocities
            v_fwd, v_lat = CoordinateTransformer.rotate_local_to_body_velocity(
                state["vx"], state["vz"], state["psi"]
            )

            # --- Lateral Control Loop (Roll) ---
            if self.roll_active:
                target_v_lat = self.pos_lat_pid.update(lat_err, dt)
                target_roll = self.vel_lat_pid.update(target_v_lat - v_lat, dt)
                roll_cmd = self.att_roll_pid.update(
                    target_roll - state["phi"], dt, rate=roll_rate_deg_s
                )
            else:
                self.pos_lat_pid.reset()
                self.vel_lat_pid.reset()
                self.att_roll_pid.reset()
                target_v_lat = 0.0
                target_roll = state["phi"]
                roll_cmd = 0.0

            # --- Longitudinal Control Loop (Pitch) ---
            if self.pitch_active:
                target_v_fwd = self.pos_lon_pid.update(fwd_err, dt)
                target_pitch = -self.vel_lon_pid.update(target_v_fwd - v_fwd, dt)
                pitch_cmd = self.att_pitch_pid.update(
                    target_pitch - state["theta"], dt, rate=pitch_rate_deg_s
                )
            else:
                self.pos_lon_pid.reset()
                self.vel_lon_pid.reset()
                self.att_pitch_pid.reset()
                target_v_fwd = 0.0
                target_pitch = state["theta"]
                pitch_cmd = 0.0

            # --- Heading Control Loop (Yaw) ---
            yaw_err = wrap_180(self.target_psi - state["psi"])
            if self.yaw_active:
                yaw_cmd = self.yaw_pid.update(yaw_err, dt, rate=yaw_rate_deg_s)
            else:
                self.yaw_pid.reset()
                yaw_cmd = 0.0

            # --- Altitude Control Loop (Collective) ---
            alt_err = self.target_y - state["y"]
            if self.collective_active:
                target_v_vert = self.alt_pid.update(alt_err, dt)
                collective_delta = self.vspeed_pid.update(
                    target_v_vert - state["vy"], dt
                )
                collective_cmd = self.hover_feedforward + collective_delta
                collective_cmd = max(0.0, min(1.0, collective_cmd))
            else:
                self.alt_pid.reset()
                self.vspeed_pid.reset()
                target_v_vert = 0.0
                collective_cmd = self.hover_feedforward

        return {
            "roll": roll_cmd,
            "pitch": pitch_cmd,
            "yaw": yaw_cmd,
            "collective": collective_cmd,
            # Intermediate targets for UI feedback
            "debug": {
                "fwd_err": fwd_err,
                "lat_err": lat_err,
                "alt_err": (
                    alt_err
                    if self.flight_mode == MODE_HOVER
                    else (self.target_y - state["y"])
                ),
                "yaw_err": yaw_err,
                "target_v_fwd": target_v_fwd,
                "target_v_lat": target_v_lat,
                "target_v_vert": (
                    target_v_vert
                    if self.flight_mode == MODE_HOVER
                    else (
                        self.alt_pid.update(self.target_y - state["y"], dt)
                        if self.pitch_active
                        else 0.0
                    )
                ),
                "target_pitch": target_pitch,
                "target_roll": target_roll,
                "v_fwd": v_fwd,
                "v_lat": v_lat,
            },
        }
