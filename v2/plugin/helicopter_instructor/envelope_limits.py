"""Centralized flight envelope boundaries, visual rings, and scoring zones."""

# --- 1. YAW / HEADING PARAMETERS (Degrees and deg/s) ---
LIMIT_HDG_GREEN_DEG = 30.0  # Green visual arc & score dead-zone
LIMIT_HDG_ORANGE_DEG = 60.0  # Caution limit; hard takeover beyond this
LIMIT_YAW_SPEED_GREEN_DEG_S = 4.0  # Green zone yaw rate; dead-zone
LIMIT_YAW_SPEED_ORANGE_DEG_S = 10.0  # Orange zone yaw rate limit

# --- 2. ALTITUDE / COLLECTIVE PARAMETERS (6.0m target deviation) ---
LIMIT_ALT_GREEN_M = 2.0  # HUD green band (4.0m - 8.0m AGL); score dead-zone
LIMIT_ALT_ORANGE_M = 4.0  # Safety limit (2.0m/10.0m AGL); takeover beyond this

# --- 3. TRANSLATION / DRIFT PARAMETERS (m radius and speed) ---
LIMIT_DRIFT_GREEN_M = 15.0  # 3D green ring (disk_15m.obj); score dead-zone
LIMIT_DRIFT_ORANGE_M = 30.0  # 3D orange ring; caution zone boundary
LIMIT_DRIFT_RED_M = 45.0  # 3D red ring; hard takeover override triggers
LIMIT_DRIFT_SPEED_GREEN_M_S = (
    0.5  # Green zone speed limit (perfect hover score); dead-zone
)
LIMIT_DRIFT_SPEED_ORANGE_M_S = (
    2.0  # Orange zone speed (0% score/unstable); warning bounds
)

# --- 4. VERTICAL SPEED PARAMETERS (m/s climb/descent rate) ---
LIMIT_VERT_SPEED_GREEN_M_S = (
    0.2  # Green zone vertical speed (perfect hover score); dead-zone
)
LIMIT_VERT_SPEED_ORANGE_M_S = (
    0.8  # Orange zone vertical speed (0% score/unstable); warning bounds
)


# --- 5. SAFETY TAKEOVER RECOVERY SEQUENCE CONSTANTS ---
LIMIT_RECOVERY_ALT_RATE_M_S = (
    1.0  # Rate (m/s) to slowly change target hover height during settling
)
LIMIT_RECOVERY_SPEED_M_S = (
    2.0  # Speed (m/s) to slowly translate hover target back to original
)

# --- 6. SAFETY LIMITS & OVERRIDE BOUNDARIES (Check Safety Limits) ---
LIMIT_ATTITUDE_DEG = 15.0  # Pitch & roll safety override takeover limit
LIMIT_YAW_RATE_DEG_S = 30.0  # Yaw rate safety override takeover limit
LIMIT_VSPEED_FT_MIN = 300.0  # Vertical speed safety override limit
LIMIT_GS_KNOTS = 12.0  # Ground speed safety override limit
LIMIT_AGL_MIN_M = 2.0  # Terrain height minimum AGL limit
LIMIT_AGL_MAX_M = 10.0  # Terrain height maximum AGL limit

# --- 7. SAFETY RECOVERY STABILIZATION BOUNDARIES (Process Recovery) ---
LIMIT_RECOVERY_ATTITUDE_DEG = 2.0  # Safe pitch & roll bounds for recovery hold
LIMIT_RECOVERY_SINK_FT_MIN = -50.0  # Arrested vertical sink rate limit
LIMIT_RECOVERY_GS_KNOTS = 1.0  # Safe ground speed limit for recovery hold

