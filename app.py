import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
from tkinterdnd2 import TkinterDnD, DND_FILES

import subprocess
import threading
import os
import sys
import re
import json


# ============================================================
# APP INFO
# ============================================================

APP_NAME = "MP3 → MP4 Converter"
APP_VERSION = "1.0"


# ============================================================
# COLORS
# ============================================================

BG = "#07111f"
PANEL = "#0b1728"
PANEL_DARK = "#081321"
BORDER = "#1d3551"

BLUE = "#1688ff"
BLUE_HOVER = "#0875e4"

PURPLE = "#8b42d9"
PURPLE_HOVER = "#7732c2"

GREEN = "#28d968"

TEXT = "#f3f6fb"
TEXT_MUTED = "#929eaf"

PROGRESS_BG = "#1b293a"

CANCEL = "#273346"
CANCEL_HOVER = "#34445c"


# ============================================================
# RESOURCE PATH
# Works both in Python and PyInstaller .exe
# ============================================================

def resource_path(filename):

    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(
            os.path.abspath(__file__)
        )

    return os.path.join(
        base_path,
        filename
    )


FFMPEG_PATH = resource_path(
    "ffmpeg.exe"
)


# ============================================================
# SETTINGS LOCATION
# ============================================================

APPDATA_FOLDER = os.path.join(
    os.getenv("APPDATA"),
    "AdiMP3ToMP4"
)

os.makedirs(
    APPDATA_FOLDER,
    exist_ok=True
)

SETTINGS_FILE = os.path.join(
    APPDATA_FOLDER,
    "settings.json"
)


# ============================================================
# CUSTOMTKINTER + DRAG/DROP ROOT
# ============================================================

class DnDCTk(
    ctk.CTk,
    TkinterDnD.DnDWrapper
):

    def __init__(
        self,
        *args,
        **kwargs
    ):

        ctk.CTk.__init__(
            self,
            *args,
            **kwargs
        )

        self.TkdndVersion = (
            TkinterDnD._require(self)
        )


# ============================================================
# GLOBAL VARIABLES
# ============================================================

image_file = ""
audio_file = ""
output_file = ""

audio_duration = 0

ffmpeg_process = None
cancel_requested = False

last_output_folder = ""


# ============================================================
# WINDOWS SUBPROCESS SETTINGS
# Prevent FFmpeg console window
# ============================================================

def hidden_process_settings():

    startupinfo = subprocess.STARTUPINFO()

    startupinfo.dwFlags |= (
        subprocess.STARTF_USESHOWWINDOW
    )

    startupinfo.wShowWindow = (
        subprocess.SW_HIDE
    )

    return {
        "startupinfo": startupinfo,
        "creationflags":
            subprocess.CREATE_NO_WINDOW
    }


# ============================================================
# SETTINGS
# ============================================================

def load_settings():

    defaults = {
        "resolution": "1080p (1920x1080)",
        "bitrate": "192k",
        "encoder": "NVIDIA GPU (NVENC)",
        "output_folder": ""
    }

    if not os.path.exists(
        SETTINGS_FILE
    ):
        return defaults

    try:

        with open(
            SETTINGS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            loaded = json.load(file)

        defaults.update(
            loaded
        )

    except Exception:
        pass

    return defaults


def save_settings():

    data = {
        "resolution":
            resolution_menu.get(),

        "bitrate":
            bitrate_menu.get(),

        "encoder":
            encoder_menu.get(),

        "output_folder":
            last_output_folder
    }

    try:

        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4
            )

    except Exception:
        pass


saved_settings = load_settings()

last_output_folder = (
    saved_settings.get(
        "output_folder",
        ""
    )
)


# ============================================================
# UTILITY
# ============================================================

def shorten_filename(
    filename,
    max_length=40
):

    if len(filename) <= max_length:
        return filename

    name, ext = os.path.splitext(
        filename
    )

    available = (
        max_length
        - len(ext)
        - 3
    )

    return (
        name[:available]
        + "..."
        + ext
    )


def format_time(seconds):

    seconds = int(seconds)

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    seconds = seconds % 60

    if hours > 0:

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


# ============================================================
# IMAGE
# ============================================================

def choose_image():

    file = filedialog.askopenfilename(

        title="Choose Image",

        filetypes=[
            (
                "Images",
                "*.png *.jpg *.jpeg *.webp *.bmp"
            ),
            (
                "All Files",
                "*.*"
            )
        ]
    )

    if file:
        set_image(file)


def set_image(file):

    global image_file

    image_file = file

    filename = os.path.basename(
        file
    )

    try:

        original = Image.open(file)

        width, height = (
            original.size
        )

        image_type = (
            os.path.splitext(file)[1]
            .replace(".", "")
            .upper()
        )

        preview_image = (
            original.copy()
        )

        preview_image.thumbnail(
            (330, 165)
        )

        preview = ctk.CTkImage(

            light_image=preview_image,

            dark_image=preview_image,

            size=preview_image.size
        )

        image_preview.configure(
            image=preview,
            text=""
        )

        image_preview.image = (
            preview
        )

        image_filename.configure(
            text=shorten_filename(
                filename,
                34
            )
        )

        image_type_label.configure(
            text=f"{image_type} Image"
        )

        image_dimensions.configure(
            text=f"{width} × {height}"
        )

        image_check.configure(
            text="✓",
            text_color=GREEN
        )

        status_label.configure(
            text="Image loaded"
        )

    except Exception as error:

        messagebox.showerror(
            "Image Error",
            str(error)
        )


# ============================================================
# AUDIO
# ============================================================

def choose_audio():

    file = filedialog.askopenfilename(

        title="Choose MP3",

        filetypes=[
            (
                "MP3 Audio",
                "*.mp3"
            ),
            (
                "All Files",
                "*.*"
            )
        ]
    )

    if file:
        set_audio(file)


def get_audio_duration(file):

    try:

        command = [
            FFMPEG_PATH,
            "-hide_banner",
            "-i",
            file
        ]

        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,

            text=True,

            encoding="utf-8",
            errors="replace",

            **hidden_process_settings()
        )

        match = re.search(

            r"Duration:\s*"
            r"(\d+):(\d+):([\d.]+)",

            result.stderr
        )

        if not match:
            return 0

        hours = int(
            match.group(1)
        )

        minutes = int(
            match.group(2)
        )

        seconds = float(
            match.group(3)
        )

        return (
            hours * 3600
            + minutes * 60
            + seconds
        )

    except Exception:
        return 0


def set_audio(file):

    global audio_file
    global audio_duration

    audio_file = file

    filename = os.path.basename(
        file
    )

    audio_filename.configure(
        text=shorten_filename(
            filename,
            40
        )
    )

    audio_type_label.configure(
        text="MP3 File"
    )

    audio_duration = (
        get_audio_duration(file)
    )

    if audio_duration > 0:

        audio_duration_label.configure(
            text=format_time(
                audio_duration
            )
        )

    else:

        audio_duration_label.configure(
            text="Duration unknown"
        )

    audio_check.configure(
        text="✓",
        text_color=GREEN
    )

    status_label.configure(
        text="Audio loaded"
    )


# ============================================================
# DRAG & DROP
# ============================================================

def drop_files(event):

    files = root.tk.splitlist(
        event.data
    )

    accepted = False

    for file in files:

        if not os.path.isfile(file):
            continue

        extension = (
            os.path.splitext(file)[1]
            .lower()
        )

        if extension in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp"
        }:

            set_image(file)
            accepted = True

        elif extension == ".mp3":

            set_audio(file)
            accepted = True

    if accepted:

        status_label.configure(
            text="Files loaded successfully"
        )

    else:

        status_label.configure(
            text="Unsupported file type"
        )


# ============================================================
# RESOLUTION
# ============================================================

def get_resolution():

    selected = (
        resolution_menu.get()
    )

    resolutions = {

        "720p (1280x720)":
            (1280, 720),

        "1080p (1920x1080)":
            (1920, 1080),

        "1440p (2560x1440)":
            (2560, 1440),

        "4K (3840x2160)":
            (3840, 2160)
    }

    return resolutions.get(
        selected,
        (1920, 1080)
    )


# ============================================================
# CONVERT
# ============================================================

def convert_video():

    global output_file
    global cancel_requested
    global last_output_folder

    if not image_file:

        messagebox.showerror(
            "Missing Image",
            "Please choose an image."
        )

        return

    if not audio_file:

        messagebox.showerror(
            "Missing MP3",
            "Please choose an MP3."
        )

        return

    if not os.path.exists(
        FFMPEG_PATH
    ):

        messagebox.showerror(

            "FFmpeg Missing",

            "ffmpeg.exe could not "
            "be found."
        )

        return

    suggested_name = (
        os.path.splitext(
            os.path.basename(
                audio_file
            )
        )[0]
        + ".mp4"
    )

    if (
        last_output_folder
        and
        os.path.isdir(
            last_output_folder
        )
    ):

        starting_folder = (
            last_output_folder
        )

    else:

        starting_folder = (
            os.path.dirname(
                audio_file
            )
        )

    output_file = (
        filedialog.asksaveasfilename(

            title="Save MP4",

            initialdir=starting_folder,

            initialfile=suggested_name,

            defaultextension=".mp4",

            filetypes=[
                (
                    "MP4 Video",
                    "*.mp4"
                )
            ]
        )
    )

    if not output_file:
        return

    if os.path.exists(
        output_file
    ):

        replace = (
            messagebox.askyesno(

                "Replace File?",

                "That file already "
                "exists.\n\n"
                "Replace it?"
            )
        )

        if not replace:
            return

    last_output_folder = (
        os.path.dirname(
            output_file
        )
    )

    save_settings()

    width, height = (
        get_resolution()
    )

    bitrate = (
        bitrate_menu.get()
    )

    encoder_choice = (
        encoder_menu.get()
    )

    if (
        encoder_choice
        == "NVIDIA GPU (NVENC)"
    ):

        video_encoder = (
            "h264_nvenc"
        )

    else:

        video_encoder = (
            "libx264"
        )

    cancel_requested = False

    set_converting_state()

    thread = threading.Thread(

        target=run_ffmpeg,

        args=(
            width,
            height,
            bitrate,
            video_encoder
        ),

        daemon=True
    )

    thread.start()


# ============================================================
# CONVERSION UI STATE
# ============================================================

def set_converting_state():

    convert_button.configure(

        text="↻  CONVERTING...",

        state="disabled"
    )

    cancel_button.configure(
        state="normal"
    )

    resolution_menu.configure(
        state="disabled"
    )

    bitrate_menu.configure(
        state="disabled"
    )

    encoder_menu.configure(
        state="disabled"
    )

    choose_image_button.configure(
        state="disabled"
    )

    choose_audio_button.configure(
        state="disabled"
    )

    progress_bar.set(0)

    percent_label.configure(
        text="0%"
    )

    current_time_label.configure(
        text=(
            "00:00 / "
            + format_time(
                audio_duration
            )
        )
    )

    status_label.configure(
        text="Starting conversion..."
    )


def reset_controls():

    convert_button.configure(

        text="↻  CONVERT TO MP4",

        state="normal"
    )

    cancel_button.configure(
        state="disabled"
    )

    resolution_menu.configure(
        state="normal"
    )

    bitrate_menu.configure(
        state="normal"
    )

    encoder_menu.configure(
        state="normal"
    )

    choose_image_button.configure(
        state="normal"
    )

    choose_audio_button.configure(
        state="normal"
    )


# ============================================================
# FFMPEG CONVERSION
# ============================================================

def run_ffmpeg(
    width,
    height,
    bitrate,
    video_encoder
):

    global ffmpeg_process
    global cancel_requested
    global audio_duration

    try:

        if audio_duration <= 0:

            audio_duration = (
                get_audio_duration(
                    audio_file
                )
            )

        filter_string = (

            f"scale={width}:{height}:"
            "force_original_aspect_ratio="
            "decrease,"

            f"pad={width}:{height}:"
            "(ow-iw)/2:(oh-ih)/2"
        )

        command = [

            FFMPEG_PATH,

            "-y",

            "-loop",
            "1",

            "-i",
            image_file,

            "-i",
            audio_file,

            "-vf",
            filter_string,

            "-c:v",
            video_encoder,

            "-c:a",
            "aac",

            "-b:a",
            bitrate,

            "-pix_fmt",
            "yuv420p",

            "-shortest",

            "-progress",
            "pipe:1",

            "-nostats"
        ]

        # CPU settings
        if (
            video_encoder
            == "libx264"
        ):

            command += [
                "-preset",
                "medium",

                "-crf",
                "18"
            ]

        # NVIDIA settings
        else:

            command += [
                "-preset",
                "p5",

                "-cq",
                "19"
            ]

        command.append(
            output_file
        )

        ffmpeg_process = (
            subprocess.Popen(

                command,

                stdout=subprocess.PIPE,

                stderr=subprocess.DEVNULL,

                text=True,

                encoding="utf-8",

                errors="replace",

                **hidden_process_settings()
            )
        )

        while True:

            if cancel_requested:

                try:
                    ffmpeg_process.terminate()
                except Exception:
                    pass

                break

            line = (
                ffmpeg_process
                .stdout
                .readline()
            )

            if not line:
                break

            line = line.strip()

            if line.startswith(
                "out_time_us="
            ):

                try:

                    microseconds = int(
                        line.split(
                            "=",
                            1
                        )[1]
                    )

                    current = (
                        microseconds
                        / 1_000_000
                    )

                    if audio_duration > 0:

                        progress = (
                            current
                            / audio_duration
                        )

                        progress = max(
                            0,
                            min(
                                1,
                                progress
                            )
                        )

                        root.after(

                            0,

                            update_progress,

                            progress,

                            current
                        )

                except Exception:
                    pass

        ffmpeg_process.wait()

        return_code = (
            ffmpeg_process.returncode
        )

        ffmpeg_process = None

        if cancel_requested:

            root.after(
                0,
                conversion_cancelled
            )

        elif return_code == 0:

            root.after(
                0,
                conversion_success
            )

        else:

            root.after(
                0,
                conversion_failed
            )

    except Exception as error:

        ffmpeg_process = None

        root.after(

            0,

            conversion_error,

            str(error)
        )


# ============================================================
# PROGRESS
# ============================================================

def update_progress(
    progress,
    current
):

    progress_bar.set(
        progress
    )

    percentage = int(
        progress * 100
    )

    percent_label.configure(
        text=f"{percentage}%"
    )

    current_time_label.configure(

        text=(

            f"{format_time(current)}"
            " / "
            f"{format_time(audio_duration)}"
        )
    )

    status_label.configure(
        text=(
            f"Converting... "
            f"{percentage}%"
        )
    )


# ============================================================
# CANCEL
# ============================================================

def cancel_conversion():

    global cancel_requested

    cancel_requested = True

    cancel_button.configure(
        state="disabled"
    )

    status_label.configure(
        text="Cancelling..."
    )


# ============================================================
# RESULTS
# ============================================================

def conversion_success():

    progress_bar.set(1)

    percent_label.configure(
        text="100%"
    )

    current_time_label.configure(

        text=(

            f"{format_time(audio_duration)}"
            " / "
            f"{format_time(audio_duration)}"
        )
    )

    status_label.configure(
        text="Conversion complete ✓"
    )

    reset_controls()

    open_folder = (
        messagebox.askyesno(

            "Conversion Complete",

            "Your MP4 was created "
            "successfully.\n\n"
            "Open the output folder?"
        )
    )

    if open_folder:

        os.startfile(
            os.path.dirname(
                output_file
            )
        )


def conversion_cancelled():

    reset_controls()

    progress_bar.set(0)

    percent_label.configure(
        text="0%"
    )

    status_label.configure(
        text="Conversion cancelled"
    )

    current_time_label.configure(
        text="00:00 / 00:00"
    )

    if (
        output_file
        and
        os.path.exists(
            output_file
        )
    ):

        try:
            os.remove(
                output_file
            )
        except Exception:
            pass


def conversion_failed():

    reset_controls()

    status_label.configure(
        text="Conversion failed"
    )

    messagebox.showerror(

        "Conversion Failed",

        "FFmpeg was unable "
        "to create the video."
    )


def conversion_error(error):

    reset_controls()

    status_label.configure(
        text="Error"
    )

    messagebox.showerror(
        "Error",
        error
    )


# ============================================================
# CLOSE
# ============================================================

def on_close():

    save_settings()

    if ffmpeg_process:

        try:
            ffmpeg_process.terminate()
        except Exception:
            pass

    root.destroy()


# ============================================================
# APP SETUP
# ============================================================

ctk.set_appearance_mode(
    "dark"
)

root = DnDCTk()

root.title(
    APP_NAME
)

root.geometry(
    "1180x790"
)

root.minsize(
    1050,
    720
)

root.configure(
    fg_color=BG
)

root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# MAIN CONTAINER
# ============================================================

main = ctk.CTkFrame(

    root,

    fg_color="transparent"
)

main.pack(

    fill="both",

    expand=True,

    padx=45,

    pady=(24, 0)
)


# ============================================================
# HEADER
# ============================================================

title = ctk.CTkLabel(

    main,

    text="MP3  →  MP4",

    text_color=TEXT,

    font=ctk.CTkFont(
        size=40,
        weight="bold"
    )
)

title.pack(
    pady=(0, 3)
)


subtitle = ctk.CTkLabel(

    main,

    text=(
        "Turn your music and artwork "
        "into a video"
    ),

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=16
    )
)

subtitle.pack(
    pady=(0, 17)
)


# ============================================================
# DROP ZONE
# ============================================================

drop_frame = ctk.CTkFrame(

    main,

    height=105,

    fg_color=PANEL_DARK,

    border_width=2,

    border_color=BLUE,

    corner_radius=18
)

drop_frame.pack(
    fill="x"
)

drop_frame.pack_propagate(
    False
)


drop_icon = ctk.CTkLabel(

    drop_frame,

    text="☁ ↓",

    text_color=PURPLE,

    font=ctk.CTkFont(
        size=27,
        weight="bold"
    )
)

drop_icon.pack(
    pady=(12, 0)
)


drop_title = ctk.CTkLabel(

    drop_frame,

    text="DROP IMAGE + MP3 HERE",

    text_color=TEXT,

    font=ctk.CTkFont(
        size=18,
        weight="bold"
    )
)

drop_title.pack()


drop_subtitle = ctk.CTkLabel(

    drop_frame,

    text=(
        "or click the buttons below "
        "to choose files"
    ),

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=13
    )
)

drop_subtitle.pack()


root.drop_target_register(
    DND_FILES
)

root.dnd_bind(
    "<<Drop>>",
    drop_files
)


# ============================================================
# FILE CARDS
# ============================================================

file_area = ctk.CTkFrame(

    main,

    fg_color="transparent"
)

file_area.pack(

    fill="x",

    pady=(15, 12)
)

file_area.grid_columnconfigure(
    0,
    weight=1
)

file_area.grid_columnconfigure(
    1,
    weight=1
)


# ============================================================
# IMAGE CARD
# ============================================================

image_card = ctk.CTkFrame(

    file_area,

    fg_color=PANEL,

    border_width=1,

    border_color=BORDER,

    corner_radius=16
)

image_card.grid(

    row=0,
    column=0,

    sticky="nsew",

    padx=(0, 8)
)


image_header = ctk.CTkLabel(

    image_card,

    text="▣  IMAGE",

    text_color=TEXT,

    font=ctk.CTkFont(
        size=16,
        weight="bold"
    )
)

image_header.pack(

    anchor="w",

    padx=18,

    pady=(14, 8)
)


image_content = ctk.CTkFrame(

    image_card,

    fg_color=PANEL_DARK,

    corner_radius=12
)

image_content.pack(

    fill="x",

    padx=15
)


image_preview = ctk.CTkLabel(

    image_content,

    text="IMAGE\nPREVIEW",

    width=330,

    height=165,

    fg_color="#101d2c",

    text_color=TEXT_MUTED,

    corner_radius=10
)

image_preview.pack(

    side="left",

    padx=10,

    pady=10
)


image_info = ctk.CTkFrame(

    image_content,

    fg_color="transparent"
)

image_info.pack(

    side="left",

    fill="both",

    expand=True,

    padx=(5, 10),

    pady=14
)


image_filename = ctk.CTkLabel(

    image_info,

    text="No image selected",

    text_color=TEXT,

    justify="left",

    anchor="w",

    wraplength=175,

    font=ctk.CTkFont(
        size=14,
        weight="bold"
    )
)

image_filename.pack(
    anchor="w"
)


image_type_label = ctk.CTkLabel(

    image_info,

    text="PNG / JPG / WEBP",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

image_type_label.pack(
    anchor="w",
    pady=(5, 0)
)


image_dimensions = ctk.CTkLabel(

    image_info,

    text="—",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

image_dimensions.pack(
    anchor="w"
)


image_check = ctk.CTkLabel(

    image_info,

    text="",

    font=ctk.CTkFont(
        size=20,
        weight="bold"
    )
)

image_check.pack(
    anchor="e",
    pady=(8, 0)
)


choose_image_button = ctk.CTkButton(

    image_card,

    text="▣  Choose Image",

    height=42,

    fg_color=BLUE,

    hover_color=BLUE_HOVER,

    corner_radius=9,

    font=ctk.CTkFont(
        size=15
    ),

    command=choose_image
)

choose_image_button.pack(

    fill="x",

    padx=15,

    pady=(10, 15)
)


# ============================================================
# AUDIO CARD
# ============================================================

audio_card = ctk.CTkFrame(

    file_area,

    fg_color=PANEL,

    border_width=1,

    border_color=BORDER,

    corner_radius=16
)

audio_card.grid(

    row=0,
    column=1,

    sticky="nsew",

    padx=(8, 0)
)


audio_header = ctk.CTkLabel(

    audio_card,

    text="♫  AUDIO",

    text_color=TEXT,

    font=ctk.CTkFont(
        size=16,
        weight="bold"
    )
)

audio_header.pack(

    anchor="w",

    padx=18,

    pady=(14, 8)
)


audio_content = ctk.CTkFrame(

    audio_card,

    fg_color=PANEL_DARK,

    corner_radius=12
)

audio_content.pack(

    fill="both",

    expand=True,

    padx=15
)


audio_icon = ctk.CTkLabel(

    audio_content,

    text="♫",

    width=92,

    height=92,

    fg_color="#29154a",

    text_color="#b66cff",

    corner_radius=12,

    font=ctk.CTkFont(
        size=45,
        weight="bold"
    )
)

audio_icon.pack(

    side="left",

    padx=12,

    pady=22
)


audio_info = ctk.CTkFrame(

    audio_content,

    fg_color="transparent"
)

audio_info.pack(

    side="left",

    fill="both",

    expand=True,

    padx=8,

    pady=23
)


audio_filename = ctk.CTkLabel(

    audio_info,

    text="No MP3 selected",

    text_color=TEXT,

    wraplength=290,

    justify="left",

    anchor="w",

    font=ctk.CTkFont(
        size=14,
        weight="bold"
    )
)

audio_filename.pack(
    anchor="w"
)


audio_type_label = ctk.CTkLabel(

    audio_info,

    text="MP3 File",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

audio_type_label.pack(

    anchor="w",

    pady=(6, 0)
)


audio_duration_label = ctk.CTkLabel(

    audio_info,

    text="—",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

audio_duration_label.pack(
    anchor="w"
)


audio_check = ctk.CTkLabel(

    audio_content,

    text="",

    font=ctk.CTkFont(
        size=20,
        weight="bold"
    )
)

audio_check.pack(

    side="right",

    padx=15
)


choose_audio_button = ctk.CTkButton(

    audio_card,

    text="♫  Choose MP3",

    height=42,

    fg_color=PURPLE,

    hover_color=PURPLE_HOVER,

    corner_radius=9,

    font=ctk.CTkFont(
        size=15
    ),

    command=choose_audio
)

choose_audio_button.pack(

    fill="x",

    padx=15,

    pady=(10, 15)
)


# ============================================================
# SETTINGS PANEL
# ============================================================

settings_card = ctk.CTkFrame(

    main,

    fg_color=PANEL,

    border_width=1,

    border_color=BORDER,

    corner_radius=16
)

settings_card.pack(
    fill="x"
)


settings_header = ctk.CTkLabel(

    settings_card,

    text="⚙  SETTINGS",

    text_color=TEXT,

    font=ctk.CTkFont(
        size=16,
        weight="bold"
    )
)

settings_header.pack(

    anchor="w",

    padx=18,

    pady=(13, 5)
)


settings_row = ctk.CTkFrame(

    settings_card,

    fg_color="transparent"
)

settings_row.pack(

    fill="x",

    padx=18,

    pady=(0, 15)
)

for column in range(3):

    settings_row.grid_columnconfigure(
        column,
        weight=1
    )


# Resolution

resolution_box = ctk.CTkFrame(

    settings_row,

    fg_color="transparent"
)

resolution_box.grid(

    row=0,
    column=0,

    sticky="ew",

    padx=(0, 10)
)


resolution_label = ctk.CTkLabel(

    resolution_box,

    text="Resolution",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

resolution_label.pack(
    anchor="w",
    pady=(0, 4)
)


resolution_menu = ctk.CTkOptionMenu(

    resolution_box,

    values=[
        "720p (1280x720)",
        "1080p (1920x1080)",
        "1440p (2560x1440)",
        "4K (3840x2160)"
    ],

    height=38,

    fg_color=PANEL_DARK,

    button_color="#16283e",

    button_hover_color="#203653",

    text_color=TEXT,

    dropdown_fg_color=PANEL,

    dropdown_hover_color="#1a2c44"
)

resolution_menu.pack(
    fill="x"
)

resolution_menu.set(

    saved_settings.get(
        "resolution",
        "1080p (1920x1080)"
    )
)


# Bitrate

bitrate_box = ctk.CTkFrame(

    settings_row,

    fg_color="transparent"
)

bitrate_box.grid(

    row=0,
    column=1,

    sticky="ew",

    padx=10
)


bitrate_label = ctk.CTkLabel(

    bitrate_box,

    text="Audio Bitrate",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

bitrate_label.pack(
    anchor="w",
    pady=(0, 4)
)


bitrate_menu = ctk.CTkOptionMenu(

    bitrate_box,

    values=[
        "128k",
        "192k",
        "256k",
        "320k"
    ],

    height=38,

    fg_color=PANEL_DARK,

    button_color="#16283e",

    button_hover_color="#203653",

    text_color=TEXT,

    dropdown_fg_color=PANEL,

    dropdown_hover_color="#1a2c44"
)

bitrate_menu.pack(
    fill="x"
)

bitrate_menu.set(

    saved_settings.get(
        "bitrate",
        "192k"
    )
)


# Encoder

encoder_box = ctk.CTkFrame(

    settings_row,

    fg_color="transparent"
)

encoder_box.grid(

    row=0,
    column=2,

    sticky="ew",

    padx=(10, 0)
)


encoder_label = ctk.CTkLabel(

    encoder_box,

    text="Encoder",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

encoder_label.pack(
    anchor="w",
    pady=(0, 4)
)


encoder_menu = ctk.CTkOptionMenu(

    encoder_box,

    values=[
        "CPU (H.264)",
        "NVIDIA GPU (NVENC)"
    ],

    height=38,

    fg_color=PANEL_DARK,

    button_color="#16283e",

    button_hover_color="#203653",

    text_color=TEXT,

    dropdown_fg_color=PANEL,

    dropdown_hover_color="#1a2c44"
)

encoder_menu.pack(
    fill="x"
)

encoder_menu.set(

    saved_settings.get(
        "encoder",
        "NVIDIA GPU (NVENC)"
    )
)


# ============================================================
# PROGRESS AREA
# ============================================================

progress_area = ctk.CTkFrame(

    main,

    fg_color="transparent"
)

progress_area.pack(

    fill="x",

    pady=(18, 0)
)


progress_row = ctk.CTkFrame(

    progress_area,

    fg_color="transparent"
)

progress_row.pack(
    fill="x"
)


progress_bar = ctk.CTkProgressBar(

    progress_row,

    height=12,

    fg_color=PROGRESS_BG,

    progress_color=BLUE
)

progress_bar.pack(

    side="left",

    fill="x",

    expand=True,

    padx=(0, 15)
)

progress_bar.set(0)


percent_label = ctk.CTkLabel(

    progress_row,

    text="0%",

    width=55,

    text_color=BLUE,

    font=ctk.CTkFont(
        size=18,
        weight="bold"
    )
)

percent_label.pack(
    side="right"
)


current_time_label = ctk.CTkLabel(

    progress_area,

    text="00:00 / 00:00",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=13
    )
)

current_time_label.pack(
    pady=(7, 0)
)


status_label = ctk.CTkLabel(

    progress_area,

    text="Ready",

    text_color=BLUE,

    font=ctk.CTkFont(
        size=14
    )
)

status_label.pack(
    pady=(3, 8)
)


# ============================================================
# CONVERSION BUTTONS
# ============================================================

button_row = ctk.CTkFrame(

    main,

    fg_color="transparent"
)

button_row.pack(
    pady=(0, 12)
)


convert_button = ctk.CTkButton(

    button_row,

    text="↻  CONVERT TO MP4",

    width=290,

    height=50,

    fg_color=BLUE,

    hover_color=BLUE_HOVER,

    corner_radius=11,

    font=ctk.CTkFont(
        size=16,
        weight="bold"
    ),

    command=convert_video
)

convert_button.pack(

    side="left",

    padx=6
)


cancel_button = ctk.CTkButton(

    button_row,

    text="✕  CANCEL",

    width=170,

    height=50,

    fg_color=CANCEL,

    hover_color=CANCEL_HOVER,

    text_color=TEXT_MUTED,

    corner_radius=11,

    state="disabled",

    font=ctk.CTkFont(
        size=14
    ),

    command=cancel_conversion
)

cancel_button.pack(

    side="left",

    padx=6
)


# ============================================================
# FOOTER
# ============================================================

footer = ctk.CTkFrame(

    root,

    height=42,

    fg_color="#08111d",

    corner_radius=0
)

footer.pack(

    fill="x",

    side="bottom"
)

footer.pack_propagate(
    False
)


footer_left = ctk.CTkLabel(

    footer,

    text=(
        "♢  Local Processing"
        "    •    H.264"
        "    •    AAC"
        "    •    No Upload"
    ),

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

footer_left.pack(

    side="left",

    padx=25
)


footer_right = ctk.CTkLabel(

    footer,

    text="Made by Adi  ♥",

    text_color=TEXT_MUTED,

    font=ctk.CTkFont(
        size=12
    )
)

footer_right.pack(

    side="right",

    padx=25
)


# ============================================================
# START APP
# ============================================================

root.mainloop()