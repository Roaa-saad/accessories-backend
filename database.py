from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment variable
# Priority: DATABASE_URL (Railway PostgreSQL) > SUPABASE_URL > local development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("SUPABASE_URL", "postgresql://postgres:123@localhost:5432/accessories_db")
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
