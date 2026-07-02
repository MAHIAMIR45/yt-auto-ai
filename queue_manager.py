import json
import os
from datetime import datetime, timezone

DB_PATH = "data/trends_db.json"


def _load_db() -> dict:
    """Database file load karta hai, agar nahi hai to naya banata hai."""
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        empty_db = {
            "meta": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_processed": 0,
                "total_queued": 0,
                "total_uploaded": 0
            },
            "queue": [],
            "uploaded": [],
            "failed": []
        }
        _save_db(empty_db)
        return empty_db

    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(db: dict):
    """Database file save karta hai."""
    os.makedirs("data", exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def save_to_queue(trending_topic: str, ai_package: dict) -> str:
    """
    AI-generated package ko database queue me save karta hai.
    Returns: unique item_id
    """
    db = _load_db()

    item_id = f"short_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{len(db['queue']):04d}"

    target_hour = ai_package.get("trend_analysis", {}).get("target_upload_hour_est", 12)
    virality = ai_package.get("trend_analysis", {}).get("virality_score_1_to_10", 5)

    queue_item = {
        "id": item_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trending_topic": trending_topic,
        "target_upload_hour_est": target_hour,
        "virality_score": virality,
        "scheduling_reason": ai_package.get("trend_analysis", {}).get("scheduling_reason", ""),
        "youtube_metadata": ai_package.get("youtube_metadata", {}),
        "production_assets": ai_package.get("production_assets", {}),
        "output_files": {}
    }

    db["queue"].append(queue_item)
    db["meta"]["total_queued"] = len(db["queue"])
    db["meta"]["total_processed"] = db["meta"].get("total_processed", 0) + 1
    db["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()

    _save_db(db)
    print(f"  [Queue] Saved: {item_id} | Virality: {virality}/10 | Upload: {target_hour}:00 EST")
    return item_id


def get_queue_status() -> dict:
    """Queue ka full status return karta hai."""
    db = _load_db()
    return {
        "total_queued": len(db["queue"]),
        "total_uploaded": len(db["uploaded"]),
        "total_failed": len(db["failed"]),
        "meta": db["meta"],
        "queue_items": [
            {
                "id": item["id"],
                "topic": item["trending_topic"],
                "virality": item["virality_score"],
                "upload_hour_est": item["target_upload_hour_est"],
                "status": item["status"],
                "title": item.get("youtube_metadata", {}).get("title", "N/A")
            }
            for item in db["queue"]
        ]
    }


def mark_as_uploaded(item_id: str, upload_url: str = ""):
    """Item ko uploaded me move karta hai."""
    db = _load_db()
    for i, item in enumerate(db["queue"]):
        if item["id"] == item_id:
            item["status"] = "uploaded"
            item["uploaded_at"] = datetime.now(timezone.utc).isoformat()
            item["upload_url"] = upload_url
            db["uploaded"].append(item)
            db["queue"].pop(i)
            db["meta"]["total_uploaded"] = len(db["uploaded"])
            db["meta"]["total_queued"] = len(db["queue"])
            _save_db(db)
            print(f"  [Queue] Marked uploaded: {item_id}")
            return
    print(f"  [Queue] Item not found: {item_id}")


def get_due_items(current_hour_est: int) -> list:
    """Current EST hour ke basis pe due items return karta hai."""
    db = _load_db()
    due = []
    for item in db["queue"]:
        if item["status"] == "queued" and item["target_upload_hour_est"] <= current_hour_est:
            due.append(item)
    return sorted(due, key=lambda x: x["virality_score"], reverse=True)


def clear_queue():
    """Queue clear karta hai (testing ke liye)."""
    db = _load_db()
    db["queue"] = []
    db["meta"]["total_queued"] = 0
    _save_db(db)
    print("  [Queue] Queue cleared.")
