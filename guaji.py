import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
import threading
import time
import random
import math
import json
from pynput.mouse import Controller
from pynput.keyboard import Listener as KeyboardListener, Key, HotKey, GlobalHotKeys
import gc

# 尝试解决 Windows 下 Tkinter 界面模糊的问题
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class IdleMouseBotApp:
    def __init__(self, root):
        self.root = root
        
        # --- 颜色主题设置 ---
        self.colors = {
            "bg": "#1E1E1E",            # 主背景
            "panel": "#252526",         # 面板背景
            "input": "#3C3C3C",         # 输入框背景
            "text": "#D4D4D4",          # 常规文字
            "text_hl": "#FFFFFF",       # 高亮文字
            "btn_bg": "#333333",        # 按钮默认背景
            "btn_hover": "#444444",     # 按钮悬停背景
            "btn_primary": "#0E639C",   # 主按钮(蓝)
            "btn_success": "#238636",   # 开始按钮(绿)
            "btn_danger": "#DA3633",    # 停止/删除按钮(红)
            "title_bar": "#2D2D30",     # 标题栏背景
            "title_btn": "#2D2D30",     # 标题栏按钮背景
            "title_btn_hover": "#3E3E42", # 标题栏按钮悬停色
            "float_normal": "#238636",  # 浮窗停止时绿色
            "float_running": "#DA3633", # 浮窗运行时红色
            "float_hover": "#444444"    # 浮窗悬停时颜色
        }

        self.is_maximized = False
        self.normal_geometry = "350x250" 

        self.root.title("鼠标挂机工具")
        self.root.geometry(self.normal_geometry)
        self.root.configure(bg=self.colors["bg"])
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app) # 确保关闭按钮绑定到close_app

        self.mouse = Controller()
        self.idle_thread = None
        self.idle_running = False

        self.idle_time_var = tk.IntVar(value=10)

        # 快捷键设置，Esc现在只用于停止挂机，不再退出应用
        self.key_bindings = {
            "start_stop": ["<f3>"],   # 默认F3开始/停止
            "stop_idle_only": ["<esc>"] # 默认Esc只停止挂机
        }
        self.load_key_bindings()

        self.resizing = False
        self.resize_edge = None

        self.setup_styles()
        self.build_title_bar()
        self.build_ui()

        self.key_listener_thread = None
        self.start_global_key_listener()

        # --- 浮窗相关 ---
        self.float_window = None
        self.float_label = None

        # 绑定最小化和最大化事件，以便控制浮窗显示
        self.root.bind("<Unmap>", self.on_minimize)
        self.root.bind("<Map>", self.on_restore)


    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("TCombobox", fieldbackground=self.colors["input"], background=self.colors["btn_bg"], foreground=self.colors["text_hl"], arrowcolor=self.colors["text"])
        style.map('TCombobox', fieldbackground=[('readonly', self.colors["input"])], selectbackground=[('readonly', self.colors["btn_primary"])], selectforeground=[('readonly', self.colors["text_hl"])])

        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("TFrame", background=self.colors["panel"])
        
    # ================= 标题栏逻辑 (不变) =================
    def build_title_bar(self):
        self.title_bar = tk.Frame(self.root, bg=self.colors["title_bar"], relief='flat', bd=0, height=32)
        self.title_bar.pack(fill='x', side='top')
        self.title_bar.pack_propagate(False)

        tk.Label(self.title_bar, text="🖱️", bg=self.colors["title_bar"], fg="#0E639C", font=("Segoe UI Emoji", 11)).pack(side='left', padx=8)
        title_lbl = tk.Label(self.title_bar, text="鼠标挂机工具", bg=self.colors["title_bar"], fg=self.colors["text_hl"], font=("微软雅黑", 9))
        title_lbl.pack(side='left', padx=2)

        btn_width = 4
        btn_font = ("微软雅黑", 10)
        
        btn_close = tk.Button(self.title_bar, text="✕", bg=self.colors["title_btn"], fg=self.colors["text"], bd=0, font=btn_font, width=btn_width, command=self.close_app)
        btn_close.pack(side='right', fill='y')
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=self.colors["btn_danger"], fg="white"))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=self.colors["title_btn"], fg=self.colors["text"]))

        self.btn_max = tk.Button(self.title_bar, text="☐", bg=self.colors["title_btn"], fg=self.colors["text"], bd=0, font=btn_font, width=btn_width, command=self.toggle_maximize)
        self.btn_max.pack(side='right', fill='y')
        self.btn_max.bind("<Enter>", lambda e: self.btn_max.config(bg=self.colors["title_btn_hover"]))
        self.btn_max.bind("<Leave>", lambda e: self.btn_max.config(bg=self.colors["title_btn"]))

        btn_min = tk.Button(self.title_bar, text="—", bg=self.colors["title_btn"], fg=self.colors["text"], bd=0, font=btn_font, width=btn_width, command=self.minimize_window)
        btn_min.pack(side='right', fill='y')
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg=self.colors["title_btn_hover"]))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=self.colors["title_btn"]))

        self.title_bar.bind("<Button-1>", self.start_move)
        title_lbl.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        title_lbl.bind("<B1-Motion>", self.do_move)
        self.title_bar.bind("<Double-Button-1>", lambda e: self.toggle_maximize())
        title_lbl.bind("<Double-Button-1>", lambda e: self.toggle_maximize())

        self.setup_resize_borders()

    def toggle_maximize(self):
        if self.is_maximized:
            self.root.geometry(self.normal_geometry)
            self.btn_max.config(text="☐")
            self.is_maximized = False
        else:
            self.normal_geometry = self.root.geometry()
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_w}x{screen_h}+0+0")
            self.btn_max.config(text="❐")
            self.is_maximized = True

    def setup_resize_borders(self):
        grips =[
            ("top", "size_ns", "n", 0, 0, 1.0, 0, 5), ("bottom", "size_ns", "s", 0, 1.0, 1.0, 0, 5),
            ("left", "size_we", "w", 0, 0, 0, 1.0, 5), ("right", "size_we", "e", 1.0, 0, 0, 1.0, 5),
            ("top_left", "size_nw_se", "nw", 0, 0, 0, 0, 10), ("top_right", "size_ne_sw", "ne", 1.0, 0, 0, 0, 10),
            ("bottom_left", "size_ne_sw", "sw", 0, 1.0, 0, 0, 10), ("bottom_right", "size_nw_se", "se", 1.0, 1.0, 0, 0, 10)
        ]
        for name, cursor, anchor, relx, rely, relw, relh, size in grips:
            f = tk.Frame(self.root, cursor=cursor, bg=self.colors["bg"])
            if relw > 0: f.place(relx=relx, rely=rely, relwidth=relw, height=size, anchor=anchor)
            elif relh > 0: f.place(relx=relx, rely=rely, relheight=relh, width=size, anchor=anchor)
            else: f.place(relx=relx, rely=rely, width=size, height=size, anchor=anchor)
            
            f.bind("<Button-1>", lambda e, dir=name: self.begin_resize(e, dir))
            f.bind("<B1-Motion>", self.perform_resize)
            f.lift()

    def begin_resize(self, event, dir):
        if self.is_maximized: return
        self.resize_dir = dir
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.win_x, self.win_y = self.root.winfo_rootx(), self.root.winfo_rooty()
        self.win_w, self.win_h = self.root.winfo_width(), self.root.winfo_height()

    def perform_resize(self, event):
        if self.is_maximized: return
        dx, dy = event.x_root - self.start_x, event.y_root - self.start_y
        x, y, w, h = self.win_x, self.win_y, self.win_w, self.win_h
        min_w, min_h = 300, 200

        if "left" in self.resize_dir:
            nw = max(min_w, w - dx)
            x, w = x + (w - nw), nw
        elif "right" in self.resize_dir: w = max(min_w, w + dx)

        if "top" in self.resize_dir:
            nh = max(min_h, h - dy)
            y, h = y + (h - nh), nh
        elif "bottom" in self.resize_dir: h = max(min_h, h + dy)

        self.root.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
        self.root.update_idletasks()

    def close_app(self):
        self.stop_global_key_listener()
        self.idle_running = False
        if self.idle_thread and self.idle_thread.is_alive():
            self.idle_thread.join(timeout=0.5)
        
        if self.float_window: # 关闭浮窗
            self.float_window.destroy()
        self.root.destroy()

    def minimize_window(self):
        self.root.withdraw() # 隐藏主窗口
        self.show_float_window() # 显示浮窗

    def on_minimize(self, event=None):
        # 当窗口被最小化（Unmap）时触发
        # 这个事件在 Windows 下可能不会准确在最小化按钮点击时触发，
        # 但 withdraw() 肯定会隐藏窗口
        if self.root.winfo_exists() and self.root.winfo_viewable(): # 检查窗口是否可见
             pass # 如果可见，说明不是最小化到托盘，不处理
        else:
             self.root.withdraw() # 确保隐藏主窗口
             self.show_float_window() # 显示浮窗

    def on_restore(self, event=None):
        # 当窗口被恢复（Map）时触发
        if self.float_window and self.float_window.winfo_exists():
            self.float_window.destroy() # 销毁浮窗
        self.root.deiconify() # 显示主窗口
        self.root.attributes('-topmost', True) # 恢复置顶

    def start_move(self, event):
        if self.is_maximized: return
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        if self.is_maximized: return
        deltax, deltay = event.x - self.x, event.y - self.y
        self.root.geometry(f"+{self.root.winfo_x() + deltax}+{self.root.winfo_y() + deltay}")   

    # ================= 浮窗逻辑 =================
    def show_float_window(self):
        if self.float_window and self.float_window.winfo_exists():
            return # 如果浮窗已存在，则不创建

        self.float_window = Toplevel(self.root)
        self.float_window.overrideredirect(True) # 无边框
        self.float_window.attributes('-topmost', True) # 置顶
        self.float_window.resizable(False, False)
        self.float_window.wm_attributes("-alpha", 0.9) # 设置透明度

        # 浮窗尺寸
        float_width = 100
        float_height = 30

        # 计算浮窗位置 (左下角)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = 10 # 距离左侧10px (挨着屏幕左边缘)
        pos_y = screen_h - float_height - 50 # 距离底部50px (避开任务栏，如果觉得高了可以把50改小，比如40)
        self.float_window.geometry(f"{float_width}x{float_height}+{pos_x}+{pos_y}")

        self.float_label = tk.Label(self.float_window, text="挂机中", font=("微软雅黑", 10, "bold"), fg="white")
        self.float_label.pack(fill='both', expand=True)
        self.update_float_window_status() # 更新浮窗状态

        self.float_label.bind("<Button-1>", self.restore_main_window_from_float) # 点击恢复主窗口
        self.float_label.bind("<Button-3>", self.show_float_context_menu) # 右键菜单
        self.float_label.bind("<Enter>", self.on_float_enter)
        self.float_label.bind("<Leave>", self.on_float_leave)
        
        # 允许浮窗拖动
        self.float_window.bind("<Button-1>", self.start_float_move)
        self.float_window.bind("<B1-Motion>", self.do_float_move)

    def update_float_window_status(self):
        if self.float_label:
            if self.idle_running:
                self.float_label.config(text="挂机中...", bg=self.colors["float_running"])
            else:
                self.float_label.config(text="已停止", bg=self.colors["float_normal"])

    def restore_main_window_from_float(self, event=None):
        if self.float_window and self.float_window.winfo_exists():
            self.float_window.destroy()
        self.root.deiconify() # 恢复主窗口
        self.root.attributes('-topmost', True) # 恢复置顶

    def show_float_context_menu(self, event):
        menu = tk.Menu(self.float_window, tearoff=0, bg=self.colors["panel"], fg=self.colors["text_hl"])
        menu.add_command(label="显示主窗口", command=self.restore_main_window_from_float)
        menu.add_separator()
        menu.add_command(label="退出应用", command=self.close_app, fg=self.colors["btn_danger"])
        menu.tk_popup(event.x_root, event.y_root)

    def on_float_enter(self, event):
        if self.float_label:
            self.float_label.config(bg=self.colors["float_hover"])

    def on_float_leave(self, event):
        self.update_float_window_status() # 恢复为根据状态显示的颜色

    def start_float_move(self, event):
        self.float_x = event.x
        self.float_y = event.y

    def do_float_move(self, event):
        deltax = event.x - self.float_x
        deltay = event.y - self.float_y
        self.float_window.geometry(f"+{self.float_window.winfo_x() + deltax}+{self.float_window.winfo_y() + deltay}")

    # ================= 界面构建 =================
    def build_ui(self):
        main_container = tk.Frame(self.root, bg=self.colors["bg"])
        main_container.pack(fill='both', expand=True, padx=15, pady=5)

        # 顶部操作区 (快捷键设置)
        top_frame = tk.Frame(main_container, bg=self.colors["bg"])
        top_frame.pack(fill='x', pady=5)

        # "Esc 停止挂机" 提示
        self.stop_idle_key_label = tk.Label(top_frame, text=f"停止挂机: {self.key_to_display(self.key_bindings['stop_idle_only'])}", bg=self.colors["bg"], fg=self.colors["text"], font=("微软雅黑", 10))
        self.stop_idle_key_label.pack(side='left', padx=(0, 10))

        # 设置按钮
        settings_btn = tk.Button(top_frame, text="设置", bg=self.colors["btn_bg"], fg=self.colors["text"], font=("微软雅黑", 10),
                                 bd=0, padx=10, pady=5, command=self.open_settings_window)
        settings_btn.pack(side='right')
        settings_btn.bind("<Enter>", lambda e: settings_btn.config(bg=self.colors["btn_hover"]))
        settings_btn.bind("<Leave>", lambda e: settings_btn.config(bg=self.colors["btn_bg"]))

        # 开始/停止大按钮
        self.start_stop_btn = tk.Button(main_container, text="开始", bg=self.colors["btn_success"], fg="white",
                                        font=("微软雅黑", 24, "bold"), bd=0, relief="flat", command=self.toggle_idle_bot)
        self.start_stop_btn.pack(fill='both', expand=True, pady=10)
        self.start_stop_btn.bind("<Enter>", self.on_start_stop_btn_hover)
        self.start_stop_btn.bind("<Leave>", self.on_start_stop_btn_leave)

        # 间隔时间设置
        interval_frame = tk.Frame(main_container, bg=self.colors["bg"])
        interval_frame.pack(fill='x', pady=5)
        
        interval_label = tk.Label(interval_frame, text="间隔时间(秒):", bg=self.colors["bg"], fg=self.colors["text"], font=("微软雅黑", 12))
        interval_label.pack(side='left', padx=(0, 5))
        
        self.interval_entry = self.create_entry(interval_frame, self.idle_time_var, width=8)
        self.interval_entry.pack(side='left')

        # 居中对齐间隔时间输入框
        interval_frame.pack_configure(anchor='center')

    def on_start_stop_btn_hover(self, event):
        if self.idle_running:
            self.start_stop_btn.config(bg="#B32F2D")
        else:
            self.start_stop_btn.config(bg="#1E6E2D")
    
    def on_start_stop_btn_leave(self, event):
        if self.idle_running:
            self.start_stop_btn.config(bg=self.colors["btn_danger"])
        else:
            self.start_stop_btn.config(bg=self.colors["btn_success"])

    def create_entry(self, parent, var, width):
        return tk.Entry(parent, textvariable=var, width=width, bg=self.colors["input"], fg=self.colors["text_hl"], insertbackground="white", relief="flat", font=("微软雅黑", 10), justify='center')

    # ================= 鼠标贝塞尔曲线模拟 (不变) =================
    def bezier_move(self, start_pos, end_pos, duration=1.0):
        x1, y1 = start_pos
        x2, y2 = end_pos
        
        cp_x = x1 + (x2 - x1) * 0.3 + random.randint(-80, 80)
        cp_y = y1 + (y2 - y1) * 0.3 + random.randint(-80, 80)
        
        sleep_time = 0.015
        steps = int(duration / sleep_time)
        if steps < 1: steps = 1
        
        for i in range(1, steps + 1):
            if not self.idle_running: break
            
            t = i / steps
            t = 1 - (1 - t) ** 3 
            
            bx = (1-t)**2 * x1 + 2*(1-t)*t * cp_x + t**2 * x2
            by = (1-t)**2 * y1 + 2*(1-t)*t * cp_y + t**2 * y2
            
            self.mouse.position = (int(bx), int(by))
            time.sleep(sleep_time)

    # ================= 挂机任务逻辑 =================
    def toggle_idle_bot(self):
        if not self.idle_running:
            self.idle_running = True
            self.start_stop_btn.config(text="停止", bg=self.colors["btn_danger"])
            self.idle_thread = threading.Thread(target=self.idle_loop, daemon=True)
            self.idle_thread.start()
            self.update_float_window_status() # 更新浮窗状态
        else:
            self.stop_idle_now() # 调用单独的停止函数

    def stop_idle_now(self):
        # 专门用于停止挂机的函数，例如被Esc键调用
        if self.idle_running:
            self.idle_running = False
            self.start_stop_btn.config(text="开始", bg=self.colors["btn_success"])
            self.update_float_window_status() # 更新浮窗状态
            gc.collect()

    def idle_loop(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        while self.idle_running:
            try:
                wait_time = int(self.idle_time_var.get())
            except tk.TclError:
                wait_time = 10
            if wait_time <= 0: wait_time = 10
            
            steps = int(wait_time / 0.5)
            for _ in range(steps):
                if not self.idle_running: return
                time.sleep(0.5)
            
            if not self.idle_running: break
            
            move_count = random.randint(2, 4)
            time_per_move = (3.0 - (move_count * 0.2)) / move_count 
            if time_per_move < 0.1: time_per_move = 0.1

            for _ in range(move_count):
                if not self.idle_running: break
                start_pos = self.mouse.position
                end_pos = (random.randint(0, screen_w), random.randint(0, screen_h)) 
                
                self.bezier_move(start_pos, end_pos, duration=time_per_move)
                
                if not self.idle_running: break
                time.sleep(random.uniform(0.1, 0.3))
            
            gc.collect(0)
            gc.collect(1)
            gc.collect(2)

    # ================= 快捷键管理 =================
    def key_to_display(self, key_binding_list):
        if not key_binding_list:
            return "未设置"

        display_parts = []
        for key_item in key_binding_list:
            if isinstance(key_item, Key):
                if key_item == Key.ctrl_l: display_parts.append("Ctrl")
                elif key_item == Key.alt_l: display_parts.append("Alt")
                elif key_item == Key.shift_l: display_parts.append("Shift")
                elif key_item == Key.esc: display_parts.append("Esc")
                elif key_item == Key.f3: display_parts.append("F3")
                else: display_parts.append(str(key_item).replace('Key.', '').capitalize())
            elif isinstance(key_item, str):
                s = key_item.strip('<>').replace('_l', '').replace('_r', '').capitalize()
                if s == 'F3': display_parts.append("F3")
                elif s == 'Esc': display_parts.append("Esc")
                elif s == 'Ctrl': display_parts.append("Ctrl")
                elif s == 'Alt': display_parts.append("Alt")
                elif s == 'Shift': display_parts.append("Shift")
                else: display_parts.append(s)
        return "+".join(sorted(list(set(display_parts)), key=lambda x: ('Ctrl' not in x, 'Alt' not in x, 'Shift' not in x, x)))


    def load_key_bindings(self):
        try:
            with open("key_bindings.json", "r") as f:
                loaded_bindings = json.load(f)
                
                for key_type, keys_str_list in loaded_bindings.items():
                    if key_type in self.key_bindings:
                        self.key_bindings[key_type] = keys_str_list
                
        except FileNotFoundError:
            self.save_key_bindings()
        except Exception as e:
            messagebox.showerror("错误", f"加载快捷键设置失败: {e}")
            self.key_bindings = { # 恢复默认值
                "start_stop": ["<f3>"],
                "stop_idle_only": ["<esc>"] 
            }
            self.save_key_bindings()


    def save_key_bindings(self):
        try:
            savable_bindings = {}
            for key, value in self.key_bindings.items():
                savable_bindings[key] = value
            
            with open("key_bindings.json", "w") as f:
                json.dump(savable_bindings, f, indent=4)
        except Exception as e:
            messagebox.showerror("错误", f"保存快捷键设置失败: {e}")

    def start_global_key_listener(self):
        self.stop_global_key_listener()

        def format_for_hotkey_string(keys_list):
            formatted_parts = []
            for key_item in keys_list:
                part = ""
                if isinstance(key_item, Key):
                    part = str(key_item).replace('Key.', '')
                elif isinstance(key_item, str):
                    part = key_item.strip('<>').lower()
                
                if part == 'ctrl_l': part = 'ctrl'
                if part == 'alt_l': part = 'alt'
                if part == 'shift_l': part = 'shift'

                if len(part) > 1 and part not in ['ctrl', 'alt', 'shift']:
                    formatted_parts.append(f"<{part}>")
                elif part in ['ctrl', 'alt', 'shift']:
                    formatted_parts.append(part)
                elif len(part) == 1 and (part.isalpha() or part.isdigit()):
                    formatted_parts.append(part)
                else: 
                    formatted_parts.append(f"<{part}>")

            sorted_unique_parts = []
            for mod_key in ['ctrl', 'alt', 'shift']:
                if mod_key in formatted_parts:
                    sorted_unique_parts.append(mod_key)
                    formatted_parts.remove(mod_key)

            remaining_keys = sorted(list(set(formatted_parts)))
            sorted_unique_parts.extend(remaining_keys)

            return '+'.join(sorted_unique_parts)


        hotkeys_dict = {
            format_for_hotkey_string(self.key_bindings["start_stop"]): lambda: self.root.after(0, self.toggle_idle_bot),
            format_for_hotkey_string(self.key_bindings["stop_idle_only"]): lambda: self.root.after(0, self.stop_idle_now)
        }
        
        self.key_listener_thread = GlobalHotKeys(hotkeys_dict)
        self.key_listener_thread.start()

    def stop_global_key_listener(self):
        if self.key_listener_thread and self.key_listener_thread.is_alive():
            self.key_listener_thread.stop()
            self.key_listener_thread.join(timeout=0.5)

    # ================= 设置窗口 =================
    def open_settings_window(self):
        settings_win = Toplevel(self.root)
        settings_win.title("快捷键设置")
        settings_win.transient(self.root)
        settings_win.grab_set()
        settings_win.resizable(False, False)
        settings_win.attributes('-topmost', True)
        settings_win.configure(bg=self.colors["panel"])
        
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (settings_win.winfo_reqwidth() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (settings_win.winfo_reqheight() // 2)
        settings_win.geometry(f"+{x}+{y}")

        tk.Label(settings_win, text="请按下新的快捷键，最多支持 3 个组合键。\n(按下Esc取消本次设置)", bg=self.colors["panel"], fg=self.colors["text"], font=("微软雅黑", 10)).pack(pady=10)

        # 开始/停止快捷键设置
        start_stop_frame = tk.Frame(settings_win, bg=self.colors["panel"])
        start_stop_frame.pack(pady=5, padx=10, fill='x')
        tk.Label(start_stop_frame, text="开始/停止:", bg=self.colors["panel"], fg=self.colors["text"], font=("微软雅黑", 10)).pack(side='left', padx=5)
        
        self.start_stop_display_lbl = tk.Label(start_stop_frame, text=self.key_to_display(self.key_bindings["start_stop"]), bg=self.colors["input"], fg=self.colors["text_hl"], width=15, relief='flat', font=("微软雅黑", 10))
        self.start_stop_display_lbl.pack(side='left', padx=5)
        
        set_start_btn = tk.Button(start_stop_frame, text="修改", bg=self.colors["btn_primary"], fg="white", font=("微软雅黑", 10), bd=0, padx=8,
                                  command=lambda: self.capture_key(settings_win, self.start_stop_display_lbl, "start_stop"))
        set_start_btn.pack(side='left', padx=5)
        set_start_btn.bind("<Enter>", lambda e: set_start_btn.config(bg=self.colors["btn_hover"]))
        set_start_btn.bind("<Leave>", lambda e: set_start_btn.config(bg=self.colors["btn_primary"]))


        # 停止挂机快捷键设置 (新的)
        stop_idle_frame = tk.Frame(settings_win, bg=self.colors["panel"])
        stop_idle_frame.pack(pady=5, padx=10, fill='x')
        tk.Label(stop_idle_frame, text="停止挂机:", bg=self.colors["panel"], fg=self.colors["text"], font=("微软雅黑", 10)).pack(side='left', padx=5)
        
        self.stop_idle_display_lbl = tk.Label(stop_idle_frame, text=self.key_to_display(self.key_bindings["stop_idle_only"]), bg=self.colors["input"], fg=self.colors["text_hl"], width=15, relief='flat', font=("微软雅黑", 10))
        self.stop_idle_display_lbl.pack(side='left', padx=5)
        
        set_stop_idle_btn = tk.Button(stop_idle_frame, text="修改", bg=self.colors["btn_primary"], fg="white", font=("微软雅黑", 10), bd=0, padx=8,
                                 command=lambda: self.capture_key(settings_win, self.stop_idle_display_lbl, "stop_idle_only"))
        set_stop_idle_btn.pack(side='left', padx=5)
        set_stop_idle_btn.bind("<Enter>", lambda e: set_stop_idle_btn.config(bg=self.colors["btn_hover"]))
        set_stop_idle_btn.bind("<Leave>", lambda e: set_stop_idle_btn.config(bg=self.colors["btn_primary"]))


        # 确认按钮
        confirm_btn = tk.Button(settings_win, text="确定", bg=self.colors["btn_success"], fg="white", font=("微软雅黑", 10, "bold"), bd=0, padx=15, pady=5,
                                command=lambda: self.confirm_settings(settings_win))
        confirm_btn.pack(pady=15)
        confirm_btn.bind("<Enter>", lambda e: confirm_btn.config(bg="#1E6E2D"))
        confirm_btn.bind("<Leave>", lambda e: confirm_btn.config(bg=self.colors["btn_success"]))

    def capture_key(self, parent_window, display_label, key_type):
        """打开一个临时窗口捕获用户按下的快捷键"""
        capture_win = Toplevel(parent_window)
        capture_win.title("按下快捷键...")
        capture_win.transient(parent_window)
        capture_win.grab_set()
        capture_win.resizable(False, False)
        capture_win.attributes('-topmost', True)
        capture_win.configure(bg=self.colors["panel"])
        
        self.root.update_idletasks()
        x = parent_window.winfo_x() + (parent_window.winfo_width() // 2) - (capture_win.winfo_reqwidth() // 2)
        y = parent_window.winfo_y() + (parent_window.winfo_height() // 2) - (capture_win.winfo_reqheight() // 2)
        capture_win.geometry(f"+{x}+{y}")

        tk.Label(capture_win, text="请按下您要设置的快捷键 (最多3个组合键)\n按下 Esc 取消", bg=self.colors["panel"], fg=self.colors["text"], font=("微软雅黑", 10)).pack(pady=10, padx=20)
        
        current_pressed_keys = set()
        
        def on_press(key):
            try:
                if isinstance(key, Key):
                    key_str = str(key).replace('Key.', '')
                else:
                    key_str = key.char
                
                if key_str == 'ctrl_l': key_str = 'ctrl'
                if key_str == 'alt_l': key_str = 'alt'
                if key_str == 'shift_l': key_str = 'shift'

                if key_str not in current_pressed_keys:
                    current_pressed_keys.add(key_str)

                if key == Key.esc: # Esc在这里是取消捕获
                    listener.stop()
                    capture_win.destroy()
                    return False
                
                if len(current_pressed_keys) > 3:
                    messagebox.showwarning("警告", "最多支持3个组合键，已自动截断。")
                    listener.stop()
                    process_keys()
                    return False

            except AttributeError:
                pass
            return True

        def on_release(key):
            if key == Key.esc:
                return False

            try:
                if isinstance(key, Key):
                    key_str = str(key).replace('Key.', '')
                else:
                    key_str = key.char
                
                if key_str == 'ctrl_l': key_str = 'ctrl'
                if key_str == 'alt_l': key_str = 'alt'
                if key_str == 'shift_l': key_str = 'shift'

                if key_str in current_pressed_keys:
                    current_pressed_keys.remove(key_str)

                if not current_pressed_keys:
                    listener.stop()
                    process_keys()
                    return False

            except AttributeError:
                pass
            return True

        def process_keys():
            if not current_pressed_keys:
                messagebox.showwarning("警告", "未检测到有效快捷键，请至少按下并松开一个键。")
                capture_win.destroy()
                return

            sorted_keys = []
            for mod_key in ['ctrl', 'alt', 'shift']:
                if mod_key in current_pressed_keys:
                    sorted_keys.append(mod_key)
            
            for other_key in sorted(current_pressed_keys - {'ctrl', 'alt', 'shift'}):
                sorted_keys.append(other_key)

            new_binding = []
            for k_str in sorted_keys:
                if k_str in ['ctrl', 'alt', 'shift']: # 修饰键不带尖括号
                    new_binding.append(k_str)
                elif len(k_str) == 1 and (k_str.isalpha() or k_str.isdigit()): # 单个字母或数字不带尖括号
                    new_binding.append(k_str.lower())
                else: # 其他特殊键（包括F键，esc）带尖括号
                    new_binding.append(f"<{k_str}>")

            self.key_bindings[key_type] = new_binding

            # 更新 UI 显示
            display_label.config(text=self.key_to_display(self.key_bindings[key_type]))
            self.stop_idle_key_label.config(text=f"停止挂机: {self.key_to_display(self.key_bindings['stop_idle_only'])}") # 更新主界面显示
            
            self.save_key_bindings()
            self.start_global_key_listener()
            capture_win.destroy()

        listener = KeyboardListener(on_press=on_press, on_release=on_release)
        listener.start()
        capture_win.protocol("WM_DELETE_WINDOW", lambda: (listener.stop(), capture_win.destroy()))
        self.root.wait_window(capture_win)

    def confirm_settings(self, settings_win):
        settings_win.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = IdleMouseBotApp(root)
    root.mainloop()