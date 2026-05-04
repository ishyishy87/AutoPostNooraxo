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

# ================= AI SCORING =================

def score_product(row):
    score = 0
    title = str(row.get("Title","")).lower()

    if any(x in title for x in ["new","hot","sale","best"]):
        score += 10
    if row.get("Image Src"):
        score += 5

    try:
        price = float(str(row.get("Price","0")).replace("$",""))
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

# ================= CAPTION =================

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

# ================= FACEBOOK POST =================

def post_to_facebook(image_path, caption_text):
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"

    with open(image_path,"rb") as img:
        r = requests.post(url, files={"source":img}, data={
            "caption": caption_text,
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
    r = requests.get(url, stream=True)
    with open(fn,"wb") as f:
        for c in r.iter_content(1024):
            f.write(c)
    return fn

# ================= PRODUCT SELECTION =================

def select_product(df, memory):
    posted = set(memory["product_id"].astype(str))

    available = df[~df["SKU"].astype(str).isin(posted)].copy()  # FIX 1

    if available.empty:
        available = df.copy()

    available["score"] = available.apply(score_product, axis=1)

    top = available.sort_values("score", ascending=False).head(max(1, len(available)//3))

    return top.sample(1).iloc[0]

# ================= MAIN =================

def main():

    if already_ran_today():
        log("Skipped (daily lock)")
        return

    df = pd.read_csv(PRODUCTS_FILE)
    df.columns = df.columns.str.strip()

    memory = load_memory()

    product = select_product(df, memory)

    pid = product["SKU"]
    title = str(product["Title"])
    price = product.get("Price","0")
    img = product.get("Image Src")

    score = score_product(product)
    final_price = adjust_price(price, score)

    log(f"Selected {title} | Score {score}")

    img_file = download_image(img, pid)
    if not img_file:
        log("No image")
        return

    cap = caption(title, final_price, score) + "\n\n" + hashtags()

    result, post_url = post_to_facebook(img_file, cap)

    # ================= FIX 2: replace append =================

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
    log("Posted + learned")

if __name__ == "__main__":
    main()
