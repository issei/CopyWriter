"""
CopyWriter AI — Entry point principal.
Orquestra: form → RAG → grafo → resultados → histórico.
"""
import os
import streamlit as st

from config import GOOGLE_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

import backend.historico as hist
from backend.graph import get_compiled_graph, AgentState
from backend.rag import setup_rag
from frontend.ui_form import render_toolbar, render_form
from frontend.ui_results import render_results
from frontend.ui_historico import render_historico

# ── Inicialização ─────────────────────────────────────────────────────────────
hist.init_db()

if "final_copy" not in st.session_state:
    st.session_state.final_copy = None
if "form_values" not in st.session_state:
    st.session_state.form_values = {}
if "last_file" not in st.session_state:
    st.session_state.last_file = None

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="CopyWriter AI", layout="wide")
st.title("🤖 Geração de Copy para Lançamentos com LangGraph")
st.write("Preencha o briefing ou carregue um template · Importe um arquivo · Gere copy para todos os canais.")

if not GOOGLE_API_KEY:
    st.error("⚠️ GOOGLE_API_KEY não encontrada. Crie um arquivo `.env` com a chave antes de continuar.")
    st.stop()

# ── Toolbar: templates e importação de arquivo ────────────────────────────────
render_toolbar()
st.divider()

# ── Formulário de briefing ────────────────────────────────────────────────────
briefing_dinamico = render_form()
# Metadados de execução saem do dict antes do RAG e do histórico
problema_principal = briefing_dinamico.pop("_problema_principal", "")
content_type       = briefing_dinamico.pop("_content_type", "padrao")
num_slides         = briefing_dinamico.pop("_num_slides", None)

# ── Botões de ação ────────────────────────────────────────────────────────────
st.divider()
col_btn, col_clear = st.columns([4, 1])
with col_btn:
    gerar = st.button(
        "🚀 Iniciar Inteligência de Grafo e Gerar Copy",
        type="primary",
        use_container_width=True,
    )
with col_clear:
    if st.button("🗑️ Limpar", use_container_width=True):
        st.session_state.final_copy = None
        st.rerun()

# ── Execução do grafo ─────────────────────────────────────────────────────────
if gerar:
    st.subheader("⚙️ Execução do Grafo em Tempo Real")

    with st.spinner("Indexando briefing no RAG local..."):
        rag_context = setup_rag(briefing_dinamico, problema_principal)

    initial_state = AgentState(
        briefing=briefing_dinamico,
        contexto_rag=rag_context,
        tentativas_refinamento=0,
        content_type=content_type,
        num_slides=num_slides,
    )

    # Acumula os updates de todos os nós: com o carrossel ligado, `adaptacao_canais`
    # deixa de ser o último a escrever `copy_por_canal`.
    estado_final = {}
    with st.spinner("Agentes colaborando na criação da campanha..."):
        for event in get_compiled_graph().stream(initial_state):
            for payload in event.values():
                if isinstance(payload, dict):
                    estado_final.update(payload)

    st.success("✅ Execução do Grafo Concluída!")

    if "copy_por_canal" in estado_final:
        copy = estado_final["copy_por_canal"]
        revisao    = estado_final.get("revisao_critico", "")
        tentativas = estado_final.get("tentativas_refinamento", 0)

        st.session_state.final_copy = copy

        # Salva no histórico somente se a geração foi bem-sucedida
        if "error" not in copy:
            hist.salvar(briefing_dinamico, copy, revisao, tentativas)
    else:
        st.error("Não foi possível recuperar o estado final das copys.")

# ── Resultados ────────────────────────────────────────────────────────────────
if st.session_state.final_copy:
    st.divider()
    render_results(st.session_state.final_copy)

# ── Histórico ─────────────────────────────────────────────────────────────────
st.divider()
render_historico()
