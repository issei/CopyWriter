"""
CopyWriter AI — Gerador de Copy para Lançamentos com LangGraph
"""
import os
import json
import re
import shutil
from typing import TypedDict, Optional, Dict, Any, List

from dotenv import load_dotenv
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import StateGraph, START, END

# ============================================================
# CONFIGURAÇÃO
# ============================================================
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.7
MAX_REFINEMENT_ATTEMPTS = 2
EMBEDDING_MODEL = "models/gemini-embedding-001"
CHROMA_PATH = "./chroma_db"


# ============================================================
# ESTADO DO GRAFO
# ============================================================
class AgentState(TypedDict):
    briefing: Dict
    contexto_rag: str
    dores_promessas: Optional[Dict]
    objecoes_quebras: Optional[Dict]
    headlines_angulos: Optional[Dict]
    contexto_enriquecido: Optional[str]
    copy_por_canal: Optional[Dict]
    revisao_critico: Optional[str]
    tentativas_refinamento: int


# ============================================================
# UTILITÁRIOS
# ============================================================
def canonicalize_briefing_to_text(briefing_dict: Dict[str, Any]) -> str:
    """Converte o dicionário de briefing em texto estruturado para indexação RAG."""
    b = briefing_dict.get("briefing_lancamento", {})
    inf = b.get("infoproduto", {})
    pub = b.get("publico_alvo", {})
    pos = b.get("posicionamento", {})
    est = b.get("estrategia_lancamento", {})
    datas = est.get("datas_chave", {})

    linhas = [
        "# Briefing de Lançamento",
        f"Nome: {inf.get('nome', '')} | Produtor: {inf.get('produtor', '')}",
        f"Preço: R$ {inf.get('preco', '')} | Formato: {inf.get('formato', '')}",
        f"Descrição: {inf.get('descricao', '')}",
        f"\nDor principal: {pub.get('problema_principal', '')}",
        f"Transformação: {pub.get('transformacao_principal', '')}",
        f"Perfil: {pub.get('demografia', '')}",
    ]
    for o in pub.get("objecoes_comuns", []):
        linhas.append(f"- Objeção: {o}")
    linhas.extend([
        f"\nUSP: {pos.get('diferencial_competitivo', '')}",
        f"Tom de voz: {pos.get('tom_de_voz', '')}",
        "Gatilhos: " + ", ".join(pos.get("gatilhos_mentais", [])),
        f"\nLançamento: {est.get('tipo_lancamento', '')} | Meta: {est.get('meta_campanha', '')}",
        f"Datas: {datas.get('inicio_campanha', '')} → {datas.get('fechamento_carrinho', '')}",
        "Canais: " + ", ".join(est.get("canais", [])),
    ])
    return "\n".join(linhas)


def force_json(llm_output: Any) -> Dict:
    """Extrai JSON da resposta do LLM com 4 estratégias em cascata."""
    content_str = llm_output.content if hasattr(llm_output, "content") else str(llm_output)

    # 1. bloco ```json ... ```
    m = re.search(r"```json\s*([\s\S]*?)\s*```", content_str)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 2. qualquer bloco ``` ... ```
    m = re.search(r"```\s*([\s\S]*?)\s*```", content_str)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. primeiro { ... } encontrado no texto livre
    m = re.search(r"\{[\s\S]*\}", content_str)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # 4. texto limpo direto
    try:
        return json.loads(content_str.strip())
    except json.JSONDecodeError:
        pass

    return {"error": "Falha ao decodificar JSON", "raw_content": content_str[:800]}


# ============================================================
# GRAFO — criado uma única vez por sessão do servidor
# ============================================================
@st.cache_resource
def get_compiled_graph():
    """
    Inicializa LLM, chains e grafo LangGraph.
    @st.cache_resource garante que o grafo seja compilado uma única vez,
    evitando reinicialização a cada rerun do Streamlit.
    """
    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=TEMPERATURE,
        api_key=GOOGLE_API_KEY,
    )

    SYSTEM_BASE = (
        "Você é um membro de uma equipe de marketing de elite especialista em copy para "
        "lançamentos de infoprodutos. Sua resposta deve ser sempre um bloco de código JSON "
        "válido, sem nenhum texto adicional antes ou depois. Utilize o tom de voz definido "
        "no briefing. Foque em clareza, estratégia e em gerar ativos prontos para usar."
    )

    chain_dores = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_BASE + (
            " Extraia as dores mais profundas e as promessas de transformação mais impactantes. "
            "Retorne um JSON com as chaves 'dores' (lista) e 'promessas' (lista)."
        )),
        ("human", "Briefing:\n{briefing}\n\nContexto RAG:\n{contexto}"),
    ]) | llm

    chain_objecoes = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_BASE + (
            " Liste as objeções mais prováveis do público e crie quebras de objeção persuasivas. "
            "Retorne um JSON com as chaves 'objecoes' (lista) e 'quebras' (lista)."
        )),
        ("human", "Briefing:\n{briefing}\n\nContexto RAG:\n{contexto}"),
    ]) | llm

    chain_headlines = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_BASE + (
            " Crie headlines magnéticas e ângulos de comunicação criativos. "
            "Retorne um JSON com as chaves 'headlines' (lista) e 'angulos' (lista)."
        )),
        ("human", "Briefing:\n{briefing}\n\nContexto RAG:\n{contexto}"),
    ]) | llm

    chain_canais = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_BASE + (
            " Adapte a mensagem para 4 canais de comunicação, criando a copy final. "
            "Se houver feedback de revisão anterior, aplique as melhorias indicadas. "
            "Retorne um JSON com as chaves: "
            "'email' (objeto com 'subject' e 'body'), "
            "'stories' (lista de slides, cada um com 'visual' e 'copy'), "
            "'ads' (lista de anúncios, cada um com 'headline', 'primary_text' e 'link_description'), "
            "'vsl' (objeto com 'script': lista de blocos com 'time', 'segment' e 'copy')."
        )),
        ("human", (
            "Briefing Original:\n{briefing}\n\n"
            "Contexto Enriquecido:\n{contexto_enriquecido}\n\n"
            "Feedback de Revisão Anterior:\n{revisao_critico}"
        )),
    ]) | llm

    chain_critico = ChatPromptTemplate.from_messages([
        ("system", (
            "Você é um CRÍTICO DE MARKETING sênior e exigente. Revise a copy gerada. "
            "Se estiver excelente, responda APENAS a palavra 'APROVADO'. "
            "Se precisar de ajustes, responda 'REFINAR:' seguido de uma lista de pontos "
            "específicos e acionáveis."
        )),
        ("human", "Briefing Original:\n{briefing}\n\nCopy para revisão:\n{copy_por_canal}"),
    ]) | llm

    # ── Nós do Grafo ──────────────────────────────────────────
    def node_dores_promessas(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Agente Dores & Promessas:* analisando o briefing...")
        result = chain_dores.invoke({
            "briefing": json.dumps(state["briefing"], ensure_ascii=False),
            "contexto": state["contexto_rag"],
        })
        return {"dores_promessas": force_json(result)}

    def node_objecoes_quebras(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Agente Objeções & Quebras:* mapeando resistências...")
        result = chain_objecoes.invoke({
            "briefing": json.dumps(state["briefing"], ensure_ascii=False),
            "contexto": state["contexto_rag"],
        })
        return {"objecoes_quebras": force_json(result)}

    def node_headlines_angulos(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Agente Headlines & Ângulos:* criando chamadas magnéticas...")
        result = chain_headlines.invoke({
            "briefing": json.dumps(state["briefing"], ensure_ascii=False),
            "contexto": state["contexto_rag"],
        })
        return {"headlines_angulos": force_json(result)}

    def node_consolidador(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Consolidador:* reunindo visões e gerando contexto enriquecido...")
        for key in ("dores_promessas", "objecoes_quebras", "headlines_angulos"):
            if state.get(key) and "error" in state[key]:
                return {"contexto_enriquecido": json.dumps({"error": f"Erro em {key}"})}
        return {
            "contexto_enriquecido": json.dumps({
                "dores_e_promessas": state.get("dores_promessas", {}),
                "objecoes_e_quebras": state.get("objecoes_quebras", {}),
                "headlines_e_angulos": state.get("headlines_angulos", {}),
            }, ensure_ascii=False, indent=2)
        }

    def node_adaptacao_canais(state: AgentState) -> Dict[str, Any]:
        tentativa = state.get("tentativas_refinamento", 0) + 1
        st.write(f"🔄 *Adaptador de Canais:* escrevendo copys (tentativa {tentativa})...")
        contexto = state.get("contexto_enriquecido", "{}")
        try:
            if "error" in json.loads(contexto):
                return {
                    "copy_por_canal": {"error": "Geração interrompida."},
                    "tentativas_refinamento": tentativa,
                }
        except (json.JSONDecodeError, TypeError):
            pass
        result = chain_canais.invoke({
            "briefing": json.dumps(state["briefing"], ensure_ascii=False),
            "contexto_enriquecido": contexto,
            "revisao_critico": state.get("revisao_critico") or "Nenhuma. Esta é a primeira versão.",
        })
        return {"copy_por_canal": force_json(result), "tentativas_refinamento": tentativa}

    def node_critico_revisor(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Crítico Revisor:* avaliando qualidade e aderência técnica...")
        copy_gerada = state.get("copy_por_canal", {})
        if "error" in copy_gerada:
            return {"revisao_critico": "ERRO_NA_GERACAO"}
        result = chain_critico.invoke({
            "briefing": json.dumps(state["briefing"], ensure_ascii=False),
            "copy_por_canal": json.dumps(copy_gerada, ensure_ascii=False),
        })
        st.info(f"💬 **Feedback do Crítico:** {result.content}")
        return {"revisao_critico": result.content}

    def decidir_pos_critica(state: AgentState) -> str:
        revisao = state.get("revisao_critico", "")
        tentativas = state.get("tentativas_refinamento", 0)
        if (
            "ERRO_NA_GERACAO" in revisao
            or "APROVADO" in revisao
            or tentativas >= MAX_REFINEMENT_ATTEMPTS
        ):
            return "end"
        return "refinar"

    # ── Construção do Grafo ────────────────────────────────────
    # START importado explicitamente — substitui o set_entry_point múltiplo anterior
    graph = StateGraph(AgentState)
    graph.add_node("analise_dores_promessas", node_dores_promessas)
    graph.add_node("analise_objecoes_quebras", node_objecoes_quebras)
    graph.add_node("analise_headlines_angulos", node_headlines_angulos)
    graph.add_node("consolidador", node_consolidador)
    graph.add_node("adaptacao_canais", node_adaptacao_canais)
    graph.add_node("critico_revisor", node_critico_revisor)

    # 3 nós de análise partem do START em paralelo (mesmo super-step)
    graph.add_edge(START, "analise_dores_promessas")
    graph.add_edge(START, "analise_objecoes_quebras")
    graph.add_edge(START, "analise_headlines_angulos")

    # Convergência → consolidador → canais → crítico
    graph.add_edge("analise_dores_promessas", "consolidador")
    graph.add_edge("analise_objecoes_quebras", "consolidador")
    graph.add_edge("analise_headlines_angulos", "consolidador")
    graph.add_edge("consolidador", "adaptacao_canais")
    graph.add_edge("adaptacao_canais", "critico_revisor")

    # Loop de refinamento (máx MAX_REFINEMENT_ATTEMPTS)
    graph.add_conditional_edges(
        "critico_revisor",
        decidir_pos_critica,
        {"refinar": "adaptacao_canais", "end": END},
    )

    return graph.compile()


# ============================================================
# RAG — setup e recuperação
# ============================================================
def setup_rag(briefing_dinamico: Dict, problema_principal: str) -> str:
    """Limpa, indexa e recupera contexto relevante do briefing via ChromaDB."""
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    canonical_text = canonicalize_briefing_to_text(briefing_dinamico)
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = splitter.create_documents([canonical_text])
    vectorstore.add_documents(docs)

    retriever = vectorstore.as_retriever()
    relevant_docs = retriever.invoke(problema_principal)
    return "\n\n".join(
        f"[Fonte: doc{i+1}]\n{doc.page_content}"
        for i, doc in enumerate(relevant_docs)
    )


# ============================================================
# SESSION STATE — inicialização
# ============================================================
if "final_copy" not in st.session_state:
    st.session_state.final_copy = None


# ============================================================
# UI — CABEÇALHO
# ============================================================
st.set_page_config(page_title="CopyWriter AI", layout="wide")
st.title("🤖 Geração de Copy para Lançamentos com LangGraph")
st.write("Preencha o briefing para colocar a equipe de agentes de IA para trabalhar cooperativamente.")

if not GOOGLE_API_KEY:
    st.error("⚠️ GOOGLE_API_KEY não encontrada. Crie um arquivo `.env` com a chave antes de continuar.")
    st.stop()


# ============================================================
# UI — FORMULÁRIO DE ENTRADA (4 ABAS)
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs(["📦 O Infoproduto", "👥 Público-Alvo", "🎯 Posicionamento", "📅 Estratégia"])

with tab1:
    st.subheader("Dados do Produto")
    nome_produto = st.text_input("Nome do Infoproduto", "Mentoria de Desenvolvimento Inteligente")
    produtor = st.text_input("Nome do Produtor", "Mauricio Issei")
    preco = st.number_input("Preço (R$)", value=2997.0, step=100.0)
    formato = st.text_input("Formato do Produto", "Mentoria com aulas ao vivo + comunidade")
    descricao = st.text_area(
        "Descrição do Produto",
        "Mentoria para desenvolvedores que querem dominar arquitetura de software, "
        "design patterns e desenvolvimento orientado a resultados.",
    )

with tab2:
    st.subheader("Persona e Dores")
    demografia = st.text_area(
        "Perfil do Público",
        "Desenvolvedores Full-Stack, 25-45 anos, 3+ anos de experiência, R$ 5k-20k/mês.",
    )
    problema_principal = st.text_area(
        "Dor Principal",
        "Sinto que estou estagnado tecnicamente, não acompanho as melhores práticas "
        "e tenho dificuldade em arquitetar soluções escaláveis.",
    )
    transformacao_principal = st.text_area(
        "Transformação Prometida",
        "Dominar arquitetura de software, ser um dev procurado e aumentar o salário em 50%.",
    )
    objecoes_texto = st.text_area(
        "Objeções (uma por linha)",
        "Não tenho tempo\nJá fiz cursos que não funcionaram\nO preço é alto",
        height=100,
    )
    objecoes_comuns = [l.strip() for l in objecoes_texto.split("\n") if l.strip()]

with tab3:
    st.subheader("Posicionamento")
    diferencial = st.text_area(
        "USP / Diferencial Competitivo",
        "A única mentoria com foco em arquitetura de software real + comunidade de devs sênior.",
    )
    tom_de_voz = st.text_input("Tom de Voz", "Direto, sem BS, prático, baseado em casos reais.")
    gatilhos_texto = st.text_input(
        "Gatilhos Mentais (vírgula)",
        "Escassez, Autoridade, Comunidade, Transformação de identidade",
    )
    gatilhos_mentais = [g.strip() for g in gatilhos_texto.split(",") if g.strip()]

with tab4:
    st.subheader("Estratégia de Lançamento")
    tipo_lancamento = st.text_input("Tipo de Lançamento", "VSL + Sequência de email")
    meta_campanha = st.text_input("Meta", "Vender 50 mentorias a R$ 2.997")
    col1, col2, col3 = st.columns(3)
    with col1:
        ini_campanha = st.text_input("Início da Campanha", "2026-06-01")
    with col2:
        abert_carrinho = st.text_input("Abertura do Carrinho", "2026-06-05")
    with col3:
        fech_carrinho = st.text_input("Fechamento do Carrinho", "2026-06-07")
    canais_texto = st.text_input(
        "Canais (vírgula)",
        "Email Marketing, Meta Ads, Instagram Stories, YouTube (VSL)",
    )
    canais = [c.strip() for c in canais_texto.split(",") if c.strip()]


# ============================================================
# UI — BOTÕES DE AÇÃO
# ============================================================
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


# ============================================================
# EXECUÇÃO DO GRAFO
# ============================================================
if gerar:
    briefing_dinamico = {
        "briefing_lancamento": {
            "infoproduto": {
                "nome": nome_produto,
                "produtor": produtor,
                "preco": preco,
                "formato": formato,
                "descricao": descricao,
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
        }
    }

    st.subheader("⚙️ Execução do Grafo em Tempo Real")

    with st.spinner("Indexando briefing no RAG local..."):
        rag_context = setup_rag(briefing_dinamico, problema_principal)

    initial_state = AgentState(
        briefing=briefing_dinamico,
        contexto_rag=rag_context,
        tentativas_refinamento=0,
    )

    final_copy_state = None
    with st.spinner("Agentes colaborando na criação da campanha..."):
        for event in get_compiled_graph().stream(initial_state):
            if "adaptacao_canais" in event:
                final_copy_state = event["adaptacao_canais"]

    st.success("✅ Execução do Grafo de Agentes Concluída!")

    if final_copy_state and "copy_por_canal" in final_copy_state:
        # Persiste no session_state para sobreviver a reruns
        st.session_state.final_copy = final_copy_state["copy_por_canal"]
    else:
        st.error("Não foi possível recuperar o estado final das copys.")


# ============================================================
# UI — RESULTADOS (lidos do session_state — persistem entre reruns)
# ============================================================
if st.session_state.final_copy:
    final_copy = st.session_state.final_copy
    st.divider()
    st.header("📋 Resultados Finais da Copy")

    # Erro de parsing → expander de debug
    if "error" in final_copy:
        st.error(f"Erro no processamento da IA: {final_copy['error']}")
        with st.expander("🔍 Ver conteúdo bruto para debug"):
            st.code(final_copy.get("raw_content", "sem conteúdo"), language="text")
        st.stop()

    out_tab1, out_tab2, out_tab3, out_tab4, out_json = st.tabs([
        "📧 Email Marketing",
        "📱 Instagram Stories",
        "📺 YouTube (VSL)",
        "📢 Meta Ads",
        "📄 JSON Completo",
    ])

    # ── Email ──────────────────────────────────────────────────
    with out_tab1:
        email_data = final_copy.get("email", {})
        # aceita tanto 'subject'/'body' quanto 'assunto'/'corpo'
        subject = email_data.get("subject", email_data.get("assunto", ""))
        body = email_data.get("body", email_data.get("corpo", ""))

        st.subheader(f"Assunto: {subject}")
        st.text_area("Corpo do Email", body, height=400, key="email_body_display")

        email_txt = f"ASSUNTO:\n{subject}\n\n{'─' * 60}\n\n{body}"
        st.download_button(
            "⬇️ Baixar Email (.txt)",
            data=email_txt,
            file_name="email_marketing.txt",
            mime="text/plain",
        )

    # ── Stories ────────────────────────────────────────────────
    with out_tab2:
        stories_data = final_copy.get("stories", [])
        if not stories_data:
            st.info("Nenhum slide gerado.")
        else:
            stories_txt_lines = []
            for i, slide in enumerate(stories_data):
                # suporta formato {slide_N: {visual, copy}} e {visual, copy} direto
                if isinstance(slide, dict):
                    slide_key = f"slide_{i + 1}"
                    data = slide.get(slide_key, slide)
                    visual = data.get("visual", data.get("imagem", ""))
                    copy_text = data.get("copy", data.get("texto", ""))
                else:
                    visual, copy_text = "", str(slide)

                st.markdown(f"**Slide {i + 1}**")
                st.info(f"🎬 *Visual:* {visual}")
                st.write(f"✍️ *Texto:* {copy_text}")
                st.divider()
                stories_txt_lines.append(
                    f"SLIDE {i + 1}\nVisual: {visual}\nTexto: {copy_text}\n"
                )

            st.download_button(
                "⬇️ Baixar Stories (.txt)",
                data="\n".join(stories_txt_lines),
                file_name="instagram_stories.txt",
                mime="text/plain",
            )

    # ── VSL ────────────────────────────────────────────────────
    with out_tab3:
        vsl = final_copy.get("vsl", {})
        script_blocks = vsl.get("script", []) if isinstance(vsl, dict) else []
        if not script_blocks:
            st.info("Nenhum script VSL gerado.")
        else:
            vsl_txt_lines = []
            for bloco in script_blocks:
                time_mark = bloco.get("time", "")
                segment = bloco.get("segment", "")
                copy_text = bloco.get("copy", "")
                st.markdown(f"⏱️ **{time_mark}** — *{segment}*")
                st.write(copy_text)
                st.divider()
                vsl_txt_lines.append(f"[{time_mark}] {segment}\n{copy_text}\n")

            st.download_button(
                "⬇️ Baixar Script VSL (.txt)",
                data="\n".join(vsl_txt_lines),
                file_name="script_vsl.txt",
                mime="text/plain",
            )

    # ── Meta Ads ───────────────────────────────────────────────
    with out_tab4:
        ads_data = final_copy.get("ads", [])
        if not ads_data:
            st.info("Nenhum anúncio gerado.")
        else:
            ads_txt_lines = []
            for i, ad in enumerate(ads_data):
                headline = ad.get("headline", "")
                primary = ad.get("primary_text", ad.get("texto_principal", ""))
                link_desc = ad.get("link_description", ad.get("descricao_link", ""))

                st.markdown(f"🎯 **Variação de Anúncio {i + 1}**")
                st.write(f"**Headline:** {headline}")
                st.write(f"**Texto Principal:** {primary}")
                st.caption(f"Descrição do link: {link_desc}")
                st.divider()
                ads_txt_lines.append(
                    f"VARIAÇÃO {i + 1}\nHeadline: {headline}\nTexto: {primary}\nLink: {link_desc}\n"
                )

            st.download_button(
                "⬇️ Baixar Anúncios (.txt)",
                data="\n".join(ads_txt_lines),
                file_name="meta_ads.txt",
                mime="text/plain",
            )

    # ── JSON Completo ──────────────────────────────────────────
    with out_json:
        st.json(final_copy)
        st.download_button(
            "⬇️ Baixar JSON Completo",
            data=json.dumps(final_copy, ensure_ascii=False, indent=2),
            file_name="copy_completa.json",
            mime="application/json",
        )
