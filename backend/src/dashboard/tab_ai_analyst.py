import streamlit as st
from .query import run_query, ask_ai_analyst


def render_ai_analyst_tab():
    st.subheader("Ask AI about your finances")
    q = st.text_input(
        "Question:",
        placeholder="e.g., How much did I spend on Swiggy? or What's a good savings rate?",
    )
    if q:
        with st.spinner("Thinking..."):
            response = ask_ai_analyst(q)

            if response['type'] == 'direct_answer':
                # Direct answer without SQL
                st.info("💡 AI Answer (No database query needed)")
                st.write(response['answer'])
            elif response['type'] == 'sql_query':
                # SQL query needed
                sql = response['sql']
                st.code(sql, language="sql")
                res, err = run_query(sql)
                if err:
                    st.error(err)
                else:
                    st.dataframe(res)
            elif response['type'] == 'error':
                # Error occurred
                st.error(f"❌ {response['message']}")
