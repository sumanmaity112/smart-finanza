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

    def text_to_sql(self, user_question: str, schema: str) -> str:
        """Convert natural language question to SQL query"""
        prompt = f"""
        You are a SQLite expert. Convert the user's question into a valid SQL query.
        
        ### SCHEMA & CONTEXT
        {schema}
        
        ### CRITICAL RULES
        1. Return ONLY the raw SQL query. No markdown, no explanations.
        2. ALWAYS use case-insensitive matching:
           - For exact category match: WHERE LOWER(category) = LOWER('Health')
           - For partial merchant match: WHERE LOWER(merchant) LIKE LOWER('%swiggy%')
        3. Filter txn_type='DEBIT' for spending, 'CREDIT' for income.
        4. Use strftime('%Y-%m', date) for monthly grouping.
        5. Use the ACTUAL category/merchant names provided in the schema above.
        
        ### QUESTION
        {user_question}
        
        ### SQL
        """
        try:
            response = self.create_client().chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0},
            )
            sql = response["message"]["content"].strip()
            if sql.startswith("```"):
                sql = sql.replace("```sql", "").replace("```", "")
            return sql.strip()
        except Exception as e:
            return f"-- Error: {str(e)}"

    def analyze_question(self, user_question: str, schema: str) -> dict:
        """
        Analyze user question to determine if it needs database access or can be answered directly.
        Returns dict with 'type' (either 'sql_query' or 'direct_answer') and corresponding content.
        """
        analysis_prompt = f"""
        You are a financial analyst AI. Analyze the user's question and determine if it requires database access.
        
        ### USER QUESTION
        {user_question}
        
        ### AVAILABLE DATABASE SCHEMA
        {schema}
        
        ### INSTRUCTIONS
        1. If the question requires accessing transaction data from the database, respond with: "SQL_QUERY_NEEDED"
        2. If the question is about general financial advice, tips, calculations, or concepts that don't need the database, respond with: "DIRECT_ANSWER: <your answer>"
        
        Examples:
        - "How much did I spend on Swiggy?" -> SQL_QUERY_NEEDED
        - "What's my total spending last month?" -> SQL_QUERY_NEEDED
        - "What is a good savings rate?" -> DIRECT_ANSWER: A good savings rate is typically 20-30% of your income...
        - "Should I invest in mutual funds?" -> DIRECT_ANSWER: Mutual funds can be a good investment option...
        - "How to budget better?" -> DIRECT_ANSWER: Here are some budgeting tips...
        
        ### YOUR RESPONSE
        """

        try:
            analysis_response = self.create_client().chat(
                model=self.model,
                messages=[{'role': 'user', 'content': analysis_prompt}],
                options={'temperature': 0}
            )

            analysis = analysis_response['message']['content'].strip()

            # If it's a direct answer, return it
            if analysis.startswith("DIRECT_ANSWER:"):
                return {
                    'type': 'direct_answer',
                    'answer': analysis.replace("DIRECT_ANSWER:", "").strip()
                }

            # Otherwise, generate SQL query
            sql = self.text_to_sql(user_question, schema)
            return {
                'type': 'sql_query',
                'sql': sql
            }
        except Exception as e:
            return {
                'type': 'error',
                'message': f"Failed to analyze question: {str(e)}"
            }
