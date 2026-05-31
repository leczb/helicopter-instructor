# v2 Development Tasks

Track tasks, progress, and upcoming features for the Helicopter Instructor (v2).

## Safety, Limits & Zone Adjustments
- [x] Add hovering safety distance from set target (lateral / longitudinal bounding circle); default: 45 meter radius (soft blending starts at 30m; 15m used for perfect hover evaluation)
- [x] When doing a safety hard take-over, first set the hover set-point to the *current* position, let the attitude settle and only then move the hover set-point to the original value.
- [x] Make the safety soft and hard limits much more permissive
- [x] Make sure that the yellow and red zones match the limit settings
- [x] Make the green zone bigger (10m)
- [x] Add safety limits to the heading; start with +/- 45 degrees, but allow for this to be configured in the plugin settings
- [x] Only praise the student on pedal control when the absolute yaw rate remains below a reasonable value. Currently the student gets praise just based on the heading remaining within a range, even if the helicopter is wildly oscillating around the target heading.

## Controls, Input & Commands
- [x] Give a little bit more generous hand-over zones (4% instead of 3%)
- [ ] Allow the student to give back controls; define a custom command for this, so it can be mapped to a joystick button
- [x] Add controls for setting the hover location and to move it around
- [x] Add controls for changing the target heading
- [ ] Define a new custom command for giving back control to the instructor
- [x] Make it clear whether the collective and pedals are synched between the VFI and the user. Currently only the collective changes color when the synch is good
- [ ] Only show inputs on the HUD that actually have to be synched
- [ ] On the HUD, make the size of the collective synch target circle and ball both match the range of accepted inputs. (Maybe add two concentric circles as "target")

## OSD & Visuals
- [x] Draw the cyclic status graphically on the OSD with graphics instead of text

## Voice, Audio & Progression
- [x] Add voice cues
- [ ] Add intro text and voice
- [ ] Automatically advance to next phase if the student can hold a stable hover for 30 seconds

## Configuration & Performance Evaluation
- [ ] Add config settings JSON file
- [x] Add performance evaluation: specify three envelopes using a 60-second moving window (with associated voice cues):
  - **Unstable**: Student cannot maintain the target.
  - **Good**: Student does not get close to the safety limits.
  - **Excellent**: Student stays well within limits and close to the target.

## User Experience
- [x] Start with the control panel visible
- [x] Package the PID parameters for the R-22 helicopter with the plugin
