from db import DatabaseEngine


# --- CATEGORIZATION ENGINE ---
class Categorizer:
    def __init__(self, db: DatabaseEngine):
        self.db = db

    def add_rule(self, keyword: str, category: str):
        """Learns a new rule and updates PAST data immediately."""
        conn = self.db.get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO category_map (keyword, category) VALUES (?, ?)",
            (keyword.lower(), category),
        )
        conn.commit()
        conn.close()
        print(f"🧠 Learned: '{keyword}' -> '{category}'")
        self.run_updates(target_keyword=keyword)

    def run_updates(self, target_keyword=None):
        """Applies rules to Uncategorized transactions."""
        conn = self.db.get_connection()
        c = conn.cursor()

        # 1. Fetch Rules
        c.execute("SELECT keyword, category FROM category_map")
        rules = c.fetchall()
        # Sort by length desc so "Amazon AWS" matches before "Amazon"
        rules.sort(key=lambda x: len(x[0]), reverse=True)

        # 2. Fetch Transactions to Process
        if target_keyword:
            # Only update transactions matching the new keyword
            c.execute(
                "SELECT id, merchant FROM transactions WHERE merchant LIKE ?",
                (f"%{target_keyword}%",),
            )
        else:
            # Update ALL uncategorized
            c.execute(
                "SELECT id, merchant FROM transactions WHERE category = 'Uncategorized'"
            )

        rows = c.fetchall()
        updates = []

        print(f"🔄 Categorizing {len(rows)} transactions against {len(rules)} rules...")

        for tx_id, merchant in rows:
            if not merchant:
                continue
            merch_lower = merchant.lower()

            for key, cat in rules:
                if key in merch_lower:
                    updates.append((cat, tx_id))
                    break  # Stop at first match (longest)

        if updates:
            c.executemany("UPDATE transactions SET category=? WHERE id=?", updates)
            conn.commit()
            print(f"✅ Updated {len(updates)} transactions.")

        conn.close()
