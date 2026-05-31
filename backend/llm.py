import os
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from config import GOOGLE_API_KEY, GEMINI_MODEL, TEMPERATURE

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY


@st.cache_resource
def get_llm() -> ChatGoogleGenerativeAI:
    """LLM singleton — instanciado uma única vez por sessão do servidor."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=TEMPERATURE,
        api_key=GOOGLE_API_KEY,
    )
