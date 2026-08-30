"""
Testes unitários do renderizador determinístico do carrossel visual.

Cobertura:
- Resiliência tipográfica (fallback para asset_path=None)
- Inferência de modo (light/dark)
- Componentes e limites de canvas (1080x1350)
- Quebra de linha
"""
import sys
from pathlib import Path
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.carousel_render.compositor import compose_slide, _infer_mode
from backend.carousel_render.typography import wrap_text, font_for_element
from backend.carousel_render.tokens import CANVAS, hex_to_rgb, CORES

# Setup genérico de slide para testes
@pytest.fixture
def base_slide():
    return {
        "texto_slide": "Ação estratégica: não é só ânimo — é método. O que diferencia quem escala.",
        "papel": "hook",
        "brand": {
            "name": "Nome Sobrenome",
            "handle": "@handle",
            "verified": True
        }
    }

# 1. Teste de resiliência (Sem Imagem)
def test_render_resilience_pure_typography(base_slide):
    # Passando asset_path=None intencionalmente
    img = compose_slide(base_slide, asset_path=None)
    
    assert isinstance(img, Image.Image)
    assert img.size == (CANVAS["width"], CANVAS["height"])
    assert img.mode == "RGBA"

# 2. Teste de inferência de modo (light vs dark)
@pytest.mark.parametrize("papel,esperado", [
    ("hook", "light"),
    ("dor", "light"),
    ("prova", "light"),
    ("oferta", "light"),
    ("cta", "light"),
    ("virada", "dark"),
    ("método", "dark"),
    ("metodo", "dark"),
    ("etapa", "dark"),
    ("etapas", "dark"),
    ("desconhecido", "light")
])
def test_infer_mode(papel, esperado):
    assert _infer_mode(papel) == esperado

# 3. Teste de fallback explícito caso modo seja passado
def test_explicit_mode_override(base_slide):
    base_slide["papel"] = "hook"  # normalmente light
    base_slide["modo"] = "dark"   # override
    
    img = compose_slide(base_slide, asset_path=None)
    # Testa se pegou a cor de fundo dark:
    bg_color = hex_to_rgb(CORES["bg_dark_notepad"]) + (255,)
    # pega a cor do pixel (0,0) - margem, deve ser bg color
    pixel = img.getpixel((0, 0))
    assert pixel == bg_color

# 4. Teste de quebra de linha determinística
def test_text_wrapping():
    texto = "Uma frase muito longa que definitivamente precisa quebrar em múltiplas linhas devido à largura limitada do canvas."
    font = font_for_element("title")
    lines = wrap_text(texto, font, max_width=920)
    
    assert len(lines) > 1
    # Garante que nenhuma linha exceda a largura
    for line in lines:
        left, top, right, bottom = font.getbbox(line)
        assert (right - left) <= 920

# 5. Teste de renderização com checklists
def test_render_checklists(base_slide):
    base_slide["checkitems"] = [
        "Identificar o gargalo",
        "Desenhar a solução",
        "Implementar em ciclos"
    ]
    base_slide["papel"] = "metodo" # força dark, que renderiza checklist textual [ ] em itálico
    
    img = compose_slide(base_slide, asset_path=None)
    assert img.size == (CANVAS["width"], CANVAS["height"])
    # Apenas verifica se rodou sem crash. O teste exato de pixel seria overfit.

# 6. Truncamento/vazio não quebra
def test_empty_text_does_not_crash(base_slide):
    base_slide["texto_slide"] = ""
    img = compose_slide(base_slide, asset_path=None)
    assert img.size == (1080, 1350)
