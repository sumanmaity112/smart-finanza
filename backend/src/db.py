import sqlite3
import hashlib
import os
from datetime import datetime
from typing import List, Dict

DB_NAME = os.getenv("DB_NAME", "finance_vault.db")


# --- DATABASE ENGINE ---
class DatabaseEngine:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        """Creates the necessary tables if they don't exist."""
        conn = self.get_connection()
        c = conn.cursor()

        # 1. Track Processed Files (Avoid Duplicates)
        c.execute("""CREATE TABLE IF NOT EXISTS processed_files (
                        file_hash TEXT PRIMARY KEY, 
                        filename TEXT, 
                        processed_date TEXT
                    )""")

        # 2. Transactions Table
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id TEXT,
                        date TEXT,
                        merchant TEXT,
                        amount REAL,
                        payment_method TEXT,
                        category TEXT DEFAULT 'Uncategorized',
                        notes TEXT,
                        source_file TEXT,
                        UNIQUE(transaction_id, source_file)
                    )""")

        # 3. Category Rules (Persistent Knowledge Base)
        c.execute("""CREATE TABLE IF NOT EXISTS category_map (
                        keyword TEXT PRIMARY KEY, 
                        category TEXT
                    )""")

        conn.commit()
        conn.close()

    def is_file_processed(self, file_hash):
        conn = self.get_connection()
        res = conn.execute(
            "SELECT 1 FROM processed_files WHERE file_hash=?", (file_hash,)
        ).fetchone()
        conn.close()
        return res is not None

    def log_file_processed(self, file_hash, filename):
        conn = self.get_connection()
        conn.execute(
            "INSERT INTO processed_files VALUES (?, ?, ?)",
            (file_hash, filename, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def save_transactions(self, transactions: List[Dict], filename: str):
        conn = self.get_connection()
        c = conn.cursor()
        count = 0
        for t in transactions:
            print(f"Debug Transaction: {t}")
            # Basic validation
            if not t.get("merchant") or not t.get("amount"):
                continue

            try:
                # We use transaction_id + source_file as a composite unique key
                # If transaction_id is missing, we generate a pseudo-ID from data
                tx_id = t.get("transaction_id")
                if not tx_id:
                    # Create a deterministic hash of the transaction content itself
                    raw_str = f"{t.get('date')}{t.get('merchant')}{t.get('amount')}"
                    tx_id = "GEN-" + hashlib.md5(raw_str.encode()).hexdigest()[:8]

                c.execute(
                    """INSERT OR IGNORE INTO transactions 
                             (transaction_id, date, merchant, amount, payment_method, notes, source_file)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tx_id,
                        t.get("date"),
                        t.get("merchant"),
                        t.get("amount"),
                        t.get("payment_method", "Unknown"),
                        t.get("notes", ""),
                        filename,
                    ),
                )
                if c.rowcount > 0:
                    count += 1
            except Exception as e:
                print(f"⚠️ DB Error on row: {e}")

        conn.commit()
        conn.close()
        return count
