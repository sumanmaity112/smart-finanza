from tracker import FinanceTracker

if __name__ == "__main__":
    tracker = FinanceTracker()
    # --- EXAMPLE USAGE ---
    # tracker.teach("uber", "Transport")
    # tracker.teach("zomato", "Food")
    # tracker.teach("netflix", "Subscription")
    # tracker.teach("salary", "Income")
    # tracker.process_file("my_bank_statement.pdf")
    # tracker.export_to_excel()
    print("\n--- System Ready ---")
    print("Use: tracker.process_file('path/to/pdf')")
    print("Use: tracker.teach('merchant_keyword', 'Category')")
    print("Use: tracker.export_to_excel()")
