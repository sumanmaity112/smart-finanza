import os
import ollama
import json
from typing import List, Dict

MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5")
CHUNK_SIZE_LINES = int(os.getenv("CHUNK_SIZE_LINES", "20"))


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
        context_hint = "raw CSV rows" if is_csv else "unstructured text from a PDF bank statement"

        prompt = f"""
        You are a financial data parser. Your job is to convert raw text into a structured JSON list.
        
        ### INPUT CONTEXT
        The text below contains transaction rows.
        - It may look like a table with columns: [Date] [Description/Details] [Amount/Debit/Credit] [Ref No].
        - Ignore header lines like "Opening Balance", "Page 1 of 5", "Total Due".
        - Ignore footer lines or legal disclaimers.

        ### EXTRACTION RULES
        1. **Date**: Convert to YYYY-MM-DD.
        2. **Merchant**: Extract the CLEAN name (e.g., remove "POS", "HYD", numbers).
           - "UBER *TRIP 1234" -> "Uber"
           - "PAYMENT RECEIVED - THANK YOU" -> "Payment Received"
        3. **Amount**: 
           - **Negative (-)** for DEBITS (Spending/Purchases).
           - **Positive (+)** for CREDITS (Refunds/Income/Deposits).
           - If text says "Dr" or column is "Debit", make it negative.
        4. **Payment Method**: Infer if possible (UPI, IMPS, NEFT, ACH, CASH, CARD). Default: "Unknown".
        5. **Transaction ID**: Look for alphanumeric codes (e.g., "TXN882", "Ref: 9928").

        ### INPUT DATA
        {text_chunk}

        ### OUTPUT FORMAT
        Return a valid JSON List of objects. Do not return a single object.
        
        Example Output:
        [
            {{
                "date": "2025-01-15",
                "merchant": "Amazon",
                "amount": -450.00,
                "payment_method": "Credit Card",
                "transaction_id": "TXN998877",
                "notes": "Purchase of electronics"
            }}
        ]
        """

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                format='json',
                options={'temperature': 0}
            )
            clean_json = self.clean_json_response(response['message']['content'])
            data = json.loads(clean_json)

            # --- ROBUSTNESS FIX ---
            # Even with the new prompt, we keep this safety check
            # to handle cases where the model returns a single dict.

            # Case 1: Wrapped in a "transactions" key (Common behavior)
            if isinstance(data, dict) and 'transactions' in data:
                return data['transactions']

            # Case 2: Returned a single dict object
            if isinstance(data, dict):
                return [data]

            # Case 3: Returned a list (Perfect)
            if isinstance(data, list):
                return data

            return []

        except Exception as e:
            print(f"❌ LLM Error: {e}")
            return []
