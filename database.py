from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variable
# Use SUPABASE_URL for production, fallback to local development database
DATABASE_URL = os.getenv(
    os.getenv("DATABASE_URL")
)

# Create engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connection before using
    pool_recycle=3600,   # Recycle connections every hour
    echo=False           # Set to True for SQL query logging
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
