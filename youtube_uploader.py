import os
import json
import time
import requests

TOKENS_PATH = "data/youtube_tokens.json"
CREDS_PATH  = "data/youtube_oauth_creds.json"
SCOPES      = ("https://www.googleapis.com/auth/youtube.upload "
               "https://www.googleapis.com/auth/youtube")
TOKEN_URL   = "https://oauth2.googleapis.com/token"


# ── CREDENTIALS ──────────────────────────────────────────────────────────────
def _load_creds() -> dict:
    """
    Priority:
      1. Environment variables  YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET
      2. data/youtube_oauth_creds.json
    This way Render pe restart ke baad bhi credentials rehte hain.
    """
    env_id  = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    env_sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if env_id and env_sec:
        return {"client_id": env_id, "client_secret": env_sec}

    if not os.path.exists(CREDS_PATH):
        raise FileNotFoundError(
            "OAuth credentials nahi mili.\n"
            "Settings se Client ID/Secret save karo "
            "ya Render Environment Variables mein YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET set karo."
        )
    with open(CREDS_PATH) as f:
        return json.load(f)


def save_oauth_creds(client_id: str, client_secret: str) -> bool:
    os.makedirs("data", exist_ok=True)
    with open(CREDS_PATH, "w") as f:
        json.dump({"client_id": client_id.strip(),
                   "client_secret": client_secret.strip()}, f)
    return True


def creds_available() -> bool:
    env_id  = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    env_sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if env_id and env_sec:
        return True
    return os.path.exists(CREDS_PATH)


# ── TOKENS ───────────────────────────────────────────────────────────────────
def _load_tokens() -> dict:
    if not os.path.exists(TOKENS_PATH):
        raise FileNotFoundError("Tokens nahi mili. Pehle authorize karo.")
    with open(TOKENS_PATH) as f:
        return json.load(f)


def _save_tokens(tokens: dict):
    os.makedirs("data", exist_ok=True)
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


def _get_valid_access_token() -> str:
    tokens = _load_tokens()
    if tokens.get("expires_at", 0) > time.time() + 60:
        return tokens["access_token"]

    creds = _load_creds()
    r = requests.post(TOKEN_URL, data={
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": tokens["refresh_token"],
        "grant_type":    "refresh_token",
    }, timeout=20)

    if r.status_code != 200:
        raise Exception(f"Token refresh fail: {r.status_code} — {r.text[:200]}")

    new = r.json()
    tokens["access_token"] = new["access_token"]
    tokens["expires_at"]   = time.time() + new.get("expires_in", 3600)
    _save_tokens(tokens)
    return tokens["access_token"]


# ── DEVICE FLOW ───────────────────────────────────────────────────────────────
def get_device_code() -> dict:
    """
    Device authorization flow shuru karta hai.
    Returns: {device_code, user_code, verification_url, expires_in, interval}
    """
    creds = _load_creds()
    r = requests.post("https://oauth2.googleapis.com/device/code", data={
        "client_id": creds["client_id"],
        "scope":     SCOPES,
    }, timeout=20)

    if r.status_code != 200:
        raise Exception(f"Device code fail: {r.status_code} — {r.text[:300]}")
    return r.json()


def poll_for_token(device_code: str) -> dict:
    """
    One-shot poll. UI auto-poll karta rahega har 5 sec.
    Returns {"success": True} ya {"success": False, "pending": bool, "error": str}
    """
    creds = _load_creds()
    r = requests.post(TOKEN_URL, data={
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
        "device_code":   device_code,
        "grant_type":    "urn:ietf:params:oauth:grant-type:device_code",
    }, timeout=20)

    data = r.json()
    if r.status_code == 200 and "access_token" in data:
        _save_tokens({
            "access_token":  data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_at":    time.time() + data.get("expires_in", 3600),
        })
        return {"success": True}

    error = data.get("error", "")
    if error in ("authorization_pending", "slow_down"):
        return {"success": False, "pending": True,
                "error": "Abhi tak authorize nahi hua — wait karo."}
    return {"success": False, "pending": False,
            "error": data.get("error_description", error)}


# ── AUTH STATUS ───────────────────────────────────────────────────────────────
def get_auth_status() -> dict:
    if not creds_available():
        return {"step": "no_creds",
                "message": "Client ID / Secret nahi hai. Settings mein save karo."}
    if not os.path.exists(TOKENS_PATH):
        return {"step": "no_tokens",
                "message": "Authorize karna baaki hai — Settings mein 'Connect YouTube' dabao."}
    try:
        _get_valid_access_token()
        return {"step": "ready", "message": "YouTube connected! Upload ready hai."}
    except Exception as e:
        return {"step": "token_error", "message": str(e)}


def verify_cookies() -> dict:
    status = get_auth_status()
    return {
        "valid":        status["step"] == "ready",
        "channel":      "YouTube Account",
        "cookie_count": 0,
        "error":        status["message"] if status["step"] != "ready" else "",
    }


# ── UPLOAD ────────────────────────────────────────────────────────────────────
def upload_to_youtube(video_path: str, title: str, description: str,
                      tags: list) -> dict:
    try:
        access_token = _get_valid_access_token()
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Auth fail: {e}"}

    metadata = {
        "snippet": {
            "title":       title[:100],
            "description": description[:5000],
            "tags":        tags if isinstance(tags, list) else [],
            "categoryId":  "25",
        },
        "status": {
            "privacyStatus":          "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    file_size = os.path.getsize(video_path)
    headers   = {"Authorization": f"Bearer {access_token}",
                 "Content-Type":  "application/json"}

    init_r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={**headers,
                 "X-Upload-Content-Type":   "video/mp4",
                 "X-Upload-Content-Length": str(file_size)},
        json=metadata, timeout=30,
    )
    if init_r.status_code not in (200, 201):
        return {"success": False,
                "error": f"Upload init fail: {init_r.status_code} — {init_r.text[:400]}"}

    upload_url = init_r.headers.get("Location", "")
    if not upload_url:
        return {"success": False, "error": "Upload URL nahi mili."}

    chunk_size = 8 * 1024 * 1024
    video_id   = ""

    with open(video_path, "rb") as f:
        offset = 0
        while offset < file_size:
            chunk   = f.read(chunk_size)
            if not chunk:
                break
            end_byte = offset + len(chunk) - 1
            r = requests.put(upload_url, data=chunk, headers={
                "Authorization":  f"Bearer {access_token}",
                "Content-Range":  f"bytes {offset}-{end_byte}/{file_size}",
                "Content-Type":   "video/mp4",
            }, timeout=120)
            offset += len(chunk)

            if r.status_code in (200, 201):
                try:
                    video_id = r.json().get("id", "")
                except Exception:
                    pass
                break
            elif r.status_code == 308:
                rng = r.headers.get("Range", "")
                if rng:
                    offset = int(rng.split("-")[1]) + 1
            else:
                return {"success": False,
                        "error": f"Chunk fail: {r.status_code} — {r.text[:200]}"}

    if not video_id:
        return {"success": False, "error": "Upload hua lekin video ID nahi mila."}

    return {"success": True, "video_id": video_id,
            "url": f"https://www.youtube.com/shorts/{video_id}"}
