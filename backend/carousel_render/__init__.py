# backend/carousel_render/__init__.py
"""
Módulo de renderização determinística do carrossel.
Não faz nenhuma chamada a API de imagem — apenas Pillow e assets locais.
"""
from backend.carousel_render.compositor import compose_slide

__all__ = ["compose_slide"]
