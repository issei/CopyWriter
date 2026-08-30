"""
E2E do worker de carrossel: grafo real, checkpointer real, compositor real.
Só o cliente de IA é falso.

A versão anterior deste teste monkeypatchava `build_carousel_graph`, que é
exatamente a linha onde o checkpointer era construído errado — por isso passava
com o worker quebrado em produção. Aqui só a factory de LLM é substituída.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.carousel_jobs import create_job, get_job, init_carousel_jobs_table, run_carousel_job


# ── Dublês de IA ──────────────────────────────────────────────────────────────

class FakeTextModel:
    def __init__(self, score):
        self.score = score

    def generate_structured(self, messages, schema=None):
        prompt = str(messages).lower()
        if "validador" in prompt:
            return {"score": self.score, "issues": [], "critical_failures": []}
        if "editorial de carrosséis" in prompt:
            return {"slides": [
                {"slide_id": i, "papel": "hook", "modo": "light",
                 "texto_slide": f"Texto exato do slide {i}"}
                for i in (1, 2, 3)
            ]}
        if "diretor de arte" in prompt:
            return {"global_style": "clean editorial",
                    "slides": [{"slide_id": i, "image_brief": {"required": True}} for i in (1, 2, 3)]}
        if "prompt designer" in prompt:
            return {"prompts": [{"slide_id": i, "prompt": "editorial", "required": True}
                                for i in (1, 2, 3)]}
        return {"key_messages": ["m"], "emotions": [], "promises": [], "narrative_arc": "x"}


class FakeVisionModel:
    def __init__(self, score):
        self.score = score

    def evaluate_image(self, file_path, rubric):
        assert os.path.exists(file_path), "vision recebeu caminho inexistente"
        return {"score": self.score, "issues": []}


class FakeImageModel:
    def generate(self, prompt, *, width, height, seed=None):
        # PNG 1×1 real: o compositor precisa conseguir abrir o arquivo.
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (width, height), (200, 200, 200)).save(buf, format="PNG")
        return buf.getvalue()


class FakeFactory:
    def __init__(self, score):
        self.score = score

    def text_model(self, *a, **kw):  return FakeTextModel(self.score)
    def vision_model(self, *a, **kw): return FakeVisionModel(self.score)
    def image_model(self, *a, **kw):  return FakeImageModel()


@pytest.fixture
def payload(tmp_path):
    return {
        "copy": "Texto exato do slide 1\n\nTexto exato do slide 2\n\nTexto exato do slide 3",
        "brand": {"name": "Talita", "handle": "@talita", "verified": True},
        "slides": {"min": 3, "max": 10, "preferred": 3},
        "canvas": {"width": 1080, "height": 1350, "format": "PNG", "quality": 95},
        "visual_preferences": {"image_style": "minimalist", "slide_hints": [],
                               "include_photos": True, "allow_copy_rewrite": False},
        "output_dir": str(tmp_path / "outputs"),
    }


def _rodar(tmp_path, monkeypatch, payload, score):
    monkeypatch.setattr("backend.llm.get_llm_factory", lambda: FakeFactory(score))

    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    init_carousel_jobs_table(conn)
    thread_id = create_job(conn)

    run_carousel_job(thread_id, payload, db_path, str(tmp_path / "checkpoints.sqlite"))
    return get_job(conn, thread_id)


def test_job_aprovado_publica_manifest(tmp_path, monkeypatch, payload):
    """Caminho feliz: o job conclui E grava o manifest_path que a UI lê."""
    job = _rodar(tmp_path, monkeypatch, payload, score=85)

    assert job["status"] == "completed", job.get("error_message")
    # Sem manifest_path na linha do job, a UI mostra "manifest não encontrado".
    assert job["manifest_path"], "manifest_path não foi gravado no job"
    assert os.path.exists(job["manifest_path"])

    manifest = json.loads(Path(job["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["total_slides"] == 3
    assert manifest["visual_generation"]["total_slides_with_image_required"] == 3


def test_job_reprovado_pausa_para_revisao_humana(tmp_path, monkeypatch, payload):
    """Score baixo esgota as revisões e para em human_review — nunca 'completed'."""
    job = _rodar(tmp_path, monkeypatch, payload, score=20)

    assert job["status"] == "awaiting_approval", job.get("error_message")
    assert job["progress_summary"]["human_review_reason"]
    assert job["progress_summary"]["carousel_plan"]["slides"]


def test_checkpointer_real_e_aceito_pelo_compile(tmp_path):
    """
    Regressão do bloqueador: `from_conn_string` é um contextmanager e o objeto
    devolvido sem `with` é rejeitado por compile() com TypeError.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver
    from backend.carousel_graph import build_carousel_graph

    with SqliteSaver.from_conn_string(str(tmp_path / "cp.sqlite")) as checkpointer:
        assert build_carousel_graph(checkpointer) is not None
