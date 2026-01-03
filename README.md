# Smart Finanza

Smart Finanza is a personal finance dashboard and analytics tool powered by LLMs (Ollama) and Streamlit. It helps you
analyze, categorize, and visualize your financial transactions from PDFs and CSVs, with AI-powered extraction and insights.

## Features

- 📂 **Import Statements**: Upload PDF or CSV bank/credit card statements. AI extracts and normalizes transactions.
- 🏦 **Database**: All transactions are stored in a local SQLite database for fast querying and analytics.
- 📊 **Dashboard**: Visualize income, expenses, savings, category splits, and trends over time.
- 🧠 **AI Analyst**: Ask questions about your finances in natural language. The LLM can answer or generate SQL for custom queries.
- 🏷️ **Rules Engine**: Define custom rules to auto-categorize merchants/transactions.
- 📋 **Transaction Viewer**: Browse all transactions in a searchable, filterable table.
- 🔒 **Local-First**: All data stays on your machine. No cloud upload required.

## Quickstart

### 1. Requirements

- Python 3.14+
- [Ollama](https://ollama.com/) (for LLM-powered extraction and Q&A)
- [uv](https://github.com/astral-sh/uv) (for fast Python dependency management)

### 2. Setup

```bash
# Clone this repo
$ git clone <this-repo-url>
$ cd smart-finanza/backend

# Create a virtual environment and install dependencies
$ make provision

# Download the Ollama model (qwen2.5 or your configured model)
$ ollama pull qwen2.5

# Start Ollama (in a separate terminal)
$ ollama serve

# Run the app
$ make run
```

### 3. Usage

- Upload your bank/credit card statements (PDF/CSV) in the sidebar.
- Explore the dashboard, ask questions, and manage rules.
- All data is stored locally in `finance_vault.db` (or as configured).

## Configuration

You can set environment variables in a `.env` file (optional):

```
DB_NAME=finance_vault.db
MODEL_NAME=qwen2.5
CHUNK_SIZE_LINES=20
```

## Development

- Use `make provision` to set up the environment.
- Use `make run` to start the app.
- Use `make test` to run tests (if available).
- Use `make fix-lint` to auto-format and lint code.

---

_Smart Finanza: AI-powered personal finance, on your terms._

> **Inspired by:** [finanza](https://github.com/sumanmaity112/finanza)
