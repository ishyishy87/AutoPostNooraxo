import os
import re
import random
import tempfile
import pandas as pd
from datetime import datetime
import requests


# ================= VIDEO IMPORTS =================

from moviepy.editor import (
    ImageClip,
    concatenate_videoclips,
    AudioFileClip
)

from PIL import Image, ImageDraw, ImageFont

# ================= CONFIG =================

PRODUCTS_FILE = "products.csv"
MEMORY_FILE = "memory.csv"
LOG_FILE = "run_log.txt"
RUN_LOCK_FILE = "run_lock.txt"

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

# ================= LOGGING =================

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {msg}\n")

# ================= SAFETY =================

def already_ran_today():
    if not os.path.exists(RUN_LOCK_FILE):
        return False
    return open(RUN_LOCK_FILE).read().strip() == str(datetime.now().date())

def mark_run():
    with open(RUN_LOCK_FILE, "w") as f:
        f.write(str(datetime.now().date()))

# ================= MEMORY =================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        df = pd.DataFrame(columns=[
            "product_id","status","price","post_url",
            "likes","comments","shares","score","date"
        ])
        df.to_csv(MEMORY_FILE, index=False)
        return df
    return pd.read_csv(MEMORY_FILE)

def save_memory(df):
    df.to_csv(MEMORY_FILE, index=False)

# ================= CSV ENGINE =================

def normalize_columns(df):
    df.columns = df.columns.str.strip().str.lower()
    return df

def map_columns(df):
    mapping = {}
    for col in df.columns:
        if col in ["title", "product title", "name", "product_name"]:
            mapping["title"] = col
        elif col in ["price", "cost", "amount", "sale price"]:
            mapping["price"] = col
        elif col in ["sku", "id", "product id", "product_id"]:
            mapping["sku"] = col
        elif col in ["image src", "image", "image_url", "img", "photo"]:
            mapping["image"] = col
    return mapping

def safe_get(row, col_map, key, default=""):
    col = col_map.get(key)
    if not col:
        return default
    val = row.get(col, default)
    if pd.isna(val):
        return default
    return val

# ================= SCORING =================

def score_product(row, col_map):
    score = 0
    title = str(safe_get(row, col_map, "title", "")).lower()

    if any(x in title for x in ["new", "hot", "sale", "best"]):
        score += 10

    if safe_get(row, col_map, "image"):
        score += 5

    try:
        price = float(re.sub(r"[^\d.]", "", str(safe_get(row, col_map, "price", 0))) or 0)
        if price < 50:
            score += 10
        elif price < 100:
            score += 5
    except:
        pass

    return score

# ================= PROFIT AI =================

def profit_optimizer(price, score):
    base = float(re.sub(r"[^\d.]", "", str(price)) or 0)

    multiplier = 1.5  # base markup

    # PROFIT-FIRST STRATEGY
    if score >= 80:
        multiplier += 0.35
        strategy = "WINNER_SCALE"
    elif score >= 60:
        multiplier += 0.25
        strategy = "STRONG_PROFIT"
    elif score >= 40:
        multiplier += 0.15
        strategy = "BALANCED_GROWTH"
    elif score >= 25:
        multiplier += 0.30
        strategy = "RISK_PROFIT"
    else:
        multiplier += 0.45
        strategy = "MAX_MARGIN_LOW_DEMAND"

    multiplier = max(1.2, min(multiplier, 2.5))

    return base * multiplier, strategy

def adjust_price(price, score):
    final_price, _ = profit_optimizer(price, score)

    final_price = int(final_price)

    # psychological pricing
    if final_price > 100:
        final_price = (final_price // 100) * 100 - 1
    elif final_price > 10:
        final_price = (final_price // 10) * 10 - 1

    return final_price

# ================= LOCAL AI VIRAL ENGINE =================
# No OpenAI/API required.
# Product title remains unchanged from products.csv.
# Everything else is generated locally through keyword detection, templates, randomization, and score-based selection.

AI_ENABLED = True

CATEGORY_KEYWORDS = {
    "fashion": ["shirt", "dress", "hoodie", "jeans", "watch", "shoes", "kurti", "bag", "wallet", "sandal", "jacket", "fashion"],
    "beauty": ["cream", "serum", "face", "skin", "makeup", "lipstick", "beauty", "hair", "shampoo", "mask", "oil"],
    "tech": ["led", "usb", "speaker", "earbuds", "charger", "mobile", "laptop", "bluetooth", "wireless", "phone", "gadget"],
    "home": ["kitchen", "knife", "cook", "pan", "home", "organizer", "storage", "cleaner", "lamp", "decor"],
    "fitness": ["gym", "fitness", "protein", "exercise", "yoga", "workout", "sports", "training"],
    "baby": ["baby", "kids", "toy", "child", "children", "mom", "school"],
    "auto": ["car", "bike", "motor", "vehicle", "holder", "cover", "light"],
}

CATEGORY_EMOJIS = {
    "fashion": ["✨", "🔥", "👗", "🛍️"],
    "beauty": ["✨", "💫", "🌸", "💄"],
    "tech": ["⚡", "🔥", "📱", "🚀"],
    "home": ["🏠", "✨", "🛒", "👌"],
    "fitness": ["💪", "🔥", "⚡", "🏋️"],
    "baby": ["🧸", "💕", "✨", "👶"],
    "auto": ["🚗", "⚡", "🔥", "👌"],
    "general": ["🔥", "⚡", "✨", "🛒"],
}

VIRAL_HOOKS = {
    "high": [
        "This one is getting attention fast",
        "Customers are noticing this deal",
        "A smart pick before it sells out",
        "One of today’s strongest picks",
        "This product has viral potential",
    ],
    "medium": [
        "A useful find at a smart price",
        "Simple, practical, and worth checking",
        "This could be your next favorite item",
        "A trending pick for daily use",
        "Good value, clean look, smart choice",
    ],
    "low": [
        "Limited-time value pick",
        "Budget-friendly choice for today",
        "A smart deal for quick buyers",
        "Useful item, simple price, easy order",
        "Today’s clean and practical pick",
    ],
}

BENEFIT_LINES = {
    "fashion": [
        "Upgrade your look without overthinking it.",
        "Easy to style, easy to love.",
        "Made for everyday confidence.",
        "Perfect for casual and smart looks.",
    ],
    "beauty": [
        "Add a fresh touch to your routine.",
        "Simple care, visible confidence.",
        "A daily-use pick for glow lovers.",
        "Designed for a neat and fresh feel.",
    ],
    "tech": [
        "Useful, modern, and made for daily convenience.",
        "A smart gadget for smarter routine.",
        "Simple tech that makes life easier.",
        "Practical choice for daily use.",
    ],
    "home": [
        "Make your home routine easier and cleaner.",
        "A practical pick for everyday home use.",
        "Smart utility for organized living.",
        "Useful design for daily convenience.",
    ],
    "fitness": [
        "Keep your routine active and focused.",
        "A smart pick for fitness-minded buyers.",
        "Simple support for daily performance.",
        "Made for active lifestyle needs.",
    ],
    "baby": [
        "A caring pick for little ones.",
        "Useful, simple, and family friendly.",
        "A smart choice for parents.",
        "Made with everyday family needs in mind.",
    ],
    "auto": [
        "A practical upgrade for your ride.",
        "Useful accessory for daily travel.",
        "Simple utility for car and bike lovers.",
        "Smart choice for everyday driving.",
    ],
    "general": [
        "Useful, affordable, and easy to order.",
        "A smart choice for daily needs.",
        "Simple product, strong value.",
        "Good deal for quick buyers.",
    ],
}

CTA_LINES = [
    "Inbox now to order.",
    "Message us before stock runs out.",
    "DM to confirm availability.",
    "Order through inbox today.",
    "Send message for quick order.",
    "Cash on Delivery available — inbox now.",
]

URGENCY_LINES = [
    "Limited stock available.",
    "Today’s deal only while available.",
    "Fast movers may sell out quickly.",
    "Grab it before the next price update.",
    "Best for quick decision buyers.",
]

COMMON_HASHTAGS = [
    "#ShopNow", "#OnlineShopping", "#Pakistan", "#Deals", "#Trending",
    "#ViralProducts", "#BestDeals", "#Sale", "#Shopping", "#COD",
    "#CashOnDelivery", "#OnlineStore", "#DailyDeals", "#MustHave",
]

CATEGORY_HASHTAGS = {
    "fashion": ["#Fashion", "#Style", "#OOTD", "#FashionSale", "#MensFashion", "#WomensFashion", "#TrendyLook"],
    "beauty": ["#Beauty", "#Skincare", "#Makeup", "#GlowUp", "#BeautyProducts", "#SelfCare"],
    "tech": ["#Gadgets", "#Tech", "#TechDeals", "#Electronics", "#SmartDevices", "#MobileAccessories"],
    "home": ["#HomeEssentials", "#KitchenTools", "#HomeDecor", "#HomeShopping", "#SmartHome", "#UsefulProducts"],
    "fitness": ["#Fitness", "#Workout", "#Gym", "#HealthyLifestyle", "#SportsGear", "#ActiveLife"],
    "baby": ["#BabyCare", "#KidsProducts", "#MomLife", "#BabyProducts", "#Toys", "#FamilyShopping"],
    "auto": ["#CarAccessories", "#BikeAccessories", "#AutoCare", "#VehicleAccessories", "#CarLovers"],
    "general": ["#SmartBuy", "#ValueDeal", "#UsefulFinds", "#EverydayEssentials", "#TrendingNow"],
}

REEL_OVERLAY_PHRASES = {
    "fashion": ["STYLE UPGRADE", "TRENDING LOOK", "LIMITED STOCK"],
    "beauty": ["GLOW PICK", "BEAUTY DEAL", "TRENDING NOW"],
    "tech": ["SMART PICK", "GADGET DEAL", "TECH FIND"],
    "home": ["HOME ESSENTIAL", "USEFUL FIND", "SMART HOME PICK"],
    "fitness": ["ACTIVE PICK", "FITNESS DEAL", "TRAIN SMART"],
    "baby": ["FAMILY PICK", "KIDS FAVORITE", "SMART BUY"],
    "auto": ["AUTO UPGRADE", "RIDE SMART", "USEFUL ACCESSORY"],
    "general": ["HOT DEAL", "SMART BUY", "TRENDING PICK"],
}

def clean_words(text):
    return re.findall(r"[a-zA-Z0-9]+", str(text).lower())

def detect_category(title):
    words = clean_words(title)
    text = " ".join(words)

    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for k in keywords if k in text)

    best = max(scores, key=scores.get) if scores else "general"
    return best if scores.get(best, 0) > 0 else "general"

def score_band(score):
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"

def product_keyword_hashtags(title):
    words = clean_words(title)
    blocked = {
        "with", "and", "for", "the", "new", "best", "sale", "pack",
        "pcs", "piece", "size", "color", "free", "only", "original"
    }

    tags = []
    for w in words:
        if len(w) >= 4 and w not in blocked:
            tag = "#" + w[:1].upper() + w[1:]
            if tag not in tags:
                tags.append(tag)

    random.shuffle(tags)
    return tags[:4]

def ai_hashtags(title, category=None):
    category = category or detect_category(title)

    tags = []
    tags += random.sample(COMMON_HASHTAGS, min(6, len(COMMON_HASHTAGS)))
    tags += random.sample(CATEGORY_HASHTAGS.get(category, CATEGORY_HASHTAGS["general"]), min(4, len(CATEGORY_HASHTAGS.get(category, []))))
    tags += product_keyword_hashtags(title)

    # Deduplicate while preserving random order
    unique = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)

    random.shuffle(unique)
    return " ".join(unique[:14])

def ai_caption(title, price, score):
    category = detect_category(title)
    band = score_band(score)
    emoji = random.choice(CATEGORY_EMOJIS.get(category, CATEGORY_EMOJIS["general"]))

    hook = random.choice(VIRAL_HOOKS[band])
    benefit = random.choice(BENEFIT_LINES.get(category, BENEFIT_LINES["general"]))
    urgency = random.choice(URGENCY_LINES)
    cta = random.choice(CTA_LINES)

    # Title is used exactly as provided from products.csv
    return f"""
{emoji} {hook}

{title}

💸 Price: Rs {price}
🚚 Cash on Delivery Available

{benefit}
{urgency}

📩 {cta}
""".strip()

def ai_reel_caption(title, price, score):
    category = detect_category(title)
    band = score_band(score)
    emoji = random.choice(CATEGORY_EMOJIS.get(category, CATEGORY_EMOJIS["general"]))

    hook = random.choice(VIRAL_HOOKS[band])
    cta = random.choice(CTA_LINES)

    return f"""
{emoji} {hook}

{title}
Rs {price}

🚚 Cash on Delivery
📩 {cta}
""".strip()

def ai_reel_overlay_text(title, price, score):
    category = detect_category(title)
    top_line = random.choice(REEL_OVERLAY_PHRASES.get(category, REEL_OVERLAY_PHRASES["general"]))
    bottom_line = random.choice(["ORDER NOW", "DM TO ORDER", "COD AVAILABLE", "LIMITED OFFER"])

    return {
        "top": top_line,
        "title": str(title),
        "price": f"Rs {price}",
        "bottom": bottom_line,
    }

# Backward-compatible aliases
def caption(title, price, score):
    return ai_caption(title, price, score)

def hashtags(title=""):
    return ai_hashtags(title)

# ================= FACEBOOK =================

def upload_images(image_paths):
    ids = []
    for path in image_paths:
        url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"
        with open(path, "rb") as img:
            r = requests.post(url, files={"source": img}, data={
                "published": "false",
                "access_token": ACCESS_TOKEN
            })
        data = r.json()
        if "id" in data:
            ids.append(data["id"])
        else:
            log(f"Image upload failed for {path}: {data}")
    return ids

def post_carousel(image_ids, caption_text):
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"

    attached = [{"media_fbid": i} for i in image_ids]

    r = requests.post(url, json={
        "message": caption_text,
        "attached_media": attached,
        "access_token": ACCESS_TOKEN
    })

    data = r.json()
    post_id = data.get("id")
    return data, f"https://facebook.com/{post_id}" if post_id else None

def delete_facebook_object(object_id):
    """
    Rollback helper. Deletes a Facebook object if possible.
    Used when carousel succeeds but reel upload fails.
    """

    if not object_id:
        return False

    url = f"https://graph.facebook.com/v18.0/{object_id}"

    try:
        r = requests.delete(url, data={
            "access_token": ACCESS_TOKEN
        })

        data = r.json()
        log(f"Rollback delete response for {object_id}: {data}")

        return data.get("success") is True

    except Exception as e:
        log(f"Rollback delete failed for {object_id}: {e}")
        return False

# ================= IMAGE =================

def download_image(url, pid):
    if not url:
        return None

    fn = f"temp_{pid}.jpg"

    try:
        r = requests.get(url, stream=True, timeout=10)
        if r.status_code != 200:
            log(f"Image download failed: HTTP {r.status_code} | {url}")
            return None

        with open(fn, "wb") as f:
            for c in r.iter_content(1024):
                if c:
                    f.write(c)
        return fn
    except Exception as e:
        log(f"Image download error: {e}")
        return None

# ================= PRODUCT =================

def select_product(df, memory, col_map):
    posted = set(memory["product_id"].astype(str))
    sku_col = col_map.get("sku")

    available = df.copy()
    if sku_col:
        available = df[~df[sku_col].astype(str).isin(posted)]

    if available.empty:
        available = df

    available["score"] = available.apply(lambda x: score_product(x, col_map), axis=1)

    top = available.sort_values("score", ascending=False)

    return top.sample(1).iloc[0]

# ================= REELS VIDEO CONFIG =================

REELS_ENABLED = True

VIDEO_OUTPUT_DIR = "videos"
VIDEO_SIZE = (1080, 1920)   # Vertical Reel format
VIDEO_FPS = 24
IMAGE_DURATION = 2.5        # seconds per image

VIDEO_BG_COLOR = (0, 0, 0)
TEXT_COLOR = "white"
FONT_SIZE_TITLE = 60
FONT_SIZE_PRICE = 80

# ================= ONLINE MUSIC CONFIG =================

MUSIC_ENABLED = True

# Direct downloadable MP3 URLs only.
# Keep royalty-free/open-license tracks you are allowed to use commercially.
OPEN_MUSIC_URLS = [
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-11.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-12.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-13.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-14.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-15.mp3",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-16.mp3",
]

# ================= RANDOM ONLINE MUSIC =================

def download_random_music():
    """
    Download one random online MP3 from OPEN_MUSIC_URLS.
    Returns local temp music path or None.
    """

    if not MUSIC_ENABLED:
        log("Music skipped - disabled")
        return None

    if not OPEN_MUSIC_URLS:
        log("Music skipped - no music URLs configured")
        return None

    music_url = random.choice(OPEN_MUSIC_URLS)
    log(f"Selected online music: {music_url}")

    try:
        r = requests.get(music_url, stream=True, timeout=20)

        if r.status_code != 200:
            log(f"Music download failed: HTTP {r.status_code}")
            return None

        music_path = os.path.join(
            tempfile.gettempdir(),
            f"music_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000,9999)}.mp3"
        )

        with open(music_path, "wb") as f:
            for chunk in r.iter_content(1024):
                if chunk:
                    f.write(chunk)

        log(f"Music downloaded: {music_path}")
        return music_path

    except Exception as e:
        log(f"Music download error: {e}")
        return None

# ================= TEXT DRAW HELPERS =================

def get_font(size):
    font_candidates = [
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    for font in font_candidates:
        try:
            return ImageFont.truetype(font, size)
        except:
            pass

    return ImageFont.load_default()

def draw_centered_text(draw, text, y, font, fill=TEXT_COLOR, max_width=960):
    text = str(text)

    # Wrap text manually
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    line_height = font.size + 10 if hasattr(font, "size") else 30

    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (VIDEO_SIZE[0] - w) // 2

        # shadow
        draw.text((x + 3, y + 3), line, fill="black", font=font)
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height

# ================= REELS IMAGE PREPARATION =================

def prepare_reel_image(image_path, title="", price="", score=0, output_size=VIDEO_SIZE):
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((output_size[0], 1150))

    background = Image.new("RGB", output_size, VIDEO_BG_COLOR)
    draw = ImageDraw.Draw(background)

    overlay = ai_reel_overlay_text(title, price, score)

    top_font = get_font(58)
    title_font = get_font(52)
    price_font = get_font(84)
    bottom_font = get_font(54)

    # Top viral line
    draw_centered_text(draw, overlay["top"], 85, top_font, fill=TEXT_COLOR)

    # Product image centered
    x = (output_size[0] - img.width) // 2
    y = 320 + (850 - img.height) // 2
    background.paste(img, (x, y))

    # Title as-is from CSV
    draw_centered_text(draw, overlay["title"], 1230, title_font, fill=TEXT_COLOR)

    # Price and CTA
    draw_centered_text(draw, overlay["price"], 1500, price_font, fill=TEXT_COLOR)
    draw_centered_text(draw, overlay["bottom"], 1660, bottom_font, fill=TEXT_COLOR)

    prepared_path = f"reel_ready_{os.path.basename(image_path)}"
    background.save(prepared_path)

    return prepared_path

# ================= REELS VIDEO CREATION =================

def create_reel_video(image_files, title, price, score):
    """
    Create vertical reel video from product images.
    All reel overlays are locally AI-generated.
    """

    if not REELS_ENABLED:
        log("Reels video skipped - disabled")
        return None

    if not image_files:
        log("Reels video skipped - no images found")
        return None

    os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

    clips = []

    for img in image_files:
        prepared_img = prepare_reel_image(img, title, price, score)

        clip = (
            ImageClip(prepared_img)
            .set_duration(IMAGE_DURATION)
        )

        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    output_path = os.path.join(
        VIDEO_OUTPUT_DIR,
        f"reel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    )

    # ===== BACKGROUND MUSIC =====

    music_path = download_random_music()

    if music_path:
        try:
            audio = AudioFileClip(music_path)

            if audio.duration > video.duration:
                audio = audio.subclip(0, video.duration)

            video = video.set_audio(audio)
            log(f"Music added to reel video | audio_duration={audio.duration}")

        except Exception as e:
            log(f"Music attach failed: {e}")

    # ===== EXPORT VIDEO =====

    video.write_videofile(
        output_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio=True,
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
        remove_temp=True
    )

    if video.audio:
        log("Final reel has audio before upload")
    else:
        log("WARNING: Final reel has NO audio before upload")

    log(f"Reel video created: {output_path}")

    return output_path

# ================= FACEBOOK REEL UPLOAD =================

def upload_reel_video(video_path, caption_text):
    """
    Upload generated reel/video to Facebook.
    This is separate from existing carousel post logic.
    """

    if not video_path or not os.path.exists(video_path):
        log("Reel upload skipped - video file not found")
        return None

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/videos"

    with open(video_path, "rb") as video:
        r = requests.post(url, files={
            "source": video
        }, data={
            "description": caption_text,
            "access_token": ACCESS_TOKEN
        })

    data = r.json()

    if "id" in data:
        log(f"Reel/video uploaded successfully: {data['id']}")
    else:
        log(f"Reel/video upload failed: {data}")

    return data

# ================= MAIN =================

def main():

    if already_ran_today():
        log("Skipped - already ran")
        return

    df = pd.read_csv(PRODUCTS_FILE)
    df = normalize_columns(df)

    memory = load_memory()
    col_map = map_columns(df)

    product = select_product(df, memory, col_map)

    pid = str(safe_get(product, col_map, "sku")).strip()
    title = safe_get(product, col_map, "title", "No Title")
    price = safe_get(product, col_map, "price", 0)
    img = safe_get(product, col_map, "image")

    score = score_product(product, col_map)
    final_price = adjust_price(price, score)
    category = detect_category(title)

    log(f"Selected {title} | Score {score} | AI Category {category}")

    # ===== IMAGE COLLECTION =====

    image_files = []

    handle_col = "url handle" if "url handle" in df.columns else None
    image_col = col_map.get("image")

    product_rows = pd.DataFrame()

    if handle_col:
        product_rows = df[df[handle_col] == product.get(handle_col)]

    if product_rows.empty and "sku" in df.columns:
        product_rows = df[df["sku"] == pid]

    if "image position" in df.columns:
        product_rows = product_rows.sort_values(by="image position")

    image_urls = product_rows[image_col].dropna().unique().tolist() if image_col else []

    log(f"Found {len(image_urls)} images")

    for i, url in enumerate(image_urls[:4]):
        f = download_image(str(url), f"{pid}_{i}")
        if f:
            image_files.append(f)

    if not image_files:
        f = download_image(img, pid)
        if f:
            image_files.append(f)

    log("Step 1 Completed: Product selected, AI category detected, and images prepared")

    # ===== AI POST CAPTION =====

    cap = ai_caption(title, final_price, score) + "\n\n" + ai_hashtags(title, category)

    log("Step 2 Completed: AI caption, CTA, and hashtags generated")

    # ===== IMAGE UPLOAD =====

    image_ids = upload_images(image_files)

    log(f"Uploaded images: {len(image_ids)}")

    if not image_ids:
        log("Failed: No images uploaded. Posting stopped.")
        return

    # ===== AI REEL VIDEO CREATION =====

    reel_video_path = create_reel_video(image_files, title, final_price, score)

    if not reel_video_path:
        log("Failed: AI reel video creation failed. Posting stopped.")
        return

    log("Step 3 Completed: AI reel video created with generated overlays and random music")

    # ===== FACEBOOK POST + REEL PUBLISH =====

    result, post_url = post_carousel(image_ids, cap)
    post_id = result.get("id") if result else None

    if not post_id:
        log(f"Failed: Facebook carousel post failed: {result}")
        return

    reel_caption_text = (
        ai_reel_caption(title, final_price, score)
        + "\n\n"
        + ai_hashtags(title, category)
    )

    reel_result = upload_reel_video(reel_video_path, reel_caption_text)
    reel_id = reel_result.get("id") if reel_result else None

    if not reel_id:
        log(f"Failed: Reel upload failed: {reel_result}")
        delete_facebook_object(post_id)
        log("Rollback completed: Carousel post deleted because reel failed")
        return

    log("Step 4 Completed: Facebook post and reel published successfully")

    # ===== MEMORY =====

    new_row = pd.DataFrame([{
        "product_id": pid,
        "status": "posted",
        "price": final_price,
        "post_url": post_url,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "score": score,
        "date": str(datetime.now())
    }])

    memory = pd.concat([memory, new_row], ignore_index=True)
    save_memory(memory)

    mark_run()
    log("Step 5 Completed: Published successfully and memory updated")

if __name__ == "__main__":
    main()
