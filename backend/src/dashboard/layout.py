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

    # --- GLOBAL: Show persistent spinner if processing is ongoing ---
    if st.session_state.get("processing_file", False):
        st.info(
            "⏳ Processing document... Please wait. Do not navigate away or interact until complete."
        )

    # --- Show Import Complete message if needed ---
    if st.session_state.get("import_success", False):
        st.toast("Import Complete!", icon="✅", duration="infinite")
        st.session_state["import_success"] = False

    # --- GLOBAL SIDEBAR: DATA INGESTION ---
    with st.sidebar:
        st.header("📂 Data Import")
        if "uploader_key" not in st.session_state:
            st.session_state["uploader_key"] = 0
        uploaded_file = st.file_uploader(
            "Upload Statement",
            type=["pdf", "csv"],
            help="Upload bank/credit card statements here to update your database.",
            accept_multiple_files=False,
            label_visibility="visible",
            disabled=st.session_state.get("processing_file", False),
            key=f"uploader_{st.session_state['uploader_key']}",
        )

        # Track processing state
        if "processing_file" not in st.session_state:
            st.session_state["processing_file"] = False

        def start_processing():
            st.session_state["processing_file"] = True

        if uploaded_file:
            process_disabled = st.session_state["processing_file"]
            if st.button(
                f"Process {uploaded_file.name}",
                type="primary",
                disabled=process_disabled,
                on_click=start_processing,
            ):
                with st.spinner("Processing document..."):
                    temp_dir = "temp_ingest"
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_path = os.path.join(temp_dir, uploaded_file.name)

                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    try:
                        tracker.process_file(temp_path)
                        st.session_state["processing_file"] = False
                        st.session_state["import_success"] = True
                        st.session_state["uploader_key"] += 1
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        st.session_state["processing_file"] = False
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
