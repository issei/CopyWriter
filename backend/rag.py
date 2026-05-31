"""Configuração e recuperação RAG com ChromaDB."""
import os
import shutil
from typing import Dict

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import EMBEDDING_MODEL, CHROMA_PATH
from backend.parsers import canonicalize_briefing


def setup_rag(briefing_dinamico: Dict, query: str) -> str:
    """
    Limpa o índice anterior, indexa o briefing e recupera os chunks mais
    relevantes para a query informada (normalmente o problema principal).
    """
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    texto = canonicalize_briefing(briefing_dinamico)
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = splitter.create_documents([texto])
    vectorstore.add_documents(docs)

    retriever = vectorstore.as_retriever()
    relevant = retriever.invoke(query or texto[:200])
    return "\n\n".join(
        f"[doc{i+1}]\n{doc.page_content}"
        for i, doc in enumerate(relevant)
    )
