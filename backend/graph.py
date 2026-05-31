"""
LangGraph: grafo de agentes com 4 nós de análise em paralelo,
agente de prova social, 4 chains especializadas por canal e loop de refinamento.
"""
import json
from typing import TypedDict, Optional, Dict, Any

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

from backend.llm import get_llm
from backend.parsers import force_json
from config import MAX_REFINEMENT


# ── Estado ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    briefing: Dict
    contexto_rag: str
    dores_promessas: Optional[Dict]
    objecoes_quebras: Optional[Dict]
    headlines_angulos: Optional[Dict]
    contexto_enriquecido: Optional[str]
    prova_social: Optional[str]          # novo: snippets de prova social formatados
    copy_por_canal: Optional[Dict]
    revisao_critico: Optional[str]
    tentativas_refinamento: int


# ── Grafo compilado (singleton por sessão) ────────────────────────────────────

@st.cache_resource
def get_compiled_graph():
    """
    Cria LLM, todas as chains e compila o grafo.
    @st.cache_resource garante que isso ocorra uma única vez por sessão.
    """
    llm = get_llm()

    BASE = (
        "Você é um especialista em marketing de lançamentos de infoprodutos. "
        "Responda SEMPRE com um bloco JSON válido, sem texto antes ou depois."
    )

    # ── Chains de análise (paralelas) ────────────────────────────────────────

    chain_dores = ChatPromptTemplate.from_messages([
        ("system", BASE + " Extraia as DORES profundas e as PROMESSAS transformacionais. "
                         "JSON: {\"dores\": [...], \"promessas\": [...]}"),
        ("human", "Briefing:\n{briefing}\n\nContexto RAG:\n{contexto}"),
    ]) | llm

    chain_objecoes = ChatPromptTemplate.from_messages([
        ("system", BASE + " Liste objeções prováveis e crie quebras persuasivas para cada uma. "
                         "JSON: {\"objecoes\": [...], \"quebras\": [...]}"),
        ("human", "Briefing:\n{briefing}\n\nContexto RAG:\n{contexto}"),
    ]) | llm

    chain_headlines = ChatPromptTemplate.from_messages([
        ("system", BASE + " Crie headlines magnéticas e ângulos de comunicação diferenciados. "
                         "JSON: {\"headlines\": [...], \"angulos\": [...]}"),
        ("human", "Briefing:\n{briefing}\n\nContexto RAG:\n{contexto}"),
    ]) | llm

    # ── Chain de prova social ─────────────────────────────────────────────────

    chain_prova_social = ChatPromptTemplate.from_messages([
        ("system", BASE + (
            " Você é especialista em prova social para lançamentos. "
            "Formate depoimentos, métricas e autoridade do produtor em snippets prontos para uso na copy. "
            "JSON: {\"snippets_depoimentos\": [...], \"snippet_metricas\": \"...\", "
            "\"snippet_autoridade\": \"...\", \"social_proof_headline\": \"...\"}"
        )),
        ("human", (
            "Briefing:\n{briefing}\n\n"
            "Depoimentos:\n{depoimentos}\n\n"
            "Métricas:\n{metricas}\n\n"
            "Autoridade do Produtor:\n{autoridade}"
        )),
    ]) | llm

    # ── Chains especializadas por canal (calibração de tom) ───────────────────

    chain_email = ChatPromptTemplate.from_messages([
        ("system", BASE + (
            " Você é especialista em EMAIL MARKETING para lançamentos. "
            "Escreva um email de vendas completo com: subject line irresistível (urgência + benefício), "
            "abertura que gera identificação imediata, storytelling que conecta dor à solução, "
            "prova social integrada organicamente, quebra das principais objeções, "
            "apresentação da oferta com valor percebido alto, e CTA claro e urgente. "
            "Tom: conversacional mas direto. Extensão: mínimo 400 palavras. "
            "JSON: {\"subject\": \"...\", \"body\": \"...\"}"
        )),
        ("human", _canal_prompt()),
    ]) | llm

    chain_stories = ChatPromptTemplate.from_messages([
        ("system", BASE + (
            " Você é especialista em INSTAGRAM STORIES para lançamentos. "
            "Crie uma sequência de exatamente 8 slides otimizados para Stories (formato vertical 9:16). "
            "Regras: texto curto (máx 3 linhas por slide), linguagem informal com emojis estratégicos, "
            "progressão narrativa (hook → dor → solução → prova → oferta → urgência → CTA → lembrete), "
            "cada slide deve funcionar de forma autônoma mas também como parte da sequência. "
            "JSON: {\"slides\": [{\"numero\": 1, \"visual\": \"descrição do visual sugerido\", \"copy\": \"texto do slide\"}]}"
        )),
        ("human", _canal_prompt()),
    ]) | llm

    chain_ads = ChatPromptTemplate.from_messages([
        ("system", BASE + (
            " Você é especialista em META ADS (Facebook/Instagram) para lançamentos. "
            "Crie 3 variações de anúncio seguindo o framework AIDA, cada uma com ângulo diferente: "
            "variação 1 (ângulo dor), variação 2 (ângulo transformação), variação 3 (ângulo autoridade/prova). "
            "Restrições: headline máx 40 chars, primary_text máx 300 chars (sem truncar a mensagem), "
            "link_description máx 30 chars. "
            "JSON: {\"ads\": [{\"angulo\": \"...\", \"headline\": \"...\", \"primary_text\": \"...\", \"link_description\": \"...\"}]}"
        )),
        ("human", _canal_prompt()),
    ]) | llm

    chain_vsl = ChatPromptTemplate.from_messages([
        ("system", BASE + (
            " Você é especialista em VSL (Video Sales Letter) para lançamentos de infoprodutos. "
            "Escreva o script completo de um VSL de 15 minutos com arco narrativo em blocos obrigatórios: "
            "Hook (0:00-1:30) — promessa ousada que para o scroll, "
            "Identificação da Dor (1:30-3:30) — espelhamento profundo da dor, "
            "Minha História (3:30-6:00) — jornada do produtor gerando autoridade, "
            "A Descoberta (6:00-8:00) — o método como virada de chave, "
            "Prova Social (8:00-10:00) — casos de sucesso específicos, "
            "O Que Você Vai Ter (10:00-12:00) — oferta detalhada com bônus, "
            "Garantia e Objeções (12:00-13:30) — quebra das últimas resistências, "
            "CTA e Urgência (13:30-15:00) — chamada para ação com escassez real. "
            "JSON: {\"script\": [{\"time\": \"0:00-1:30\", \"segment\": \"Hook\", \"copy\": \"...\"}]}"
        )),
        ("human", _canal_prompt()),
    ]) | llm

    # ── Chain do crítico ──────────────────────────────────────────────────────

    chain_critico = ChatPromptTemplate.from_messages([
        ("system", (
            "Você é um DIRETOR CRIATIVO sênior, extremamente exigente, com 20 anos em marketing de resposta direta. "
            "Avalie cada canal (email, stories, ads, vsl) em 3 critérios: "
            "clareza da proposta de valor, força emocional e especificidade (sem generalismos). "
            "Se TODOS os canais estiverem excelentes, responda APENAS a palavra 'APROVADO'. "
            "Caso contrário, responda 'REFINAR:' seguido de pontos numerados e acionáveis por canal."
        )),
        ("human", "Briefing:\n{briefing}\n\nCopy gerada:\n{copy_por_canal}"),
    ]) | llm

    # ── Nós do Grafo ──────────────────────────────────────────────────────────

    def _b(state): return json.dumps(state["briefing"], ensure_ascii=False)
    def _c(state): return state["contexto_rag"]

    def node_dores_promessas(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Dores & Promessas:* mapeando o universo emocional do público...")
        r = chain_dores.invoke({"briefing": _b(state), "contexto": _c(state)})
        return {"dores_promessas": force_json(r)}

    def node_objecoes_quebras(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Objeções & Quebras:* antecipando resistências do comprador...")
        r = chain_objecoes.invoke({"briefing": _b(state), "contexto": _c(state)})
        return {"objecoes_quebras": force_json(r)}

    def node_headlines_angulos(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Headlines & Ângulos:* criando ganchos e ângulos magnéticos...")
        r = chain_headlines.invoke({"briefing": _b(state), "contexto": _c(state)})
        return {"headlines_angulos": force_json(r)}

    def node_consolidador(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Consolidador:* integrando as análises em contexto estratégico...")
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

    def node_prova_social(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Prova Social:* formatando depoimentos e métricas para máxima credibilidade...")
        ps = state["briefing"].get("briefing_lancamento", {}).get("prova_social", {})
        r = chain_prova_social.invoke({
            "briefing":    _b(state),
            "depoimentos": ps.get("depoimentos", "Nenhum depoimento informado."),
            "metricas":    ps.get("metricas", "Nenhuma métrica informada."),
            "autoridade":  ps.get("autoridade_produtor", ""),
        })
        parsed = force_json(r)
        # Serializa como texto para injetar nos prompts dos canais
        if "error" not in parsed:
            snippets = (
                f"DEPOIMENTOS: {', '.join(parsed.get('snippets_depoimentos', []))}\n"
                f"MÉTRICAS: {parsed.get('snippet_metricas', '')}\n"
                f"AUTORIDADE: {parsed.get('snippet_autoridade', '')}\n"
                f"HEADLINE DE PROVA: {parsed.get('social_proof_headline', '')}"
            )
        else:
            snippets = "Sem prova social disponível."
        return {"prova_social": snippets}

    def _canal_input(state: AgentState) -> Dict:
        """Monta o input padrão para os 4 prompts de canal."""
        return {
            "briefing":            _b(state),
            "contexto_enriquecido": state.get("contexto_enriquecido", ""),
            "prova_social":        state.get("prova_social", ""),
            "revisao_critico":     state.get("revisao_critico") or "Primeira versão — sem feedback anterior.",
        }

    def node_adaptacao_canais(state: AgentState) -> Dict[str, Any]:
        tentativa = state.get("tentativas_refinamento", 0) + 1
        st.write(f"🔄 *Adaptação por Canal:* gerando copy especializada para cada canal (tentativa {tentativa})...")

        contexto = state.get("contexto_enriquecido", "{}")
        try:
            if "error" in json.loads(contexto):
                return {"copy_por_canal": {"error": "Contexto inválido."}, "tentativas_refinamento": tentativa}
        except (json.JSONDecodeError, TypeError):
            pass

        inp = _canal_input(state)
        email_raw   = chain_email.invoke(inp)
        stories_raw = chain_stories.invoke(inp)
        ads_raw     = chain_ads.invoke(inp)
        vsl_raw     = chain_vsl.invoke(inp)

        email   = force_json(email_raw)
        stories = force_json(stories_raw)
        ads     = force_json(ads_raw)
        vsl     = force_json(vsl_raw)

        copy = {
            "email":   email,
            "stories": stories.get("slides", stories),
            "ads":     ads.get("ads", [ads] if "headline" in ads else []),
            "vsl":     vsl,
        }
        return {"copy_por_canal": copy, "tentativas_refinamento": tentativa}

    def node_critico_revisor(state: AgentState) -> Dict[str, Any]:
        st.write("🔄 *Crítico Revisor:* auditando qualidade e coerência estratégica...")
        copy = state.get("copy_por_canal", {})
        if "error" in copy:
            return {"revisao_critico": "ERRO_NA_GERACAO"}
        r = chain_critico.invoke({
            "briefing":     _b(state),
            "copy_por_canal": json.dumps(copy, ensure_ascii=False),
        })
        st.info(f"💬 **Crítico:** {r.content}")
        return {"revisao_critico": r.content}

    def decidir_pos_critica(state: AgentState) -> str:
        revisao   = state.get("revisao_critico", "")
        tentativas = state.get("tentativas_refinamento", 0)
        if "ERRO_NA_GERACAO" in revisao or "APROVADO" in revisao or tentativas >= MAX_REFINEMENT:
            return "end"
        return "refinar"

    # ── Montagem do Grafo ─────────────────────────────────────────────────────

    graph = StateGraph(AgentState)
    graph.add_node("analise_dores_promessas",   node_dores_promessas)
    graph.add_node("analise_objecoes_quebras",  node_objecoes_quebras)
    graph.add_node("analise_headlines_angulos", node_headlines_angulos)
    graph.add_node("consolidador",              node_consolidador)
    graph.add_node("analise_prova_social",      node_prova_social)
    graph.add_node("adaptacao_canais",          node_adaptacao_canais)
    graph.add_node("critico_revisor",           node_critico_revisor)

    # 3 análises em paralelo a partir do START
    graph.add_edge(START, "analise_dores_promessas")
    graph.add_edge(START, "analise_objecoes_quebras")
    graph.add_edge(START, "analise_headlines_angulos")

    # Convergência → consolidador → prova social → adaptação → crítico
    graph.add_edge("analise_dores_promessas",   "consolidador")
    graph.add_edge("analise_objecoes_quebras",  "consolidador")
    graph.add_edge("analise_headlines_angulos", "consolidador")
    graph.add_edge("consolidador",              "analise_prova_social")
    graph.add_edge("analise_prova_social",      "adaptacao_canais")
    graph.add_edge("adaptacao_canais",          "critico_revisor")

    graph.add_conditional_edges(
        "critico_revisor",
        decidir_pos_critica,
        {"refinar": "adaptacao_canais", "end": END},
    )

    return graph.compile()


# ── Helper (definido fora para evitar closure circular) ───────────────────────

def _canal_prompt():
    return (
        "Briefing:\n{briefing}\n\n"
        "Contexto Estratégico (dores, objeções, headlines):\n{contexto_enriquecido}\n\n"
        "Prova Social Formatada:\n{prova_social}\n\n"
        "Feedback do Crítico (se refinamento):\n{revisao_critico}"
    )
