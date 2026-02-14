import os
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
    Upload file to Supabase Storage and return public URL
    """
    if not supabase:
        raise Exception("Supabase client not initialized. Please set SUPABASE_ANON_KEY environment variable.")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Upload to Supabase Storage
        response = supabase.storage.from_(BUCKET_NAME).upload(
            path=filename,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        # Get public URL
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
