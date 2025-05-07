from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from pydub import AudioSegment
from pydub.utils import which
from threading import Thread
from flask import Flask, request, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import os, subprocess, uuid, time, json, re
from pydub import AudioSegment
import subprocess
import os
import uuid
import json
import re
import validators
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load config
load_dotenv()
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "static/output")
JOBS_DIR = "jobs"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(JOBS_DIR, exist_ok=True)
AudioSegment.converter = which("ffmpeg")

app = Flask(__name__)
Talisman(app, content_security_policy=None)  # Enforce HTTPS and security headers
limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)
CORS(app)


ALLOWED_DOMAINS = ['youtube.com', 'www.youtube.com', 'youtu.be']

def is_valid_youtube_url(url):
    if not validators.url(url): return False
    return any(domain in url for domain in ALLOWED_DOMAINS)

def sanitize_filename(title):
    """Remove characters unsafe for filenames"""
    return re.sub(r'[\\/*?:"<>|]', "", title)

def save_job(job_id, data):
    with open(f"{JOBS_DIR}/job_{job_id}.json", "w") as f:
        json.dump(data, f)

def load_job(job_id):
    try:
        with open(f"{JOBS_DIR}/job_{job_id}.json", "r") as f:
            return json.load(f)
    except:
        return None

def convert_audio_background(job_id, url, fmt, bitrate, normalize):
    try:
        # 1️⃣ Get title first using yt-dlp
        title_result = subprocess.run(
            ["yt-dlp", "--get-title", url],
            capture_output=True, text=True
        )

        if title_result.returncode != 0:
            raise Exception("Failed to fetch video title")

        raw_title = title_result.stdout.strip()
        title = sanitize_filename(raw_title)
        base_filename = f"{title}.{fmt}"
        tmp_audio_path = os.path.join(OUTPUT_DIR, f"{job_id}.m4a")
        final_path = os.path.join(OUTPUT_DIR, base_filename)

        # 2️⃣ Download audio in M4A
        result = subprocess.run([
            "yt-dlp", "-f", "bestaudio", "-x",
            "--audio-format", "m4a",
            "-o", tmp_audio_path,
            url
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(result.stderr)

        # 3️⃣ Load, normalize, convert
        audio = AudioSegment.from_file(tmp_audio_path, format="m4a")
        if normalize:
            audio = audio.normalize()

        export_params = {}
        if fmt in BITRATE_FORMATS:
            export_params["bitrate"] = bitrate

        audio.export(final_path, format=fmt, **export_params)
        os.remove(tmp_audio_path)

        # 4️⃣ Update job
        job = load_job(job_id)
        job['status'] = 'ready'
        job['filename'] = base_filename
        job['title'] = title
        save_job(job_id, job)

    except Exception as e:
        job = load_job(job_id)
        job['status'] = 'error'
        job['error'] = str(e)
        save_job(job_id, job)



def cleanup_old_files():
    while True:
        try:
            max_age = int(os.getenv("MAX_FILE_AGE_MINUTES", 10))
            cutoff = datetime.now() - timedelta(minutes=max_age)

            for fname in os.listdir(OUTPUT_DIR):
                fpath = os.path.join(OUTPUT_DIR, fname)
                if os.path.isfile(fpath):
                    ftime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if ftime < cutoff:
                        os.remove(fpath)

            for fname in os.listdir(JOBS_DIR):
                fpath = os.path.join(JOBS_DIR, fname)
                if os.path.isfile(fpath):
                    ftime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if ftime < cutoff:
                        os.remove(fpath)

        except Exception as e:
            print("Cleanup error:", str(e))

        time.sleep(int(os.getenv("CLEANUP_INTERVAL_SECONDS", 60)))

# Supported formats
ALLOWED_FORMATS = ["mp3", "wav", "aac", "ogg", "flac", "m4a", "wma", "opus", "alac"]

DEFAULT_BITRATE = "192k"  # default fallback
BITRATE_FORMATS = ["mp3", "aac", "ogg", "wma", "opus", "m4a"]

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json(force=True)
    url = data.get("url")
    fmt = data.get("format", "mp3").lower()
    bitrate = data.get("bitrate", DEFAULT_BITRATE)
    normalize = data.get("normalize", False)

    if not url:
        return jsonify({"error": "URL is required"}), 400

    if fmt not in ALLOWED_FORMATS:
        return jsonify({"error": f"Format {fmt} not supported"}), 400
    
    if not is_valid_youtube_url(data.get("url", "")):
        return jsonify({"error": "Invalid URL"}), 400

    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "url": url,
        "format": fmt,
        "bitrate": bitrate,
        "normalize": normalize,
        "status": "pending",
        "created_at": time.time()
    }
    save_job(job_id, job)

    thread = Thread(target=convert_audio_background, args=(job_id, url, fmt, bitrate, normalize))
    thread.start()

    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def job_status(job_id):
    job = load_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route('/download/<job_id>')
def download(job_id):
    job = load_job(job_id)
    if job and job.get('status') == 'ready':
        file_path = os.path.join(OUTPUT_DIR, job['filename'])
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "File not ready"}), 400


@app.route('/')
def index():
    return "🔊 YouTube Audio Converter is live!"

if __name__ == '__main__':
    Thread(target=cleanup_old_files, daemon=True).start()
    app.run(debug=True)

from flask import Flask, request, send_from_directory
import os

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    dist_dir = os.path.join(os.getcwd(), "frontend", "dist")
    file_path = os.path.join(dist_dir, path)

    if path != "" and os.path.exists(file_path):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, "index.html")
