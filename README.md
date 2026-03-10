# MultiMediaKnob 🚀: Autonomous HID Control Dial

A highly configurable, autonomous rotary encoder (**MultiMediaKnob**) built with a Raspberry Pi Pico (CircuitPython) and a sleek PC configurator app (**KnobStudio**) built with Python/CustomTkinter.

This project has evolved from a simple media controller into a powerful control station, now featuring **Shift Layers**, **Multi-Click Actions** (double/triple), **Mouse Control**, and a full **Sequential Macro Engine**.

![Wiring Diagram](images/pico_and_rotary_encoder.png)

![UI](images/UI.png)

*The modern, dark-themed KnobStudio app.*

---

## 🚀 Features

* **⚡ Autonomous HID:** The knob works as a standalone USB device (Keyboard, Media Controller, **and Mouse**) without any PC software running in the background.
* **💨 Zero Lag:** By acting as a native HID, all actions (volume, scroll) are instant, with no lag or buffering.
* **🚦 3 Profiles + Shift Layers:** Switch between three independent profiles. Each profile now has **two "layers"**, giving you 6 distinct rotation actions.
* **🐧 Native Linux Support (NEW):** A dedicated Linux version of KnobStudio with smart `CIRCUITPY` drive detection (handling KDE/Fedora automounts) and automated `dialout` permission checks.
* **🛡️ Bulletproof Reliability (v7.1 Refactor):** Hardware debouncing is now backed by a robust software debounce state machine. Time tracking has been upgraded to nanosecond precision (`time.monotonic_ns()`), and file saving now uses strict `os.fsync` to guarantee profile writes.
* **🎨 Deep Customization:** Configure actions for **8 different gestures** per profile:
    * Rotate Clockwise (CW)
    * Rotate Counter-Clockwise (CCW)
    * Short Click
    *  Double Click
    *  Triple Click
    * Long Press
    * Hold + CW (Shifted)
    * Hold + CCW (Shifted)
* **⌨️ Advanced Sequential Macro Engine:** Go beyond simple shortcuts. The new script-based editor allows you to create **multi-step sequences** for complex automation. Assign a sequence of actions like `press CTRL`, `wait 100ms`, `tap C`, `release_all` to any of the 8 available gestures.
* **🖱️ Native Mouse Control:** Use the knob for vertical/horizontal scroll, pointer movement, or clicks (left, right, middle).
* **🎚️ Per-Action Sensitivity:** Set different "steps per click" (1x-10x) independently for **Volume**, **Scroll**, and **Mouse** movements.
* **🖥️ Modern UI (KnobStudio):** A sleek, dark-mode app (`customtkinter`) to easily set up all your profiles, sensitivities, and macros.
* **💾 Simple "Save & Reboot":** The app saves your settings directly to a `profiles.json` file on the Pico's `CIRCUITPY` drive and then sends a serial command to reboot the Pico, loading the new settings instantly.
* **🔄 Persistent On-Device Profile Saving:** When you switch profiles *using the knob* (e.g., with a 'Next Profile' action), your choice is automatically saved to the Pico's flash. The knob will now boot into the last-used profile.

---

## 🛣️ Future Roadmap

This project is now in a mature stage. The architecture was designed to be modular, allowing for several more exciting features to be added in the future:

* **🖥️ App-Specific Profiles:** A new PC-side agent that detects the active application (e.g., Photoshop, VS Code, Spotify) and automatically signals the Pico to switch to a corresponding profile.
* **📱 Wireless Bluetooth Version:** Developing a hardware revision (likely with a Pico W) to create a fully wireless, battery-powered version of the knob using Bluetooth LE (HID).
* **🍏 macOS Support:** Porting the `KnobStudio` configurator app to support macOS drive routing natively.
* **🌈 RGB LED Profile Indicator:** The next planned hardware addition is an RGB LED (like a NeoPixel). This will provide instant visual feedback on the active profile by changing color (e.g., Profile 1 = Red, Profile 2 = Green).
* **📺 OLED Display Integration:** An I2C OLED screen (like an SSD1306) can be added to display dynamic information, such as custom profile names ("Volume", "Editing", "Gaming").
* **👋 Per-Action Haptic Feedback (Advanced):** Integrating a small vibration motor to provide tactile feedback on action execution or profile switching.

---

## 🛠️ How It Works

This project uses a "Configurator" model, which combines the speed of an autonomous HID with the visual flexibility of a GUI.

### The Pico (The "Muscle"): Runs `code.py`

1.  On boot, it reads a `profiles.json` file from its own storage, validating it strictly against type errors.
2.  It initializes itself as a USB Keyboard, Media Controller, & Mouse.
3.  When you turn or press the knob, a **software-debounced state machine** differentiates between a single click, double click, triple click, long press, and a "shifted" (hold+rotate) action.
4.  It sends the corresponding **direct HID command** or executes a **multi-step macro sequence** to the PC.
5.  It passively listens on its Data Serial Port for soft-reboot interrupts from the PC.

### The PC App (KnobStudio): Runs `KnobStudio.py`

1.  This app **does not** need to run in the background. Open it only to change settings.
2.  When you click "Save & Reboot Pico":
    * It safely finds the Pico's `CIRCUITPY` USB drive (using `psutil` and fallback probes).
    * It writes your new settings to `profiles.json` and flushes the buffer to prevent corruption.
    * It finds the Pico's Serial Port (using `pyserial`).
    * It sends a soft-reboot serial interrupt (`\x03` + `\x04`).
3.  The Pico receives the command, soft-reboots, reads the *new* `profiles.json`, and is ready instantly.

---

## 🔌 Hardware & Wiring

(This remains unchanged from the original version)

* Raspberry Pi Pico
* Rotary Encoder Module (KY-040 or similar, 5-pin)
* Breadboard and jumper wires

### Wiring Diagram

* **Encoder `GND`** -> Pico `GND` (e.g., Pin 38)
* **Encoder `+` (VCC)** -> Pico `3.3V(OUT)` (Pin 36)
* **Encoder `SW` (Switch)** -> Pico **`GP15`** (Pin 20)
* **Encoder `DT` (Data)** -> Pico **`GP14`** (Pin 19)
* **Encoder `CLK` (Clock)** -> Pico **`GP13`** (Pin 17)

---

## ⚙️ Requirements

### Pico (Hardware)

1.  **CircuitPython:** Ensure you have the latest version of [CircuitPython for your Pico](https://circuitpython.org/board/raspberry_pi_pico/) installed.
2.  **CircuitPython Libraries:** Copy the following library from the [CircuitPython Library Bundle](https://circuitpython.org/libraries) to the `lib` folder on your `CIRCUITPY` drive:
    * `adafruit_hid`

### PC (KnobStudio App)

The Configurator app is written in Python 3. 

**For Windows (`KnobStudio.py`):**
```bash
pip install customtkinter psutil pyserial pywin32
```

**For Linux (`KnobStudio_Linux.py`):**
```bash
pip install customtkinter psutil pyserial
```
*Note for Linux users: Your user must be part of the `dialout` group to send the serial reboot command to the Pico. KnobStudio will warn you if you aren't. To fix it, run `sudo usermod -aG dialout $USER` and log out/in.*
