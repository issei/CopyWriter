"""Persistência de lançamentos em SQLite."""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional

from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS historico (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em        TEXT    NOT NULL,
    nome_produto     TEXT,
    produtor         TEXT,
    tipo_lancamento  TEXT,
    briefing_json    TEXT,
    copy_json        TEXT,
    revisao_critico  TEXT,
    tentativas       INTEGER DEFAULT 0
)
"""


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as c:
        c.execute(_SCHEMA)


def salvar(briefing: Dict, copy: Dict, revisao: str, tentativas: int) -> int:
    """Insere um lançamento no histórico e retorna o id gerado."""
    b = briefing.get("briefing_lancamento", {})
    inf = b.get("infoproduto", {})
    est = b.get("estrategia_lancamento", {})
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO historico
               (criado_em, nome_produto, produtor, tipo_lancamento,
                briefing_json, copy_json, revisao_critico, tentativas)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                inf.get("nome", ""),
                inf.get("produtor", ""),
                est.get("tipo_lancamento", ""),
                json.dumps(briefing, ensure_ascii=False),
                json.dumps(copy, ensure_ascii=False),
                revisao,
                tentativas,
            ),
        )
        return cur.lastrowid


def listar(limit: int = 20) -> List[Dict]:
    """Retorna os lançamentos mais recentes."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, criado_em, nome_produto, produtor, tipo_lancamento, tentativas "
            "FROM historico ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        dict(zip(["id", "criado_em", "nome_produto", "produtor", "tipo_lancamento", "tentativas"], r))
        for r in rows
    ]


def carregar(id: int) -> Optional[Dict]:
    """Carrega um lançamento completo pelo id."""
    with _conn() as c:
        row = c.execute(
            "SELECT briefing_json, copy_json, revisao_critico FROM historico WHERE id=?", (id,)
        ).fetchone()
    if not row:
        return None
    return {
        "briefing": json.loads(row[0]),
        "copy":     json.loads(row[1]),
        "revisao":  row[2],
    }


def deletar(id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM historico WHERE id=?", (id,))
