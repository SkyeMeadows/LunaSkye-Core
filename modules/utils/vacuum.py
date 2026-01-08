import sqlite3
import argparse
from pathlib import Path

def enable_incremental_vacuum(db_path: Path):
    """Enable incremental vacuum mode if not already set."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
    conn.commit()
    conn.close()
    print(f"[{db_path.name}] Incremental vacuum mode enabled.")

def reclaim_space(db_path: Path, chunk_bytes: int):
    """Reclaim up to chunk_bytes of free space using incremental vacuum."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA freelist_count;")
    freelist_pages = cursor.fetchone()[0]

    if freelist_pages == 0:
        print(f"[{db_path.name}] No free pages to reclaim.")
        conn.close()
        return False

    cursor.execute("PRAGMA page_size;")
    page_size = cursor.fetchone()[0]

    pages_to_vacuum = min(freelist_pages, chunk_bytes // page_size)

    actual_mb = (pages_to_vacuum * page_size) // (1024 * 1024)
    print(f"[{db_path.name}] Reclaiming ~{actual_mb} MB ({pages_to_vacuum} pages out of {freelist_pages} free)")

    # Perform the incremental vacuum
    if pages_to_vacuum <= 100:
        # When only a tiny amount is left, just reclaim everything remaining
        print(f"[{db_path.name}] Remaining space small — reclaiming all leftover pages.")
        cursor.execute("PRAGMA incremental_vacuum;")  # Reclaim all possible
    else:
        cursor.execute(f"PRAGMA incremental_vacuum({pages_to_vacuum});")

    conn.commit()
    conn.close()

    # Always check again after vacuum — if nothing was freed, we're done
    # But we return True/False based on whether freelist was >0 before this pass
    return freelist_pages > 0

def vacuum_database(db_path: Path, max_chunk_mb: int):
    db_path = db_path.resolve()
    print(f"\nProcessing: {db_path} (max {max_chunk_mb} MB per pass)\n")

    enable_incremental_vacuum(db_path)

    chunk_bytes = max_chunk_mb * 1024 * 1024
    reclaimed_any = True
    pass_count = 0

    while reclaimed_any:
        pass_count += 1
        print(f"Pass {pass_count}...")
        reclaimed_any = reclaim_space(db_path, chunk_bytes)

    print(f"[{db_path.name}] Finished. No more space to reclaim in {max_chunk_mb} MB chunks.")

def main():
    parser = argparse.ArgumentParser(
        description="Safely reclaim disk space from SQLite databases using incremental vacuum."
    )
    parser.add_argument(
        "--db_path",
        type=Path,
        help="One SQLite database file to vacuum"
    )
    parser.add_argument(
        "--reclaim_size",
        type=int,
        default=500,
        help="Max MB to reclaim per pass on large DBs (default: 500)"
    )

    args = parser.parse_args()

    chunk_mb = args.reclaim_size
    db_path = args.db_path
    vacuum_database(db_path, chunk_mb)

if __name__ == "__main__":
    main()