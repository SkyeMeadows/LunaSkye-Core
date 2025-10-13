import pandas as pd
import sqlite3

# Path to your CSV and DB
csv_file = "D:\EVE-Data\Data\GSF_HOME_sell_5_avg.csv"
db_file = "C:\Programs\\2-EVE\LunaSkye-Core\Shared-Content\market_historical_data.db"
print(f"Path of Database File: {db_file}")
table_name = "market_orders"  # name of the new table

# Read the CSV
df = pd.read_csv(csv_file)
df = df.dropna(subset=["price"])

# Connect (creates DB if not exists)
conn = sqlite3.connect(db_file)
rows = conn.execute("SELECT * FROM market_orders").fetchall()
for row in rows:
    print(row)


# Write to SQL (replace or append as needed)
df.to_sql(table_name, conn, if_exists="append", index=False)

# Close the connection
conn.close()

print(f"Imported {csv_file} into {db_file} (table '{table_name}')")
