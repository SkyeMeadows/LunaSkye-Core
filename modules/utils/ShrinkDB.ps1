# Run clone
try {
    sqlite3 .\data\jita_market_prices.db ".backup .\data\jita_market_prices_clone.db"
    Write-Host "clone of jita DB created successfully."
} catch {
    Write-Host "Error creating clone of jita DB: $_"
    exit 1
}

# Run clone
try {
    sqlite3 .\data\gsf_market_prices.db ".backup .\data\gsf_market_prices_clone.db"
    Write-Host "clone of jita DB created successfully."
} catch {
    Write-Host "Error creating clone of gsf DB: $_"
    exit 1
}

# Integrity check on compacted jita
try {
    sqlite3 .\data\jita_compacted.db "PRAGMA integrity_check;"
    Write-Host "Integrity check on jita compacted DB: OK"
} catch {
    Write-Host "Integrity check failed on jita compacted DB: $_"
    exit 1
}

# Integrity check on compacted gsf
try {
    sqlite3 .\data\gsf_compacted.db "PRAGMA integrity_check;"
    Write-Host "Integrity check on gsf compacted DB: OK"
} catch {
    Write-Host "Integrity check failed on gsf compacted DB: $_"
    exit 1
}

# Run Pruning
try {
    python -m modules.utils.data_prune --db_path .\data\jita_market_prices_clone.db
    Write-Host "Pruned jita DB created successfully."
} catch {
    Write-Host "Error creating compacted jita DB: $_"
    exit 1
}

# Run Pruning
try {
    python -m modules.utils.data_prune --db_path .\data\gsf_market_prices_clone.db
    Write-Host "Pruned gsf DB created successfully."
} catch {
    Write-Host "Error creating compacted gsf DB: $_"
    exit 1
}

# Run 
try {
    sqlite3 .\data\jita_market_prices_clone.db "VACUUM INTO '.\data\jita_compacted.db';"
    Write-Host "Compacted jita DB created successfully."
} catch {
    Write-Host "Error creating compacted jita DB: $_"
    exit 1
}

# Run 
try {
    sqlite3 .\data\gsf_market_prices_clone.db "VACUUM INTO '.\data\gsf_compacted.db';"
    Write-Host "Compacted gsf DB created successfully."
} catch {
    Write-Host "Error creating compacted gsf DB: $_"
    exit 1
}

# Integrity check on compacted jita
try {
    sqlite3 .\data\jita_compacted.db "PRAGMA integrity_check;"
    Write-Host "Integrity check on jita compacted DB: OK"
} catch {
    Write-Host "Integrity check failed on jita compacted DB: $_"
    exit 1
}

# Integrity check on compacted gsf
try {
    sqlite3 .\data\gsf_compacted.db "PRAGMA integrity_check;"
    Write-Host "Integrity check on gsf compacted DB: OK"
} catch {
    Write-Host "Integrity check failed on gsf compacted DB: $_"
    exit 1
}

# Rename originals to _OLD
try {
    Rename-Item -Path .\data\jita_market_prices.db -NewName jita_market_prices_OLD.db
    Rename-Item -Path .\data\gsf_market_prices.db -NewName gsf_market_prices_OLD.db
    Write-Host "Original DBs renamed to _OLD successfully."
} catch {
    Write-Host "Error renaming original DBs: $_"
    exit 1
}

# Rename compacted to originals
try {
    Rename-Item -Path .\data\jita_compacted.db -NewName jita_market_prices.db
    Rename-Item -Path .\data\gsf_compacted.db -NewName gsf_market_prices.db
    Write-Host "Compacted DBs renamed to originals successfully."
} catch {
    Write-Host "Error renaming compacted DBs: $_"
    exit 1
}

# Delete the _OLD databases
try {
    Remove-Item -Path .\data\jita_market_prices_OLD.db
    Remove-Item -Path .\data\gsf_market_prices_OLD.db
    Write-Host "OLD DBs removed successfully."
} catch {
    Write-Host "Error removing OLD DBs: $_"
    exit 1
}

Write-Host "Script completed successfully."