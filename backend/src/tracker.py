import os
import hashlib
import pandas as pd
import pdfplumber
from db import DatabaseEngine
from llm import LLMExtractor, CHUNK_SIZE_LINES
from categorizer import Categorizer


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

        all_transactions = []
        ext = filepath.lower().split('.')[-1]

        # --- STRATEGY: TABLE ROW-BY-ROW (100% Accuracy) ---
        if ext == 'pdf':
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    print(f"  📄 Scanning Page {i+1}...")

                    # 1. Try Table Extraction
                    tables = page.extract_tables()

                    if tables:
                        print(f"    Found {len(tables)} tables. analyzing row-by-row...")
                        for table in tables:
                            for row in table:
                                # Pre-filtering: Skip empty rows or headers to save time
                                # We check if the row has at least a Date-like string or a number
                                row_str = str(row).lower()
                                if "date" in row_str or "amount" in row_str or "balance" in row_str:
                                    continue # Skip headers
                                if not any(field and len(str(field)) > 3 for field in row):
                                    continue # Skip empty/junk rows

                                # Send SINGLE ROW to LLM
                                # print(f"    > Analyzing row: {row[:2]}...") # Optional: clear clutter
                                extracted = self.llm.extract_chunk(str(row), is_csv=True)
                                all_transactions.extend(extracted)

                    else:
                        # 2. Fallback to Raw Text
                        print(f"    ⚠️ No tables found. Falling back to raw text...")
                        text = page.extract_text()
                        if text:
                            extracted = self.llm.extract_chunk(text, is_csv=False)
                            all_transactions.extend(extracted)

        elif ext == 'csv':
            # CSVs are usually cleaner, but we can do row-by-row here too if needed
            # For now, we keep chunking for CSVs as they format easier
            try:
                df = pd.read_csv(filepath)
                for i in range(0, len(df), CHUNK_SIZE_LINES):
                    chunks = df.iloc[i:i+CHUNK_SIZE_LINES].to_string(index=False)
                    extracted = self.llm.extract_chunk(chunks, is_csv=True)
                    all_transactions.extend(extracted)
            except Exception as e:
                print(f"CSV Error: {e}")
                return

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
