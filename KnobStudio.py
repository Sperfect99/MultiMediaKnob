# File: KnobStudio
# Version: 4.0 
# Author: Stylianos Tanellari
"""
KnobStudio — Shift Layers Edition
--------------------------------------------
Version 5.0 
- Adds two new action slots per profile:
  - "Hold + CW" (cw_shifted)
  - "Hold + CCW" (ccw_shifted)
- Window is taller to accommodate the new UI elements.
- Save/Load logic is updated for the new v3.0 config structure.
"""

import os
import sys
import time
import json
import threading
import serial
import serial.tools.list_ports
import psutil
import tkinter as tk
from tkinter import messagebox
from collections import OrderedDict

try:
    import customtkinter as ctk
except Exception as e:
    messagebox.showerror("Missing dependency",
                         f"CustomTkinter is missing!\nPlease install it:\n\npip install customtkinter\n\n{e}")
    sys.exit(1)

# --- Available "Simple" Actions  ---
AVAILABLE_SIMPLE_ACTIONS = [
    "nothing",
    "volume_up", "volume_down", "mute", "play_pause", "next_track", "prev_track",
    "scroll_up", "scroll_down", "undo", "redo",
    "mouse_move_x_pos", "mouse_move_x_neg", "mouse_move_y_pos", "mouse_move_y_neg",
    "mouse_scroll_v_pos", "mouse_scroll_v_neg", "mouse_scroll_h_pos", "mouse_scroll_h_neg",
    "mouse_click_left", "mouse_click_right", "mouse_click_middle",
    "next_profile", "switch_profile_1", "switch_profile_2", "switch_profile_3"
]


MODIFIER_DISPLAY_MAP = {
    "LEFT_CONTROL": "Ctrl", "LEFT_SHIFT": "Shift", "LEFT_ALT": "Alt", "LEFT_GUI": "Win/Cmd",
    "RIGHT_CONTROL": "RCtrl", "RIGHT_SHIFT": "RShift", "RIGHT_ALT": "RAlt", "RIGHT_GUI": "RWin"
}
DEFAULT_ACTION_OBJECT = {"type": "simple", "action": "nothing"}


def normalize_key_name(key_str):
    key = key_str.strip().upper()
    if key in ["CONTROL", "CTRL"]: return "LEFT_CONTROL"
    if key in ["SHIFT"]: return "LEFT_SHIFT"
    if key in ["ALT", "ALT_GR"]: return "LEFT_ALT"
    if key in ["WIN", "CMD", "WINDOWS", "COMMAND"]: return "LEFT_GUI"
    if key in ["DEL"]: return "DELETE"
    if key in ["ESC"]: return "ESCAPE"
    if key in ["UP"]: return "UP_ARROW"
    if key in ["DOWN"]: return "DOWN_ARROW"
    if key in ["LEFT"]: return "LEFT_ARROW"
    if key in ["RIGHT"]: return "RIGHT_ARROW"
    return key

# --- Helper Functions (Pico Finder) ---
def find_circuitpy_drive():
    for part in psutil.disk_partitions(all=True):
        if 'rw' in part.opts and part.mountpoint and part.fstype:
            try:
                if (os.path.exists(os.path.join(part.mountpoint,'code.py')) or
                    os.path.exists(os.path.join(part.mountpoint,'boot_out.txt'))):
                    label=""
                    if sys.platform=="win32":
                        try:
                            import win32api
                            label=win32api.GetVolumeInformation(part.mountpoint+"\\")[0]
                        except Exception: pass
                    if "CIRCUITPY" in (label or "") or label=="":
                        return part.mountpoint
            except Exception: continue
    return None

def find_pico_serial_port_for_reboot():
    VID=0x2E8A; PID=0x000A
    for port in serial.tools.list_ports.comports():
        if port.vid==VID and getattr(port,"pid",None)==PID:
            return port.device
    for port in serial.tools.list_ports.comports():
        if ("Pico" in (port.description or "") or "CircuitPython" in (port.description or "")) and port.vid==VID:
            return port.device
    return None

def send_reboot_command(port_name):
    try:
        with serial.Serial(port_name,timeout=0.5,write_timeout=0.5) as s:
            s.write(b"REBOOT\n")
        return True
    except Exception as e:
        print("Reboot error:",e); return False

# ====================================================================== #
#                            ACTION EDITOR                               #
# ====================================================================== #

class ActionEditor(ctk.CTkToplevel):
    def __init__(self, parent, current_action_obj, profile_num, action_key):
        super().__init__(parent)
        self.parent = parent
        self.result = None
        
        self.title(f"Edit Action (P{profile_num} - {action_key.upper()})")
        self.geometry("450x300")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        self.tabs = ctk.CTkTabview(self, width=400, height=240)
        self.tabs.pack(pady=10, padx=10, fill="both", expand=True)
        self.tabs.add("Simple Action")
        self.tabs.add("Advanced Macro")
        
        simple_frame = self.tabs.tab("Simple Action")
        self.simple_tab_var = tk.StringVar()
        ctk.CTkLabel(simple_frame, text="Select a simple HID action:").pack(anchor="w", padx=20, pady=(10,5))
        self.simple_menu = ctk.CTkOptionMenu(simple_frame, values=AVAILABLE_SIMPLE_ACTIONS, variable=self.simple_tab_var, width=300)
        self.simple_menu.pack(anchor="w", padx=20, pady=5)
        
        macro_frame = self.tabs.tab("Advanced Macro")
        self.macro_entry_var = tk.StringVar()
        ctk.CTkLabel(macro_frame, text="Enter key combination (e.g., CTRL+SHIFT+T):").pack(anchor="w", padx=20, pady=(10,5))
        self.macro_entry = ctk.CTkEntry(macro_frame, textvariable=self.macro_entry_var, width=300, font=("Consolas", 13))
        self.macro_entry.pack(anchor="w", padx=20, pady=5)
        ctk.CTkLabel(macro_frame, text="Separate simultaneous keys with '+'.", text_color="gray", font=("Arial", 10)).pack(anchor="w", padx=20)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.save_btn = ctk.CTkButton(btn_frame, text="Save Action", command=self._on_save)
        self.save_btn.pack(side="right", padx=10)
        
        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, fg_color="gray")
        self.cancel_btn.pack(side="right", padx=5)

        self._load_current_action(current_action_obj)

    def _load_current_action(self, action_obj):
        try:
            if action_obj.get("type") == "macro":
                self.tabs.set("Advanced Macro")
                display_keys = []
                for key in action_obj.get("keys", []):
                    display_keys.append(MODIFIER_DISPLAY_MAP.get(key, key.upper()))
                self.macro_entry_var.set(" + ".join(display_keys))
            else:
                self.tabs.set("Simple Action")
                self.simple_tab_var.set(action_obj.get("action", "nothing"))
        except Exception as e:
            print(f"Error loading action: {e}")

    def _on_save(self):
        active_tab = self.tabs.get()
        
        if active_tab == "Simple Action":
            self.result = {
                "type": "simple",
                "action": self.simple_tab_var.get()
            }
        elif active_tab == "Advanced Macro":
            macro_string = self.macro_entry_var.get()
            if not macro_string:
                messagebox.showerror("Error", "Macro string is empty.", parent=self)
                return
            raw_keys = macro_string.split('+')
            final_keys = [normalize_key_name(key) for key in raw_keys if key.strip()]
            if not final_keys:
                messagebox.showerror("Error", "Macro string is invalid.", parent=self)
                return
            self.result = {
                "type": "macro",
                "keys": final_keys
            }
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()

# ====================================================================== #
#                         MAIN UI CLASS (v5.0)                         #
# ====================================================================== #
class MultiKnobConfiguratorModern:
    
    def __init__(self, root):
        self.root = root
        self.root.title("KnobStudio — v5.0")
        ctk.set_appearance_mode("Dark")
        try:
            ctk.set_default_color_theme("green")
        except Exception:
            pass
        # --- v5.0 Change: Window is taller to fit new rows ---
        self.root.geometry("1000x640") # Was 560
        self.root.minsize(980, 640)
        
        self.profile_vars = {}
        self.action_labels = {}
        
        self.current_settings = self.load_gui_settings()
        self.action_names_simple = AVAILABLE_SIMPLE_ACTIONS

        self.main_frame = ctk.CTkFrame(root, corner_radius=8, fg_color="#0b1220")
        self.main_frame.pack(fill="both", expand=True, padx=12, pady=12)
        self.left = ctk.CTkFrame(self.main_frame)
        self.left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
        self.right = ctk.CTkFrame(self.main_frame, width=260)
        self.right.pack(side="right", fill="y", padx=(4, 8), pady=8)
        
        self.build_left()
        self.build_right()
        self.bottom_bar()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    # ---------------- LEFT (v5.0 UPDATE) ----------------
    def build_left(self):
        ctk.CTkLabel(self.left, text="KnobStudio", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=14, pady=(10, 6))
        
        # --- General Settings Frame  ---
        gf = ctk.CTkFrame(self.left)
        gf.pack(fill="x", padx=12, pady=(0, 10))
        gf.grid_columnconfigure(1, weight=1)
        gf.grid_columnconfigure(4, weight=1)

        # Row 0: Volume and Kbd Scroll
        self.sens_vol = tk.IntVar(value=self.current_settings.get("sensitivity_volume", 2))
        ctk.CTkLabel(gf, text="Volume Sens:").grid(row=0, column=0, padx=(8, 4), pady=8, sticky="w")
        self.sens_vol_label = ctk.CTkLabel(gf, width=28)
        self.sens_vol_label.grid(row=0, column=2, padx=(0, 12))
        slider_vol = ctk.CTkSlider(gf, from_=2, to=10, number_of_steps=8, variable=self.sens_vol,
                                   command=lambda v: self.sens_vol_label.configure(text=f"{int(v)}x"))
        slider_vol.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="ew")
        self.sens_vol_label.configure(text=f"{self.sens_vol.get()}x")

        self.sens_scr = tk.IntVar(value=self.current_settings.get("sensitivity_scroll", 1))
        ctk.CTkLabel(gf, text="Kbd Scroll:").grid(row=0, column=3, padx=(8, 4), pady=8, sticky="w")
        self.sens_scr_label = ctk.CTkLabel(gf, width=28)
        self.sens_scr_label.grid(row=0, column=5, padx=(0, 12))
        slider_scr = ctk.CTkSlider(gf, from_=1, to=10, number_of_steps=9, variable=self.sens_scr,
                                   command=lambda v: self.sens_scr_label.configure(text=f"{int(v)}x"))
        slider_scr.grid(row=0, column=4, padx=(0, 8), pady=8, sticky="ew")
        self.sens_scr_label.configure(text=f"{self.sens_scr.get()}x")
        
        # Row 1: Mouse Sens
        self.sens_mouse = tk.IntVar(value=self.current_settings.get("sensitivity_mouse", 4))
        ctk.CTkLabel(gf, text="Mouse Sens:").grid(row=1, column=0, padx=(8, 4), pady=8, sticky="w")
        self.sens_mouse_label = ctk.CTkLabel(gf, width=28)
        self.sens_mouse_label.grid(row=1, column=5, padx=(0, 12))
        slider_mouse = ctk.CTkSlider(gf, from_=1, to=10, number_of_steps=9, variable=self.sens_mouse,
                                     command=lambda v: self.sens_mouse_label.configure(text=f"{int(v)}x"))
        slider_mouse.grid(row=1, column=1, columnspan=4, padx=(0, 8), pady=8, sticky="ew")
        self.sens_mouse_label.configure(text=f"{self.sens_mouse.get()}x")
        
        
        # --- Tabs (v5.0 UPDATE) ---
        self.tabs = ctk.CTkTabview(self.left)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=8)
        
        for i in (1, 2, 3):
            self.tabs.add(f"Profile {i}")
            tab = self.tabs.tab(f"Profile {i}")
            tab.grid_columnconfigure(1, weight=1)
            tab.grid_columnconfigure(2, weight=0)
            
            profile_key = f"profile{i}"
            # v5.0: Load new default keys
            self.profile_vars[i] = self.current_settings.get(profile_key, {
                'cw': DEFAULT_ACTION_OBJECT, 'ccw': DEFAULT_ACTION_OBJECT,
                'click': DEFAULT_ACTION_OBJECT, 'long_press': DEFAULT_ACTION_OBJECT,
                'cw_shifted': DEFAULT_ACTION_OBJECT, 'ccw_shifted': DEFAULT_ACTION_OBJECT # New
            })
            
            self.action_labels[i] = {}
            
            # v5.0: Add new rows
            self._profile_row(tab, i, "Clockwise (CW):", "cw", 0)
            self._profile_row(tab, i, "Counter-CW (CCW):", "ccw", 1)
            self._profile_row(tab, i, "Click:", "click", 2)
            self._profile_row(tab, i, "Long Press:", "long_press", 3)
            # --- New Rows ---
            self._profile_row(tab, i, "Hold + CW:", "cw_shifted", 4, is_new=True)
            self._profile_row(tab, i, "Hold + CCW:", "ccw_shifted", 5, is_new=True)
        
        self.tabs.set("Profile 1")

    # (v5.0 UPDATE)
    def _profile_row(self, tab, profile_index, label_text, action_key, row, is_new=False):
        # Add a subtle top padding for the new "Hold" rows
        pady_val = (12 if is_new else (10 if row == 0 else 8), 8)
        
        ctk.CTkLabel(tab, text=label_text).grid(row=row, column=0, sticky="w", padx=10, pady=pady_val)
        
        # Ensure the key exists in the loaded data, even if loading old config
        if action_key not in self.profile_vars[profile_index]:
             self.profile_vars[profile_index][action_key] = DEFAULT_ACTION_OBJECT
             
        action_obj = self.profile_vars[profile_index][action_key]
        display_text = self._get_action_display_text(action_obj)
        action_label = ctk.CTkLabel(tab, text=display_text, anchor="e", font=ctk.CTkFont(family="Consolas", size=13))
        action_label.grid(row=row, column=1, padx=10, pady=pady_val, sticky="ew")
        self.action_labels[profile_index][action_key] = action_label
        edit_btn = ctk.CTkButton(tab, text="Edit Action...", width=120,
                                 command=lambda p=profile_index, k=action_key: self.open_action_editor(p, k))
        edit_btn.grid(row=row, column=2, sticky="e", padx=10, pady=pady_val)


    def _get_action_display_text(self, action_obj):
        try:
            if action_obj.get("type") == "macro":
                keys = action_obj.get("keys", [])
                display_keys = [MODIFIER_DISPLAY_MAP.get(k, k.upper()) for k in keys]
                return f"Macro: {' + '.join(display_keys)}"
            else:
                return action_obj.get("action", "nothing")
        except Exception:
            return "Error"


    def open_action_editor(self, profile_index, action_key):
        current_action = self.profile_vars[profile_index][action_key]
        editor_window = ActionEditor(self.root, current_action, profile_index, action_key)
        self.root.wait_window(editor_window)
        new_action = editor_window.result
        if new_action:
            self.profile_vars[profile_index][action_key] = new_action
            display_text = self._get_action_display_text(new_action)
            self.action_labels[profile_index][action_key].configure(text=display_text)
            
    # --- RIGHT  ---
    def build_right(self):
        ctk.CTkLabel(self.right,text="Control & Status",font=ctk.CTkFont(size=14,weight="bold")).pack(pady=(10,6))
        qf=ctk.CTkFrame(self.right); qf.pack(fill="x",padx=10,pady=(4,8))
        self.refresh_btn=ctk.CTkButton(qf,text="Find CIRCUITPY",command=self.refresh_thread); self.refresh_btn.pack(fill="x",padx=10,pady=8)
        self.reboot_port_label=ctk.CTkLabel(qf,text="Reboot port: —",anchor="w"); self.reboot_port_label.pack(fill="x",padx=10,pady=(0,8))
        lf=ctk.CTkFrame(self.right); lf.pack(fill="both",expand=True,padx=10,pady=4)
        ctk.CTkLabel(lf,text="Status Log:").pack(anchor="w",padx=10,pady=(8,2))
        self.log=ctk.CTkTextbox(lf,height=10,wrap="word"); self.log.pack(fill="both",expand=True,padx=10,pady=(0,8))
        self.log.configure(state="disabled")
        pf=ctk.CTkFrame(self.right); pf.pack(fill="x",padx=10,pady=(4,8))
        self.progress=ctk.CTkProgressBar(pf); self.progress.set(0); self.progress.pack(fill="x",padx=10,pady=(10,6))
        self.save_btn=ctk.CTkButton(pf,text="Save & Reboot Pico",command=self.save_thread)
        self.save_btn.pack(fill="x",padx=10,pady=(4,10))

    # --- BOTTOM (v5.0) ---
    def bottom_bar(self):
        bar=ctk.CTkFrame(self.root,height=28,corner_radius=0); bar.pack(fill="x",side="bottom")
        self.status=tk.StringVar(value="Ready (v5.0).")
        ctk.CTkLabel(bar,textvariable=self.status,anchor="w").pack(side="left",padx=10)
        ctk.CTkLabel(bar,text="Shift Layer Edition",anchor="e").pack(side="right",padx=10)

    # --- Threads  ---
    def save_thread(self):
        self.save_btn.configure(state="disabled"); self.refresh_btn.configure(state="disabled")
        threading.Thread(target=self._save_and_reboot,daemon=True).start()
        self.animate_progress()
    def refresh_thread(self):
        threading.Thread(target=self._refresh,daemon=True).start()
    def animate_progress(self):
        def step():
            val=self.progress.get()+0.03
            if val>0.9: val=0.1
            self.progress.set(val)
            if str(self.save_btn.cget("state"))=="disabled":
                self.root.after(120,step)
            else:
                self.progress.set(1.0); self.root.after(700,lambda:self.progress.set(0))
        step()

    # --- Logging helpers ---
    def log_add(self,text):
        def _():
            self.log.configure(state="normal"); self.log.insert("end",f"{time.strftime('%H:%M:%S')} — {text}\n")
            self.log.see("end"); self.log.configure(state="disabled")
        self.root.after(0,_)
    def set_status(self,text): self.root.after(0,lambda:self.status.set(text))

    # --- SAVE LOGIC (v5.0 UPDATE) ---
    def _save_and_reboot(self):
        try:
            self.set_status("Finding CIRCUITPY..."); self.log_add("Finding drive...")
            drive = find_circuitpy_drive()
            if not drive:
                self.log_add("CIRCUITPY not found."); self.set_status("Error: Drive not found")
                self.root.after(0, lambda: messagebox.showerror("Error", "CIRCUITPY drive not found."))
                return
            
            json_path = os.path.join(drive, "profiles.json")
            
            s_vol = self._safe_int(self.sens_vol.get(), 2)
            s_scr = self._safe_int(self.sens_scr.get(), 1)
            s_mouse = self._safe_int(self.sens_mouse.get(), 4)
            
            # v5.0: profile_vars now contains all 6 keys, so this is fine
            p1 = self.profile_vars.get(1, {})
            p2 = self.profile_vars.get(2, {})
            p3 = self.profile_vars.get(3, {})
            
            cur_prof = 1
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        cur_prof = json.load(f).get("current_profile", 1)
                except: pass
                
            
            cfg = {
                "current_profile": cur_prof,
                "sensitivity_volume": s_vol,
                "sensitivity_scroll": s_scr,
                "sensitivity_mouse": s_mouse,
                "profiles": [p1, p2, p3] # These dicts now contain all 6 keys
            }
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            
            # v5.0: Save all 6 keys to the local cache too
            self.save_gui_settings(p1, p2, p3, s_vol, s_scr, s_mouse)
            self.log_add("File saved."); self.set_status("Finishing write...")
            
            time.sleep(2.0)
            
            port = find_pico_serial_port_for_reboot()
            if port:
                self.reboot_port_label.configure(text=f"Reboot port: {port}")
                self.log_add(f"Rebooting via {port}..."); self.set_status("Sending reboot...")
                ok = send_reboot_command(port)
                if ok:
                    self.log_add("Reboot successful."); self.set_status("Complete.")
                    self.root.after(0, lambda: messagebox.showinfo("Success", "Saved & Rebooted!"))
                else:
                    self.log_add("Failed to send reboot command."); self.set_status("Manual reboot required.")
                    self.root.after(0, lambda: messagebox.showwarning("Warning", "Saved, but failed to send the reboot command."))
            else:
                self.log_add("Reboot port not found (as expected)."); self.set_status("Complete.")
                self.root.after(0, lambda: messagebox.showinfo("Success", "Settings saved!\nThe Pico will apply them on its next reboot."))
        except Exception as e:
            self.log_add(f"Error: {e}"); self.set_status("Write Error")
            self.root.after(0, lambda: messagebox.showerror("Error", f"{e}"))
        finally:
            self.root.after(0, lambda: self.save_btn.configure(state="normal"))
            self.root.after(0, lambda: self.refresh_btn.configure(state="normal"))

    # --- REFRESH  ---
    def _refresh(self):
        self.set_status("Searching...")
        drive=find_circuitpy_drive()
        self.log_add(f"Drive: {drive if drive else '—'}")
        port=find_pico_serial_port_for_reboot()
        self.root.after(0,lambda:self.reboot_port_label.configure(text=f"Reboot port: {port if port else '—'}"))
        self.set_status("Ready.")

    # --- Helpers (v5.0 UPDATE) ---
    @staticmethod
    def _safe_int(v, default):
        try: return int(v)
        except: return default
    
    # v5.0: save_gui_settings is unchanged, as p1,p2,p3 already contain the new keys
    def save_gui_settings(self, p1, p2, p3, sv, ss, sm):
        data = {
            'profile1': p1, 'profile2': p2, 'profile3': p3,
            'sensitivity_volume': sv, 'sensitivity_scroll': ss,
            'sensitivity_mouse': sm
        }
        try:
            with open("configurator_settings.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log_add(f"Error saving GUI settings: {e}")

    # v5.0: load_gui_settings now loads defaults for 6 keys
    def load_gui_settings(self):
        # Define the full v3.0 default profile
        default_p_base = {
            'cw': DEFAULT_ACTION_OBJECT, 'ccw': DEFAULT_ACTION_OBJECT,
            'click': DEFAULT_ACTION_OBJECT, 'long_press': DEFAULT_ACTION_OBJECT,
            'cw_shifted': DEFAULT_ACTION_OBJECT, 'ccw_shifted': DEFAULT_ACTION_OBJECT
        }
        
        # Create specific defaults
        default_p1 = default_p_base.copy()
        default_p1.update({'cw': {'type': 'simple', 'action': 'volume_up'}, 'ccw': {'type': 'simple', 'action': 'volume_down'}, 'click': {'type': 'simple', 'action': 'mute'}, 'long_press': {'type': 'simple', 'action': 'next_profile'}})
        
        default_p2 = default_p_base.copy()
        default_p2.update({'cw': {'type': 'simple', 'action': 'scroll_up'}, 'ccw': {'type': 'simple', 'action': 'scroll_down'}, 'click': {'type': 'simple', 'action': 'play_pause'}})
        
        default_p3 = default_p_base.copy()
        default_p3.update({'cw': {"type": "simple", "action": "mouse_scroll_v_pos"}, 'ccw': {"type": "simple", "action": "mouse_scroll_v_neg"}, 'click': {"type": "simple", "action": "mouse_click_middle"}, 'cw_shifted': {"type": "simple", "action": "mouse_scroll_h_pos"}, 'ccw_shifted': {"type": "simple", "action": "mouse_scroll_h_neg"}})
        
        
        d = {
            'profile1': default_p1, 'profile2': default_p2, 'profile3': default_p3,
            'sensitivity_volume': 2, 'sensitivity_scroll': 1,
            'sensitivity_mouse': 4
        }
        
        try:
            with open("configurator_settings.json", "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                
                # Check what version the config is and migrate if needed
                if isinstance(loaded_data.get('profile1', {}).get('cw'), str):
                    self.log_add("Old v1.0 config found. Migrating to v3.0...")
                    d = self._migrate_v1_to_v3(loaded_data)
                elif 'cw_shifted' not in loaded_data.get('profile1', {}):
                    self.log_add("v2.0 (Mouse) config found. Migrating to v3.0 (Shift)...")
                    d.update(loaded_data) # Load v2 data
                    # Add new keys to profiles
                    for i in (1, 2, 3):
                        d[f'profile{i}'].setdefault('cw_shifted', DEFAULT_ACTION_OBJECT)
                        d[f'profile{i}'].setdefault('ccw_shifted', DEFAULT_ACTION_OBJECT)
                else:
                    d.update(loaded_data)
                    self.log_add("Loaded v3.0+ (Shift) config settings.")
                    
        except FileNotFoundError:
            self.log_add("No settings file found. Loading defaults.")
        except Exception as e:
            self.log_add(f"Error loading settings: {e}. Loading defaults.")
        return d

    # v5.0: This migrates from the very first version (v1)
    def _migrate_v1_to_v3(self, v1_data):
        v3_data = {
            'sensitivity_volume': v1_data.get('sensitivity_volume', 2),
            'sensitivity_scroll': v1_data.get('sensitivity_scroll', 1),
            'sensitivity_mouse': 4 # Add mouse default
        }
        
        for i in (1, 2, 3):
            profile_key = f'profile{i}'
            v1_profile = v1_data.get(profile_key, {})
            v3_profile = {}
            for action_key in ("cw", "ccw", "click", "long_press"):
                action_name = v1_profile.get(action_key, "nothing")
                v3_profile[action_key] = {
                    "type": "simple",
                    "action": action_name
                }
            # Add new shift keys
            v3_profile['cw_shifted'] = DEFAULT_ACTION_OBJECT
            v3_profile['ccw_shifted'] = DEFAULT_ACTION_OBJECT
            v3_data[profile_key] = v3_profile
            
        return v3_data

# --- Run ---
if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import win32api
        except:
            pass
    root = ctk.CTk()
    app = MultiKnobConfiguratorModern(root)
    root.mainloop()

