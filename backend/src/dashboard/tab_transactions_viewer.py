import streamlit as st


def render_transactions_viewer_tab(df, tracker):
    st.markdown("Manually review transactions details.")
    st.caption("To make permanent changes, use the 'Rules' tab.")

    if df.empty:
        st.info("No transactions found.")
        return

    # Dynamically get all unique categories from the data
    category_options = sorted(
        [c for c in df["category"].dropna().unique() if str(c).strip() != ""]
    )
    if not category_options:
        category_options = ["Uncategorized"]

    st.data_editor(
        df.sort_values(by="date", ascending=False),
        column_config={
            "category": st.column_config.SelectboxColumn(
                "Category",
                options=category_options,
                required=True,
            )
        },
        hide_index=True,
        width="stretch",
        key="viewer",
        height=600,
        disabled=True,  # Make the table read-only
    )
