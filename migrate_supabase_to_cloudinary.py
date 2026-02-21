import os
import io
from supabase import create_client, Client
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
BUCKET_NAME = "product-images"

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def list_supabase_files():
    return supabase.storage.from_(BUCKET_NAME).list()

def download_supabase_file(filename):
    return supabase.storage.from_(BUCKET_NAME).download(filename)

def upload_to_cloudinary(file_bytes, filename):
    result = cloudinary.uploader.upload(
        io.BytesIO(file_bytes),
        public_id=f"products/{filename}",
        resource_type="image"
    )
    return result["secure_url"]

def migrate_all_images():
    files = list_supabase_files()
    for file in files:
        filename = file["name"]
        print(f"Migrating: {filename}")
        file_bytes = download_supabase_file(filename)
        url = upload_to_cloudinary(file_bytes, filename)
        print(f"Cloudinary URL: {url}")

if __name__ == "__main__":
    migrate_all_images()
