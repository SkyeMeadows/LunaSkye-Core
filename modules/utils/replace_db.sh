#!/bin/bash

# Rename originals to _OLD
mv ./data/jita_market_prices.db ./data/jita_market_prices_OLD.db && \
mv ./data/gsf_market_prices.db ./data/gsf_market_prices_OLD.db && \
echo "Original DBs renamed to _OLD successfully." || {
    echo "Error renaming original DBs: $?"
    exit 1
}

# Rename compacted to originals
mv ./data/jita_compacted.db ./data/jita_market_prices.db && \
mv ./data/gsf_compacted.db ./data/gsf_market_prices.db && \
echo "Compacted DBs renamed to originals successfully." || {
    echo "Error renaming compacted DBs: $?"
    exit 1
}

# Delete the _OLD databases
rm ./data/jita_market_prices_OLD.db && \
rm ./data/gsf_market_prices_OLD.db && \
echo "OLD DBs removed successfully." || {
    echo "Error removing OLD DBs: $?"
    exit 1
}

# Delete the clones
rm ./data/jita_market_prices_clone.db
rm ./data/gsf_market_prices_clone.db

echo "Script completed successfully."