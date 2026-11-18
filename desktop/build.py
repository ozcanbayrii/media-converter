import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def build():
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "MediaConverter",
        "--icon", str(BASE_DIR / "assets" / "app.ico"),
        "--add-data", f"{BASE_DIR / 'ui'};ui",
        "--add-data", f"{BASE_DIR / 'assets' / 'app.ico'};assets",
        "--collect-all", "webview",
        "--collect-all", "curl_cffi",
        "--collect-data", "certifi",
        "--hidden-import", "yt_dlp.networking._curlcffi",
        "--hidden-import", "yt_dlp.networking.impersonate",
        "--exclude-module", "tkinter",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
        "--exclude-module", "test",
        "--distpath", str(BASE_DIR / "dist"),
        "--workpath", str(BASE_DIR / "build"),
        "--specpath", str(BASE_DIR),
        str(BASE_DIR / "main.py"),
    ]
    print("Building MediaConverter.exe...")
    subprocess.run(cmd, check=True, cwd=str(BASE_DIR))
    exe_path = BASE_DIR / "dist" / "MediaConverter.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"Build complete: {exe_path} ({size_mb:.1f} MB)")
    else:
        raise FileNotFoundError("MediaConverter.exe was not created.")


if __name__ == "__main__":
    build()
