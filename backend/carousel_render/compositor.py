"""
compositor.py — Layout determinístico de slides do carrossel.

Regras fundamentais (spec §5.4):
- Alinhamento à esquerda como padrão ouro.
- Grid de 8 px.
- Quebra de linha, medição e paginação determinísticas.
- Recebe exact_copy e o desenha LITERALMENTE — nenhuma reescrita nesta camada.
- asset_path=None → composição puramente tipográfica (fundo + tipografia +
  componentes geométricos). É o caminho NORMAL de degradação, não um erro.
- Texto exato NUNCA é renderizado pela API de imagem (regra 4 da spec §3).

Tipos de slide suportados (via slide_data['modo']):
  'light'  — Fachada Editorial (fundo claro: diagnóstico, autoridade, dor)
  'dark'   — Bastidores (fundo escuro: método, execução, etapas)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw

from backend.carousel_render.tokens import (
    CANVAS, MARGEM, CONTENT_W, CORES, rgb, hex_to_rgb,
)
from backend.carousel_render.typography import (
    font_for_element, wrap_text, LEADING, GAP_SECTION, GAP_TITLE_PAR, SIZE,
)
from backend.carousel_render.components import (
    author_header, editorial_divider, notes_header,
    checklist_pain, checklist_method, ios_highlight,
)


# ── Constantes de layout ──────────────────────────────────────────────────────

W = CANVAS["width"]
H = CANVAS["height"]
SAFE_AREA_BOTTOM = MARGEM   # espaço mínimo acima do rodapé


# ── compose_slide (função pública principal) ──────────────────────────────────

def compose_slide(slide_data: dict[str, Any], asset_path: Optional[str] = None) -> Image.Image:
    """
    Compõe um slide completo como PIL.Image (RGBA, 1080×1350).

    slide_data deve conter:
      - 'texto_slide': str — copy exata pt-BR
      - 'papel': str — 'hook' | 'dor' | 'virada' | 'método' | 'prova' | 'oferta' | 'cta'
      - 'modo': str opcional — 'light' (padrão) | 'dark'
      - 'numero': int opcional — número do slide
      - 'total_slides': int opcional — total para referência
      - 'brand': dict opcional — {name, handle, avatar_path, verified}
      - 'checkitems': list[str] opcional — itens de checklist

    asset_path=None → composição tipográfica pura (fundo + texto + componentes).
    """
    modo = slide_data.get("modo", _infer_mode(slide_data.get("papel", "")))
    canvas = _make_canvas(modo, asset_path)
    draw   = ImageDraw.Draw(canvas)

    y = MARGEM   # cursor vertical

    # ── Topo Notes (só modo escuro) ───────────────────────────────────────────
    if modo == "dark":
        font_notes = font_for_element("notes_header")
        y = notes_header(draw, MARGEM, y, CONTENT_W, font=font_notes)
        y += 16   # respiro

    # ── Cabeçalho de autoria ──────────────────────────────────────────────────
    brand = slide_data.get("brand")
    if brand:
        av_path = brand.get("avatar_path")
        av_img  = None
        if av_path and os.path.exists(av_path):
            av_img = Image.open(av_path).convert("RGBA")

        fn_name   = font_for_element("author_name")
        fn_handle = font_for_element("author_handle")

        y = author_header(
            draw, canvas, MARGEM, y,
            name    = brand.get("name", ""),
            handle  = brand.get("handle", ""),
            avatar_img = av_img,
            verified   = brand.get("verified", True),
            font_name   = fn_name,
            font_handle = fn_handle,
        )
        y += 8

    # ── Divisor editorial (modo claro, após cabeçalho) ────────────────────────
    if modo == "light" and brand:
        ink = hex_to_rgb(CORES["text_ink_primary"])
        y = editorial_divider(draw, MARGEM, y, color=ink) + 24

    # ── Texto principal ────────────────────────────────────────────────────────
    texto = slide_data.get("texto_slide", "").strip()
    papel = slide_data.get("papel", "")

    if texto:
        y = _draw_text_block(draw, canvas, texto, papel, modo, y)

    # ── Checklists ────────────────────────────────────────────────────────────
    items = slide_data.get("checkitems", [])
    if items:
        y += GAP_TITLE_PAR // 2
        for item in items:
            if modo == "dark":
                font_m = font_for_element("checklist_method")
                y = checklist_method(draw, MARGEM, y, item, font=font_m) + 4
            else:
                font_p = font_for_element("checklist_pain")
                y = checklist_pain(draw, MARGEM, y, item, font=font_p) + 4

    return canvas


# ── Funções internas ──────────────────────────────────────────────────────────

def _infer_mode(papel: str) -> str:
    """
    Infere o modo (light/dark) a partir do papel narrativo.
    Fachada Editorial (claro): hook, dor, prova, oferta, cta.
    Bastidores (escuro): virada, método, etapas.
    """
    dark_papers = {"virada", "método", "metodo", "etapa", "etapas"}
    return "dark" if papel.lower() in dark_papers else "light"


def _make_canvas(modo: str, asset_path: Optional[str]) -> Image.Image:
    """
    Cria o canvas base:
    - Se asset_path é fornecido: usa a imagem como fundo (recortada centralmente).
    - Se asset_path é None: fundo de cor sólida conforme modo.
    """
    bg_color_key = "bg_dark_notepad" if modo == "dark" else "bg_warm_paper"
    canvas = Image.new("RGBA", (W, H), hex_to_rgb(CORES[bg_color_key]) + (255,))

    if asset_path and os.path.exists(asset_path):
        try:
            img = Image.open(asset_path).convert("RGBA")
            # Recorte central para 1080×1350
            img_w, img_h = img.size
            scale = max(W / img_w, H / img_h)
            new_w, new_h = int(img_w * scale), int(img_h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            # Recorte central
            left = (new_w - W) // 2
            top  = (new_h - H) // 2
            img = img.crop((left, top, left + W, top + H))
            # Overlay semi-transparente para garantir legibilidade do texto
            overlay_alpha = 160 if modo == "dark" else 120
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, overlay_alpha))
            canvas = Image.alpha_composite(img, overlay)
        except Exception:
            # Degradação silenciosa para cor sólida — a regra 6 diz que falha de
            # imagem nunca interrompe; aqui a imagem já estava em disco mas corrompida.
            pass

    return canvas


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    canvas: Image.Image,
    text: str,
    papel: str,
    modo: str,
    y: int,
) -> int:
    """
    Desenha o bloco de texto principal do slide.
    Escolhe a fonte e a cor conforme o modo e o papel.
    """
    # Seleção de fonte por papel
    is_title_role = papel.lower() in {"hook", "oferta", "cta"}
    font_key = "title" if is_title_role else "diagnosis"
    font = font_for_element(font_key)

    # Cor do texto
    color_key = "text_dark_primary" if modo == "dark" else "text_ink_primary"
    color = hex_to_rgb(CORES[color_key])

    # Entrelinha conforme tipo
    leading_key = "title" if is_title_role else "default"
    leading = LEADING[leading_key]

    # Quebra de linha determinística
    lines = wrap_text(text, font, CONTENT_W)

    _, top_b, _, bottom_b = font.getbbox("Ag")
    line_h = (bottom_b - top_b) * leading

    for line in lines:
        draw.text((MARGEM, y), line, fill=color, font=font)
        y += int(line_h)

    return y + GAP_TITLE_PAR // 2


# ── save_slide ────────────────────────────────────────────────────────────────

def save_slide(image: Image.Image, path: str) -> None:
    """
    Salva um slide em disco no formato PNG, qualidade máxima.
    Cria diretórios intermediários se necessário.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(str(out), format="PNG", optimize=False)
