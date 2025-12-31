# 💰 Smart Finanza
---

A privacy-focused, AI-powered financial analysis tool that runs 100% locally on your machine. It uses Ollama (Qwen 2.5 /
Llama 3) to extract structured data from PDF bank statements and CSV files, automatically categorizes transactions based
on your personal rules, and stores everything in a persistent SQLite vault.

🔒 Privacy Note: No financial data leaves your computer. All processing happens on your local hardware.

✨ Features
📄 Multi-Format Support: Ingests PDF (Bank Statements) and CSV (Spreadsheets) automatically.

🧠 AI Extraction: Uses LLMs to parse messy layouts, extract merchant names, dates, amounts, and transaction IDs.

🔄 Smart De-Duplication: Uses file hashing to ensure you never double-count a statement, even if you run it twice.

🏷️ Auto-Learning Categories: Teach the system once ("uber" -> "Transport"), and it auto-updates all past and future
transactions.

💾 Persistent Vault: Stores all data in a local finance_vault.db (SQLite) file.

📊 Excel Export: One-click export to .xlsx for analysis in Excel or Google Sheets.
