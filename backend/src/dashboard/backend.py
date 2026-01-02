import streamlit as st
from db import DatabaseEngine
from tracker import FinanceTracker
from llm import LLMExtractor


@st.cache_resource
def get_backend():
    db = DatabaseEngine()
    llm = LLMExtractor()
    tracker = FinanceTracker()
    return db, llm, tracker
