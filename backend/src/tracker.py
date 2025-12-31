import os
import hashlib
import pandas as pd
from db import DatabaseEngine
from llm import LLMExtractor, CHUNK_SIZE_LINES
from categorizer import Categorizer

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
        f_hash = self.get_file_hash(filepath)
        if self.db.is_file_processed(f_hash):
            print(f"⏭️ Skipping {os.path.basename(filepath)} (Already in Vault)")
            return
        print(f"📂 Processing: {os.path.basename(filepath)}...")
        chunks = []
        ext = filepath.lower().split(".")[-1]
        if ext == "pdf":
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        chunks.append(text)
        elif ext == "csv":
            try:
                df = pd.read_csv(filepath)
                for i in range(0, len(df), CHUNK_SIZE_LINES):
                    chunks.append(df.iloc[i : i + CHUNK_SIZE_LINES].to_string(index=False))
            except Exception as e:
                print(f"CSV Error: {e}")
                return
        all_transactions = []
        for i, chunk in enumerate(chunks):
            print(f"  Thinking... (Chunk {i + 1}/{len(chunks)})")
            extracted = self.llm.extract_chunk(chunk, is_csv=(ext == "csv"))
            all_transactions.extend(extracted)
        count = self.db.save_transactions(all_transactions, os.path.basename(filepath))
        self.db.log_file_processed(f_hash, os.path.basename(filepath))
        print(f"🎉 Saved {count} new transactions.")
        self.categorizer.run_updates()

    def teach(self, keyword, category):
        self.categorizer.add_rule(keyword, category)

    def export_to_excel(self, filename="finance_report.xlsx"):
        conn = self.db.get_connection()
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
        df.to_excel(filename, index=False)
        print(f"📊 Report exported to {filename}")
        conn.close()
