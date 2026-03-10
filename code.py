# File: code.py
# Version: 7.1 Refactored
# Author: Stylianos Tanellari
# Board: Raspberry Pi Pico (CircuitPython)

import board
import digitalio
import rotaryio
import time
import json
import usb_hid
import usb_cdc
import microcontroller
import storage
import traceback
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.mouse import Mouse

print("--- MultiMediaKnob v7.1 (refactored)---")


# Config & Pin Constants

CONFIG_FILE = "/profiles.json"

ENCODER_CLK = board.GP13
ENCODER_DT  = board.GP14
ENCODER_SW  = board.GP15

# A brief startup delay lets the host finish POST before the Pico enumerates as a composite HID device, which can otherwise cause BIOS/UEFI hangs.

print("[SYSTEM] Waiting 5 s for host POST...")
time.sleep(5.0)
print("[SYSTEM] Initializing HID...")


# HID Init
try:
    kbd   = Keyboard(usb_hid.devices)
    cc    = ConsumerControl(usb_hid.devices)
    mouse = Mouse(usb_hid.devices)
    print("[HID] Keyboard, ConsumerControl, and Mouse ready.")
except Exception as e:
    print(f"[HID] FATAL: {e}")
    while True:
        time.sleep(1)


# Hardware Init

encoder   = rotaryio.IncrementalEncoder(ENCODER_CLK, ENCODER_DT, divisor=4)
button_sw = digitalio.DigitalInOut(ENCODER_SW)
button_sw.direction = digitalio.Direction.INPUT
button_sw.pull      = digitalio.Pull.UP


# Global State

current_profile_index = 0
num_profiles          = 3
profiles_data         = {}
sensitivity_volume    = 2
sensitivity_scroll    = 1
sensitivity_mouse     = 4


# Profile Persistence

def save_current_profile_index(index):
    global profiles_data
    if "current_profile" not in profiles_data:
        print("[FS] 'current_profile' key missing — cannot persist.")
        return
    profiles_data["current_profile"] = index + 1
    try:
        storage.remount("/", readonly=False)
        with open(CONFIG_FILE, "w") as f:
            json.dump(profiles_data, f, indent=2)
        storage.remount("/", readonly=True)
        print(f"[FS] Profile {index + 1} saved as default.")
    except Exception as e:
        print(f"[FS] Save error: {e}")
        try:
            storage.remount("/", readonly=True)
        except Exception:
            pass


def switch_profile(target_index):
    global current_profile_index
    if 0 <= target_index < num_profiles:
        current_profile_index = target_index
        print(f"[SYSTEM] Profile -> {current_profile_index + 1}")
        save_current_profile_index(current_profile_index)
    else:
        print(f"[SYSTEM] Invalid profile index: {target_index}")


def next_profile():
    switch_profile((current_profile_index + 1) % num_profiles)


# Mouse Helpers

def _mouse_move_x_pos():   mouse.move(x=sensitivity_mouse)
def _mouse_move_x_neg():   mouse.move(x=-sensitivity_mouse)
def _mouse_move_y_pos():   mouse.move(y=sensitivity_mouse)
def _mouse_move_y_neg():   mouse.move(y=-sensitivity_mouse)
def _mouse_scroll_v_pos(): mouse.move(wheel=1)
def _mouse_scroll_v_neg(): mouse.move(wheel=-1)
def _mouse_scroll_h_pos(): mouse.move(wheel=1)
def _mouse_scroll_h_neg(): mouse.move(wheel=-1)


# Simple Actions Map

SIMPLE_ACTIONS_MAP = {
    "nothing":              lambda: None,
    "volume_up":            lambda: cc.send(ConsumerControlCode.VOLUME_INCREMENT),
    "volume_down":          lambda: cc.send(ConsumerControlCode.VOLUME_DECREMENT),
    "mute":                 lambda: cc.send(ConsumerControlCode.MUTE),
    "play_pause":           lambda: cc.send(ConsumerControlCode.PLAY_PAUSE),
    "next_track":           lambda: cc.send(ConsumerControlCode.SCAN_NEXT_TRACK),
    "prev_track":           lambda: cc.send(ConsumerControlCode.SCAN_PREVIOUS_TRACK),
    "scroll_up":            lambda: kbd.send(Keycode.UP_ARROW),
    "scroll_down":          lambda: kbd.send(Keycode.DOWN_ARROW),
    "undo":                 lambda: kbd.send(Keycode.LEFT_CONTROL, Keycode.Z),
    "redo":                 lambda: kbd.send(Keycode.LEFT_CONTROL, Keycode.Y),
    "mouse_move_x_pos":     _mouse_move_x_pos,
    "mouse_move_x_neg":     _mouse_move_x_neg,
    "mouse_move_y_pos":     _mouse_move_y_pos,
    "mouse_move_y_neg":     _mouse_move_y_neg,
    "mouse_scroll_v_pos":   _mouse_scroll_v_pos,
    "mouse_scroll_v_neg":   _mouse_scroll_v_neg,
    "mouse_scroll_h_pos":   _mouse_scroll_h_pos,
    "mouse_scroll_h_neg":   _mouse_scroll_h_neg,
    "mouse_click_left":     lambda: mouse.click(Mouse.LEFT_BUTTON),
    "mouse_click_right":    lambda: mouse.click(Mouse.RIGHT_BUTTON),
    "mouse_click_middle":   lambda: mouse.click(Mouse.MIDDLE_BUTTON),
    "next_profile":         next_profile,
    "switch_profile_1":     lambda: switch_profile(0),
    "switch_profile_2":     lambda: switch_profile(1),
    "switch_profile_3":     lambda: switch_profile(2),
}


# Key Name -> Keycode Map

KEYNAME_TO_KEYCODE = {
    # Modifiers
    "LEFT_CONTROL":  Keycode.LEFT_CONTROL,  "CONTROL": Keycode.LEFT_CONTROL,  "CTRL": Keycode.LEFT_CONTROL,
    "LEFT_SHIFT":    Keycode.LEFT_SHIFT,    "SHIFT":   Keycode.LEFT_SHIFT,
    "LEFT_ALT":      Keycode.LEFT_ALT,      "ALT":     Keycode.LEFT_ALT,
    "LEFT_GUI":      Keycode.LEFT_GUI,      "WIN":     Keycode.LEFT_GUI,      "CMD": Keycode.LEFT_GUI, "COMMAND": Keycode.LEFT_GUI,
    "WIN/CMD":       Keycode.LEFT_GUI,      "WIN/COMMAND": Keycode.LEFT_GUI,
    "RIGHT_CONTROL": Keycode.RIGHT_CONTROL, "RCTRL":   Keycode.RIGHT_CONTROL,
    "RIGHT_SHIFT":   Keycode.RIGHT_SHIFT,   "RSHIFT":  Keycode.RIGHT_SHIFT,
    "RIGHT_ALT":     Keycode.RIGHT_ALT,     "RALT":    Keycode.RIGHT_ALT,     "ALT_GR": Keycode.RIGHT_ALT,
    "RIGHT_GUI":     Keycode.RIGHT_GUI,     "RWIN":    Keycode.RIGHT_GUI,     "RCMD":   Keycode.RIGHT_GUI,
    # Letters
    "A": Keycode.A, "B": Keycode.B, "C": Keycode.C, "D": Keycode.D, "E": Keycode.E,
    "F": Keycode.F, "G": Keycode.G, "H": Keycode.H, "I": Keycode.I, "J": Keycode.J,
    "K": Keycode.K, "L": Keycode.L, "M": Keycode.M, "N": Keycode.N, "O": Keycode.O,
    "P": Keycode.P, "Q": Keycode.Q, "R": Keycode.R, "S": Keycode.S, "T": Keycode.T,
    "U": Keycode.U, "V": Keycode.V, "W": Keycode.W, "X": Keycode.X, "Y": Keycode.Y, "Z": Keycode.Z,
    # Numbers
    "1": Keycode.ONE,   "2": Keycode.TWO,   "3": Keycode.THREE, "4": Keycode.FOUR,  "5": Keycode.FIVE,
    "6": Keycode.SIX,   "7": Keycode.SEVEN, "8": Keycode.EIGHT, "9": Keycode.NINE,  "0": Keycode.ZERO,
    # Function Keys
    "F1":  Keycode.F1,  "F2":  Keycode.F2,  "F3":  Keycode.F3,  "F4":  Keycode.F4,
    "F5":  Keycode.F5,  "F6":  Keycode.F6,  "F7":  Keycode.F7,  "F8":  Keycode.F8,
    "F9":  Keycode.F9,  "F10": Keycode.F10, "F11": Keycode.F11, "F12": Keycode.F12,
    # Common
    "ENTER":     Keycode.ENTER,     "RETURN":   Keycode.ENTER,
    "ESCAPE":    Keycode.ESCAPE,    "ESC":      Keycode.ESCAPE,
    "BACKSPACE": Keycode.BACKSPACE,
    "TAB":       Keycode.TAB,
    "SPACE":     Keycode.SPACE,     "SPACEBAR": Keycode.SPACE,
    "DELETE":    Keycode.DELETE,    "DEL":      Keycode.DELETE,
    # Navigation
    "UP_ARROW":    Keycode.UP_ARROW,    "UP":    Keycode.UP_ARROW,
    "DOWN_ARROW":  Keycode.DOWN_ARROW,  "DOWN":  Keycode.DOWN_ARROW,
    "LEFT_ARROW":  Keycode.LEFT_ARROW,  "LEFT":  Keycode.LEFT_ARROW,
    "RIGHT_ARROW": Keycode.RIGHT_ARROW, "RIGHT": Keycode.RIGHT_ARROW,
    "PAGE_UP":   Keycode.PAGE_UP,   "PGUP": Keycode.PAGE_UP,
    "PAGE_DOWN": Keycode.PAGE_DOWN, "PGDN": Keycode.PAGE_DOWN,
    "HOME":   Keycode.HOME,
    "END":    Keycode.END,
    "INSERT": Keycode.INSERT,
}


_NOOP_ACTION = {"type": "simple", "action": "nothing"}


# Default Profile Config

_ALL_GESTURE_KEYS = (
    "cw", "ccw", "click", "double_click", "triple_click",
    "long_press", "cw_shifted", "ccw_shifted",
)

def _noop():
    return {"type": "simple", "action": "nothing"}

def _default_profile_base():
    return {k: _noop() for k in _ALL_GESTURE_KEYS}


def _make_default_profiles():
    p1 = _default_profile_base()
    p1["cw"]         = {"type": "simple", "action": "volume_up"}
    p1["ccw"]        = {"type": "simple", "action": "volume_down"}
    p1["click"]      = {"type": "simple", "action": "mute"}
    p1["long_press"] = {"type": "simple", "action": "next_profile"}

    p2 = _default_profile_base()
    p2["cw"]    = {"type": "simple", "action": "scroll_up"}
    p2["ccw"]   = {"type": "simple", "action": "scroll_down"}
    p2["click"] = {"type": "simple", "action": "play_pause"}

    p3 = _default_profile_base()
    p3["cw"]          = {"type": "simple", "action": "mouse_scroll_v_pos"}
    p3["ccw"]         = {"type": "simple", "action": "mouse_scroll_v_neg"}
    p3["click"]       = {"type": "simple", "action": "mouse_click_middle"}
    p3["cw_shifted"]  = {"type": "simple", "action": "mouse_scroll_h_pos"}
    p3["ccw_shifted"] = {"type": "simple", "action": "mouse_scroll_h_neg"}

    return [p1, p2, p3]

default_profiles = {
    "current_profile":    1,
    "sensitivity_volume": 2,
    "sensitivity_scroll": 1,
    "sensitivity_mouse":  4,
    "profiles": _make_default_profiles(),
}


# Config Validation & Loading

def _safe_int(val, default):
    """
    Type-safe integer coercion for values read from JSON.
    JSON is untyped at the schema level — a human or tool can write
    "sensitivity_volume": "5" (string) or null, producing a str/None in
    Python. Without this guard, the chained comparisons on lines like
      `if not 2 <= sensitivity_volume <= 10`
    raise TypeError at module level (outside any try/except), permanently
    halting the Pico firmware at startup. int("5")=5, int(5.0)=5, anything
    that can't be coerced falls back to `default`.
    """
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def is_valid_config(config):
    try:
        required_top = ("current_profile", "sensitivity_volume",
                        "sensitivity_scroll", "sensitivity_mouse", "profiles")
        if not all(k in config for k in required_top):
            return False

        for key in ("current_profile", "sensitivity_volume",
                    "sensitivity_scroll", "sensitivity_mouse"):
            raw = config[key]
            if raw is None or isinstance(raw, (list, dict, bool)):
                return False
            try:
                int(raw)
            except (TypeError, ValueError):
                return False
        if not (isinstance(config["profiles"], list) and len(config["profiles"]) >= 3):
            return False
        for profile in config["profiles"]:
            for key in _ALL_GESTURE_KEYS:
                action_obj = profile.get(key)
                if not (isinstance(action_obj, dict) and "type" in action_obj):
                    return False
        return True
    except Exception as e:
        print(f"[VALIDATE] {e}")
        return False


def _upgrade_config(raw):

    base = json.loads(json.dumps(default_profiles))
    base.update(raw)
    if len(base.get("profiles", [])) < 3:
        base["profiles"] = json.loads(json.dumps(default_profiles["profiles"]))
    for i in range(3):
        for key in _ALL_GESTURE_KEYS:
            base["profiles"][i].setdefault(key, {"type": "simple", "action": "nothing"})
    return base


try:
    with open(CONFIG_FILE, "r") as f:
        _raw = json.load(f)
    if is_valid_config(_raw):
        profiles_data = _raw
        print(f"[FS] Loaded config from {CONFIG_FILE}")
    else:
        print(f"[FS] Config structure outdated — upgrading.")
        profiles_data = _upgrade_config(_raw)
except OSError:
    print(f"[FS] {CONFIG_FILE} not found — using defaults.")
    profiles_data = json.loads(json.dumps(default_profiles))
except Exception as e:
    print(f"[FS] Load error: {e} — using defaults.")
    traceback.print_exception(type(e), e, e.__traceback__)
    profiles_data = json.loads(json.dumps(default_profiles))

if not profiles_data:
    print("[FS] CRITICAL: falling back to defaults.")
    profiles_data = json.loads(json.dumps(default_profiles))


current_profile_index = _safe_int(profiles_data.get("current_profile", 1), 1) - 1
sensitivity_volume    = _safe_int(profiles_data.get("sensitivity_volume", 2), 2)
sensitivity_scroll    = _safe_int(profiles_data.get("sensitivity_scroll", 1), 1)
sensitivity_mouse     = _safe_int(profiles_data.get("sensitivity_mouse",  4), 4)
num_profiles          = len(profiles_data.get("profiles", []))

if not 0 <= current_profile_index < num_profiles:
    print("[CONFIG] Profile index out of range — resetting to 0.")
    current_profile_index = 0
    profiles_data["current_profile"] = 1


if not 2 <= sensitivity_volume <= 10: sensitivity_volume = 2
if not 1 <= sensitivity_scroll <= 10: sensitivity_scroll = 1
if not 1 <= sensitivity_mouse <= 10:  sensitivity_mouse  = 4


# Loop State Variables

last_position        = encoder.position
# States: 0=Released  1=Pressed/awaiting  2=LongPress/awaiting release  3=Shifted
button_state         = 0
button_press_time    = 0            # integer nanoseconds (time.monotonic_ns())
LONG_PRESS_NS        = 800000000    # 800 ms in nanoseconds
click_count          = 0
last_release_time    = 0
MULTI_CLICK_TIMEOUT_NS = 300000000    # 300 ms in nanoseconds


# Software Debounce State

DEBOUNCE_COUNT        = 2
_btn_stable_count     = 0
_btn_last_raw         = False   # last raw reading (pre-debounce)
button_debounced      = False   # debounced state exposed to state machine


# HID Action Executor

def execute_hid_action(action_key):

    try:
        profile     = profiles_data["profiles"][current_profile_index]
        action_obj  = profile.get(action_key, _NOOP_ACTION)
        action_type = action_obj.get("type", "simple")

        if action_type == "simple":
            action_name = action_obj.get("action", "nothing")
            action_func = SIMPLE_ACTIONS_MAP.get(action_name, SIMPLE_ACTIONS_MAP["nothing"])

            multiplier     = 1
            delay_per_step = 0.005

            if action_key in ("cw", "ccw", "cw_shifted", "ccw_shifted"):
                if action_name in ("volume_up", "volume_down"):
                    multiplier     = max(1, round(sensitivity_volume / 2))
                    delay_per_step = 0.015
                elif action_name in ("scroll_up", "scroll_down"):
                    multiplier     = sensitivity_scroll
                    delay_per_step = 0.005

            if action_name.startswith("switch_profile_") or action_name == "next_profile":
                action_func()
            elif multiplier == 1:
                action_func()
            else:
                for _ in range(multiplier):
                    action_func()
                    time.sleep(delay_per_step)

        elif action_type == "macro":
            keys_to_press = action_obj.get("keys", [])
            keycodes = [KEYNAME_TO_KEYCODE[k] for k in keys_to_press if k in KEYNAME_TO_KEYCODE]
            if keycodes:
                try:
                    kbd.press(*keycodes)
                    time.sleep(0.01)
                    kbd.release_all()
                except Exception as e:
                    print(f"[MACRO] {e}")
                    kbd.release_all()

        elif action_type == "macro_advanced":

            steps = action_obj.get("steps", [])
            if not steps:
                print("[MACRO_ADV] 'steps' list is empty.")
                return
            try:
                for step in steps:
                    if "press" in step:
                        codes = [KEYNAME_TO_KEYCODE[k] for k in step["press"] if k in KEYNAME_TO_KEYCODE]
                        if codes:
                            kbd.press(*codes)
                    elif "release" in step:
                        codes = [KEYNAME_TO_KEYCODE[k] for k in step["release"] if k in KEYNAME_TO_KEYCODE]
                        if codes:
                            kbd.release(*codes)
                    elif "tap" in step:
                        codes = [KEYNAME_TO_KEYCODE[k] for k in step["tap"] if k in KEYNAME_TO_KEYCODE]
                        if codes:
                            kbd.press(*codes)
                            time.sleep(0.01)
                            kbd.release(*codes)
                    elif "wait" in step:
                        try:
                            time.sleep(float(step["wait"]))
                        except Exception:
                            print(f"[MACRO_ADV] Invalid wait: {step['wait']}")
                    elif step.get("release_all"):
                        kbd.release_all()
                    time.sleep(0.01)
            except Exception as e:
                print(f"[MACRO_ADV] Error: {e}")
            finally:

                try:
                    kbd.release_all()
                except Exception:
                    pass

    except Exception as e:
        print(f"[ACTION] Error on '{action_key}': {e}")
        traceback.print_exception(type(e), e, e.__traceback__)

        try:
            kbd.release_all()
        except Exception:
            pass


# Main Loop

print("--- Ready  Profile " + str(current_profile_index + 1) + " | Vol " + str(sensitivity_volume) + "x | Scroll " + str(sensitivity_scroll) + "x | Mouse " + str(sensitivity_mouse) + "x ---")

serial_port = usb_cdc.data

while True:
    current_time     = time.monotonic_ns()
    current_position = encoder.position
    _raw_pressed     = not button_sw.value

    if _raw_pressed == _btn_last_raw:
        if _btn_stable_count < DEBOUNCE_COUNT:
            _btn_stable_count += 1
            if _btn_stable_count >= DEBOUNCE_COUNT:
                button_debounced = _raw_pressed
    else:
        _btn_last_raw     = _raw_pressed
        _btn_stable_count = 1
    button_pressed = button_debounced

    # Serial command check
    if serial_port and serial_port.connected and serial_port.in_waiting > 0:
        try:
            raw = bytearray()
            while serial_port.in_waiting > 0:
                raw.extend(serial_port.read(serial_port.in_waiting))
            command = raw.decode("utf-8").strip().upper() if raw else ""
            if command == "REBOOT":
                print("[SYSTEM] Rebooting...")
                time.sleep(0.5)
                microcontroller.reset()
            elif command:
                print(f"[SERIAL] Unknown command: {command}")
        except Exception as e:
            print(f"[SERIAL] {e}")

    # Button & encoder state machine
    try:

        if button_state == 0 and click_count > 0:
            if (current_time - last_release_time) > MULTI_CLICK_TIMEOUT_NS:
                pending     = click_count
                click_count = 0           # commit reset unconditionally first
                if pending == 1:
                    execute_hid_action("click")
                elif pending == 2:
                    execute_hid_action("double_click")
                else:
                    execute_hid_action("triple_click")

        if button_state == 0:   # Released
            if button_pressed:
                button_state      = 1
                button_press_time = current_time
            else:
                if current_position != last_position:

                    if click_count == 0:
                        execute_hid_action("cw" if current_position > last_position else "ccw")
                    last_position = current_position   # always sync regardless of click_count

        elif button_state == 1:   # Pressed — awaiting action
            if not button_pressed:
                button_state      = 0
                click_count      += 1
                last_release_time = current_time

                if click_count >= 3:
                    click_count = 0
                    execute_hid_action("triple_click")
            else:
                if current_position != last_position:
                    direction     = "cw_shifted" if current_position > last_position else "ccw_shifted"
                    last_position = current_position
                    button_state  = 3
                    click_count   = 0
                    execute_hid_action(direction)
                elif (current_time - button_press_time) >= LONG_PRESS_NS:
                    button_state = 2
                    click_count  = 0
                    execute_hid_action("long_press")

        elif button_state == 2:   # Long press done — wait for release
            if not button_pressed:
                button_state = 0

        elif button_state == 3:   # Shifted — continue shifted rotation until release
            if not button_pressed:
                button_state = 0
            elif current_position != last_position:
                execute_hid_action("cw_shifted" if current_position > last_position else "ccw_shifted")
                last_position = current_position

    except Exception as e:
        print(f"[LOOP] {e}")
        traceback.print_exception(type(e), e, e.__traceback__)
        time.sleep(0.5)

    time.sleep(0.01)
