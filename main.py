import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import pygame

try:
    from PIL import Image, ImageTk, ImageOps

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: PIL/Pillow 未安装，图像功能将不可用")

try:
    import win32com.client

    HAS_SPEECH = True
except ImportError:
    HAS_SPEECH = False
    print("警告: win32com 未安装，COM相关功能将不可用")

pygame.mixer.init()


class FitnessAppUI:
    def __init__(self, root):
        """初始化FitnessAppUI类，设置主窗口、颜色、路径、状态变量等"""
        self.root = root
        # 窗口基本设置
        self.root.title("FITNESS APP")
        self.root.geometry("500x800")
        self.root.resizable(False, False)

        # 配色方案
        self.colors = {
            # 背景色
            "bg": "#fcecf9",           # 主窗口背景
            "card_bg": "#acd1ff",      # 卡片背景

            # 按钮颜色
            "button_bg": "#ffffff",    # 按钮背景（常态）
            "button_hover": "#ffe5f4", # 按钮背景（悬停）
            "button_fg": "#4a4d5e",    # 按钮文字

            # 功能色（常态）
            "primary": "#8badfc",  # 主色调
            "danger": "#ff91b4",   # 危险色
            "success": "#00b894",  # 成功色

            # 功能色（悬停）
            "primary_hover": "#add2ff",  # 主色调悬停
            "danger_hover": "#f9b2c8",  # 危险色悬停

            # 功能色（按下）
            "primary_active": "#6b8edf",   # 主色调按下
            "danger_active": "#e47296",    # 危险色按下

            # 文字色
            "text": "#ffffff",         # 主要文字
            "sub_text": "#797777",     # 次要文字

            # 边框
            "border": "#404040"

        }
        self.root.configure(bg=self.colors["bg"])

        # 路径设置
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.base_dir, "data")
        
        # 资源文件夹路径
        self.assets_dir = os.path.join(self.base_dir, "assets")
        self.images_dir = os.path.join(self.assets_dir, "images")
        self.audio_dir = os.path.join(self.assets_dir, "audio")

        # 训练脚本路径
        self.squat_script = os.path.join(self.base_dir, "squat_counter.py")
        self.pushup_script = os.path.join(self.base_dir, "pushup_counter.py")

        # 背景音乐文件路径
        self.squat_music = os.path.join(self.audio_dir, "squat_music.mp3")
        self.pushup_music = os.path.join(self.audio_dir, "pushup_music.mp3")

        # 进程和状态变量
        self.current_process = None
        self.current_name = None
        self.current_music = None
        self.music_enabled = True
        self.music_volume = 0.5

        # 倒计时相关变量
        self.countdown_seconds = 0
        self.remaining_seconds = 0
        self.countdown_active = False
        self.countdown_job = None
        self.elapsed_seconds = 0

        # 信号文件路径
        self.signal_file = os.path.join(self.data_dir, ".start_signal")
        self.stop_signal_file = os.path.join(self.data_dir, ".stop_signal")
        self.signal_check_job = None

        # 初始化语音引擎
        self.speaker = None
        if HAS_SPEECH:
            try:
                self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
                self.speaker.Rate = 0
            except Exception as e:
                print(f"语音引擎初始化失败: {e}")
                self.speaker = None

        # 防止重复处理退出的标志
        self.exit_handling = False

        # 加载图标资源
        self.icons = {}
        if HAS_PIL:
            self.set_window_icon()
            self._load_icon("squat", "squat.png")
            self._load_icon("pushup", "pushup.png")

        # 创建UI界面
        self._create_ui()

        # 启动进程状态轮询
        self.root.after(200, self._poll_process)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_ui(self):
        """创建主界面布局"""
        # 顶部标题栏
        header_frame = tk.Frame(self.root, bg=self.colors["primary"], height=60)
        header_frame.pack(fill="x")

        title_label = tk.Label(
            header_frame,
            text="健身计数器",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="white",
            bg=self.colors["primary"]
        )
        title_label.pack(pady=15)
 
        # 核心功能区
        action_frame = tk.Frame(self.root, bg=self.colors["bg"])
        action_frame.pack(pady=(30, 10))

        # 按钮样式定义
        btn_style = {
            "font": ("Microsoft YaHei UI", 12, "bold"),
            "bg": self.colors["button_bg"],
            "fg": self.colors["button_fg"],
            "activebackground": self.colors["button_hover"],
            "activeforeground": self.colors["button_fg"],
            "relief": "flat",
            "bd": 1,
            "highlightthickness": 1,
            "highlightbackground": self.colors["border"],
            "highlightcolor": self.colors["border"],
            "compound": "top",
            "width": 180 if HAS_PIL else 20,
            "height": 180 if HAS_PIL else 2,
            "cursor": "hand2"
        }

        # 深蹲按钮
        self.btn_squat = tk.Button(
            action_frame,
            text="\n深蹲训练",
            command=lambda: self.start_script(self.squat_script, "深蹲"),
            **btn_style
        )
        if "squat" in self.icons:
            self.btn_squat.config(image=self.icons["squat"])
        self.btn_squat.grid(row=0, column=0, padx=15)

        # 俯卧撑按钮
        self.btn_pushup = tk.Button(
            action_frame,
            text="\n俯卧撑训练",
            command=lambda: self.start_script(self.pushup_script, "俯卧撑"),
            **btn_style
        )
        if "pushup" in self.icons:
            self.btn_pushup.config(image=self.icons["pushup"])
        self.btn_pushup.grid(row=0, column=1, padx=15)

        # 倒计时显示容器
        self.status_container = tk.Frame(self.root, bg=self.colors["bg"])
        self.status_container.pack(pady=0, fill="x")

        # 倒计时显示标签
        self.countdown_label = tk.Label(
            self.status_container,
            text="",
            font=("Microsoft YaHei UI", 30, "bold"),
            fg=self.colors["primary"],
            bg=self.colors["bg"]
        )
        self.countdown_label.pack()

        # 倒计时设置区域
        self._add_countdown_controls()

        # 音乐设置区域
        self.add_music_controls()

        # 操作按钮区
        button_container = tk.Frame(self.root, bg=self.colors["bg"])
        button_container.pack(pady=10, fill="x")

        # 重置按钮
        self.btn_reset = tk.Button(
            button_container,
            text="↺ 重置计数",
            font=("Microsoft YaHei UI", 11),
            bg=self.colors["primary"],
            fg=self.colors["button_fg"],
            activebackground=self.colors["primary_active"],
            activeforeground=self.colors["button_fg"],
            command=self.reset_current,
            width=35,
            pady=8,
            relief="groove",
            cursor="hand2",
            bd=1
        )
        self.btn_reset.pack(pady=(0, 8))

        # 退出按钮
        self.btn_stop = tk.Button(
            button_container,
            text="⏹ 退出训练",
            font=("Microsoft YaHei UI", 11),
            bg=self.colors["danger"],
            fg=self.colors["button_fg"],
            activebackground=self.colors["danger_active"],
            activeforeground=self.colors["button_fg"],
            command=self.stop_current,
            width=35,
            pady=8,
            relief="groove",
            cursor="hand2",
            bd=1
        )
        self.btn_stop.pack()

        # 为按钮添加悬停效果
        self.add_hover_effects()

        # 启动进程状态轮询和窗口关闭处理
        self.root.after(200, self._poll_process)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_hover_effects(self):
        """为所有按钮添加悬停效果"""
        def add_effect(button, normal_color, hover_color):
            def on_enter(e):
                button.config(bg=hover_color)

            def on_leave(e):
                button.config(bg=normal_color)

            button.bind("<Enter>", on_enter)
            button.bind("<Leave>", on_leave)

        # 重置按钮悬停效果
        add_effect(
            self.btn_reset,
            self.colors["primary"],
            self.colors["primary_hover"]
        )

        # 退出按钮悬停效果
        add_effect(
            self.btn_stop,
            self.colors["danger"],
            self.colors["danger_hover"]
        )

    def set_window_icon(self):
        """设置主窗口图标"""
        if not HAS_PIL:
            return

        icon_path = os.path.join(self.images_dir, "icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                icon_photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, icon_photo)
                self.window_icon = icon_photo
            except Exception as e:
                print(f"设置图标失败: {e}")


    def _load_icon(self, name, filename):
        """加载并处理图标文件"""
        path = os.path.join(self.images_dir, filename)
        if not os.path.exists(path):
            return

        try:
            img = Image.open(path)
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            target = 120
            img.thumbnail((target, target), Image.Resampling.LANCZOS)

            canvas = Image.new("RGBA", (target, target), (255, 255, 255, 255))
            x = (target - img.width) // 2
            y = (target - img.height) // 2
            canvas.paste(img, (x, y), img if img.mode in ("RGBA", "LA") else None)

            self.icons[name] = ImageTk.PhotoImage(canvas)
        except Exception as e:
            print(f"加载图标 {filename} 失败: {e}")

    def _add_countdown_controls(self):
        """添加倒计时控制界面"""
        countdown_card = tk.Frame(self.root, bg=self.colors["card_bg"], relief="flat", bd=1)
        countdown_card.pack(pady=10, padx=30, fill="x")

        countdown_inner = tk.Frame(countdown_card, bg=self.colors["card_bg"])
        countdown_inner.pack(padx=15, pady=10)

        # 标题行
        title_row = tk.Frame(countdown_inner, bg=self.colors["card_bg"])
        title_row.pack(fill="x", pady=(0, 5))

        title_label = tk.Label(
            title_row,
            text="⏱ 训练时长",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=self.colors["text"],
            bg=self.colors["card_bg"]
        )
        title_label.pack(expand=True)

        # 无限制模式选项
        self.unlimited_var = tk.BooleanVar(value=False)
        unlimited_row = tk.Frame(countdown_inner, bg=self.colors["card_bg"])
        unlimited_row.pack(fill="x", pady=(0, 8))

        self.unlimited_check = tk.Checkbutton(
            unlimited_row,
            text="不限时",
            variable=self.unlimited_var,
            command=self._toggle_unlimited,
            font=("Microsoft YaHei UI", 10),
            bg=self.colors["card_bg"],
            activebackground=self.colors["card_bg"]
        )
        self.unlimited_check.pack()

        # 时间选择行
        time_row = tk.Frame(countdown_inner, bg=self.colors["card_bg"])
        time_row.pack(fill="x")

        # 分钟标签
        tk.Label(
            time_row,
            text="分钟:",
            font=("Microsoft YaHei UI", 10),
            fg=self.colors["sub_text"],
            bg=self.colors["card_bg"]
        ).pack(side="left")

        # 分钟选择下拉框
        self.minutes_var = tk.StringVar(value="1")
        minutes_options = ["0", "1", "2", "3", "5", "10", "15", "20", "30"]
        self.minutes_combo = tk.OptionMenu(time_row, self.minutes_var, *minutes_options)
        self.minutes_combo.config(
            font=("Microsoft YaHei UI", 10),
            bg=self.colors["button_bg"],
            fg=self.colors["button_fg"],
            activebackground=self.colors["button_hover"],
            activeforeground=self.colors["button_fg"],
            width=3,
            relief="raised",
            bd=2,
            highlightthickness=1,
            highlightbackground="#d0d0d0",
            highlightcolor="#707070",
            cursor="hand2"
        )
        self.minutes_combo.pack(side="left", padx=5)

        # 秒标签
        tk.Label(
            time_row,
            text="秒:",
            font=("Microsoft YaHei UI", 10),
            fg=self.colors["sub_text"],
            bg=self.colors["card_bg"]
        ).pack(side="left", padx=(15, 0))

        # 秒钟选择下拉框
        self.seconds_var = tk.StringVar(value="0")
        seconds_options = ["0", "10", "15", "20", "30", "45"]
        self.seconds_combo = tk.OptionMenu(time_row, self.seconds_var, *seconds_options)
        self.seconds_combo.config(
            font=("Microsoft YaHei UI", 10),
            bg=self.colors["button_bg"],
            fg=self.colors["button_fg"],
            activebackground=self.colors["button_hover"],
            activeforeground=self.colors["button_fg"],
            width=3,
            relief="raised",
            bd=2,
            highlightthickness=1,
            highlightbackground="#d0d0d0",
            highlightcolor="#707070",
            cursor="hand2"
        )
        self.seconds_combo.pack(side="left", padx=5)

    def _toggle_unlimited(self):
        """切换不限时模式"""
        if self.unlimited_var.get():
            self.minutes_combo.config(state=tk.DISABLED)
            self.seconds_combo.config(state=tk.DISABLED)
        else:
            self.minutes_combo.config(state=tk.NORMAL)
            self.seconds_combo.config(state=tk.NORMAL)

    def get_countdown_time(self):
        """获取设定的倒计时秒数"""
        if self.unlimited_var.get():
            return 0
        try:
            minutes = int(self.minutes_var.get())
            seconds = int(self.seconds_var.get())
            return minutes * 60 + seconds
        except ValueError:
            return 60

    def start_countdown(self):
        """开始倒计时"""
        self.countdown_seconds = self.get_countdown_time()
        self.elapsed_seconds = 0

        if self.countdown_seconds == 0:
            # 不限时模式，显示正计时
            self.countdown_active = True
            self.remaining_seconds = 0
            self._update_countup()
        else:
            # 倒计时模式
            self.countdown_active = True
            self.remaining_seconds = self.countdown_seconds
            self._update_countdown()

    def _update_countdown(self):
        """更新倒计时显示"""
        if not self.countdown_active:
            return

        if self.remaining_seconds <= 0:
            # 倒计时结束
            self.countdown_label.config(text="⏰ 时间到！", fg=self.colors["danger"])
            self.countdown_active = False
            self.on_countdown_finished()
            return

        mins, secs = divmod(self.remaining_seconds, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        if self.remaining_seconds <= 10:
            self.countdown_label.config(text=time_str, fg=self.colors["danger"])
        else:
            self.countdown_label.config(text=time_str, fg=self.colors["primary"])

        self.remaining_seconds -= 1
        self.countdown_job = self.root.after(1000, self._update_countdown)

    def _update_countup(self):
        """不限时模式"""
        if not self.countdown_active:
            return

        mins, secs = divmod(self.remaining_seconds, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        self.countdown_label.config(text=time_str, fg=self.colors["success"])

        self.remaining_seconds += 1
        self.elapsed_seconds = self.remaining_seconds
        self.countdown_job = self.root.after(1000, self._update_countup)

    def stop_countdown(self):
        """停止倒计时"""
        self.countdown_active = False
        if self.countdown_job:
            self.root.after_cancel(self.countdown_job)
            self.countdown_job = None
        if self.signal_check_job:
            self.root.after_cancel(self.signal_check_job)
            self.signal_check_job = None
        self.countdown_label.config(text="")

    def speak(self, text, callback=None):
        """语音播报"""
        if not HAS_SPEECH:
            if callback:
                self.root.after(100, callback)
            return

        def _speak():
            try:
                import pythoncom
                pythoncom.CoInitialize()
                try:
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Rate = 0
                    speaker.Speak(text)
                finally:
                    pythoncom.CoUninitialize()
            except Exception as e:
                print(f"语音播报失败: {e}")
            finally:
                if callback:
                    self.root.after(0, callback)

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()

    def on_countdown_finished(self):
        """倒计时结束后的处理"""
        if self.exit_handling:
            return
        self.exit_handling = True

        finished_name = self.current_name

        self.stop_music()

        if self.current_process and self.current_process.poll() is None:
            try:
                with open(self.stop_signal_file, 'w') as f:
                    f.write('stop')

                try:
                    self.current_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.current_process.terminate()
                    self.current_process.wait(timeout=1)
            except Exception as e:
                print(f"停止子进程出错: {e}")
                try:
                    self.current_process.terminate()
                except:
                    pass
            finally:
                if os.path.exists(self.stop_signal_file):
                    try:
                        os.remove(self.stop_signal_file)
                    except:
                        pass

        self.root.after(500, lambda: self._finish_training_with_speech(finished_name))

    def _finish_training_with_speech(self, finished_name):
        """播报语音后完成训练"""
        final_count = self.get_final_count(finished_name)
        self.speak(f"{finished_name}训练结束，共完成{final_count}个，辛苦了！")
        self.root.after(2000, lambda: self._show_finish_dialog(finished_name, final_count))

    def _show_finish_dialog(self, finished_name, final_count):
        """显示完成对话框"""
        self.current_process = None
        self.current_name = None
        self._set_buttons_running(False)
        self.countdown_label.config(text="")

        messagebox.showinfo("训练完成", f"共完成{final_count}个{finished_name}")

    def add_music_controls(self):
        """音乐控制区域"""
        music_card = tk.Frame(self.root, bg=self.colors["card_bg"], relief="flat", bd=1)
        music_card.pack(pady=10, padx=30, fill="x")

        music_inner = tk.Frame(music_card, bg=self.colors["card_bg"])
        music_inner.pack(padx=15, pady=10)

        # 标题行
        title_row = tk.Frame(music_inner, bg=self.colors["card_bg"])
        title_row.pack(fill="x", pady=(0, 5))

        title_label = tk.Label(
            title_row,
            text="🎵 音乐设置",
            font=("Microsoft YaHei UI", 12, "bold"),
            fg=self.colors["text"],
            bg=self.colors["card_bg"]
        )
        title_label.pack(expand=True)

        # 音乐开关
        self.music_var = tk.BooleanVar(value=True)
        toggle_row = tk.Frame(music_inner, bg=self.colors["card_bg"])
        toggle_row.pack(fill="x", pady=(0, 0))

        music_toggle = tk.Checkbutton(
            toggle_row,
            text="启用音乐",
            variable=self.music_var,
            command=self.toggle_music,
            font=("Microsoft YaHei UI", 10),
            bg=self.colors["card_bg"],
            activebackground=self.colors["card_bg"]
        )
        music_toggle.pack()

        # 音量控制行
        volume_row = tk.Frame(music_inner, bg=self.colors["card_bg"])
        volume_row.pack(fill="x")

        # 音量标签
        vol_label = tk.Label(
            volume_row,
            text="音量:",
            font=("Microsoft YaHei UI", 10),
            fg=self.colors["sub_text"],
            bg=self.colors["card_bg"]
        )
        vol_label.pack(side="left", pady=5)

        # 音量滑块
        self.volume_scale = tk.Scale(
            volume_row,
            from_=0, to=100,
            orient="horizontal",
            length=200,
            showvalue=False,
            bg=self.colors["card_bg"],
            fg=self.colors["text"],
            troughcolor=self.colors["button_bg"],
            activebackground=self.colors["primary"],
            sliderrelief="flat",
            highlightthickness=0,
            command=self._on_volume_change
        )
        self.volume_scale.set(50)
        self.volume_scale.pack(side="left", padx=(10, 5))

        # 音量数值标签
        self.volume_value_label = tk.Label(
            volume_row,
            text="50%",
            font=("Microsoft YaHei UI", 10),
            fg=self.colors["text"],
            bg=self.colors["card_bg"],
            width=3
        )
        self.volume_value_label.pack(side="left", padx=(0, 5))

    def toggle_music(self):
        """切换音乐"""
        self.music_enabled = self.music_var.get()
        if not self.music_enabled:
            self.stop_music()
        else:
            if self.current_process and self.current_process.poll() is None:
                if self.current_name == "深蹲":
                    self.play_music(self.squat_music)
                elif self.current_name == "俯卧撑":
                    self.play_music(self.pushup_music)

    def _on_volume_change(self, value):
        """音量变化"""
        self.music_volume = int(value) / 100
        pygame.mixer.music.set_volume(self.music_volume)
        self.volume_value_label.config(text=f"{int(value)}%")

    def play_music(self, music_path):
        """播放音乐"""
        if not self.music_enabled:
            return
        if not os.path.exists(music_path):
            return
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1)
            self.current_music = music_path
        except Exception as e:
            print(f"播放音乐失败: {e}")

    def stop_music(self):
        """停止音乐"""
        try:
            pygame.mixer.music.stop()
            self.current_music = None
        except Exception:
            pass


    def _set_buttons_running(self, running):
        """设置按钮状态"""
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_squat.config(state=state)
        self.btn_pushup.config(state=state)

    def _watch_child(self, proc):
        """监视子进程"""
        proc.wait()
        self.root.after(0, self._on_child_exit)

    def _on_child_exit(self):
        """子进程退出时的处理"""
        if self.exit_handling:
            return
        self.exit_handling = True

        self.stop_music()
        self.stop_countdown()

        finished_name = self.current_name

        self.current_process = None
        self.current_name = None
        self._set_buttons_running(False)
        self.countdown_label.config(text="")

        if finished_name:
            self.root.after(300, lambda: self._show_exit_result(finished_name))
    def _show_exit_result(self, finished_name):
        """显示退出结果"""
        final_count = self.get_final_count(finished_name)

        if self.unlimited_var.get() and self.elapsed_seconds > 0:
            duration_str = self._format_duration(self.elapsed_seconds)
            messagebox.showinfo("训练结束", f"共完成{final_count}个{finished_name}\n训练时长：{duration_str}")
        else:
            messagebox.showinfo("训练结束", f"共完成{final_count}个{finished_name}")

    def _format_duration(self, seconds):
        """格式化时长显示"""
        mins, secs = divmod(seconds, 60)
        if mins > 0:
            return f"{mins}分{secs}秒"
        else:
            return f"{secs}秒"

    def get_final_count(self, name):
        """获取最终计数"""
        if name == "深蹲":
            count_file = os.path.join(self.data_dir, "squat_count.txt")
        else:
            count_file = os.path.join(self.data_dir, "pushup_count.txt")
        
        try:
            if os.path.exists(count_file):
                with open(count_file, 'r') as f:
                    return int(f.read().strip())
        except Exception:
            pass
        return 0

    def _poll_process(self):
        """轮询检查进程状态"""
        if self.current_process and self.current_process.poll() is not None:
            self._on_child_exit()
        self.root.after(200, self._poll_process)

    def reset_current(self):
        """重置当前运动计数"""
        if self.current_process and self.current_process.poll() is None:
            try:
                # 创建重置信号文件
                flag_path = os.path.join(self.data_dir, "reset.flag")
                with open(flag_path, 'w') as f:
                    f.write('reset')
                # 重置计时器
                self.stop_countdown()
                self.countdown_label.config(text="准备中...", fg=self.colors["sub_text"])
                if os.path.exists(self.signal_file):
                    try:
                        os.remove(self.signal_file)
                    except:
                        pass
                self.wait_for_start_signal()

            except Exception as e:
                messagebox.showerror("错误", f"重置失败：{e}")
        else:
            messagebox.showinfo("提示", "当前没有运行中的训练")

    def start_script(self, script_path, name):
        """启动训练脚本"""
        if not os.path.exists(script_path):
            messagebox.showerror("错误", f"找不到脚本：\n{script_path}")
            return

        if self.current_process and self.current_process.poll() is None:
            messagebox.showinfo("提示", f"当前正在运行：{self.current_name}\n请先停止或等待结束。")
            return

        try:
            self.stop_music()
            self.stop_countdown()
            self.exit_handling = False

            if os.path.exists(self.signal_file):
                os.remove(self.signal_file)

            self.current_process = subprocess.Popen(
                [sys.executable, script_path],
                cwd=self.base_dir,
                creationflags=0
            )
            self.current_name = name

            self.countdown_label.config(text="准备中...", fg=self.colors["sub_text"])
            self.wait_for_start_signal()

            if name == "深蹲":
                self.play_music(self.squat_music)
            else:
                self.play_music(self.pushup_music)

            self._set_buttons_running(True)

            watcher = threading.Thread(target=self._watch_child, args=(self.current_process,), daemon=True)
            watcher.start()
        except Exception as e:
            self.current_process = None
            self.current_name = None
            messagebox.showerror("启动失败", f"{name} 启动失败：\n{e}")

    def wait_for_start_signal(self):
        """等待子脚本发送开始信号"""
        if os.path.exists(self.signal_file):
            try:
                os.remove(self.signal_file)
            except:
                pass
            self.start_countdown()
            self.signal_check_job = None
        elif self.current_process and self.current_process.poll() is None:
            self.signal_check_job = self.root.after(100, self.wait_for_start_signal)
        else:
            self.signal_check_job = None
            self.countdown_label.config(text="")

    def stop_current(self):
        """停止当前训练并退出程序"""
        if self.current_process and self.current_process.poll() is None:
            self.exit_handling = True
            finished_name = self.current_name
            was_unlimited = self.unlimited_var.get()
            final_elapsed = self.elapsed_seconds

            self.stop_countdown()
            self.stop_music()

            try:
                with open(self.stop_signal_file, 'w') as f:
                    f.write('stop')

                try:
                    self.current_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.current_process.terminate()
                    self.current_process.wait(timeout=1)
            except Exception:
                try:
                    self.current_process.terminate()
                except:
                    pass
            finally:
                if os.path.exists(self.stop_signal_file):
                    try:
                        os.remove(self.stop_signal_file)
                    except:
                        pass

            final_count = 0
            if finished_name:
                final_count = self.get_final_count(finished_name)

            # 如果是不限时模式，显示训练时长
            if was_unlimited and final_elapsed > 0:
                duration_str = self._format_duration(final_elapsed)
                messagebox.showinfo("训练结束", f"共完成{final_count}个{finished_name}\n训练时长：{duration_str}")
            else:
                messagebox.showinfo("训练结束", f"共完成{final_count}个{finished_name}")

        self.on_close()

    def on_close(self):
        """关闭程序"""
        if os.path.exists(self.signal_file):
            try:
                os.remove(self.signal_file)
            except:
                pass

        if os.path.exists(self.stop_signal_file):
            try:
                os.remove(self.stop_signal_file)
            except:
                pass

        self.stop_countdown()
        self.stop_music()

        if self.current_process:
            try:
                if self.current_process.poll() is None:
                    with open(self.stop_signal_file, 'w') as f:
                        f.write('stop')
                    try:
                        self.current_process.wait(timeout=2)
                    except:
                        self.current_process.terminate()
            except Exception:
                pass
            finally:
                if os.path.exists(self.stop_signal_file):
                    try:
                        os.remove(self.stop_signal_file)
                    except:
                        pass

        pygame.mixer.quit()
        self.root.destroy()


def main():
    """程序主入口"""
    root = tk.Tk()
    app = FitnessAppUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()