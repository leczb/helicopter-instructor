# Helicopter Virtual Flight Instructor (VFI)

A virtual flight instructor plugin for **X-Plane 12** designed to teach student pilots how to master hovering a helicopter. Written in Python, it runs under the **XPPython3** runtime environment and provides automated hands-on curriculum training, real-time coaching cues, performance scoring, and Vulkan/Metal-native 3D overlay visualization.

---

## 🚀 Key Features

* **Cascaded PID Autopilot:** A multi-axis controller (roll, pitch, yaw, collective) capable of holding a precise 3D hover target.
* **6-Phase Curriculum:** Progressive training stages that incrementally transfer control axes from the VFI autopilot to the student pilot.
* **Real-time Performance Metrics:**
  * **Precision Scoring:** Horizontal drift, ground drift speed, altitude error, climb/sink rate, and heading alignment.
  * **Overcorrection Index (OCI):** Tracks pilot over-controlling via an Exponential Moving Average (EMA) of hardware input velocities.
  * **Proficiency Envelope:** Automatically grades the student (`Excellent`, `Good`, `Unstable`) based on a 60-second sliding window.
* **Audio & Visual Coaching Cues:** Audio prompts (voiced training tips and warnings), 3D hover target circles, and a 2D altitude reference bar.

---

## ⚙️ Installation & Usage

For detailed instructions on installing and using the plugin, see the [v2 README](v2/README.md).

---

## 🧪 Development & Testing

For guidelines on coding conventions, style, and running the tests, see the [v2 Development Guide](v2/docs/developer_documentation.md).
