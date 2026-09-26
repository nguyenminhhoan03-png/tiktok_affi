import os
import json
import subprocess
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent.resolve()
JOBS_FILE = BASE_DIR / "jobs.json"
CONFIG_FILE = BASE_DIR / "config.json"
LOGS_FILE = BASE_DIR / "logs" / "tiktok_uploader.log"
VIDEOS_DIR = BASE_DIR / "videos"
ENV_FILE = BASE_DIR / ".env"

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static")
)

pipeline_process = None
pipeline_status = {"running": False, "log": "", "last_output": ""}

def _read_json(file_path):
    if not file_path.exists():
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _write_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.route("/")
def index():
    return render_template("index.html")

# --- API ENDPOINTS ---

@app.route("/api/stats", methods=["GET"])
def get_stats():
    jobs = _read_json(JOBS_FILE)
    total = len(jobs)
    pending = sum(1 for j in jobs if j.get("status") == "pending")
    processing = sum(1 for j in jobs if j.get("status") == "processing")
    failed = sum(1 for j in jobs if j.get("status") == "failed")
    
    # Video counts
    video_files = list(VIDEOS_DIR.glob("*.mp4")) if VIDEOS_DIR.exists() else []
    done_files = list((VIDEOS_DIR / "done").glob("*.mp4")) if (VIDEOS_DIR / "done").exists() else []
    
    return jsonify({
        "total_jobs": total,
        "pending": pending,
        "processing": processing,
        "failed": failed,
        "active_videos": len(video_files),
        "completed_videos": len(done_files),
        "pipeline_running": pipeline_status["running"]
    })

@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    jobs = _read_json(JOBS_FILE)
    return jsonify(jobs)

@app.route("/api/jobs", methods=["POST"])
def add_job():
    data = request.json
    jobs = _read_json(JOBS_FILE)
    
    new_job = {
        "product_url": data.get("product_url", "").strip(),
        "product_name": data.get("product_name", "").strip(),
        "prompt": data.get("prompt", "auto").strip() or "auto",
        "caption": data.get("caption", "auto").strip() or "auto",
        "video_segments": int(data.get("video_segments", 2)),
        "tiktok_account": data.get("tiktok_account", "acc1").strip() or "acc1",
        "status": "pending"
    }
    
    jobs.append(new_job)
    _write_json(JOBS_FILE, jobs)
    return jsonify({"success": True, "job": new_job})

@app.route("/api/jobs/batch", methods=["POST"])
def add_batch_jobs():
    data = request.json
    urls = data.get("urls", [])
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.splitlines() if u.strip()]
        
    jobs = _read_json(JOBS_FILE)
    added_count = 0
    
    for url in urls:
        if url:
            jobs.append({
                "product_url": url,
                "product_name": "",
                "prompt": "auto",
                "caption": "auto",
                "video_segments": 2,
                "tiktok_account": data.get("tiktok_account", "acc1"),
                "status": "pending"
            })
            added_count += 1
            
    _write_json(JOBS_FILE, jobs)
    return jsonify({"success": True, "added": added_count})

@app.route("/api/jobs/<int:index>", methods=["DELETE"])
def delete_job(index):
    jobs = _read_json(JOBS_FILE)
    if 0 <= index < len(jobs):
        deleted = jobs.pop(index)
        _write_json(JOBS_FILE, jobs)
        return jsonify({"success": True, "deleted": deleted})
    return jsonify({"success": False, "error": "Index out of range"}), 400

@app.route("/api/jobs/<int:index>/reset", methods=["POST"])
def reset_job(index):
    jobs = _read_json(JOBS_FILE)
    if 0 <= index < len(jobs):
        jobs[index]["status"] = "pending"
        jobs[index].pop("error_msg", None)
        jobs[index].pop("success", None)
        _write_json(JOBS_FILE, jobs)
        return jsonify({"success": True, "job": jobs[index]})
    return jsonify({"success": False, "error": "Index out of range"}), 400

@app.route("/api/logs", methods=["GET"])
def get_logs():
    if not LOGS_FILE.exists():
        return jsonify({"log": "No log file found."})
    try:
        with open(LOGS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return jsonify({"log": "".join(lines[-200:])})
    except Exception as e:
        return jsonify({"log": f"Error reading log: {e}"})

@app.route("/api/videos", methods=["GET"])
def get_videos():
    result = []
    if VIDEOS_DIR.exists():
        for f in VIDEOS_DIR.glob("*.mp4"):
            result.append({"name": f.name, "type": "active", "path": f"/videos_file/{f.name}"})
    
    done_dir = VIDEOS_DIR / "done"
    if done_dir.exists():
        for f in done_dir.glob("*.mp4"):
            result.append({"name": f.name, "type": "done", "path": f"/videos_file/done/{f.name}"})
            
    return jsonify(result)

@app.route("/videos_file/<path:filename>")
def serve_video(filename):
    return send_from_directory(str(VIDEOS_DIR), filename)

@app.route("/api/pipeline/run", methods=["POST"])
def run_pipeline_api():
    global pipeline_process, pipeline_status
    if pipeline_status["running"]:
        return jsonify({"success": False, "error": "Pipeline is already running"}), 400

    def _worker():
        global pipeline_process, pipeline_status
        pipeline_status["running"] = True
        try:
            cmd = ["python3", "main.py", "run-pipeline"]
            pipeline_process = subprocess.Popen(
                cmd, cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in iter(pipeline_process.stdout.readline, ''):
                pipeline_status["last_output"] = line.strip()
            pipeline_process.wait()
        except Exception as e:
            pipeline_status["last_output"] = f"Error: {e}"
        finally:
            pipeline_status["running"] = False

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Pipeline started"})

@app.route("/api/config", methods=["GET", "POST"])
def manage_config():
    if request.method == "POST":
        data = request.json
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"success": True})
    else:
        cfg = _read_json(CONFIG_FILE)
        return jsonify(cfg)

def run_server(port=5000, host="0.0.0.0"):
    logger_msg = f"🌐 Starting TikTok Auto Uploader Dashboard on http://localhost:{port}"
    print(logger_msg)
    app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    run_server()
