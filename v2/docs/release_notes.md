# Release Notes

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
- **Added**: Excellent Criteria Debug panel on the HUD OSD. When enabled it
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
