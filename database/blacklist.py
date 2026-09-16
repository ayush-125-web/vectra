import sqlite3
from pathlib import Path
from datetime import datetime

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Database path
DB_PATH = BASE_DIR / "anpr_system.db"


def add_blacklist(plate_number, reason):
    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO blacklist (
                plate_number,
                reason,
                flagged_on,
                status
            )
            VALUES (?, ?, ?, ?)
        """, (
            plate_number,
            reason,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active"
        ))

        conn.commit()

        print(f"Added {plate_number} to blacklist")

    except sqlite3.IntegrityError as e:
        print("Could not add blacklist entry:")
        print(e)

    finally:
        conn.close()


# --------------------------------------------------
# ADD TEST BLACKLIST VEHICLES
# --------------------------------------------------

add_blacklist("LM07MKD", "Test blacklisted vehicle")
add_blacklist("TN10XY4567", "Stolen vehicle")
add_blacklist("TN09AB1234", "Wanted vehicle")