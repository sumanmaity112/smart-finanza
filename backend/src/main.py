from tracker import FinanceTracker

# --- USER INTERFACE ---
if __name__ == "__main__":
    tracker = FinanceTracker()

    # --- EXAMPLE USAGE ---

    # 1. Teach it some initial rules (You can add more later)
    # tracker.teach("uber", "Transport")
    # tracker.teach("zomato", "Food")
    # tracker.teach("netflix", "Subscription")
    # tracker.teach("salary", "Income")

    # 2. Process Files (Put your file path here)
    # tracker.process_file("my_bank_statement.pdf")

    # 3. Export Data
    # tracker.export_to_excel()

    print("\n--- System Ready ---")
    print("Use: tracker.process_file('path/to/pdf')")
    print("Use: tracker.teach('merchant_keyword', 'Category')")
    print("Use: tracker.export_to_excel()")
