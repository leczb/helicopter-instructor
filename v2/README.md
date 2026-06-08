# Virtual Helicopter Flight Instructor

An intelligent virtual flight instructor (VFI) training aid plugin for X-Plane, optimized for learning how to hover a helicopter using standard non-force-feedback flight controls.

---

## Overview

Mastering helicopter hovering is notoriously challenging due to highly coupled aerodynamics and the continuous micro-corrections required. This plugin acts as an interactive instructor, implementing a modular "building-block" progression curriculum, soft and hard safety interventions, and seamless control synchronization. It keeps a stable hover while the student practices specific control aspects in isolation, and then gradually hands over more and more control to the student.

### Key Features

* **Modular Handoff Curriculum**: Uncouples flight controls and hands them over to the student in progressive stages:
  1. *Pedals Only*: VFI controls the collective and the cyclic; student learns heading control using the anti-torque pedals.
  2. *Collective Only*: VFI controls the cyclic and the pedals; student learns altitude control using the collective.
  3. *Collective & Pedals*: VFI controls the cyclic; student controls the collective and pedals. Gets the student used to countering torque changes caused by collective changes.
  4. *Cyclic Only*: VFI controls the pedals and the collective; student learns to control attitude and translation using the cyclic.
  5. *Cyclic & Pedals*: VFI controls the collective; student controls the cyclic and pedals. Gets the student used to countering drift caused by the tail rotor.
  6. *Full Integration (All Controls)*: Student receives total control authority.
* **Anti-Jerk Control Synchronization**: Prevents violent "jumps" during handoffs on non-force-feedback physical controllers by requiring the student to match their physical stick/pedal inputs with the VFI's active virtual control positions within a small matching dead-zone before control is transferred.
* **Emergency Safety Takeover**:
  * **Hard Emergency Override**: Automatically severs control authority, plays an audio takeover cue (*"I have control"*), and recovers the helicopter to a stable hover if any critical safety threshold (pitch, roll, yaw rate, sink rate, or drift) is breached or the helicopter drifts too far from the initial hover position.
* **3D Proximity Boundaries**: The hover safety limits are rendered as floating rings around the hover target point (green, orange, and red; orange/green for target proximity, red for the hard override limits).
* **Heads-Up Display (HUD)**: Includes a draggable HUD showing control synchronization crosshairs and status information.
* **Aural Voice Cues**: High-quality, authoritative voice cues that guide the student through handoffs, safety warnings, and performance feedback.

---

## Installation Instructions

This plugin is designed to run in X-Plane 12 via the **X-PPython3** (Python 3 Interface) execution environment.

### Prerequisites

1. **XPPython3 Plugin**:
   - Download the latest release of the **X-PPython3** plugin from the [XPPython3 Website](https://xppython3.readthedocs.io/).
   - Install it by extracting the folder into your X-Plane 12 directory: `<X-Plane 12>/Resources/plugins/`.

### Installing the Plugin

1. Navigate to the X-Plane 12 plugins folder:
   ```
   <X-Plane 12>/Resources/plugins/
   ```
2. Open or create the `PythonPlugins` directory:
   ```
   <X-Plane 12>/Resources/plugins/PythonPlugins/
   ```
3. Copy the plugin files into the `PythonPlugins` folder:
   - **From the release ZIP**: copy the contents of the `PythonPlugins/` folder inside the archive.
   - **From the source repository**: copy the contents of the `v2/plugin/` directory.

   The final file structure inside `PythonPlugins` must look like this:
   ```
    <X-Plane 12>/Resources/plugins/PythonPlugins/
    ├── PI_helicopter_instructor.py
    └── helicopter_instructor/
        ├── __init__.py
        ├── audio.py
        ├── config.py
        ├── envelope_limits.py
        ├── graphics.py
        ├── hud.py
        ├── metrics.py
        ├── ui.py
        ├── virtual_instructor.py
        ├── assets/
        │   ├── Correct the drift.wav
        │   ├── Get ready to take control.wav
        │   ├── Great pedals.wav
        │   ├── I have control.wav
        │   ├── Nice recovery.wav
        │   ├── Perfect.wav
        │   ├── Relax cyclic.wav
        │   ├── Smooth collective.wav
        │   ├── Smooth cyclic.wav
        │   ├── Steady pedals.wav
        │   ├── We are too high.wav
        │   ├── We are too low.wav
        │   ├── You have all controls.wav
        │   ├── You have the collective and the pedals.wav
        │   ├── You have the collective.wav
        │   ├── You have the cyclic and the pedals.wav
        │   ├── You have the cyclic.wav
        │   └── You have the pedals.wav
        └── autopilot/
            ├── __init__.py
            ├── helicopter_control.py
            └── autopilot_gains_Robinson_R22_Beta_II.json
   ```

---

## How to Use

1. Launch **X-Plane 12** and load a helicopter (e.g., Robinson R44 or Bell 206) at an airport or helipad.
2. Ensure your physical joystick, cyclic, collective, and pedals are calibrated inside X-Plane.
3. Configure your physical collective axis as "Flaps" (not "Collective").
4. In the X-Plane menu bar, navigate to **Plugins** -> **Helicopter Instructor** -> **Toggle Control Panel** to open the instructor window.
5. Check **MASTER INSTRUCTOR ENGAGE** to engage the VFI. The instructor will immediately take off and stabilize the helicopter at a 6 meter hovering height above the ground.
6. Select a lesson phase in the *Hover Training Curriculum* section. A control hand-off sequence will automatically trigger once the initial introduction audio finishes playing after engagement. You can also manually trigger it at any time by clicking **Trigger lesson Handoff**. Match your physical inputs with the help of the HUD. Once you have matched the controls for a few seconds, the instructor gives you control, confirming the hand-off with a voice cue.
