# Release Notes

## v2.1.36 - 2026-06-01
- **Added**: Automatic phase progression. The instructor now advances the
  training curriculum automatically once the student has maintained an
  "Excellent" proficiency envelope for 30 continuous seconds. The VFI takes
  back full control, plays *Phase transition.wav*, plays the per-phase intro
  audio (*Phase N intro.wav*), then hands the next phase back to the student.
  After mastering all six phases the instructor plays *Now you know how to
  hover.wav* and stops advancing.

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

