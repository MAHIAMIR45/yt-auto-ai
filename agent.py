import os
import json
import requests
import re
from datetime import datetime


# ── Cloudflare Workers AI credentials ──────────────────────────────────────
def _load_cf_creds():
    account_id = os.environ.get("CF_ACCOUNT_ID", "")
    api_token  = os.environ.get("CF_API_TOKEN", "")
    if not account_id or not api_token:
        try:
            with open(os.path.join("data", "cf_creds.json"), "r") as f:
                saved = json.load(f)
            account_id = account_id or saved.get("account_id", "")
            api_token  = api_token  or saved.get("api_token", "")
            if account_id:
                os.environ["CF_ACCOUNT_ID"] = account_id
            if api_token:
                os.environ["CF_API_TOKEN"] = api_token
        except Exception:
            pass
    return account_id, api_token


CF_ACCOUNT_ID, CF_API_TOKEN = _load_cf_creds()

CF_FREE_MODELS = [
    "@cf/meta/llama-3.1-8b-instruct",
    "@cf/meta/llama-3.2-3b-instruct",
    "@cf/mistral/mistral-7b-instruct-v0.1",
    "@cf/google/gemma-7b-it",
    "@cf/qwen/qwen1.5-7b-chat-awq",
    "@cf/microsoft/phi-2",
]

SYSTEM_PROMPT = """You are a world-class YouTube Shorts viral growth strategist and SEO expert. Your SOLE job is to maximize views, clicks, and watch time for every video. You know exactly how the YouTube algorithm works.

TODAY'S DATE: {current_date}
CURRENT YEAR: {current_year}
IMPORTANT: Always use the correct year {current_year} in titles, tags, and descriptions — never use any past year.

TRENDING_TOPIC: "{trending_topic}"

### YOUR TRAFFIC MAXIMIZATION RULES:

#### TITLE FORMULA (most important — decides 80% of clicks):
- Length: 40-55 characters MAXIMUM (longer titles get cut off on mobile)
- MUST use one of these proven viral structures:
  * "This [topic] SHOCKED Everyone..." (curiosity gap)
  * "Nobody Knew This About [topic]" (exclusivity)
  * "The Truth About [topic] EXPOSED" (controversy)
  * "[Number] Seconds That Changed [topic] Forever" (specificity)
  * "Why [topic] Has Everyone Talking" (social proof)
  * "[topic] Just Changed Everything..." (urgency)
- ALWAYS end with "..." to create open loops in viewer's brain
- Use ALL CAPS on ONE power word only: SHOCKED, EXPOSED, REVEALED, INSANE, WILD
- Add exactly 2 hashtags at end: one broad (#shorts) one topic-specific

#### DESCRIPTION FORMULA (drives SEO and suggested video traffic):
Line 1: Restate the hook as a question — makes people read more
Line 2-3: 2 sentences with high-search keywords naturally embedded
Line 4: "Watch till the end — you won't believe what happens next."
Line 5-6: 3 related questions people search on YouTube (drives suggested traffic)
Line 7: Call to action: "Follow for daily [topic] updates you won't find anywhere else."
Blank line, then: 25-30 hashtags in this order:
  - 5 MEGA hashtags (100M+ views): #shorts #viral #trending #fyp #foryou
  - 5 LARGE hashtags (10M+ views): topic-category tags
  - 10 MEDIUM hashtags (1M-10M): specific topic tags  
  - 5 NICHE hashtags (under 1M): very specific long-tail tags
  - 5 TRENDING hashtags: current trending tags related to topic

#### TAGS ARRAY (YouTube backend search — 30 tags):
Mix: broad terms + specific terms + question phrases + trending phrases
Example pattern: ["topic keyword", "topic news", "topic 2025", "what happened to topic",
"topic explained", "topic shorts", "topic viral", "shocking topic", ...]

### OUTPUT: Reply ONLY with raw valid JSON. No markdown, no code blocks, no explanation.

{
    "trend_analysis": {
        "virality_score_1_to_10": 9,
        "target_upload_hour_est": 12,
        "scheduling_reason": "Specific reason this time slot maximizes views for this trend type"
    },
    "youtube_metadata": {
        "title": "Apply TITLE FORMULA above. 40-55 chars. ONE power word in CAPS. End with ... Add 2 hashtags.",
        "description": "Apply DESCRIPTION FORMULA above. Min 150 words. Include 25-30 hashtags at end.",
        "tags": ["30 tags as JSON array — mix of broad, specific, questions, trending — NO comma strings"]
    },
    "production_assets": {
        "voiceover_script": "Exactly 55 seconds when read at normal speed. FIRST sentence: shocking fact or stat that stops scrolling — no hello, no welcome, no today. Use short punchy sentences 6-10 words each. Build suspense. Use rhetorical questions. End with a revelation. Plain ASCII only — no brackets, no dashes, no ellipsis, no emojis.",
        "image_prompts": [
            "SCENE 1 HOOK: Jaw-dropping opening visual SPECIFIC to this exact topic. Include: exact subject description, lighting (golden hour / stormy / neon city night / harsh spotlight), camera angle (extreme close-up / low angle hero shot / aerial), color mood. Suffix: ultra photorealistic, RED cinema camera, 8K, anamorphic bokeh, vertical 9:16, no text no watermark no letters",
            "SCENE 2 CONTEXT: Different angle expanding the story. Specific environmental details tied to topic. Suffix: hyper-realistic, cinematic Kodak color grade, volumetric light rays, vertical 9:16, no text no watermark",
            "SCENE 3 TENSION: Peak dramatic moment — intense expression or stunning visual reveal. Suffix: DSLR photorealistic, f/1.4 shallow depth, dramatic rim lighting, vertical 9:16, no text no watermark",
            "SCENE 4 DETAIL: Key close-up detail or evidence shot proving the story. Macro or investigative style. Suffix: ultra HD, pin-sharp professional lighting, vertical 9:16, no text no watermark",
            "SCENE 5 SCALE: Epic wide shot showing full scope and scale of topic. Aerial or sweeping landscape. Suffix: cinematic wide angle, dramatic storm clouds or golden sunset, hyper-realistic, vertical 9:16, no text no watermark",
            "SCENE 6 EMOTION: Human face or hands showing genuine emotion — shock, awe, grief, joy. Intimate portrait. Suffix: photorealistic, professional rim lighting, shallow bokeh background, film grain, vertical 9:16, no text no watermark",
            "SCENE 7 FINALE: The most powerful, memorable image of the video. Grand, epic, unforgettable. Suffix: cinematic concept art meets photorealism, award-winning composition, perfect dramatic lighting, vertical 9:16, no text no watermark no letters"
        ]
    }
}

### ABSOLUTE RULES:
1. Title MUST be under 55 characters — count every character
2. Description MUST have minimum 25 hashtags at the end
3. Tags MUST be a JSON array of 25-30 strings — never a comma-separated single string
4. Image prompts MUST be specific to THIS topic — never generic placeholders
5. Script MUST start with a shocking fact — never with greetings
6. Every hashtag in description must start with # symbol"""


def generate_autonomous_package(trending_topic: str, model: str = "@cf/meta/llama-3.1-8b-instruct") -> dict:
    # Fresh load every time (UI se update ke baad bhi kaam kare)
    account_id, api_token = _load_cf_creds()
    if not account_id or not api_token:
        raise ValueError(
            "Cloudflare credentials set nahi hain! "
            "Settings ⚙️ mein jaake CF Account ID aur API Token save karo."
        )

    # CF model prefix ensure karo
    if not model.startswith("@cf/"):
        model = "@cf/meta/llama-3.1-8b-instruct"

    now = datetime.utcnow()
    filled_prompt = (SYSTEM_PROMPT
                     .replace("{trending_topic}", trending_topic)
                     .replace("{current_year}", str(now.year))
                     .replace("{current_date}", now.strftime("%B %d, %Y")))

    user_msg = (
        f"Today is {now.strftime('%B %d, %Y')}. "
        f"Generate a viral YouTube Shorts package for this trending topic. "
        f"Use year {now.year} everywhere. Output raw JSON only: {trending_topic}"
    )

    payload = {
        "messages": [
            {"role": "system", "content": filled_prompt},
            {"role": "user",   "content": user_msg}
        ],
        "max_tokens": 4000,
        "temperature": 0.75
    }

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        raise Exception(f"Cloudflare API Error {response.status_code}: {response.text[:300]}")

    res_json = response.json()
    if not res_json.get("success", False):
        errors = res_json.get("errors", [])
        raise Exception(f"Cloudflare Error: {errors}")

    # Cloudflare different models alag format dete hain — sab handle karo
    result = res_json.get("result", {})
    if isinstance(result, str):
        raw = result
    elif isinstance(result, dict):
        # Standard: result.response = string
        resp = result.get("response", "")
        if isinstance(resp, str):
            raw = resp
        elif isinstance(resp, dict):
            # Kabhi kabhi nested dict hota hai
            raw = resp.get("text", "") or resp.get("content", "") or json.dumps(resp)
        else:
            # Fallback: poora result JSON kar do aur us mein se JSON dhundo
            raw = json.dumps(result)
    else:
        raw = str(result)
    raw = raw.strip()

    # Code block cleanup
    raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    # Invalid control characters fix (Cloudflare models kabhi kabhi raw \n \t inject karte hain)
    raw = re.sub(r'(?<!\\)[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', raw)
    # JSON string ke andar literal newlines/tabs ko escape karo
    def _fix_json_strings(s):
        result = []
        in_str = False
        i = 0
        while i < len(s):
            c = s[i]
            if c == '\\' and in_str:
                result.append(c)
                i += 1
                if i < len(s):
                    result.append(s[i])
                i += 1
                continue
            if c == '"':
                in_str = not in_str
                result.append(c)
            elif in_str and c == '\n':
                result.append('\\n')
            elif in_str and c == '\r':
                result.append('\\r')
            elif in_str and c == '\t':
                result.append('\\t')
            else:
                result.append(c)
            i += 1
        return ''.join(result)

    raw = _fix_json_strings(raw)

    package = json.loads(raw)

    tags = package.get("youtube_metadata", {}).get("tags", [])
    if isinstance(tags, str):
        package["youtube_metadata"]["tags"] = [t.strip() for t in tags.split(",")]

    return package


def get_available_free_models() -> list:
    return CF_FREE_MODELS
