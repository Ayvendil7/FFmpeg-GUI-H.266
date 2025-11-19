import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import threading
from pathlib import Path
import json
import time
import re
from tkinterdnd2 import DND_FILES, TkinterDnD

# Версия приложения
VERSION = "v0.19"

class ToolTip:
    """Всплывающая подсказка для виджетов"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """Показать подсказку"""
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
        """Скрыть подсказку"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class ComboboxTooltip:
    """Всплывающая подсказка для элементов выпадающего списка"""
    def __init__(self, combobox, descriptions_dict):
        self.combobox = combobox
        self.descriptions = descriptions_dict
        self.tooltip = None
        
        # Привязываем события
        self.combobox.bind('<Motion>', self.on_motion)
        self.combobox.bind('<Leave>', self.hide_tooltip)
        
    def on_motion(self, event):
        """Обработчик движения мыши"""
        # Получаем текущее значение под курсором
        try:
            current_value = self.combobox.get()
            if current_value and ' - ' in current_value:
                # Извлекаем техническое название кодека
                codec_name = current_value.split(' - ')[0].strip()
                description = self.descriptions.get(codec_name, "")
                
                if description and len(description) > 60:
                    # Показываем полное описание если оно было обрезано
                    self.show_tooltip(event, description)
                else:
                    self.hide_tooltip()
            else:
                self.hide_tooltip()
        except:
            self.hide_tooltip()
    
    def show_tooltip(self, event, text):
        """Показать подсказку"""
        if self.tooltip:
            self.hide_tooltip()
            
        x = self.combobox.winfo_rootx() + 20
        y = self.combobox.winfo_rooty() + self.combobox.winfo_height() + 5
        
        self.tooltip = tw = tk.Toplevel(self.combobox)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        # Ограничиваем ширину подсказки
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                        background="#ffffe0", foreground="#000000",
                        relief=tk.SOLID, borderwidth=1,
                        font=("Segoe UI", 9), padx=8, pady=6,
                        wraplength=400)
        label.pack()
    
    def hide_tooltip(self, event=None):
        """Скрыть подсказку"""
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class ConfigManager:
    """Управление настройками приложения"""
    def __init__(self, config_file="ffmpeg_converter_config.json"):
        self.config_file = config_file
        self.default_config = {
            "ffmpeg_path": "ffmpeg",
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
        """Загрузка настроек из файла"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Объединяем с дефолтными настройками
                return {**self.default_config, **config}
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
        return self.default_config.copy()

    def save(self, config):
        """Сохранение настроек в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")

class CodecManager:
    """Управление кодеками и их отображением"""
    CODEC_DISPLAY_NAMES = {
        # Видео кодеки
        "libvvenc": "H.266 (VVC/libvvenc)",
        "libx265": "H.265 (HEVC/libx265)",
        "librav1e": "AV1 (librav1e)",
        "libvpx-vp9": "VP9 (libvpx-vp9)",
        "libaom-av1": "AV1 (libaom-av1)",
        # Аудио кодеки
        "libopus": "Opus (libopus)",
        "aac": "AAC",
        "libvorbis": "Vorbis (libvorbis)",
        "ac3": "AC3"
    }

    VIDEO_CODECS = ["libvvenc", "libx265", "librav1e", "libvpx-vp9", "libaom-av1"]
    AUDIO_CODECS = ["libopus", "aac", "libvorbis", "ac3"]

    @staticmethod
    def get_display_name(codec):
        """Получить пользовательское название кодека"""
        return CodecManager.CODEC_DISPLAY_NAMES.get(codec, codec)

    @staticmethod
    def get_tech_name(display_name):
        """Получить техническое название кодека по пользовательскому"""
        for tech, disp in CodecManager.CODEC_DISPLAY_NAMES.items():
            if disp == display_name:
                return tech
        return display_name

    @staticmethod
    def filter_supported(codecs, supported_list):
        """Фильтровать кодеки по списку поддерживаемых"""
        return [c for c in codecs if c in supported_list]

class FFmpegValidator:
    """Валидация параметров FFmpeg"""
    @staticmethod
    def validate_file_path(path, must_exist=True):
        """Валидация пути к файлу"""
        if not path:
            raise ValueError("Путь к файлу не указан")
        if must_exist and not os.path.exists(path):
            raise FileNotFoundError(f"Файл не найден: {path}")
        return True

    @staticmethod
    def validate_bitrate(bitrate):
        """Валидация битрейта"""
        pattern = r'^\d+[kKmM]$'
        if not re.match(pattern, bitrate):
            raise ValueError(f"Неверный формат битрейта: {bitrate}. Используйте формат: 384k, 2M")
        
        # Дополнительная проверка разумных значений
        value = int(bitrate[:-1])
        unit = bitrate[-1].lower()
        
        if unit == 'k':
            if value < 8 or value > 50000:
                raise ValueError(f"Битрейт {bitrate} вне разумного диапазона (8k-50000k)")
        elif unit == 'm':
            if value < 1 or value > 50:
                raise ValueError(f"Битрейт {bitrate} вне разумного диапазона (1M-50M)")
        
        return True

    @staticmethod
    def validate_resolution(resolution):
        """Валидация разрешения"""
        pattern = r'^\d+x\d+$'
        if not re.match(pattern, resolution):
            raise ValueError(f"Неверный формат разрешения: {resolution}. Используйте формат: 1280x720")
        return True

    @staticmethod
    def validate_fps(fps):
        """Валидация FPS"""
        try:
            fps_value = float(fps)
            if fps_value <= 0 or fps_value > 300:
                raise ValueError("FPS должен быть в диапазоне 1-300")
            return True
        except ValueError:
            raise ValueError(f"Неверное значение FPS: {fps}")

    @staticmethod
    def validate_quality(quality):
        """Валидация CRF/качества"""
        try:
            quality_value = int(quality)
            if quality_value < 0 or quality_value > 51:
                raise ValueError("Качество (CRF) должно быть в диапазоне 0-51")
            return True
        except ValueError:
            raise ValueError(f"Неверное значение качества: {quality}")

    @staticmethod
    def validate_timestamp(timestamp):
        """Валидация временной метки"""
        # Формат: HH:MM:SS или MM:SS или SS
        pattern = r'^(\d{1,2}:)?(\d{1,2}:)?\d{1,2}(\.\d+)?$'
        if not re.match(pattern, timestamp):
            raise ValueError(f"Неверный формат времени: {timestamp}. Используйте формат: HH:MM:SS")
        return True

class FFmpegConverter:
    def __init__(self, root):
        self.root = root
        self.root.title(f"FFmpeg Video Converter {VERSION}")
        self.root.geometry("900x800")
        self.root.minsize(800, 650)
        self.root.resizable(True, True)

        # Менеджеры
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()

        # Путь к FFmpeg
        self.ffmpeg_path = self.config.get("ffmpeg_path", "ffmpeg")

        # Процесс конвертации
        self.current_process = None
        self.start_time = None

        # Информация о FFmpeg и кодеках
        self.ffmpeg_version_info = ""
        self.ffmpeg_build_config = ""
        self.supported_encoders = []
        self.all_video_encoders = []
        self.all_audio_encoders = []
        self.video_encoder_descriptions = {}
        self.audio_encoder_descriptions = {}

        # Стили
        self.setup_styles()

        # Переменные
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.video_codec = tk.StringVar(value=self.config.get("video_codec", "libvvenc"))
        self.video_preset = tk.StringVar(value=self.config.get("video_preset", "medium"))
        self.video_bitrate = tk.StringVar(value=self.config.get("video_bitrate", "384k"))
        self.video_resolution = tk.StringVar(value=self.config.get("video_resolution", "1280x720"))
        self.resolution_mode = tk.StringVar(value=self.config.get("resolution_mode", "Исходное"))
        self.custom_resolution = tk.StringVar(value=self.config.get("custom_resolution", "1280x720"))
        
        # Обработчик изменения пользовательского разрешения
        self.custom_resolution.trace('w', self.on_custom_resolution_change)
        
        self.original_resolution = ""  # Будет установлено при автоопределении
        self.video_quality = tk.StringVar(value=self.config.get("video_quality", "25"))
        self.video_fps = tk.StringVar(value=self.config.get("video_fps", "30"))
        self.audio_codec = tk.StringVar(value=self.config.get("audio_codec", "libopus"))
        self.audio_bitrate = tk.StringVar(value=self.config.get("audio_bitrate", "64k"))
        self.use_crf = tk.BooleanVar(value=self.config.get("use_crf", False))
        
        # Независимые галочки для видео и аудио кодеков
        self.show_all_video_codecs = tk.BooleanVar(value=False)
        self.show_all_audio_codecs = tk.BooleanVar(value=False)

        # Переменные для обрезки видео
        self.enable_trim = tk.BooleanVar(value=self.config.get("enable_trim", False))
        self.trim_start = tk.StringVar(value=self.config.get("trim_start", "00:00:00"))
        self.trim_end = tk.StringVar(value=self.config.get("trim_end", "00:00:00"))
        self.video_duration = 0  # Длительность видео в секундах

        # Создание интерфейса
        self.create_widgets()

        # Настройка Drag & Drop
        self.setup_drag_drop()

        # Проверка наличия FFMPEG и получение информации
        self.check_ffmpeg_and_codecs()

        # Привязка события закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        """Настройка стилей интерфейса"""
        style = ttk.Style()
        style.theme_use('clam')

        # Цветовая схема
        self.colors = {
            'primary': '#3498db',
            'primary_hover': '#2980b9',
            'secondary': '#95a5a6',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'info': '#3498db',
            'light': '#ecf0f1',
            'dark': '#2c3e50',
            'background': '#f8f9fa',
            'card': '#ffffff',
            'border': '#dee2e6'
        }

        # Настройка стилей
        style.configure('TFrame', background=self.colors['background'])
        style.configure('TLabelframe', background=self.colors['background'])
        style.configure('TLabelframe.Label',
                       background=self.colors['background'],
                       foreground=self.colors['dark'],
                       font=('Segoe UI', 10, 'bold'))
        
        style.configure('TLabel',
                       background=self.colors['background'],
                       foreground=self.colors['dark'],
                       font=('Segoe UI', 9))
        
        style.configure('Header.TLabel',
                       font=('Segoe UI', 16, 'bold'),
                       foreground=self.colors['dark'],
                       background=self.colors['background'])
        
        style.configure('Card.TFrame',
                       background=self.colors['card'],
                       relief='solid',
                       borderwidth=1)

        # Стиль для кнопок
        style.configure('Modern.TButton',
                       font=('Segoe UI', 9),
                       padding=6,
                       relief='flat',
                       borderwidth=0)
        style.map('Modern.TButton',
                 background=[
                     ('active', self.colors['primary_hover']),
                     ('pressed', self.colors['primary_hover']),
                     ('!active', self.colors['primary'])
                 ],
                 foreground=[('active', 'white'), ('!active', 'white')],
                 relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        style.configure('Secondary.TButton',
                       font=('Segoe UI', 9),
                       padding=6,
                       relief='flat',
                       borderwidth=0)
        style.map('Secondary.TButton',
                 background=[
                     ('active', '#7f8c8d'),
                     ('pressed', '#7f8c8d'),
                     ('!active', self.colors['secondary'])
                 ],
                 foreground=[('active', 'white'), ('!active', 'white')])

        # Стиль для прогресс бара
        style.configure('Horizontal.TProgressbar',
                       troughcolor=self.colors['light'],
                       background=self.colors['primary'],
                       thickness=10)

        # Стиль для комбобоксов
        style.configure('TCombobox',
                       fieldbackground='white',
                       background='white',
                       arrowcolor=self.colors['dark'])

    def setup_drag_drop(self):
        """Настройка функциональности Drag & Drop"""
        # Регистрируем обработчики для входного файла
        self.input_entry.drop_target_register(DND_FILES)
        self.input_entry.dnd_bind('<<Drop>>', self.on_input_drop)

        # Регистрируем обработчики для выходного файла
        self.output_entry.drop_target_register(DND_FILES)
        self.output_entry.dnd_bind('<<Drop>>', self.on_output_drop)

    def on_input_drop(self, event):
        """Обработчик перетаскивания для входного файла"""
        files = self.parse_drop_files(event.data)
        if files:
            file_path = files[0]  # Берём первый файл
            self.input_file.set(file_path)
            # Автоматически устанавливаем выходной файл если не задан
            if not self.output_file.get():
                input_path = Path(file_path)
                output_path = input_path.parent / f"{input_path.stem}_converted.mp4"
                self.output_file.set(str(output_path))
            # Определяем параметры видео
            self.auto_detect_video_params(file_path)
            self.update_file_info()
            self.log(f"Файл добавлен: {file_path}", "success")

    def on_output_drop(self, event):
        """Обработчик перетаскивания для выходного файла"""
        files = self.parse_drop_files(event.data)
        if files:
            file_path = files[0]
            # Для выходного файла используем директорию + оригинальное имя входного файла
            if os.path.isdir(file_path):
                # Если перетащили директорию
                if self.input_file.get():
                    input_path = Path(self.input_file.get())
                    output_path = Path(file_path) / f"{input_path.stem}_converted.mp4"
                    self.output_file.set(str(output_path))
            else:
                # Если перетащили файл
                self.output_file.set(file_path)
            self.update_file_info()
            self.log(f"Выходной путь установлен: {self.output_file.get()}", "success")

    def parse_drop_files(self, data):
        """Парсинг файлов из события drop"""
        # Обработка различных форматов данных
        files = []
        if isinstance(data, str):
            # tkinterdnd2 передает пути в фигурных скобках для путей с пробелами
            # Например: {C:/путь с пробелами/файл.mp4} или несколько файлов
            data = data.strip()
            # Парсим пути в фигурных скобках
            if data.startswith('{'):
                # Разбираем строку с учетом фигурных скобок
                current_path = ""
                in_braces = False
                for char in data:
                    if char == '{':
                        in_braces = True
                        current_path = ""
                    elif char == '}':
                        in_braces = False
                        if current_path:
                            files.append(current_path.strip())
                        current_path = ""
                    elif in_braces:
                        current_path += char
            else:
                # Если нет фигурных скобок, просто добавляем путь как есть
                files = [data]
        elif isinstance(data, (list, tuple)):
            files = list(data)
        return files

    def create_widgets(self):
        """Создание виджетов интерфейса"""
        # Главный контейнер
        main_container = ttk.Frame(self.root, style='TFrame')
        main_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Заголовок
        header_frame = ttk.Frame(main_container, style='TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 12))

        # Название и версия
        title_frame = ttk.Frame(header_frame, style='TFrame')
        title_frame.pack(side=tk.LEFT)

        header_label = ttk.Label(title_frame, text="FFmpeg Video Converter", style='Header.TLabel')
        header_label.pack(side=tk.LEFT)

        version_label = ttk.Label(title_frame, text=VERSION,
                                 font=('Segoe UI', 9),
                                 foreground=self.colors['secondary'])
        version_label.pack(side=tk.LEFT, padx=(8, 0))

        # Кнопки в заголовке
        button_container = ttk.Frame(header_frame, style='TFrame')
        button_container.pack(side=tk.RIGHT)

        ttk.Button(button_container, text="Настройки FFmpeg",
                  command=self.show_ffmpeg_settings,
                  style='Secondary.TButton').pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(button_container, text="Инфо о FFmpeg",
                  command=self.show_ffmpeg_info,
                  style='Secondary.TButton').pack(side=tk.LEFT)

        # Основной контент
        content_frame = ttk.Frame(main_container, style='Card.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Файлы
        self.create_file_section(content_frame)

        # Обрезка видео
        self.create_trim_section(content_frame)

        # Параметры
        params_frame = ttk.Frame(content_frame, style='TFrame')
        params_frame.pack(fill=tk.BOTH, expand=True)

        # Видео параметры
        self.create_video_section(params_frame)

        # Аудио параметры
        self.create_audio_section(params_frame)

        # Прогресс и логи
        self.create_progress_section(content_frame)

        # Информационная панель
        self.create_info_section(content_frame)

    def create_file_section(self, parent):
        """Создание секции выбора файлов"""
        frame = ttk.LabelFrame(parent, text="Файлы (поддерживается Drag & Drop)", padding="12")
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        # Входной файл
        ttk.Label(frame, text="Входной файл:").grid(row=0, column=0, sticky=tk.W, pady=4)
        
        input_frame = ttk.Frame(frame)
        input_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 4), pady=4)
        input_frame.columnconfigure(0, weight=1)
        
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_file, state='readonly')
        self.input_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(input_frame, text="Обзор", command=self.browse_input, style='Modern.TButton').grid(row=0, column=1, padx=(4, 0))

        # Выходной файл
        ttk.Label(frame, text="Выходной файл:").grid(row=1, column=0, sticky=tk.W, pady=4)
        
        output_frame = ttk.Frame(frame)
        output_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 4), pady=4)
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_file, state='readonly')
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(output_frame, text="Обзор", command=self.browse_output, style='Modern.TButton').grid(row=0, column=1, padx=(4, 0))

    def create_trim_section(self, parent):
        """Создание секции обрезки видео"""
        frame = ttk.LabelFrame(parent, text="Обрезка видео", padding="12")
        frame.pack(fill=tk.X, pady=(0, 10))
        frame.columnconfigure(1, weight=1)

        # Галочка и поля времени в одной строке
        trim_checkbox = ttk.Checkbutton(frame, text="Обрезать видео",
                                       variable=self.enable_trim,
                                       command=self.toggle_trim_controls)
        trim_checkbox.grid(row=0, column=0, sticky=tk.W, padx=(0, 16))

        trim_tooltip = (
            "Позволяет вырезать нужный фрагмент из видео.\n"
            "Полезно для удаления заставок, титров или рекламы.\n\n"
            "Формат времени: ЧЧ:MM:СС (например: 01:23:45)\n"
            "или MM:СС (например: 05:30)\n"
            "или просто секунды (например: 150)"
        )
        ToolTip(trim_checkbox, trim_tooltip)

        # Контейнер для полей времени
        time_container = ttk.Frame(frame)
        time_container.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0))

        # Начало
        ttk.Label(time_container, text="Начало:").pack(side=tk.LEFT, padx=(0, 4))
        self.trim_start_entry = ttk.Entry(time_container, textvariable=self.trim_start, width=10)
        self.trim_start_entry.pack(side=tk.LEFT, padx=(0, 16))

        # Конец
        ttk.Label(time_container, text="Конец:").pack(side=tk.LEFT, padx=(0, 4))
        self.trim_end_entry = ttk.Entry(time_container, textvariable=self.trim_end, width=10)
        self.trim_end_entry.pack(side=tk.LEFT, padx=(0, 12))

        # Метка длительности
        self.duration_label = ttk.Label(time_container, text="",
                                       foreground=self.colors['secondary'])
        self.duration_label.pack(side=tk.LEFT)

        # Изначально отключаем контролы если обрезка выключена
        if not self.enable_trim.get():
            self.trim_start_entry.config(state='disabled')
            self.trim_end_entry.config(state='disabled')

    def toggle_trim_controls(self):
        """Переключение доступности контролов обрезки"""
        if self.enable_trim.get():
            self.trim_start_entry.config(state='normal')
            self.trim_end_entry.config(state='normal')
        else:
            self.trim_start_entry.config(state='disabled')
            self.trim_end_entry.config(state='disabled')

    def create_video_section(self, parent):
        """Создание секции параметров видео"""
        frame = ttk.LabelFrame(parent, text="Параметры видео", padding="12")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        frame.columnconfigure(1, weight=1)

        row = 0

        # Кодек с галочкой "Показать все"
        ttk.Label(frame, text="Кодек:").grid(row=row, column=0, sticky=tk.W, pady=4)
        
        codec_container = ttk.Frame(frame)
        codec_container.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        codec_container.columnconfigure(0, weight=1)
        
        self.video_codec_combobox = ttk.Combobox(codec_container, state="readonly")
        self.video_codec_combobox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.video_codec_combobox.bind("<<ComboboxSelected>>", self.on_video_codec_change)
        
        # Галочка "Показать все" для видео
        show_all_video = ttk.Checkbutton(codec_container, text="Ещё", 
                                        variable=self.show_all_video_codecs,
                                        command=self.toggle_video_codecs)
        show_all_video.grid(row=0, column=1, padx=(4, 0))
        
        row += 1

        # Пресет и CRF в одной строке
        ttk.Label(frame, text="Пресет:").grid(row=row, column=0, sticky=tk.W, pady=4)
        
        preset_crf_container = ttk.Frame(frame)
        preset_crf_container.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        preset_crf_container.columnconfigure(0, weight=1)
        
        # Пресет (половина ширины)
        preset_combo = ttk.Combobox(preset_crf_container, textvariable=self.video_preset,
                    values=["faster", "fast", "medium", "slow", "slower"],
                    state="readonly", width=10)
        preset_combo.grid(row=0, column=0, sticky=tk.W)
        
        # CRF чекбокс
        crf_checkbox = ttk.Checkbutton(preset_crf_container, text="CRF",
                                      variable=self.use_crf,
                                      command=self.toggle_encoding_mode)
        crf_checkbox.grid(row=0, column=1, padx=(12, 0), sticky=tk.W)

        # Добавляем подсказку для CRF
        crf_tooltip_text = (
            "CRF (Constant Rate Factor) - режим постоянного качества.\n\n"
            "• Значения: 0-51 (меньше = лучше качество, больше размер файла)\n"
            "• Рекомендуемые значения:\n"
            "  - 18-23: Высокое качество\n"
            "  - 23-28: Среднее качество (оптимально)\n"
            "  - 28-35: Низкое качество\n\n"
            "В отличие от битрейта, CRF адаптирует сжатие под сложность сцены,\n"
            "обеспечивая более стабильное визуальное качество."
        )
        ToolTip(crf_checkbox, crf_tooltip_text)

        row += 1

        # Битрейт и FPS в одной строке
        self.bitrate_label = ttk.Label(frame, text="Битрейт:")
        self.bitrate_label.grid(row=row, column=0, sticky=tk.W, pady=4)
        
        bitrate_fps_container = ttk.Frame(frame)
        bitrate_fps_container.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        bitrate_fps_container.columnconfigure(0, weight=1)
        
        # Битрейт/Качество
        self.bitrate_entry = ttk.Entry(bitrate_fps_container, textvariable=self.video_bitrate, width=12)
        self.bitrate_entry.grid(row=0, column=0, sticky=tk.W)
        
        # Добавляем подсказку для битрейта
        bitrate_tooltip = (
            "Битрейт видео определяет качество и размер файла.\n\n"
            "Форматы: 384k, 2M (k = килобит/с, M = мегабит/с)\n"
            "Если не указать единицу, автоматически добавится 'k'.\n\n"
            "Рекомендуемые значения:\n"
            "  • 720p: 1000-2500k\n"
            "  • 1080p: 2500-5000k\n"
            "  • 4K: 8000-20000k"
        )
        ToolTip(self.bitrate_entry, bitrate_tooltip)
        
        # FPS
        ttk.Label(bitrate_fps_container, text="FPS:").grid(row=0, column=1, padx=(12, 4), sticky=tk.W)
        fps_entry = ttk.Entry(bitrate_fps_container, textvariable=self.video_fps, width=8)
        fps_entry.grid(row=0, column=2, sticky=tk.W)
        
        row += 1

        # Разрешение
        ttk.Label(frame, text="Разрешение:").grid(row=row, column=0, sticky=tk.W, pady=4)
        
        resolution_frame = ttk.Frame(frame)
        resolution_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        resolution_frame.columnconfigure(1, weight=1)

        # Комбобокс с разрешениями
        resolution_options = ["Исходное", "VGA (640x480)", "DVD (720x480)", "DVD+ (960x540)", "HD (1280x720)", "FHD (1920x1080)", "Особое"]
        self.resolution_combobox = ttk.Combobox(resolution_frame,
                                               textvariable=self.resolution_mode,
                                               values=resolution_options,
                                               state="readonly",
                                               width=14)
        self.resolution_combobox.grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.resolution_combobox.bind("<<ComboboxSelected>>", self.on_resolution_mode_change)

        # Поле для особого разрешения
        self.custom_resolution_entry = ttk.Entry(resolution_frame, textvariable=self.custom_resolution, width=12)
        self.custom_resolution_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))

        # Изначально скрываем поле для особого разрешения
        if self.resolution_mode.get() != "Особое":
            self.custom_resolution_entry.grid_remove()

        # Обновляем интерфейс в зависимости от режима
        self.toggle_encoding_mode()

    def toggle_encoding_mode(self):
        """Переключение между режимами битрейта и CRF"""
        if self.use_crf.get():
            self.bitrate_label.config(text="Качество (CRF):")
            self.bitrate_entry.config(textvariable=self.video_quality)
        else:
            self.bitrate_label.config(text="Битрейт:")
            self.bitrate_entry.config(textvariable=self.video_bitrate)

    def on_video_codec_change(self, event):
        """Обработчик изменения выбора видео кодека"""
        selected_display_name = self.video_codec_combobox.get()
        
        # Если это формат "codec - description", извлекаем только название кодека
        if ' - ' in selected_display_name:
            tech_name = selected_display_name.split(' - ')[0].strip()
        else:
            tech_name = CodecManager.get_tech_name(selected_display_name)
            # Если это нераспознанный кодек из полного списка
            if tech_name == selected_display_name and selected_display_name not in CodecManager.CODEC_DISPLAY_NAMES.values():
                tech_name = selected_display_name
        
        self.video_codec.set(tech_name)

    def create_audio_section(self, parent):
        """Создание секции параметров аудио и управления"""
        frame = ttk.LabelFrame(parent, text="Параметры аудио и управление", padding="12")
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        # Кодек с галочкой "Показать все"
        ttk.Label(frame, text="Кодек:").grid(row=0, column=0, sticky=tk.W, pady=4)
        
        codec_frame = ttk.Frame(frame)
        codec_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        codec_frame.columnconfigure(0, weight=1)
        
        self.audio_codec_combobox = ttk.Combobox(codec_frame, state="readonly")
        self.audio_codec_combobox.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.audio_codec_combobox.bind("<<ComboboxSelected>>", self.on_audio_codec_change)
        
        # Галочка "Показать все" для аудио
        show_all_audio = ttk.Checkbutton(codec_frame, text="Ещё", 
                                        variable=self.show_all_audio_codecs,
                                        command=self.toggle_audio_codecs)
        show_all_audio.grid(row=0, column=1, padx=(4, 0))

        # Битрейт
        ttk.Label(frame, text="Битрейт:").grid(row=1, column=0, sticky=tk.W, pady=4)
        
        bitrate_frame = ttk.Frame(frame)
        bitrate_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        
        audio_bitrate_entry = ttk.Entry(bitrate_frame, textvariable=self.audio_bitrate)
        audio_bitrate_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Добавляем подсказку для аудио битрейта
        audio_bitrate_tooltip = (
            "Битрейт аудио определяет качество звука.\n\n"
            "Форматы: 64k, 128k, 192k\n"
            "Если не указать 'k', она добавится автоматически.\n\n"
            "Рекомендуемые значения:\n"
            "  • Речь/подкасты: 32-64k\n"
            "  • Музыка (стерео): 128-192k\n"
            "  • Музыка (высокое качество): 256-320k"
        )
        ToolTip(audio_bitrate_entry, audio_bitrate_tooltip)

        # Разделитель
        separator = ttk.Separator(frame, orient='horizontal')
        separator.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(12, 8))

        # Кнопки управления
        button_frame = ttk.Frame(frame, style='TFrame')
        button_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(4, 0))
        button_frame.columnconfigure(0, weight=1)

        # Центральный контейнер для кнопок
        buttons_container = ttk.Frame(button_frame, style='TFrame')
        buttons_container.grid(row=0, column=0)

        self.convert_button = ttk.Button(buttons_container, text="Начать конвертацию",
                                        command=self.start_conversion,
                                        style='Modern.TButton',
                                        width=18)
        self.convert_button.grid(row=0, column=0, padx=(0, 4))

        self.stop_button = ttk.Button(buttons_container, text="Остановить",
                                     command=self.stop_conversion,
                                     state='disabled',
                                     style='Secondary.TButton',
                                     width=13)
        self.stop_button.grid(row=0, column=1, padx=(4, 4))

        ttk.Button(buttons_container, text="Предпросмотр команды",
                  command=self.preview_command,
                  style='Secondary.TButton',
                  width=18).grid(row=0, column=2, padx=(4, 0))

    def on_audio_codec_change(self, event):
        """Обработчик изменения выбора аудио кодека"""
        selected_display_name = self.audio_codec_combobox.get()
        
        # Если это формат "codec - description", извлекаем только название кодека
        if ' - ' in selected_display_name:
            tech_name = selected_display_name.split(' - ')[0].strip()
        else:
            tech_name = CodecManager.get_tech_name(selected_display_name)
            # Если это нераспознанный кодек из полного списка
            if tech_name == selected_display_name and selected_display_name not in CodecManager.CODEC_DISPLAY_NAMES.values():
                tech_name = selected_display_name
        
        self.audio_codec.set(tech_name)

    def on_custom_resolution_change(self, *args):
        """Обработчик изменения пользовательского разрешения"""
        if self.resolution_mode.get() == "Особое":
            self.video_resolution.set(self.custom_resolution.get())

    def on_resolution_mode_change(self, event):
        """Обработчик изменения режима разрешения"""
        mode = self.resolution_mode.get()
        
        if mode == "Особое":
            # Показываем поле для ввода
            self.custom_resolution_entry.grid()
            self.video_resolution.set(self.custom_resolution.get())
        else:
            # Скрываем поле для ввода
            self.custom_resolution_entry.grid_remove()
            
            # Устанавливаем разрешение в зависимости от выбранного режима
            if mode == "Исходное":
                if self.original_resolution:
                    self.video_resolution.set(self.original_resolution)
                else:
                    self.video_resolution.set("1280x720")  # Значение по умолчанию
            elif mode == "VGA (640x480)":
                self.video_resolution.set("640x480")
            elif mode == "DVD (720x480)":
                self.video_resolution.set("720x480")
            elif mode == "DVD+ (960x540)":
                self.video_resolution.set("960x540")
            elif mode == "HD (1280x720)":
                self.video_resolution.set("1280x720")
            elif mode == "FHD (1920x1080)":
                self.video_resolution.set("1920x1080")

    def toggle_video_codecs(self):
        """Переключение между предустановленными и всеми видео кодеками"""
        self.filter_video_codec_options()
        
    def toggle_audio_codecs(self):
        """Переключение между предустановленными и всеми аудио кодеками"""
        self.filter_audio_codec_options()
                
        
    def create_progress_section(self, parent):
        """Создание секции прогресса и логов"""
        frame = ttk.LabelFrame(parent, text="Прогресс и логи", padding="12")
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        # Прогресс бар и информация
        progress_frame = ttk.Frame(frame, style='TFrame')
        progress_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        progress_frame.columnconfigure(1, weight=1)

        # Прогресс бар
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame,
                                           variable=self.progress_var,
                                           maximum=100,
                                           style='Horizontal.TProgressbar')
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))

        # Текст прогресса
        self.progress_label = ttk.Label(progress_frame, text="Готово к конвертации")
        self.progress_label.grid(row=1, column=0, sticky=tk.W)

        # Оставшееся время
        self.time_label = ttk.Label(progress_frame, text="")
        self.time_label.grid(row=1, column=1, sticky=tk.E)

        # Текстовое поле для логов
        log_frame = ttk.Frame(frame)
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=7, wrap=tk.WORD,
                               font=('Consolas', 8),
                               bg=self.colors['light'],
                               fg=self.colors['dark'],
                               relief='flat',
                               borderwidth=1)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Создание контекстного меню и биндингов
        self.create_context_menu()

    def create_info_section(self, parent):
        """Создание секции информации о файлах"""
        frame = ttk.LabelFrame(parent, text="Информация о файлах", padding="12")
        frame.pack(fill=tk.X)
        frame.columnconfigure(1, weight=1)

        # Информация о входном файле (компактный формат)
        ttk.Label(frame, text="Входной файл:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_info_label = ttk.Label(frame, text="Не выбран", background=self.colors['background'])
        self.input_info_label.grid(row=0, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        # Информация о выходном файле
        ttk.Label(frame, text="Выходной файл:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_info_label = ttk.Label(frame, text="Не создан", background=self.colors['background'])
        self.output_info_label.grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        # Экономия места
        ttk.Label(frame, text="Экономия:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.saving_label = ttk.Label(frame, text="0%", background=self.colors['background'])
        self.saving_label.grid(row=2, column=1, sticky=tk.W, padx=(8, 0), pady=2)

    def create_context_menu(self):
        """Создание контекстного меню для текстового поля лога"""
        self.context_menu = tk.Menu(self.log_text, tearoff=0, font=('Segoe UI', 9))
        self.context_menu.add_command(label="Копировать", command=self.copy_text)
        self.context_menu.add_command(label="Выделить всё", command=self.select_all_text)
        self.context_menu.add_command(label="Очистить", command=self.clear_log)

        # Привязка события правой кнопки мыши
        self.log_text.bind("<Button-3>", self.show_context_menu)

        # Привязка горячих клавиш
        self.log_text.bind("<Control-a>", lambda event: self.select_all_text())
        self.log_text.bind("<Control-A>", lambda event: self.select_all_text())
        self.log_text.bind("<Control-c>", lambda event: self.copy_text())
        self.log_text.bind("<Control-C>", lambda event: self.copy_text())

    def show_context_menu(self, event):
        """Показ контекстного меню"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_text(self):
        """Копирование выделенного текста в буфер обмена"""
        try:
            selected_text = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            pass

    def select_all_text(self):
        """Выделение всего текста"""
        self.log_text.tag_add(tk.SEL, "1.0", tk.END)
        self.log_text.mark_set(tk.INSERT, "1.0")
        self.log_text.see(tk.INSERT)
        return "break"

    def clear_log(self):
        """Очистка лога"""
        self.log_text.delete('1.0', tk.END)

    def browse_input(self):
        """Выбор входного файла"""
        initial_dir = self.config.get("last_input_dir", "")
        filename = filedialog.askopenfilename(
            title="Выберите входной файл",
            initialdir=initial_dir if initial_dir and os.path.exists(initial_dir) else None,
            filetypes=[
                ("Все файлы", "*.*"),
                ("Видео файлы", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.mts *.m2ts"),
                ("Аудио файлы", "*.mp3 *.wav *.aac *.flac *.m4a *.ogg *.opus")
            ]
        )
        if filename:
            self.input_file.set(filename)
            self.config["last_input_dir"] = str(Path(filename).parent)
            
            if not self.output_file.get():
                input_path = Path(filename)
                output_path = input_path.parent / f"{input_path.stem}_converted.mp4"
                self.output_file.set(str(output_path))
            
            # Автоматическое определение параметров видео
            self.auto_detect_video_params(filename)
            
            # Обновление информации о файлах
            self.update_file_info()

    def browse_output(self):
        """Выбор выходного файла"""
        initial_dir = self.config.get("last_output_dir", "")
        filename = filedialog.asksaveasfilename(
            title="Сохранить как",
            initialdir=initial_dir if initial_dir and os.path.exists(initial_dir) else None,
            defaultextension=".mp4",
            filetypes=[("MP4 файлы", "*.mp4"), ("MKV файлы", "*.mkv"), ("WebM файлы", "*.webm"), ("Все файлы", "*.*")]
        )
        if filename:
            self.output_file.set(filename)
            self.config["last_output_dir"] = str(Path(filename).parent)
            self.update_file_info()

    def update_file_info(self):
        """Обновление информации о файлах (компактный формат)"""
        input_path = self.input_file.get()
        output_path = self.output_file.get()

        # Информация о входном файле
        if input_path and os.path.exists(input_path):
            info_parts = []
            
            # Размер файла
            size = os.path.getsize(input_path)
            size_str = self.format_file_size(size)
            info_parts.append(size_str)
            
            # Получаем подробную информацию
            video_info = self.get_video_info(input_path)
            if video_info:
                # Длительность
                if video_info['duration']:
                    duration_str = self.format_duration(video_info['duration'])
                    info_parts.append(duration_str)
                    
                    # Сохраняем длительность для расчетов
                    self.video_duration = video_info['duration']
                    
                    # Если обрезка не включена, устанавливаем конечное время = длительности видео
                    if not self.enable_trim.get() or self.trim_end.get() == "00:00:00":
                        self.trim_end.set(self.seconds_to_timestamp(video_info['duration']))
                        self.update_trim_duration_label()
                
                # Формат (только короткое название)
                if video_info['format']:
                    format_name = video_info['format'].split(',')[0].split('/')[0].strip()
                    if len(format_name) > 15:
                        format_name = format_name[:12] + "..."
                    info_parts.append(format_name)
                
                # Видео информация
                video_parts = []
                if video_info['video_codec']:
                    # Извлекаем короткое название кодека
                    codec_name = video_info['video_codec'].split('/')[0].strip()
                    if '(' in codec_name:
                        codec_name = codec_name.split('(')[0].strip()
                    video_parts.append(codec_name[:15])
                
                if video_info['video_bitrate']:
                    video_parts.append(video_info['video_bitrate'])
                
                if video_info['resolution']:
                    res_fps = video_info['resolution']
                    if video_info['fps']:
                        res_fps += f"@{video_info['fps']}fps"
                    video_parts.append(res_fps)
                
                if video_parts:
                    info_parts.append(", ".join(video_parts))
                
                # Аудио информация
                audio_parts = []
                if video_info['audio_codec']:
                    # Извлекаем короткое название кодека
                    codec_name = video_info['audio_codec'].split('(')[0].strip()
                    audio_parts.append(codec_name[:10])
                
                if video_info['audio_bitrate']:
                    audio_parts.append(video_info['audio_bitrate'])
                
                if video_info['audio_channels']:
                    # Извлекаем только лейаут (без цифры)
                    if '(' in video_info['audio_channels']:
                        layout = video_info['audio_channels'].split('(')[1].rstrip(')')
                        audio_parts.append(layout.capitalize())
                    else:
                        audio_parts.append(f"{video_info['audio_channels']}ch")
                
                if video_info['audio_sample_rate']:
                    audio_parts.append(video_info['audio_sample_rate'])
                
                if audio_parts:
                    info_parts.append(", ".join(audio_parts))
            
            # Собираем всё в одну строку
            if info_parts:
                self.input_info_label.config(text=" | ".join(info_parts))
            else:
                self.input_info_label.config(text=size_str)
        else:
            self.input_info_label.config(text="Не выбран")

        # Информация о выходном файле
        if output_path and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            size_str = self.format_file_size(size)
            self.output_info_label.config(text=f"{size_str}")
        else:
            self.output_info_label.config(text="Не создан")

        # Расчет экономии
        self.calculate_saving()

    def update_trim_duration_label(self):
        """Обновление метки с длительностью обрезанного фрагмента"""
        try:
            start_seconds = self.timestamp_to_seconds(self.trim_start.get())
            end_seconds = self.timestamp_to_seconds(self.trim_end.get())
            
            if end_seconds > start_seconds:
                duration = end_seconds - start_seconds
                duration_str = self.seconds_to_timestamp(duration)
                self.duration_label.config(text=f"Длительность: {duration_str}")
            else:
                self.duration_label.config(text="")
        except:
            self.duration_label.config(text="")

    def timestamp_to_seconds(self, timestamp):
        """Конвертация временной метки в секунды"""
        parts = timestamp.split(':')
        if len(parts) == 3:  # HH:MM:SS
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:  # MM:SS
            m, s = map(float, parts)
            return m * 60 + s
        else:  # SS
            return float(parts[0])

    def seconds_to_timestamp(self, seconds):
        """Конвертация секунд во временную метку"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def format_duration(self, seconds):
        """Форматирование длительности видео"""
        try:
            seconds = int(float(seconds))
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            else:
                return f"{minutes:02d}:{secs:02d}"
        except:
            return "—"

    def format_file_size(self, size_bytes):
        """Форматирование размера файла"""
        if size_bytes == 0:
            return "0 Б"
        size_names = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

    def calculate_saving(self):
        """Расчет экономии места"""
        input_path = self.input_file.get()
        output_path = self.output_file.get()

        if input_path and output_path and os.path.exists(input_path) and os.path.exists(output_path):
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            
            if input_size > 0:
                saving_percent = (1 - output_size / input_size) * 100
                if saving_percent > 0:
                    self.saving_label.config(text=f"{saving_percent:.1f}% (меньше)",
                                           foreground=self.colors['success'])
                else:
                    self.saving_label.config(text=f"{abs(saving_percent):.1f}% (больше)",
                                           foreground=self.colors['danger'])
            else:
                self.saving_label.config(text="0%")
        else:
            self.saving_label.config(text="0%", foreground=self.colors['dark'])

    def auto_detect_video_params(self, filepath):
        """Автоматическое определение параметров видео"""
        self.root.config(cursor="watch")
        self.root.update()
        
        video_info = self.get_video_info(filepath)
        if video_info:
            if video_info['resolution']:
                # Сохраняем исходное разрешение
                self.original_resolution = video_info['resolution']
                self.video_resolution.set(video_info['resolution'])
                
                # Устанавливаем режим "Исходное" по умолчанию
                self.resolution_mode.set("Исходное")
                self.custom_resolution_entry.grid_remove()
                
                self.log(f"Определено разрешение: {video_info['resolution']}", "info")
            
            if video_info['fps']:
                self.video_fps.set(video_info['fps'])
                self.log(f"Определено FPS: {video_info['fps']}", "info")
            
            # Устанавливаем длительность для обрезки
            if video_info['duration']:
                self.video_duration = video_info['duration']
                self.trim_end.set(self.seconds_to_timestamp(video_info['duration']))
                self.log(f"Длительность: {self.format_duration(video_info['duration'])}", "info")
        else:
            self.log("Не удалось автоматически определить параметры видео", "warning")
        
        self.root.config(cursor="")

    def get_video_info(self, filepath):
        """Получение подробной информации о медиафайле"""
        try:
            if not os.path.exists(filepath):
                return None

            # Определяем путь к ffprobe
            ffprobe_path = self.get_ffprobe_path()
            
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                filepath
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                info = {
                    'resolution': None,
                    'fps': None,
                    'video_codec': None,
                    'video_bitrate': None,
                    'audio_codec': None,
                    'audio_bitrate': None,
                    'duration': None,
                    'format': None,
                    'audio_channels': None,
                    'audio_sample_rate': None
                }

                # Получаем информацию о формате
                format_data = data.get('format', {})
                info['format'] = format_data.get('format_long_name', format_data.get('format_name', 'Неизвестен'))
                
                # Получаем длительность
                duration = format_data.get('duration')
                if duration:
                    try:
                        info['duration'] = float(duration)
                    except:
                        pass

                # Поиск видео и аудио потоков
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type')
                    
                    if codec_type == 'video' and not info['video_codec']:
                        # Видео информация
                        width = stream.get('width')
                        height = stream.get('height')
                        info['resolution'] = f"{width}x{height}" if width and height else None
                        
                        # FPS
                        avg_frame_rate = stream.get('avg_frame_rate')
                        if avg_frame_rate and avg_frame_rate != '0/0':
                            try:
                                num, den = map(int, avg_frame_rate.split('/'))
                                if den != 0:
                                    info['fps'] = str(int(num / den))
                            except:
                                pass
                        
                        # Видео кодек
                        codec_name = stream.get('codec_long_name', stream.get('codec_name', 'Неизвестен'))
                        info['video_codec'] = codec_name
                        
                        # Видео битрейт
                        bitrate = stream.get('bit_rate')
                        if bitrate:
                            try:
                                bitrate_kbps = int(bitrate) // 1000
                                info['video_bitrate'] = f"{bitrate_kbps} kbps"
                            except:
                                pass
                    
                    elif codec_type == 'audio' and not info['audio_codec']:
                        # Аудио информация
                        codec_name = stream.get('codec_long_name', stream.get('codec_name', 'Неизвестен'))
                        info['audio_codec'] = codec_name
                        
                        # Аудио битрейт
                        bitrate = stream.get('bit_rate')
                        if bitrate:
                            try:
                                bitrate_kbps = int(bitrate) // 1000
                                info['audio_bitrate'] = f"{bitrate_kbps} kbps"
                            except:
                                pass
                        
                        # Количество каналов
                        channels = stream.get('channels')
                        if channels:
                            channel_layout = stream.get('channel_layout', '')
                            info['audio_channels'] = f"{channels} ({channel_layout})" if channel_layout else str(channels)
                        
                        # Частота дискретизации
                        sample_rate = stream.get('sample_rate')
                        if sample_rate:
                            try:
                                rate_khz = int(sample_rate) // 1000
                                info['audio_sample_rate'] = f"{rate_khz} kHz"
                            except:
                                pass

                return info
            
            return None

        except subprocess.TimeoutExpired:
            self.log("Превышено время ожидания при получении информации о медиафайле", "warning")
            return None
        except Exception as e:
            self.log(f"Ошибка при получении информации о медиафайле: {e}", "warning")
            return None

    def get_ffprobe_path(self):
        """Получение пути к ffprobe"""
        if os.path.exists(self.ffmpeg_path) and self.ffmpeg_path.endswith('ffmpeg.exe'):
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe')
            if os.path.exists(ffprobe_path):
                return ffprobe_path
        return "ffprobe"

    def check_ffmpeg_and_codecs(self):
        """Проверка наличия FFmpeg и получение информации о кодеках"""
        self.root.config(cursor="watch")
        self.root.update()
        
        try:
            # Проверяем наличие ffmpeg
            result = subprocess.run([self.ffmpeg_path, '-version'],
                                  capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                version_lines = result.stdout.split('\n')
                self.ffmpeg_version_info = version_lines[0] if version_lines else "Неизвестная версия"
                
                # Попробуем получить более подробную информацию о сборке
                build_line = ""
                for line in version_lines[1:4]:
                    if 'configuration:' in line:
                        build_line = line.strip()
                        break
                
                self.ffmpeg_build_config = build_line if build_line else "Информация о сборке недоступна"
                
                self.log(f"FFmpeg найден: {self.ffmpeg_version_info}", "success")
                
                # Проверяем доступные кодеки
                result = subprocess.run([self.ffmpeg_path, '-encoders'],
                                      capture_output=True, text=True, timeout=20)
                
                available_encoders_output = result.stdout
                
                self.supported_encoders = []
                self.all_video_encoders = []
                self.all_audio_encoders = []
                self.video_encoder_descriptions = {}
                self.audio_encoder_descriptions = {}
                encoders_info = []
                
                # Парсим вывод для всех кодеков
                in_encoders_section = False
                for line in available_encoders_output.split('\n'):
                    # Ищем начало секции кодеков
                    if '------' in line:
                        in_encoders_section = True
                        continue
                    
                    if in_encoders_section and line.strip():
                        # Формат строки: " V..... libx264             libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10"
                        # Разбиваем на тип, название и описание
                        parts = line.strip().split(maxsplit=2)
                        if len(parts) >= 2:
                            encoder_type = parts[0]
                            encoder_name = parts[1]
                            encoder_description = parts[2] if len(parts) >= 3 else encoder_name
                            
                            # V = video, A = audio
                            if 'V' in encoder_type:
                                self.all_video_encoders.append(encoder_name)
                                self.video_encoder_descriptions[encoder_name] = encoder_description
                                # Проверяем предустановленные кодеки
                                if encoder_name in CodecManager.VIDEO_CODECS:
                                    self.supported_encoders.append(encoder_name)
                                    encoders_info.append(CodecManager.get_display_name(encoder_name))
                            elif 'A' in encoder_type:
                                self.all_audio_encoders.append(encoder_name)
                                self.audio_encoder_descriptions[encoder_name] = encoder_description
                                # Проверяем предустановленные кодеки
                                if encoder_name in CodecManager.AUDIO_CODECS:
                                    self.supported_encoders.append(encoder_name)
                                    encoders_info.append(CodecManager.get_display_name(encoder_name))
                
                # Фильтруем списки в GUI на основе поддерживаемых кодеков
                self.filter_video_codec_options()
                self.filter_audio_codec_options()
                
                if encoders_info:
                    self.log(f"Поддерживаемые кодеки: {', '.join(encoders_info[:5])}...", "info")
                else:
                    self.log("Не найдено поддерживаемых кодеков!", "warning")
                
            else:
                raise Exception("FFmpeg вернул ошибку")
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            error_msg = f"FFmpeg не найден или недоступен: {e}"
            self.log(f"Ошибка: {error_msg}", "error")
            messagebox.showwarning("Внимание",
                                 f"{error_msg}\n\nПожалуйста, настройте путь к FFmpeg в настройках.")
        finally:
            self.root.config(cursor="")

    def filter_video_codec_options(self):
        """Фильтрует опции видео кодеков в выпадающих списках"""
        if self.show_all_video_codecs.get():
            # Показываем все доступные видео кодеки
            video_codecs_to_show = self.all_video_encoders
        else:
            # Показываем только предустановленные видео кодеки
            video_codecs_to_show = CodecManager.filter_supported(CodecManager.VIDEO_CODECS, self.supported_encoders)
        
        # Формируем отображаемые названия с описаниями
        video_display_names = []
        for codec in video_codecs_to_show:
            if self.show_all_video_codecs.get() and hasattr(self, 'video_encoder_descriptions'):
                # Для всех кодеков показываем с описанием
                description = self.video_encoder_descriptions.get(codec, codec)
                # Ограничиваем длину описания для читаемости
                if len(description) > 60:
                    description = description[:57] + "..."
                display_name = f"{codec} - {description}"
            else:
                # Для предустановленных используем красивые имена
                display_name = CodecManager.get_display_name(codec)
            video_display_names.append(display_name)
        
        # Обновляем значения в комбобоксе
        self.video_codec_combobox['values'] = video_display_names
        
        # Проверяем, поддерживается ли текущий выбранный кодек
        current_video_tech = self.video_codec.get()
        if current_video_tech not in video_codecs_to_show and video_codecs_to_show:
            self.video_codec.set(video_codecs_to_show[0])
            self.video_codec_combobox.set(video_display_names[0])
        else:
            # Обновляем отображаемое имя
            if self.show_all_video_codecs.get() and hasattr(self, 'video_encoder_descriptions'):
                description = self.video_encoder_descriptions.get(current_video_tech, current_video_tech)
                if len(description) > 60:
                    description = description[:57] + "..."
                current_display = f"{current_video_tech} - {description}"
            else:
                current_display = CodecManager.get_display_name(current_video_tech)
            self.video_codec_combobox.set(current_display)
        
        # Добавляем всплывающие подсказки для комбобокса
        if self.show_all_video_codecs.get():
            ComboboxTooltip(self.video_codec_combobox, self.video_encoder_descriptions)

    def filter_audio_codec_options(self):
        """Фильтрует опции аудио кодеков в выпадающих списках"""
        if self.show_all_audio_codecs.get():
            # Показываем все доступные аудио кодеки
            audio_codecs_to_show = self.all_audio_encoders
        else:
            # Показываем только предустановленные аудио кодеки
            audio_codecs_to_show = CodecManager.filter_supported(CodecManager.AUDIO_CODECS, self.supported_encoders)
        
        # Формируем отображаемые названия с описаниями
        audio_display_names = []
        for codec in audio_codecs_to_show:
            if self.show_all_audio_codecs.get() and hasattr(self, 'audio_encoder_descriptions'):
                # Для всех кодеков показываем с описанием
                description = self.audio_encoder_descriptions.get(codec, codec)
                # Ограничиваем длину описания для читаемости
                if len(description) > 60:
                    description = description[:57] + "..."
                display_name = f"{codec} - {description}"
            else:
                # Для предустановленных используем красивые имена
                display_name = CodecManager.get_display_name(codec)
            audio_display_names.append(display_name)
        
        # Обновляем значения в комбобоксе
        self.audio_codec_combobox['values'] = audio_display_names
        
        # Проверяем, поддерживается ли текущий выбранный кодек
        current_audio_tech = self.audio_codec.get()
        if current_audio_tech not in audio_codecs_to_show and audio_codecs_to_show:
            self.audio_codec.set(audio_codecs_to_show[0])
            self.audio_codec_combobox.set(audio_display_names[0])
        else:
            # Обновляем отображаемое имя
            if self.show_all_audio_codecs.get() and hasattr(self, 'audio_encoder_descriptions'):
                description = self.audio_encoder_descriptions.get(current_audio_tech, current_audio_tech)
                if len(description) > 60:
                    description = description[:57] + "..."
                current_display = f"{current_audio_tech} - {description}"
            else:
                current_display = CodecManager.get_display_name(current_audio_tech)
            self.audio_codec_combobox.set(current_display)
        
        # Добавляем всплывающие подсказки для комбобокса
        if self.show_all_audio_codecs.get():
            ComboboxTooltip(self.audio_codec_combobox, self.audio_encoder_descriptions)

    def show_ffmpeg_settings(self):
        """Показывает окно настроек FFmpeg"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки FFmpeg")
        settings_window.geometry("500x200")
        settings_window.resizable(False, False)

        frame = ttk.Frame(settings_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Путь к FFmpeg
        ttk.Label(frame, text="Путь к FFmpeg:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        path_frame = ttk.Frame(frame)
        path_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        path_frame.columnconfigure(0, weight=1)

        path_var = tk.StringVar(value=self.ffmpeg_path)
        path_entry = ttk.Entry(path_frame, textvariable=path_var)
        path_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        def browse_ffmpeg():
            filename = filedialog.askopenfilename(
                title="Выберите FFmpeg",
                filetypes=[("Исполняемые файлы", "*.exe"), ("Все файлы", "*.*")]
            )
            if filename:
                path_var.set(filename)

        ttk.Button(path_frame, text="Обзор", command=browse_ffmpeg).grid(row=0, column=1)

        # Информация
        info_label = ttk.Label(frame,
                              text="Укажите путь к исполняемому файлу FFmpeg или оставьте 'ffmpeg'\nдля поиска в PATH системы.",
                              foreground=self.colors['secondary'])
        info_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 20))

        # Кнопки
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, sticky=tk.E)

        def save_settings():
            new_path = path_var.get()
            self.ffmpeg_path = new_path
            self.config["ffmpeg_path"] = new_path
            self.config_manager.save(self.config)
            messagebox.showinfo("Успех", "Настройки сохранены. Проверка FFmpeg...")
            settings_window.destroy()
            self.check_ffmpeg_and_codecs()

        ttk.Button(button_frame, text="Сохранить", command=save_settings,
                  style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Отмена", command=settings_window.destroy,
                  style='Secondary.TButton').pack(side=tk.LEFT)

    def show_ffmpeg_info(self):
        """Показывает окно с информацией о FFmpeg"""
        info_window = tk.Toplevel(self.root)
        info_window.title("Информация о FFmpeg")
        info_window.geometry("700x500")
        info_window.resizable(True, True)

        # Текстовое поле с информацией
        text_frame = ttk.Frame(info_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10),
                            bg=self.colors['light'], fg=self.colors['dark'])
        
        text_widget.insert(tk.END, f"Версия FFmpeg:\n{self.ffmpeg_version_info}\n\n")
        text_widget.insert(tk.END, f"Путь: {self.ffmpeg_path}\n\n")
        text_widget.insert(tk.END, f"Конфигурация сборки:\n{self.ffmpeg_build_config}\n\n")
        
        text_widget.insert(tk.END, "Поддерживаемые видео кодеки:\n")
        for encoder in self.supported_encoders:
            if encoder in CodecManager.VIDEO_CODECS:
                display_name = CodecManager.get_display_name(encoder)
                text_widget.insert(tk.END, f"  • {display_name}\n")
        
        text_widget.insert(tk.END, "\nПоддерживаемые аудио кодеки:\n")
        for encoder in self.supported_encoders:
            if encoder in CodecManager.AUDIO_CODECS:
                display_name = CodecManager.get_display_name(encoder)
                text_widget.insert(tk.END, f"  • {display_name}\n")
        
        if self.show_all_video_codecs.get() or self.show_all_audio_codecs.get():
            text_widget.insert(tk.END, f"\n\nВсего доступно видео кодеков: {len(self.all_video_encoders)}\n")
            text_widget.insert(tk.END, f"Всего доступно аудио кодеков: {len(self.all_audio_encoders)}\n")
        
        text_widget.config(state=tk.DISABLED)
        
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопка закрытия
        button_frame = ttk.Frame(info_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(button_frame, text="Закрыть", command=info_window.destroy,
                  style='Modern.TButton').pack()

    def log(self, message, level="info"):
        """Логирование сообщений"""
        if level == "error":
            tag = "ERROR: "
            color = self.colors['danger']
        elif level == "warning":
            tag = "WARNING: "
            color = self.colors['warning']
        elif level == "success":
            tag = "✓ "
            color = self.colors['success']
        else:
            tag = ""
            color = self.colors['dark']

        self.log_text.insert(tk.END, f"{tag}{message}\n")
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()

    def preview_command(self):
        """Предпросмотр команды FFmpeg"""
        try:
            cmd = self.build_ffmpeg_command()
            cmd_str = ' '.join(cmd)

            # Создаем новое окно для предпросмотра
            preview_window = tk.Toplevel(self.root)
            preview_window.title("Предпросмотр команды")
            preview_window.geometry("800x350")
            preview_window.resizable(True, True)

            # Текстовое поле с командой
            text_frame = ttk.Frame(preview_window, padding="10")
            text_frame.pack(fill=tk.BOTH, expand=True)

            text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 10),
                                bg=self.colors['light'], fg=self.colors['dark'])
            text_widget.insert(tk.END, cmd_str)
            text_widget.config(state=tk.DISABLED)

            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Кнопки
            button_frame = ttk.Frame(preview_window)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Копировать в буфер",
                      command=lambda: self.copy_to_clipboard(cmd_str),
                      style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Button(button_frame, text="Закрыть",
                      command=preview_window.destroy,
                      style='Secondary.TButton').pack(side=tk.LEFT)

        except ValueError as e:
            self.log(f"Ошибка: {e}", "error")
            messagebox.showerror("Ошибка", str(e))
        except Exception as e:
            self.log(f"Ошибка при создании предпросмотра: {e}", "error")

    def copy_to_clipboard(self, text):
        """Копирование текста в буфер обмена"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Успех", "Команда скопирована в буфер обмена")

    def normalize_bitrate(self, bitrate):
        """Нормализация битрейта - добавляет 'k' если не указана единица измерения"""
        bitrate = bitrate.strip()
        # Проверяем, есть ли уже единица измерения (k, K, m, M)
        if bitrate and bitrate[-1].lower() not in ['k', 'm']:
            # Если это просто число, добавляем 'k'
            if bitrate.isdigit():
                return bitrate + 'k'
        return bitrate

    def build_ffmpeg_command(self):
        """Построение команды FFmpeg с валидацией"""
        input_file = self.input_file.get()
        output_file = self.output_file.get()

        # Валидация
        FFmpegValidator.validate_file_path(input_file, must_exist=True)
        FFmpegValidator.validate_file_path(output_file, must_exist=False)
        
        # Нормализация битрейтов (добавляем 'k' если не указана единица измерения)
        video_bitrate = self.normalize_bitrate(self.video_bitrate.get())
        audio_bitrate = self.normalize_bitrate(self.audio_bitrate.get())
        
        FFmpegValidator.validate_bitrate(video_bitrate)
        FFmpegValidator.validate_bitrate(audio_bitrate)
        FFmpegValidator.validate_resolution(self.video_resolution.get())
        FFmpegValidator.validate_fps(self.video_fps.get())
        if self.use_crf.get():
            FFmpegValidator.validate_quality(self.video_quality.get())

        # Основная команда
        cmd = [self.ffmpeg_path]
        
        # Добавляем параметры обрезки если включено
        if self.enable_trim.get():
            try:
                FFmpegValidator.validate_timestamp(self.trim_start.get())
                FFmpegValidator.validate_timestamp(self.trim_end.get())
                
                cmd.extend(['-ss', self.trim_start.get()])
                cmd.extend(['-to', self.trim_end.get()])
                
                # Обновляем метку длительности
                self.update_trim_duration_label()
            except ValueError as e:
                raise ValueError(f"Ошибка в параметрах обрезки: {e}")
        
        cmd.extend([
            '-i', input_file,
            '-c:v', self.video_codec.get(),
            '-preset', self.video_preset.get(),
            '-threads', '0',  # Использовать все доступные ядра CPU
        ])

        # Добавляем либо битрейт, либо CRF
        if self.use_crf.get():
            cmd.extend(['-crf', self.video_quality.get()])
        else:
            cmd.extend(['-b:v', video_bitrate])

        cmd.extend([
            '-s', self.video_resolution.get(),
            '-r', self.video_fps.get(),
            '-c:a', self.audio_codec.get(),
            '-b:a', audio_bitrate,
            '-y',  # Перезаписывать файл без подтверждения
            output_file
        ])

        return cmd

    def start_conversion(self):
        """Запуск конвертации"""
        try:
            cmd = self.build_ffmpeg_command()

            # Отключаем кнопку конвертации
            self.convert_button.config(state='disabled', text="Конвертация...")
            self.stop_button.config(state='normal')

            # Сброс прогресса
            self.progress_var.set(0)
            self.progress_label.config(text="Начало конвертации...")
            self.time_label.config(text="")

            # Запуск в отдельном потоке
            self.conversion_thread = threading.Thread(target=self.run_conversion, args=(cmd,))
            self.conversion_thread.daemon = True
            self.conversion_thread.start()

        except ValueError as e:
            self.log(f"Ошибка валидации: {e}", "error")
            messagebox.showerror("Ошибка", str(e))
        except FileNotFoundError as e:
            self.log(f"Файл не найден: {e}", "error")
            messagebox.showerror("Ошибка", str(e))
        except Exception as e:
            self.log(f"Ошибка при запуске конвертации: {e}", "error")
            messagebox.showerror("Ошибка", f"Ошибка при запуске конвертации: {e}")

    def run_conversion(self, cmd):
        """Выполнение конвертации в отдельном потоке"""
        try:
            self.start_time = time.time()
            self.log(f"Команда: {' '.join(cmd)}")

            # Запуск процесса
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Чтение вывода построчно
            while True:
                output = self.current_process.stdout.readline()
                if output == '' and self.current_process.poll() is not None:
                    break
                if output:
                    self.log(output.strip())
                    self.update_progress(output.strip())

            # Проверка результата
            return_code = self.current_process.poll()
            
            if return_code == 0:
                elapsed_time = time.time() - self.start_time
                self.progress_var.set(100)
                self.log(f"Конвертация завершена успешно! Время: {self.format_time(elapsed_time)}", "success")
                self.progress_label.config(text="Конвертация завершена!")
                self.time_label.config(text=f"Время: {self.format_time(elapsed_time)}")
                messagebox.showinfo("Успех", "Конвертация завершена успешно!")
                self.update_file_info()  # Обновляем информацию о файлах
            else:
                self.log(f"Ошибка конвертации. Код возврата: {return_code}", "error")
                self.progress_label.config(text="Ошибка конвертации")
                messagebox.showerror("Ошибка", f"Конвертация завершена с ошибкой. Код: {return_code}")

        except Exception as e:
            self.log(f"Ошибка выполнения: {e}", "error")
            self.progress_label.config(text="Ошибка выполнения")
            messagebox.showerror("Ошибка", f"Ошибка выполнения: {e}")
        finally:
            # Включаем кнопку обратно
            self.convert_button.config(state='normal', text="Начать конвертацию")
            self.stop_button.config(state='disabled')
            self.current_process = None

    def update_progress(self, output):
        """Обновление прогресса на основе вывода FFmpeg"""
        if "frame=" in output and "time=" in output:
            try:
                # Извлекаем время
                time_part = output.split("time=")[1].split()[0]
                if time_part != "N/A":
                    # Рассчитываем прогресс
                    h, m, s = map(float, time_part.split(":"))
                    current_seconds = h * 3600 + m * 60 + s

                    # Получаем общую продолжительность (с учетом обрезки)
                    if self.enable_trim.get():
                        try:
                            start_seconds = self.timestamp_to_seconds(self.trim_start.get())
                            end_seconds = self.timestamp_to_seconds(self.trim_end.get())
                            duration = end_seconds - start_seconds
                        except:
                            duration = self.get_video_duration(self.input_file.get())
                    else:
                        duration = self.get_video_duration(self.input_file.get())
                    
                    if duration and duration > 0:
                        progress = (current_seconds / duration) * 100
                        self.progress_var.set(min(progress, 100))

                        # Расчет оставшегося времени
                        elapsed_time = time.time() - self.start_time
                        if progress > 0:
                            estimated_total = elapsed_time / (progress / 100)
                            remaining = estimated_total - elapsed_time
                            self.time_label.config(text=f"Осталось: {self.format_time(remaining)}")
                        
                        self.progress_label.config(text=f"Прогресс: {progress:.1f}%")
            except Exception:
                pass  # Игнорируем ошибки парсинга

    def format_time(self, seconds):
        """Форматирование времени в часы:минуты:секунды или минуты:секунды"""
        if seconds < 0:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def get_video_duration(self, filepath):
        """Получение продолжительности видео"""
        try:
            ffprobe_path = self.get_ffprobe_path()
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                filepath
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0

    def stop_conversion(self):
        """Остановка конвертации"""
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
                self.log("Конвертация остановлена пользователем", "warning")
                self.progress_label.config(text="Конвертация остановлена")
            except subprocess.TimeoutExpired:
                self.current_process.kill()
                self.log("Конвертация принудительно завершена", "error")
            except Exception as e:
                self.log(f"Ошибка при остановке: {e}", "error")
            finally:
                self.convert_button.config(state='normal', text="Начать конвертацию")
                self.stop_button.config(state='disabled')
                self.current_process = None

    def on_closing(self):
        """Обработчик закрытия окна"""
        # Сохраняем настройки
        self.config["video_codec"] = self.video_codec.get()
        self.config["video_preset"] = self.video_preset.get()
        self.config["video_bitrate"] = self.video_bitrate.get()
        self.config["video_resolution"] = self.video_resolution.get()
        self.config["resolution_mode"] = self.resolution_mode.get()
        self.config["custom_resolution"] = self.custom_resolution.get()
        self.config["video_quality"] = self.video_quality.get()
        self.config["video_fps"] = self.video_fps.get()
        self.config["audio_codec"] = self.audio_codec.get()
        self.config["audio_bitrate"] = self.audio_bitrate.get()
        self.config["use_crf"] = self.use_crf.get()
        self.config["show_all_video_codecs"] = self.show_all_video_codecs.get()
        self.config["show_all_audio_codecs"] = self.show_all_audio_codecs.get()
        self.config["enable_trim"] = self.enable_trim.get()
        self.config["trim_start"] = self.trim_start.get()
        self.config["trim_end"] = self.trim_end.get()
        
        self.config_manager.save(self.config)

        # Останавливаем процесс если запущен
        if self.current_process:
            result = messagebox.askyesno(
                "Конвертация в процессе",
                "Конвертация еще выполняется. Остановить и закрыть программу?"
            )
            if result:
                self.stop_conversion()
            else:
                return
        
        self.root.destroy()

def main():
    root = TkinterDnD.Tk()  # Используем TkinterDnD вместо обычного Tk
    app = FFmpegConverter(root)
    root.mainloop()

if __name__ == "__main__":
    main()
