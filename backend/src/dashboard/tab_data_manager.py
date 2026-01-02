import streamlit as st
import os


def render_data_manager_tab(df, tracker):
    st.subheader("📤 Import Statements")
    uploaded_file = st.file_uploader("Upload PDF or CSV", type=["pdf", "csv"])
    if uploaded_file:
        if st.button(f"Process {uploaded_file.name}"):
            with st.spinner("Analyzing document... (Using backend pipeline)"):
                temp_dir = "temp_ingest"
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, uploaded_file.name)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                try:
                    tracker.process_file(temp_path)
                    st.success("✅ Processing Complete! Refreshing data...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error during processing: {e}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
    st.divider()
    st.subheader("✏️ Quick Edit Transactions")
    if not df.empty:
        st.data_editor(
            df.sort_values(by="date", ascending=False),
            column_config={
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=[
                        "Food",
                        "Transport",
                        "Utilities",
                        "Shopping",
                        "Health",
                        "Investment",
                        "Transfer",
                        "Other",
                        "Uncategorized",
                    ],
                    required=True,
                )
            },
            hide_index=True,
            width="stretch",
            key="editor",
        )
        st.caption(
            "*Note: UI edits are currently visual only. Use 'Rules' tab to permanently categorize.*"
        )
