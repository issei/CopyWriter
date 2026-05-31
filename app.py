import os
import json
import re
import shutil
from typing import TypedDict, Optional, Dict, Any, List
import streamlit as st

# LangChain e LangGraph
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import StateGraph, END

# --- CONFIGURAÇÃO DA API KEY (Como solicitado, fixa no código) ---
GOOGLE_API_KEY = "AIzaSyDLq9oBFly7YvpLkD-gXmYKsMm3S7Z9w9E" 
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Parâmetros Globais
GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.7
MAX_REFINEMENT_ATTEMPTS = 2

# --- DEFINIÇÃO DO ESTADO DO GRAFO ---
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

# --- CONFIGURAÇÃO DO STREAMLIT (FRONTEND) ---
st.set_page_config(page_title="Gerador de Copy com Agentes de IA", layout="wide")
st.title("🤖 Geração de Copy para Lançamentos com LangGraph")
st.write("Preencha o briefing abaixo para colocar a equipe de agentes de IA para trabalhar cooperativamente.")

# Criação das Abas do Formulário de Entrada
tab1, tab2, tab3, tab4 = st.tabs(["📦 O Infoproduto", "👥 Público-Alvo", "🎯 Posicionamento", "📅 Estratégia"])

with tab1:
    st.subheader("Dados do Produto")
    nome_produto = st.text_input("Nome do Infoproduto", "Mentoria de Desenvolvimento Inteligente")
    produtor = st.text_input("Nome do Produtor", "Mauricio Issei")
    preco = st.number_input("Preço (R$)", value=999.97, step=100.0)
    formato = st.text_input("Formato do Produto", "Mentoria Individual")
    descricao = st.text_area("Descrição do Produto", "Mentoria individual para desenvolver arquiteturas de soluções complexas de software utilizando IA.")

with tab2:
    st.subheader("Persona e Dores")
    demografia = st.text_area("Demografia / Perfil do Público", "Empreendedores digitais, desenvolvedores de software e profissionais de tecnologia.")
    problema_principal = st.text_area("Problema/Dor Principal", "Dificuldade em arquitetar soluções robustas e escaláveis, falta de um método claro para o desenvolvimento, resultando em baixo faturamento e projetos estagnados.")
    transformacao_principal = st.text_area("Transformação Principal", "Capacidade de criar soluções de software de alta qualidade e escaláveis do zero, alcançando faturamento de 6 ou 7 dígitos.")
    
    st.write("**Objeções Comuns (uma por linha):**")
    objecoes_texto = st.text_area("Objeções", "Não tenho conhecimento técnico suficiente\nO preço é muito alto para mim\nNão tenho tempo para aplicar o método", height=100)
    objecoes_comuns = [line.strip() for line in objecoes_texto.split("\n") if line.strip()]

with tab3:
    st.subheader("Diferenciais e Comunicação")
    diferencial = st.text_area("Diferencial Competitivo (USP)", "Único método que combina estratégia de arquitetura de soluções de software com o poder do desenvolvimento acelerado por ferramentas de IA.")
    tom_de_voz = st.text_input("Tom de Voz", "Autoridade, inspirador e prático.")
    
    st.write("**Gatilhos Mentais Prioritários (separados por vírgula):**")
    gatilhos_texto = st.text_input("Gatilhos", "Autoridade, Prova Social, Escassez, Reciprocidade")
    gatilhos_mentais = [g.strip() for g in gatilhos_texto.split(",") if g.strip()]

with tab4:
    st.subheader("Planejamento do Lançamento")
    tipo_lancamento = st.text_input("Tipo de Lançamento", "Semente")
    meta_campanha = st.text_input("Meta da Campanha", "Vender 50 unidades e faturar R$ 50.000")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        ini_campanha = st.text_input("Início da Campanha", "2025-09-15")
    with col2:
        abert_carrinho = st.text_input("Abertura do Carrinho", "2025-09-22")
    with col3:
        fech_carrinho = st.text_input("Fechamento do Carrinho", "2025-09-29")
        
    st.write("**Canais de Comunicação (separados por vírgula):**")
    canais_texto = st.text_input("Canais", "Email Marketing, Meta Ads, Instagram Stories, YouTube (VSL)")
    canais = [c.strip() for c in canais_texto.split(",") if c.strip()]

# --- LÓGICA BACKEND (FUNÇÕES AUXILIARES E AGENTES) ---

def canonicalize_briefing_to_text(briefing_dict: Dict[str, Any]) -> str:
    b = briefing_dict.get("briefing_lancamento", {})
    inf = b.get("infoproduto", {})
    pub = b.get("publico_alvo", {})
    pos = b.get("posicionamento", {})
    est = b.get("estrategia_lancamento", {})
    datas = est.get("datas_chave", {})

    linhas = [
        "# Briefing de Lançamento — Canonicalizado",
        "## Produto",
        f"Nome: {inf.get('nome','')} | Produtor: {inf.get('produtor','')} | Preço: {inf.get('preco','')} | Formato: {inf.get('formato','')}",
        f"Descrição: {inf.get('descricao','')}",
        "\n## Público-alvo & Persona",
        f"Demografia/Psicografia: {pub.get('demografia','')}",
        f"Dor principal: {pub.get('problema_principal','')}",
        f"Transformação: {pub.get('transformacao_principal','')}",
    ]
    if pub.get("objecoes_comuns"):
        linhas.append("Objeções comuns:")
        for o in pub["objecoes_comuns"]:
            linhas.append(f"- {o}")

    linhas.extend([
        "\n## Posicionamento & Diferencial",
        f"USP: {pos.get('diferencial_competitivo','')}",
        f"Tom de voz: {pos.get('tom_de_voz','')}",
    ])
    if pos.get("gatilhos_mentais"):
        linhas.append("Gatilhos prioritários: " + ", ".join(pos["gatilhos_mentais"]))

    linhas.extend([
        "\n## Estratégia de Lançamento",
        f"Tipo: {est.get('tipo_lancamento','')} | Meta: {est.get('meta_campanha','')}",
        f"Período/Datas: início={datas.get('inicio_campanha','')} | abertura={datas.get('abertura_carrinho','')} | fechamento={datas.get('fechamento_carrinho','')}",
    ])
    if est.get("canais"):
        linhas.append("Canais: " + ", ".join(est["canais"]))

    return "\n".join(linhas)

def force_json(llm_output: Any) -> Dict:
    content_str = llm_output.content if hasattr(llm_output, 'content') else str(llm_output)

    # Estratégia 1: bloco ```json ... ```
    match = re.search(r"```json\s*([\s\S]*?)\s*```", content_str)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Estratégia 2: qualquer bloco de código ``` ... ```
    match = re.search(r"```\s*([\s\S]*?)\s*```", content_str)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Estratégia 3: extrai o maior bloco { ... } do texto
    match = re.search(r"\{[\s\S]*\}", content_str)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Estratégia 4: tenta o texto completo limpo
    try:
        return json.loads(content_str.strip())
    except json.JSONDecodeError:
        pass

    # Fallback: retorna o texto bruto para debug
    return {"error": "Falha ao decodificar JSON", "raw_content": content_str[:500]}

# Inicialização de Modelos
llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=TEMPERATURE)
SYSTEM_BASE = (
    "Você é um membro de uma equipe de marketing de elite especialista em copy para lançamentos de infoprodutos. "
    "Sua resposta deve ser sempre um bloco de código JSON, sem nenhum texto adicional antes ou depois. "
    "Utilize o tom de voz definido no briefing. Foque em clareza, estratégia e em gerar ativos prontos para usar. "
    "Respeite a persona (dores, desejos) e o posicionamento (USP) do produto."
)

# Definição das Cadeias
prompt_dores = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_BASE + " Extraia as dores mais profundas do público e as promessas de transformação mais impactantes. Retorne um JSON com chaves 'dores' e 'promessas'."),
    ("human", "Briefing:\n{briefing}\n\nContexto Adicional (RAG):\n{contexto}")
])
chain_dores = prompt_dores | llm

prompt_objecoes = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_BASE + " Liste as objeções mais prováveis do público e crie quebras de objeção persuasivas. Retorne um JSON com chaves 'objecoes' e 'quebras'."),
    ("human", "Briefing:\n{briefing}\n\nContexto Adicional (RAG):\n{contexto}")
])
chain_objecoes = prompt_objecoes | llm

prompt_headlines = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_BASE + " Crie headlines magnéticas e ângulos de comunicação criativos para os anúncios e emails. Retorne um JSON com chaves 'headlines' e 'angulos'."),
    ("human", "Briefing:\n{briefing}\n\nContexto Adicional (RAG):\n{contexto}")
])
chain_headlines = prompt_headlines | llm

prompt_canais = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_BASE + " Adapte a mensagem para os canais de comunicação, criando a copy final. Se receber um feedback de revisão, aplique as melhorias. Retorne um JSON com chaves 'email', 'stories', 'ads', 'vsl'."),
    ("human", "Briefing Original:\n{briefing}\n\nContexto Enriquecido (Análises dos outros agentes):\n{contexto_enriquecido}\n\nFeedback de Revisão Anterior (se houver):\n{revisao_critico}")
])
chain_canais = prompt_canais | llm

prompt_critico = ChatPromptTemplate.from_messages([
    ("system", "Você é um CRÍTICO DE MARKETING sênior e exigente. Sua tarefa é revisar a copy gerada. Se estiver excelente, responda apenas 'APROVADO'. Se precisar de ajustes, responda 'REFINAR:' seguido por uma lista de pontos específicos e acionáveis."),
    ("human", "Briefing Original:\n{briefing}\n\nCopy Gerada para Revisão:\n{copy_por_canal}")
])
chain_critico = prompt_critico | llm

# Nós do Grafo que atualizam a interface gráfica com o status
def node_dores_promessas(state: AgentState) -> Dict[str, Any]:
    st.write("🔄 *Agente Dores & Promessas:* Analisando o briefing...")
    result = chain_dores.invoke({"briefing": json.dumps(state['briefing']), "contexto": state['contexto_rag']})
    return {"dores_promessas": force_json(result)}

def node_objecoes_quebras(state: AgentState) -> Dict[str, Any]:
    st.write("🔄 *Agente Objeções & Quebras:* Mapeando resistências...")
    result = chain_objecoes.invoke({"briefing": json.dumps(state['briefing']), "contexto": state['contexto_rag']})
    return {"objecoes_quebras": force_json(result)}

def node_headlines_angulos(state: AgentState) -> Dict[str, Any]:
    st.write("🔄 *Agente Headlines & Ângulos:* Criando chamadas magnéticas...")
    result = chain_headlines.invoke({"briefing": json.dumps(state['briefing']), "contexto": state['contexto_rag']})
    return {"headlines_angulos": force_json(result)}

def node_consolidador(state: AgentState) -> Dict[str, Any]:
    st.write("🔄 *Consolidador:* Reunindo visões e gerando super contexto...")
    for key in ['dores_promessas', 'objecoes_quebras', 'headlines_angulos']:
        if state.get(key) and 'error' in state[key]:
            return {"contexto_enriquecido": json.dumps({"error": f"Erro em {key}"})}
    contexto_enriquecido = json.dumps({
        "dores_e_promessas": state.get('dores_promessas', {}),
        "objecoes_e_quebras": state.get('objecoes_quebras', {}),
        "headlines_e_angulos": state.get('headlines_angulos', {})
    }, indent=2, ensure_ascii=False)
    return {"contexto_enriquecido": contexto_enriquecido}

def node_adaptacao_canais(state: AgentState) -> Dict[str, Any]:
    st.write(f"🔄 *Adaptador de Canais:* Escrevendo as copys (Tentativa {state.get('tentativas_refinamento', 0) + 1})...")
    contexto = state.get('contexto_enriquecido', '{}')
    try:
        if 'error' in json.loads(contexto):
            return {"copy_por_canal": {"error": "Geração interrompida."}}
    except (json.JSONDecodeError, TypeError):
        pass
    tentativas = state.get('tentativas_refinamento', 0) + 1
    revisao = state.get('revisao_critico') or "Nenhuma. Esta é a primeira versão."
    result = chain_canais.invoke({
        "briefing": json.dumps(state['briefing']),
        "contexto_enriquecido": contexto,
        "revisao_critico": revisao
    })
    return {"copy_por_canal": force_json(result), "tentativas_refinamento": tentativas}

def node_critico_revisor(state: AgentState) -> Dict[str, Any]:
    st.write("🔄 *Crítico Revisor:* Avaliando qualidade e aderência técnica...")
    copy_gerada = state.get('copy_por_canal', {})
    if 'error' in copy_gerada:
        return {"revisao_critico": "ERRO_NA_GERACAO"}
    result = chain_critico.invoke({
        "briefing": json.dumps(state['briefing']),
        "copy_por_canal": json.dumps(copy_gerada)
    })
    st.info(f"💬 **Feedback do Crítico:** {result.content}")
    return {"revisao_critico": result.content}

def decidir_pos_critica(state: AgentState) -> str:
    revisao = state.get('revisao_critico', '')
    tentativas = state.get('tentativas_refinamento', 0)
    if "ERRO_NA_GERACAO" in revisao or "APROVADO" in revisao or tentativas >= MAX_REFINEMENT_ATTEMPTS:
        return "end"
    else:
        return "refinar"

# Construção do Fluxo de Trabalho (LangGraph)
workflow = StateGraph(AgentState)
workflow.add_node("analise_dores_promessas", node_dores_promessas)
workflow.add_node("analise_objecoes_quebras", node_objecoes_quebras)
workflow.add_node("analise_headlines_angulos", node_headlines_angulos)
workflow.add_node("consolidador", node_consolidador)
workflow.add_node("adaptacao_canais", node_adaptacao_canais)
workflow.add_node("critico_revisor", node_critico_revisor)

workflow.set_entry_point("analise_dores_promessas")
workflow.set_entry_point("analise_objecoes_quebras")
workflow.set_entry_point("analise_headlines_angulos")

workflow.add_edge("analise_dores_promessas", "consolidador")
workflow.add_edge("analise_objecoes_quebras", "consolidador")
workflow.add_edge("analise_headlines_angulos", "consolidador")
workflow.add_edge("consolidador", "adaptacao_canais")
workflow.add_edge("adaptacao_canais", "critico_revisor")

workflow.add_conditional_edges(
    "critico_revisor",
    decidir_pos_critica,
    {"refinar": "adaptacao_canais", "end": END}
)
app = workflow.compile()


# --- BOTÃO DE EXECUÇÃO ---
if st.button("🚀 Iniciar Inteligência de Grafo e Gerar Copy", type="primary"):
    
    # 1. Montagem do dicionário de briefing dinâmico baseado nos inputs do Frontend
    briefing_dinamico = {
        "briefing_lancamento": {
            "infoproduto": {
                "nome": nome_produto,
                "produtor": produtor,
                "preco": preco,
                "formato": formato,
                "descricao": descricao
            },
            "publico_alvo": {
                "demografia": demografia,
                "problema_principal": problema_principal,
                "transformacao_principal": transformacao_principal,
                "objecoes_comuns": objecoes_comuns
            },
            "posicionamento": {
                "diferencial_competitivo": diferencial,
                "tom_de_voz": tom_de_voz,
                "gatilhos_mentais": gatilhos_mentais
            },
            "estrategia_lancamento": {
                "tipo_lancamento": tipo_lancamento,
                "meta_campanha": meta_campanha,
                "datas_chave": {
                    "inicio_campanha": ini_campanha,
                    "abertura_carrinho": abert_carrinho,
                    "fechamento_carrinho": fech_carrinho
                },
                "canais": canais
            }
        }
    }
    
    st.subheader("⚙️ Execução do Grafo em Tempo Real")
    
    with st.spinner("Processando e Indexando o Briefing no RAG local..."):
        # Limpar vetorização anterior para evitar contaminação de contexto
        if os.path.exists("./chroma_db"):
            shutil.rmtree("./chroma_db")
            
        canonical_text = canonicalize_briefing_to_text(briefing_dinamico)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        docs = text_splitter.create_documents([canonical_text])
        vectorstore.add_documents(docs)
        
        # Recuperação atualizada usando invoke() como recomendado
        retriever = vectorstore.as_retriever()
        relevant_docs = retriever.invoke(problema_principal)
        rag_context = "\n\n".join(f"[Fonte: doc{i+1}]\n{doc.page_content}" for i, doc in enumerate(relevant_docs))

    # Execução do Grafo
    initial_state = AgentState(
        briefing=briefing_dinamico,
        contexto_rag=rag_context,
        tentativas_refinamento=0
    )
    
    final_copy_state = None
    with st.spinner("Agentes colaborando na criação da sua campanha..."):
        for event in app.stream(initial_state):
            if "adaptacao_canais" in event:
                final_copy_state = event["adaptacao_canais"]
                
    st.success("✅ Execução do Grafo de Agentes Concluída!")
    
    # --- EXIBIÇÃO DOS RESULTADOS NO FRONTEND ---
    if final_copy_state and "copy_por_canal" in final_copy_state:
        final_copy = final_copy_state["copy_por_canal"]
        
        if "error" in final_copy:
            st.error(f"Erro no processamento da IA: {final_copy['error']}")
        else:
            st.header("📋 Resultados Finais da Copy")
            
            out_tab1, out_tab2, out_tab3, out_tab4, out_json = st.tabs(["📧 Email Marketing", "📱 Instagram Stories", "📺 YouTube (VSL)", "📢 Meta Ads", "📄 JSON Completo"])
            
            with out_tab1:
                email_data = final_copy.get("email", {})
                st.subheader(f"Assunto: {email_data.get('subject', '')}")
                st.text_area("Corpo do Email", email_data.get("body", ""), height=400)
                
            with out_tab2:
                stories_data = final_copy.get("stories", [])
                for i, slide in enumerate(stories_data):
                    slide_key = f"slide_{i+1}"
                    if slide_key in slide:
                        st.markdown(f"**Slide {i+1}**")
                        st.info(f"🎬 *Visual:* {slide[slide_key].get('visual', '')}")
                        st.write(f"✍️ *Texto:* {slide[slide_key].get('copy', '')}")
                        st.divider()
                        
            with out_tab3:
                vsl_data = final_copy.get("vsl", {}).get("script", [])
                for bloco in vsl_data:
                    st.markdown(f"⏱️ **{bloco.get('time', '')}** — *{bloco.get('segment', '')}*")
                    st.write(bloco.get("copy", ""))
                    st.divider()
                    
            with out_tab4:
                ads_data = final_copy.get("ads", [])
                for i, ad in enumerate(ads_data):
                    st.markdown(f"🎯 **Variação de Anúncio {i+1}**")
                    st.write(f"**Headline:** {ad.get('headline', '')}")
                    st.write(f"**Texto Principal:** {ad.get('primary_text', '')}")
                    st.caption(f"Descrição do link: {ad.get('link_description', '')}")
                    st.divider()
                    
            with out_json:
                st.json(final_copy)
    else:
        st.error("Não foi possível resgatar o estado final das copys.")