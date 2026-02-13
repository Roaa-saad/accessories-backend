from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variable
# Priority: DATABASE_URL (Railway PostgreSQL) > SUPABASE_URL > local development
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL") or "postgresql://postgres:123@localhost:5432/accessories_db"

# Validate that we have a proper URL
if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
    raise ValueError(f"Invalid DATABASE_URL: {DATABASE_URL}")

print(f"Connecting to database: {DATABASE_URL[:20]}...")  # Print first 20 chars for debugging

# Create engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connection before using
    pool_recycle=3600,   # Recycle connections every hour
    echo=False           # Set to True for SQL query logging
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
