import os
import ollama
import json
from typing import List, Dict

MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5")
CHUNK_SIZE_LINES = int(os.getenv("CHUNK_SIZE_LINES", "20"))

class LLMExtractor:
    def __init__(self, model=MODEL_NAME):
        self.model = model

    def clean_json_response(self, response_text):
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
        4. Merchant: Clean up the name (e.g., 'UBER *TRIP 882' -> 'Uber').
        5. Payment Method: Infer from text (UPI, Card, NEFT, etc.). Default 'Unknown'.
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
                options={"temperature": 0},
            )
            clean_json = self.clean_json_response(response["message"]["content"])
            data = json.loads(clean_json)
            if isinstance(data, dict):
                return data.get("transactions", [])
            return data
        except Exception as e:
            print(f"❌ LLM Error: {e}")
            return []
