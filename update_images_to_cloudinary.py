import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Get database connection info from .env
DATABASE_URL = os.getenv("DATABASE_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")

# Connect to PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Fetch all product_images
cur.execute("SELECT id, image FROM product_images")
rows = cur.fetchall()

for img_id, old_image in rows:
    # Extract filename from old image path or URL
    filename = os.path.basename(old_image)
    # Build Cloudinary URL
    cloudinary_url = f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/upload/products/{filename}"
    # Update the image field
    cur.execute("UPDATE product_images SET image = %s WHERE id = %s", (cloudinary_url, img_id))
    print(f"Updated id {img_id}: {cloudinary_url}")

conn.commit()
cur.close()
conn.close()
print("All product_images updated to Cloudinary URLs.")
