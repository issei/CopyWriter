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
from backend.parsers import podar
from backend.rag import setup_rag
from backend.carousel_jobs import (
    init_carousel_jobs_table, create_job, get_job, run_carousel_job, friendly_node_label,
)
from frontend.ui_form import render_toolbar, render_form
from frontend.ui_results import render_results, render_carousel_job_status
from frontend.ui_historico import render_historico

# ── Inicialização ─────────────────────────────────────────────────────────────
hist.init_db()

# O Streamlit reexecuta este script inteiro a cada interação — e o poller de job
# faz isso a cada 2s. Sem @st.cache_resource, cada rerun abriria uma conexão e um
# executor novos, nenhum deles fechado.

@st.cache_resource
def _get_db_conn() -> sqlite3.Connection:
    """Conexão SQLite compartilhada: check_same_thread=False obrigatório (D9)."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_carousel_jobs_table(conn)
    return conn


@st.cache_resource
def _get_executor() -> ThreadPoolExecutor:
    """Executor dedicado para workers de carrossel."""
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="carousel_worker")

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
    from config import get_settings

    settings  = get_settings()
    thread_id = create_job(_get_db_conn())
    _get_executor().submit(
        run_carousel_job, thread_id, payload,
        settings.db_path, settings.carousel_checkpoints,
    )
    return thread_id


def get_carousel_job_status(thread_id: str) -> dict | None:
    """Consulta o status de um job de carrossel."""
    return get_job(_get_db_conn(), thread_id)


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
num_slides         = briefing_dinamico.pop("_num_slides", None)

# Os canais selecionados decidem quais agentes rodam; o carrossel é derivado deles.
canais = (briefing_dinamico.get("briefing_lancamento", {})
          .get("estrategia_lancamento", {}).get("canais", []))
content_type = "carousel" if "carrossel" in canais else "padrao"

# ── Botões de ação ────────────────────────────────────────────────────────────
st.divider()

# Com tudo opcional, dois campos ainda são indispensáveis: sem canal não há o que
# gerar, e sem a dor principal o RAG não tem query de recuperação.
_faltando = []
if not canais:
    _faltando.append("selecione ao menos um canal")
if not problema_principal.strip():
    _faltando.append("preencha a dor principal")

col_btn, col_clear = st.columns([4, 1])
with col_btn:
    gerar = st.button(
        "🚀 Iniciar Inteligência de Grafo e Gerar Copy",
        type="primary",
        use_container_width=True,
        disabled=bool(_faltando),
    )
with col_clear:
    if st.button("🗑️ Limpar", use_container_width=True):
        st.session_state.final_copy = None
        st.rerun()
if _faltando:
    st.caption("⚠️ Para gerar: " + " · ".join(_faltando) + ".")

# ── Execução do grafo ─────────────────────────────────────────────────────────
if gerar:
    st.subheader("⚙️ Execução do Grafo em Tempo Real")

    # Campos em branco não chegam aos agentes: viram ruído em toda chamada.
    briefing_limpo = podar(briefing_dinamico)

    with st.spinner("Indexando briefing no RAG local..."):
        rag_context = setup_rag(briefing_limpo, problema_principal)

    initial_state = AgentState(
        briefing=briefing_limpo,
        contexto_rag=rag_context,
        tentativas_refinamento=0,
        canais=canais,
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
            # O formulário não tem seção de marca; o produtor é o único dado de
            # autoria que existe. Sem ele o cabeçalho de autoria não é desenhado.
            _bl = briefing_limpo.get("briefing_lancamento", {})
            _produtor = _bl.get("infoproduto", {}).get("produtor", "")

            carousel_payload = {
                "copy": "\n\n".join(
                    s.get("texto_slide", "") for s in carrossel_copy.get("slides", [])
                ),
                "brand": {
                    "name": _produtor,
                    "handle": _produtor.lower().replace(" ", ""),
                    "verified": False,
                    "voice": _bl.get("posicionamento", {}).get("tom_de_voz", ""),
                } if _produtor else {},
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
            hist.salvar(briefing_limpo, copy, revisao, tentativas)
    else:
        st.error("Não foi possível recuperar o estado final das copys.")

# ── Resultados ────────────────────────────────────────────────────────────────
if st.session_state.final_copy:
    st.divider()
    render_results(st.session_state.final_copy)

# ── Status dos jobs de carrossel visual ──────────────────────────────────────
_algum_job_ativo = False
if st.session_state.carousel_thread_ids:
    st.divider()
    st.subheader("🎠 Jobs de Carrossel Visual")
    for tid in list(st.session_state.carousel_thread_ids):
        job = get_carousel_job_status(tid)
        if job:
            _algum_job_ativo |= render_carousel_job_status(job, tid)

# ── Histórico ─────────────────────────────────────────────────────────────────
st.divider()
render_historico()

# O polling fica no fim: com o rerun dentro do laço de jobs, o script morria no
# primeiro job em andamento e nem os demais nem o histórico chegavam a renderizar.
if _algum_job_ativo:
    time.sleep(2)
    st.rerun()

