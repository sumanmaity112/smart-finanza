import streamlit as st
import pandas as pd
from .backend import get_backend
from .query import run_query
from .tab_dashboard import render_dashboard_tab
from .tab_data_manager import render_data_manager_tab
from .tab_ai_analyst import render_ai_analyst_tab
from .tab_rules import render_rules_tab

db_engine, llm_engine, tracker = get_backend()


def main():
    st.title("💰 Finance Command Center")
    try:
        df, err = db_engine.get_all_transactions()
        if err:
            st.info(
                "Database initialized but empty. Go to 'Data Manager' to upload files."
            )
            df = pd.DataFrame()
        elif not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df["month"] = df["date"].dt.to_period("M").astype(str)
    except Exception as e:
        st.error(f"Critical DB Error: {e}")
        df = pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Dashboard", "📝 Data Manager", "🤖 AI Analyst", "⚙️ Rules"]
    )

    with tab1:
        render_dashboard_tab(df)
    with tab2:
        render_data_manager_tab(df, tracker)
    with tab3:
        render_ai_analyst_tab()
    with tab4:
        render_rules_tab(tracker, run_query)
