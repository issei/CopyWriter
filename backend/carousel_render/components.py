"""
components.py — Elementos de assinatura do carrossel (Pillow).

Cada função é testável isoladamente por dimensão e cor.
Nenhuma função aqui chama LLM ou API externa.

Referências: spec §5.3, identidade visual §4.
"""
from __future__ import annotations

import math
from typing import Optional

from PIL import Image, ImageDraw

from backend.carousel_render.tokens import CORES, MARGEM, CONTENT_W, hex_to_rgb, hex_to_rgba, rgb


# ── author_header ─────────────────────────────────────────────────────────────

def author_header(
    draw: ImageDraw.ImageDraw,
    image: Image.Image,
    x: int,
    y: int,
    name: str,
    handle: str,
    avatar_img: Optional[Image.Image] = None,
    verified: bool = True,
    *,
    font_name=None,
    font_handle=None,
) -> int:
    """
    Desenha o cabeçalho de autoria: avatar circular + nome + selo + @handle.

    Retorna a nova posição Y após o componente.
    Avatar: 64–80 px circular (spec §5.3: 48–64 × 1,278 → 64–80)
    """
    AVATAR_SIZE = 72   # múltiplo de 8, dentro de 64–80
    BADGE_SIZE  = 20   # roseta do selo verificado

    # Avatar circular
    avatar_x = x
    avatar_y = y

    if avatar_img is not None:
        # Recorte circular
        av = avatar_img.convert("RGBA").resize((AVATAR_SIZE, AVATAR_SIZE))
        mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1], fill=255)
        image.paste(av, (avatar_x, avatar_y), mask)
    else:
        # Placeholder circular cinza
        draw.ellipse(
            [avatar_x, avatar_y, avatar_x + AVATAR_SIZE, avatar_y + AVATAR_SIZE],
            fill=rgb("text_ink_muted"),
        )

    # Nome da autora
    text_x = avatar_x + AVATAR_SIZE + 16   # 16 px de espaço
    name_y = avatar_y + 8

    if font_name:
        draw.text((text_x, name_y), name, fill=rgb("text_ink_primary"), font=font_name)
        try:
            _, top, _, bottom = font_name.getbbox("Ag")
            name_h = bottom - top
        except Exception:
            name_h = 40
    else:
        draw.text((text_x, name_y), name, fill=rgb("text_ink_primary"))
        name_h = 40

    # Selo de verificação (imediatamente após o nome)
    if verified:
        name_w = 0
        if font_name:
            try:
                bbox = font_name.getbbox(name)
                name_w = bbox[2] - bbox[0]
            except Exception:
                name_w = len(name) * 22
        badge_x = text_x + name_w + 8
        badge_y = name_y + (name_h - BADGE_SIZE) // 2
        verified_badge(draw, badge_x, badge_y, BADGE_SIZE)

    # @handle
    handle_y = name_y + name_h + 4
    handle_text = handle if handle.startswith("@") else f"@{handle}"
    if font_handle:
        draw.text((text_x, handle_y), handle_text, fill=rgb("text_ink_muted"), font=font_handle)
        try:
            _, top, _, bottom = font_handle.getbbox("Ag")
            handle_h = bottom - top
        except Exception:
            handle_h = 24
    else:
        draw.text((text_x, handle_y), handle_text, fill=rgb("text_ink_muted"))
        handle_h = 24

    return avatar_y + AVATAR_SIZE + 24   # espaço após o cabeçalho


# ── verified_badge ────────────────────────────────────────────────────────────

def verified_badge(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 20) -> None:
    """
    Roseta em verified_cyan com check branco no centro.
    Desenhada como polígono de 8 pontas.
    """
    cx = x + size // 2
    cy = y + size // 2
    r_outer = size // 2
    r_inner = int(r_outer * 0.65)
    points = []
    n_points = 8
    for i in range(n_points * 2):
        angle = math.pi / n_points * i - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    draw.polygon(points, fill=rgb("verified_cyan"))

    # Check branco simples (✓ estilizado com linhas)
    check_margin = size // 4
    cx1, cy1 = x + check_margin, y + size // 2
    cx2, cy2 = x + size // 2 - 1, y + size - check_margin
    cx3, cy3 = x + size - check_margin, y + check_margin
    draw.line([cx1, cy1, cx2, cy2, cx3, cy3], fill=(255, 255, 255), width=2)


# ── ios_highlight ─────────────────────────────────────────────────────────────

def ios_highlight(
    image: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    """
    Caixa em highlight_caramel a 60% de opacidade + dois pinos em highlight_pin.
    Simula a seleção nativa de texto do iPhone (iOS grifo).
    """
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)

    # Fundo caramelo 60%
    fill = hex_to_rgba(CORES["highlight_caramel"], HIGHLIGHT_OPACITY := 0.60)
    ov_draw.rectangle([x, y, x + width, y + height], fill=fill)

    # Pinos: superior-esquerdo e inferior-direito
    PIN_R = 6
    pin_color = hex_to_rgb(CORES["highlight_pin"])

    # Pino 1: superior-esquerdo — círculo + linha vertical
    ov_draw.ellipse([x - PIN_R, y - PIN_R, x + PIN_R, y + PIN_R], fill=pin_color)
    ov_draw.line([x, y, x, y + height], fill=pin_color, width=2)

    # Pino 2: inferior-direito
    ex, ey = x + width, y + height
    ov_draw.ellipse([ex - PIN_R, ey - PIN_R, ex + PIN_R, ey + PIN_R], fill=pin_color)
    ov_draw.line([ex, y, ex, ey], fill=pin_color, width=2)

    image.alpha_composite(overlay)


# ── notes_header ──────────────────────────────────────────────────────────────

def notes_header(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    *,
    font=None,
) -> int:
    """
    Falso header do Apple Notes (modo escuro apenas).
    Esquerda: '< Notas' em accent_amber. Direita: '...' em accent_amber.
    Retorna nova Y.
    """
    amber = rgb("accent_amber")
    left_text = "< Notas"
    right_text = "..."

    kw = {"fill": amber}
    if font:
        kw["font"] = font
        try:
            bbox = font.getbbox("Ag")
            line_h = bbox[3] - bbox[1]
        except Exception:
            line_h = 24
    else:
        line_h = 24

    draw.text((x, y), left_text, **kw)

    # Alinhar '...' à direita
    if font:
        try:
            rw = font.getbbox(right_text)[2] - font.getbbox(right_text)[0]
        except Exception:
            rw = 20
    else:
        rw = 20
    draw.text((x + width - rw, y), right_text, **kw)

    return y + line_h + 16   # padding após o header


# ── editorial_divider ─────────────────────────────────────────────────────────

def editorial_divider(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    *,
    color: tuple = None,
    thickness: int = 4,    # 4–5 px (spec §5.3: 3–4 × 1,278 → 4–5)
    length: int = 136,     # múltiplo de 8, dentro de 123–153
) -> int:
    """
    Linha sólida alinhada à esquerda, espessura 4–5 px, largura 123–153 px.
    Nunca largura total.
    Retorna nova Y.
    """
    _color = color or hex_to_rgb(CORES["text_ink_primary"])
    draw.line(
        [x, y, x + length, y],
        fill=_color,
        width=thickness,
    )
    return y + thickness + 24   # espaço após o divisor


# ── checklist_pain ────────────────────────────────────────────────────────────

def checklist_pain(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    *,
    font=None,
    text_color: tuple = None,
    marker_size: int = 24,   # múltiplo de 8
) -> int:
    """
    Item de checklist de diagnóstico de dor.
    Marcador: quadrado verde arredondado com check branco.
    Fonte: DM Serif Display Regular (checklist_pain).
    Retorna nova Y.
    """
    _text_color = text_color or hex_to_rgb(CORES["text_ink_primary"])
    green = hex_to_rgb(CORES["check_green"])
    radius = 4

    # Quadrado verde arredondado
    mx, my = x, y
    draw.rounded_rectangle(
        [mx, my, mx + marker_size, my + marker_size],
        radius=radius,
        fill=green,
    )

    # Check branco dentro do marcador
    cpad = marker_size // 4
    draw.line(
        [mx + cpad, my + marker_size // 2,
         mx + marker_size // 2, my + marker_size - cpad,
         mx + marker_size - cpad, my + cpad],
        fill=(255, 255, 255),
        width=2,
    )

    # Texto
    text_x = x + marker_size + 12
    text_y = y + (marker_size - 32) // 2   # centralizar verticalmente com o marcador

    kw = {"fill": _text_color}
    if font:
        kw["font"] = font

    draw.text((text_x, text_y), text, **kw)

    line_h = marker_size + 8   # espaçamento entre itens
    return y + line_h


# ── checklist_method ──────────────────────────────────────────────────────────

def checklist_method(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    *,
    font=None,
    text_color: tuple = None,
    marker_color: tuple = None,
    marker_size: int = 24,
) -> int:
    """
    Item de checklist de método (modo escuro).
    Marcador: '[ ]' em cinza/âmbar.
    Fonte: DM Serif Display Italic (checklist_method).
    Retorna nova Y.
    """
    _text_color = text_color or hex_to_rgb(CORES["text_dark_primary"])
    _marker_color = marker_color or hex_to_rgb(CORES["accent_amber"])

    marker_text = "[ ]"
    kw_marker = {"fill": _marker_color}
    kw_text   = {"fill": _text_color}

    if font:
        kw_marker["font"] = font
        kw_text["font"]   = font
        try:
            mw = font.getbbox(marker_text)[2] - font.getbbox(marker_text)[0]
        except Exception:
            mw = marker_size
    else:
        mw = marker_size

    draw.text((x, y), marker_text, **kw_marker)
    draw.text((x + mw + 12, y), text, **kw_text)

    if font:
        try:
            _, top, _, bottom = font.getbbox("Ag")
            line_h = (bottom - top) + 8
        except Exception:
            line_h = 40
    else:
        line_h = 40

    return y + line_h
