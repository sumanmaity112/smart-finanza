import sqlite3
import hashlib
import os
from datetime import datetime
from typing import List, Dict
from constants import TxnType, PaymentMethod

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
                                                                 txn_type TEXT,       -- Stores 'DEBIT' or 'CREDIT'
                                                                 payment_method TEXT, -- Stores 'Credit Card', 'UPI', etc.
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

    def save_transactions(
        self, transactions: List[Dict], filename: str, default_method: PaymentMethod
    ):
        conn = self.get_connection()
        c = conn.cursor()
        count = 0

        for t in transactions:
            # Basic validation
            if not t.get("merchant") or not t.get("amount"):
                continue

            # 1. ENUM LOGIC: Resolve Payment Method
            # The LLM gives us a string; we try to match it to an Enum, or fallback to file default
            raw_method = t.get("payment_method")
            p_method = default_method

            if raw_method and raw_method != "Unknown":
                for pm in PaymentMethod:
                    if pm.value.lower() == raw_method.lower():
                        p_method = pm
                        break

            # 2. ENUM LOGIC: Resolve Transaction Type
            raw_type = t.get("txn_type", "DEBIT")
            txn_type = TxnType.DEBIT  # Default
            if str(raw_type).upper() == "CREDIT":
                txn_type = TxnType.CREDIT

            # 3. Clean Amount
            try:
                amt = abs(float(str(t["amount"]).replace(",", "")))
            except Exception:
                continue

            try:
                # We use transaction_id + source_file as a composite unique key
                # If transaction_id is missing, we generate a pseudo-ID from data
                tx_id = t.get("transaction_id")
                if not tx_id:
                    # Create a deterministic hash of the transaction content itself
                    raw_str = f"{t.get('date')}{t.get('merchant')}{amt}"
                    tx_id = "GEN-" + hashlib.md5(raw_str.encode()).hexdigest()[:8]

                c.execute(
                    """INSERT OR IGNORE INTO transactions 
                             (transaction_id, date, merchant, amount, txn_type, payment_method, notes, source_file)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        tx_id,
                        t.get("date"),
                        t.get("merchant"),
                        amt,
                        txn_type.value,  # Save Enum string value
                        p_method.value,  # Save Enum string value
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
