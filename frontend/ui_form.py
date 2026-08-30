"""
Formulário de entrada: templates, importação de arquivo, seleção de entrega
e 5 abas de briefing.
"""
from typing import Dict, List

import streamlit as st

from backend.llm import get_llm
from backend.parsers import clamp_slides, extrair_texto_de_arquivo, extrair_campos_de_texto
from data.templates import TEMPLATES
from data.prompts import CANAIS, GATILHOS_MENTAIS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _v(key: str, default) -> object:
    """Retorna valor do form_values em session_state ou o default."""
    return st.session_state.get("form_values", {}).get(key, default)


def _split_list(text: str) -> List[str]:
    return [x.strip() for x in text.split("\n") if x.strip()]


def _split_csv(text: str) -> List[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


# ── Barra de ferramentas: templates + importação ──────────────────────────────

def render_toolbar() -> None:
    """Renderiza selector de templates e uploader de arquivo."""
    col_tpl, col_file = st.columns([1, 1])

    with col_tpl:
        opcao = st.selectbox(
            "📋 Carregar template de nicho",
            list(TEMPLATES.keys()),
            index=0,
            key="template_selecionado",
        )
        if opcao != "— Selecione um template —":
            if st.button("✅ Aplicar Template", use_container_width=True):
                tpl = TEMPLATES[opcao]
                st.session_state.form_values = tpl
                st.session_state.last_file = None
                st.rerun()

    with col_file:
        uploaded = st.file_uploader(
            "📄 Importar Briefing (PDF / DOCX / TXT)",
            type=["pdf", "docx", "txt"],
            key="arquivo_briefing",
        )
        if uploaded and uploaded.name != st.session_state.get("last_file"):
            with st.spinner(f"Extraindo e interpretando {uploaded.name}..."):
                texto = extrair_texto_de_arquivo(uploaded)
                campos = extrair_campos_de_texto(texto, get_llm())
            if campos:
                st.session_state.form_values = campos
                st.session_state.last_file = uploaded.name
                st.success(f"✅ Briefing extraído de **{uploaded.name}**")
                st.rerun()
            else:
                st.warning("Não foi possível extrair campos automaticamente. Preencha manualmente.")


# ── Formulário principal ──────────────────────────────────────────────────────

def render_form() -> Dict:
    """
    Renderiza a seleção de entrega e as 5 abas de briefing, e retorna o
    dicionário briefing_dinamico pronto para o grafo.

    As chaves com prefixo `_` são metadados de execução, não dados de briefing:
    quem chama deve removê-las com `pop` antes de passar o dict adiante, para
    não poluir o RAG (`canonicalize_briefing`) nem o histórico.
    """
    t1, t2, t3, t4, t5 = st.tabs([
        "📦 O Infoproduto",
        "👥 Público-Alvo",
        "🎯 Posicionamento",
        "📅 Estratégia",
        "📣 Prova Social",
    ])

    # ── Aba 1: Infoproduto ────────────────────────────────────────────────────
    with t1:
        st.subheader("Dados do Produto")
        c1, c2 = st.columns(2)
        with c1:
            nome_produto = st.text_input("Nome do Infoproduto",    value=_v("nome_produto", ""))
            produtor     = st.text_input("Nome do Produtor",       value=_v("produtor", ""))
            preco        = st.number_input("Preço (R$)",           value=_v("preco", None), step=100.0)
        with c2:
            formato  = st.text_input("Formato do Produto",   value=_v("formato", ""))
            descricao = st.text_area("Descrição do Produto", value=_v("descricao", ""), height=130)

    # ── Aba 2: Público-Alvo ───────────────────────────────────────────────────
    with t2:
        st.subheader("Persona e Dores")
        demografia = st.text_area(
            "Perfil do Público",
            value=_v("demografia", ""),
        )
        problema_principal = st.text_area(
            "Dor Principal",
            value=_v("problema_principal", ""),
        )
        transformacao_principal = st.text_area(
            "Transformação Prometida",
            value=_v("transformacao_principal", ""),
        )
        objecoes_texto = st.text_area(
            "Objeções (uma por linha)",
            value=_v("objecoes_comuns", ""),
            height=100,
        )
        objecoes_comuns = _split_list(objecoes_texto)

    # ── Aba 3: Posicionamento ─────────────────────────────────────────────────
    with t3:
        st.subheader("Posicionamento")
        diferencial = st.text_area(
            "USP / Diferencial Competitivo",
            value=_v("diferencial_competitivo", ""),
        )
        tom_de_voz = st.text_input(
            "Tom de Voz",
            value=_v("tom_de_voz", ""),
        )
        gatilhos_mentais = st.multiselect(
            "Gatilhos Mentais",
            options=GATILHOS_MENTAIS,
            default=[g for g in _v("gatilhos_mentais", []) if g in GATILHOS_MENTAIS],
            help="Opcional. Orienta o tom da copy em todos os canais.",
        )

    # ── Aba 4: Estratégia ─────────────────────────────────────────────────────
    with t4:
        st.subheader("Estratégia de Lançamento")
        c1, c2 = st.columns(2)
        with c1:
            tipo_lancamento = st.text_input("Tipo de Lançamento", value=_v("tipo_lancamento", ""))
            meta_campanha   = st.text_input("Meta",               value=_v("meta_campanha", ""))
        with c2:
            ini_campanha  = st.text_input("Início da Campanha",      value=_v("ini_campanha", ""))
            abert_carrinho = st.text_input("Abertura do Carrinho",   value=_v("abert_carrinho", ""))
            fech_carrinho  = st.text_input("Fechamento do Carrinho", value=_v("fech_carrinho", ""))
        canais = st.multiselect(
            "Canais",
            options=list(CANAIS.keys()),
            format_func=lambda c: CANAIS[c]["rotulo"],
            default=[c for c in _v("canais", []) if c in CANAIS],
            help="Cada canal tem um agente especializado. Só os selecionados são gerados.",
        )
        num_slides = None
        if "carrossel" in canais:
            num_slides = st.slider(
                "Número de slides do carrossel",
                min_value=5, max_value=10,
                value=clamp_slides(_v("num_slides", 7)),
            )

    # ── Aba 5: Prova Social (nova skill) ──────────────────────────────────────
    with t5:
        st.subheader("Prova Social e Autoridade")
        st.caption(
            "Estas informações alimentam o **Agente de Prova Social**, que formata "
            "depoimentos e métricas e os injeta organicamente na copy de cada canal."
        )
        autoridade_produtor = st.text_area(
            "Autoridade do Produtor",
            value=_v("autoridade_produtor", ""),
            height=80,
        )
        depoimentos_texto = st.text_area(
            "Depoimentos de Alunos (um por linha: Nome: Resultado obtido)",
            value=_v("depoimentos", ""),
            height=120,
        )
        metricas = st.text_area(
            "Métricas e Resultados (dados quantitativos)",
            value=_v("metricas", ""),
            height=80,
        )

    # ── Monta o dicionário de briefing ────────────────────────────────────────
    return {
        "briefing_lancamento": {
            "infoproduto": {
                "nome": nome_produto, "produtor": produtor,
                "preco": preco, "formato": formato, "descricao": descricao,
            },
            "publico_alvo": {
                "demografia": demografia,
                "problema_principal": problema_principal,
                "transformacao_principal": transformacao_principal,
                "objecoes_comuns": objecoes_comuns,
            },
            "posicionamento": {
                "diferencial_competitivo": diferencial,
                "tom_de_voz": tom_de_voz,
                "gatilhos_mentais": gatilhos_mentais,
            },
            "estrategia_lancamento": {
                "tipo_lancamento": tipo_lancamento,
                "meta_campanha": meta_campanha,
                "datas_chave": {
                    "inicio_campanha": ini_campanha,
                    "abertura_carrinho": abert_carrinho,
                    "fechamento_carrinho": fech_carrinho,
                },
                "canais": canais,
            },
            "prova_social": {
                "autoridade_produtor": autoridade_produtor,
                "depoimentos": depoimentos_texto,
                "metricas": metricas,
            },
        },
        "_problema_principal": problema_principal,   # atalho para o RAG
        "_num_slides": num_slides,
    }
