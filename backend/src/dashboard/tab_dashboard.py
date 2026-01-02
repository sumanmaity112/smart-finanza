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
        view_df = df[df["month"] == selected_month]
    else:
        view_df = df
    income = view_df[view_df["txn_type"] == TxnType.CREDIT.value]["amount"].sum()
    expenses = view_df[view_df["txn_type"] == TxnType.DEBIT.value]["amount"].sum()
    savings = income - expenses
    c1, c2, c3 = st.columns(3)
    c1.metric("Income", f"₹{income:,.0f}")
    c2.metric("Expenses", f"₹{expenses:,.0f}")
    c3.metric("Savings", f"₹{savings:,.0f}", delta_color="normal")
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Category Split")
        cat_data = (
            view_df[view_df["txn_type"] == TxnType.DEBIT.value]
            .groupby("category")["amount"]
            .sum()
            .reset_index()
        )
        if not cat_data.empty:
            fig = px.pie(cat_data, values="amount", names="category", hole=0.4)
            st.plotly_chart(fig, width="stretch")
    with col_b:
        st.subheader("Spending Trend")
        daily_data = (
            view_df[view_df["txn_type"] == TxnType.DEBIT.value]
            .groupby("date")["amount"]
            .sum()
            .reset_index()
        )
        if not daily_data.empty:
            fig = px.bar(daily_data, x="date", y="amount")
            st.plotly_chart(fig, width="stretch")
