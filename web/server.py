import os
import time
import uuid
import shutil
import threading
import re
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
import yt_dlp

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# In-memory job tracker
# job_id -> {status, progress, speed, eta, title, file_path, filename, error, created_at}
jobs = {}
jobs_lock = threading.Lock()

def cleanup_old_files():
    """Periodically delete downloads older than 30 minutes to save VPS disk space."""
    while True:
        try:
            now = time.time()
            cutoff = now - (30 * 60) # 30 mins
            
            with jobs_lock:
                expired_job_ids = []
                for jid, info in jobs.items():
                    if info.get("created_at", 0) < cutoff:
                        expired_job_ids.append(jid)
                
                for jid in expired_job_ids:
                    info = jobs.pop(jid, None)
                    if info and info.get("file_path"):
                        try:
                            fp = Path(info["file_path"])
                            if fp.exists():
                                fp.unlink()
                        except Exception:
                            pass
                        
            # Also clean orphan files in DOWNLOADS_DIR older than 30 mins
            for f in DOWNLOADS_DIR.iterdir():
                if f.is_file():
                    try:
                        if f.stat().st_mtime < cutoff:
                            f.unlink()
                    except Exception:
                        pass
        except Exception as e:
            print(f"Cleanup error: {e}")
            
        time.sleep(300) # Check every 5 minutes

# Start cleanup thread in background
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def make_progress_hook(job_id):
    def hook(d):
        status = d.get('status')
        with jobs_lock:
            if job_id not in jobs:
                return
            
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                
                percent = 0
                if total > 0:
                    percent = int((downloaded / total) * 100)
                elif d.get('_percent_str'):
                    raw_p = re.sub(r'\x1b\[[0-9;]*m', '', d['_percent_str']).replace('%', '').strip()
                    try:
                        percent = int(float(raw_p))
                    except ValueError:
                        percent = 50

                speed = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', '')).strip()
                eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', '')).strip()

                jobs[job_id]["status"] = "downloading"
                jobs[job_id]["progress"] = max(1, min(percent, 95))
                jobs[job_id]["speed"] = speed
                jobs[job_id]["eta"] = eta

            elif status == 'finished':
                jobs[job_id]["status"] = "converting"
                jobs[job_id]["progress"] = 96
                filename = d.get('filename')
                if filename:
                    jobs[job_id]["file_path"] = filename

    return hook

def make_postprocessor_hook(job_id):
    def hook(d):
        status = d.get('status')
        with jobs_lock:
            if job_id not in jobs:
                return
            if status == 'started':
                jobs[job_id]["status"] = "converting"
                jobs[job_id]["progress"] = 98
            elif status == 'finished':
                jobs[job_id]["progress"] = 99
    return hook

def run_download_worker(job_id, url, fmt, quality="best", lang="tr"):
    try:
        ffmpeg_path = shutil.which("ffmpeg")
        # Unique prefix so filenames never clash
        safe_prefix = f"{job_id[:8]}_%(title).100s.%(ext)s"
        outtmpl = str(DOWNLOADS_DIR / safe_prefix)

        ydl_opts = {
            'outtmpl': outtmpl,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'windowsfilenames': True,
            'progress_hooks': [make_progress_hook(job_id)],
            'postprocessor_hooks': [make_postprocessor_hook(job_id)],
            'js_runtimes': {'node': {}},
            'remote_components': ['ejs:github'],
            'socket_timeout': 30,
            'retries': 5,
        }

        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        if fmt == "mp3":
            ydl_opts['format'] = 'bestaudio/best'
            if quality not in ["320", "256", "192", "128"]:
                quality = "320"
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }]
        else: # mp4
            if quality == "best" or not quality:
                ydl_opts['format'] = 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b'
            else:
                try:
                    h = int(quality)
                    ydl_opts['format'] = f'bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[height<={h}][ext=mp4] / bv*[height<={h}]+ba/b[height<={h}] / best'
                except ValueError:
                    ydl_opts['format'] = 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b'
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Media' if lang == 'en' else 'Medya')
            
            ext = "mp3" if fmt == "mp3" else "mp4"
            expected_file = ydl.prepare_filename(info)
            base, _ = os.path.splitext(expected_file)
            target_file = f"{base}.{ext}"

            final_path = None
            if os.path.exists(target_file):
                final_path = target_file
            elif os.path.exists(expected_file):
                final_path = expected_file
            else:
                # Find matching file with job_id prefix
                for f in DOWNLOADS_DIR.glob(f"{job_id[:8]}*"):
                    final_path = str(f)
                    break

            if not final_path or not os.path.exists(final_path):
                raise Exception("Downloaded file not found on disk." if lang == "en" else "İndirilen dosya disk üzerinde bulunamadı.")

            file_size_bytes = os.path.getsize(final_path)
            # Friendly size string
            if file_size_bytes > 1024 * 1024:
                size_str = f"{file_size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size_bytes / 1024:.1f} KB"

            clean_filename = f"{title}.{ext}".replace('/', '_').replace('\\', '_')

            with jobs_lock:
                jobs[job_id]["status"] = "completed"
                jobs[job_id]["progress"] = 100
                jobs[job_id]["title"] = title
                jobs[job_id]["file_path"] = final_path
                jobs[job_id]["filename"] = clean_filename
                jobs[job_id]["file_size"] = size_str

    except Exception as e:
        err_msg = str(e)
        if "Private video" in err_msg or "login" in err_msg.lower():
            friendly_err = "This video is private or requires login." if lang == "en" else "Bu video gizli veya giriş yapılmasını gerektiriyor."
        elif "Video unavailable" in err_msg or "404" in err_msg:
            friendly_err = "Video not found or unavailable." if lang == "en" else "Video bulunamadı veya silinmiş."
        else:
            lines = [l.strip() for l in err_msg.split('\n') if l.strip()]
            clean_err = lines[-1] if lines else err_msg
            if clean_err.startswith("ERROR: "):
                clean_err = clean_err[7:]
            friendly_err = clean_err

        with jobs_lock:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = friendly_err

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    fmt = data.get("format", "mp4").lower()
    quality = (data.get("quality") or "best").strip().lower()
    lang = (data.get("lang") or "tr").strip().lower()
    if lang not in ["tr", "en"]:
        lang = "tr"

    if not url:
        msg = "Please enter a link." if lang == "en" else "Lütfen bir bağlantı girin."
        return jsonify({"success": False, "error": msg}), 400

    if not (url.startswith("http://") or url.startswith("https://")):
        msg = "Please enter a valid URL starting with http:// or https://." if lang == "en" else "Geçerli bir web bağlantısı girin (http:// veya https://)."
        return jsonify({"success": False, "error": msg}), 400

    if fmt not in ["mp4", "mp3"]:
        fmt = "mp4"

    job_id = str(uuid.uuid4())
    with jobs_lock:
        jobs[job_id] = {
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
            "created_at": time.time(),
        }

    thread = threading.Thread(target=run_download_worker, args=(job_id, url, fmt, quality, lang), daemon=True)
    thread.start()

    return jsonify({"success": True, "job_id": job_id})

@app.route("/api/status/<job_id>")
def get_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"status": "error", "error": "İşlem bulunamadı."}), 404
        return jsonify(job)

@app.route("/api/file/<job_id>")
def download_file(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.get("status") != "completed":
            return abort(404, description="Dosya henüz hazır değil veya bulunamadı.")
        
        file_path = job.get("file_path")
        filename = job.get("filename") or "medya_indirilen"

    if not file_path or not os.path.exists(file_path):
        return abort(404, description="Dosya disk üzerinde bulunamadı.")

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename
    )

if __name__ == "__main__":
    # Host on 0.0.0.0 so it can be accessed from outside VPS
    port = int(os.environ.get("PORT", 5050))
    print(f"🚀 Medya Dönüştürücü Web Sunucusu Başlatılıyor: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
