from .backend import get_backend

db_engine, llm_engine, tracker = get_backend()


def run_query(query):
    """Execute SQL query using DatabaseEngine"""
    return db_engine.run_query(query)


def get_database_context():
    """Get actual values from database to help LLM generate accurate queries"""
    context = {
        'categories': [],
        'merchants': [],
        'payment_methods': []
    }

    # Get unique categories
    categories_df, _ = run_query("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category")
    if categories_df is not None and not categories_df.empty:
        context['categories'] = categories_df['category'].tolist()

    # Get top merchants
    merchants_df, _ = run_query("SELECT DISTINCT merchant FROM transactions WHERE merchant IS NOT NULL ORDER BY merchant LIMIT 50")
    if merchants_df is not None and not merchants_df.empty:
        context['merchants'] = merchants_df['merchant'].tolist()

    # Get payment methods
    methods_df, _ = run_query("SELECT DISTINCT payment_method FROM transactions WHERE payment_method IS NOT NULL ORDER BY payment_method")
    if methods_df is not None and not methods_df.empty:
        context['payment_methods'] = methods_df['payment_method'].tolist()

    return context


def ask_ai_analyst(user_question):
    """
    Analyze user question and either:
    1. Convert to SQL if it requires database query
    2. Answer directly if it's general advice or calculation
    """
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

    # Get actual database values for context
    db_context = get_database_context()

    # Build enhanced schema with actual values
    enhanced_schema = schema + f"""
    
    ### ACTUAL DATA IN DATABASE:
    
    Available Categories: {', '.join(db_context['categories'])}
    
    Sample Merchants: {', '.join(db_context['merchants'][:20])}
    
    Payment Methods: {', '.join(db_context['payment_methods'])}
    
    ### IMPORTANT SQL RULES:
    - Always use LIKE with wildcards for text matching (e.g., WHERE category LIKE '%Health%')
    - Use LOWER() or UPPER() for case-insensitive matching
    - For categories, use: WHERE LOWER(category) = LOWER('Health')
    - For merchants, use: WHERE merchant LIKE '%Swiggy%' (case-insensitive)
    """

    # Delegate to LLMExtractor - all AI logic happens there
    return llm_engine.analyze_question(user_question, enhanced_schema)
