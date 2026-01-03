from .backend import get_backend

db_engine, llm_engine, tracker = get_backend()


def run_query(query):
    """Execute SQL query using DatabaseEngine"""
    return db_engine.run_query(query)


def get_database_context():
    """Get actual values from database to help LLM generate accurate queries"""
    context = {"categories": [], "merchants": [], "payment_methods": []}

    # Simple safeguard against empty DB
    try:
        categories_df, _ = run_query(
            "SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category"
        )
        if categories_df is not None and not categories_df.empty:
            context["categories"] = categories_df["category"].tolist()

        merchants_df, _ = run_query(
            "SELECT DISTINCT merchant FROM transactions WHERE merchant IS NOT NULL ORDER BY merchant LIMIT 50"
        )
        if merchants_df is not None and not merchants_df.empty:
            context["merchants"] = merchants_df["merchant"].tolist()

        methods_df, _ = run_query(
            "SELECT DISTINCT payment_method FROM transactions WHERE payment_method IS NOT NULL ORDER BY payment_method"
        )
        if methods_df is not None and not methods_df.empty:
            context["payment_methods"] = methods_df["payment_method"].tolist()
    except Exception:
        pass  # DB might be empty

    return context


def ask_ai_analyst(user_question, chat_history=None):
    """
    1. Contextualize question using history.
    2. Analyze intent.
    3. Generate SQL or Direct Answer.
    """
    # 1. Contextualize
    if chat_history and len(chat_history) > 0:
        # Extract just role/content to keep tokens low
        clean_history = [
            {"role": m["role"], "content": m["content"]} for m in chat_history
        ]
        refined_question = llm_engine.contextualize_question(clean_history)
    else:
        refined_question = user_question

    schema = """
    TABLE transactions (
        id INTEGER PRIMARY KEY,
        date TEXT (YYYY-MM-DD),
        merchant TEXT,
        amount REAL (Always positive),
        txn_type TEXT ('DEBIT' or 'CREDIT'),
        payment_method TEXT,
        category TEXT,
        notes TEXT
    )
    """

    db_context = get_database_context()

    enhanced_schema = (
        schema
        + f"""
    ### ACTUAL DATA SAMPLES:
    Categories: {", ".join(db_context["categories"][:20])}
    Merchants: {", ".join(db_context["merchants"][:20])}
    Payment Methods: {", ".join(db_context["payment_methods"])}
    
    ### IMPORTANT SQL RULES:
    - Always use LIKE with wildcards for text matching (e.g., WHERE category LIKE '%Health%')
    - Use LOWER() or UPPER() for case-insensitive matching
    - For categories, use: WHERE LOWER(category) = LOWER('Health')
    - For merchants, use: WHERE merchant LIKE '%Swiggy%' (case-insensitive)
    """
    )

    # 2. Analyze & Execute
    return llm_engine.analyze_question(refined_question, enhanced_schema)
