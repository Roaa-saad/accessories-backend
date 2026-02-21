import os
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_BASE = f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/products/"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Fetch all product_images
cur.execute("SELECT id, image FROM product_images")
rows = cur.fetchall()

for img_id, old_url in rows:
    filename = os.path.basename(old_url)
    # Try .webp first
    webp_url = CLOUDINARY_BASE + os.path.splitext(filename)[0] + ".webp"
    resp = requests.head(webp_url)
    if resp.status_code == 200:
        new_url = webp_url
    else:
        # Try original extension
        orig_url = CLOUDINARY_BASE + filename
        resp2 = requests.head(orig_url)
        if resp2.status_code == 200:
            new_url = orig_url
        else:
            print(f"Missing in Cloudinary: {filename}")
            continue
    # Update DB if needed
    if old_url != new_url:
        cur.execute("UPDATE product_images SET image = %s WHERE id = %s", (new_url, img_id))
        print(f"Updated id {img_id}: {new_url}")

conn.commit()
cur.close()
conn.close()
print("Checked and fixed missing Cloudinary URLs.")
