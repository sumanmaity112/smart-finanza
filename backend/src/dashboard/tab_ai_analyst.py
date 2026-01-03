import streamlit as st
import plotly.express as px
from .query import run_query, ask_ai_analyst


def get_plot_config(df):
    """
    Helper to find the best X and Y columns for plotting.
    """
    config = {"val": None, "dim": None}

    if df.empty:
        return config

    # 1. Find Numeric Column (Y-axis)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return config

    # Priority search for "amount"-like columns
    config["val"] = next(
        (
            c
            for c in numeric_cols
            if any(k in c.lower() for k in ["total", "sum", "spent", "amount", "cost"])
        ),
        numeric_cols[0],
    )

    # 2. Find Dimension Column (X-axis)
    remaining = [c for c in df.columns if c != config["val"]]
    if remaining:
        config["dim"] = remaining[0]

    return config


def visualize_result(df, chart_type="table"):
    """
    Renders charts based on the LLM's recommended type.
    """
    if df.empty:
        st.warning("Query returned no data.")
        return

    # Get best columns
    config = get_plot_config(df)

    # Fallback to table if we can't find appropriate columns for a chart
    if chart_type != "table" and (not config["val"] or not config["dim"]):
        st.caption("⚠️ Could not determine columns for chart. Showing data.")
        chart_type = "table"

    # --- RENDERERS ---
    if chart_type == "metric":
        # Just show the big number
        if config["val"]:
            total = df[config["val"]].sum()
            st.metric(
                label=config["val"].replace("_", " ").title(), value=f"₹{total:,.2f}"
            )
        else:
            st.dataframe(df)

    elif chart_type == "line":
        st.caption(f"📈 {config['val'].title()} over {config['dim'].title()}")
        fig = px.line(df, x=config["dim"], y=config["val"], markers=True)
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "bar":
        st.caption(f"📊 {config['val'].title()} by {config['dim'].title()}")
        fig = px.bar(df, x=config["dim"], y=config["val"], color=config["dim"])
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "pie":
        st.caption(f"🍩 Breakdown of {config['val'].title()}")
        fig = px.pie(df, values=config["val"], names=config["dim"], hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    else:  # Table
        pass  # The table is always shown below in the main view


def render_ai_analyst_tab():
    # ... [CSS styles remain same] ...
    st.markdown(
        """
        <style>
        .stChatInput {position: fixed; bottom: 20px; z-index: 999;}
        .block-container {padding-bottom: 120px;}
        </style>
    """,
        unsafe_allow_html=True,
    )

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "I am your Financial Co-Pilot. Ask me about spending trends or budget.",
            }
        ]
    if "latest_data" not in st.session_state:
        st.session_state.latest_data = None
    if "latest_viz_type" not in st.session_state:
        st.session_state.latest_viz_type = "table"

    col_chat, col_viz = st.columns([1, 1.5], gap="medium")

    # === LEFT: CHAT ===
    with col_chat:
        st.subheader("💬 Chat")
        with st.container(height=600):
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    if "sql" in msg:
                        with st.expander("View SQL"):
                            st.code(msg["sql"], language="sql")

    # === RIGHT: VISUALS ===
    with col_viz:
        st.subheader("📊 Live Insights")
        with st.container(border=True):
            if st.session_state.latest_data is not None:
                df = st.session_state.latest_data
                viz_type = st.session_state.latest_viz_type

                # 1. Render the requested chart
                visualize_result(df, viz_type)

                # 2. Always show the Data Table below
                with st.expander("📄 View Source Data", expanded=(viz_type == "table")):
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Ask a question to generate insights.")

    # === INPUT ===
    if prompt := st.chat_input("Ask about your finances..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with col_chat:
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    response = ask_ai_analyst(prompt)

                    if response["type"] == "direct_answer":
                        st.write(response["answer"])
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response["answer"]}
                        )
                        st.session_state.latest_data = None

                    elif response["type"] == "sql_query":
                        sql = response["sql"]
                        viz_type = response["visualization"]  # Capture the LLM's choice

                        res, err = run_query(sql)

                        if err:
                            st.error(f"SQL Error: {err}")
                            st.session_state.messages.append(
                                {"role": "assistant", "content": f"Error: {err}"}
                            )
                        elif res.empty:
                            st.warning("No records found.")
                            st.session_state.messages.append(
                                {"role": "assistant", "content": "No records found."}
                            )
                            st.session_state.latest_data = None
                        else:
                            msg = f"I've visualized this as a **{viz_type}** for you."
                            st.write(msg)

                            # Save state including visualization type
                            st.session_state.latest_data = res
                            st.session_state.latest_viz_type = viz_type
                            st.session_state.messages.append(
                                {"role": "assistant", "content": msg, "sql": sql}
                            )
                            st.rerun()

                    elif response["type"] == "error":
                        st.error(response["message"])
