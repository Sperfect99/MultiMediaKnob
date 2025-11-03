# File: KnobStudio
# Version: 5.2
# Author: Stylianos Tanellari
"""
KnobStudio — Modern Dark Edition
--------------------------------------------
A modern, Dark UI (teal accent) built with customtkinter.
Keeps all the functionality of the original configurator.

Requirements:
    pip install customtkinter psutil pyserial
    (Windows: pip install pywin32 if missing)
"""


"""
test5_UIV2: In this version, we added sliders to the UI instead of a simple value selection.
test5_UIV3: In this version, we changed the 'connection lost' message after saving to a 'success' message.
"""
"""
codeV5_2: In this version, we fixed the bug where values received from the app were being duplicated.
"""



import os, sys, time, json, threading, serial, serial.tools.list_ports, psutil, tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
except Exception as e:
    messagebox.showerror("Missing dependency",
                         f"CustomTkinter is missing!\nPlease install it:\n\npip install customtkinter\n\n{e}")
    sys.exit(1)

# --- Available Actions ---
AVAILABLE_ACTIONS_PC = [
    "nothing","volume_up","volume_down","mute","play_pause","next_track","prev_track",
    "scroll_up","scroll_down","undo","redo","next_profile","switch_profile_1","switch_profile_2","switch_profile_3"
]

# --- Find CIRCUITPY ---
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

# --- Find Pico Serial Port ---
def find_pico_serial_port_for_reboot():
    VID=0x2E8A; PID=0x000A
    for port in serial.tools.list_ports.comports():
        if port.vid==VID and getattr(port,"pid",None)==PID:
            return port.device
    for port in serial.tools.list_ports.comports():
        if ("Pico" in (port.description or "") or "CircuitPython" in (port.description or "")) and port.vid==VID:
            return port.device
    return None

# --- Reboot Pico ---
def send_reboot_command(port_name):
    try:
        with serial.Serial(port_name,timeout=0.5,write_timeout=0.5) as s:
            s.write(b"REBOOT\n")
        return True
    except Exception as e:
        print("Reboot error:",e)
        return False

# ====================================================================== #
#                               MAIN UI CLASS                               #
# ====================================================================== #
class MultiKnobConfiguratorModern:
    def __init__(self,root):
        self.root=root
        self.root.title("KnobStudio — Dark Edition")
        ctk.set_appearance_mode("Dark")
        try: ctk.set_default_color_theme("green")
        except Exception: pass
        self.root.geometry("1000x480"); self.root.minsize(980,480)
        self.current_settings=self.load_gui_settings()
        self.action_names=AVAILABLE_ACTIONS_PC

        self.main_frame=ctk.CTkFrame(root,corner_radius=8,fg_color="#0b1220")
        self.main_frame.pack(fill="both",expand=True,padx=12,pady=12)
        self.left=ctk.CTkFrame(self.main_frame); self.left.pack(side="left",fill="both",expand=True,padx=(8,4),pady=8)
        self.right=ctk.CTkFrame(self.main_frame,width=260); self.right.pack(side="right",fill="y",padx=(4,8),pady=8)
        self.build_left(); self.build_right(); self.bottom_bar()
        self.root.protocol("WM_DELETE_WINDOW",self.root.destroy)

    # ---------------- LEFT ----------------
# ---------------- LEFT (IMPROVED WITH SLIDERS) ----------------
# ---------------- LEFT (IMPROVED WITH SLIDERS & CORRECT STRETCH) ----------------
    def build_left(self):
        ctk.CTkLabel(self.left,text="KnobStudio",font=ctk.CTkFont(size=18,weight="bold")).pack(anchor="w",padx=14,pady=(10,6))
        
        # --- General Settings Frame ---
        gf = ctk.CTkFrame(self.left); gf.pack(fill="x",padx=12,pady=(0,10))
        
        # --- FIX HERE ---
        # Make columns 1 and 4 (which hold the sliders) stretch equally
        gf.grid_columnconfigure(1, weight=1)
        gf.grid_columnconfigure(4, weight=1)
        # ---------------------
        
        # Volume Sensitivity Slider
        self.sens_vol = tk.IntVar(value=self.current_settings.get("sensitivity_volume",2))
        ctk.CTkLabel(gf,text="Volume Sens:").grid(row=0,column=0,padx=(8,4),pady=8,sticky="w")
        slider_vol = ctk.CTkSlider(gf, from_=2, to=10, number_of_steps=8, variable=self.sens_vol, command=lambda v: self.sens_vol_label.configure(text=f"{int(v)}x"))
        slider_vol.grid(row=0,column=1, padx=(0,8), pady=8, sticky="ew") # sticky="ew" = stretch horizontally
        self.sens_vol_label = ctk.CTkLabel(gf, width=28) # Removed textvariable so the command lambda works
        self.sens_vol_label.configure(text=f"{self.sens_vol.get()}x") # Initialize text
        self.sens_vol_label.grid(row=0,column=2, padx=(0,12))

        # Scroll Sensitivity Slider
        self.sens_scr = tk.IntVar(value=self.current_settings.get("sensitivity_scroll",1))
        ctk.CTkLabel(gf,text="Scroll Sens:").grid(row=0,column=3,padx=(8,4),pady=8,sticky="w")
        slider_scr = ctk.CTkSlider(gf, from_=1, to=10, number_of_steps=9, variable=self.sens_scr, command=lambda v: self.sens_scr_label.configure(text=f"{int(v)}x"))
        slider_scr.grid(row=0,column=4, padx=(0,8), pady=8, sticky="ew") # sticky="ew" = stretch horizontally
        self.sens_scr_label = ctk.CTkLabel(gf, width=28) # Removed textvariable
        self.sens_scr_label.configure(text=f"{self.sens_scr.get()}x") # Initialize text
        self.sens_scr_label.grid(row=0,column=5, padx=(0,12))
        
        # --- Tabs ---
        self.tabs=ctk.CTkTabview(self.left); self.tabs.pack(fill="both",expand=True,padx=12,pady=8)
        for i in (1,2,3): self.tabs.add(f"Profile {i}")
        self.tabs.set("Profile 1")
        self.profile_vars={}
        for i in (1,2,3):
            tab=self.tabs.tab(f"Profile {i}")
            tab.grid_columnconfigure(1,weight=1) # Make the dropdown fill the space
            p=self.current_settings.get(f"profile{i}",{'cw':'nothing','ccw':'nothing','click':'nothing','long_press':'nothing'})
            cw,ccw,click,longp=[tk.StringVar(value=p[k]) for k in ('cw','ccw','click','long_press')]
            self.profile_vars[i]=(cw,ccw,click,longp)
            self._profile_row(tab,"Clockwise (CW):",cw,0)
            self._profile_row(tab,"Counter-CW (CCW):",ccw,1)
            self._profile_row(tab,"Click:",click,2)
            self._profile_row(tab,"Long Press:",longp,3)
        # Collection of all option menus
        self.all_optionmenus=[]
        for i in (1,2,3):
            tab=self.tabs.tab(f"Profile {i}")
            for child in tab.winfo_children():
                if isinstance(child,ctk.CTkOptionMenu):
                    self.all_optionmenus.append(child)



    def _profile_row(self,tab,label,var,row):
        ctk.CTkLabel(tab,text=label).grid(row=row,column=0,sticky="w",padx=10,pady=(8 if row==0 else 6,6))
        ctk.CTkOptionMenu(tab,values=self.action_names,variable=var,width=280).grid(row=row,column=1,padx=8,pady=6,sticky="w")

    # ---------------- RIGHT ----------------
    def build_right(self):
        ctk.CTkLabel(self.right,text="Control & Status",font=ctk.CTkFont(size=14,weight="bold")).pack(pady=(10,6))
        # quick actions
        qf=ctk.CTkFrame(self.right); qf.pack(fill="x",padx=10,pady=(4,8))
        self.refresh_btn=ctk.CTkButton(qf,text="Find CIRCUITPY",command=self.refresh_thread); self.refresh_btn.pack(fill="x",padx=10,pady=8)
        self.reboot_port_label=ctk.CTkLabel(qf,text="Reboot port: —",anchor="w"); self.reboot_port_label.pack(fill="x",padx=10,pady=(0,8))
        # log
        lf=ctk.CTkFrame(self.right); lf.pack(fill="both",expand=True,padx=10,pady=4)
        ctk.CTkLabel(lf,text="Status Log:").pack(anchor="w",padx=10,pady=(8,2))
        self.log=ctk.CTkTextbox(lf,height=10,wrap="word"); self.log.pack(fill="both",expand=True,padx=10,pady=(0,8))
        self.log.configure(state="disabled")
        # progress + save
        pf=ctk.CTkFrame(self.right); pf.pack(fill="x",padx=10,pady=(4,8))
        self.progress=ctk.CTkProgressBar(pf); self.progress.set(0); self.progress.pack(fill="x",padx=10,pady=(10,6))
        self.save_btn=ctk.CTkButton(pf,text="Save & Reboot Pico",command=self.save_thread)
        self.save_btn.pack(fill="x",padx=10,pady=(4,10))

    # ---------------- BOTTOM ----------------
    def bottom_bar(self):
        bar=ctk.CTkFrame(self.root,height=28,corner_radius=0); bar.pack(fill="x",side="bottom")
        self.status=tk.StringVar(value="Ready.")
        ctk.CTkLabel(bar,textvariable=self.status,anchor="w").pack(side="left",padx=10)
        ctk.CTkLabel(bar,text="Dark UI",anchor="e").pack(side="right",padx=10)

    # --- Threads ---
    def save_thread(self):
        self.save_btn.configure(state="disabled"); self.refresh_btn.configure(state="disabled")
        threading.Thread(target=self._save_and_reboot,daemon=True).start()
        self.animate_progress()

    def refresh_thread(self):
        threading.Thread(target=self._refresh,daemon=True).start()

    # --- Progress animation ---
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

    # --- SAVE LOGIC ---
# --- SAVE LOGIC (FIXED - NO FALSE WARNING) ---
    def _save_and_reboot(self):
        try:
            self.set_status("Finding CIRCUITPY..."); self.log_add("Finding drive...")
            drive=find_circuitpy_drive()
            if not drive:
                self.log_add("CIRCUITPY not found."); self.set_status("Error: Drive not found")
                self.root.after(0,lambda:messagebox.showerror("Error","CIRCUITPY drive not found.")); return
            json_path=os.path.join(drive,"profiles.json")
            
            # Read values from the GUI
            s_vol=self._safe_int(self.sens_vol.get(),2)
            s_scr=self._safe_int(self.sens_scr.get(),1)
            p1,p2,p3=[{'cw':v[0].get(),'ccw':v[1].get(),'click':v[2].get(),'long_press':v[3].get()} for v in self.profile_vars.values()]
            cur_prof=1
            
            if os.path.exists(json_path):
                try:
                    with open(json_path,"r",encoding="utf-8") as f: cur_prof=json.load(f).get("current_profile",1)
                except: pass
                
            cfg={"current_profile":cur_prof,"sensitivity_volume":s_vol,"sensitivity_scroll":s_scr,"profiles":[p1,p2,p3]}
            
            # Write the file
            with open(json_path,"w",encoding="utf-8") as f: json.dump(cfg,f,indent=2,ensure_ascii=False)
            self.save_gui_settings(p1,p2,p3,s_vol,s_scr)
            self.log_add("File saved."); self.set_status("Finishing write...")
            
            # --- INCREASED WAIT TIME ---
            time.sleep(2.0) # Increased time to 2 seconds
            
            port=find_pico_serial_port_for_reboot()
            if port:
                self.reboot_port_label.configure(text=f"Reboot port: {port}")
                self.log_add(f"Rebooting via {port}..."); self.set_status("Sending reboot...")
                ok=send_reboot_command(port)
                if ok:
                    self.log_add("Reboot successful."); self.set_status("Complete.")
                    self.root.after(0,lambda:messagebox.showinfo("Success","Saved & Rebooted!"))
                else:
                    self.log_add("Failed to send reboot command."); self.set_status("Manual reboot required.")
                    self.root.after(0,lambda:messagebox.showwarning("Warning","Saved, but failed to send the reboot command."))
            else:
                # --- CHANGE HERE ---
                # We removed the messagebox.showwarning
                self.log_add("Reboot port not found (as expected)."); self.set_status("Complete.")
                # Since we know this works, just show a success message
                self.root.after(0,lambda:messagebox.showinfo("Success","Settings saved!\nThe Pico will apply them on its next reboot."))
                # ------------------
        except Exception as e:
            self.log_add(f"Error: {e}"); self.set_status("Write Error")
            self.root.after(0,lambda:messagebox.showerror("Error",f"{e}"))
        finally:
            self.root.after(0,lambda:self.save_btn.configure(state="normal"))
            self.root.after(0,lambda:self.refresh_btn.configure(state="normal"))
    # --- REFRESH ---
    def _refresh(self):
        self.set_status("Searching...")
        drive=find_circuitpy_drive()
        self.log_add(f"Drive: {drive if drive else '—'}")
        port=find_pico_serial_port_for_reboot()
        self.root.after(0,lambda:self.reboot_port_label.configure(text=f"Reboot port: {port if port else '—'}"))
        self.set_status("Ready.")

    # --- Helpers ---
    @staticmethod
    def _safe_int(v,default): 
        try: return int(v)
        except: return default

    def save_gui_settings(self,p1,p2,p3,sv,ss):
        data={'profile1':p1,'profile2':p2,'profile3':p3,'sensitivity_volume':sv,'sensitivity_scroll':ss}
        try:
            with open("configurator_settings.json","w",encoding="utf-8") as f: json.dump(data,f,indent=4,ensure_ascii=False)
        except Exception as e: self.log_add(f"Error saving GUI settings: {e}")

    def load_gui_settings(self):
        d={'profile1':{'cw':'nothing','ccw':'nothing','click':'nothing','long_press':'nothing'},
           'profile2':{'cw':'nothing','ccw':'nothing','click':'nothing','long_press':'nothing'},
           'profile3':{'cw':'nothing','ccw':'nothing','click':'nothing','long_press':'nothing'},
           'sensitivity_volume':2,'sensitivity_scroll':1}
        try:
            with open("configurator_settings.json","r",encoding="utf-8") as f: d.update(json.load(f))
        except: pass
        return d

# --- Run ---
if __name__=="__main__":
    if sys.platform=="win32":
        try: import win32api
        except: pass
    root=ctk.CTk(); app=MultiKnobConfiguratorModern(root); root.mainloop()