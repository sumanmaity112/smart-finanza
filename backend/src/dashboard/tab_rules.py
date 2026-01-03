import streamlit as st
import pandas as pd


def update_category_from_select():
    """
    Callback: When user picks from the dropdown, fill the text box.
    """
    if st.session_state.sel_existing_cat:
        st.session_state.final_cat_input = st.session_state.sel_existing_cat


def reset_add_rule_form():
    st.session_state["sel_existing_cat"] = None
    st.session_state["final_cat_input"] = ""
    st.session_state["add_rule_keyword"] = ""


def render_rules_tab(tracker, run_query):
    st.header("🧠 Teach the System")
    st.markdown(
        "Define rules to automatically categorize transactions.\n\n"
        "- **Keyword**: A substring to match in merchant names.\n"
        "- **Category**: The target category for matching transactions.\n"
        "\n*Tip: Use the preview to see which transactions will be affected before saving a rule.*"
    )

    # --- Fetch Context ---
    try:
        cat_df, _ = run_query(
            "SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL AND category != '' ORDER BY category"
        )
        existing_categories = cat_df["category"].tolist() if not cat_df.empty else []
    except Exception:
        existing_categories = []

    # --- SUGGESTION HANDLING ---
    # If a suggestion was clicked, update the input value and rerun before rendering the widget
    if (
        "cat_suggestion_clicked" in st.session_state
        and st.session_state.cat_suggestion_clicked
    ):
        st.session_state.final_cat_input = st.session_state.cat_suggestion_clicked
        st.session_state.cat_suggestion_clicked = ""
        st.rerun()

    # --- SECTION 1: ADD NEW RULE ---
    with st.container(border=True):
        st.subheader("➕ Add New Rule")
        col1, col2 = st.columns(2)
        with col1:
            new_keyword = st.text_input(
                "If merchant name contains:",
                placeholder="e.g. UBER",
                key="add_rule_keyword",
                help="Enter a substring to match in merchant names.",
                value=st.session_state.get("add_rule_keyword", ""),
            )
        with col2:
            new_category = st.text_input(
                "Set Category to:",
                key="final_cat_input",
                value=st.session_state.get("final_cat_input", ""),
                placeholder="Type or select category...",
                help="Start typing to see suggestions.",
            )
            # Show suggestions as user types
            if new_category:
                suggestions = [
                    cat
                    for cat in existing_categories
                    if new_category.lower() in cat.lower()
                ]
                if suggestions:
                    st.caption("Suggestions:")
                    for cat in suggestions[:5]:
                        if st.button(f"Use '{cat}'", key=f"cat_suggest_{cat}"):
                            st.session_state.final_cat_input = cat
                            st.rerun()
        # --- SMART PREVIEW ---
        if new_keyword:
            preview_sql = f"""
                SELECT date, merchant, amount, category as current_category 
                FROM transactions 
                WHERE merchant LIKE '%{new_keyword}%' 
                ORDER BY date DESC LIMIT 5
            """
            try:
                preview_df, _ = run_query(preview_sql)
            except Exception:
                preview_df = pd.DataFrame()
            if not preview_df.empty:
                st.info(
                    f"🔎 **Preview:** This rule will match **{len(preview_df)}** visible transactions (likely many more)"
                )
                with st.expander("View matching transactions", expanded=True):
                    preview_df["new_category"] = new_category if new_category else "???"
                    st.dataframe(
                        preview_df,
                        column_config={
                            "current_category": "Old Category",
                            "new_category": st.column_config.Column(
                                "New Category", help="Target Category"
                            ),
                        },
                        width="stretch",
                        hide_index=True,
                    )
            else:
                st.caption(
                    "ℹ️ No matches found in current data, but this rule will apply to future uploads."
                )
        # --- SAVE BUTTONS ---
        c_save, c_reset = st.columns([2, 1])
        with c_save:
            if st.button("Save & Apply Rule", type="primary"):
                if not new_keyword or not new_category:
                    st.error("Please fill both fields.")
                else:
                    try:
                        tracker.teach(new_keyword, new_category)
                        st.toast(
                            f"✅ Rule saved! Future imports will now auto-tag '{new_keyword}'."
                        )
                        reset_add_rule_form()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving rule: {e}")
        with c_reset:
            if st.button("Reset", type="secondary"):
                reset_add_rule_form()
                st.experimental_rerun()

    # --- SECTION 2: MANAGE RULES ---
    st.divider()
    st.subheader("📚 Knowledge Base")
    try:
        # Sort by merchant (keyword), then category
        rules_df, _ = run_query(
            "SELECT keyword, category FROM category_map ORDER BY keyword, category"
        )
    except Exception:
        rules_df = pd.DataFrame()
    if not rules_df.empty:
        search = st.text_input(
            "🔍 Search existing rules...",
            placeholder="Filter by merchant or category...",
        )
        if search:
            mask = rules_df["keyword"].str.contains(search, case=False) | rules_df[
                "category"
            ].str.contains(search, case=False)
            rules_df = rules_df[mask]
        r_col1, r_col2 = st.columns([3, 1])
        with r_col1:
            st.dataframe(
                rules_df,
                width="stretch",
                height=400,
                hide_index=True,
                column_config={
                    "keyword": st.column_config.TextColumn(
                        "Merchant Keyword", width="large"
                    ),
                    "category": st.column_config.TextColumn("Category", width="medium"),
                },
            )
        with r_col2:
            st.write("🗑️ **Delete Rule**")
            available_rules = rules_df["keyword"].tolist()
            if available_rules:
                rule_to_delete = st.selectbox(
                    "Select rule to remove", available_rules, key="del_select"
                )
                if st.button("Delete Selected", type="secondary"):
                    if st.confirm(
                        f"Are you sure you want to delete the rule for '{rule_to_delete}'?"
                    ):
                        try:
                            conn = tracker.db.get_connection()
                            conn.execute(
                                "DELETE FROM category_map WHERE keyword = ?",
                                (rule_to_delete,),
                            )
                            conn.commit()
                            conn.close()
                            st.toast(f"Deleted rule: {rule_to_delete}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            else:
                st.caption("No rules match search.")
    else:
        st.info("No rules defined yet. Add one above to get started!")
