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
from adafruit_hid.mouse import Mouse
import traceback
import storage

print("--- Multi-Knob v13.0 ---")

# --- Pins ---
encoder_clk = board.GP13
encoder_dt = board.GP14
encoder_sw = board.GP15

# --- HID Init ---
try:
    kbd = Keyboard(usb_hid.devices)
    cc = ConsumerControl(usb_hid.devices)
    mouse = Mouse(usb_hid.devices)
    print("[HID] Keyboard, ConsumerControl, and Mouse initialized.")
except Exception as e:
    print(f"[HID] ERROR initializing HID devices: {e}")
    while True:
        time.sleep(1)

# --- Components Init ---
encoder = rotaryio.IncrementalEncoder(encoder_clk, encoder_dt, divisor=4)
button_sw = digitalio.DigitalInOut(encoder_sw)
button_sw.direction = digitalio.Direction.INPUT
button_sw.pull = digitalio.Pull.UP

# --- Global Variables ---
current_profile_index = 0
num_profiles = 3
profiles_data = {}
sensitivity_volume = 1
sensitivity_scroll = 1
sensitivity_mouse = 4

# --- Profile Switching ---
def save_current_profile_index(index):
    global profiles_data
    if not profiles_data or "current_profile" not in profiles_data:
        return
    profiles_data["current_profile"] = index + 1

def switch_profile(target_index):
    global current_profile_index
    if 0 <= target_index < num_profiles:
        current_profile_index = target_index
        print(f"[SYSTEM] Switched to Profile {current_profile_index + 1}")
        save_current_profile_index(current_profile_index)
    else:
        print(f"[SYSTEM] Invalid target profile index: {target_index}")

def next_profile():
    global current_profile_index
    next_index = (current_profile_index + 1) % num_profiles
    switch_profile(next_index)

# --- v12.1 Helper functions for Mouse  ---
def _mouse_move_x_pos(): mouse.move(x=sensitivity_mouse)
def _mouse_move_x_neg(): mouse.move(x=-sensitivity_mouse)
def _mouse_move_y_pos(): mouse.move(y=sensitivity_mouse)
def _mouse_move_y_neg(): mouse.move(y=-sensitivity_mouse)
def _mouse_scroll_v_pos(): mouse.move(wheel=1)
def _mouse_scroll_v_neg(): mouse.move(wheel=-1)
def _mouse_scroll_h_pos(): mouse.move(wheel=1, horizontal=True)
def _mouse_scroll_h_neg(): mouse.move(wheel=-1, horizontal=True)

# --- HID Actions MAP (v12.1 List) ---
SIMPLE_ACTIONS_MAP = {
    "nothing": lambda: None,
    "volume_up": lambda: cc.send(ConsumerControlCode.VOLUME_INCREMENT),
    "volume_down": lambda: cc.send(ConsumerControlCode.VOLUME_DECREMENT),
    "mute": lambda: cc.send(ConsumerControlCode.MUTE),
    "play_pause": lambda: cc.send(ConsumerControlCode.PLAY_PAUSE),
    "next_track": lambda: cc.send(ConsumerControlCode.SCAN_NEXT_TRACK),
    "prev_track": lambda: cc.send(ConsumerControlCode.SCAN_PREVIOUS_TRACK),
    "scroll_up": lambda: kbd.send(Keycode.UP_ARROW),
    "scroll_down": lambda: kbd.send(Keycode.DOWN_ARROW),
    "undo": lambda: kbd.send(Keycode.LEFT_CONTROL, Keycode.Z),
    "redo": lambda: kbd.send(Keycode.LEFT_CONTROL, Keycode.Y),
    "mouse_move_x_pos": _mouse_move_x_pos,
    "mouse_move_x_neg": _mouse_move_x_neg,
    "mouse_move_y_pos": _mouse_move_y_pos,
    "mouse_move_y_neg": _mouse_move_y_neg,
    "mouse_scroll_v_pos": _mouse_scroll_v_pos,
    "mouse_scroll_v_neg": _mouse_scroll_v_neg,
    "mouse_scroll_h_pos": _mouse_scroll_h_pos,
    "mouse_scroll_h_neg": _mouse_scroll_h_neg,
    "mouse_click_left": lambda: mouse.click(Mouse.LEFT_BUTTON),
    "mouse_click_right": lambda: mouse.click(Mouse.RIGHT_BUTTON),
    "mouse_click_middle": lambda: mouse.click(Mouse.MIDDLE_BUTTON),
    "next_profile": next_profile,
    "switch_profile_1": lambda: switch_profile(0),
    "switch_profile_2": lambda: switch_profile(1),
    "switch_profile_3": lambda: switch_profile(2),
}
AVAILABLE_ACTIONS = list(SIMPLE_ACTIONS_MAP.keys())

# --- KEYNAME_TO_KEYCODE Map (v11.1) ---
KEYNAME_TO_KEYCODE = {
    # Modifiers
    "LEFT_CONTROL": Keycode.LEFT_CONTROL, "CONTROL": Keycode.LEFT_CONTROL, "CTRL": Keycode.LEFT_CONTROL,
    "LEFT_SHIFT": Keycode.LEFT_SHIFT, "SHIFT": Keycode.LEFT_SHIFT,
    "LEFT_ALT": Keycode.LEFT_ALT, "ALT": Keycode.LEFT_ALT,
    "LEFT_GUI": Keycode.LEFT_GUI, "WIN": Keycode.LEFT_GUI, "CMD": Keycode.LEFT_GUI, "COMMAND": Keycode.LEFT_GUI,
    "RIGHT_CONTROL": Keycode.RIGHT_CONTROL, "RCTRL": Keycode.RIGHT_CONTROL,
    "RIGHT_SHIFT": Keycode.RIGHT_SHIFT, "RSHIFT": Keycode.RIGHT_SHIFT,
    "RIGHT_ALT": Keycode.RIGHT_ALT, "RALT": Keycode.RIGHT_ALT, "ALT_GR": Keycode.RIGHT_ALT,
    "RIGHT_GUI": Keycode.RIGHT_GUI, "RWIN": Keycode.RIGHT_GUI, "RCMD": Keycode.RIGHT_GUI,
    # Letters
    "A": Keycode.A, "B": Keycode.B, "C": Keycode.C, "D": Keycode.D, "E": Keycode.E,
    "F": Keycode.F, "G": Keycode.G, "H": Keycode.H, "I": Keycode.I, "J": Keycode.J,
    "K": Keycode.K, "L": Keycode.L, "M": Keycode.M, "N": Keycode.N, "O": Keycode.O,
    "P": Keycode.P, "Q": Keycode.Q, "R": Keycode.R, "S": Keycode.S, "T": Keycode.T,
    "U": Keycode.U, "V": Keycode.V, "W": Keycode.W, "X": Keycode.X, "Y": Keycode.Y, "Z": Keycode.Z,
    # Numbers
    "1": Keycode.ONE, "2": Keycode.TWO, "3": Keycode.THREE, "4": Keycode.FOUR, "5": Keycode.FIVE,
    "6": Keycode.SIX, "7": Keycode.SEVEN, "8": Keycode.EIGHT, "9": Keycode.NINE, "0": Keycode.ZERO,
    # Function Keys
    "F1": Keycode.F1, "F2": Keycode.F2, "F3": Keycode.F3, "F4": Keycode.F4, "F5": Keycode.F5,
    "F6": Keycode.F6, "F7": Keycode.F7, "F8": Keycode.F8, "F9": Keycode.F9, "F10": Keycode.F10,
    "F11": Keycode.F11, "F12": Keycode.F12,
    # Common Keys
    "ENTER": Keycode.ENTER, "RETURN": Keycode.ENTER,
    "ESCAPE": Keycode.ESCAPE, "ESC": Keycode.ESCAPE,
    "BACKSPACE": Keycode.BACKSPACE,
    "TAB": Keycode.TAB,
    "SPACE": Keycode.SPACE, "SPACEBAR": Keycode.SPACE,
    "DELETE": Keycode.DELETE, "DEL": Keycode.DELETE,
    # Arrow Keys
    "UP_ARROW": Keycode.UP_ARROW, "UP": Keycode.UP_ARROW,
    "DOWN_ARROW": Keycode.DOWN_ARROW, "DOWN": Keycode.DOWN_ARROW,
    "LEFT_ARROW": Keycode.LEFT_ARROW, "LEFT": Keycode.LEFT_ARROW,
    "RIGHT_ARROW": Keycode.RIGHT_ARROW, "RIGHT": Keycode.RIGHT_ARROW,
    # Other
    "PAGE_UP": Keycode.PAGE_UP, "PGUP": Keycode.PAGE_UP,
    "PAGE_DOWN": Keycode.PAGE_DOWN, "PGDN": Keycode.PAGE_DOWN,
    "HOME": Keycode.HOME, "END": Keycode.END,
    "INSERT": Keycode.INSERT,
}

# --- Config Loading (v13.0) ---
CONFIG_FILE = "/profiles.json"
DEFAULT_ACTION_OBJECT = {"type": "simple", "action": "nothing"}

# --- v13.0: Added cw_shifted and ccw_shifted to defaults ---
default_profiles = {
    "current_profile": 1,
    "sensitivity_volume": 2,
    "sensitivity_scroll": 1,
    "sensitivity_mouse": 4, 
    "profiles": [
        {"cw": {"type": "simple", "action": "volume_up"}, "ccw": {"type": "simple", "action": "volume_down"}, "click": {"type": "simple", "action": "mute"}, "long_press": {"type": "simple", "action": "next_profile"}, "cw_shifted": DEFAULT_ACTION_OBJECT, "ccw_shifted": DEFAULT_ACTION_OBJECT},
        {"cw": {"type": "simple", "action": "scroll_up"}, "ccw": {"type": "simple", "action": "scroll_down"}, "click": {"type": "simple", "action": "play_pause"}, "long_press": DEFAULT_ACTION_OBJECT, "cw_shifted": DEFAULT_ACTION_OBJECT, "ccw_shifted": DEFAULT_ACTION_OBJECT},
        {"cw": {"type": "simple", "action": "mouse_scroll_v_pos"}, "ccw": {"type": "simple", "action": "mouse_scroll_v_neg"}, "click": {"type": "simple", "action": "mouse_click_middle"}, "long_press": DEFAULT_ACTION_OBJECT, "cw_shifted": {"type": "simple", "action": "mouse_scroll_h_pos"}, "ccw_shifted": {"type": "simple", "action": "mouse_scroll_h_neg"}}
    ]
}

def is_valid_v3_config(config):
    try:
        
        if not ("current_profile" in config and "sensitivity_volume" in config and
                "sensitivity_scroll" in config and "sensitivity_mouse" in config and
                "profiles" in config and
                isinstance(config["profiles"], list) and len(config["profiles"]) >= 3):
            return False
        for profile in config["profiles"]:
            # Check for ALL 6 action keys
            for key in ("cw", "ccw", "click", "long_press", "cw_shifted", "ccw_shifted"):
                action_obj = profile.get(key)
                if not (isinstance(action_obj, dict) and "type" in action_obj): return False
                # Validate the action object itself
                if action_obj["type"] == "simple":
                    if not "action" in action_obj: return False
                elif action_obj["type"] == "macro":
                    if not ("keys" in action_obj and isinstance(action_obj["keys"], list)): return False
        return True # All checks passed
    except Exception as e:
        print(f"[VALIDATE] Error: {e}"); return False

try:
    with open(CONFIG_FILE, "r") as f:
        loaded_data = json.load(f)
        if is_valid_v3_config(loaded_data):
            profiles_data = loaded_data
            print(f"[FS] Loaded valid config v3.0+ (Shift) from {CONFIG_FILE}")
        else:
            print(f"[FS] Invalid/Old structure in {CONFIG_FILE}. Upgrading...")
            # This is a simple migration, just assumes defaults for missing keys
            base_data = default_profiles.copy()
            base_data.update(loaded_data) # Overwrite defaults with user settings
            # Ensure profiles are at least 3
            if len(base_data["profiles"]) < 3: base_data["profiles"] = default_profiles["profiles"]
            # Ensure new keys exist in profiles
            for i in range(3):
                base_data["profiles"][i].setdefault("cw_shifted", DEFAULT_ACTION_OBJECT)
                base_data["profiles"][i].setdefault("ccw_shifted", DEFAULT_ACTION_OBJECT)
            profiles_data = base_data
            print("[FS] Upgrade complete. Using migrated config.")
            
except OSError:
    print(f"[FS] {CONFIG_FILE} not found. Using defaults.")
    profiles_data = default_profiles.copy()
except Exception as e:
    print(f"[FS] ERROR loading {CONFIG_FILE}: {e}. Using defaults.")
    traceback.print_exception(e)
    profiles_data = default_profiles.copy()

if not profiles_data:
    print("[FS] CRITICAL: Using defaults.")
    profiles_data = default_profiles.copy()

# Load values into memory
current_profile_index = profiles_data.get("current_profile", 1) - 1
sensitivity_volume = profiles_data.get("sensitivity_volume", 2)
sensitivity_scroll = profiles_data.get("sensitivity_scroll", 1)
sensitivity_mouse = profiles_data.get("sensitivity_mouse", 4)
num_profiles = len(profiles_data.get("profiles", []))
if not 0 <= current_profile_index < num_profiles:
    print(f"[CONFIG] Invalid profile index. Resetting.")
    current_profile_index = 0
    profiles_data["current_profile"] = 1
if not 1 <= sensitivity_volume <= 10: sensitivity_volume = 2
if not 1 <= sensitivity_scroll <= 10: sensitivity_scroll = 1
if not 1 <= sensitivity_mouse <= 10: sensitivity_mouse = 4

# --- Loop Variables ---
last_position = encoder.position
button_state = 0 # 0=Released, 1=Pressed(awaiting action), 2=LongPressed(awaiting release), 3=Shifted(awaiting release)
button_press_time = 0.0
LONG_PRESS_THRESHOLD = 0.8

# --- execute_hid_action (v12.1) ---
def execute_hid_action(action_key):
    global current_profile_index, profiles_data, SIMPLE_ACTIONS_MAP, KEYNAME_TO_KEYCODE
    global sensitivity_volume, sensitivity_scroll
    
    try:
        profile = profiles_data["profiles"][current_profile_index]
        action_obj = profile.get(action_key, DEFAULT_ACTION_OBJECT)
        action_type = action_obj.get("type", "simple")
        
        if action_type == "simple":
            action_name = action_obj.get("action", "nothing")
            action_func = SIMPLE_ACTIONS_MAP.get(action_name, SIMPLE_ACTIONS_MAP["nothing"])
            
            multiplier = 1
            delay_per_step = 0.005
            
            if action_key in ["cw", "ccw", "cw_shifted", "ccw_shifted"]: # Apply sensitivity to shifted actions too
                if action_name in ["volume_up", "volume_down"]:
                    multiplier = max(1, round(sensitivity_volume / 2))
                    delay_per_step = 0.015
                elif action_name in ["scroll_up", "scroll_down"]:
                    multiplier = sensitivity_scroll
                    delay_per_step = 0.005
            
            if action_name.startswith("switch_profile_") or action_name == "next_profile":
                action_func()
            else:
                for _ in range(multiplier):
                    action_func()
                    time.sleep(delay_per_step)

        elif action_type == "macro":
            keys_to_press = action_obj.get("keys", [])
            keycodes = []
            for key_name in keys_to_press:
                keycode = KEYNAME_TO_KEYCODE.get(key_name)
                if keycode:
                    keycodes.append(keycode)
                else:
                    print(f"[MACRO] Unknown key: {key_name}")
            
            if keycodes:
                try:
                    kbd.press(*keycodes)
                    time.sleep(0.01)
                    kbd.release_all()
                except Exception as e:
                    print(f"[MACROC] Error: {e}")
                    kbd.release_all()

    except Exception as e:
        print(f"ERROR executing action '{action_key}': {e}")
        traceback.print_exception(e)


# --- Main Loop (v13.0) ---
print(f"--- Ready (Profile {current_profile_index + 1}, Vol: {sensitivity_volume}x, Scroll: {sensitivity_scroll}x, Mouse: {sensitivity_mouse}x) ---")
serial_port = usb_cdc.data

while True:
    current_time = time.monotonic()
    current_position = encoder.position
    button_is_pressed = not button_sw.value

    # --- 1. Check Serial (Unchanged) ---
    if serial_port and serial_port.connected and serial_port.in_waiting > 0:
        try:
            raw_data = bytearray()
            command = ""
            while serial_port.in_waiting > 0: raw_data.extend(serial_port.read(serial_port.in_waiting))
            if raw_data: command = raw_data.decode("utf-8").strip().upper()
            if command == "REBOOT":
                print("[SYSTEM] Rebooting..."); time.sleep(0.5); microcontroller.reset()
            elif command: print(f"[SERIAL] Unknown command: {command}")
        except Exception as e: print(f"[SERIAL] Error: {e}")

    # --- 2. Button State Machine ---
    try:
        if button_state == 0: # State 0: Released
            if button_is_pressed:
                # Button was just pressed, start timer
                button_state = 1
                button_press_time = current_time
            else:
                # Button is not pressed, check for normal rotation
                if current_position != last_position:
                    action_key = "cw" if current_position > last_position else "ccw"
                    execute_hid_action(action_key)
                    last_position = current_position

        elif button_state == 1: # State 1: Pressed, awaiting action
            if not button_is_pressed:
                # --- Button was RELEASED (Short Click) ---
                # It wasn't held long enough for long_press, and no rotation happened
                execute_hid_action("click")
                button_state = 0 # Go back to released state
            else:
                # --- Button is STILL HELD ---
                # Check for SHIFTED rotation *first*
                if current_position != last_position:
                    action_key = "cw_shifted" if current_position > last_position else "ccw_shifted"
                    execute_hid_action(action_key)
                    last_position = current_position
                    button_state = 3 # Go to "Shifted" state
                
                # If no rotation, check for LONG PRESS
                elif (current_time - button_press_time) >= LONG_PRESS_THRESHOLD:
                    execute_hid_action("long_press")
                    button_state = 2 # Go to "Long Press Done" state
        
        elif button_state == 2: # State 2: Long Press Done, waiting for release
            if not button_is_pressed:
                button_state = 0 # Released
        
        elif button_state == 3: # State 3: Shifted, waiting for release (or more shift)
            if not button_is_pressed:
                button_state = 0 # Released
            else:
                # Allow *continued* shifted rotation
                if current_position != last_position:
                    action_key = "cw_shifted" if current_position > last_position else "ccw_shifted"
                    execute_hid_action(action_key)
                    last_position = current_position
                    
    except Exception as e:
        print(f"ERROR reading button/encoder: {e}")
        traceback.print_exception(e)
        time.sleep(0.5)

    time.sleep(0.01)

