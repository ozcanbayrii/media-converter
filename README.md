# Media Converter

**English** · [Türkçe](README.tr.md)

Minimalist, self-hosted **MP4 & MP3 media converter** for **YouTube**, **Instagram**, and **TikTok** — available as both a responsive web application and a native Windows desktop executable (`.exe`).

Live demo: **[converter.ozcan.work](https://converter.ozcan.work)**

---

## Features

- **Multi-platform support:** YouTube (videos & Shorts), Instagram (Reels & posts), TikTok (watermark-free via `curl_cffi` TLS impersonation), and other `yt-dlp` supported sites.
- **Format & quality control:**
  - **MP4 Video:** Auto/Max resolution, `1080p`, `720p`, `480p`
  - **MP3 Audio:** `320 kbps`, `256 kbps`, `192 kbps`, `128 kbps`
- **Minimalist monochrome UI:** Soft off-black (`#121213`) dark mode and warm alabaster (`#F3F2EE`) light mode with automatic system theme detection and manual toggle.
- **Bilingual (`EN` / `TR`):** Automatically detects browser or OS language on startup, with instant in-app switching.
- **Web App (`web/`):** Mobile-friendly Flask backend, real-time progress telemetry, manual download confirmation, Docker support, and automatic 30-minute temporary file cleanup.
- **Desktop App (`desktop/`):** Lightweight native Windows WebView2 app (`pywebview`) with synced Windows 11 dark/light titlebar, native folder picker, persistent settings, one-click open/reveal in Explorer, and single-file `.exe` build script.

---

## Project Structure

```text
media-converter/
├── web/                     # Self-hosted web application (Flask + Docker)
│   ├── server.py            # Backend API, yt-dlp worker & auto-cleanup
│   ├── templates/
│   │   └── index.html       # Responsive monochrome UI (EN/TR, Dark/Light)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── VPS_KURULUM.md       # VPS deployment guide (Turkish)
├── desktop/                 # Native Windows desktop application (pywebview)
│   ├── main.py              # Desktop backend & Win32 titlebar integration
│   ├── ui/
│   │   ├── index.html       # Monochrome desktop UI (EN/TR, Dark/Light)
│   │   └── icon.png
│   ├── assets/
│   │   ├── app.ico
│   │   └── icon.png
│   ├── build.py             # PyInstaller single-file .exe builder
│   └── requirements.txt
├── README.md                # English documentation
├── README.tr.md             # Turkish documentation
└── LICENSE
```

---

## Prerequisites

- **Python** 3.11+
- **FFmpeg** (available on `PATH` — required for MP3 extraction and HD MP4 merging)
- **Node.js** (recommended for solving YouTube JS challenges via `yt-dlp`)

---

## Quick Start — Web App

### Option 1: Docker Compose (Recommended)

```bash
cd web
docker compose up -d --build
```

The app will be available at `http://localhost:5000`.

### Option 2: Run Locally with Python

```bash
cd web
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
python server.py
```

By default, `server.py` runs on port `5050` (`PORT` environment variable supported): `http://localhost:5050`.

---

## Quick Start — Windows Desktop App

### Run from source

```bash
cd desktop
pip install -r requirements.txt
python main.py
```

### Build standalone `.exe`

```bash
cd desktop
python build.py
```

This generates a standalone executable at `desktop/dist/MediaConverter.exe` with zero console window and native WebView2 rendering.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
