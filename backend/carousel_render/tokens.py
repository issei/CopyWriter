"""
tokens.py — Constantes visuais da identidade.

Valores exatos da especificação §5.1 e do documento de identidade visual.
NUNCA usar recuperação por similaridade para estes tokens — são constantes literais.
"""

# ── Canvas (D1: 4:5 — 1080×1350) ─────────────────────────────────────────────
CANVAS = {"width": 1080, "height": 1350, "format": "PNG", "quality": 95}

# ── Grid ──────────────────────────────────────────────────────────────────────
MARGEM = 80          # múltiplo de 8 — margem lateral e vertical mínima
CONTENT_W = 920      # 1080 - 2*80

# ── Cores ─────────────────────────────────────────────────────────────────────
CORES = {
    # Modo claro (Editorial / Paper)
    "bg_paper":          "#FFFFFF",
    "bg_warm_paper":     "#FBFAF7",
    # Modo escuro (Notepad / Bastidores)
    "bg_dark_notepad":   "#121212",
    # Texto modo claro
    "text_ink_primary":  "#111522",
    "text_ink_muted":    "#92949B",
    # Texto modo escuro
    "text_dark_primary": "#F5F5F7",
    # Destaque âmbar (iOS Notes)
    "accent_amber":      "#EAA034",
    # Grifo de seleção iOS (aplicar a ~60% de opacidade)
    "highlight_caramel": "#9E7138",
    "highlight_pin":     "#E7D6C2",
    # Selo de verificação (uso exclusivo)
    "verified_cyan":     "#13C4E5",
    # Checklist (check verde)
    "check_green":       "#5C9E31",
}

HIGHLIGHT_OPACITY = 0.60   # aplicado ao highlight_caramel


# ── Helpers de conversão de cor ───────────────────────────────────────────────

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Converte '#RRGGBB' em (R, G, B)."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def hex_to_rgba(hex_color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    """Converte '#RRGGBB' em (R, G, B, A) com opacidade [0, 1]."""
    r, g, b = hex_to_rgb(hex_color)
    return (r, g, b, int(255 * opacity))


def rgb(token: str) -> tuple[int, int, int]:
    """Atalho: CORES[token] → (R, G, B)."""
    return hex_to_rgb(CORES[token])
