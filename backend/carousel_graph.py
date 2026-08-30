"""
carousel_graph.py — Grafo de 11 nós do pipeline de carrossel.

ISOLAMENTO OBRIGATÓRIO (spec §3 regra 1):
- Este módulo NÃO importa backend.graph, e vice-versa.
- Os dois grafos são compilados de forma completamente independente.
- Nenhum campo de estado é compartilhado por referência.

Topologia (spec v2 §2.1):
  ingest_copy → analyze_copy → plan_carousel → art_director → prompt_designer
  → generate_visual_assets → compose_slides
  → [content_validator, visual_validator] (em paralelo) → quality_gate
  → {approved: export_package, revise_plan: plan_carousel,
     revise_compose: compose_slides, revise_art: art_director,
     regenerate_asset: generate_visual_assets, human_review: END}
  export_package → END

Execução assíncrona: o grafo é construído pelo worker de fundo
(_run_carousel_graph_background em app.py) e NUNCA chama st.* (D9 da SPEC).
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from backend.carousel_state import CarouselState
from backend.carousel_nodes import (
    make_ingest_copy_node,
    make_analyze_copy_node,
    make_plan_carousel_node,
    make_art_director_node,
    make_prompt_designer_node,
    make_generate_visual_assets_node,
    make_compose_slides_node,
    make_content_validator_node,
    make_visual_validator_node,
    make_quality_gate_node,
    make_export_package_node,
)


def route_quality_gate(state: CarouselState) -> str:
    """
    Função pura de roteamento — sem closure do LLM, testável isoladamente.
    Lê o campo quality_decision já calculado pelo nó quality_gate.
    """
    decision = state.get("quality_decision", "human_review")
    valid_decisions = {
        "approved",
        "revise_plan",
        "revise_compose",
        "revise_art",
        "regenerate_asset",
        "human_review",
    }
    if decision not in valid_decisions:
        return "human_review"
    return decision


def build_carousel_graph(checkpointer=None):
    """
    Constrói e compila o grafo de carrossel.

    checkpointer: SqliteSaver ou InMemorySaver (para testes).
    Se None, compila sem checkpointer (modo simplificado para testes unitários).

    Retorna o grafo compilado.
    """
    # Instancia os nós via fábrica — injeção de dependência real
    factory = None   # get_llm_factory() em produção; FakeLLMFactory em testes
    # Os make_*_node chamam get_llm_factory() internamente se factory=None

    nodes = {
        "ingest_copy":             make_ingest_copy_node(),
        "analyze_copy":            make_analyze_copy_node(factory),
        "plan_carousel":           make_plan_carousel_node(factory),
        "art_director":            make_art_director_node(factory),
        "prompt_designer":         make_prompt_designer_node(factory),
        "generate_visual_assets":  make_generate_visual_assets_node(factory),
        "compose_slides":          make_compose_slides_node(),
        "content_validator":       make_content_validator_node(factory),
        "visual_validator":        make_visual_validator_node(factory),
        "quality_gate":            make_quality_gate_node(factory),
        "export_package":          make_export_package_node(),
    }

    graph = StateGraph(CarouselState)

    # Registrar todos os nós
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # Arestas lineares principais
    graph.add_edge(START,                    "ingest_copy")
    graph.add_edge("ingest_copy",            "analyze_copy")
    graph.add_edge("analyze_copy",           "plan_carousel")
    graph.add_edge("plan_carousel",          "art_director")
    graph.add_edge("art_director",           "prompt_designer")
    graph.add_edge("prompt_designer",        "generate_visual_assets")
    graph.add_edge("generate_visual_assets", "compose_slides")

    # Composição → validação paralela → quality gate
    graph.add_edge("compose_slides",         "content_validator")
    graph.add_edge("compose_slides",         "visual_validator")
    graph.add_edge(["content_validator", "visual_validator"], "quality_gate")

    # Roteamento condicional do quality gate
    graph.add_conditional_edges(
        "quality_gate",
        route_quality_gate,
        {
            "approved":           "export_package",
            "revise_plan":        "plan_carousel",
            "revise_compose":     "compose_slides",
            "revise_art":         "art_director",
            "regenerate_asset":   "generate_visual_assets",
            "human_review":       END,   # retomado via checkpoint (spec v2 §5.2)
        },
    )
    graph.add_edge("export_package", END)

    # Compilar com ou sem checkpointer
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def build_carousel_graph_with_mock_factory(mock_factory):
    """
    Versão de teste: aceita uma FakeLLMFactory injetada externamente.
    Usada em pytest sem precisar de chave de API real.
    """
    nodes = {
        "ingest_copy":             make_ingest_copy_node(),
        "analyze_copy":            make_analyze_copy_node(mock_factory),
        "plan_carousel":           make_plan_carousel_node(mock_factory),
        "art_director":            make_art_director_node(mock_factory),
        "prompt_designer":         make_prompt_designer_node(mock_factory),
        "generate_visual_assets":  make_generate_visual_assets_node(mock_factory),
        "compose_slides":          make_compose_slides_node(),
        "content_validator":       make_content_validator_node(mock_factory),
        "visual_validator":        make_visual_validator_node(mock_factory),
        "quality_gate":            make_quality_gate_node(mock_factory),
        "export_package":          make_export_package_node(),
    }

    graph = StateGraph(CarouselState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.add_edge(START,                    "ingest_copy")
    graph.add_edge("ingest_copy",            "analyze_copy")
    graph.add_edge("analyze_copy",           "plan_carousel")
    graph.add_edge("plan_carousel",          "art_director")
    graph.add_edge("art_director",           "prompt_designer")
    graph.add_edge("prompt_designer",        "generate_visual_assets")
    graph.add_edge("generate_visual_assets", "compose_slides")
    graph.add_edge("compose_slides",         "content_validator")
    graph.add_edge("compose_slides",         "visual_validator")
    graph.add_edge(["content_validator", "visual_validator"], "quality_gate")

    graph.add_conditional_edges(
        "quality_gate",
        route_quality_gate,
        {
            "approved":           "export_package",
            "revise_plan":        "plan_carousel",
            "revise_compose":     "compose_slides",
            "revise_art":         "art_director",
            "regenerate_asset":   "generate_visual_assets",
            "human_review":       END,
        },
    )
    graph.add_edge("export_package", END)

    return graph.compile()
