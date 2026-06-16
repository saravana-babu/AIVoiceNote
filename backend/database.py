import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default to SQLite for local development, switch to PostgreSQL dynamically if DATABASE_URL is set.
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///./voicemind.db')

# For SQLite, we need connect_args={"check_same_thread": False}
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
