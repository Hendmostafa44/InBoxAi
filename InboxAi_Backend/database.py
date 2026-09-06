import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / "agents" / ".env"
load_dotenv(env_path)

DATABASE_URL = (
    f"postgresql+psycopg://"
    f"{os.getenv('SUPABASE_DB_USER')}:"
    f"{os.getenv('SUPABASE_DB_PASSWORD')}@"
    f"{os.getenv('SUPABASE_DB_HOST')}:"
    f"{os.getenv('SUPABASE_DB_PORT')}/"
    f"{os.getenv('SUPABASE_DB_NAME')}"
)

engine = create_engine(DATABASE_URL)


def test_db_connection():
    with engine.connect() as connection:
        print("✅ Connected to Supabase PostgreSQL!")


if __name__ == "__main__":
    test_db_connection()