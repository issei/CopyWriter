"""
typography.py — Escala tipográfica derivada para o canvas 1080×1350.

Fator de escala: 920 / 720 = 1,278 (canvas CONTENT_W / referência desktop)
Todos os tamanhos arredondados ao múltiplo de 8 mais próximo.

D6: DM Serif Display não tem Bold. Onde a identidade pede Bold 700,
usamos DM Serif Display Regular — é uma display de alto contraste que
lê como peso forte em tamanho grande. Bold sintético PROIBIDO.

Fontes: carregadas de assets/fonts/ — nunca de fallback de sistema.
Se um TTF não carregar, é ERRO DURO, não fallback silencioso.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont


# ── Caminhos base ─────────────────────────────────────────────────────────────

# Calculado em runtime para ser robusto independente do diretório de trabalho.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FONTS_DIR = _REPO_ROOT / "assets" / "fonts"

_FONT_FILES = {
    "dm_regular": _FONTS_DIR / "DM_Serif_Display" / "DMSerifDisplay-Regular.ttf",
    "dm_italic":  _FONTS_DIR / "DM_Serif_Display" / "DMSerifDisplay-Italic.ttf",
    "inter_regular":  _FONTS_DIR / "Inter" / "static" / "Inter_18pt-Regular.ttf",
    "inter_semibold": _FONTS_DIR / "Inter" / "static" / "Inter_18pt-SemiBold.ttf",
}


# ── Tamanhos canvas (grid de 8px, fator 1,278) ────────────────────────────────
# Tabela da spec §5.2 — valores EXATOS, não estimativas.

SIZE = {
    "author_name":      40,   # DM Serif Display Regular  — ref 32 × 1,278 → 40
    "author_handle":    24,   # Inter Regular 400          — ref 16 × 1,278 → 24 (arred. 8)
    "title":            80,   # DM Serif Display Regular   — ref 60 × 1,278 → 80 (arred. 8)
    "diagnosis":        40,   # DM Serif Display Regular   — ref 32 × 1,278 → 40
    "checklist_pain":   32,   # DM Serif Display Regular   — ref 24 × 1,278 → 32 (arred. 8)
    "checklist_method": 32,   # DM Serif Display Italic    — ref 24 × 1,278 → 32 (arred. 8)
    "notes_header":     24,   # Inter SemiBold 600         — ref 18 × 1,278 → 24 (arred. 8)
}

# Entrelinha: 1,15 para títulos, 1,40 para corpo
LEADING = {
    "title":   1.15,
    "default": 1.40,
}

# Espaçamentos entre seções (spec §5.2)
GAP_SECTION   = 120   # múltiplo de 8, dentro da faixa 96–152
GAP_TITLE_PAR = 56    # múltiplo de 8, dentro da faixa 48–72


# ── Carregamento de fonte (cache por (key, size)) ─────────────────────────────

@lru_cache(maxsize=64)
def get_font(key: str, size: int | None = None) -> ImageFont.FreeTypeFont:
    """
    Retorna uma fonte carregada do TTF local.

    key: um dos identificadores em _FONT_FILES
    size: tamanho em pixels — usa SIZE[key] se omitido.

    Lança FileNotFoundError se o TTF não existir e
    IOError/OSError se o arquivo estiver corrompido.
    NUNCA usa fallback de sistema — erro duro intencional.
    """
    path = _FONT_FILES.get(key)
    if path is None:
        raise ValueError(f"Chave de fonte desconhecida: {key!r}")
    if not path.exists():
        raise FileNotFoundError(
            f"TTF não encontrado: {path}\n"
            "Execute 'git mv docs/DM_Serif_Display assets/fonts/DM_Serif_Display' "
            "e equivalente para Inter."
        )
    pt = size if size is not None else SIZE.get(key, 32)
    return ImageFont.truetype(str(path), pt)


def font_for_element(element: str) -> ImageFont.FreeTypeFont:
    """
    Retorna a fonte correta para um elemento da hierarquia tipográfica.

    Elementos suportados: 'author_name', 'author_handle', 'title',
    'diagnosis', 'checklist_pain', 'checklist_method', 'notes_header'.
    """
    _MAP = {
        "author_name":      ("dm_regular",      SIZE["author_name"]),
        "author_handle":    ("inter_regular",   SIZE["author_handle"]),
        "title":            ("dm_regular",      SIZE["title"]),
        "diagnosis":        ("dm_regular",      SIZE["diagnosis"]),       # D6: Regular, não Bold
        "checklist_pain":   ("dm_regular",      SIZE["checklist_pain"]),
        "checklist_method": ("dm_italic",       SIZE["checklist_method"]),
        "notes_header":     ("inter_semibold",  SIZE["notes_header"]),
    }
    if element not in _MAP:
        raise ValueError(f"Elemento tipográfico desconhecido: {element!r}")
    key, size = _MAP[element]
    return get_font(key, size)


def measure_text_height(text: str, font: ImageFont.FreeTypeFont,
                        max_width: int, leading: float = 1.40) -> int:
    """
    Calcula a altura total de um bloco de texto com quebra de linha.
    Usa 'getbbox' para medição exata — sem aproximações.
    """
    lines = wrap_text(text, font, max_width)
    if not lines:
        return 0
    _, top, _, bottom = font.getbbox("Ag")
    line_h = (bottom - top) * leading
    return int(len(lines) * line_h)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Quebra texto em linhas que caibam dentro de max_width.
    Preserva quebras de linha explícitas (\n).
    """
    result = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            result.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = font.getbbox(candidate)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current = candidate
            else:
                result.append(current)
                current = word
        result.append(current)
    return result
