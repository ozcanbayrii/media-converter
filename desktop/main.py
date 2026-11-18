import os
import sys
import re
import json
import time
import uuid
import shutil
import ctypes
import threading
import subprocess
from pathlib import Path

# Prevent crashes when built with PyInstaller --windowed (stdout/stderr is None)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import webview
import yt_dlp

APP_NAME = "Media Converter"
APP_VERSION = "1.0.0"


def resource_path(rel_path: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base / rel_path


def get_config_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    cfg_dir = Path(appdata) / "MediaConverter"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.json"


def detect_windows_theme() -> str:
    if sys.platform != "win32":
        return "dark"
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if val == 1 else "dark"
    except Exception:
        return "dark"


def detect_windows_lang() -> str:
    if sys.platform == "win32":
        try:
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (lcid & 0x3FF) == 0x1F:
                return "tr"
            return "en"
        except Exception:
            pass
    import locale
    loc = (locale.getlocale()[0] or "").lower()
    return "tr" if loc.startswith("tr") else "en"


def find_ffmpeg() -> str | None:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        local_ff = exe_dir / "ffmpeg.exe"
        if local_ff.exists():
            return str(local_ff)
    return shutil.which("ffmpeg")


def read_windows_clipboard() -> str:
    if sys.platform != "win32":
        return ""
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

    text = ""
    if user32.OpenClipboard(None):
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    try:
                        text = ctypes.wstring_at(ptr)
                    finally:
                        kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    return text.strip()


def apply_win32_window_chrome_async(title: str, theme: str, ico_path: Path):
    """Apply Windows DWM titlebar color and icon on a non-blocking helper thread."""
    if sys.platform != "win32":
        return

    def _apply():
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, title)
            if not hwnd:
                return

            dwmapi = ctypes.windll.dwmapi
            is_dark = 1 if theme == "dark" else 0

            val_dark = ctypes.c_int(is_dark)
            dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val_dark), ctypes.sizeof(val_dark))

            # Windows 11 caption & text color (0x00BBGGRR) matching --bg
            caption_color = ctypes.c_int(0x00131212 if is_dark else 0x00EEF2F3)
            text_color = ctypes.c_int(0x00E8ECEC if is_dark else 0x001B1919)
            dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color))
            dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))

            # Non-blocking PostMessageW so we can never deadlock the UI thread
            if ico_path.exists():
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x0010
                WM_SETICON = 0x0080
                user32 = ctypes.windll.user32
                user32.LoadImageW.restype = ctypes.c_void_p
                hicon_small = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                hicon_big = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
                if hicon_small:
                    user32.PostMessageW(hwnd, WM_SETICON, 0, hicon_small)
                if hicon_big:
                    user32.PostMessageW(hwnd, WM_SETICON, 1, hicon_big)
        except Exception:
            pass

    threading.Thread(target=_apply, daemon=True).start()


class SilentLogger:
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class DownloadCancelled(Exception):
    pass


class DesktopAPI:
    """
    NOTE: All internal state attributes MUST be prefixed with '_' so pywebview
    does NOT recursively introspect them (especially _window, which holds .NET Form).
    """

    def __init__(self):
        self._window = None
        self._config_path = get_config_path()
        self._config = self._load_config()
        self._jobs = {}
        self._cancel_flags = {}
        self._lock = threading.Lock()
        self._ico_path = resource_path("assets/app.ico")

    def _load_config(self) -> dict:
        defaults = {
            "theme": detect_windows_theme(),
            "lang": detect_windows_lang(),
            "save_dir": str(Path.home() / "Downloads"),
        }
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                defaults.update({k: v for k, v in saved.items() if k in defaults and v})
            except Exception:
                pass
        if not Path(defaults["save_dir"]).exists():
            defaults["save_dir"] = str(Path.home() / "Downloads")
        return defaults

    def _save_config(self):
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_init_state(self):
        return {
            "theme": self._config["theme"],
            "lang": self._config["lang"],
            "save_dir": self._config["save_dir"],
            "ffmpeg_ok": find_ffmpeg() is not None,
            "version": APP_VERSION,
        }

    def set_theme(self, theme: str):
        if theme in ("dark", "light"):
            self._config["theme"] = theme
            self._save_config()
            apply_win32_window_chrome_async(APP_NAME, theme, self._ico_path)
        return {"ok": True}

    def set_lang(self, lang: str):
        if lang in ("tr", "en"):
            self._config["lang"] = lang
            self._save_config()
        return {"ok": True}

    def choose_folder(self):
        if not self._window:
            return {"save_dir": self._config["save_dir"]}
        try:
            result = self._window.create_file_dialog(
                webview.FileDialog.FOLDER,
                directory=self._config["save_dir"],
            )
            if result and len(result) > 0:
                chosen = result[0]
                if os.path.isdir(chosen):
                    self._config["save_dir"] = chosen
                    self._save_config()
        except Exception:
            pass
        return {"save_dir": self._config["save_dir"]}

    def get_clipboard(self):
        return {"text": read_windows_clipboard()}

    def start_download(self, url: str, fmt: str, quality: str):
        url = (url or "").strip()
        fmt = (fmt or "mp4").lower()
        quality = (quality or "best").strip().lower()
        lang = self._config.get("lang", "tr")

        if not url:
            msg = "Please paste a video or audio link." if lang == "en" else "Lütfen bir video veya ses bağlantısı girin."
            return {"success": False, "error": msg}

        if not (url.startswith("http://") or url.startswith("https://")):
            msg = "Invalid URL. Link must start with http:// or https://." if lang == "en" else "Geçersiz bağlantı. Link http:// veya https:// ile başlamalıdır."
            return {"success": False, "error": msg}

        if fmt not in ("mp4", "mp3"):
            fmt = "mp4"

        save_dir = self._config["save_dir"]
        os.makedirs(save_dir, exist_ok=True)

        job_id = str(uuid.uuid4())
        cancel_ev = threading.Event()

        with self._lock:
            self._cancel_flags[job_id] = cancel_ev
            self._jobs[job_id] = {
                "status": "pending",
                "progress": 0,
                "speed": "",
                "eta": "",
                "title": "",
                "file_path": "",
                "filename": "",
                "file_size": "",
                "format": fmt,
                "quality": quality,
                "error": "",
            }

        thread = threading.Thread(
            target=self._download_worker,
            args=(job_id, url, fmt, quality, save_dir, lang, cancel_ev),
            daemon=True,
        )
        thread.start()

        return {"success": True, "job_id": job_id}

    def cancel_download(self, job_id: str):
        with self._lock:
            ev = self._cancel_flags.get(job_id)
            if ev:
                ev.set()
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "cancelled"
        return {"ok": True}

    def get_status(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {"status": "error", "error": "Job not found."}
            return dict(job)

    def open_folder(self, file_path: str = ""):
        try:
            if file_path and os.path.exists(file_path):
                subprocess.Popen(["explorer", "/select,", os.path.abspath(file_path)])
            else:
                os.startfile(self._config["save_dir"])
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_file(self, file_path: str = ""):
        try:
            if file_path and os.path.exists(file_path):
                os.startfile(file_path)
                return {"ok": True}
            return {"ok": False}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _download_worker(self, job_id, url, fmt, quality, save_dir, lang, cancel_ev):
        def progress_hook(d):
            if cancel_ev.is_set():
                raise DownloadCancelled()

            status = d.get("status")
            with self._lock:
                if job_id not in self._jobs:
                    return
                if status == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes") or 0
                    percent = 0
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                    elif d.get("_percent_str"):
                        raw = re.sub(r"\x1b\[[0-9;]*m", "", d["_percent_str"]).replace("%", "").strip()
                        try:
                            percent = int(float(raw))
                        except ValueError:
                            percent = 50
                    speed = re.sub(r"\x1b\[[0-9;]*m", "", d.get("_speed_str", "")).strip()
                    eta = re.sub(r"\x1b\[[0-9;]*m", "", d.get("_eta_str", "")).strip()
                    self._jobs[job_id]["status"] = "downloading"
                    self._jobs[job_id]["progress"] = max(1, min(percent, 95))
                    self._jobs[job_id]["speed"] = speed
                    self._jobs[job_id]["eta"] = eta
                elif status == "finished":
                    self._jobs[job_id]["status"] = "converting"
                    self._jobs[job_id]["progress"] = 96

        def postprocessor_hook(d):
            if cancel_ev.is_set():
                raise DownloadCancelled()
            status = d.get("status")
            with self._lock:
                if job_id not in self._jobs:
                    return
                if status == "started":
                    self._jobs[job_id]["status"] = "converting"
                    self._jobs[job_id]["progress"] = 98
                elif status == "finished":
                    self._jobs[job_id]["progress"] = 99

        try:
            ffmpeg_path = find_ffmpeg()
            outtmpl = os.path.join(save_dir, "%(title).100s.%(ext)s")

            ydl_opts = {
                "outtmpl": outtmpl,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "windowsfilenames": True,
                "logger": SilentLogger(),
                "progress_hooks": [progress_hook],
                "postprocessor_hooks": [postprocessor_hook],
                "js_runtimes": {"node": {}},
                "remote_components": ["ejs:github"],
                "socket_timeout": 30,
                "retries": 5,
            }

            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path

            if fmt == "mp3":
                ydl_opts["format"] = "bestaudio/best"
                if quality not in ("320", "256", "192", "128"):
                    quality = "320"
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": quality,
                    }
                ]
            else:
                if quality == "best" or not quality:
                    ydl_opts["format"] = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b"
                else:
                    try:
                        h = int(quality)
                        ydl_opts["format"] = (
                            f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[height<={h}][ext=mp4] "
                            f"/ bv*[height<={h}]+ba/b[height<={h}] / best"
                        )
                    except ValueError:
                        ydl_opts["format"] = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b"
                ydl_opts["merge_output_format"] = "mp4"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if cancel_ev.is_set():
                    raise DownloadCancelled()

                title = info.get("title") or ("Media" if lang == "en" else "Medya")
                ext = "mp3" if fmt == "mp3" else "mp4"
                expected_file = ydl.prepare_filename(info)
                base, _ = os.path.splitext(expected_file)
                target_file = f"{base}.{ext}"

                final_path = ""
                if os.path.exists(target_file):
                    final_path = target_file
                elif os.path.exists(expected_file):
                    final_path = expected_file

                size_str = ""
                if final_path and os.path.exists(final_path):
                    sz = os.path.getsize(final_path)
                    size_str = f"{sz / (1024 * 1024):.1f} MB" if sz > 1024 * 1024 else f"{sz / 1024:.1f} KB"

                with self._lock:
                    self._jobs[job_id]["status"] = "completed"
                    self._jobs[job_id]["progress"] = 100
                    self._jobs[job_id]["title"] = title
                    self._jobs[job_id]["file_path"] = final_path
                    self._jobs[job_id]["filename"] = os.path.basename(final_path) if final_path else f"{title}.{ext}"
                    self._jobs[job_id]["file_size"] = size_str

        except DownloadCancelled:
            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = "cancelled"
        except Exception as e:
            err_msg = str(e)
            if "Private video" in err_msg or "login" in err_msg.lower():
                friendly = "This video is private or requires login." if lang == "en" else "Bu video gizli veya giriş yapılmasını gerektiriyor."
            elif "Video unavailable" in err_msg or "404" in err_msg:
                friendly = "Video not found or unavailable." if lang == "en" else "Video bulunamadı veya silinmiş."
            else:
                lines = [l.strip() for l in err_msg.split("\n") if l.strip()]
                clean = lines[-1] if lines else err_msg
                if clean.startswith("ERROR: "):
                    clean = clean[7:]
                friendly = clean

            with self._lock:
                if job_id in self._jobs:
                    self._jobs[job_id]["status"] = "error"
                    self._jobs[job_id]["error"] = friendly


def main():
    api = DesktopAPI()
    html_file = resource_path("ui/index.html")
    bg_color = "#121213" if api._config["theme"] == "dark" else "#F3F2EE"

    window = webview.create_window(
        title=APP_NAME,
        url=str(html_file),
        js_api=api,
        width=620,
        height=690,
        min_size=(480, 600),
        background_color=bg_color,
        text_select=True,
    )
    api._window = window

    def on_shown():
        apply_win32_window_chrome_async(APP_NAME, api._config["theme"], api._ico_path)

    window.events.shown += on_shown
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
