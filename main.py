import os
import pandas as pd
from datetime import datetime, timedelta
import requests
import random

# ---------------- CONFIG ----------------

PRODUCTS_FILE = "products.csv"
MEMORY_FILE = "memory.csv"
LOG_FILE = "run_log.txt"
RUN_LOCK_FILE = "run_lock.txt"

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

COOLDOWN_DAYS = 7

# ---------------- LOGGING ----------------

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {msg}\n")


# ---------------- RUN LOCK ----------------

def already_ran_today():
    if not os.path.exists(RUN_LOCK_FILE):
        return False
    with open(RUN_LOCK_FILE, "r") as f:
        return f.read().strip() == str(datetime.now().date())

def mark_run():
    with open(RUN_LOCK_FILE, "w") as f:
        f.write(str(datetime.now().date()))


# ---------------- AI CAPTION ENGINE (V2) ----------------

def generate_caption(title, price):
    hooks = [
        "🔥 LIMITED TIME DEAL!",
        "⚡ HOT SELLING NOW!",
        "🚨 TRENDING PRODUCT!",
        "💥 BEST VALUE TODAY!"
    ]

    emotions = [
        "Don't miss this offer!",
        "Everyone is buying this!",
        "Grab it before stock ends!",
        "Customer favorite pick!"
    ]

    cta = [
        "Order now via inbox 📩",
        "Message us to buy 💬",
        "Limited stock available 🚚",
        "Fast delivery across Pakistan 🚀"
    ]

    return f"""
{random.choice(hooks)}

🔥 {title}

💸 Price: {price}

{random.choice(emotions)}

{random.choice(cta)}

#Sale #Deal #Pakistan #OnlineShopping
""".strip()


# ---------------- HASHTAG ENGINE ----------------

def generate_hashtags(title):
    base = ["#Sale", "#Deal", "#Pakistan", "#ShopNow", "#HotDeal", "#Trending"]

    if any(x in title.lower() for x in ["shirt", "dress", "jeans"]):
        base += ["#Fashion", "#Style"]
    elif any(x in title.lower() for x in ["phone", "laptop", "watch"]):
        base += ["#Tech", "#Gadget"]

    return " ".join(random.sample(base, 6))


# ---------------- IMAGE DOWNLOAD ----------------

def download_image(url, product_id):
    try:
        if not url or str(url).strip() == "":
            return None

        filename = f"temp_{product_id}.jpg"

        r = requests.get(url, stream=True, timeout=20)
        r.raise_for_status()

        with open(filename, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)

        return filename

    except Exception as e:
        log(f"Image error: {str(e)}")
        return None


# ---------------- FACEBOOK POST ----------------

def post_to_facebook(image_path, caption):
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"

    with open(image_path, "rb") as img:
        files = {"source": img}
        data = {
            "caption": caption,
            "access_token": ACCESS_TOKEN
        }

        res = requests.post(url, files=files, data=data)

    if res.status_code != 200:
        raise Exception(res.text)

    result = res.json()
    post_id = result.get("id")
    post_url = f"https://www.facebook.com/{post_id}" if post_id else None

    return result, post_url


# ---------------- MEMORY SYSTEM V2 ----------------

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        df = pd.DataFrame(columns=[
            "product_id", "status", "original_price",
            "adjusted_price", "post_url", "date"
        ])
        df.to_csv(MEMORY_FILE, index=False)
        return df

    return pd.read_csv(MEMORY_FILE)


def update_memory(pid, price, post_url, status="posted"):
    df = load_memory()

    new_row = {
        "product_id": str(pid),
        "status": status,
        "original_price": price,
        "adjusted_price": price,
        "post_url": post_url,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(MEMORY_FILE, index=False)


# ---------------- SMART FILTER (NO DUPLICATES) ----------------

def get_available(products, memory):
    posted = set(memory[memory["status"] == "posted"]["product_id"].astype(str))
    available = products[~products["SKU"].astype(str).isin(posted)]
    return available if len(available) > 0 else products


# ---------------- PRODUCT SCORING (AI v2 CORE) ----------------

def score_product(row):
    score = 0

    price = str(row.get("Price", ""))

    if price and price != "nan":
        score += 10

    if row.get("Image Src"):
        score += 5

    title = str(row.get("Title", "")).lower()

    if any(x in title for x in ["new", "hot", "best", "sale"]):
        score += 5

    return score


# ---------------- MAIN ENGINE ----------------

def main():
    try:
        if already_ran_today():
            log("Skipped (already run today)")
            return

        products = pd.read_csv(PRODUCTS_FILE)
        products.columns = products.columns.str.strip()

        memory = load_memory()

        available = get_available(products, memory)

        # ---------------- AI PRODUCT SELECTION ----------------

        available["score"] = available.apply(score_product, axis=1)
        available = available.sort_values("score", ascending=False)

        selected = available.iloc[0]

        title = str(selected.get("Title", "Amazing Product"))
        price = str(selected.get("Price", "Contact for Price"))
        image_url = selected.get("Image Src")
        product_id = selected.get("SKU", str(selected.name))

        if title.lower() == "nan":
            title = "Amazing Product"

        if price.lower() == "nan":
            price = "Contact for Price"

        log(f"Selected AI product: {title} | {price}")

        image_path = download_image(image_url, product_id)

        if not image_path:
            raise Exception("Image missing")

        caption = generate_caption(title, price)
        hashtags = generate_hashtags(title)

        final_caption = f"{caption}\n\n{hashtags}"

        result, post_url = post_to_facebook(image_path, final_caption)

        log(f"Posted: {post_url}")

        update_memory(product_id, price, post_url)

        mark_run()

        print("POST SUCCESS")

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    main()
