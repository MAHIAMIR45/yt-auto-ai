import sys
import json
import argparse
import os

from agent import generate_autonomous_package, get_available_free_models
from trends import fetch_trending_topics, get_single_topic
from queue_manager import save_to_queue, get_queue_status
from scheduler import get_est_time_info
from output_generator import save_package_to_file, generate_images_pollinations, generate_voiceover_edgetts
from video_editor import create_shorts_video


BANNER = """
╔══════════════════════════════════════════════════════════╗
║     🎬 YouTube Shorts Autonomous AI Producer v2.0        ║
║     OpenRouter (FREE) + Pollinations + TTS + FFmpeg      ║
╚══════════════════════════════════════════════════════════╝
"""


def run_single(topic=None, generate_images=False, generate_audio=False,
               make_video=False, model="google/gemini-2.5-flash"):
    print(BANNER)

    time_info = get_est_time_info()
    print(f"⏰ Current Time : {time_info['est_time']}")
    print(f"📊 Next Peak    : {time_info['next_peak_slot']}:00 EST")
    print("─" * 60)

    trending_topic = get_single_topic(topic)
    print(f"\n🔥 Topic: '{trending_topic}'")
    print(f"🤖 Model: {model}")
    print("─" * 60)

    print("\n[1/5] 🤖 AI Agent se package generate ho raha hai...")
    ai_package = generate_autonomous_package(trending_topic, model=model)

    ta = ai_package["trend_analysis"]
    yt = ai_package["youtube_metadata"]
    pa = ai_package["production_assets"]

    print(f"\n✅ AI Package Ready!")
    print(f"   🎯 Virality  : {ta['virality_score_1_to_10']}/10")
    print(f"   ⏰ Upload     : {ta['target_upload_hour_est']}:00 EST")
    print(f"   📝 Reason    : {ta['scheduling_reason']}")
    print(f"   📺 Title     : {yt['title']}")

    print("\n[2/5] 💾 Database queue me save kar raha hoon...")
    item_id = save_to_queue(trending_topic, ai_package)

    print("\n[3/5] 📁 Output files save kar raha hoon...")
    import re
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
    folder = os.path.join("output", safe_id)
    os.makedirs(folder, exist_ok=True)
    save_package_to_file(item_id, ai_package, trending_topic)

    images = []
    audio_path = ""

    if generate_images or make_video:
        print("\n[4/5] 🖼️  Pollinations AI se images download ho rahi hain...")
        prompts = pa.get("image_prompts", [])
        images = generate_images_pollinations(prompts, item_id)
        print(f"   ✅ {len(images)} images ready")
    else:
        print("\n[4/5] ⏭️  Images skip (--images ya --video use karo)")

    if generate_audio or make_video:
        print("\n[4b] 🎙️  edge-tts se voiceover generate ho raha hai...")
        script = pa.get("voiceover_script", "")
        audio_path = generate_voiceover_edgetts(script, item_id)
    else:
        print("      ⏭️  Audio skip")

    video_path = ""
    if make_video:
        print("\n[5/5] 🎬 FFmpeg se video edit ho raha hai...")
        title = yt.get("title", "")
        video_path = create_shorts_video(item_id, images, audio_path, title, folder)
    else:
        print("\n[5/5] ⏭️  Video skip (--video use karo full video ke liye)")

    print("\n" + "═" * 60)
    print("🎉 COMPLETE!")
    print(f"   📁 ID    : {item_id}")
    print(f"   📂 Folder: output/{safe_id}/")
    if video_path:
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"   🎬 Video : shorts_video.mp4 ({size_mb:.1f} MB)")
    print("─" * 60)
    print("\n📋 Script Preview:")
    print(f"   {pa.get('voiceover_script','')[:200]}...")
    print("═" * 60)

    return item_id, ai_package


def run_batch(count=3, make_video=False, model="google/gemini-2.5-flash"):
    print(BANNER)
    print(f"🚀 Batch Mode: {count} topics")
    print("─" * 60)

    topics = fetch_trending_topics(limit=count)
    print(f"\n🔥 Trending Topics ({len(topics)}):")
    for i, t in enumerate(topics, 1):
        print(f"   {i}. {t}")

    results = []
    for i, topic in enumerate(topics, 1):
        print(f"\n{'═'*60}")
        print(f"[{i}/{len(topics)}] → '{topic}'")
        try:
            item_id, _ = run_single(topic=topic, make_video=make_video, model=model)
            results.append({"topic": topic, "item_id": item_id, "status": "success"})
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({"topic": topic, "status": "failed", "error": str(e)})

    ok = sum(1 for r in results if r["status"] == "success")
    print(f"\n{'═'*60}")
    print(f"✅ Batch Done: {ok}/{len(results)} successful")
    return results


def show_queue():
    print(BANNER)
    s = get_queue_status()
    print(f"📊 QUEUE STATUS")
    print(f"{'─'*60}")
    print(f"   Queued  : {s['total_queued']}")
    print(f"   Uploaded: {s['total_uploaded']}")
    print(f"   Failed  : {s['total_failed']}")
    if s["queue_items"]:
        print(f"\n📋 ITEMS:")
        for item in s["queue_items"]:
            print(f"   [{item['upload_hour_est']:02d}:00 EST] ⭐{item['virality']}/10  {item['topic']}")
            print(f"            {item['title']}")
    else:
        print("\n   Queue khaali hai.")


def main():
    parser = argparse.ArgumentParser(description="YT Shorts AI Producer")
    sub = parser.add_subparsers(dest="command")

    rp = sub.add_parser("run", help="Single topic process karo")
    rp.add_argument("--topic", type=str, default=None)
    rp.add_argument("--images", action="store_true", help="Images generate karo")
    rp.add_argument("--audio", action="store_true", help="Voiceover generate karo")
    rp.add_argument("--video", action="store_true", help="Full video banao (images+audio+ffmpeg)")
    rp.add_argument("--model", type=str, default="google/gemini-2.5-flash")

    bp = sub.add_parser("batch", help="Multiple topics")
    bp.add_argument("--count", type=int, default=3)
    bp.add_argument("--video", action="store_true")
    bp.add_argument("--model", type=str, default="google/gemini-2.5-flash")

    sub.add_parser("queue", help="Queue status")
    sub.add_parser("web", help="Web dashboard start karo")
    sub.add_parser("models", help="Free models list")

    args = parser.parse_args()

    if args.command == "run":
        run_single(
            topic=args.topic,
            generate_images=args.images,
            generate_audio=args.audio,
            make_video=args.video,
            model=args.model
        )
    elif args.command == "batch":
        run_batch(count=args.count, make_video=args.video, model=args.model)
    elif args.command == "queue":
        show_queue()
    elif args.command == "web":
        from app import app
        print(BANNER)
        print("🌐 Web Dashboard: http://0.0.0.0:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)
    elif args.command == "models":
        print("\n🤖 Free Models:")
        for m in get_available_free_models():
            print(f"   • {m}")
    else:
        parser.print_help()
        print("\n💡 Commands:")
        print("   python main.py run --video          # Full video pipeline")
        print("   python main.py run --topic 'Tesla'  # Custom topic")
        print("   python main.py batch --count 3      # 3 topics batch")
        print("   python main.py queue                # Queue dekho")
        print("   python main.py web                  # Web dashboard")


if __name__ == "__main__":
    main()
