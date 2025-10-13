import sqlite3
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

common_folder = os.path.join(os.path.dirname(script_dir), "Shared-Content")
DB_PATH = os.path.join(common_folder, "market_historical_data.db")

def init_db():
    first_time = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # Enable WAL mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL;")
    
    # Create tables if they don't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_orders (
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        item_id INTEGER NOT NULL,
        system TEXT NOT NULL,
        price REAL NOT NULL
    );
    """)

    conn.commit()
    conn.close()

    if first_time:
        print("Database initialized and WAL mode enabled.")
    else:
        print("Database already exists — schema checked.")

if __name__ == "__main__":
    init_db()
