import os
import hashlib
import pandas as pd
import pdfplumber
import concurrent.futures
from tqdm import tqdm

from db import DatabaseEngine
from llm import LLMExtractor, CHUNK_SIZE_LINES
from categorizer import Categorizer
from constants import PaymentMethod, FileType

ROW_BATCH_SIZE = int(os.getenv("ROW_BATCH_SIZE", "1"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "2"))

print(f"⚙️ Config: Batch Size={ROW_BATCH_SIZE}, Workers={MAX_WORKERS}")


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

    def infer_payment_method(self, filepath, first_page_text="") -> PaymentMethod:
        """
        Determines payment method using 3-step priority:
        1. AI Analysis of Page 1 Content (Smartest)
        2. Keyword Search in Content (Fallback)
        3. Filename Analysis (Last Resort / Strongest Signal)
        """
        fname = os.path.basename(filepath).lower()
        text_lower = first_page_text.lower() if first_page_text else ""

        # --- STEP 1: AI Analysis ---
        # We ask the LLM to read the header and classify it
        if first_page_text:
            ai_guess = self.llm.identify_instrument(first_page_text)
            # Map the string result back to our Enum
            for pm in PaymentMethod:
                if pm.value.lower() == ai_guess.lower():
                    print(f"  🧠 AI Identified Instrument: {pm.value}")
                    return pm

        # --- STEP 2: Content Keywords (Fallback) ---
        if "credit card" in text_lower:
            return PaymentMethod.CREDIT_CARD
        if "upi" in text_lower:
            return PaymentMethod.UPI
        if "savings" in text_lower or "account statement" in text_lower:
            return PaymentMethod.BANK_TRANSFER

        # --- STEP 3: Filename Check (Final / Strongest Signal) ---
        if "credit" in fname and "card" in fname:
            return PaymentMethod.CREDIT_CARD
        if "debit" in fname and "card" in fname:
            return PaymentMethod.DEBIT_CARD
        if "upi" in fname:
            return PaymentMethod.UPI
        if "bank" in fname:
            return PaymentMethod.BANK_TRANSFER

        return PaymentMethod.UNKNOWN

    def _process_task(self, task_args):
        """Helper for parallel execution"""
        text, file_type = task_args
        return self.llm.extract_chunk(text, file_type=file_type)

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
        ext = filepath.lower().split(".")[-1]

        # Collection list for parallel tasks
        tasks = []

        # Default detected method (Enum)
        detected_method = PaymentMethod.UNKNOWN

        # --- STRATEGY: TABLE ROW-BY-ROW (100% Accuracy) ---
        if ext == "pdf":
            with pdfplumber.open(filepath) as pdf:
                # 0. Detect Method from Page 1
                if len(pdf.pages) > 0:
                    first_page = pdf.pages[0].extract_text() or ""
                    detected_method = self.infer_payment_method(filepath, first_page)
                    print(f"  ℹ️  Detected Instrument: {detected_method.value}")

                for i, page in enumerate(pdf.pages):
                    # 1. Try Table Extraction
                    tables = page.extract_tables()

                    if tables:
                        print(f"    Found {len(tables)} tables. Queuing rows...")
                        for table in tables:
                            current_batch = []
                            for row in table:
                                # 1. Clean row content
                                row_values = [
                                    str(field).strip() for field in row if field
                                ]
                                row_str = " ".join(row_values).lower()

                                # 2. Skip known Headers
                                if "date" in row_str and "amount" in row_str:
                                    continue

                                # 3. Skip Empty/Junk Rows
                                if len(row_values) < 2:
                                    continue

                                # 4. Skip "Page x of y" lines
                                if "page" in row_str and "of" in row_str:
                                    continue

                                # --- BATCHING LOGIC START ---
                                current_batch.append(str(row))

                                # If batch is full, queue it
                                if len(current_batch) >= ROW_BATCH_SIZE:
                                    # Join with newlines to mimic a mini-table
                                    batch_text = "\n".join(current_batch)
                                    tasks.append((batch_text, FileType.CSV))
                                    current_batch = []

                            # Queue remaining rows in the batch
                            if current_batch:
                                batch_text = "\n".join(current_batch)
                                tasks.append((batch_text, FileType.CSV))
                                # --- BATCHING LOGIC END ---

                    else:
                        # 2. Fallback to Raw Text
                        print("    ⚠️ No tables found. Falling back to raw text...")
                        text = page.extract_text()
                        if text:
                            # Queue Task (Preserving FileType.PDF logic for raw text)
                            tasks.append((text, FileType.PDF))

        elif ext == "csv":
            # For CSV, try filename inference
            detected_method = self.infer_payment_method(filepath, "")
            try:
                df = pd.read_csv(filepath)
                for i in range(0, len(df), CHUNK_SIZE_LINES):
                    chunks = df.iloc[i : i + CHUNK_SIZE_LINES].to_string(index=False)
                    # Queue Task (Preserving FileType.CSV logic)
                    tasks.append((chunks, FileType.CSV))
            except Exception as e:
                print(f"CSV Error: {e}")
                return

        # --- PARALLEL EXECUTION ---
        if not tasks:
            print("  ⚠️ No data found to process.")
            return

        print(
            f"  🚀 Analyzing {len(tasks)} batches with {MAX_WORKERS} parallel workers..."
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks to the pool
            futures = [executor.submit(self._process_task, t) for t in tasks]

            # Process results as they complete
            for future in tqdm(
                concurrent.futures.as_completed(futures), total=len(futures)
            ):
                try:
                    result = future.result()
                    if result:
                        all_transactions.extend(result)
                except Exception as e:
                    print(f"  ⚠️ Task failed: {e}")

        # 4. Save & Finalize (Pass Enum)
        count = self.db.save_transactions(
            all_transactions, os.path.basename(filepath), detected_method
        )
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
