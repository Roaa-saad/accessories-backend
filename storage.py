import os
import io
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL_STORAGE", "https://mvnbzqsqqxnhvehpwklh.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# Only initialize if key is present
if SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except ImportError:
        print("Warning: supabase package not installed")
        supabase = None
else:
    print("Warning: SUPABASE_ANON_KEY not set")
    supabase = None

BUCKET_NAME = "product-images"


async def upload_to_supabase(file, filename: str) -> str:
    """
    Upload file to Supabase Storage, converting to WebP format for better performance
    Creates both full size (800px) and thumbnail (400px) versions
    Falls back to original format if conversion fails
    """
    if not supabase:
        raise Exception("Supabase client not initialized. Please set SUPABASE_ANON_KEY environment variable.")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Try to convert to WebP
        try:
            from PIL import Image
            
            # Open image
            original_image = Image.open(io.BytesIO(file_content))
            
            # Handle transparency - convert to RGB with white background
            if original_image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', original_image.size, (255, 255, 255))
                if original_image.mode == 'P':
                    original_image = original_image.convert('RGBA')
                if original_image.mode in ('RGBA', 'LA'):
                    background.paste(original_image, mask=original_image.split()[-1])
                else:
                    background.paste(original_image)
                original_image = background
            elif original_image.mode != 'RGB':
                original_image = original_image.convert('RGB')
            
            # Create optimized version (max 800px)
            image = original_image.copy()
            max_width = 800
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to WebP with good compression
            webp_buffer = io.BytesIO()
            image.save(webp_buffer, format='WEBP', quality=75, method=6)
            webp_content = webp_buffer.getvalue()
            
            # Change extension to .webp
            filename_base = os.path.splitext(filename)[0]
            webp_filename = f"{filename_base}.webp"
            
            # Upload main WebP version
            response = supabase.storage.from_(BUCKET_NAME).upload(
                path=webp_filename,
                file=webp_content,
                file_options={"content-type": "image/webp", "cacheControl": "3600"}
            )
            
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(webp_filename)
            print(f"✅ Converted to WebP: {filename} → {webp_filename} ({len(file_content)} → {len(webp_content)} bytes, {int((1 - len(webp_content)/len(file_content))*100)}% smaller)")
            return public_url
            
        except Exception as convert_error:
            # Fallback: upload original if conversion fails
            print(f"⚠️ WebP conversion failed for {filename}: {convert_error}. Uploading original.")
            response = supabase.storage.from_(BUCKET_NAME).upload(
                path=filename,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
            return public_url
    
    except Exception as e:
        print(f"Error uploading to Supabase: {e}")
        raise


async def delete_from_supabase(filename: str) -> bool:
    """
    Delete file from Supabase Storage
    """
    if not supabase:
        return False
        
    try:
        supabase.storage.from_(BUCKET_NAME).remove([filename])
        return True
    except Exception as e:
        print(f"Error deleting from Supabase: {e}")
        return False
        return False
