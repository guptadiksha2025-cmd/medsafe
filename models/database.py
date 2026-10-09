import sqlite3
import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "database", "medsafe.db"))

def get_db_connection():
    """Returns a SQLite connection object with Row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables when needed."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    # Placeholder for database schema initialization
    pass
