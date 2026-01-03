import os
from ollama import Client
import json
import re
from typing import List, Dict
from constants import FileType

MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5")
CHUNK_SIZE_LINES = int(os.getenv("CHUNK_SIZE_LINES", "20"))


class LLMExtractor:
    def __init__(self, model=MODEL_NAME):
        self.model = model

    def create_client(self):
        return Client()

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

    def identify_instrument(self, text_chunk: str) -> str:
        prompt = f"""
        Analyze the header text of this financial document.
        Identify the payment instrument or account type.
        
        Return ONLY one of the following exact strings:
        - "Credit Card"
        - "UPI"
        - "Bank Transfer"
        - "Debit Card"
        - "Unknown"

        Text:
        {text_chunk[:2000]} 
        """

        try:
            response = self.create_client().chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0},
            )
            result = (
                response["message"]["content"].strip().replace('"', "").replace("'", "")
            )
            valid_types = ["Credit Card", "UPI", "Bank Transfer", "Debit Card"]
            for v in valid_types:
                if v.lower() in result.lower():
                    return v
            return "Unknown"
        except Exception:
            return "Unknown"

    def extract_chunk(self, text_chunk: str, file_type: FileType) -> List[Dict]:
        # Determine context based on Enum
        if file_type == FileType.CSV:
            context_hint = "raw CSV rows"
        else:
            context_hint = "unstructured text from a PDF bank statement"

        prompt = f"""
        You are a strict financial data parser. Extract transactions from the {context_hint} below.
        
        ### CRITICAL RULES (Follow these or fail)
        1. **Truthfulness**: Only extract data explicitly present in the Input Text. DO NOT invent transactions. 
           - If the input text is just headers, footers, or empty, return an empty list: [].
           
        2. **Date**: Input is likely DD/MM/YYYY. Convert strictly to YYYY-MM-DD.
        
        3. **Merchant**: Extract the CLEAN name.
           - Remove cities (e.g. "MUMBAI", "HYD"), "POS", and "Value Date".
           - **EXCEPTION**: Do NOT remove "Payment Received" or "Fuel Surcharge Waiver". Keep them as the merchant name.
           - Example: "PAYMENT RECEIVED BBPS" -> "Payment Received BBPS"
           - Example: "FUEL SURCHARGE WAIVER" -> "Fuel Surcharge Waiver"
           
        4. **Amount**: ALWAYS Positive.
        
        5. **Type**: "DEBIT" (Spending) or "CREDIT" (Refund/Income/Waiver).
        
        6. **Transaction ID**: Extract the unique identifier.
           - Look for labels like "Ref No", "Txn ID", "Reference".
           - **IMPORTANT**: Capture long numeric strings (e.g., "19999999...") often found in waivers/payments.

        7. **Notes**: Capture any remaining details (Category, Narration, Remarks).
           - If the row has a "Category" column (e.g., "Professional Service"), put it here.
           - If the row has narration (e.g., "IMPS/1234/Remark"), put it here.
           - **If there is NO extra text, return an empty string ""**.
           
        8. **Structure**: Return a JSON List.
        
        ### INPUT TEXT
        {text_chunk}

        ### EXAMPLE OUTPUT (Use this format, but NOT this data)
        [
            {{
                "date": "2025-12-31",
                "merchant": "EXAMPLE_MERCHANT_ONLY", 
                "amount": 100.00,
                "txn_type": "DEBIT",
                "payment_method": "Unknown",
                "transaction_id": "REF123456789",
                "notes": "Retail Outlet Services" 
            }}
        ]
        """

        try:
            response = self.create_client().chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0},
            )
            clean_json = self.clean_json_response(response["message"]["content"])
            data = json.loads(clean_json)

            # --- POST-PROCESSING FILTERS ---
            transactions = []
            if isinstance(data, dict):
                if "transactions" in data:
                    transactions = data["transactions"]
                else:
                    transactions = [data]
            elif isinstance(data, list):
                transactions = data

            valid_txns = []
            for t in transactions:
                # 1. Skip if it matches the example merchant
                if "EXAMPLE_MERCHANT" in t.get("merchant", "").upper():
                    continue

                # 2. Skip if no amount
                if not t.get("amount"):
                    continue

                # 3. Date Sanitization
                if not re.match(r"\d{4}-\d{2}-\d{2}", t.get("date", "")):
                    continue

                valid_txns.append(t)

            return valid_txns

        except Exception:
            # print(f"❌ LLM Error: {e}")
            return []

    def text_to_sql(self, user_question: str, schema: str) -> dict:
        """
        Convert natural language to SQL + Visualization Type.
        Returns JSON: {"sql": "...", "visualization": "..."}
        """
        prompt = f"""
        You are a SQLite expert and Data Analyst. 
        1. Generate a valid SQL query to answer the question.
        2. Determine the best visualization type for the result.

        ### SCHEMA
        {schema}

        ### VISUALIZATION TYPES
        - "bar": Comparing categories (e.g. spending by category/merchant).
        - "line": Trends over time (e.g. monthly spending).
        - "pie": Parts of a whole (e.g. % split).
        - "metric": Single number (e.g. total spent).
        - "table": Detailed lists.

        ### CRITICAL SQL RULES
        1. Filter txn_type='DEBIT' for spending, 'CREDIT' for income.
        2. Use strftime('%Y-%m', date) for monthly grouping.
        3. ALWAYS use case-insensitive matching (LOWER(col) LIKE ...).
        4. DO NOT add filters unless explicitly asked.

        ### QUESTION
        {user_question}

        ### OUTPUT FORMAT (JSON ONLY)
        {{
            "sql": "SELECT ...",
            "visualization": "bar"
        }}
        """
        try:
            response = self.create_client().chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0},
            )
            return json.loads(response["message"]["content"])
        except Exception as e:
            return {"sql": f"-- Error: {str(e)}", "visualization": "table"}

    def analyze_question(self, user_question: str, schema: str) -> dict:
        """
        Analyze user question to determine intent.
        Handles greetings/conversation as DIRECT_ANSWER to avoid bad SQL.
        """
        analysis_prompt = f"""
        You are a financial analyst AI. Analyze the user's input to determine the next action.
        
        ### USER INPUT
        "{user_question}"
        
        ### INSTRUCTIONS
        Determine the intent and respond with exactly ONE of these options:
        
        Option 1: If the input is a greeting, conversation, or general knowledge question that DOES NOT require specific database data.
        Response: "DIRECT_ANSWER: <A polite conversational reply or general answer>"
        Examples: 
        - "hi" -> "DIRECT_ANSWER: Hello! How can I help you with your finances today?"
        - "hey there" -> "DIRECT_ANSWER: Hi! Ask me about your spending trends or budget."
        - "what is inflation?" -> "DIRECT_ANSWER: Inflation is..."

        Option 2: If the input requires querying the transaction database.
        Response: "SQL_QUERY_NEEDED"
        Examples:
        - "how much did I spend on food?" -> "SQL_QUERY_NEEDED"
        - "show my top merchants" -> "SQL_QUERY_NEEDED"

        Your Response:
        """

        try:
            # 1. Check Intent (Text Mode)
            analysis_response = self.create_client().chat(
                model=self.model,
                messages=[{"role": "user", "content": analysis_prompt}],
                options={"temperature": 0},
            )
            analysis = analysis_response["message"]["content"].strip()

            # Case A: Direct Answer (Greetings, etc.)
            if "DIRECT_ANSWER" in analysis:
                answer = analysis.replace("DIRECT_ANSWER:", "").strip()
                # Fallback if model forgets to put a message after the tag
                if not answer: answer = "Hello! How can I help with your financial data?"
                return {
                    "type": "direct_answer",
                    "answer": answer
                }

            # Case B: SQL Needed -> Call the JSON generator
            # We assume anything else implies we need to try querying
            result = self.text_to_sql(user_question, schema)

            return {
                "type": "sql_query",
                "sql": result.get("sql"),
                "visualization": result.get("visualization", "table")
            }

        except Exception as e:
            return {"type": "error", "message": f"Analysis failed: {str(e)}"}
