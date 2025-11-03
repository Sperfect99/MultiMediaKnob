import board
import digitalio
import rotaryio
import time
import json
import usb_hid
import usb_cdc
import microcontroller
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
import traceback
import storage # For checking/saving current_profile

print("--- Multi-Knob v10.1 (HID Configurable - Per Action Sensitivity) ---")

# --- Pins ---
encoder_clk = board.GP13; encoder_dt = board.GP14; encoder_sw = board.GP15


# --- HID Init ---
try:
    kbd = Keyboard(usb_hid.devices)
    cc = ConsumerControl(usb_hid.devices)
    print("[HID] Keyboard and ConsumerControl initialized.")
except Exception as e:
    print(f"[HID] ERROR initializing HID devices: {e}")
    while True: time.sleep(1)

# --- Components Init ---
# divisor=4: 1 click = 1 clean signal. Speed is handled by sensitivity.
encoder = rotaryio.IncrementalEncoder(encoder_clk, encoder_dt, divisor=4)
button_sw = digitalio.DigitalInOut(encoder_sw); button_sw.direction = digitalio.Direction.INPUT; button_sw.pull = digitalio.Pull.UP


# --- Global Variables ---
current_profile_index = 0; num_profiles = 3; profiles_data = {}
sensitivity_volume = 1 # Default, will be loaded from JSON
sensitivity_scroll = 1 # Default, will be loaded from JSON

# --- Profile Switching Functions ---
def save_current_profile_index(index):
    global profiles_data
    if not profiles_data or "current_profile" not in profiles_data: return
    # Update in-memory only
    profiles_data["current_profile"] = index + 1
    # We don't try to write to the file here anymore

def switch_profile(target_index):
    global current_profile_index
    if 0 <= target_index < num_profiles:
        current_profile_index = target_index
        print(f"[SYSTEM] Switched to Profile {current_profile_index + 1}")
        save_current_profile_index(current_profile_index)
    else: print(f"[SYSTEM] Invalid target profile index: {target_index}")

def next_profile():
    global current_profile_index
    next_index = (current_profile_index + 1) % num_profiles
    switch_profile(next_index)

# --- HID Actions MAP (profile switching) ---
ACTIONS_MAP = {
    "nothing": lambda: None, "volume_up": lambda: cc.send(ConsumerControlCode.VOLUME_INCREMENT),
    "volume_down": lambda: cc.send(ConsumerControlCode.VOLUME_DECREMENT), "mute": lambda: cc.send(ConsumerControlCode.MUTE),
    "play_pause": lambda: cc.send(ConsumerControlCode.PLAY_PAUSE), "next_track": lambda: cc.send(ConsumerControlCode.SCAN_NEXT_TRACK),
    "prev_track": lambda: cc.send(ConsumerControlCode.SCAN_PREVIOUS_TRACK), "scroll_up": lambda: kbd.send(Keycode.UP_ARROW),
    "scroll_down": lambda: kbd.send(Keycode.DOWN_ARROW), "undo": lambda: kbd.send(Keycode.LEFT_CONTROL, Keycode.Z),
    "redo": lambda: kbd.send(Keycode.LEFT_CONTROL, Keycode.Y),
    "next_profile": next_profile, "switch_profile_1": lambda: switch_profile(0),
    "switch_profile_2": lambda: switch_profile(1), "switch_profile_3": lambda: switch_profile(2),
}
AVAILABLE_ACTIONS = list(ACTIONS_MAP.keys())

# --- Config Loading ---
CONFIG_FILE = "/profiles.json"
# Updated defaults including new sensitivity settings
default_profiles = {
    "current_profile": 1,
    "sensitivity_volume": 2, # Default for volume
    "sensitivity_scroll": 1, # Default for scroll
    "profiles": [
        {"cw": "volume_up", "ccw": "volume_down", "click": "mute", "long_press": "next_profile"},
        {"cw": "scroll_up", "ccw": "scroll_down", "click": "play_pause", "long_press": "nothing"},
        {"cw": "next_track", "ccw": "prev_track", "click": "nothing", "long_press": "nothing"}
    ]
}

# --- Load config on boot ---
try:
    with open(CONFIG_FILE, "r") as f:
        loaded_data = json.load(f)
        # Check for v10.1+ config structure
        if ("current_profile" in loaded_data and "sensitivity_volume" in loaded_data and
            "sensitivity_scroll" in loaded_data and "profiles" in loaded_data and
            isinstance(loaded_data["profiles"], list) and len(loaded_data["profiles"]) >= 3 and
            all(isinstance(p, dict) and "cw" in p and "ccw" in p and "click" in p and "long_press" in p
                for p in loaded_data["profiles"])):
            profiles_data = loaded_data
            print(f"[FS] Loaded valid config v10.1+ from {CONFIG_FILE}")
        else:
            print(f"[FS] Invalid/Old structure in {CONFIG_FILE}. Using defaults.")
            profiles_data = default_profiles.copy()
except OSError:
    print(f"[FS] {CONFIG_FILE} not found. Using defaults.")
    profiles_data = default_profiles.copy()
except Exception as e:
    print(f"[FS] ERROR loading {CONFIG_FILE}: {e}. Using defaults.")
    traceback.print_exception(e)
    profiles_data = default_profiles.copy()

if not profiles_data: print("[FS] CRITICAL: Using defaults."); profiles_data = default_profiles.copy()

# Load values into memory
current_profile_index = profiles_data.get("current_profile", 1) - 1
sensitivity_volume = profiles_data.get("sensitivity_volume", 1) # Load volume sensitivity
sensitivity_scroll = profiles_data.get("sensitivity_scroll", 1) # Load scroll sensitivity
num_profiles = len(profiles_data.get("profiles", []))
if not 0 <= current_profile_index < num_profiles: print(f"[CONFIG] Invalid profile index. Resetting."); current_profile_index = 0; profiles_data["current_profile"] = 1
# Sanity check sensitivities if out of bounds (e.g., 1-10)
if not 1 <= sensitivity_volume <= 10: print(f"[CONFIG] Invalid volume sensitivity. Setting to 1."); sensitivity_volume = 1
if not 1 <= sensitivity_scroll <= 10: print(f"[CONFIG] Invalid scroll sensitivity. Setting to 1."); sensitivity_scroll = 1


# --- Loop Variables ---
last_position = encoder.position; button_state = 0; button_press_time = 0.0; LONG_PRESS_THRESHOLD = 0.8



def execute_hid_action(action_key):
    """Executes an HID action, applying the correct sensitivity and correcting for double pulses."""
    global current_profile_index, profiles_data, ACTIONS_MAP, sensitivity_volume, sensitivity_scroll
    try:
        num_profiles_safe = len(profiles_data.get("profiles", []))
        if 0 <= current_profile_index < num_profiles_safe:
            action_name = profiles_data["profiles"][current_profile_index].get(action_key, "nothing")
            action_func = ACTIONS_MAP.get(action_name, ACTIONS_MAP["nothing"])

            multiplier = 1
            delay_per_step = 0.005

            if action_key in ["cw", "ccw"]:
                if action_name in ["volume_up", "volume_down"]:
                    # Compensate for the double hardware pulse (x0.5)
                    multiplier = max(1, round(sensitivity_volume / 2))
                    delay_per_step = 0.015
                elif action_name in ["scroll_up", "scroll_down"]:
                    multiplier = sensitivity_scroll
                    delay_per_step = 0.005

            # --- Execute Action ---
            if action_name.startswith("switch_profile_") or action_name == "next_profile":
                action_func()
            else:
                for _ in range(multiplier):
                    action_func()
                    time.sleep(delay_per_step)
        else:
            print(f"ERROR: Invalid profile index {current_profile_index}!")
    except Exception as e:
        print(f"ERROR executing action '{action_key}': {e}")


# --- Main Loop ---
print(f"--- Ready (Profile {current_profile_index + 1}, Vol Sens: {sensitivity_volume}x, Scroll Sens: {sensitivity_scroll}x) ---")

serial_port = usb_cdc.data

while True:
    current_time = time.monotonic()

    # --- 1. Check for REBOOT Command ---
    if serial_port and serial_port.connected and serial_port.in_waiting > 0:
        try:
            raw_data=bytearray(); command=""
            while serial_port.in_waiting > 0: raw_data.extend(serial_port.read(serial_port.in_waiting))
            if raw_data: command = raw_data.decode("utf-8").strip().upper()
            if command == "REBOOT": print("[SYSTEM] Rebooting..."); time.sleep(0.5); microcontroller.reset()
            elif command: print(f"[SERIAL] Unknown command: {command}")
        except Exception as e: print(f"[SERIAL] Error: {e}")

    # --- 2. Check Rotary Encoder ---
    try:
        current_position = encoder.position
        if current_position != last_position:
            action_key = "cw" if current_position > last_position else "ccw"
            execute_hid_action(action_key) # execute_hid_action handles the multiplier
            last_position = current_position
    except Exception as e: print(f"ERROR reading encoder: {e}"); time.sleep(0.5)

    # --- 3. Check Encoder Button (Corrected Logic) ---
    try:
        button_is_pressed = not button_sw.value
        if button_state == 0: # Released
            if button_is_pressed: button_state = 1; button_press_time = current_time
        elif button_state == 1: # Pressed
            if not button_is_pressed: # Released (Short Press)
                press_duration = current_time - button_press_time
                if press_duration < LONG_PRESS_THRESHOLD:
                    execute_hid_action("click") # multiplier=1 by default
                button_state = 0
            else: # Still Held -> Check Long Press
                press_duration = current_time - button_press_time
                if press_duration >= LONG_PRESS_THRESHOLD:
                    execute_hid_action("long_press") # multiplier=1 by default
                    button_state = 2 # Long press done
        elif button_state == 2: # Long press done
            if not button_is_pressed: button_state = 0 # Released after long press
    except Exception as e: print(f"ERROR reading button: {e}"); time.sleep(0.5)

    time.sleep(0.01)