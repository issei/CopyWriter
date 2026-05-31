"""Formulário de entrada: templates, importação de arquivo e 5 abas de briefing."""
from typing import Dict, List

import streamlit as st

from backend.llm import get_llm
from backend.parsers import extrair_texto_de_arquivo, extrair_campos_de_texto
from data.templates import TEMPLATES


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
    Renderiza as 5 abas de briefing e retorna o dicionário
    briefing_dinamico pronto para o grafo.
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
            nome_produto = st.text_input("Nome do Infoproduto",    value=_v("nome_produto", "Mentoria de Desenvolvimento Inteligente"))
            produtor     = st.text_input("Nome do Produtor",       value=_v("produtor",     "Mauricio Issei"))
            preco        = st.number_input("Preço (R$)",           value=float(_v("preco", 2997.0)), step=100.0)
        with c2:
            formato  = st.text_input("Formato do Produto",   value=_v("formato",  "Mentoria com aulas ao vivo + comunidade"))
            descricao = st.text_area("Descrição do Produto", value=_v("descricao", "Mentoria para desenvolvedores que querem dominar arquitetura de software e design patterns."), height=130)

    # ── Aba 2: Público-Alvo ───────────────────────────────────────────────────
    with t2:
        st.subheader("Persona e Dores")
        demografia = st.text_area(
            "Perfil do Público",
            value=_v("demografia", "Desenvolvedores Full-Stack, 25-45 anos, 3+ anos de experiência, R$ 5k-20k/mês."),
        )
        problema_principal = st.text_area(
            "Dor Principal",
            value=_v("problema_principal", "Estou estagnado tecnicamente, não acompanho as melhores práticas e tenho dificuldade em arquitetar soluções escaláveis."),
        )
        transformacao_principal = st.text_area(
            "Transformação Prometida",
            value=_v("transformacao_principal", "Dominar arquitetura de software, ser um dev procurado e aumentar o salário em 50%."),
        )
        objecoes_texto = st.text_area(
            "Objeções (uma por linha)",
            value=_v("objecoes_comuns", "Não tenho tempo\nJá fiz cursos que não funcionaram\nO preço é alto"),
            height=100,
        )
        objecoes_comuns = _split_list(objecoes_texto)

    # ── Aba 3: Posicionamento ─────────────────────────────────────────────────
    with t3:
        st.subheader("Posicionamento")
        diferencial = st.text_area(
            "USP / Diferencial Competitivo",
            value=_v("diferencial_competitivo", "A única mentoria com foco em arquitetura de software real + comunidade de devs sênior."),
        )
        tom_de_voz = st.text_input(
            "Tom de Voz",
            value=_v("tom_de_voz", "Direto, sem BS, prático, baseado em casos reais."),
        )
        gatilhos_texto = st.text_input(
            "Gatilhos Mentais (separados por vírgula)",
            value=_v("gatilhos_mentais", "Escassez, Autoridade, Comunidade, Transformação de identidade"),
        )
        gatilhos_mentais = _split_csv(gatilhos_texto)

    # ── Aba 4: Estratégia ─────────────────────────────────────────────────────
    with t4:
        st.subheader("Estratégia de Lançamento")
        c1, c2 = st.columns(2)
        with c1:
            tipo_lancamento = st.text_input("Tipo de Lançamento", value=_v("tipo_lancamento", "VSL + Sequência de email"))
            meta_campanha   = st.text_input("Meta",               value=_v("meta_campanha",   "Vender 50 mentorias a R$ 2.997"))
        with c2:
            ini_campanha  = st.text_input("Início da Campanha",      value=_v("ini_campanha",  "2026-06-01"))
            abert_carrinho = st.text_input("Abertura do Carrinho",   value=_v("abert_carrinho", "2026-06-05"))
            fech_carrinho  = st.text_input("Fechamento do Carrinho", value=_v("fech_carrinho",  "2026-06-07"))
        canais_texto = st.text_input(
            "Canais (vírgula)",
            value=_v("canais", "Email Marketing, Meta Ads, Instagram Stories, YouTube (VSL)"),
        )
        canais = _split_csv(canais_texto)

    # ── Aba 5: Prova Social (nova skill) ──────────────────────────────────────
    with t5:
        st.subheader("Prova Social e Autoridade")
        st.caption(
            "Estas informações alimentam o **Agente de Prova Social**, que formata "
            "depoimentos e métricas e os injeta organicamente na copy de cada canal."
        )
        autoridade_produtor = st.text_area(
            "Autoridade do Produtor",
            value=_v("autoridade_produtor", "20+ anos desenvolvendo software, ex-CTO de 3 startups, mentor de +500 devs."),
            height=80,
        )
        depoimentos_texto = st.text_area(
            "Depoimentos de Alunos (um por linha: Nome: Resultado obtido)",
            value=_v("depoimentos", (
                "Carlos Silva: Em 3 meses passei de dev pleno para sênior e aumentei meu salário em 40%.\n"
                "Mariana Costa: Aprendi a arquitetar sistemas que antes eram impossíveis para mim."
            )),
            height=120,
        )
        metricas = st.text_area(
            "Métricas e Resultados (dados quantitativos)",
            value=_v("metricas", "+500 devs mentorados, 92% de aprovação nos desafios técnicos, média de aumento salarial de 35%"),
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
        "_problema_principal": problema_principal,  # atalho para o RAG
    }
