from db import DatabaseEngine

class Categorizer:
    def __init__(self, db: DatabaseEngine):
        self.db = db

    def add_rule(self, keyword: str, category: str):
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
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT keyword, category FROM category_map")
        rules = c.fetchall()
        rules.sort(key=lambda x: len(x[0]), reverse=True)
        if target_keyword:
            c.execute(
                "SELECT id, merchant FROM transactions WHERE merchant LIKE ?",
                (f"%{target_keyword}%",),
            )
        else:
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
                    break
        if updates:
            c.executemany("UPDATE transactions SET category=? WHERE id=?", updates)
            conn.commit()
            print(f"✅ Updated {len(updates)} transactions.")
        conn.close()
