"""
carousel_state.py — Estado tipado do pipeline de carrossel.

CarouselState é independente de AgentState (backend/graph.py).
Nenhum campo é compartilhado por referência com o grafo principal.
"""
from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class SlideAssetResult(TypedDict):
    slide_id: int
    asset_path: Optional[str]
    degraded: bool
    degradation_reason: Optional[str]


class CarouselState(TypedDict, total=False):
    """
    Estado completo do pipeline de geração de carrossel.

    Campos com total=False são opcionais — não precisam estar presentes
    no estado inicial. Cada nó preenche os campos de sua responsabilidade.
    """

    # ── Entrada ────────────────────────────────────────────────────────────────
    copy: str                          # copy pt-BR já aprovada pelo crítico
    brand: dict                        # {name, handle, avatar_path, verified, voice}
    slides: dict                       # {min, max, preferred}
    canvas: dict                       # {width, height, format, quality}
    visual_preferences: dict           # {image_style, slide_hints, include_photos, allow_copy_rewrite}
    execution: dict                    # {output_dir, require_human_approval}

    # ── Análise ────────────────────────────────────────────────────────────────
    analyzed_copy: dict                # {key_messages, emotions, promises, objections}
    rewrite_log: list[dict]            # [{slide_id, original, rewritten, reason}]

    # ── Planejamento ──────────────────────────────────────────────────────────
    carousel_plan: dict                # {slides: [{slide_id, papel, texto_slide, mode, ...}]}
    num_slides: int                    # número final de slides planejados

    # ── Direção de Arte ────────────────────────────────────────────────────────
    design_plan: dict                  # {slides: [{slide_id, image_brief, layout, ...}]}
    art_direction: dict                # {global_style, palette, mood}

    # ── Prompts Visuais ────────────────────────────────────────────────────────
    image_prompts: list[dict]          # [{slide_id, prompt, style_tags}]

    # ── Geração de Assets ─────────────────────────────────────────────────────
    asset_results: list[SlideAssetResult]
    degraded_slides: list[int]         # IDs de slides com degradação

    # ── Composição ────────────────────────────────────────────────────────────
    composed_slides: list[dict]        # [{slide_id, file_path, degraded}]
    output_dir: str

    # ── Validação ─────────────────────────────────────────────────────────────
    content_validation: dict           # {score, issues, critical_failures}
    visual_validation: dict            # {score, issues, warnings}

    # ── Quality Gate ──────────────────────────────────────────────────────────
    quality_decision: str              # 'approved' | 'revise_plan' | 'revise_compose' | 'revise_art' | 'regenerate_asset' | 'human_review'
    quality_score: float               # 0-100
    revision_count: int                # número de revisões até agora
    human_review_reason: Optional[str] # motivo da pausa para aprovação humana

    # ── Export ────────────────────────────────────────────────────────────────
    manifest: dict                     # manifest.json completo
    manifest_path: Optional[str]
    export_complete: bool
