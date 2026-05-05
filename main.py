import os
import pandas as pd
from datetime import datetime
import requests

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

# ================= SAFETY LOCK =================

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

# ================= SELF-HEALING CSV ENGINE =================

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

    value = row.get(col, default)

    if pd.isna(value):
        return default

    return value

# ================= AI SCORING =================

def score_product(row, col_map):
    score = 0

    title = str(safe_get(row, col_map, "title", "")).lower()

    if any(x in title for x in ["new", "hot", "sale", "best"]):
        score += 10

    if safe_get(row, col_map, "image"):
        score += 5

    try:
        price = float(str(safe_get(row, col_map, "price", 0)).replace("$",""))
        if price < 50:
            score += 10
        elif price < 100:
            score += 5
    except:
        pass

    return score

# ================= PRICE OPTIMIZER =================

def adjust_price(price, score):
    try:
        p = float(str(price).replace("$",""))
    except:
        return price

    if score > 80:
        p *= 0.95
    elif score < 30:
        p *= 1.05

    return round(p, 2)

# ================= CAPTION ENGINE =================

def caption(title, price, score):
    if score > 70:
        hook = "🔥 BEST SELLER ALERT!"
    elif score > 40:
        hook = "⚡ TRENDING DEAL!"
    else:
        hook = "🚨 LIMITED OFFER!"

    return f"""
{hook}

🔥 {title}
💸 Price: {price}

🚚 Cash on Delivery Available
📩 Order Now via Inbox
""".strip()

def hashtags():
    return "#Sale #Pakistan #ShopNow #Deals #OnlineShopping"

# ================= FACEBOOK CAROUSEL =================

def upload_images(image_paths):
    uploaded_ids = []

    for path in image_paths:
        url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"

        with open(path, "rb") as img:
            r = requests.post(url, files={"source": img}, data={
                "published": "false",
                "access_token": ACCESS_TOKEN
            })

        data = r.json()

        if "id" in data:
            uploaded_ids.append(data["id"])
        else:
            log(f"Image upload failed: {data}")

    return uploaded_ids


def post_carousel(image_ids, caption_text):
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"

    attached_media = [{"media_fbid": img_id} for img_id in image_ids]

    r = requests.post(url, json={
        "message": caption_text,
        "attached_media": attached_media,
        "access_token": ACCESS_TOKEN
    })

    data = r.json()

    post_id = data.get("id")
    post_url = f"https://facebook.com/{post_id}" if post_id else None

    return data, post_url

# ================= IMAGE =================

def download_image(url, pid):
    if not url:
        return None

    fn = f"temp_{pid}.jpg"

    try:
        r = requests.get(url, stream=True, timeout=10)
        with open(fn,"wb") as f:
            for c in r.iter_content(1024):
                f.write(c)
        return fn
    except:
        return None

# ================= PRODUCT VALIDATION =================

def validate_product(row, col_map):
    required = ["title", "price", "sku"]
    missing = []

    for r in required:
        if not safe_get(row, col_map, r):
            missing.append(r)

    return len(missing) == 0, missing

# ================= PRODUCT SELECTION =================

def select_product(df, memory, col_map):

    posted = set(memory["product_id"].astype(str))

    sku_col = col_map.get("sku")

    if not sku_col:
        return df.sample(1).iloc[0]

    available = df[~df[sku_col].astype(str).isin(posted)].copy()

    if available.empty:
        available = df.copy()

    available["score"] = available.apply(lambda x: score_product(x, col_map), axis=1)

    top = available.sort_values("score", ascending=False).head(max(1, len(available)//3))

    return top.sample(1).iloc[0]

# ================= MAIN ENGINE =================

def main():

    if already_ran_today():
        log("Skipped (daily lock)")
        return

    df = pd.read_csv(PRODUCTS_FILE)
    df = normalize_columns(df)

    memory = load_memory()

    col_map = map_columns(df)

    product = select_product(df, memory, col_map)

    valid, missing = validate_product(product, col_map)

    if not valid:
        log(f"Skipped product due to missing fields: {missing}")
        return

    pid = safe_get(product, col_map, "sku")
    title = safe_get(product, col_map, "title", "No Title")
    price = safe_get(product, col_map, "price", 0)
    img = safe_get(product, col_map, "image")

    score = score_product(product, col_map)
    final_price = adjust_price(price, score)

    log(f"Selected {title} | Score {score}")

    # ===== MULTI IMAGE FROM SHOPIFY CSV =====

    image_files = []

    sku_col = col_map.get("sku")
    image_col = col_map.get("image")

    if sku_col and image_col:

        product_rows = df[df[sku_col].astype(str) == str(pid)]

        if "image position" in df.columns:
            product_rows = product_rows.sort_values(by="image position")

        image_urls = product_rows[image_col].dropna().unique().tolist()

        for i, url in enumerate(image_urls[:4]):
            f = download_image(str(url).strip(), f"{pid}_{i}")
            if f:
                image_files.append(f)

    else:
        f = download_image(img, pid)
        if f:
            image_files.append(f)

    if not image_files:
        log("No images downloaded")
        return

    cap = caption(title, final_price, score) + "\n\n" + hashtags()

    # ===== CAROUSEL POST =====

    image_ids = upload_images(image_files)

    if not image_ids:
        log("Image upload failed")
        return

    result, post_url = post_carousel(image_ids, cap)

    # ================= MEMORY UPDATE =================

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
    log("Posted + learned successfully")

if __name__ == "__main__":
    main()
