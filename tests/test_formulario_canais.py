"""
Testes da Fase 1 — briefing opcional e canais seletivos.

Nenhum teste aqui precisa de chave de API. O grafo é compilado com o LLM
substituído por um duplo.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.parsers import canonicalize_briefing, podar          # noqa: E402
from data.prompts import CANAIS, CANAIS_PADRAO, GATILHOS_MENTAIS  # noqa: E402


# ── Poda de campos vazios ─────────────────────────────────────────────────────

def test_podar_remove_vazios():
    assert podar({"a": "", "b": "x", "c": {"d": None}, "e": [None, "y"]}) == {"b": "x", "e": ["y"]}


@pytest.mark.parametrize("valor", [0, 0.0, False])
def test_podar_preserva_falsy_significativo(valor):
    assert podar({"preco": valor}) == {"preco": valor}


def test_podar_remove_dict_que_ficou_vazio():
    assert podar({"prova_social": {"depoimentos": "", "metricas": None}}) == {}


def test_canonicalize_omite_linha_vazia():
    b = {"briefing_lancamento": {"publico_alvo": {"problema_principal": "Estagnado."}}}
    t = canonicalize_briefing(b)
    assert t == "# Briefing de Lançamento\nDor principal: Estagnado."
    assert "None" not in t
    assert not any(l.endswith(": ") for l in t.split("\n"))


def test_canonicalize_nao_emite_preco_ausente():
    b = {"briefing_lancamento": {"infoproduto": {"nome": "X", "preco": None}}}
    assert "Preço" not in canonicalize_briefing(b)


# ── Registro de canais ────────────────────────────────────────────────────────

def test_registro_integro():
    assert len(CANAIS) == 5
    rotulos = [c["rotulo"] for c in CANAIS.values()]
    assert len(set(rotulos)) == len(rotulos), "rótulos duplicados"
    for nome, cfg in CANAIS.items():
        assert cfg["raiz"] is None or isinstance(cfg["raiz"], str), nome
        assert isinstance(cfg["no_dedicado"], bool), nome


def test_carrossel_fora_do_laco_padrao():
    assert "carrossel" not in CANAIS_PADRAO
    assert CANAIS_PADRAO == ["email", "stories", "ads", "vsl"]


def test_gatilhos_sem_duplicata():
    assert len(GATILHOS_MENTAIS) == 32
    assert len(set(GATILHOS_MENTAIS)) == 32


# ── Prova social condicional ──────────────────────────────────────────────────

def _estado(ps):
    return {"briefing": {"briefing_lancamento": {"prova_social": ps}}}


@pytest.mark.parametrize("ps,esperado", [
    ({}, "sem_prova"),
    ({"autoridade_produtor": "", "depoimentos": "", "metricas": ""}, "sem_prova"),
    ({"autoridade_produtor": "ex-CTO"}, "com_prova"),
    ({"metricas": "500 devs"}, "com_prova"),
])
def test_pula_prova_social_sem_dado(ps, esperado):
    from backend.graph import tem_prova_social
    assert tem_prova_social(_estado(ps)) == esperado


def test_prova_social_sem_briefing_nao_quebra():
    from backend.graph import tem_prova_social
    assert tem_prova_social({}) == "sem_prova"


# ── Seleção de canais no grafo ────────────────────────────────────────────────

def _grafo_com_llm_falso():
    import json as _json
    from langchain_core.runnables import RunnableLambda

    resposta = _json.dumps({
        "veredito": "APROVADO",
        "dores": ["d"], "objecoes": ["o"], "headlines": ["h"],
        "snippets_depoimentos": [], "snippet_metricas": "", "snippet_autoridade": "",
        "subject": "s", "body": "b",
        "slides": [{"numero": 1, "visual": "v", "copy": "c",
                    "texto_slide": "t", "prompt_visual_pomelli": "p"}],
        "ads": [{"angulo": "a", "headline": "h", "primary_text": "p", "link_description": "l"}],
        "script": [{"time": "0:00", "segment": "Hook", "copy": "c"}],
        "estilo_visual_global": "minimal", "legenda": "L", "hashtags": ["#x"],
    }, ensure_ascii=False)

    class Msg:
        content = resposta

    with patch("backend.graph.get_llm", return_value=RunnableLambda(lambda _: Msg())), \
         patch("time.sleep", lambda *_: None):
        from backend.graph import get_compiled_graph
        return get_compiled_graph.__wrapped__()


def _rodar(canais):
    g = _grafo_com_llm_falso()
    estado = {"briefing": {"briefing_lancamento": {}}, "contexto_rag": "",
              "tentativas_refinamento": 0}
    if canais is not None:
        estado["canais"] = canais
    with patch("time.sleep", lambda *_: None):
        final = {}
        for ev in g.stream(estado):
            for payload in ev.values():
                if isinstance(payload, dict):
                    final.update(payload)
    return final.get("copy_por_canal", {})


def test_selecao_parcial_gera_so_o_pedido():
    assert set(_rodar(["email"])) == {"email"}


def test_selecao_ausente_gera_os_quatro_padrao():
    """Compatibilidade com histórico anterior à multiseleção."""
    assert set(_rodar(None)) == {"email", "stories", "ads", "vsl"}


def test_carrossel_nao_entra_no_laco_de_adaptacao():
    copy = _rodar(["email", "carrossel"])
    assert "email" in copy
    assert "carrossel" not in copy, "o carrossel tem nó dedicado, fora do laço"
