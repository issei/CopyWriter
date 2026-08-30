"""
carousel_jobs.py — Persistência de thread_id e status dos jobs de carrossel.

Tabela carousel_jobs no SQLite existente do projeto (DB_PATH da config),
reutilizando o mesmo banco — sem introduzir um novo motor (spec v2 §5.3).

Nenhuma dependência do Streamlit aqui.
check_same_thread=False é obrigatório: a conexão é criada no thread da UI
e usada no worker de fundo (D9 da SPEC).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional


# ── DDL ───────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS carousel_jobs (
    thread_id        TEXT PRIMARY KEY,
    status           TEXT NOT NULL DEFAULT 'queued',
    current_node     TEXT,
    progress_summary TEXT DEFAULT '{}',
    manifest_path    TEXT,
    created_at       DATETIME NOT NULL,
    updated_at       DATETIME NOT NULL,
    error_message    TEXT
);
"""


def init_carousel_jobs_table(conn: sqlite3.Connection) -> None:
    """Cria a tabela carousel_jobs se ainda não existir."""
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_job(conn: sqlite3.Connection) -> str:
    """
    Cria um novo job com status 'queued' e retorna o thread_id (UUID).
    """
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO carousel_jobs
           (thread_id, status, current_node, progress_summary, created_at, updated_at)
           VALUES (?, 'queued', NULL, '{}', ?, ?)""",
        (thread_id, now, now),
    )
    conn.commit()
    return thread_id


def update_job(conn: sqlite3.Connection, thread_id: str, **fields) -> None:
    """
    Atualiza campos do job. Campos suportados:
      status, current_node, progress_summary (dict ou str), manifest_path, error_message.
    updated_at é sempre atualizado automaticamente.
    """
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Serializa progress_summary se for dict
    if "progress_summary" in fields and not isinstance(fields["progress_summary"], str):
        fields["progress_summary"] = json.dumps(fields["progress_summary"], ensure_ascii=False)

    if not fields:
        return

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE carousel_jobs SET {set_clause} WHERE thread_id = ?",
        (*fields.values(), thread_id),
    )
    conn.commit()


def get_job(conn: sqlite3.Connection, thread_id: str) -> Optional[dict]:
    """
    Retorna o job como dict, ou None se não encontrado.
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM carousel_jobs WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    # Desserializa progress_summary
    if isinstance(d.get("progress_summary"), str):
        try:
            d["progress_summary"] = json.loads(d["progress_summary"])
        except (json.JSONDecodeError, TypeError):
            d["progress_summary"] = {}
    return d


def list_jobs(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """
    Lista os jobs mais recentes (para a tela de histórico).
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM carousel_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if isinstance(d.get("progress_summary"), str):
            try:
                d["progress_summary"] = json.loads(d["progress_summary"])
            except (json.JSONDecodeError, TypeError):
                d["progress_summary"] = {}
        result.append(d)
    return result


# ── Mapeamento de nó → rótulo amigável ────────────────────────────────────────

NODE_LABELS = {
    "ingest_copy":            "Carregando copy",
    "analyze_copy":           "Analisando copy",
    "plan_carousel":          "Planejando estrutura",
    "art_director":           "Definindo direção de arte",
    "prompt_designer":        "Criando prompts visuais",
    "generate_visual_assets": "Gerando elementos visuais",
    "compose_slides":         "Compondo slides",
    "content_validator":      "Validando conteúdo",
    "visual_validator":       "Validando qualidade visual",
    "quality_gate":           "Avaliando qualidade final",
    "export_package":         "Exportando pacote",
}


def friendly_node_label(node: Optional[str]) -> str:
    """Retorna rótulo amigável para o nó atual."""
    if not node:
        return "Aguardando início"
    return NODE_LABELS.get(node, node)


# ── Worker de fundo ───────────────────────────────────────────────────────────

def run_carousel_job(thread_id: str, payload: dict, db_path: str, checkpoint_path: str) -> None:
    """
    Executa o grafo de carrossel e reflete o resultado na tabela carousel_jobs.

    NUNCA chama st.* — violaria o ScriptRunContext (D9 da SPEC).

    Vive aqui, e não em app.py, porque app.py é um script do Streamlit: o que
    mora lá só é exercitável por teste com a UI inteira mockada, e foi por isso
    que a construção errada do checkpointer passou despercebida.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver
    from backend.carousel_graph import build_carousel_graph

    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        update_job(conn, thread_id, status="running")

        # from_conn_string é um @contextmanager: sem o `with`, o que volta é um
        # _GeneratorContextManager e compile() rejeita com TypeError.
        with SqliteSaver.from_conn_string(checkpoint_path) as checkpointer:
            graph = build_carousel_graph(checkpointer)

            estado: dict = {}
            for evento in graph.stream(payload, config={"configurable": {"thread_id": thread_id}}):
                for no, update in evento.items():
                    update_job(conn, thread_id, current_node=no)
                    if isinstance(update, dict):
                        estado.update(update)

        # O grafo chega a END por dois caminhos: export_package (pronto) e
        # human_review (pausado). Só o primeiro é conclusão.
        if estado.get("quality_decision") == "human_review":
            update_job(
                conn, thread_id,
                status="awaiting_approval",
                progress_summary={
                    "human_review_reason": estado.get("human_review_reason") or "",
                    "quality_score": estado.get("quality_score"),
                    "carousel_plan": estado.get("carousel_plan") or {},
                    "output_dir": estado.get("output_dir") or payload.get("output_dir", ""),
                },
            )
        else:
            update_job(
                conn, thread_id,
                status="completed",
                manifest_path=estado.get("manifest_path"),
                progress_summary={"quality_score": estado.get("quality_score")},
            )

    except Exception as exc:
        update_job(conn, thread_id, status="failed", error_message=str(exc)[:500])
    finally:
        conn.close()
