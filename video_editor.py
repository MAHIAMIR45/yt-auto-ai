import os
import subprocess
import re
import shutil
import tempfile


def _get_duration(path: str) -> float:
    """ffprobe se file ki exact duration seconds mein lo."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30
        )
        val = result.stdout.strip()
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def create_shorts_video(item_id: str, images: list, audio_path: str, title: str, output_dir: str) -> str:
    output_video = os.path.join(output_dir, "shorts_video.mp4")

    clips = [img for img in images if os.path.exists(img)]
    if not clips:
        print("  [Video] Koi valid image nahi mili.")
        return ""

    # Audio duration pehle lo — video usi pe fit hoga
    audio_dur = _get_duration(audio_path) if (audio_path and os.path.exists(audio_path)) else 0.0
    if audio_dur > 0:
        print(f"  [Video] 🎙️ Audio duration: {audio_dur:.1f}s — video isi pe fit hoga")

    n = len(clips)
    fps = 30

    # Har clip ki duration = audio ko equally distribute karo
    # Agar audio nahi hai toh 8s default
    if audio_dur > 0:
        # Xfade overlap = 1s, total video = n*seg - (n-1)*1
        # audio_dur = n*seg - (n-1)  =>  seg = (audio_dur + n - 1) / n
        seg_dur = max(4, round((audio_dur + n - 1) / n))
    else:
        seg_dur = 8

    fps = 24  # ✅ Memory fix: 30→24 fps (YouTube Shorts ke liye kaafi, ~20% less memory)

    print(f"  [Video] {n} images × {seg_dur}s per clip — Ken Burns effect...")
    clip_files = []

    for i, img_path in enumerate(clips):
        clip_out = os.path.join(output_dir, f"_clip_{i}.mp4")
        zoom_in = (i % 2 == 0)
        ok = _make_ken_burns_clip(img_path, clip_out, seg_dur, fps, zoom_in)
        if ok:
            clip_files.append(clip_out)
            print(f"  [Video] ✅ Clip {i+1}/{n} ready ({'zoom-in' if zoom_in else 'zoom-out'})")
        else:
            print(f"  [Video] ⚠️ Clip {i+1} Ken Burns fail — static fallback...")
            ok2 = _make_static_clip(img_path, clip_out, seg_dur, fps)
            if ok2:
                clip_files.append(clip_out)
        # ✅ Memory fix: image use ho gayi, delete karo — RAM free karo
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except Exception:
            pass

    if not clip_files:
        print("  [Video] Koi clip nahi bana.")
        return ""

    print(f"  [Video] {len(clip_files)} clips ko xfade se join kar raha hoon...")

    if len(clip_files) == 1:
        raw_video = clip_files[0]
    else:
        merged = os.path.join(output_dir, "_merged.mp4")
        ok = _xfade_merge(clip_files, merged, fps, seg_dur, xfade_dur=1)
        if ok:
            raw_video = merged
        else:
            print("  [Video] Xfade fail — simple concat fallback...")
            raw_video = _concat_clips(clip_files, os.path.join(output_dir, "_raw.mp4"))

    if not raw_video or not os.path.exists(raw_video):
        print("  [Video] Video merge fail.")
        return ""

    final = _add_audio(raw_video, audio_path, output_video, audio_dur)

    if final and os.path.exists(final):
        _cleanup_temp_clips(output_dir)
        size_mb = os.path.getsize(output_video) / (1024 * 1024)
        print(f"  [Video] ✅ Final video ready: {output_video} ({size_mb:.1f} MB)")
        return output_video

    return ""


def _make_ken_burns_clip(img_path: str, out_path: str, duration: int, fps: int, zoom_in: bool) -> bool:
    frames = duration * fps

    if zoom_in:
        zoom_expr = "min(zoom+0.0015,1.3)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    else:
        zoom_expr = "if(eq(on,1),1.3,max(zoom-0.0015,1.001))"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    # ✅ Memory fix: 1080x1920 scale ONLY (no 4K intermediate — was killing 512MB RAM)
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"setsar=1,"
        f"zoompan=z='{zoom_expr}':d={frames}:x='{x_expr}':y='{y_expr}':s=1080x1920:fps={fps},"
        f"trim=duration={duration},"
        f"setpts=PTS-STARTPTS"
    )

    cmd = [
        "ffmpeg", "-y",
        "-threads", "2",                  # ✅ Memory fix: thread limit
        "-loop", "1", "-t", str(duration + 2), "-i", img_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",            # ✅ Memory fix: was 'medium'
        "-crf", "26",                     # ✅ Memory fix: was '18' (good quality, much less RAM)
        "-profile:v", "baseline",         # ✅ Memory fix: simpler profile
        "-level:v", "4.0",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        "-r", str(fps),
        "-an",
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        print(f"    zoompan error: {result.stderr[-300:]}")
        return False
    return os.path.exists(out_path) and os.path.getsize(out_path) > 1000


def _make_static_clip(img_path: str, out_path: str, duration: int, fps: int) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-threads", "2",
        "-loop", "1", "-t", str(duration), "-i", img_path,
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={fps}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "26",
        "-profile:v", "baseline",
        "-level:v", "4.0",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        "-an",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0


def _xfade_merge(clip_files: list, out_path: str, fps: int, seg_dur: int, xfade_dur: int = 1) -> bool:
    n = len(clip_files)

    cmd = ["ffmpeg", "-y", "-threads", "2"]
    for cf in clip_files:
        cmd += ["-i", cf]

    parts = []

    if n == 2:
        offset = seg_dur - xfade_dur
        fc = f"[0:v][1:v]xfade=transition=fade:duration={xfade_dur}:offset={offset}[vout]"
        cmd += ["-filter_complex", fc, "-map", "[vout]"]
    else:
        offset0 = seg_dur - xfade_dur
        parts.append(f"[0:v][1:v]xfade=transition=fade:duration={xfade_dur}:offset={offset0}[xf1]")
        prev = "xf1"
        for i in range(2, n):
            offset = i * (seg_dur - xfade_dur)
            label = "vout" if i == n - 1 else f"xf{i}"
            parts.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={xfade_dur}:offset={offset}[{label}]")
            prev = label
        fc = ";".join(parts)
        cmd += ["-filter_complex", fc, "-map", "[vout]"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "veryfast",      # ✅ Memory fix: was 'medium'
        "-crf", "26",               # ✅ Memory fix: was '18'
        "-profile:v", "baseline",   # ✅ Memory fix: was 'high'
        "-level:v", "4.0",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        "-an",
        out_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"    xfade error: {result.stderr[-400:]}")
        return False
    return os.path.exists(out_path) and os.path.getsize(out_path) > 1000


def _concat_clips(clip_files: list, out_path: str) -> str:
    concat_txt = out_path.replace(".mp4", "_concat.txt")
    with open(concat_txt, "w") as f:
        for cf in clip_files:
            f.write(f"file '{os.path.abspath(cf)}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c:v", "copy", "-an",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return out_path if (result.returncode == 0 and os.path.exists(out_path)) else ""


def _add_audio(video_path: str, audio_path: str, out_path: str, audio_dur: float = 0.0) -> str:
    """
    Audio ko video pe properly merge karo.
    - Audio duration ke barabar video trim/extend hogi
    - Koi bhi filter buffering issue nahi hoga
    - End mein silence nahi hogi
    """
    if not audio_path or not os.path.exists(audio_path):
        shutil.copy2(video_path, out_path)
        return out_path

    # Exact durations pata karo
    if audio_dur <= 0:
        audio_dur = _get_duration(audio_path)
    video_dur = _get_duration(video_path)

    print(f"  [Audio] 📏 Video: {video_dur:.1f}s | Audio: {audio_dur:.1f}s")

    if audio_dur <= 0:
        # Audio duration nahi mili — simple copy
        shutil.copy2(video_path, out_path)
        return out_path

    # ── STRATEGY: Video ko audio duration pe set karo ──────────────────
    # Agar video chhota hai → last frame loop karo
    # Agar video bada hai  → trim karo
    # `-shortest` bilkul nahi — explicit -t use karo
    # ────────────────────────────────────────────────────────────────────

    target = audio_dur  # Video aur audio dono isi pe khatam honge

    if video_dur < audio_dur - 0.5:
        # Video chhota hai — last frame extend karo (tpad filter)
        print(f"  [Audio] 🔁 Video chhota ({video_dur:.1f}s) — last frame extend kar raha hoon...")
        extended = out_path.replace(".mp4", "_extended.mp4")
        extra = audio_dur - video_dur + 1.0
        cmd_ext = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"tpad=stop_mode=clone:stop_duration={extra:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-an",
            extended
        ]
        r = subprocess.run(cmd_ext, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and os.path.exists(extended):
            video_path = extended
            video_dur = _get_duration(video_path)
            print(f"  [Audio] ✅ Extended video: {video_dur:.1f}s")

    # ── Audio merge — clean aur artifact-free ──────────────────────────
    # Sirf volume normalize + end mein 0.4s fade-out
    # highpass/lowpass/acompressor hata diye — yahi beep/ringing karte the
    fade_start = max(0.0, target - 0.4)
    audio_filter = (
        f"volume=1.8,"
        f"afade=t=out:st={fade_start:.3f}:d=0.4"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-af", audio_filter,
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-t", f"{target:.3f}",
        "-movflags", "+faststart",
        out_path
    ]

    print("  [Audio] 🎚️ Audio merge ho raha hai (clean — fade-out only)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if result.returncode == 0 and os.path.exists(out_path):
        final_dur = _get_duration(out_path)
        print(f"  [Audio] ✅ Final video duration: {final_dur:.1f}s — audio fully synced!")
        # Extended temp cleanup
        if "_extended.mp4" in video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass
        return out_path

    # ── Ultra simple fallback — koi filter nahi ────────────────────────
    print("  [Audio] ⚠️ Filter fail — no-filter fallback...")
    cmd2 = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-t", f"{target:.3f}",
        "-movflags", "+faststart",
        out_path
    ]
    result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=180)
    if result2.returncode == 0:
        final_dur = _get_duration(out_path)
        print(f"  [Audio] ✅ Fallback OK — {final_dur:.1f}s")
        return out_path

    shutil.copy2(video_path, out_path)
    return out_path


def _concat_fallback(clip_files: list, audio_path: str, out_path: str) -> str:
    raw = _concat_clips(clip_files, out_path.replace(".mp4", "_raw.mp4"))
    if raw:
        return _add_audio(raw, audio_path, out_path)
    return ""


def _cleanup_temp_clips(output_dir: str):
    for fname in os.listdir(output_dir):
        if (fname.startswith("_clip_") or
                fname in ("_merged.mp4", "_raw.mp4", "_extended.mp4") or
                fname.endswith("_concat.txt")):
            try:
                os.remove(os.path.join(output_dir, fname))
            except Exception:
                pass
