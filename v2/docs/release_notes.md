# Release Notes

## v2.1.73 - 2026-06-15

- **Feature**: Added automated update checking using the GitHub releases API.
  The plugin checks for updates in a background thread at startup, comparing
  the latest release version against the installed version.
- **Feature**: Added update status displays (checking, up to date, update
  available, and error with retry option) and a button to view/download the
  release in the browser within the ImGui control panel.

## v2.1.72 - 2026-06-15

- **Feature**: Automatically hide the HUD when "MASTER INSTRUCTOR ENGAGE" is disabled.
- **Fixed**: Resolved a graphics pipeline conflict under Linux/Wayland where creating the HUD window as invisible caused the ImGui Control Panel UI to render blank. The HUD window is now kept registered as visible in X-Plane but renders as transparent off-screen when disabled.

## v2.1.71 - 2026-06-15

- **Feature**: Hide the HUD by default, and automatically show it once the "MASTER INSTRUCTOR ENGAGE" is enabled by the user.

## v2.1.70 - 2026-06-15

- **Docs**: Added a clear disclaimer warning that this software is strictly for simulator flying and not intended or approved for real-world flight training.

## v2.1.69 - 2026-06-08

- **Fixed**: Prevent skipped lesson introduction audio files from piling up in the sequential playback queue during rapid manual phase navigation. Changing phases now cancels and clears any playing or queued intros.

## v2.1.68 - 2026-06-08

- **Feature**: Automatically trigger control hand-off (transition to `SYNCING` state) after the initial lesson introduction audio plays and finishes upon autopilot engagement.
- **Docs**: Updated README.md instructions under "How to Use" to reflect the new automatic hand-off behavior.

## v2.1.67 - 2026-06-06

- **Improvement**: Formatted the stability envelope grade on the HUD to use the enum member's name string (e.g., `"EXCELLENT"`, `"GOOD"`, `"UNSTABLE"`) instead of displaying the raw Python object representation (`"Envelope.EXCELLENT"`).
- **Improvement**: Re-formatted `hud.py` code for styling consistency.
- **Improvement**: Updated system state status labels on the HUD to be more user-friendly (e.g. "STANDBY" instead of "STANDBY (DISENGAGED)", "INSTRUCTOR FLYING" instead of "AUTO HOVER ACTIVE", "STUDENT FLYING" instead of "STUDENT IN CONTROL", and "SAFETY INTERVENTION" instead of "TAKEBACK TAKEOVER ACTIVE!").

- **Docs**: Updated `v2/docs/state_machine_diagram.md` to reflect the current state of the virtual instructor state machine, adding the `CELEBRATING` transitional state and documenting the delayed control handoff behavior (which waits for the phase explanation audio to finish).

## v2.1.65 - 2026-06-05

- **Refactor**: Cleaned up the codebase to ensure 100% style and docstring consistency.
  - Standardized all string literals to use double quotes (`"`) across both the plugin and test suites.
  - Formatted all long lines to strictly fit within the 80-character limit.
  - Completed Google-style docstrings with descriptive `Args:` and `Returns:` sections for all public functions, classes, properties, and command handlers.
  - Verified code style and AST docstring checkers report zero violations.

## v2.1.64 - 2026-06-04

- **Fixed**: Resolved a bug where control handoffs during automatic and manual phase transitions would happen too quickly if user inputs happened to match target values, skipping the "Get ready to take control" audio cue. Handoff synchronization is now delayed until after the phase explanation/intro audio finishes playing.

## v2.1.63 - 2026-06-04

- **Fixed**: Fixed a bug where a safety override or manual phase change during the delayed phase transition (`CELEBRATING`) would leave the `transition_in_progress` flag set to `True` indefinitely. Centralized the resetting of the flag in the `system_state` property setter to clear it whenever the state transitions to any state other than `CELEBRATING`.

## v2.1.62 - 2026-06-04

- **Fixed**: Simplified the "Perfect" hover praise timer check to evaluate only the `Envelope.EXCELLENT` grade (removing the drift speed limit constraint). This enables "Perfect" praise cues to play across all curriculum phases when the student is active and performing excellently, regardless of whether they have cyclic control.

## v2.1.61 - 2026-06-04

- **Improvement**: Postponed virtual flight instructor control takeover during automatic phase transitions. The student now retains control of the helicopter during the playback of the `Phase transition.wav` jingle, and control is handed over to the VFI only after the chime finishes.
- **Improvement**: Added a new transitional state `VFIState.CELEBRATING` to represent this phase transition delay.
- **Improvement**: Safety override limit checks remain fully active during this celebrating period. If any limit is breached, the state transitions immediately to `OVERRIDE` and the jingle delay is canceled.
- **Improvement**: Shortened the continuous "Excellent" rating duration requirement for automatic phase transition from 35 seconds to 25 seconds (`PHASE_EXCELLENT_REQUIRED_S`).

## v2.1.60 - 2026-06-04

- **Refactor**: Extracted unit conversion constants (such as `M_S_TO_FT_MIN` and `M_S_TO_KNOTS`) from `virtual_instructor.py` and `metrics.py` into a new central module `constants.py` to eliminate duplication and clean up code organization.

## v2.1.59 - 2026-06-04

- **Fixed**: Fixed a type-checking bug in the automatic phase progression sequence where `PhaseAdvancedEvent` instances returned by the reloaded `virtual_instructor` module failed type checking via `isinstance` in `PI_helicopter_instructor.py`. Replaced the direct class type check with a namespace-aware check (`virtual_instructor.PhaseAdvancedEvent`) to ensure the transition audio cue ("Phase transition.wav") plays correctly.

## v2.1.58 - 2026-06-04

- **Fixed**: Reset the student evaluation timer (`excellent_timer`) to `0.0` when the student takes control (`STUDENT_FLIGHT`). This prevents the curriculum from instantly completing a phase after regaining control if they had previously accumulated time before an override or handoff.

## v2.1.57 - 2026-06-04

- **Improvement**: Enhanced logging architecture for better bug reports and troubleshooting.
  - Replaced legacy print statements and raw `xp.log` calls with standard Python `logging`.
  - Configured a dual-handler logging setup: (1) `RotatingFileHandler` writing isolated logs to `helicopter_instructor.log` under the plugin folder, and (2) custom `XPLogHandler` mirroring records to X-Plane's `xp.log` (letting XPPython3 handle the plugin prefix automatically).
  - Structured logs to capture critical system events (VFI state transitions, synchronization lock states, control handoffs, curriculum phase advancement, and detailed safety breach reasons) on an edge-triggered basis to ensure O(1) file-safety inside the 50Hz flight loop callback.
  - Logged instructor verbal coaching warnings/praise cue decisions and audio play/stop events (including duration tracking).
  - Wrapped the 50Hz flight loop callback in a try-except handler to safely log tracebacks of uncaught errors before reporting them to X-Plane.

## v2.1.56 - 2026-06-04

- **Refactor**: Resolved caption color routing fragility by introducing an
  explicit style parameter (`hud_caption_style`) on the HUD. The color
  routing is now driven by semantic style states (`danger`, `success`,
  `warning`, `info`) instead of checking substrings of the display text,
  making the HUD presentation robust to subtitle text changes.

## v2.1.55 - 2026-06-04

- **Refactor**: Extracted all hardcoded safety limit parameters from the state
  machine checks (`check_safety_limits()`) and post-takeover settling checks
  (`process_recovery()`) in `virtual_instructor.py` into
  `envelope_limits.py`. This aligns the module with project safety rules,
  making `envelope_limits.py` the single source of truth for all limits.

## v2.1.54 - 2026-06-04

- **Refactor**: Encapsulated state transitions within the `VirtualInstructor`
  class. Added transition validation to prevent invalid states and removed
  direct state mutations from the plugin. Automatic phase advance
  orchestration is now handled internally by `VirtualInstructor.update()`,
  returning events via a backward-compatible `UpdateResult` dictionary
  subclass.

## v2.1.53 - 2026-06-04

- **Refactor**: Introduced `ControlAxis` enum (`ROLL`, `PITCH`, `YAW`,
  `COLLECTIVE`) to replace raw string dictionary keys for flight axis
  identification across the entire codebase. All `PHASE_CONFIGS`,
  `control_assignment`, `sync_locked`, hardware inputs, VFI outputs, OCI
  metrics, and HUD rendering now use type-safe enum keys.

## v2.1.52 - 2026-06-04

- **Refactor**: Replaced all raw string comparisons for state machine states,
  axis authority, proficiency envelope, and heading zones with Python `Enum`
  types (`VFIState`, `Authority`, `Envelope`, `HeadingZone`). This eliminates
  an entire class of silent typo bugs and enables IDE autocompletion across
  the codebase. New central module: `helicopter_instructor/enums.py`.

## v2.1.51 - 2026-06-03

- **Docs**: Wired curriculum phase screenshots, target safety zones, and external view images into the top-level README.md.

## v2.1.50 - 2026-06-03

- **Fixed**: Restrained the translucent dark background box of the HUD to only cover the bottom control input graphics section. This prevents text elements (which are drawn at a scaled 2x size) from stretching past or spilling horizontally out of the background.

## v2.1.49 - 2026-06-03

- **Refactor**: Consistently renamed all "OSD" / "On-Screen Display" occurrences to "HUD" (Heads-Up Display) across code and documentation.

## v2.1.48 - 2026-06-02

- **Chore**: Formatted all .py files with Black

- **Chore**: Removed unnecessary prefix "Helicopter Flight Instructor: " from log messages

## v2.1.47 - 2026-06-02

- **Fixed**: Updated the plugin signature and description to be consistent
  with X-Plane community practices.

- **Fixed**: Updated Markdown formatting and cleaned up some comments.

## v2.1.46 - 2026-06-02

- **Docs**: Updated `AGENTS.md` test commands to use `python3` (the correct
  interpreter on macOS) and replaced the `pytest` invocation with
  `python3 -m unittest discover tests -v`.

## v2.1.45 - 2026-06-02

- **Fixed**: "Phase transition.wav" is no longer played when the student
  completes Phase 6 (the final phase). There is no next phase to transition
  into, so the VFI now goes straight to the completion cue
  ("Now you know how to hover.wav") without the preceding jingle.

## v2.1.44 - 2026-06-02

- **Fixed**: Eliminated attitude jolts at every phase transition, not just
  safety overrides. When the VFI reclaims cyclic authority from the student
  (on any STUDENT_FLIGHT → \* transition), the position/velocity/attitude PID
  cascade is now reset before the VFI issues its first cyclic command.

  Three distinct paths all trigger the reset:
  - **Safety override** — state changes inside `instructor.update()` (Step C).
  - **Manual phase change** — command handler fires between frames; on the
    next frame `last_system_state` is still `STUDENT_FLIGHT` while
    `curr_state` is already `SYNCING`.
  - **Automatic phase advance** — state changes inside STEP C4 (within the
    same frame as the last student frame); the check runs after the STEP C4
    re-read so it catches the within-frame flip.

  Previously only the safety-override path was covered; the two phase-change
  paths were silently missed.

## v2.1.43 - 2026-06-02

- **Fixed**: Eliminated the violent attitude jolt that occurred when the VFI
  took back cyclic control after a safety boundary violation (e.g. drifting
  45 m from the hover target in Phase 4).

  **Root cause:** The flight loop was applying the override (snapping the
  hover target to the current position) _after_ the autopilot had already
  computed its commands for that frame. This meant the PID cascade saw a 45 m
  position error on the first recovery frame and produced maximum cyclic
  deflection. Additionally, the position/velocity/attitude PIDs had accumulated
  large integrals during student flight (they run continuously to provide
  stable reference outputs), which persisted into the first recovery frame and
  compounded the jolt.

  **Fix (two parts):**
  1. The override target snap now runs _before_ `controller.update()` on every
     frame, so the autopilot always sees the correct hover position.
  2. When an override first fires, the lateral and longitudinal position,
     velocity, and attitude PIDs are explicitly reset — clearing wound-up
     integrals and stale derivative state. Recovery from frame N+1 onwards
     therefore produces calm, near-zero attitude commands.

## v2.1.42 - 2026-06-02

- **Fixed**: Manually selecting a phase via the UI now plays that phase's
  intro audio. If the student was flying, "I have control" plays first;
  if the VFI already had control, only the intro is queued.

## v2.1.41 - 2026-06-02

- **Fixed**: Phase 1 intro audio ("Phase 1 intro.wav") is now played when the
  VFI first engages, so the student always hears an explanation of the current
  phase before taking the controls. Re-engaging on any phase will play that
  phase's intro.
- **Fixed**: Two unit tests in `test_audio.py` that broke in v2.1.40 when the
  audio registry gained a `duration_s` field — updated mock entries to include
  the new key.

## v2.1.40 - 2026-06-01

- **Fixed**: Fixed audio length management. Instead of hardcoding the length of audio samples,
  we now compute the length of each audio sample at load time.
  This ensures that the length of the audio samples is always correct.

## v2.1.39 - 2026-06-01

- **Improved**: Relaxed Phase 1 "Excellent" rating criteria — yaw rate green
  limit raised from 2.0 to 4.0 deg/s and pedal OCI threshold raised from 0.2
  to 0.3, making the grade more achievable during early pedal training.
- **Improved**: Proficiency sliding window shortened from 60 s to 20 s so that
  a good run of pedal control flips the envelope grade to Excellent much faster.
- **Added**: Excellent Criteria Debug panel on the HUD. When enabled it
  shows live heading error, yaw rate, and pedal OCI values next to their limits
  with OK / !! colour indicators. Toggle via "Show Excellent Criteria Debug
  Info" in the UI panel (disabled by default, indented under the HUD overlay
  toggle).

## v2.1.36 - 2026-06-01

- **Added**: Automatic phase progression. The instructor now advances the
  training curriculum automatically once the student has maintained an
  "Excellent" proficiency envelope for 30 continuous seconds. The VFI takes
  back full control, plays _Phase transition.wav_, plays the per-phase intro
  audio (_Phase N intro.wav_), then hands the next phase back to the student.
  After mastering all six phases the instructor plays _Now you know how to
  hover.wav_ and stops advancing.

## v2.1.35 - 2026-06-01

- **Added**: Safety takeover recovery with smooth parallel target translation.

## v2.1.34 - 2026-06-01

- **Added**: Completely remove soft blending feature and update documentation.

## v2.1.33 - 2026-06-01

- **Added**: Implement immediate parallel recovery target translation.

## v2.1.32 - 2026-06-01

- **Added**: Implement three‑stage post‑takeover target stabilization.

## v2.1.31 - 2026-06-01

- **Docs**: Correct state delegation explanation and provide `load_gains` example in developer documentation.

## v2.1.30 - 2026-06-01

- **Docs**: Update design specifications, README tree, and developer docs.

## v2.1.29 - 2026-06-01

- **Added**: Scale overall and precision scores by station‑keeping deviation.

## v2.1.28 - 2026-06-01

- **Fixed**: Gate sliding‑window envelope evaluation on active student axes.

## v2.1.27 - 2026-06-01

- **Added**: Integrate yaw‑rate into central envelope and expose it in ImGui UI metrics panel.

## v2.1.26 - 2026-06-01

- **Added**: Tighten Nice recovery triggers and reset warning state on takeover.

## v2.1.21 - 2026-06-01

- **Docs**: Add minimal factual project‑level README.md.
- **Fixed**: Stop active audio channel before playing new sound to prevent overlapping playback.

## v2.1.20 - 2026-06-01

- **Fixed**: Warn about drift sooner.
- **Fixed**: Trigger altitude and drift warnings at green‑zone boundary rather than midway in the orange band.
- **Misc**: Import v2 as the initial state.
