import pandas as pd
from modules.utils.paths import TYPE_DICTIONARY_FILE

# Load the CSV file (adjust the path if needed)
df = pd.read_csv(TYPE_DICTIONARY_FILE)

# Drop the 'groupID' column (axis=1 specifies columns)
df = df.drop('type_ID', axis=1)

# Save the updated DataFrame to a new CSV file (without the index column)
df.to_csv(TYPE_DICTIONARY_FILE, index=False)

# Optional: Preview the first few rows to confirm
print(df.head())