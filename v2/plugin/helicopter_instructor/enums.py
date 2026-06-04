"""Enum definitions for the Helicopter Flight Instructor state machine.

Centralises all symbolic constants for states, authority, proficiency
grades, and safety zones.
"""

from enum import Enum


class VFIState(Enum):
    """States of the Virtual Flight Instructor state machine.

    Lifecycle:
        VFI_FLIGHT -> SYNCING -> STUDENT_FLIGHT -> OVERRIDE
            -> RECOVERY_HOLD -> SYNCING ...
    """

    VFI_FLIGHT = "VFI_FLIGHT"
    SYNCING = "SYNCING"
    STUDENT_FLIGHT = "STUDENT_FLIGHT"
    OVERRIDE = "OVERRIDE"
    RECOVERY_HOLD = "RECOVERY_HOLD"


class ControlAxis(Enum):
    """Flight control axes.

    Used as dictionary keys in PHASE_CONFIGS, control_assignment,
    sync_locked, hardware inputs, and VFI outputs.
    """

    ROLL = "roll"
    PITCH = "pitch"
    YAW = "yaw"
    COLLECTIVE = "collective"


class Authority(Enum):
    """Axis control authority assignment.

    Each flight axis (roll, pitch, yaw, collective) is assigned
    either VFI (autopilot) or STUDENT (human pilot) authority.
    """

    VFI = "VFI"
    STUDENT = "STUDENT"


class Envelope(Enum):
    """Proficiency envelope grades over the sliding window.

    See envelope_limits.py and metrics.py for the specific
    thresholds that define each grade.
    """

    EXCELLENT = "Excellent"
    GOOD = "Good"
    UNSTABLE = "Unstable"


class HeadingZone(Enum):
    """Heading error safety zone classification.

    GREEN: Within green-zone heading tolerance.
    ORANGE: Between green and orange heading limits.
    RED: Beyond orange heading limit (triggers safety override).
    """

    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


class CaptionStyle(Enum):
    """Style classifications for HUD caption announcements.

    Determines text coloring on the HUD overlay.
    """

    DANGER = "danger"
    SUCCESS = "success"
    WARNING = "warning"
    INFO = "info"

