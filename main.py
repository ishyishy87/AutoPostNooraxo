import os
import pandas as pd
from datetime import datetime, timedelta

PRODUCTS_FILE = "products.csv"
MEMORY_FILE = "memory.csv"
LOG_FILE = "run_log.txt"

# ✅ Static image from repo
IMAGE_PATH = "final_product.jpg"

# GitHub Secrets
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

COOLDOWN_DAYS = 7


def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - {msg}\n")


def check_secrets():
    if not ACCESS_TOKEN or not PAGE_ID:
        raise Exception("Missing required GitHub Secrets")


# ✅ Load products safely
def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        raise Exception("products.csv not found")

    df = pd.read_csv(PRODUCTS_FILE)

    if "product_id" not in df.columns:
        df["product_id"] = df.index.astype(str)

    if "priority" not in df.columns:
        df["priority"] = 1

    return df


# ✅ FIXED memory loader (handles old + new format)
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        df = pd.DataFrame(columns=["product_id", "last_used"])
        df.to_csv(MEMORY_FILE, index=False)
        return df

    try:
        df = pd.read_csv(MEMORY_FILE)

        # 🔥 Auto-fix old format
        if "last_used" not in df.columns:
            df["last_used"] = pd.NaT
            df.to_csv(MEMORY_FILE, index=False)

        return df

    except:
        df = pd.DataFrame(columns=["product_id", "last_used"])
        df.to_csv(MEMORY_FILE, index=False)
        return df


# ✅ Smart availability filter
def get_available(products, memory):
    if memory.empty:
        return products

    memory["last_used"] = pd.to_datetime(memory["last_used"], errors="coerce")
    cutoff = datetime.now() - timedelta(days=COOLDOWN_DAYS)

    recent = set(
        memory[memory["last_used"] > cutoff]["product_id"].astype(str)
    )

    available = products[
        ~products["product_id"].astype(str).isin(recent)
    ]

    if available.empty:
        log("All products in cooldown → resetting cycle")
        return products

    return available


# ✅ Update memory
def update_memory(product_id):
    df = load_memory()

    new_entry = pd.DataFrame([{
        "product_id": str(product_id),
        "last_used": datetime.now()
    }])

    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(MEMORY_FILE, index=False)


def main():
    try:
        check_secrets()

        products = load_products()
        memory = load_memory()

        available = get_available(products, memory)

        # ✅ Priority-based selection
        selected = available.sample(
            1,
            weights=available["priority"]
        ).iloc[0]

        log(f"Selected product: {selected.to_dict()}")

        # ✅ Static image usage
        if not os.path.exists(IMAGE_PATH):
            raise Exception("final_product.jpg not found in repo")

        image_path = IMAGE_PATH

        # (Future: Facebook upload will use image_path)
        log(f"Using image: {image_path}")

        print("Selected Product:")
        print(selected)

        update_memory(selected["product_id"])

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    main()
