import streamlit as st
import pandas as pd
import os
from .backend import get_backend
from .query import run_query
from .tab_dashboard import render_dashboard_tab
from .tab_transactions_viewer import render_transactions_viewer_tab
from .tab_ai_analyst import render_ai_analyst_tab
from .tab_rules import render_rules_tab

db_engine, llm_engine, tracker = get_backend()

def main():
    st.title("💰 Finance Command Center")

    # --- GLOBAL SIDEBAR: DATA INGESTION ---
    with st.sidebar:
        st.header("📂 Data Import")
        uploaded_file = st.file_uploader("Upload Statement", type=["pdf", "csv"], help="Upload bank statements here to update your database.")

        if uploaded_file:
            if st.button(f"Process {uploaded_file.name}", type="primary"):
                with st.spinner("Processing document..."):
                    # Save temp file
                    temp_dir = "temp_ingest"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, uploaded_file.name)

                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    try:
                        # Run the tracker logic
                        tracker.process_file(temp_path)
                        st.success("✅ Import Complete!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

        st.divider()
        st.caption(f"Backend: {llm_engine.model}")

    # --- MAIN CONTENT ---
    try:
        df, err = db_engine.get_all_transactions()
        if err:
            st.info("Database empty. Upload a file in the sidebar to get started.")
            df = pd.DataFrame()
        elif not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df["month"] = df["date"].dt.to_period("M").astype(str)
    except Exception as e:
        st.error(f"DB Error: {e}")
        df = pd.DataFrame()

    # Layout Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Dashboard", "🤖 AI Analyst", "⚙️ Rules", "📋 Transaction Viewer"]
    )

    with tab1:
        render_dashboard_tab(df)
    with tab2:
        render_ai_analyst_tab()
    with tab3:
        render_rules_tab(tracker, run_query)
    with tab4:
        render_transactions_viewer_tab(df, tracker)
