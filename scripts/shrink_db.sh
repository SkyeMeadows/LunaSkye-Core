#!/bin/bash

# Run clone for jita
sqlite3 ./data/jita_market_prices.db ".backup ./data/jita_market_prices_clone.db" && \
echo "clone of jita DB created successfully." || {
    echo "Error creating clone of jita DB: $?"
    exit 1
}

# Run clone for gsf
sqlite3 ./data/gsf_market_prices.db ".backup ./data/gsf_market_prices_clone.db" && \
echo "clone of gsf DB created successfully." || {
    echo "Error creating clone of gsf DB: $?"
    exit 1
}

# Integrity check on compacted jita
sqlite3 ./data/jita_compacted.db "PRAGMA integrity_check;" && \
echo "Integrity check on jita compacted DB: OK" || {
    echo "Integrity check failed on jita compacted DB: $?"
    exit 1
}

# Integrity check on compacted gsf
sqlite3 ./data/gsf_compacted.db "PRAGMA integrity_check;" && \
echo "Integrity check on gsf compacted DB: OK" || {
    echo "Integrity check failed on gsf compacted DB: $?"
    exit 1
}

# Run Pruning for jita
python -m modules.utils.data_prune --db_path ./data/jita_market_prices_clone.db && \
echo "Pruned jita DB created successfully." || {
    echo "Error creating compacted jita DB: $?"
    exit 1
}

# Run Pruning for gsf
python -m modules.utils.data_prune --db_path ./data/gsf_market_prices_clone.db && \
echo "Pruned gsf DB created successfully." || {
    echo "Error creating compacted gsf DB: $?"
    exit 1
}

# Run Vacuum for jita
sqlite3 ./data/jita_market_prices_clone.db "VACUUM INTO './data/jita_compacted.db';" && \
echo "Compacted jita DB created successfully." || {
    echo "Error creating compacted jita DB: $?"
    exit 1
}

# Run Vacuum for gsf
sqlite3 ./data/gsf_market_prices_clone.db "VACUUM INTO './data/gsf_compacted.db';" && \
echo "Compacted gsf DB created successfully." || {
    echo "Error creating compacted gsf DB: $?"
    exit 1
}

# Integrity check on compacted jita
sqlite3 ./data/jita_compacted.db "PRAGMA integrity_check;" && \
echo "Integrity check on jita compacted DB: OK" || {
    echo "Integrity check failed on jita compacted DB: $?"
    exit 1
}

# Integrity check on compacted gsf
sqlite3 ./data/gsf_compacted.db "PRAGMA integrity_check;" && \
echo "Integrity check on gsf compacted DB: OK" || {
    echo "Integrity check failed on gsf compacted DB: $?"
    exit 1
}

echo "Script completed successfully."