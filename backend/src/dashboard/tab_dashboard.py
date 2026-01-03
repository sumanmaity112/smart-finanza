import streamlit as st
from constants import TxnType
import plotly.express as px


def render_dashboard_tab(df):
    if df.empty:
        st.warning("No data found.")
        return
    all_months = sorted(df["month"].unique(), reverse=True)
    selected_month = st.sidebar.selectbox("Period", ["All Time"] + all_months)

    if selected_month != "All Time":
        base_df = df[df["month"] == selected_month]
    else:
        base_df = df

    income = base_df[base_df["txn_type"] == TxnType.CREDIT.value]["amount"].sum()
    expenses = base_df[base_df["txn_type"] == TxnType.DEBIT.value]["amount"].sum()
    savings = income - expenses

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", f"₹{income:,.0f}")
    c2.metric("Total Expenses", f"₹{expenses:,.0f}")
    c3.metric("Net Savings", f"₹{savings:,.0f}", delta_color="normal")

    st.divider()

    col_pie, col_line = st.columns(2)

    pie_df = (
        base_df[base_df["txn_type"] == TxnType.DEBIT.value]
        .groupby("category")["amount"]
        .sum()
        .reset_index()
    )

    with col_pie:
        st.subheader("Expenses by Category")
        if not pie_df.empty:
            fig_pie = px.pie(pie_df, values="amount", names="category", hole=0.4)
            st.plotly_chart(fig_pie, width="stretch")
        else:
            st.info("No expense data available.")

    with col_line:
        st.subheader("Expense Trends by Category")

        trend_data = (
            base_df[base_df["txn_type"] == TxnType.DEBIT.value]
            .groupby(["date", "category"])["amount"]
            .sum()
            .reset_index()
        )

        if not trend_data.empty:
            fig_line = px.line(
                trend_data, x="date", y="amount", color="category", markers=True
            )
            fig_line.update_layout(
                xaxis_title="Date",
                yaxis_title="Amount (₹)",
                hovermode="x unified",
                legend=dict(
                    orientation="v", yanchor="top", y=1, xanchor="left", x=1.02
                ),
            )
            st.plotly_chart(fig_line, width="stretch")
        else:
            st.info("No expense trend data for this period.")

    st.divider()

    all_categories = ["All Categories"] + sorted(base_df["category"].unique().tolist())
    selected_category_filter = st.selectbox(
        "Filter expenses by category:", all_categories
    )

    if selected_category_filter == "All Categories":
        table_df = base_df[base_df["txn_type"] == TxnType.DEBIT.value]
        table_title = "📄 All Expense Transactions"
    else:
        table_df = base_df[
            (base_df["category"] == selected_category_filter)
            & (base_df["txn_type"] == TxnType.DEBIT.value)
        ]
        table_title = f"📄 {selected_category_filter} Expense Transactions"

    st.subheader(table_title)

    st.dataframe(
        table_df.sort_values(by="date", ascending=False),
        column_config={
            "amount": st.column_config.NumberColumn(format="₹%.2f"),
            "date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "merchant": st.column_config.TextColumn("Merchant", width="medium"),
            "category": st.column_config.TextColumn("Category", width="small"),
            "notes": st.column_config.TextColumn("Notes", width="large"),
        },
        column_order=["date", "merchant", "amount", "category", "notes"],
        width="stretch",
        hide_index=True,
        height=400,
    )
