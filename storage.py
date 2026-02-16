import os
import io
from PIL import Image
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
    """
    if not supabase:
        raise Exception("Supabase client not initialized. Please set SUPABASE_ANON_KEY environment variable.")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Convert image to WebP format
        try:
            # Open image
            image = Image.open(io.BytesIO(file_content))
            
            # Convert RGBA to RGB if necessary (WebP doesn't support transparency in all modes)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if image is too large (max 1920px width while maintaining aspect ratio)
            max_width = 1920
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save as WebP with good quality
            webp_buffer = io.BytesIO()
            image.save(webp_buffer, format='WEBP', quality=85, method=6)
            webp_content = webp_buffer.getvalue()
            
            # Change filename extension to .webp
            filename_without_ext = os.path.splitext(filename)[0]
            webp_filename = f"{filename_without_ext}.webp"
            
            print(f"✅ Converted {filename} to WebP format ({len(file_content)} bytes → {len(webp_content)} bytes)")
            
            # Upload WebP to Supabase Storage
            response = supabase.storage.from_(BUCKET_NAME).upload(
                path=webp_filename,
                file=webp_content,
                file_options={"content-type": "image/webp"}
            )
            
            # Get public URL
            public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(webp_filename)
            
            return public_url
            
        except Exception as img_error:
            print(f"Warning: Could not convert to WebP: {img_error}")
            # Fallback: upload original file
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
