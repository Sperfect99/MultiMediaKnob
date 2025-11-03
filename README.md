# 🚀 MultiMediaKnob : Autonomous HID Control Dial

A highly configurable, autonomous rotary encoder (**MultiMediaKnob**) built with a Raspberry Pi Pico (CircuitPython) and a sleek PC configurator app (**KnobStudio**) built with Python/CustomTkinter. This project serves as the robust foundation for an expandable media control station.

![Wiring Diagram](images/pico_and_rotary_encoder.png)


*The modern, dark-themed KnobStudio app.*

---

## 🚀 Features

* **⚡ Autonomous HID:** The knob works as a standalone USB device (Keyboard & Media Controller) without any PC software running in the background.
* **💨 Zero Lag:** By acting as a native HID, all actions (volume, scroll) are instant, with no lag or buffering.
* **🚦 3 Configurable Profiles:** Switch between three independent profiles using a custom action (like a long press).
* **🎨 Deep Customization:** Configure actions for:
    * Rotate Clockwise (CW)
    * Rotate Counter-Clockwise (CCW)
    * Short Click
    * Long Press
* **🎚️ Per-Action Sensitivity:** Set different "steps per click" (1x-10x) for Volume and Scroll independently.
* **🖥️ Modern UI (KnobStudio):** A sleek, dark-mode app built with `customtkinter` to easily set up all your profiles and sensitivities.
* **💾 Simple "Save & Reboot":** The app saves your settings directly to a `profiles.json` file on the Pico's `CIRCUITPY` drive and then sends a serial command to reboot the Pico, loading the new settings instantly.

---

## 🛣️ Future Roadmap

This project is currently in its initial, stable stage. The architecture was designed to be modular, allowing for several exciting features to be added in the future:

* **🌈 RGB LED Profile Indicator:** The next planned hardware addition is an RGB LED (like a Common Anode module or a NeoPixel). This will provide instant visual feedback on the active profile by changing color (e.g., Profile 1 = Red, Profile 2 = Green, Profile 3 = Blue).
* **📺 OLED Display Integration:** An I2C OLED screen (like an SSD1306) can be added to display dynamic information. This will allow the Configurator to save custom profile names (e.g., "Volume", "Editing", "Gaming") which are then displayed on the screen as you switch.
* **⌨️ Advanced Macro Editor:** Expanding the KnobStudio app to include a full macro editor, allowing users to assign complex, multi-key sequences (e.g., `Ctrl+Alt+Shift+P`) to any action.
* **👋 Per-Action Haptic Feedback (Advanced):** Integrating a small vibration motor to provide tactile feedback on action execution or profile switching.

---

## 🛠️ How It Works

This project uses a "Configurator" model, which combines the speed of HID with the flexibility of a GUI.

### The Pico (The "Muscle"): Runs `code.py`

1.  On boot, it reads a `profiles.json` file from its own storage.
2.  It initializes itself as a USB Keyboard & Media Controller (HID).
3.  When you turn or press the knob, it reads the desired action from the loaded settings and sends the corresponding **direct HID command** to the PC (e.g., `Volume Up`).
4.  It also listens on its Data Serial Port for one specific command: `"REBOOT"`.

### The PC App (KnobStudio): Runs `KnobStudio.py`

1.  This app **does not** need to run in the background.
2.  When you click "Save & Reboot Pico":
    * It finds the Pico's `CIRCUITPY` USB drive (using `psutil`).
    * It writes your new settings (profiles, sensitivity) to the `profiles.json` file on the drive.
    * It finds the Pico's Data Serial Port (using `pyserial`).
    * It sends the text command `"REBOOT"` over the serial port.
3.  The Pico receives the command, reboots, reads the *new* `profiles.json`, and is ready with the new settings.

---

## 🔌 Hardware & Wiring

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

1.  **Raspberry Pi Pico:** A Pico or Pico W.
2.  **CircuitPython:** The code is written for CircuitPython. Ensure you have the latest version of [CircuitPython for your Pico](https://circuitpython.org/board/raspberry_pi_pico/) installed.
3.  **CircuitPython Libraries:** After installing CircuitPython, copy the following library from the [CircuitPython Library Bundle](https://circuitpython.org/libraries) to the `lib` folder on your `CIRCUITPY` drive:
    * `adafruit_hid` (https://circuitpython.org/libraries)

### PC (KnobStudio App)

The Configurator app (`KnobStudio.py`) is written in Python 3 and requires the following libraries. You can install them all by running:

```bash
pip install customtkinter psutil pyserial pywin32
