import streamlit as st


def render_rules_tab(tracker, run_query):
    st.subheader("🧠 Teach the System")
    c1, c2 = st.columns(2)
    with c1:
        new_keyword = st.text_input(
            "If merchant name contains:", placeholder="e.g. STARBUCKS"
        )
    with c2:
        new_category = st.text_input("Set Category to:", placeholder="e.g. Coffee")
    if st.button("Add Rule"):
        if new_keyword and new_category:
            tracker.teach(new_keyword, new_category)
            st.success(
                f"Rule Added: '{new_keyword}' -> '{new_category}'. Past transactions updated!"
            )
            st.rerun()
        else:
            st.error("Please fill both fields.")
    st.divider()
    st.subheader("Existing Rules")
    try:
        rules_df, _ = run_query("SELECT * FROM category_map ORDER BY keyword")
        st.dataframe(rules_df, width="stretch")
    except Exception:
        st.info("No rules defined yet.")
