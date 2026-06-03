# Helicopter Virtual Flight Instructor (VFI)

A virtual flight instructor plugin for **X-Plane 12** designed to teach student pilots how to master hovering a helicopter. Written in Python, it runs under the **XPPython3** runtime environment and provides automated hands-on curriculum training, real-time coaching cues, performance scoring, and Vulkan/Metal-native 3D overlay visualization.

![Helicopter Virtual Flight Instructor External View](v2/docs/screenshots/Screenshot%20-%20Pedals%20only%20-%20external%20view.png)

---

## 🚀 Key Features

* **Cascaded PID Autopilot:** A multi-axis controller (roll, pitch, yaw, collective) capable of holding a precise 3D hover target.
* **6-Phase Curriculum:** Progressive training stages that incrementally transfer control axes from the VFI autopilot to the student pilot.
* **Real-time Performance Metrics:**
  * **Precision Scoring:** Horizontal drift, ground drift speed, altitude error, climb/sink rate, and heading alignment.
  * **Overcorrection Index (OCI):** Tracks pilot over-controlling via an Exponential Moving Average (EMA) of hardware input velocities.
  * **Proficiency Envelope:** Automatically grades the student (`Excellent`, `Good`, `Unstable`) based on a 20-second sliding window.
* **Audio & Visual Coaching Cues:** Audio prompts (voiced training tips and warnings), 3D hover target circles, and a 2D altitude reference bar.

---

## 📸 Screenshots

### 3D Visual Guidance & Control Panel
| 3D Safety Zones & Guidance Rings | ImGui Instructor Control Panel |
| :---: | :---: |
| ![3D Safety Zones](v2/docs/screenshots/Screenshot%20-%20Safety%20zones.png) | ![Control Panel](v2/docs/screenshots/Screenshot%20-%20Control%20panel.png) |

### Curriculum Training Phases
| Phase 1: Pedals Only | Phase 2: Collective Only |
| :---: | :---: |
| ![Pedals Only](v2/docs/screenshots/Screenshot%20-%20Pedals%20only.png) | ![Collective Only](v2/docs/screenshots/Screenshot%20-%20Collective%20only.png) |

| Phase 4: Cyclic Only | Phase 6: All Controls |
| :---: | :---: |
| ![Cyclic Only](v2/docs/screenshots/Screenshot%20-%20Cyclic%20only.png) | ![All Controls](v2/docs/screenshots/Screenshot%20-%20All%20three%20controls.png) |

---

## ⚙️ Installation & Usage

For detailed instructions on installing and using the plugin, see the [v2 README](v2/README.md).

---

## 🧪 Development & Testing

For guidelines on coding conventions, style, and running the tests, see the [v2 Development Guide](v2/docs/developer_documentation.md).
