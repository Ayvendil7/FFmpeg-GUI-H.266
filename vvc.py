import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import threading
import queue
import shutil
import sys
from pathlib import Path
import json
import time
import re
from tkinterdnd2 import DND_FILES, TkinterDnD

# Версия приложения
VERSION = "v0.21"

class ToolTip:
    """Всплывающая подсказка для виджетов"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", foreground="#000000",
                        relief=tk.SOLID, borderwidth=1,
                        font=("Segoe UI", 9), padx=8, pady=6)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class ComboboxTooltip:
    """Всплывающая подсказка для элементов выпадающего списка"""
    def __init__(self, combobox, descriptions_dict):
        self.combobox = combobox
        self.descriptions = descriptions_dict
        self.tooltip = None
        self.combobox.bind('<Motion>', self.on_motion)
        self.combobox.bind('<Leave>', self.hide_tooltip)
        
    def on_motion(self, event):
        try:
            current_value = self.combobox.get()
            if current_value and ' - ' in current_value:
                codec_name = current_value.split(' - ')[0].strip()
                description = self.descriptions.get(codec_name, "")
                if description and len(description) > 60:
                    self.show_tooltip(event, description)
                else:
                    self.hide_tooltip()
            else:
                self.hide_tooltip()
        except:
            self.hide_tooltip()
    
    def show_tooltip(self, event, text):
        if self.tooltip:
            self.hide_tooltip()
        x = self.combobox.winfo_rootx() + 20
        y = self.combobox.winfo_rooty() + self.combobox.winfo_height() + 5
        self.tooltip = tw = tk.Toplevel(self.combobox)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                        background="#ffffe0", foreground="#000000",
                        relief=tk.SOLID, borderwidth=1,
                        font=("Segoe UI", 9), padx=8, pady=6,
                        wraplength=400)
        label.pack()
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def destroy(self):
        """Отвязать все события и уничтожить активную подсказку (fix #4).

        Вызывать перед повторным созданием ComboboxTooltip на том же combobox —
        иначе старые бинды <Motion>/<Leave> копятся и каждый наведение мыши
        порождает новый tooltip поверх старого.
        """
        try:
            self.combobox.unbind('<Motion>')
            self.combobox.unbind('<Leave>')
        except Exception:
            pass
        self.hide_tooltip()

class ConfigManager:
    """Управление настройками приложения"""
    def __init__(self, config_file="ffmpeg_converter_config.json"):
        self.config_file = config_file
        self.default_config = {
            "use_local_ffmpeg": False,
            "ffmpeg_path": "ffmpeg",
            "hw_accel": "ЦП (Программное)",
            "last_input_dir": "",
            "last_output_dir": "",
            "video_codec": "libvvenc",
            "video_preset": "medium",
            "video_bitrate": "384k",
            "video_resolution": "1280x720",
            "video_quality": "25",
            "video_fps": "30",
            "audio_codec": "libopus",
            "audio_bitrate": "64k",
            "use_crf": False,
            "show_all_video_codecs": False,
            "show_all_audio_codecs": False,
            "enable_trim": False,
            "trim_start": "00:00:00",
            "trim_end": "00:00:00"
        }

    def load(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return {**self.default_config, **config}
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
        return self.default_config.copy()

    def save(self, config):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")

class CodecManager:
    """Управление кодеками и их отображением"""
    CODEC_DISPLAY_NAMES = {
        "libvvenc": "H.266 (VVC/libvvenc)",
        "libx265": "H.265 (HEVC/libx265)",
        "librav1e": "AV1 (librav1e)",
        "libvpx-vp9": "VP9 (libvpx-vp9)",
        "libaom-av1": "AV1 (libaom-av1)",
        "libopus": "Opus (libopus)",
        "aac": "AAC",
        "libvorbis": "Vorbis (libvorbis)",
        "ac3": "AC3"
    }

    VIDEO_CODECS = ["libvvenc", "libx265", "librav1e", "libvpx-vp9", "libaom-av1"]
    AUDIO_CODECS = ["libopus", "aac", "libvorbis", "ac3"]

    # Карта соответствия программных кодеков аппаратным
    HW_MAP = {
        "NVIDIA (NVENC)": {
            "libx264": "h264_nvenc",
            "libx265": "hevc_nvenc",
            "librav1e": "av1_nvenc",
            "libaom-av1": "av1_nvenc"
        },
        "AMD (AMF)": {
            "libx264": "h264_amf",
            "libx265": "hevc_amf",
            "librav1e": "av1_amf",
            "libaom-av1": "av1_amf"
        },
        "Intel (QSV)": {
            "libx264": "h264_qsv",
            "libx265": "hevc_qsv",
            "librav1e": "av1_qsv",
            "libaom-av1": "av1_qsv",
            "libvpx-vp9": "vp9_qsv"
        }
    }

    @staticmethod
    def get_display_name(codec):
        return CodecManager.CODEC_DISPLAY_NAMES.get(codec, codec)

    @staticmethod
    def get_tech_name(display_name):
        for tech, disp in CodecManager.CODEC_DISPLAY_NAMES.items():
            if disp == display_name:
                return tech
        return display_name

class FFmpegValidator:
    """Валидация параметров FFmpeg"""
    @staticmethod
    def validate_file_path(path, must_exist=True):
        if not path:
            raise ValueError("Путь к файлу не указан")
        if must_exist and not os.path.exists(path):
            raise FileNotFoundError(f"Файл не найден: {path}")
        return True

    @staticmethod
    def validate_bitrate(bitrate):
        pattern = r'^\d+[kKmM]$'
        if not re.match(pattern, bitrate):
            raise ValueError(f"Неверный формат битрейта: {bitrate}. Используйте формат: 384k, 2M")
        return True

    @staticmethod
    def validate_resolution(resolution):
        pattern = r'^\d+x\d+$'
        if not re.match(pattern, resolution):
            raise ValueError(f"Неверный формат разрешения: {resolution}. Используйте формат: 1280x720")
        return True

    @staticmethod
    def validate_fps(fps):
        try:
            fps_value = float(fps)
            if fps_value <= 0 or fps_value > 300:
                raise ValueError("FPS должен быть в диапазоне 1-300")
            return True
        except ValueError:
            raise ValueError(f"Неверное значение FPS: {fps}")

    @staticmethod
    def validate_quality(quality):
        try:
            quality_value = int(quality)
            if quality_value < 0 or quality_value > 51:
                raise ValueError("Качество (CRF) должно быть в диапазоне 0-51")
            return True
        except ValueError:
            raise ValueError(f"Неверное значение качества: {quality}")

    @staticmethod
    def validate_timestamp(timestamp):
        pattern = r'^(\d{1,2}:)?(\d{1,2}:)?\d{1,2}(\.\d+)?$'
        if not re.match(pattern, timestamp):
            raise ValueError(f"Неверный формат времени: {timestamp}. Используйте формат: HH:MM:SS")
        return True

class FFmpegConverter:
    def __init__(self, root):
        self.root = root
        self.root.title(f"FFmpeg Video Converter {VERSION}")
        self.root.geometry("900x850")
        self.root.minsize(800, 700)
        self.root.resizable(True, True)

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()

        # Инициализация очереди для потокобезопасности GUI
        self.ui_queue = queue.Queue()
        self.root.after(100, self.process_queue)

        self.setup_ffmpeg_paths()

        self.current_process = None
        self.start_time = None

        self.ffmpeg_version_info = ""
        self.supported_encoders = []
        self.all_video_encoders = []
        self.all_audio_encoders = []
        self.video_encoder_descriptions = {}
        self.audio_encoder_descriptions = {}

        # Ссылки на активные ComboboxTooltip — уничтожаем перед повторным
        # созданием, иначе копятся дублирующиеся бинды (fix #4).
        self._video_tooltip = None
        self._audio_tooltip = None

        # Кэш эффективной длительности для расчёта прогресса (fix R5).
        self._effective_duration = 0.0

        self.setup_styles()

        # Переменные
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        
        self.use_local_ffmpeg = tk.BooleanVar(value=self.config.get("use_local_ffmpeg", False))
        self.hw_accel = tk.StringVar(value=self.config.get("hw_accel", "CPU (Программное)"))
        self.video_codec = tk.StringVar(value=self.config.get("video_codec", "libvvenc"))
        self.video_preset = tk.StringVar(value=self.config.get("video_preset", "medium"))
        self.video_bitrate = tk.StringVar(value=self.config.get("video_bitrate", "384k"))
        self.video_resolution = tk.StringVar(value=self.config.get("video_resolution", "1280x720"))
        self.resolution_mode = tk.StringVar(value=self.config.get("resolution_mode", "Исходное"))
        self.custom_resolution = tk.StringVar(value=self.config.get("custom_resolution", "1280x720"))
        self.custom_resolution.trace('w', self.on_custom_resolution_change)
        
        self.original_resolution = ""
        self.video_quality = tk.StringVar(value=self.config.get("video_quality", "25"))
        self.video_fps = tk.StringVar(value=self.config.get("video_fps", "30"))
        self.audio_codec = tk.StringVar(value=self.config.get("audio_codec", "libopus"))
        self.audio_bitrate = tk.StringVar(value=self.config.get("audio_bitrate", "64k"))
        self.use_crf = tk.BooleanVar(value=self.config.get("use_crf", False))
        
        self.show_all_video_codecs = tk.BooleanVar(value=self.config.get("show_all_video_codecs", False))
        self.show_all_audio_codecs = tk.BooleanVar(value=self.config.get("show_all_audio_codecs", False))

        self.enable_trim = tk.BooleanVar(value=self.config.get("enable_trim", False))
        self.trim_start = tk.StringVar(value=self.config.get("trim_start", "00:00:00"))
        self.trim_end = tk.StringVar(value=self.config.get("trim_end", "00:00:00"))
        self.video_duration = 0

        self.create_widgets()
        self.setup_drag_drop()
        self.check_ffmpeg_and_codecs()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def process_queue(self):
        """Чтение сообщений из очереди фонового потока для обновления UI (fix A6).

        Оборачиваем тело в try/except Exception — если виджет уничтожен во время
        закрытия окна или возникла любая другая ошибка, мы всё равно перепланируем
        следующий вызов, иначе UI перестанет обновляться навсегда.
        """
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                try:
                    if msg['type'] == 'log':
                        self._log_direct(msg['message'], msg['level'])
                    elif msg['type'] == 'progress':
                        self.progress_var.set(msg['value'])
                        self.progress_label.config(text=msg['text'])
                        if 'time' in msg:
                            self.time_label.config(text=msg['time'])
                    elif msg['type'] == 'status':
                        self.convert_button.config(state=msg['btn_convert'])
                        self.stop_button.config(state=msg['btn_stop'])
                except Exception as e:
                    # Логируем в stderr — UI-виджет мог быть уже уничтожен
                    print(f"process_queue: ошибка обработки сообщения {msg.get('type')}: {e}",
                          file=sys.stderr)
        except queue.Empty:
            pass
        except Exception as e:
            # Неожиданная ошибка — логируем, но НЕ прерываем цикл опроса
            print(f"process_queue: непредвиденная ошибка: {e}", file=sys.stderr)
        finally:
            self.root.after(100, self.process_queue)

    def setup_ffmpeg_paths(self):
        """Определение рабочих путей FFmpeg (Локальный vs Системный)"""
        # Путь к локальной папке программы
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            
        local_ffmpeg = os.path.join(self.app_dir, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        local_ffprobe = os.path.join(self.app_dir, 'ffprobe.exe' if os.name == 'nt' else 'ffprobe')

        if self.config.get("use_local_ffmpeg", False) and os.path.exists(local_ffmpeg):
            self.ffmpeg_path = local_ffmpeg
            self.ffprobe_path = local_ffprobe
        else:
            self.ffmpeg_path = self.config.get("ffmpeg_path", "ffmpeg")
            self.ffprobe_path = "ffprobe"

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        self.colors = {
            'primary': '#3498db', 'primary_hover': '#2980b9', 'secondary': '#95a5a6',
            'success': '#27ae60', 'warning': '#f39c12', 'danger': '#e74c3c',
            'light': '#ecf0f1', 'dark': '#2c3e50', 'background': '#f8f9fa',
            'card': '#ffffff', 'border': '#dee2e6'
        }
        style.configure('TFrame', background=self.colors['background'])
        style.configure('TLabelframe', background=self.colors['background'])
        style.configure('TLabelframe.Label', background=self.colors['background'], foreground=self.colors['dark'], font=('Segoe UI', 10, 'bold'))
        style.configure('TLabel', background=self.colors['background'], foreground=self.colors['dark'], font=('Segoe UI', 9))
        style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'), foreground=self.colors['dark'], background=self.colors['background'])
        style.configure('Card.TFrame', background=self.colors['card'], relief='solid', borderwidth=1)
        
        style.configure('Modern.TButton', font=('Segoe UI', 9), padding=6, relief='flat', borderwidth=0)
        style.map('Modern.TButton', background=[('active', self.colors['primary_hover']), ('!active', self.colors['primary'])], foreground=[('!active', 'white')])
        style.configure('Secondary.TButton', font=('Segoe UI', 9), padding=6, relief='flat', borderwidth=0)
        style.map('Secondary.TButton', background=[('active', '#7f8c8d'), ('!active', self.colors['secondary'])], foreground=[('!active', 'white')])
        style.configure('Horizontal.TProgressbar', troughcolor=self.colors['light'], background=self.colors['primary'], thickness=10)

    def setup_drag_drop(self):
        self.input_entry.drop_target_register(DND_FILES)
        self.input_entry.dnd_bind('<<Drop>>', self.on_input_drop)
        self.output_entry.drop_target_register(DND_FILES)
        self.output_entry.dnd_bind('<<Drop>>', self.on_output_drop)

    def on_input_drop(self, event):
        files = self.parse_drop_files(event.data)
        if files:
            file_path = files[0]
            self.input_file.set(file_path)
            if not self.output_file.get():
                input_path = Path(file_path)
                self.output_file.set(str(input_path.parent / f"{input_path.stem}_converted.mp4"))
            self.auto_detect_video_params(file_path)
            self.update_file_info()
            self.log(f"Файл добавлен: {file_path}", "success")

    def on_output_drop(self, event):
        files = self.parse_drop_files(event.data)
        if files:
            file_path = files[0]
            if os.path.isdir(file_path) and self.input_file.get():
                input_path = Path(self.input_file.get())
                self.output_file.set(str(Path(file_path) / f"{input_path.stem}_converted.mp4"))
            else:
                self.output_file.set(file_path)
            self.update_file_info()

    def parse_drop_files(self, data):
        files = []
        if isinstance(data, str):
            data = data.strip()
            if data.startswith('{'):
                current_path, in_braces = "", False
                for char in data:
                    if char == '{': in_braces, current_path = True, ""
                    elif char == '}': 
                        in_braces = False
                        if current_path: files.append(current_path.strip())
                        current_path = ""
                    elif in_braces: current_path += char
            else: files = [data]
        elif isinstance(data, (list, tuple)): files = list(data)
        return files

    def create_widgets(self):
        main_container = ttk.Frame(self.root, style='TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        header_frame = ttk.Frame(main_container, style='TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 12))

        title_frame = ttk.Frame(header_frame, style='TFrame')
        title_frame.pack(side=tk.LEFT)
        ttk.Label(title_frame, text="FFmpeg Video Converter", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Label(title_frame, text=VERSION, foreground=self.colors['secondary']).pack(side=tk.LEFT, padx=(8, 0))

        button_container = ttk.Frame(header_frame, style='TFrame')
        button_container.pack(side=tk.RIGHT)
        ttk.Button(button_container, text="Настройки FFmpeg", command=self.show_ffmpeg_settings, style='Secondary.TButton').pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(button_container, text="Инфо о FFmpeg", command=self.show_ffmpeg_info, style='Secondary.TButton').pack(side=tk.LEFT)

        content_frame = ttk.Frame(main_container, style='Card.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)

        self.create_file_section(content_frame)
        self.create_trim_section(content_frame)

        params_frame = ttk.Frame(content_frame, style='TFrame')
        params_frame.pack(fill=tk.BOTH, expand=True)

        self.create_video_section(params_frame)
        self.create_audio_section(params_frame)
        self.create_progress_section(content_frame)
        self.create_info_section(content_frame)

    def create_file_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Файлы (поддерживается Drag & Drop)", padding="12")
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Входной файл:").grid(row=0, column=0, sticky=tk.W, pady=4)
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 4), pady=4)
        input_frame.columnconfigure(0, weight=1)
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_file, state='readonly')
        self.input_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(input_frame, text="Обзор", command=self.browse_input, style='Modern.TButton').grid(row=0, column=1, padx=(4, 0))

        ttk.Label(frame, text="Выходной файл:").grid(row=1, column=0, sticky=tk.W, pady=4)
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 4), pady=4)
        output_frame.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_file, state='readonly')
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(output_frame, text="Обзор", command=self.browse_output, style='Modern.TButton').grid(row=0, column=1, padx=(4, 0))

    def create_trim_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Обрезка видео", padding="12")
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        trim_checkbox = ttk.Checkbutton(frame, text="Обрезать видео", variable=self.enable_trim, command=self.toggle_trim_controls)
        trim_checkbox.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        ToolTip(trim_checkbox, "Формат времени: ЧЧ:MM:СС или MM:СС или просто секунды")

        ttk.Label(frame, text="Начало:").grid(row=1, column=0, sticky=tk.W, pady=4)
        start_frame = ttk.Frame(frame)
        start_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        self.trim_start_entry = ttk.Entry(start_frame, textvariable=self.trim_start, width=12)
        self.trim_start_entry.pack(side=tk.LEFT)

        ttk.Label(frame, text="Конец:").grid(row=2, column=0, sticky=tk.W, pady=4)
        end_frame = ttk.Frame(frame)
        end_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        self.trim_end_entry = ttk.Entry(end_frame, textvariable=self.trim_end, width=12)
        self.trim_end_entry.pack(side=tk.LEFT)
        self.duration_label = ttk.Label(end_frame, text="", foreground=self.colors['secondary'])
        self.duration_label.pack(side=tk.LEFT, padx=(8, 0))

        if not self.enable_trim.get():
            self.trim_start_entry.config(state='disabled')
            self.trim_end_entry.config(state='disabled')

    def toggle_trim_controls(self):
        state = 'normal' if self.enable_trim.get() else 'disabled'
        self.trim_start_entry.config(state=state)
        self.trim_end_entry.config(state=state)

    def create_video_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Параметры видео", padding="12")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        frame.columnconfigure(1, weight=1)
        row = 0

        # Аппаратное ускорение
        ttk.Label(frame, text="Ускорение:").grid(row=row, column=0, sticky=tk.W, pady=4)
        hw_frame = ttk.Frame(frame)
        hw_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        hw_combobox = ttk.Combobox(hw_frame, textvariable=self.hw_accel, 
                                 values=["ЦП (Программное)", "NVIDIA (NVENC)", "AMD (AMF)", "Intel (QSV)"], state="readonly")
        hw_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ToolTip(hw_combobox, "Аппаратное ускорение (GPU) работает во много раз быстрее,\nно качество сжатия на ЦП обычно лучше.\nВнимание: H.266 пока не поддерживается ни одной существующей видеокартой.")
        row += 1

        # Кодек
        ttk.Label(frame, text="Кодек:").grid(row=row, column=0, sticky=tk.W, pady=4)
        codec_container = ttk.Frame(frame)
        codec_container.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        codec_container.columnconfigure(0, weight=1)
        self.video_codec_combobox = ttk.Combobox(codec_container, state="readonly")
        self.video_codec_combobox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.video_codec_combobox.bind("<<ComboboxSelected>>", lambda e: self._on_codec_change('video'))
        
        ttk.Checkbutton(codec_container, text="Ещё", variable=self.show_all_video_codecs, command=lambda: self._filter_codecs('video')).grid(row=0, column=1, padx=(4, 0))
        row += 1

        # Пресет
        ttk.Label(frame, text="Пресет:").grid(row=row, column=0, sticky=tk.W, pady=4)
        preset_frame = ttk.Frame(frame)
        preset_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        ttk.Combobox(preset_frame, textvariable=self.video_preset, values=["faster", "fast", "medium", "slow", "slower"], state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)
        row += 1

        # Режим
        ttk.Label(frame, text="Режим:").grid(row=row, column=0, sticky=tk.W, pady=4)
        crf_checkbox = ttk.Checkbutton(frame, text="CRF (постоянное качество)", variable=self.use_crf, command=self.toggle_encoding_mode)
        crf_checkbox.grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=4)
        ToolTip(crf_checkbox, "CRF адаптирует сжатие под сложность сцены. Оптимально: 23-28")
        row += 1

        # Битрейт / Качество
        self.bitrate_label = ttk.Label(frame, text="Битрейт:")
        self.bitrate_label.grid(row=row, column=0, sticky=tk.W, pady=4)
        self.bitrate_entry = ttk.Entry(frame, textvariable=self.video_bitrate)
        self.bitrate_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        row += 1

        # Разрешение
        ttk.Label(frame, text="Разрешение:").grid(row=row, column=0, sticky=tk.W, pady=4)
        resolution_frame = ttk.Frame(frame)
        resolution_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        self.resolution_combobox = ttk.Combobox(resolution_frame, textvariable=self.resolution_mode, values=["Исходное", "HD (1280x720)", "FHD (1920x1080)", "Особое"], state="readonly", width=14)
        self.resolution_combobox.grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.resolution_combobox.bind("<<ComboboxSelected>>", self.on_resolution_mode_change)
        self.custom_resolution_entry = ttk.Entry(resolution_frame, textvariable=self.custom_resolution, width=12)
        self.custom_resolution_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        if self.resolution_mode.get() != "Особое": self.custom_resolution_entry.grid_remove()
        row += 1

        # FPS
        ttk.Label(frame, text="FPS:").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame, textvariable=self.video_fps, width=10).grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=4)

        self.toggle_encoding_mode()

    def create_audio_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Параметры аудио и управление", padding="12")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Кодек:").grid(row=0, column=0, sticky=tk.W, pady=4)
        codec_frame = ttk.Frame(frame)
        codec_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        codec_frame.columnconfigure(0, weight=1)
        self.audio_codec_combobox = ttk.Combobox(codec_frame, state="readonly")
        self.audio_codec_combobox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.audio_codec_combobox.bind("<<ComboboxSelected>>", lambda e: self._on_codec_change('audio'))
        ttk.Checkbutton(codec_frame, text="Ещё", variable=self.show_all_audio_codecs, command=lambda: self._filter_codecs('audio')).grid(row=0, column=1, padx=(4, 0))

        ttk.Label(frame, text="Битрейт:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame, textvariable=self.audio_bitrate).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        ttk.Separator(frame, orient='horizontal').grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(12, 8))

        buttons_container = ttk.Frame(frame, style='TFrame')
        buttons_container.grid(row=3, column=0, columnspan=2, pady=(4, 0))
        self.convert_button = ttk.Button(buttons_container, text="Начать конвертацию", command=self.start_conversion, style='Modern.TButton', width=18)
        self.convert_button.grid(row=0, column=0, padx=(0, 4))
        self.stop_button = ttk.Button(buttons_container, text="Остановить", command=self.stop_conversion, state='disabled', style='Secondary.TButton', width=13)
        self.stop_button.grid(row=0, column=1, padx=(4, 4))
        ttk.Button(buttons_container, text="Предпросмотр команды", command=self.preview_command, style='Secondary.TButton', width=18).grid(row=0, column=2, padx=(4, 0))

    def _filter_codecs(self, codec_type):
        """Единый метод фильтрации для видео и аудио кодеков (DRY)"""
        is_video = codec_type == 'video'
        show_all = self.show_all_video_codecs.get() if is_video else self.show_all_audio_codecs.get()
        all_encs = self.all_video_encoders if is_video else self.all_audio_encoders
        supported_base = CodecManager.VIDEO_CODECS if is_video else CodecManager.AUDIO_CODECS
        
        codecs_to_show = all_encs if show_all else [c for c in supported_base if c in self.supported_encoders]
        descriptions = self.video_encoder_descriptions if is_video else self.audio_encoder_descriptions
        combobox = self.video_codec_combobox if is_video else self.audio_codec_combobox
        current_var = self.video_codec if is_video else self.audio_codec

        display_names = []
        for codec in codecs_to_show:
            if show_all:
                desc = descriptions.get(codec, codec)
                display_names.append(f"{codec} - {desc[:57]}..." if len(desc) > 60 else f"{codec} - {desc}")
            else:
                display_names.append(CodecManager.get_display_name(codec))
        
        combobox['values'] = display_names
        
        current_tech = current_var.get()
        if current_tech not in codecs_to_show and codecs_to_show:
            current_var.set(codecs_to_show[0])
            combobox.set(display_names[0])
        else:
            if show_all:
                desc = descriptions.get(current_tech, current_tech)
                combobox.set(f"{current_tech} - {desc[:57]}..." if len(desc) > 60 else f"{current_tech} - {desc}")
            else:
                combobox.set(CodecManager.get_display_name(current_tech))
        
        # ComboboxTooltip: создаём один раз и уничтожаем перед повторным
        # созданием — иначе копятся дублирующиеся бинды <Motion>/<Leave> (fix #4).
        attr = '_video_tooltip' if is_video else '_audio_tooltip'
        if show_all:
            if getattr(self, attr) is None:
                tooltip = ComboboxTooltip(combobox, descriptions)
                setattr(self, attr, tooltip)
        else:
            existing = getattr(self, attr)
            if existing is not None:
                existing.destroy()
                setattr(self, attr, None)

    def _on_codec_change(self, codec_type):
        """Единый обработчик смены кодека"""
        combobox = self.video_codec_combobox if codec_type == 'video' else self.audio_codec_combobox
        target_var = self.video_codec if codec_type == 'video' else self.audio_codec
        val = combobox.get()
        tech_name = val.split(' - ')[0].strip() if ' - ' in val else CodecManager.get_tech_name(val)
        target_var.set(tech_name)

    def toggle_encoding_mode(self):
        if self.use_crf.get():
            self.bitrate_label.config(text="Качество (CRF):")
            self.bitrate_entry.config(textvariable=self.video_quality)
        else:
            self.bitrate_label.config(text="Битрейт:")
            self.bitrate_entry.config(textvariable=self.video_bitrate)

    def on_custom_resolution_change(self, *args):
        if self.resolution_mode.get() == "Особое":
            self.video_resolution.set(self.custom_resolution.get())

    def on_resolution_mode_change(self, event):
        mode = self.resolution_mode.get()
        if mode == "Особое":
            self.custom_resolution_entry.grid()
            self.video_resolution.set(self.custom_resolution.get())
        else:
            self.custom_resolution_entry.grid_remove()
            if mode == "Исходное": self.video_resolution.set(self.original_resolution or "1280x720")
            elif "HD" in mode: self.video_resolution.set(mode.split('(')[1].strip(')'))

    def create_progress_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Прогресс и логи", padding="12")
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        progress_frame = ttk.Frame(frame, style='TFrame')
        progress_frame.pack(fill=tk.X, pady=(0, 8))
        progress_frame.columnconfigure(1, weight=1)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, style='Horizontal.TProgressbar')
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))

        self.progress_label = ttk.Label(progress_frame, text="Готово к конвертации")
        self.progress_label.grid(row=1, column=0, sticky=tk.W)
        self.time_label = ttk.Label(progress_frame, text="")
        self.time_label.grid(row=1, column=1, sticky=tk.E)

        self.log_text = tk.Text(frame, height=7, wrap=tk.WORD, font=('Consolas', 8), bg=self.colors['light'])
        # Цветовые теги для разных уровней логов (fix R1/#10)
        self.log_text.tag_config('error', foreground=self.colors['danger'])
        self.log_text.tag_config('warning', foreground=self.colors['warning'])
        self.log_text.tag_config('success', foreground=self.colors['success'])
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.create_context_menu()

    def create_info_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Информация о файлах", padding="12")
        frame.pack(fill=tk.X)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Входной файл:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_info_label = ttk.Label(frame, text="Не выбран")
        self.input_info_label.grid(row=0, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        ttk.Label(frame, text="Выходной файл:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_info_label = ttk.Label(frame, text="Не создан")
        self.output_info_label.grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        ttk.Label(frame, text="Экономия:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.saving_label = ttk.Label(frame, text="0%")
        self.saving_label.grid(row=2, column=1, sticky=tk.W, padx=(8, 0), pady=2)

    def create_context_menu(self):
        """Контекстное меню лога (fix R14).

        Старая реализация падала с TclError при "Копировать" без выделения.
        Добавлены: clipboard_clear перед копированием, "Выделить всё",
        горячие клавиши Ctrl+A / Ctrl+C.
        """
        self.context_menu = tk.Menu(self.log_text, tearoff=0, font=('Segoe UI', 9))
        self.context_menu.add_command(label="Копировать", command=self._copy_log_selection)
        self.context_menu.add_command(label="Выделить всё", command=self._select_all_log)
        self.context_menu.add_command(label="Очистить", command=lambda: self.log_text.delete('1.0', tk.END))
        self.log_text.bind("<Button-3>", lambda e: self.context_menu.tk_popup(e.x_root, e.y_root))
        # Горячие клавиши
        self.log_text.bind("<Control-a>", lambda e: self._select_all_log())
        self.log_text.bind("<Control-A>", lambda e: self._select_all_log())
        self.log_text.bind("<Control-c>", lambda e: self._copy_log_selection())
        self.log_text.bind("<Control-C>", lambda e: self._copy_log_selection())

    def _copy_log_selection(self):
        """Копирование выделенного текста в буфер обмена (fix R14)."""
        try:
            selected = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
        except tk.TclError:
            # Ничего не выделено — просто игнорируем
            pass

    def _select_all_log(self):
        """Выделение всего лога (fix R14). Возвращает 'break' чтобы не
        передавать событие дальше (иначе Tcl сам добавляет поведение)."""
        self.log_text.tag_add(tk.SEL, "1.0", tk.END)
        self.log_text.mark_set(tk.INSERT, "1.0")
        self.log_text.see(tk.INSERT)
        return "break"

    def browse_input(self):
        filename = filedialog.askopenfilename(filetypes=[("Видео файлы", "*.mp4 *.mkv *.avi"), ("Все файлы", "*.*")])
        if filename:
            self.input_file.set(filename)
            if not self.output_file.get():
                p = Path(filename)
                self.output_file.set(str(p.parent / f"{p.stem}_converted.mp4"))
            self.auto_detect_video_params(filename)
            self.update_file_info()

    def browse_output(self):
        filename = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4"), ("MKV", "*.mkv")])
        if filename:
            self.output_file.set(filename)
            self.update_file_info()

    def update_file_info(self):
        if self.input_file.get() and os.path.exists(self.input_file.get()):
            size = os.path.getsize(self.input_file.get())
            self.input_info_label.config(text=f"{size / (1024*1024):.1f} МБ")
        if self.output_file.get() and os.path.exists(self.output_file.get()):
            size = os.path.getsize(self.output_file.get())
            self.output_info_label.config(text=f"{size / (1024*1024):.1f} МБ")

    def auto_detect_video_params(self, filepath):
        self.log(f"Добавлен файл: {filepath}", "info")

    def check_ffmpeg_and_codecs(self):
        try:
            result = subprocess.run([self.ffmpeg_path, '-version'], capture_output=True, text=True, errors='replace')
            if result.returncode == 0:
                self.ffmpeg_version_info = result.stdout.split('\n')[0]
                self.log(f"FFmpeg найден: {self.ffmpeg_version_info}", "success")
                
                res = subprocess.run([self.ffmpeg_path, '-encoders'], capture_output=True, text=True, errors='replace')
                self.supported_encoders = []
                self.all_video_encoders = []
                self.all_audio_encoders = []
                
                in_encoders = False
                for line in res.stdout.split('\n'):
                    if '------' in line: in_encoders = True; continue
                    if in_encoders and line.strip():
                        parts = line.strip().split(maxsplit=2)
                        if len(parts) >= 2:
                            etype, ename = parts[0], parts[1]
                            desc = parts[2] if len(parts) >= 3 else ename
                            if 'V' in etype:
                                self.all_video_encoders.append(ename)
                                self.video_encoder_descriptions[ename] = desc
                                if ename in CodecManager.VIDEO_CODECS: self.supported_encoders.append(ename)
                            elif 'A' in etype:
                                self.all_audio_encoders.append(ename)
                                self.audio_encoder_descriptions[ename] = desc
                                if ename in CodecManager.AUDIO_CODECS: self.supported_encoders.append(ename)
                
                self._filter_codecs('video')
                self._filter_codecs('audio')
        except Exception as e:
            self.log(f"FFmpeg не найден: {e}", "error")

    def show_ffmpeg_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Настройки FFmpeg")
        win.geometry("550x300")
        
        frame = ttk.Frame(win, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Режим работы:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        radio_frame = ttk.Frame(frame)
        radio_frame.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))
        ttk.Radiobutton(radio_frame, text="Использовать системный FFmpeg (PATH)", variable=self.use_local_ffmpeg, value=False).pack(anchor=tk.W)
        ttk.Radiobutton(radio_frame, text="Использовать FFmpeg из папки программы", variable=self.use_local_ffmpeg, value=True).pack(anchor=tk.W)

        ttk.Label(frame, text="Путь к системному FFmpeg (если выбран системный):").grid(row=2, column=0, sticky=tk.W)
        path_frame = ttk.Frame(frame)
        path_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        path_var = tk.StringVar(value=self.config.get("ffmpeg_path", "ffmpeg"))
        ttk.Entry(path_frame, textvariable=path_var, width=50).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(path_frame, text="Обзор", command=lambda: path_var.set(filedialog.askopenfilename() or path_var.get())).pack(side=tk.LEFT)

        def vacuum_ffmpeg():
            sys_ffmpeg = shutil.which("ffmpeg")
            if not sys_ffmpeg:
                messagebox.showerror("Ошибка", "Системный FFmpeg не найден в PATH!")
                return
            try:
                local_ff = os.path.join(self.app_dir, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
                shutil.copy2(sys_ffmpeg, local_ff)
                sys_ffprobe = shutil.which("ffprobe")
                if sys_ffprobe:
                    local_pr = os.path.join(self.app_dir, "ffprobe.exe" if os.name == 'nt' else "ffprobe")
                    shutil.copy2(sys_ffprobe, local_pr)
                self.use_local_ffmpeg.set(True)
                messagebox.showinfo("Успех", f"FFmpeg успешно скопирован в:\n{self.app_dir}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось скопировать: {e}")

        ttk.Button(frame, text="Найти и скопировать FFmpeg в папку программы", command=vacuum_ffmpeg).grid(row=4, column=0, sticky=tk.W, pady=(0, 15))

        def save():
            self.config["use_local_ffmpeg"] = self.use_local_ffmpeg.get()
            self.config["ffmpeg_path"] = path_var.get()
            self.config_manager.save(self.config)
            self.setup_ffmpeg_paths()
            self.check_ffmpeg_and_codecs()
            win.destroy()

        btn_f = ttk.Frame(frame)
        btn_f.grid(row=5, column=0, sticky=tk.E)
        ttk.Button(btn_f, text="Сохранить", command=save, style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_f, text="Отмена", command=win.destroy).pack(side=tk.LEFT)

    def show_ffmpeg_info(self):
        messagebox.showinfo("FFmpeg Info", f"Версия: {self.ffmpeg_version_info}\nПуть: {self.ffmpeg_path}")

    def log(self, message, level="info"):
        """Потокобезопасная обертка для логов"""
        self.ui_queue.put({'type': 'log', 'message': message, 'level': level})

    def _log_direct(self, message, level):
        """Прямая запись в UI (вызывается из очереди). fix R1/#10: цвет применяется."""
        prefix_map = {'error': 'ERROR: ', 'warning': 'WARNING: ', 'success': '✓ '}
        prefix = prefix_map.get(level, '')
        tag = level if level in prefix_map else None
        self.log_text.insert(tk.END, prefix + message + '\n', tag)
        self.log_text.see(tk.END)

    def preview_command(self):
        try:
            cmd = ' '.join(self.build_ffmpeg_command())
            messagebox.showinfo("Команда", cmd)
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def normalize_bitrate(self, bitrate):
        bitrate = bitrate.strip()
        if bitrate and bitrate[-1].lower() not in ['k', 'm'] and bitrate.isdigit():
            return bitrate + 'k'
        return bitrate

    def get_actual_video_codec(self):
        """Возвращает кодек с учетом аппаратного ускорения"""
        base_codec = self.video_codec.get()
        hw_mode = self.hw_accel.get()
        
        if hw_mode == "CPU (Программное)":
            return base_codec
            
        hw_codec = CodecManager.HW_MAP.get(hw_mode, {}).get(base_codec, base_codec)
        if hw_codec == base_codec and base_codec == "libvvenc":
            self.log("Внимание: VVC пока не имеет аппаратного энкодера, используется CPU.", "warning")
        return hw_codec

    def build_ffmpeg_command(self):
        """Построение команды FFmpeg (fixes #6, #7, #9).

        #6 — CRF/качество для каждого кодека:
            - libx264/libx265/libvvenc  → -crf N
            - libaom-av1                 → -crf N -b:v 0  (иначе режим не активируется)
            - librav1e                   → -qp N          (-crf игнорируется)
            - libvpx-vp9                 → -crf N -b:v 0
            - nvenc                      → -rc vbr -cq N
            - amf                        → -rc cqp -qp_i N -qp_p N
            - qsv                        → -global_quality N
        #7 — пресет: x264/x265/vvenc используют -preset; остальным нужны
            числовые флаги (-cpu-used для aom, -speed для rav1e/vpx).
        #9 — trim: -ss до -i (быстрый seek) + -t после -i (длительность).
            Старая схема -ss + -to до -i имела путаную семантику абсолютного
            таймштампа и давала неточные результаты.
        """
        FFmpegValidator.validate_file_path(self.input_file.get())
        v_bitrate = self.normalize_bitrate(self.video_bitrate.get())
        a_bitrate = self.normalize_bitrate(self.audio_bitrate.get())

        cmd = [self.ffmpeg_path]

        # --- Trim (fix #9): -ss до -i, -t после -i ---
        trim_duration_seconds = None
        if self.enable_trim.get():
            FFmpegValidator.validate_timestamp(self.trim_start.get())
            FFmpegValidator.validate_timestamp(self.trim_end.get())
            start_s = self.timestamp_to_seconds(self.trim_start.get())
            end_s   = self.timestamp_to_seconds(self.trim_end.get())
            if end_s <= start_s:
                raise ValueError("Время конца должно быть позже времени начала")
            trim_duration_seconds = end_s - start_s
            cmd.extend(['-ss', self.trim_start.get()])

        cmd.extend(['-i', self.input_file.get()])

        # Длительность фрагмента (после -i)
        if trim_duration_seconds is not None:
            cmd.extend(['-t', self.seconds_to_timestamp(trim_duration_seconds)])

        actual_codec = self.get_actual_video_codec()

        # Видео кодек
        cmd.extend(['-c:v', actual_codec, '-threads', '0'])

        # Контроль качества / битрейт (fix #6)
        if self.use_crf.get():
            quality = self.video_quality.get()
            if "nvenc" in actual_codec:
                cmd.extend(['-rc', 'vbr', '-cq', quality])
            elif "amf" in actual_codec:
                cmd.extend(['-rc', 'cqp', '-qp_i', quality, '-qp_p', quality])
            elif "qsv" in actual_codec:
                cmd.extend(['-global_quality', quality, '-look_ahead', '0'])
            elif actual_codec == 'librav1e':
                # librav1e не понимает -crf, нужен -qp
                cmd.extend(['-qp', quality])
            elif actual_codec == 'libaom-av1':
                # aom-av1: -crf активируется только вместе с -b:v 0
                cmd.extend(['-crf', quality, '-b:v', '0'])
            elif actual_codec == 'libvpx-vp9':
                # VP9: -crf + -b:v 0 включает режим постоянного качества
                cmd.extend(['-crf', quality, '-b:v', '0'])
            else:
                # libx264, libx265, libvvenc
                cmd.extend(['-crf', quality])
        else:
            cmd.extend(['-b:v', v_bitrate])

        # Пресет / скорость (fix #7)
        # x264/x265/vvenc используют текстовый -preset; остальным нужны числовые флаги.
        preset = self.video_preset.get()
        # Карта: текстовый пресет → числовое значение скорости для каждого кодека
        SPEED_MAP = {
            'libaom-av1':  {'faster': 6, 'fast': 4, 'medium': 2, 'slow': 1, 'slower': 0},
            'librav1e':    {'faster': 8, 'fast': 6, 'medium': 4, 'slow': 2, 'slower': 1},
            'libvpx-vp9':  {'faster': 5, 'fast': 4, 'medium': 2, 'slow': 1, 'slower': 0},
        }
        if "nvenc" in actual_codec or "amf" in actual_codec or "qsv" in actual_codec:
            # Для HW-энкодеров -preset валиден, но значения другие (p1..p7 для nvenc,
            # speed/quality/balanced для amf, veryfast..slower для qsv).
            # Не передаём, чтобы не падать — пусть кодек использует свой дефолт.
            pass
        elif actual_codec == 'libaom-av1':
            cmd.extend(['-cpu-used', str(SPEED_MAP[actual_codec].get(preset, 2))])
        elif actual_codec == 'librav1e':
            cmd.extend(['-speed', str(SPEED_MAP[actual_codec].get(preset, 4))])
        elif actual_codec == 'libvpx-vp9':
            cmd.extend(['-speed', str(SPEED_MAP[actual_codec].get(preset, 2))])
        else:
            # libx264, libx265, libvvenc — текстовый -preset
            cmd.extend(['-preset', preset])

        cmd.extend(['-s', self.video_resolution.get(), '-r', self.video_fps.get(),
                    '-c:a', self.audio_codec.get(), '-b:a', a_bitrate])
        if self.audio_codec.get() == 'libopus': cmd.extend(['-ac', '2'])
        cmd.extend(['-y', self.output_file.get()])
        return cmd

    def timestamp_to_seconds(self, timestamp):
        """Конвертация HH:MM:SS / MM:SS / SS в секунды (fix #9 helper)."""
        parts = timestamp.split(':')
        if len(parts) == 3:
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = map(float, parts)
            return m * 60 + s
        return float(parts[0])

    def seconds_to_timestamp(self, seconds):
        """Конвертация секунд в HH:MM:SS (fix #9 helper)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _get_video_duration(self, filepath):
        """Получение длительности файла через ffprobe (fix R5 helper)."""
        try:
            result = subprocess.run(
                [self.ffprobe_path, '-v', 'quiet',
                 '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
                capture_output=True, text=True, errors='replace', timeout=10
            )
            if result.returncode == 0 and result.stdout and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0

    def _compute_effective_duration(self):
        """Длительность целевого фрагмента в секундах (fix R5).

        Если включена обрезка — это (end - start). Иначе — полная длительность файла.
        Вычисляется ОДИН РАЗ в start_conversion, чтобы не запускать ffprobe на
        каждой строке вывода ffmpeg (как делала старая реализация).
        """
        try:
            if self.enable_trim.get():
                start_s = self.timestamp_to_seconds(self.trim_start.get())
                end_s   = self.timestamp_to_seconds(self.trim_end.get())
                if end_s > start_s:
                    return end_s - start_s
            # Без обрезки — полная длительность (кэш в self.video_duration,
            # если он устанавливается при выборе файла, иначе — ffprobe)
            if self.video_duration and self.video_duration > 0:
                return float(self.video_duration)
            return self._get_video_duration(self.input_file.get())
        except Exception:
            try:
                return self._get_video_duration(self.input_file.get())
            except Exception:
                return 0.0

    def start_conversion(self):
        """Запуск конвертации. fix R5: длительность вычисляется один раз здесь."""
        try:
            cmd = self.build_ffmpeg_command()
            # Кэш длительности для расчёта прогресса (fix R5)
            self._effective_duration = self._compute_effective_duration()
            self.convert_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.progress_var.set(0)
            self.progress_label.config(text="Начало конвертации...")
            self.time_label.config(text="")

            self.conversion_thread = threading.Thread(target=self.run_conversion, args=(cmd,))
            self.conversion_thread.daemon = True
            self.conversion_thread.start()
        except Exception as e:
            self.log(f"Ошибка: {e}", "error")
            self.convert_button.config(state='normal')

    def run_conversion(self, cmd):
        """Выполнение конвертации в рабочем потоке (fix R5).

        Все UI-обновления идут через self.ui_queue → process_queue (главный поток).
        Прогресс считается по реальному time= из вывода ffmpeg + _effective_duration.
        """
        try:
            self.start_time = time.time()
            self.log(f"Запуск: {' '.join(cmd)}")

            # Windows: не показывать чёрное окно консоли
            creationflags = 0
            if os.name == 'nt':
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, errors='replace',
                creationflags=creationflags,
            )

            for out in iter(self.current_process.stdout.readline, ''):
                if not out:
                    if self.current_process.poll() is not None:
                        break
                    continue
                out = out.rstrip()
                if not out:
                    continue
                self.log(out)
                # Парсим time= и считаем реальный прогресс (fix R5)
                match = re.search(r"time=(\d+:\d+:\d+\.\d+)", out)
                if match:
                    self._update_progress_from_time(match.group(1))

            rc = self.current_process.poll()
            if rc == 0:
                self.ui_queue.put({'type': 'progress', 'value': 100,
                                   'text': "Конвертация завершена!"})
                self.log("Успешно завершено", "success")
            else:
                self.log(f"Ошибка конвертации. Код возврата: {rc}", "error")
                self.ui_queue.put({'type': 'progress', 'value': 0,
                                   'text': "Ошибка конвертации"})
        except Exception as e:
            self.log(f"Ошибка выполнения: {e}", "error")
        finally:
            self.ui_queue.put({'type': 'status', 'btn_convert': 'normal', 'btn_stop': 'disabled'})
            self.current_process = None

    def _update_progress_from_time(self, time_str):
        """Расчёт прогресса из time= строки вывода ffmpeg (fix R5).

        Вызывается в рабочем потоке — кладёт сообщение в ui_queue,
        не трогает Tkinter напрямую.
        """
        try:
            parts = time_str.split(':')
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            current_seconds = h * 3600 + m * 60 + s
            duration = self._effective_duration
            if not duration or duration <= 0:
                # Длительность неизвестна — показываем только текущее время
                self.ui_queue.put({'type': 'progress', 'value': 0,
                                   'text': f"Обработка: {time_str}"})
                return
            progress = min(100.0, (current_seconds / duration) * 100)
            elapsed = time.time() - self.start_time
            if progress > 0:
                estimated_total = elapsed / (progress / 100)
                remaining = max(0, estimated_total - elapsed)
                time_text = f"Осталось: {self._format_time(remaining)}"
            else:
                time_text = ""
            self.ui_queue.put({
                'type': 'progress', 'value': progress,
                'text': f"Прогресс: {progress:.1f}%",
                'time': time_text,
            })
        except Exception:
            pass

    @staticmethod
    def _format_time(seconds):
        """HH:MM:SS или MM:SS."""
        if seconds < 0:
            return "00:00"
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

    def stop_conversion(self):
        """Остановка конвертации (fix R15).

        Старая реализация звала только terminate() без wait() — если ffmpeg
        игнорировал SIGTERM (бывает на тяжёлом кадре), процесс оставался зомби,
        а кнопки не возвращались в исходное состояние. Теперь: terminate →
        wait(5) → kill() на таймаут + сброс UI.
        """
        if not self.current_process:
            return
        try:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
                self.current_process.wait(timeout=3)
                self.log("Конвертация принудительно завершена (kill)", "error")
            else:
                self.log("Остановлено пользователем", "warning")
        except Exception as e:
            self.log(f"Ошибка при остановке: {e}", "error")
        finally:
            # Сбрасываем UI — иначе кнопка "Начать" остаётся disabled, пока
            # рабочий поток не выйдет из readline() (fix R15).
            self.ui_queue.put({'type': 'status', 'btn_convert': 'normal', 'btn_stop': 'disabled'})
            self.ui_queue.put({'type': 'progress', 'value': 0,
                               'text': "Конвертация остановлена"})
            self.current_process = None

    def on_closing(self):
        """Сохранение ВСЕХ настроек перед закрытием (fix R11).

        Старая реализация сохраняла только часть переменных — audio_codec,
        audio_bitrate, use_crf, show_all_*, enable_trim, trim_*, use_local_ffmpeg
        терялись при каждом перезапуске.
        """
        self.config.update({
            # Видео
            "video_codec": self.video_codec.get(),
            "video_preset": self.video_preset.get(),
            "video_bitrate": self.video_bitrate.get(),
            "video_resolution": self.video_resolution.get(),
            "resolution_mode": self.resolution_mode.get(),
            "custom_resolution": self.custom_resolution.get(),
            "video_quality": self.video_quality.get(),
            "video_fps": self.video_fps.get(),
            # Аудио
            "audio_codec": self.audio_codec.get(),
            "audio_bitrate": self.audio_bitrate.get(),
            # Режимы
            "use_crf": self.use_crf.get(),
            "show_all_video_codecs": self.show_all_video_codecs.get(),
            "show_all_audio_codecs": self.show_all_audio_codecs.get(),
            # Обрезка
            "enable_trim": self.enable_trim.get(),
            "trim_start": self.trim_start.get(),
            "trim_end": self.trim_end.get(),
            # FFmpeg
            "hw_accel": self.hw_accel.get(),
            "use_local_ffmpeg": self.use_local_ffmpeg.get(),
            "ffmpeg_path": self.config.get("ffmpeg_path", "ffmpeg"),
            # Последние папки
            "last_input_dir": self.config.get("last_input_dir", ""),
            "last_output_dir": self.config.get("last_output_dir", ""),
        })
        self.config_manager.save(self.config)
        if self.current_process:
            self.stop_conversion()
        self.root.destroy()

def main():
    root = TkinterDnD.Tk()
    app = FFmpegConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main()