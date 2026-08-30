"""
CopyWriter AI — Entry point principal.
Orquestra: form → RAG → grafo → resultados → histórico.
+ Carrossel: orquestra jobs assíncronos via ThreadPoolExecutor (D9 da SPEC).
"""
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from config import GOOGLE_API_KEY, DB_PATH
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

import backend.historico as hist
from backend.graph import get_compiled_graph, AgentState
from backend.rag import setup_rag
from backend.carousel_jobs import (
    init_carousel_jobs_table, create_job, update_job, get_job, friendly_node_label,
)
from frontend.ui_form import render_toolbar, render_form
from frontend.ui_results import render_results, render_carousel_job_status
from frontend.ui_historico import render_historico

# ── Inicialização ─────────────────────────────────────────────────────────────
hist.init_db()

# Conexão SQLite compartilhada: check_same_thread=False obrigatório (D9)
_db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_db_conn.row_factory = sqlite3.Row
init_carousel_jobs_table(_db_conn)

# Executor dedicado para workers de carrossel
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="carousel_worker")

if "final_copy" not in st.session_state:
    st.session_state.final_copy = None
if "form_values" not in st.session_state:
    st.session_state.form_values = {}
if "last_file" not in st.session_state:
    st.session_state.last_file = None
# Jobs de carrossel em andamento nesta sessão
if "carousel_thread_ids" not in st.session_state:
    st.session_state.carousel_thread_ids = []


# ── Orquestração de carrossel ─────────────────────────────────────────────────

def start_carousel_job(payload: dict) -> str:
    """
    Cria um job, despacha o worker de fundo e retorna o thread_id.
    O worker nunca chama st.* — apenas escreve na tabela carousel_jobs.
    """
    thread_id = create_job(_db_conn)
    _executor.submit(_run_carousel_graph_background, thread_id, payload)
    return thread_id


def _run_carousel_graph_background(thread_id: str, payload: dict) -> None:
    """
    Worker de fundo: executa o grafo de carrossel e atualiza a tabela.
    NUNCA chama nenhuma função st.* — violaria o ScriptRunContext (D9).
    """
    import sqlite3 as _sqlite3
    from config import get_settings
    from backend.carousel_graph import build_carousel_graph

    settings = get_settings()
    # Conexão própria do thread (necessário: check_same_thread=False)
    conn = _sqlite3.connect(settings.db_path, check_same_thread=False)

    try:
        update_job(conn, thread_id, status="running")

        # Checkpointer SQLite dedicado para o carrossel
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            checkpointer = SqliteSaver.from_conn_string(settings.carousel_checkpoints)
        except Exception:
            checkpointer = None   # sem checkpointer em ambiente sem suporte

        graph = build_carousel_graph(checkpointer)

        for evento in graph.stream(payload, config={"configurable": {"thread_id": thread_id}}):
            for no in evento:
                update_job(conn, thread_id, current_node=no)

        update_job(conn, thread_id, status="completed")

    except Exception as exc:
        update_job(conn, thread_id, status="failed", error_message=str(exc)[:500])
    finally:
        conn.close()


def get_carousel_job_status(thread_id: str) -> dict | None:
    """Consulta o status de um job de carrossel."""
    return get_job(_db_conn, thread_id)


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

        # ── Disparar job de carrossel visual (pós-crítico, se aprovado) ───────
        carrossel_copy = copy.get("carrossel", {})
        if carrossel_copy and carrossel_copy.get("slides"):
            carousel_payload = {
                "copy": "\n\n".join(
                    s.get("texto_slide", "") for s in carrossel_copy.get("slides", [])
                ),
                "brand": briefing_dinamico.get("briefing_lancamento", {}).get("marca", {}),
                "slides": {
                    "min": 5, "max": 10,
                    "preferred": len(carrossel_copy.get("slides", [])),
                },
                "canvas": {"width": 1080, "height": 1350, "format": "PNG", "quality": 95},
                "visual_preferences": {
                    "image_style": carrossel_copy.get("estilo_visual_global", "fotografia editorial orgânica"),
                    "slide_hints": [s.get("prompt_visual_pomelli", "") for s in carrossel_copy.get("slides", [])],
                    "include_photos": True,
                    "allow_copy_rewrite": False,
                },
                "output_dir": "./outputs/carrosseis",
            }
            tid = start_carousel_job(carousel_payload)
            st.session_state.carousel_thread_ids.append(tid)
            st.info(f"🎠 Job de carrossel visual iniciado: `{tid[:8]}...`")

        # Salva no histórico somente se a geração foi bem-sucedida
        if "error" not in copy:
            hist.salvar(briefing_dinamico, copy, revisao, tentativas)
    else:
        st.error("Não foi possível recuperar o estado final das copys.")

# ── Resultados ────────────────────────────────────────────────────────────────
if st.session_state.final_copy:
    st.divider()
    render_results(st.session_state.final_copy)

# ── Status dos jobs de carrossel visual ──────────────────────────────────────
if st.session_state.carousel_thread_ids:
    st.divider()
    st.subheader("🎠 Jobs de Carrossel Visual")
    for tid in list(st.session_state.carousel_thread_ids):
        job = get_carousel_job_status(tid)
        if job:
            render_carousel_job_status(job, tid)

# ── Histórico ─────────────────────────────────────────────────────────────────
st.divider()
render_historico()

