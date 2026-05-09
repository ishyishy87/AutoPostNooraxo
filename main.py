import os
import re
import pandas as pd
from datetime import datetime
import requests


# ================= VIDEO IMPORTS =================

from moviepy.editor import (
    ImageClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip
)

from PIL import Image
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

# ================= CAPTION =================

def caption(title, price, score):
    hook = "🔥 BEST SELLER ALERT!" if score > 70 else "⚡ TRENDING DEAL!" if score > 40 else "🚨 LIMITED OFFER!"

    return f"""
{hook}

🔥 {title}
💸 Price: {price}

🚚 Cash on Delivery Available
📩 Order Now via Inbox
""".strip()

def hashtags():
    return "#Sale #Pakistan #ShopNow #Deals #OnlineShopping"

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

# ================= IMAGE =================

def download_image(url, pid):
    if not url:
        return None

    fn = f"temp_{pid}.jpg"

    try:
        r = requests.get(url, stream=True, timeout=10)
        with open(fn, "wb") as f:
            for c in r.iter_content(1024):
                f.write(c)
        return fn
    except:
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

    log(f"Selected {title} | Score {score}")

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

    # ===== POST =====

    cap = caption(title, final_price, score) + "\n\n" + hashtags()

    image_ids = upload_images(image_files)

    log(f"Uploaded images: {len(image_ids)}")

    result, post_url = post_carousel(image_ids, cap)

    # ===== REEL VIDEO CREATION =====

    reel_video_path = create_reel_video(image_files, title, final_price)

    if reel_video_path:

        log(f"Reel ready for upload: {reel_video_path}")

        reel_caption = (
            caption(title, final_price, score)
            + "\n\n"
            + REEL_HASHTAGS
        )

        upload_reel_video(reel_video_path, reel_caption)
        
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
    log("Posted successfully")

# ================= REELS VIDEO PROBLEM STATEMENT =================
"""
PROBLEM STATEMENT:

The current automation creates a Facebook carousel post using product images,
caption, pricing logic, memory tracking, and daily run-lock safety.

New requirement:
After the existing Facebook post workflow is completed, generate a short
vertical reel/video from the same selected product images and caption data.

Important Constraints:
1. Existing product selection logic must not be changed.
2. Existing Facebook carousel posting logic must not be changed.
3. Existing memory.csv and run_lock.txt behavior must not be changed.
4. New reel/video functionality must be added as a separate block of code.
5. The reel should use already downloaded product images.
6. The reel should be suitable for Facebook/Instagram Reels format.
7. The reel/video feature should be optional and safely callable after post creation.
"""

# ================= REELS VIDEO CONFIG =================

REELS_ENABLED = True

VIDEO_OUTPUT_DIR = "videos"
VIDEO_SIZE = (1080, 1920)   # Vertical Reel format
VIDEO_FPS = 24
IMAGE_DURATION = 2.5        # seconds per image

VIDEO_BG_COLOR = (0, 0, 0)
TEXT_COLOR = "white"
FONT_SIZE_TITLE = 70
FONT_SIZE_PRICE = 85

REEL_HASHTAGS = "#Reels #FacebookReels #ShopNow #Pakistan #OnlineShopping"


# ================= REELS IMAGE PREPARATION =================

def prepare_reel_image(image_path, output_size=VIDEO_SIZE):
    """
    Prepare product image for vertical reel format.
    Existing image download/post logic remains unchanged.
    """

    img = Image.open(image_path).convert("RGB")
    img.thumbnail(output_size)

    background = Image.new("RGB", output_size, VIDEO_BG_COLOR)

    x = (output_size[0] - img.width) // 2
    y = (output_size[1] - img.height) // 2

    background.paste(img, (x, y))

    prepared_path = f"reel_ready_{os.path.basename(image_path)}"
    background.save(prepared_path)

    return prepared_path

# ================= REELS VIDEO CREATION =================

def create_reel_video(image_files, title, price):
    """
    Create vertical reel video from product images.
    This function is separate and does not affect carousel posting.
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
        prepared_img = prepare_reel_image(img)

        clip = (
            ImageClip(prepared_img)
            .set_duration(IMAGE_DURATION)
            .resize(VIDEO_SIZE)
        )

        title_text = (
            TextClip(
                str(title),
                fontsize=FONT_SIZE_TITLE,
                color=TEXT_COLOR,
                method="caption",
                size=(950, None)
            )
            .set_position(("center", 120))
            .set_duration(IMAGE_DURATION)
        )

        price_text = (
            TextClip(
                f"Rs {price}",
                fontsize=FONT_SIZE_PRICE,
                color=TEXT_COLOR
            )
            .set_position(("center", 1650))
            .set_duration(IMAGE_DURATION)
        )

        final_clip = CompositeVideoClip([clip, title_text, price_text])
        clips.append(final_clip)

    video = concatenate_videoclips(clips, method="compose")

    output_path = os.path.join(
        VIDEO_OUTPUT_DIR,
        f"reel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    )

    video.write_videofile(
        output_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio=False
    )

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

if __name__ == "__main__":
    main()
