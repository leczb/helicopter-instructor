# AGENTS.md — Helicopter Flight Instructor Plugin

AI agent rules, architecture notes, and coding conventions for the
**Helicopter Virtual Flight Instructor** X-Plane 12 plugin (v2).

---

## 1. Project Overview

This is an X-Plane 12 plugin written in Python (XPPython3 runtime). It acts as a
virtual flight instructor for student helicopter pilots, providing:

- A cascaded PID autopilot that can hold a 3D hover target
- A 6-phase training curriculum that progressively hands axes of control to the student
- Real-time performance metrics (precision, smoothness, safety envelope)
- Audio coaching cues and an ImGui control panel

Active plugin version is in `v2/plugin/PI_helicopter_instructor.py`:

```python
self.version = "X.Y.Z"   # bump patch version (Z) on every commit (see Section 9)
```

---

## 2. Repository Layout

```
helicopter-instructor/
├── AGENTS.md                          # ← this file
└── v2/
    ├── plugin/
    │   ├── PI_helicopter_instructor.py    # X-Plane entry point; keep minimal
    │   └── helicopter_instructor/
    │       ├── envelope_limits.py         # SINGLE SOURCE OF TRUTH for all limits
    │       ├── metrics.py                 # Performance scoring engine
    │       ├── virtual_instructor.py      # State machine + safety enforcement
    │       ├── audio.py                   # WAV playback via XP OpenAL
    │       ├── ui.py                      # ImGui control panel
    │       ├── hud.py                     # OSD overlay + alt bar
    │       ├── graphics.py                # Programmatic OBJ8 + texture generation
    │       ├── config.py                  # Aircraft detection + PID JSON I/O
    │       └── autopilot/
    │           └── helicopter_control.py  # Cascaded PID loops
    ├── tests/                             # Python unittest suite
    └── docs/                             # Architecture + spec documents
```

---

## 3. Critical Architecture Rules

### 3.1 `envelope_limits.py` is the single source of truth for all limits

All safety thresholds, scoring zones, and visual ring radii **must be defined
once** in `v2/plugin/helicopter_instructor/envelope_limits.py` and imported
everywhere else. Never hardcode a limit value in another module.

```python
# CORRECT
from helicopter_instructor.envelope_limits import LIMIT_DRIFT_RED_M

# WRONG — never do this
TAKEOVER_RADIUS = 45.0  # duplicating a limit inline
```

Any new limit added to `envelope_limits.py` must also have a corresponding
contract test in `v2/tests/test_limits_contract.py` asserting that the alias
in `metrics.py` matches the canonical value.

### 3.2 Dependency injection pattern

Sub-modules receive the state they need as function arguments rather than
reading from global or module-level singletons. Avoid adding mutable
module-level variables to any sub-module.

### 3.3 X-Plane 3D rendering — use XPLMInstance, never raw OpenGL

Direct OpenGL drawing callbacks (`Phase_Modern3D`, `Phase_FirstCockpit`) do
**not** render under Vulkan/Metal and lack depth occlusion. For all 3D
in-world visualization:

1. **Generate OBJ8 files** at startup using `VLINE`/`LINES` primitives
   (see `graphics.py`).
2. **Load** via `xp.loadObject()`.
3. **Instantiate** via `xp.createInstance()`.
4. **Update position** at 50 Hz in `flight_loop_callback` via
   `xp.instanceSetPosition()`. Hide by setting `y = -9999.0`.

### 3.4 Flight loop runs at 50 Hz — keep it fast

All code called from `flight_loop_callback` must be O(n) or better with
small constants. No disk I/O, no blocking calls, no dynamic memory allocation
in the hot path. The metrics circular buffer is capped at 3,000 frames (60 s).

---

## 4. VFI State Machine

The Virtual Instructor cycles through five states:

```
VFI_FLIGHT → SYNCING → STUDENT_FLIGHT → OVERRIDE → RECOVERY_HOLD → SYNCING …
```

| State | Description |
|---|---|
| `VFI_FLIGHT` | VFI holds 100% authority on all axes |
| `SYNCING` | VFI holds authority; student aligns hardware to VFI outputs within ±4% for ≥ 500 ms |
| `STUDENT_FLIGHT` | Student has authority on phase-assigned axes; soft blending active 30–45 m from target |
| `OVERRIDE` | Safety limit violated; VFI takes instant 100% control, target set to current position |
| `RECOVERY_HOLD` | Helicopter stabilised; original target restored; 3 s countdown before re-SYNCING |

**Safety takeover triggers** (OVERRIDE): attitude > 15°, climb/sink > 300 ft/min,
AGL < 2.0 m or > 10.0 m, ground speed > 12 knots, or drift > 45 m.

---

## 5. Training Curriculum (6 Phases)

Phases progressively hand axes of control to the student. The authoritative
phase definitions live in `virtual_instructor.PHASE_CONFIGS`. Precision
scoring and audio cues are gated on the axes marked `"STUDENT"` in the
active phase.
---

## 6. Performance Metrics

### Scoring components (gated by active phase)

| Component | Phase Gate | Green Zone (100%) | Orange Limit (0%) |
|---|---|---|---|
| Heading error | Yaw = STUDENT | ≤ 30.0° | 60.0° |
| Altitude error | Collective = STUDENT | ≤ 2.0 m | 4.0 m |
| Horizontal drift | Cyclic = STUDENT | ≤ 15.0 m | 45.0 m |
| Drift speed (ground) | Cyclic = STUDENT | ≤ 0.5 m/s | 2.0 m/s |
| Vertical speed | Collective = STUDENT | ≤ 0.2 m/s | 0.8 m/s |

All limits live in `envelope_limits.py`; scoring aliases live in `metrics.py`
(verified by `test_limits_contract.py`).

### Proficiency envelope (60-second sliding window)

| Grade | Condition |
|---|---|
| **Excellent** | > 60% of window frames meet all green-zone thresholds and OCI < 0.3/0.2 |
| **Good** | Unstable ratio ≤ 15% and Excellent ratio ≤ 60% |
| **Unstable** | > 15% of frames breach any orange limit or OCI > 1.5 |

---

## 7. Code Style

Follows the **Google Python Style Guide** throughout.

- **Line length**: 80 characters max
- **Indentation**: 4 spaces, no tabs
- **Blank lines**: 2 between top-level definitions, 1 between methods
- **Docstrings**: Google format with `Args:` / `Returns:` sections on every
  public function and class
- **Imports**: stdlib → third-party (`xp`, `imgui`) → local
  (`helicopter_instructor.*`), each group alphabetically sorted

---

## 8. Testing

Run the full suite from `v2/`:

```bash
python -m pytest tests/ -v
# or
python -m unittest discover tests
```

**All tests must pass before committing.** Coverage:

```bash
python -m coverage run -m unittest discover tests
python -m coverage report -m
```

### Test conventions

- New scoring limits → add a contract assertion in `test_limits_contract.py`
- New metrics behaviour → add a unit test in `test_metrics.py`
- New audio behaviour → add a unit test in `test_audio.py`
- Tests must not import `xp`, `imgui`, or any X-Plane module directly;
  mock them at the top of the test file as shown in `test_limits_contract.py`

---

## 9. Versioning & Committing

> **CRITICAL — follow every time.**

1. Before every `git commit`, increment the **patch** version (`Z` in `X.Y.Z`)
   in `v2/plugin/PI_helicopter_instructor.py`:
   ```python
   self.version = "2.1.15"   # was 2.1.14
   ```
2. Include the new version string in the commit message.
3. **Never commit without explicit user approval** — present the diff and
   proposed commit message first.
4. Use conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `docs:`,
   `test:`, `chore:`.

---

## 10. What Not to Do

- **Do not** duplicate limit constants outside `envelope_limits.py`.
- **Do not** add raw OpenGL 3D drawing; use the XPLMInstance API (Section 3.3).
- **Do not** perform disk I/O or blocking operations inside `flight_loop_callback`.
- **Do not** add mutable module-level state to sub-modules.
- **Do not** commit without running the full test suite and bumping the version.
