"""
Testes do fluxo de carrossel.

Cobrem as funções puras — nenhum teste aqui precisa de chave de API ou de um
runtime do Streamlit. O grafo é compilado com o LLM substituído por um duplo.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.parsers import (  # noqa: E402
    bloco_pomelli_completo,
    bloco_pomelli_slide,
    clamp_slides,
    normalizar_carrossel,
)


# ── AC1 · a V1 roda sem os campos novos ───────────────────────────────────────

def test_v1_encerra_sem_os_campos_novos():
    """Estado da V1: sem content_type, sem num_slides, sem visual_suggestions."""
    from backend.graph import decidir_pos_critica
    state = {"revisao_critico": "APROVADO", "tentativas_refinamento": 1}
    assert decidir_pos_critica(state) == "end"


def test_v1_ainda_refina():
    from backend.graph import decidir_pos_critica
    state = {"revisao_critico": "REFINAR: 1. o email está genérico",
             "tentativas_refinamento": 1}
    assert decidir_pos_critica(state) == "refinar"


def test_v1_para_no_limite_de_refinamentos():
    from backend.graph import decidir_pos_critica
    from config import MAX_REFINEMENT
    state = {"revisao_critico": "REFINAR: ainda fraco",
             "tentativas_refinamento": MAX_REFINEMENT}
    assert decidir_pos_critica(state) == "end"


@pytest.mark.parametrize("content_type,esperado", [
    ("carousel", "carrossel"),
    ("padrao",   "end"),
    (None,       "end"),
    ("",         "end"),
])
def test_roteamento_por_content_type(content_type, esperado):
    from backend.graph import decidir_pos_critica
    state = {"revisao_critico": "APROVADO", "tentativas_refinamento": 1}
    if content_type is not None:
        state["content_type"] = content_type
    assert decidir_pos_critica(state) == esperado


def test_erro_de_geracao_nao_dispara_carrossel():
    """Sem os 4 canais válidos não há contexto para o carrossel."""
    from backend.graph import decidir_pos_critica
    state = {"revisao_critico": "ERRO_NA_GERACAO", "tentativas_refinamento": 1,
             "content_type": "carousel"}
    assert decidir_pos_critica(state) == "end"


def test_refinamento_pendente_tem_precedencia_sobre_o_carrossel():
    from backend.graph import decidir_pos_critica
    state = {"revisao_critico": "REFINAR: mais específico",
             "tentativas_refinamento": 0, "content_type": "carousel"}
    assert decidir_pos_critica(state) == "refinar"


# ── AC2 · o grafo compila sem dead ends ───────────────────────────────────────

def test_grafo_compila_com_o_no_de_carrossel():
    # Runnable de verdade: `prompt | llm` exige algo que o LangChain saiba coagir.
    from langchain_core.runnables import RunnableLambda

    def _nunca_chamado(_):
        raise AssertionError("nenhuma chamada ao LLM nos testes")

    with patch("backend.graph.get_llm", return_value=RunnableLambda(_nunca_chamado)):
        from backend.graph import get_compiled_graph
        compilado = get_compiled_graph.__wrapped__()   # ignora @st.cache_resource

    nos = set(compilado.get_graph().nodes)
    assert "geracao_carrossel" in nos
    # os nós da V1 continuam todos presentes
    for no in ("analise_dores_promessas", "analise_objecoes_quebras",
               "analise_headlines_angulos", "consolidador",
               "analise_prova_social", "adaptacao_canais", "critico_revisor"):
        assert no in nos
    # todo destino do roteador existe (o compile já rejeita órfãos; aqui fica em CI)
    for destino in ("adaptacao_canais", "geracao_carrossel"):
        assert destino in nos


# ── AC4 · normalização ────────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    (7, 7), (5, 5), (10, 10),
    (1, 5), (99, 10),           # fora da faixa → clamp
    (None, 7), ("abc", 7),      # inválido → default
    ("8", 8),                   # string numérica
])
def test_clamp_slides(entrada, esperado):
    assert clamp_slides(entrada) == esperado


def _bruto(n=3):
    return {
        "estilo_visual_global": "minimalist background, bold typography",
        "legenda": "Legenda do post",
        "hashtags": ["#dev", "carreira"],
        "slides": [
            {"numero": 99, "papel": "hook", "texto_slide": f"Texto {i}",
             "prompt_visual_pomelli": f"visual {i}"}
            for i in range(1, n + 1)
        ],
    }


def test_trunca_excesso_de_slides():
    out = normalizar_carrossel(_bruto(12), 7)
    assert len(out["slides"]) == 7


def test_nao_inventa_slides_faltantes():
    out = normalizar_carrossel(_bruto(3), 7)
    assert len(out["slides"]) == 3


def test_renumera_os_slides():
    out = normalizar_carrossel(_bruto(4), 7)
    assert [s["numero"] for s in out["slides"]] == [1, 2, 3, 4]


def test_slides_como_dict_viram_lista():
    bruto = {"slides": {"a": {"texto_slide": "um"}, "b": {"texto_slide": "dois"}}}
    out = normalizar_carrossel(bruto, 7)
    assert [s["texto_slide"] for s in out["slides"]] == ["um", "dois"]


def test_slides_embrulhados_em_slide_n():
    bruto = {"slides": [{"slide_1": {"copy": "um", "visual": "azul"}}]}
    out = normalizar_carrossel(bruto, 7)
    assert out["slides"][0]["texto_slide"] == "um"
    assert out["slides"][0]["prompt_visual_pomelli"] == "azul"


@pytest.mark.parametrize("alias", ["texto_slide", "texto", "copy", "text"])
def test_aliases_de_texto(alias):
    out = normalizar_carrossel({"slides": [{alias: "conteúdo"}]}, 7)
    assert out["slides"][0]["texto_slide"] == "conteúdo"


@pytest.mark.parametrize("alias", ["prompt_visual_pomelli", "prompt_visual", "visual"])
def test_aliases_de_visual(alias):
    out = normalizar_carrossel({"slides": [{"texto_slide": "x", alias: "azul"}]}, 7)
    assert out["slides"][0]["prompt_visual_pomelli"] == "azul"


def test_slide_sem_texto_e_descartado():
    bruto = {"slides": [{"texto_slide": "ok"}, {"prompt_visual_pomelli": "só visual"}, "lixo"]}
    out = normalizar_carrossel(bruto, 7)
    assert len(out["slides"]) == 1


def test_hashtags_ganham_cerquilha():
    out = normalizar_carrossel(_bruto(1), 7)
    assert out["hashtags"] == ["#dev", "#carreira"]


def test_hashtags_como_string():
    out = normalizar_carrossel({"slides": [{"texto_slide": "x"}],
                                "hashtags": "#dev, carreira"}, 7)
    assert out["hashtags"] == ["#dev", "#carreira"]


def test_erro_do_force_json_e_preservado():
    bruto = {"error": "Falha ao decodificar JSON", "raw_content": "blá"}
    assert normalizar_carrossel(bruto, 7) == bruto


def test_entrada_nao_dict_vira_erro():
    out = normalizar_carrossel("resposta solta", 7)
    assert "error" in out and "raw_content" in out


def test_campos_ausentes_nao_quebram():
    out = normalizar_carrossel({}, 7)
    assert out == {"estilo_visual_global": "", "legenda": "", "hashtags": [], "slides": []}


# ── AC5 · blocos da ponte com o Pomelli ───────────────────────────────────────

def test_bloco_do_slide_junta_texto_e_visual():
    out = normalizar_carrossel(_bruto(3), 7)
    bloco = bloco_pomelli_slide(out["slides"][1], 3, out["estilo_visual_global"])
    assert "SLIDE 2/3 — hook" in bloco
    assert "Texto 2" in bloco
    # o estilo global precede a variação do slide
    assert "minimalist background, bold typography, visual 2" in bloco


def test_bloco_completo_abre_pelo_estilo_global_e_traz_tudo():
    out = normalizar_carrossel(_bruto(3), 7)
    bloco = bloco_pomelli_completo(out)
    assert bloco.index("ESTILO VISUAL GLOBAL") < bloco.index("SLIDE 1/3")
    for i in (1, 2, 3):
        assert f"SLIDE {i}/3" in bloco and f"Texto {i}" in bloco
    assert "LEGENDA DO POST" in bloco and "#dev #carreira" in bloco


def test_bloco_completo_sem_legenda_nao_emite_secao_vazia():
    out = normalizar_carrossel({"slides": [{"texto_slide": "x"}]}, 7)
    assert "LEGENDA DO POST" not in bloco_pomelli_completo(out)


# ── AC3 · histórico serializa o carrossel sem migração ────────────────────────

def test_historico_serializa_o_carrossel(tmp_path, monkeypatch):
    import backend.historico as hist
    monkeypatch.setattr(hist, "DB_PATH", str(tmp_path / "h.db"))
    hist.init_db()

    carrossel = normalizar_carrossel(_bruto(3), 7)
    copy = {"email": {"subject": "s", "body": "b"}, "stories": [], "ads": [],
            "vsl": {}, "carrossel": carrossel}
    briefing = {"briefing_lancamento": {
        "infoproduto": {"nome": "Mentoria", "produtor": "Maurício"},
        "estrategia_lancamento": {"tipo_lancamento": "VSL"},
    }}

    rid = hist.salvar(briefing, copy, "APROVADO", 1)
    carregado = hist.carregar(rid)

    assert carregado["copy"]["carrossel"] == carrossel
    # acentuação sobrevive (ensure_ascii=False)
    assert carregado["briefing"]["briefing_lancamento"]["infoproduto"]["produtor"] == "Maurício"


def test_copy_sem_carrossel_continua_carregando(tmp_path, monkeypatch):
    """Registros anteriores à mudança não têm a chave — a aba só não aparece."""
    import backend.historico as hist
    monkeypatch.setattr(hist, "DB_PATH", str(tmp_path / "h.db"))
    hist.init_db()

    copy = {"email": {}, "stories": [], "ads": [], "vsl": {}}
    rid = hist.salvar({"briefing_lancamento": {}}, copy, "APROVADO", 0)
    assert hist.carregar(rid)["copy"].get("carrossel") is None
