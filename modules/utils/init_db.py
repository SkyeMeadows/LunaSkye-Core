import sqlite3
from modules.utils.paths import DATA_DIR

markets = ["jita", "gsf"] # Modify this list to add markets

create_table_sql = '''
CREATE TABLE IF NOT EXISTS market_prices (
    item_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL,
    price REAL NOT NULL
    );
'''

for market in markets:
    
    db_file = DATA_DIR / f"{market}_market_prices.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    conn.commit()
    print(f"Database '{db_file}' at directory {db_file.resolve()} initialized.")

    cursor.execute("PRAGMA table_info(market_prices);")
    schema = cursor.fetchall()
    print(f"Schema for '{market}' Database: {schema}")
    conn.close