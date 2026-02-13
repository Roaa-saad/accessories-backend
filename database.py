from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variable
# Priority: DATABASE_URL (Railway PostgreSQL) > SUPABASE_URL > local development
raw_db_url = os.getenv("DATABASE_URL")
raw_supabase_url = os.getenv("SUPABASE_URL")

print(f"DEBUG - DATABASE_URL exists: {raw_db_url is not None}")
print(f"DEBUG - SUPABASE_URL exists: {raw_supabase_url is not None}")

DATABASE_URL = raw_db_url or raw_supabase_url or "postgresql://postgres:123@localhost:5432/accessories_db"

# Railway sometimes provides postgres:// URLs, convert to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("DEBUG - Converted postgres:// to postgresql://")

# Validate that we have a proper URL
if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    print(f"ERROR - Invalid DATABASE_URL: {DATABASE_URL}")
    raise ValueError(f"Invalid DATABASE_URL: {DATABASE_URL}")

print(f"Connecting to database: {DATABASE_URL[:30]}...")  # Print first 30 chars for debugging

# Create engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connection before using
    pool_recycle=3600,   # Recycle connections every hour
    echo=False           # Set to True for SQL query logging
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
