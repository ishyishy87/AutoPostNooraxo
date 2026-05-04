import os
import pandas as pd
from datetime import datetime, timedelta
import requests

# ---------------- CONFIG ----------------

PRODUCTS_FILE = "products.csv"
MEMORY_FILE = "memory.csv"
LOG_FILE = "run_log.txt"

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

COOLDOWN_DAYS = 7


# ---------------- LOGGING ----------------

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - {msg}\n")


# ---------------- FACEBOOK POST ----------------

def post_to_facebook(image_path, caption):
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"

    with open(image_path, "rb") as img:
        files = {"source": img}
        data = {
            "caption": caption,
            "access_token": ACCESS_TOKEN
        }

        response = requests.post(url, files=files, data=data)

    if response.status_code != 200:
        raise Exception(f"Facebook पोस्ट failed: {response.text}")

    return response.json()


# ---------------- IMAGE DOWNLOAD (PRO FEATURE) ----------------

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


# ---------------- CAPTION ----------------

def generate_caption(title, price):
    return f"""
🔥 {title}

💸 Price: {price}

✅ Limited Time Offer
🚚 Cash on Delivery Available

📩 Order Now via Inbox!

#Sale #Deal #Pakistan
""".strip()


# ---------------- SECRETS CHECK ----------------

def check_secrets():
    if not ACCESS_TOKEN or not PAGE_ID:
        raise Exception("Missing required GitHub Secrets")


# ---------------- LOAD PRODUCTS (SHOPIFY CSV SAFE) ----------------

def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        raise Exception("products.csv not found")

    df = pd.read_csv(PRODUCTS_FILE)

    # clean headers (important for your CSV)
    df.columns = df.columns.str.strip()

    return df


# ---------------- MEMORY ----------------

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        df = pd.DataFrame(columns=["product_id", "last_used"])
        df.to_csv(MEMORY_FILE, index=False)
        return df

    df = pd.read_csv(MEMORY_FILE)

    if "last_used" not in df.columns:
        df["last_used"] = pd.NaT
        df.to_csv(MEMORY_FILE, index=False)

    return df


def update_memory(product_id):
    df = load_memory()

    new_entry = pd.DataFrame([{
        "product_id": str(product_id),
        "last_used": datetime.now()
    }])

    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(MEMORY_FILE, index=False)


# ---------------- SMART FILTER ----------------

def get_available(products, memory):
    if memory.empty:
        return products

    memory["last_used"] = pd.to_datetime(memory["last_used"], errors="coerce")
    cutoff = datetime.now() - timedelta(days=COOLDOWN_DAYS)

    recent = set(
        memory[memory["last_used"] > cutoff]["product_id"].astype(str)
    )

    available = products[
        ~products["SKU"].astype(str).isin(recent)
    ]

    if available.empty:
        log("All products in cooldown → resetting cycle")
        return products

    return available


# ---------------- MAIN ENGINE ----------------

def main():
    try:
        check_secrets()

        products = load_products()
        memory = load_memory()

        available = get_available(products, memory)

        selected = available.sample(1).iloc[0]

        # ---------------- MAP SHOPIFY COLUMNS ----------------

        title = selected.get("Title", "Amazing Product")
        price = selected.get("Price", "")
        image_url = selected.get("Image Src")
        product_id = selected.get("SKU", str(selected.name))

        log(f"Selected product: {title} | {price}")

        # ---------------- IMAGE DOWNLOAD ----------------

        image_path = download_image(image_url, product_id)

        if not image_path:
            raise Exception("Image download failed (no valid image)")

        # ---------------- CAPTION ----------------

        caption = generate_caption(title, price)

        # ---------------- POST TO FACEBOOK ----------------

        result = post_to_facebook(image_path, caption)

        log(f"Posted successfully: {result}")

        print("Posted Successfully:", result)

        # ---------------- UPDATE MEMORY ----------------

        update_memory(product_id)

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    main()
