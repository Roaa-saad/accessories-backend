import os
import io
from supabase import create_client, Client
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")  # Use API URL for Supabase
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
BUCKET_NAME = "product-images"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def list_supabase_files():
    return supabase.storage.from_(BUCKET_NAME).list()

def download_supabase_file(filename):
    res = supabase.storage.from_(BUCKET_NAME).download(filename)
    return res

def compress_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    # Convert to WebP with good compression
    webp_buffer = io.BytesIO()
    image.save(webp_buffer, format='WEBP', quality=75, method=6)
    return webp_buffer.getvalue()

def upload_to_supabase(filename, file_bytes):
    filename_base = os.path.splitext(filename)[0]
    webp_filename = f"{filename_base}.webp"
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=webp_filename,
            file=file_bytes,
            file_options={"content-type": "image/webp", "cacheControl": "3600"}
        )
        print(f"Uploaded compressed: {webp_filename}")
    except Exception as e:
        if 'Duplicate' in str(e) or 'resource already exists' in str(e):
            print(f"Skipped (already exists): {webp_filename}")
        else:
            print(f"Error uploading {webp_filename}: {e}")

def compress_all_images():
    files = list_supabase_files()
    for file in files:
        filename = file["name"]
        print(f"Compressing: {filename}")
        image_bytes = download_supabase_file(filename)
        compressed_bytes = compress_image(image_bytes)
        upload_to_supabase(filename, compressed_bytes)

if __name__ == "__main__":
    compress_all_images()
