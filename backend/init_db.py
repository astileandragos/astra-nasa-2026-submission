"""Create the SQLite database (backend/astra.db) from schema.sql. Safe to run again."""
from app import DB_PATH, init_db

init_db()
print(f"Database ready: {DB_PATH}")
