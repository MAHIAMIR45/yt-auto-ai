import threading
import time
import os
import re
import json
from datetime import datetime, timezone, timedelta

EST_OFFSET = timedelta(hours=-5)
PEAK_SLOTS = [8, 12, 17]
DAILY_LIMIT = 4
GEN_LEAD_HOURS = 2

_PERSIST_PATH = "data/autopilot_state.json"

_state = {
    "running": False,
    "status_msg": "Stopped",
    "daily_uploads": 0,
    "daily_date": "",
    "last_generated_topic": None,
    "next_action": None,
    "next_action_time": None,
    "log": [],
    "generating": False,
    "uploading": False,
}
_lock = threading.Lock()
_thread = None


def _save_persist_state():
    """Disk pe save karo — restart ke baad bhi state yaad rahe."""
    try:
        os.makedirs("data", exist_ok=True)
        with _lock:
            data = {
                "running": _state["running"],
                "daily_uploads": _state["daily_uploads"],
                "daily_date": _state["daily_date"],
            }
        with open(_PERSIST_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _load_persist_state() -> dict:
    """Disk se saved state load karo."""
    try:
        if os.path.exists(_PERSIST_PATH):
            with open(_PERSIST_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def auto_resume():
    """
    Server restart ke baad call karo.
    Agar pehle se Auto-Pilot ON tha, automatically restart ho jaata hai.
    """
    saved = _load_persist_state()
    if saved.get("running"):
        today = (datetime.now(timezone.utc) + EST_OFFSET).strftime("%Y-%m-%d")
        with _lock:
            if saved.get("daily_date") == today:
                _state["daily_uploads"] = saved.get("daily_uploads", 0)
                _state["daily_date"] = today
        print("[AutoPilot] 🔄 Server restart detected — Auto-Pilot auto-resuming...")
        start()
        return True
    return False


def _est_now():
    return datetime.now(timezone.utc) + EST_OFFSET


def _log(msg):
    with _lock:
        ts = _est_now().strftime("%d %b %H:%M EST")
        entry = {"time": ts, "msg": msg}
        _state["log"].insert(0, entry)
        _state["log"] = _state["log"][:60]
    print(f"  [AutoPilot] {msg}")


def get_state():
    with _lock:
        s = dict(_state)
        s["log"] = list(_state["log"])
        return s


def start():
    global _thread
    with _lock:
        if _state["running"]:
            return {"ok": False, "msg": "Already running"}
        _state["running"] = True
        _state["status_msg"] = "Running"
    _save_persist_state()
    _thread = threading.Thread(target=_run_loop, daemon=True)
    _thread.start()
    _log("🚀 Auto-Pilot started! 24/7 mode ON")
    return {"ok": True}


def stop():
    with _lock:
        _state["running"] = False
        _state["status_msg"] = "Stopped"
    _save_persist_state()
    _log("⏹️ Auto-Pilot stopped by user.")
    return {"ok": True}


def get_schedule_today():
    now = _est_now()
    today = now.strftime("%Y-%m-%d")
    schedule = []
    for peak in PEAK_SLOTS:
        gen_hour = max(0, peak - GEN_LEAD_HOURS)
        schedule.append({
            "generate_at": f"{gen_hour:02d}:00 EST",
            "upload_at": f"{peak:02d}:00 EST",
            "status": "done" if now.hour > peak else ("active" if now.hour >= gen_hour else "pending"),
            "slot": peak,
        })
    return schedule


def get_next_upload_seconds():
    now = _est_now()
    hour = now.hour
    minute = now.minute
    second = now.second
    for peak in PEAK_SLOTS:
        if peak > hour:
            diff_secs = (peak - hour) * 3600 - minute * 60 - second
            return diff_secs
    tomorrow_first = PEAK_SLOTS[0]
    diff_secs = (24 - hour + tomorrow_first) * 3600 - minute * 60 - second
    return diff_secs


def _reset_daily_if_needed():
    now = _est_now()
    date_str = now.strftime("%Y-%m-%d")
    is_new_day = False
    with _lock:
        if _state["daily_date"] != date_str:
            _state["daily_date"] = date_str
            _state["daily_uploads"] = 0
            is_new_day = True
    if is_new_day:
        _save_persist_state()
        _log(f"📅 New day ({date_str}) — daily counter reset (0/{DAILY_LIMIT})")
        threading.Thread(target=_daily_storage_cleanup, daemon=True).start()


def _run_loop():
    _log("⚙️ Auto-Pilot engine running (checks every 5 min)...")
    while True:
        with _lock:
            if not _state["running"]:
                break
        try:
            _reset_daily_if_needed()
            _tick()
        except Exception as e:
            _log(f"❌ Loop error: {e}")
        time.sleep(300)


def _tick():
    now = _est_now()
    hour = now.hour

    with _lock:
        daily = _state["daily_uploads"]
        is_gen = _state["generating"]
        is_up = _state["uploading"]

    if daily >= DAILY_LIMIT:
        with _lock:
            _state["status_msg"] = f"✅ Daily limit reached ({DAILY_LIMIT}/day). Resume tomorrow."
            _state["next_action"] = "Tomorrow"
        return

    if hour in PEAK_SLOTS and not is_up:
        _do_upload(hour)

    should_gen = False
    for peak in PEAK_SLOTS:
        gen_hour = max(0, peak - GEN_LEAD_HOURS)
        if hour == gen_hour:
            should_gen = True
            break

    if should_gen and not is_gen and not is_up:
        with _lock:
            daily2 = _state["daily_uploads"]
        if daily2 < DAILY_LIMIT:
            threading.Thread(target=_do_generate, daemon=True).start()

    _update_next_action(hour)


def _update_next_action(hour):
    for peak in PEAK_SLOTS:
        gen_hour = max(0, peak - GEN_LEAD_HOURS)
        if hour < gen_hour:
            with _lock:
                _state["next_action"] = f"Generate video at {gen_hour:02d}:00 EST → Upload at {peak:02d}:00 EST"
            return
        elif hour < peak:
            with _lock:
                _state["next_action"] = f"Upload queued video at {peak:02d}:00 EST"
            return
    with _lock:
        next_peak = PEAK_SLOTS[0]
        _state["next_action"] = f"Next cycle starts at {max(0, next_peak - GEN_LEAD_HOURS):02d}:00 EST tomorrow"


def _cleanup_output_folder(safe_id: str):
    """
    Upload ke baad heavy files delete karo — storage free karo.
    Rakho: full_package.json, youtube_metadata.txt, image_prompts.txt, voiceover_script.txt
    Delete karo: shorts_video.mp4, voiceover.mp3, scene_*.jpg
    """
    folder = os.path.join("output", safe_id)
    if not os.path.isdir(folder):
        return

    delete_patterns = [
        "shorts_video.mp4",
        "voiceover.mp3",
    ]

    freed_mb = 0.0
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        should_delete = (
            fname in delete_patterns or
            fname.startswith("scene_") and fname.endswith(".jpg")
        )
        if should_delete and os.path.isfile(fpath):
            try:
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                os.remove(fpath)
                freed_mb += size_mb
            except Exception:
                pass

    if freed_mb > 0:
        _log(f"🗑️ Storage freed: {freed_mb:.1f} MB deleted from {safe_id}/")


def _daily_storage_cleanup():
    """
    Roz midnight EST pe run hota hai.
    Koi bhi purani video/audio/image files delete karo jo 
    uploaded items ki hain ya 2 din se zyada purani hain.
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td

    output_dir = "output"
    if not os.path.isdir(output_dir):
        return

    cutoff = _dt.now(_tz.utc) - _td(days=1)
    freed_total = 0.0

    for folder_name in os.listdir(output_dir):
        folder_path = os.path.join(output_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue

        pkg_path = os.path.join(folder_path, "full_package.json")
        if not os.path.exists(pkg_path):
            continue

        # Folder ka creation time check karo
        try:
            mtime = _dt.fromtimestamp(os.path.getmtime(pkg_path), tz=_tz.utc)
            if mtime < cutoff:
                for fname in os.listdir(folder_path):
                    if (fname == "shorts_video.mp4" or
                            fname == "voiceover.mp3" or
                            (fname.startswith("scene_") and fname.endswith(".jpg"))):
                        fpath = os.path.join(folder_path, fname)
                        try:
                            freed_total += os.path.getsize(fpath) / (1024 * 1024)
                            os.remove(fpath)
                        except Exception:
                            pass
        except Exception:
            pass

    if freed_total > 0:
        _log(f"🌙 Daily cleanup: {freed_total:.1f} MB freed from old output folders")
    else:
        _log("🌙 Daily cleanup: Storage already clean ✅")


def _do_upload(hour):
    from queue_manager import get_due_items, mark_as_uploaded
    from youtube_uploader import upload_to_youtube, get_auth_status

    auth = get_auth_status()
    if auth["step"] != "ready":
        _log("⚠️ YouTube not connected — upload skip kar raha hoon")
        return

    due = get_due_items(hour)
    if not due:
        _log(f"⏰ {hour:02d}:00 — Queue mein koi video nahi")
        return

    item = due[0]
    item_id = item["id"]
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
    video_path = os.path.join("output", safe_id, "shorts_video.mp4")

    if not os.path.exists(video_path):
        _log(f"⚠️ Video file nahi mili: {safe_id}")
        return

    title = item.get("youtube_metadata", {}).get("title", "YouTube Short")
    description = item.get("youtube_metadata", {}).get("description", "")
    tags = item.get("youtube_metadata", {}).get("tags", [])

    with _lock:
        _state["uploading"] = True
        _state["status_msg"] = f"📤 Uploading: '{title[:40]}...'"

    _log(f"📤 Upload shuru: '{title[:50]}'")
    result = upload_to_youtube(video_path, title, description, tags)

    with _lock:
        _state["uploading"] = False

    if result["success"]:
        mark_as_uploaded(item_id, result["url"])
        with _lock:
            _state["daily_uploads"] += 1
            daily = _state["daily_uploads"]
            _state["status_msg"] = f"✅ Running — {daily}/{DAILY_LIMIT} videos uploaded today"
        _save_persist_state()
        _log(f"✅ Upload done! {result['url']} ({daily}/{DAILY_LIMIT} today)")

        # ── Upload ke turant baad storage free karo ──────────────────
        _log("🗑️ Storage cleanup — video/audio/images delete ho rahe hain...")
        _cleanup_output_folder(safe_id)
    else:
        _log(f"❌ Upload fail: {result.get('error', 'Unknown error')}")
        with _lock:
            _state["status_msg"] = "Running — Upload fail, retry next slot"


def _do_generate():
    from trends import fetch_trending_topics
    from agent import generate_autonomous_package
    from queue_manager import save_to_queue
    from output_generator import save_package_to_file, generate_images_pollinations, generate_voiceover_edgetts
    from video_editor import create_shorts_video

    _CKPT_PATH = "data/gen_checkpoint.json"

    def _save_ckpt(data: dict):
        try:
            with open(_CKPT_PATH, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load_ckpt() -> dict:
        try:
            if os.path.exists(_CKPT_PATH):
                with open(_CKPT_PATH) as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _clear_ckpt():
        try:
            if os.path.exists(_CKPT_PATH):
                os.remove(_CKPT_PATH)
        except Exception:
            pass

    with _lock:
        _state["generating"] = True

    try:
        # ── CHECKPOINT: kya pehle se koi incomplete job hai? ──────────────
        ckpt = _load_ckpt()
        item_id = ckpt.get("item_id")
        topic   = ckpt.get("topic")
        step    = ckpt.get("step", "start")   # start / images / voiceover / video

        if item_id and topic and step != "start":
            _log(f"🔄 Checkpoint mila! Resume: '{topic[:40]}' (step: {step})")
        else:
            # Fresh start
            _log("🔍 USA trending topics fetch ho rahi hain...")
            topics = fetch_trending_topics(limit=5)
            if not topics:
                _log("❌ Koi trending topic nahi mila")
                return
            topic = topics[0]
            _log(f"🔥 Topic selected: '{topic}'")

            with _lock:
                _state["status_msg"] = f"🤖 Generating video: '{topic[:40]}'"
                _state["last_generated_topic"] = topic

            _log("🤖 AI se package generate ho raha hai...")
            ai_package = generate_autonomous_package(topic)
            item_id = save_to_queue(topic, ai_package)
            save_package_to_file(item_id, ai_package, topic)
            _save_ckpt({"item_id": item_id, "topic": topic, "step": "images"})
            step = "images"
            title = ai_package.get("youtube_metadata", {}).get("title", "")
            _log(f"📝 Script ready: '{title[:50]}'")

        safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
        folder  = os.path.join("output", safe_id)

        # Title load karo checkpoint ke baad ke steps ke liye
        pkg_path = os.path.join(folder, "full_package.json")
        title = ""
        try:
            with open(pkg_path) as f:
                pkg_data = json.load(f)
            title = pkg_data.get("package", {}).get("youtube_metadata", {}).get("title", "")
            prompts = pkg_data.get("package", {}).get("production_assets", {}).get("image_prompts", [])
            script  = pkg_data.get("package", {}).get("production_assets", {}).get("voiceover_script", "")
        except Exception:
            prompts, script = [], ""

        # ── STEP: Images ─────────────────────────────────────────────────
        if step == "images":
            n_imgs = len(prompts)
            _log(f"🖼️ {n_imgs} cinematic images download ho rahi hain (memory-safe)...")
            images = generate_images_pollinations(prompts, item_id)
            _log(f"✅ {len(images)}/{n_imgs} images ready")
            _save_ckpt({"item_id": item_id, "topic": topic, "step": "voiceover"})
            step = "voiceover"

        # ── STEP: Voiceover ──────────────────────────────────────────────
        audio_path = os.path.join(folder, "voiceover.mp3")
        if step == "voiceover":
            _log("🎙️ Voiceover generate ho raha hai...")
            audio = generate_voiceover_edgetts(script, item_id)
            _save_ckpt({"item_id": item_id, "topic": topic, "step": "video"})
            step = "video"
        else:
            audio = audio_path if os.path.exists(audio_path) else ""

        # ── STEP: Video ──────────────────────────────────────────────────
        if step == "video":
            # Existing images check karo (images already deleted ho sakti hain agar resume)
            existing_imgs = sorted([
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.startswith("scene_") and f.endswith(".jpg")
            ]) if os.path.isdir(folder) else []

            if existing_imgs:
                _log("🎬 FFmpeg se video edit ho raha hai (low-memory mode)...")
                create_shorts_video(item_id, existing_imgs, audio, title, folder)
                _log("🎉 Video ready! Upload next peak slot pe hogi.")
                _clear_ckpt()
            else:
                video_path = os.path.join(folder, "shorts_video.mp4")
                if os.path.exists(video_path):
                    _log("✅ Video already exists (restart recovery)")
                    _clear_ckpt()
                else:
                    _log("⚠️ Images nahi mili — images step se restart...")
                    _save_ckpt({"item_id": item_id, "topic": topic, "step": "images"})

        with _lock:
            _state["status_msg"] = "Running — Video ready, upload queue mein hai"

    except Exception as e:
        _log(f"❌ Generate error: {e}")
        with _lock:
            _state["status_msg"] = f"Running — Error: {str(e)[:60]}"
    finally:
        with _lock:
            _state["generating"] = False
