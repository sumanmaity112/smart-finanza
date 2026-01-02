import streamlit as st
from dashboard.layout import main

# Configure Streamlit page
st.set_page_config(
    page_title="Finance Command Center",
    layout="wide",
    page_icon="💰"
)

if __name__ == "__main__":
    main()
