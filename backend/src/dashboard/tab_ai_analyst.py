import streamlit as st
import plotly.express as px
from .query import run_query, ask_ai_analyst

def get_plot_config(df):
    """
    Helper to find the best X and Y columns for plotting.
    Analyzes data types and column names to guess intent.
    """
    config = {"val": None, "dim": None}

    if df.empty:
        return config

    # 1. Find Numeric Column (The Y-axis / Value)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return config

    # Priority search for columns that look like money/totals
    # If none found, default to the first numeric column available
    config["val"] = next(
        (c for c in numeric_cols if any(k in c.lower() for k in ["total", "sum", "spent", "amount", "cost"])),
        numeric_cols[0],
    )

    # 2. Find Dimension Column (The X-axis / Category)
    # Usually the first non-numeric column (e.g. 'category', 'month', 'merchant')
    remaining = [c for c in df.columns if c != config["val"]]
    if remaining:
        config["dim"] = remaining[0]

    return config

def visualize_result(df, chart_type="table"):
    """
    Renders the appropriate chart based on the LLM's recommendation
    and the data shape.
    """
    if df.empty:
        st.warning("Query returned no data.")
        return

    # Auto-detect best columns
    config = get_plot_config(df)

    # Fallback to table if we can't find good columns for a chart
    if chart_type != "table" and (not config["val"] or not config["dim"]):
        chart_type = "table"

    # --- RENDER LOGIC ---
    if chart_type == "metric":
        # Just show the big number
        if config["val"]:
            total = df[config["val"]].sum()
            # Try to format as currency if it looks like it
            st.metric(label=config["val"].replace("_", " ").title(), value=f"₹{total:,.2f}")
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

    else:
        # For 'table', we do nothing here.
        # The calling function handles showing the dataframe below.
        pass

def render_ai_analyst_tab():
    # --- CSS: Chainlit-like Styling ---
    st.markdown("""
        <style>
        /* Status box styling to look like a 'Process Log' */
        div[data-testid="stStatusWidget"] {
            border: 1px solid #f0f2f6;
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 0.9em;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- STATE INITIALIZATION ---
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "I am your Financial Co-Pilot. Ask me about spending trends or budget."}
        ]
    if "latest_data" not in st.session_state:
        st.session_state.latest_data = None
    if "latest_viz_type" not in st.session_state:
        st.session_state.latest_viz_type = "table"

    # --- SPLIT LAYOUT ---
    col_chat, col_viz = st.columns([1.2, 1.5], gap="medium")

    # === LEFT COLUMN: CHAT INTERFACE ===
    with col_chat:
        # Use a container for the history so it scrolls independently
        chat_container = st.container(height=600)

        with chat_container:
            for msg in st.session_state.messages:
                avatar = "🤖" if msg["role"] == "assistant" else "👤"
                with st.chat_message(msg["role"], avatar=avatar):
                    # 1. Show main text
                    st.write(msg["content"])

                    # 2. Show SQL details (collapsed by default)
                    if "sql" in msg:
                        with st.status("🔧 Process Details", state="complete", expanded=False):
                            st.code(msg["sql"], language="sql")
                            if "viz_type" in msg:
                                st.caption(f"Visualization: {msg['viz_type']}")

        # === CHAT INPUT ===
        # Placed inside the column so it aligns with the chat window
        if prompt := st.chat_input("Ask about your finances..."):

            # 1. Append User Message
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Show immediately in UI
            with chat_container:
                with st.chat_message("user", avatar="👤"):
                    st.write(prompt)

            # 2. Process Response
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):

                    final_response_text = ""

                    # A. The Thinking Process (Collapsible Status)
                    with st.status("🧠 Thinking...", expanded=True) as status:
                        st.write("📝 Analyzing intent...")

                        # Call the backend
                        response = ask_ai_analyst(prompt)

                        # Case 1: Direct Answer (e.g. "Hi")
                        if response["type"] == "direct_answer":
                            status.update(label="Conversation", state="complete", expanded=False)
                            final_response_text = response["answer"]

                        # Case 2: SQL Query
                        elif response["type"] == "sql_query":
                            st.write("⚙️ Generating SQL...")
                            sql = response["sql"]
                            viz_type = response["visualization"]

                            st.write("🔎 Executing Query...")
                            res, err = run_query(sql)

                            if err:
                                status.update(label="Error", state="error", expanded=True)
                                final_response_text = f"❌ SQL Error: {err}"
                            elif res.empty:
                                status.update(label="No Data", state="complete", expanded=False)
                                final_response_text = "I ran the query but found no matching records."
                                st.session_state.latest_data = None
                            else:
                                status.update(label="Analysis Complete", state="complete", expanded=False)
                                final_response_text = f"I've visualized this as a **{viz_type}** for you."

                                # Update Global State for the Right Column
                                st.session_state.latest_data = res
                                st.session_state.latest_viz_type = viz_type

                                # Append to history with metadata
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": final_response_text,
                                    "sql": sql,
                                    "viz_type": viz_type
                                })

                        # Case 3: Error
                        elif response["type"] == "error":
                            status.update(label="Error", state="error")
                            final_response_text = f"❌ {response['message']}"

                    # B. Show the Final Answer (Outside the status box)
                    if final_response_text:
                        st.write(final_response_text)

                        # Append to history if it wasn't a SQL success (which is already appended above)
                        if response["type"] != "sql_query":
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": final_response_text
                            })

            # Force refresh to update the Visuals column immediately
            st.rerun()

    # === RIGHT COLUMN: LIVE VISUALS ===
    with col_viz:
        # Frame the insights area
        with st.container(border=True, height=650):
            st.subheader("📊 Live Insights")

            if st.session_state.latest_data is not None:
                df = st.session_state.latest_data
                viz_type = st.session_state.latest_viz_type

                # 1. Render Chart
                visualize_result(df, viz_type)

                # 2. Source Data Table (Always visible below chart)
                with st.expander("📄 View Source Data", expanded=(viz_type == "table")):
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Ask a question to see live data visualization here.")
