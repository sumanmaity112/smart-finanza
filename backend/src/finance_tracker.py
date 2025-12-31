import sqlite3
import hashlib
import json
import os
import pdfplumber
import pandas as pd
import ollama
from datetime import datetime
from typing import List, Dict

# --- CONFIGURATION ---
DB_NAME = "finance_vault.db"
MODEL_NAME = "qwen2.5"  # Best for structured data. Alt: "llama3.1"
CHUNK_SIZE_LINES = 20  # How many CSV lines to feed the model at once


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


# --- LLM ENGINE ---
class LLMExtractor:
    def __init__(self, model=MODEL_NAME):
        self.model = model

    def clean_json_response(self, response_text):
        """Removes Markdown formatting if the model adds it."""
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def extract_chunk(self, text_chunk: str, is_csv: bool = False) -> List[Dict]:
        context_hint = "raw CSV rows" if is_csv else "PDF bank statement text"

        prompt = f"""
        Act as a strict financial data parser. Extract transactions from the {context_hint} below.
        
        RULES:
        1. Output pure JSON only. No markdown, no conversational text.
        2. Date Format: YYYY-MM-DD.
        3. Amount: Float. Negative for Debits/Spending, Positive for Credits/Income.
        4. Merchant: Clean up the name (e.g., "UBER *TRIP 882" -> "Uber").
        5. Payment Method: Infer from text (UPI, Card, NEFT, etc.). Default "Unknown".
        6. Transaction ID: Extract if present. Return null if not found.
        
        INPUT TEXT:
        {text_chunk}
        
        REQUIRED JSON STRUCTURE:
        [
            {{
                "date": "2024-01-01",
                "merchant": "Merchant Name",
                "amount": -50.00,
                "payment_method": "Credit Card",
                "transaction_id": "TXN123",
                "notes": "Any narration text"
            }}
        ]
        """

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0},  # Strict mode
            )
            clean_json = self.clean_json_response(response["message"]["content"])
            data = json.loads(clean_json)

            # Handle cases where model returns dict instead of list
            if isinstance(data, dict):
                return data.get("transactions", [])
            return data

        except Exception as e:
            print(f"❌ LLM Error: {e}")
            return []


# --- CATEGORIZATION ENGINE ---
class Categorizer:
    def __init__(self, db: DatabaseEngine):
        self.db = db

    def add_rule(self, keyword: str, category: str):
        """Learns a new rule and updates PAST data immediately."""
        conn = self.db.get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO category_map (keyword, category) VALUES (?, ?)",
            (keyword.lower(), category),
        )
        conn.commit()
        conn.close()
        print(f"🧠 Learned: '{keyword}' -> '{category}'")
        self.run_updates(target_keyword=keyword)

    def run_updates(self, target_keyword=None):
        """Applies rules to Uncategorized transactions."""
        conn = self.db.get_connection()
        c = conn.cursor()

        # 1. Fetch Rules
        c.execute("SELECT keyword, category FROM category_map")
        rules = c.fetchall()
        # Sort by length desc so "Amazon AWS" matches before "Amazon"
        rules.sort(key=lambda x: len(x[0]), reverse=True)

        # 2. Fetch Transactions to Process
        if target_keyword:
            # Only update transactions matching the new keyword
            c.execute(
                "SELECT id, merchant FROM transactions WHERE merchant LIKE ?",
                (f"%{target_keyword}%",),
            )
        else:
            # Update ALL uncategorized
            c.execute(
                "SELECT id, merchant FROM transactions WHERE category = 'Uncategorized'"
            )

        rows = c.fetchall()
        updates = []

        print(f"🔄 Categorizing {len(rows)} transactions against {len(rules)} rules...")

        for tx_id, merchant in rows:
            if not merchant:
                continue
            merch_lower = merchant.lower()

            for key, cat in rules:
                if key in merch_lower:
                    updates.append((cat, tx_id))
                    break  # Stop at first match (longest)

        if updates:
            c.executemany("UPDATE transactions SET category=? WHERE id=?", updates)
            conn.commit()
            print(f"✅ Updated {len(updates)} transactions.")

        conn.close()


# --- MAIN CONTROLLER ---
class FinanceTracker:
    def __init__(self):
        self.db = DatabaseEngine()
        self.llm = LLMExtractor()
        self.categorizer = Categorizer(self.db)

    def get_file_hash(self, filepath):
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def process_file(self, filepath):
        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return

        # 1. Duplicate Check
        f_hash = self.get_file_hash(filepath)
        if self.db.is_file_processed(f_hash):
            print(f"⏭️ Skipping {os.path.basename(filepath)} (Already in Vault)")
            return

        print(f"📂 Processing: {os.path.basename(filepath)}...")

        # 2. Text Extraction
        chunks = []
        ext = filepath.lower().split(".")[-1]

        if ext == "pdf":
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        chunks.append(text)
        elif ext == "csv":
            try:
                df = pd.read_csv(filepath)
                # Convert to string chunks
                for i in range(0, len(df), CHUNK_SIZE_LINES):
                    chunks.append(
                        df.iloc[i : i + CHUNK_SIZE_LINES].to_string(index=False)
                    )
            except Exception as e:
                print(f"CSV Error: {e}")
                return

        # 3. LLM Analysis
        all_transactions = []
        for i, chunk in enumerate(chunks):
            print(f"  Thinking... (Chunk {i + 1}/{len(chunks)})")
            extracted = self.llm.extract_chunk(chunk, is_csv=(ext == "csv"))
            all_transactions.extend(extracted)

        # 4. Save & Finalize
        count = self.db.save_transactions(all_transactions, os.path.basename(filepath))
        self.db.log_file_processed(f_hash, os.path.basename(filepath))
        print(f"🎉 Saved {count} new transactions.")

        # 5. Auto-Categorize
        self.categorizer.run_updates()

    def teach(self, keyword, category):
        self.categorizer.add_rule(keyword, category)

    def export_to_excel(self, filename="finance_report.xlsx"):
        conn = self.db.get_connection()
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
        df.to_excel(filename, index=False)
        print(f"📊 Report exported to {filename}")
        conn.close()


# --- USER INTERFACE ---
if __name__ == "__main__":
    tracker = FinanceTracker()

    # --- EXAMPLE USAGE ---

    # 1. Teach it some initial rules (You can add more later)
    # tracker.teach("uber", "Transport")
    # tracker.teach("zomato", "Food")
    # tracker.teach("netflix", "Subscription")
    # tracker.teach("salary", "Income")

    # 2. Process Files (Put your file path here)
    # tracker.process_file("my_bank_statement.pdf")

    # 3. Export Data
    # tracker.export_to_excel()

    print("\n--- System Ready ---")
    print("Use: tracker.process_file('path/to/pdf')")
    print("Use: tracker.teach('merchant_keyword', 'Category')")
    print("Use: tracker.export_to_excel()")
