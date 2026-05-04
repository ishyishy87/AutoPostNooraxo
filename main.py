
import os
import pandas as pd
from datetime import datetime, timedelta

PRODUCTS_FILE = "products.csv"
MEMORY_FILE = "memory.csv"
LOG_FILE = "run_log.txt"

# Load secrets from GitHub Secrets
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PAGE_ID = os.getenv("PAGE_ID")

COOLDOWN_DAYS = 7


def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - {msg}\n")


def check_secrets():
    if not ACCESS_TOKEN or not PAGE_ID:
        raise Exception("Missing required GitHub Secrets")


def load_products():
    df = pd.read_csv(PRODUCTS_FILE)

    if "product_id" not in df.columns:
        df["product_id"] = df.index.astype(str)

    if "priority" not in df.columns:
        df["priority"] = 1

    return df


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        df = pd.DataFrame(columns=["product_id", "last_used"])
        df.to_csv(MEMORY_FILE, index=False)
        return df

    try:
        return pd.read_csv(MEMORY_FILE)
    except:
        df = pd.DataFrame(columns=["product_id", "last_used"])
        df.to_csv(MEMORY_FILE, index=False)
        return df


def get_available(products, memory):
    if memory.empty:
        return products

    memory["last_used"] = pd.to_datetime(memory["last_used"], errors="coerce")
    cutoff = datetime.now() - timedelta(days=COOLDOWN_DAYS)

    recent = set(memory[memory["last_used"] > cutoff]["product_id"].astype(str))
    available = products[~products["product_id"].astype(str).isin(recent)]

    return available if not available.empty else products


def main():
    try:
        check_secrets()

        products = load_products()
        memory = load_memory()

        available = get_available(products, memory)
        selected = available.sample(1, weights=available["priority"]).iloc[0]

        log(f"Selected: {selected.to_dict()}")

        # Example usage of secrets
        log(f"Using PAGE_ID: {PAGE_ID}")

        new_entry = pd.DataFrame([{
            "product_id": str(selected["product_id"]),
            "last_used": datetime.now()
        }])

        memory = pd.concat([memory, new_entry], ignore_index=True)
        memory.to_csv(MEMORY_FILE, index=False)

    except Exception as e:
        log(f"ERROR: {str(e)}")
        raise


if __name__ == "__main__":
    main()
