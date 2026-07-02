import os
import json
import re
import time
import requests
import urllib.parse

OUTPUT_DIR = "output"

# ── POLLINATIONS MODELS (best quality first) ──────────────────────────────────
# flux-realism  → ultra photorealistic, best for news/documentary content
# flux          → FLUX.1 base, great all-around
# turbo         → faster, slightly lower quality
POLLINATIONS_MODEL = "flux-realism"

# Universal cinematic quality suffix appended to every prompt
QUALITY_SUFFIX = (
    ", ultra photorealistic, shot on RED MONSTRO cinema camera, "
    "8K resolution, ultra sharp detail, professional color grading, "
    "anamorphic lens flare, vertical 9:16 portrait format, "
    "no text, no watermark, no letters, no words, no captions"
)


def save_package_to_file(item_id: str, ai_package: dict, trending_topic: str) -> dict:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
    folder  = os.path.join(OUTPUT_DIR, safe_id)
    os.makedirs(folder, exist_ok=True)

    full_path = os.path.join(folder, "full_package.json")
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump({"topic": trending_topic, "package": ai_package}, f,
                  indent=2, ensure_ascii=False)

    assets = ai_package.get("production_assets", {})

    script = assets.get("voiceover_script", "")
    if script:
        with open(os.path.join(folder, "voiceover_script.txt"), "w", encoding="utf-8") as f:
            f.write(script)

    metadata = ai_package.get("youtube_metadata", {})
    if metadata:
        with open(os.path.join(folder, "youtube_metadata.txt"), "w", encoding="utf-8") as f:
            f.write(f"TITLE:\n{metadata.get('title','')}\n\n")
            f.write(f"DESCRIPTION:\n{metadata.get('description','')}\n\n")
            f.write(f"TAGS:\n{', '.join(metadata.get('tags',[]))}\n")

    prompts = assets.get("image_prompts", [])
    if prompts:
        with open(os.path.join(folder, "image_prompts.txt"), "w", encoding="utf-8") as f:
            for i, p in enumerate(prompts, 1):
                f.write(f"Scene {i}:\n{p}\n\n")

    print(f"  [Output] ✅ Package saved → {folder}/")
    return {"full_package": full_path}


def _clean_prompt(raw: str) -> str:
    """Remove scene label prefix and inject quality suffix."""
    # Remove "Scene N:" or "SCENE N LABEL:" prefixes
    clean = re.sub(r"^(SCENE\s+\d+\s+\w+\s*:|Scene\s+\d+\s*:)\s*", "", raw,
                   flags=re.IGNORECASE).strip()
    # Remove bracketed placeholders like [Describe ...]
    clean = re.sub(r"\[.*?\]", "", clean).strip()
    # Append quality suffix if not already there
    if "no text" not in clean.lower():
        clean += QUALITY_SUFFIX
    return clean


def generate_images_pollinations(image_prompts: list, item_id: str,
                                  max_retries: int = 3) -> list:
    """
    Pollinations AI (flux-realism) se 9:16 cinematic images generate karta hai.
    Professional quality — RED camera + 8K + anamorphic lens.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
    folder  = os.path.join(OUTPUT_DIR, safe_id)
    os.makedirs(folder, exist_ok=True)

    saved = []

    for i, raw_prompt in enumerate(image_prompts, 1):
        clean   = _clean_prompt(raw_prompt)
        encoded = urllib.parse.quote(clean)
        img_path = os.path.join(folder, f"scene_{i}.jpg")

        success = False
        for attempt in range(1, max_retries + 1):
            try:
                seed = (i * 777) + (attempt * 333)

                # flux-realism gives the most cinematic photorealistic output
                url = (
                    f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?model={POLLINATIONS_MODEL}"
                    f"&width=1080&height=1920"
                    f"&nologo=true&enhance=true"
                    f"&seed={seed}"
                )

                label = f"Scene {i}/{len(image_prompts)}"
                if attempt == 1:
                    print(f"  [Image] {label} generating (flux-realism)...")
                else:
                    print(f"  [Image] {label} retry {attempt}/{max_retries}...")

                resp = requests.get(url, timeout=120, stream=True)

                if resp.status_code == 200:
                    tmp = img_path + ".tmp"
                    with open(tmp, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)

                    size_kb = os.path.getsize(tmp) / 1024
                    if size_kb < 10:
                        os.remove(tmp)
                        print(f"  [Image] ⚠️ {label} too small ({size_kb:.0f}KB), retry...")
                        time.sleep(4)
                        continue

                    os.rename(tmp, img_path)
                    saved.append(img_path)
                    print(f"  [Image] ✅ {label} saved ({size_kb:.0f}KB)")
                    success = True
                    time.sleep(1)   # small gap — polite to API
                    break
                else:
                    print(f"  [Image] ⚠️ {label} HTTP {resp.status_code}, retry...")
                    time.sleep(6)

            except Exception as e:
                print(f"  [Image] ⚠️ Scene {i} attempt {attempt} error: {e}")
                time.sleep(6)

        if not success:
            # Fallback: try with basic 'flux' model
            print(f"  [Image] 🔄 Scene {i} fallback to flux model...")
            try:
                fallback_url = (
                    f"https://image.pollinations.ai/prompt/{encoded}"
                    f"?model=flux"
                    f"&width=1080&height=1920"
                    f"&nologo=true&seed={i*999}"
                )
                resp = requests.get(fallback_url, timeout=120, stream=True)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                    sz = os.path.getsize(img_path) / 1024
                    if sz > 5:
                        saved.append(img_path)
                        print(f"  [Image] ✅ Scene {i} fallback OK ({sz:.0f}KB)")
                    else:
                        os.remove(img_path)
                        print(f"  [Image] ❌ Scene {i} fallback also failed.")
            except Exception as e2:
                print(f"  [Image] ❌ Scene {i} fallback error: {e2}")

    print(f"  [Image] Total: {len(saved)}/{len(image_prompts)} scenes ready.")
    return saved


def generate_voiceover_edgetts(script: str, item_id: str) -> str:
    """
    edge-tts se free American English voiceover.
    Voice: GuyNeural — deep, authoritative news-anchor style.
    """
    try:
        import asyncio
        import edge_tts

        safe_id  = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
        folder   = os.path.join(OUTPUT_DIR, safe_id)
        os.makedirs(folder, exist_ok=True)
        out_path = os.path.join(folder, "voiceover.mp3")

        async def _tts():
            communicate = edge_tts.Communicate(
                script,
                voice="en-US-GuyNeural",      # Deep authoritative news-anchor voice
                rate="+8%",                    # Slightly faster — more energetic
                pitch="-2Hz",                  # Slightly lower — more gravitas
                volume="+10%"
            )
            await communicate.save(out_path)

        asyncio.run(_tts())
        kb = os.path.getsize(out_path) / 1024
        print(f"  [TTS] ✅ Voiceover ready ({kb:.0f}KB) — GuyNeural")
        return out_path

    except Exception as e:
        print(f"  [TTS] ❌ edge-tts error: {e}")
        return ""
