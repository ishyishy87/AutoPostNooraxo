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


# ---------------- HASHTAGS ENGINE ----------------

HASHTAG_POOL = {
    "general": ["#Sale", "#Deal", "#Pakistan", "#OnlineShopping", "#HotDeal"],
    "fashion": ["#Fashion", "#Style", "#Trendy", "#OOTD", "#Wear"],
    "electronics": ["#Tech", "#Gadgets", "#SmartBuy", "#Electronics", "#Upgrade"],
}

def generate_hashtags(title):
    title_lower = str(title).lower()

    if any(x in title_lower for x in ["shirt", "dress", "jeans", "shoe"]):
        base = HASHTAG_POOL["fashion"]
    elif any(x in title_lower for x in ["phone", "laptop", "watch", "earbuds"]):
        base = HASHTAG_POOL["electronics"]
    else:
        base = HASHTAG_POOL["general"]

    return " ".join(random.sample(base, k=min(4, len(base))))


# ---------------- VIRAL CAPTION ENGINE ----------------

def generate_caption(title, price):
    urgency = random.choice([
        "🔥 LIMITED STOCK ALERT!",
        "⚡ HOT DEAL TODAY ONLY!",
        "🚨 FAST SELLING PRODUCT!",
        "💥 TRENDING NOW!"
    ])

    hook = random.choice([
        "Don't miss this deal!",
        "Grab it before it's gone!",
        "Best price guaranteed!",
        "Customer favorite product!"
    ])

    return f"""
{urgency}

🔥 {title}

💸 Price: {price}

{hook}
🚚 Cash on Delivery Available

📩 Order Now via Inbox!
""".strip()


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
        log(f"Image download failed: {url} | {str(e)}")
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

    return res.json()


# ---------------- MEMORY ----------------

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        df = pd.DataFrame(columns=["product_id", "last_used"])
        df.to_csv(MEMORY_FILE, index=False)
        return df

    return pd.read_csv(MEMORY_FILE)


def update_memory(pid):
    df = load_memory()
    df = pd.concat([df, pd.DataFrame([{
        "product_id": str(pid),
        "last_used": datetime.now()
    }])], ignore_index=True)

    df.to_csv(MEMORY_FILE, index=False)


# ---------------- FILTER ENGINE ----------------

def get_available(products, memory):
    memory["last_used"] = pd.to_datetime(memory.get("last_used"), errors="coerce")
    cutoff = datetime.now() - timedelta(days=COOLDOWN_DAYS)

    recent = set(memory[memory["last_used"] > cutoff]["product_id"].astype(str))

    filtered = products[~products["SKU"].astype(str).isin(recent)]

    return filtered if len(filtered) > 0 else products


# ---------------- MAIN ENGINE ----------------

def main():
    try:
        if already_ran_today():
            log("Skipped: already ran today")
            return

        products = pd.read_csv(PRODUCTS_FILE)
        products.columns = products.columns.str.strip()

        memory = load_memory()
        available = get_available(products, memory)

        selected = available.sample(1).iloc[0]

        title = str(selected.get("Title", "Amazing Product"))
        price = str(selected.get("Price", "Contact for Price"))
        image_url = selected.get("Image Src")
        product_id = selected.get("SKU", str(selected.name))

        if title.lower() == "nan":
            title = "Amazing Product"

        if price.lower() == "nan":
            price = "Contact for Price"

        log(f"Selected: {title} | {price}")

        image_path = download_image(image_url, product_id)

        if not image_path:
            raise Exception("Image missing")

        caption = generate_caption(title, price)
        hashtags = generate_hashtags(title)

        final_caption = f"{caption}\n\n{hashtags}"

        result = post_to_facebook(image_path, final_caption)

        log(f"Posted: {result}")

        update_memory(product_id)
        mark_run()

        print("POSTED SUCCESSFULLY")

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    main()
