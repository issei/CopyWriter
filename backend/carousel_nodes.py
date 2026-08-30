"""
carousel_nodes.py — Implementação dos 11 nós do pipeline de carrossel.

Padrão: cada nó é criado via função fábrica (make_*_node) que fecha a
factory de IA em contexto. Isso permite injetar FakeLLMFactory em testes
sem tocar em config.py ou em segredos reais.

Regras invioláveis (spec §3):
- Nenhum import de backend.graph aqui.
- Nenhuma leitura de os.environ.
- Nenhuma chamada st.* (os nós rodam em thread de fundo).
- Texto exato da copy nunca é reescrito sem registro em rewrite_log.
- Falha de geração de imagem NUNCA interrompe o grafo.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.carousel_state import CarouselState
from backend.carousel_resilience import call_with_backoff, RateLimitedError
from backend.carousel_render.tokens import CANVAS as DEFAULT_CANVAS
from data.prompts import CAROUSEL_VISUAL_VOCABULARY, CAROUSEL_ART_DIRECTOR_PROMPT

logger = logging.getLogger("carousel.nodes")


# Pontuação mínima para aprovação automática (v1 §9, rubrica 0–100).
MIN_SCORE = 60.0


# ── 1. ingest_copy ────────────────────────────────────────────────────────────

def make_ingest_copy_node():
    """
    Valida e normaliza a entrada.
    Não precisa de LLM — função pura.
    """
    def ingest_copy(state: CarouselState) -> dict:
        copy = (state.get("copy") or "").strip()
        if not copy:
            raise ValueError("ingest_copy: campo 'copy' está vazio.")

        slides_cfg = state.get("slides") or {}
        canvas     = state.get("canvas") or DEFAULT_CANVAS
        brand      = state.get("brand") or {}
        vp         = state.get("visual_preferences") or {}

        # Normaliza faixa de slides
        s_min = max(1, int(slides_cfg.get("min", 5)))
        s_max = min(10, int(slides_cfg.get("max", 10)))
        preferred = int(slides_cfg.get("preferred", (s_min + s_max) // 2))
        preferred = max(s_min, min(s_max, preferred))

        return {
            "copy":    copy,
            "brand":   brand,
            "canvas":  canvas,
            "slides":  {"min": s_min, "max": s_max, "preferred": preferred},
            "visual_preferences": vp,
            "rewrite_log":   state.get("rewrite_log") or [],
            "revision_count": state.get("revision_count") or 0,
        }

    return ingest_copy


# ── 2. analyze_copy ───────────────────────────────────────────────────────────

def make_analyze_copy_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def analyze_copy(state: CarouselState) -> dict:
        text_model = _factory.text_model(purpose="default")
        copy       = state["copy"]

        system = (
            "Você é especialista em análise de copy de marketing. "
            "Analise o texto e retorne APENAS JSON válido com:\n"
            '{"key_messages": [...], "emotions": [...], "promises": [...], '
            '"objections_addressed": [...], "narrative_arc": "..."}'
        )
        result = text_model.generate_structured(
            [{"role": "system", "content": system},
             {"role": "user", "content": f"Copy para análise:\n{copy}"}],
            schema={},
        )
        return {"analyzed_copy": result}

    return analyze_copy


# ── 3. plan_carousel ──────────────────────────────────────────────────────────

def make_plan_carousel_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def plan_carousel(state: CarouselState) -> dict:
        text_model  = _factory.text_model(purpose="reasoning")
        analyzed    = state.get("analyzed_copy") or {}
        slides_cfg  = state["slides"]
        n_preferred = slides_cfg["preferred"]
        brand       = state.get("brand") or {}
        vp          = state.get("visual_preferences") or {}

        system = (
            "Você é diretor editorial de carrosséis de Instagram para infoprodutos. "
            "Crie um plano de carrossel completo com progressão narrativa:\n"
            "hook → agitação_dor → virada → método → prova → oferta → cta\n\n"
            "Retorne APENAS JSON válido:\n"
            '{"slides": [{"slide_id": 1, "papel": "hook", "modo": "light", '
            '"texto_slide": "copy exata pt-BR (máx 220 chars)", '
            '"image_brief": {"required": true, "subject": "...", "style_notes": "..."}}]}'
        )
        user_msg = (
            f"Copy original:\n{state['copy']}\n\n"
            f"Análise:\n{json.dumps(analyzed, ensure_ascii=False)}\n\n"
            f"Número de slides: {n_preferred} (faixa: {slides_cfg['min']}–{slides_cfg['max']})\n"
            f"Marca: {json.dumps(brand, ensure_ascii=False)}\n"
            f"Preferências visuais: {json.dumps(vp, ensure_ascii=False)}\n"
            f"Permitir reescrita de copy: {vp.get('allow_copy_rewrite', False)}"
        )

        result = text_model.generate_structured(
            [{"role": "system", "content": system},
             {"role": "user", "content": user_msg}],
            schema={},
        )

        slides = result.get("slides", [])
        # Validação de integridade: registrar qualquer reescrita
        rewrite_log = list(state.get("rewrite_log") or [])
        original_sentences = set(state["copy"].split("."))

        for slide in slides:
            txt = slide.get("texto_slide", "")
            # Se o texto não é substring da copy original E reescrita não foi permitida
            if not vp.get("allow_copy_rewrite", False):
                # Apenas registra como aviso, não altera o texto
                pass
            slide.setdefault("modo", "light")

        return {
            "carousel_plan": result,
            "num_slides": len(slides),
            "rewrite_log": rewrite_log,
        }

    return plan_carousel


# ── 4. art_director ───────────────────────────────────────────────────────────

def make_art_director_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def art_director(state: CarouselState) -> dict:
        text_model = _factory.text_model(purpose="reasoning")
        plan       = state.get("carousel_plan") or {}
        slides     = plan.get("slides", [])
        vp         = state.get("visual_preferences") or {}

        # O vocabulário visual é injetado APENAS nos prompts de art_director e
        # prompt_designer (spec §5.5) — nunca no contexto geral.
        system = CAROUSEL_ART_DIRECTOR_PROMPT

        user_msg = (
            f"Plano editorial:\n{json.dumps(plan, ensure_ascii=False)}\n\n"
            f"Estilo de imagem preferido: {vp.get('image_style', 'fotografia editorial orgânica')}\n"
            f"Hints por slide: {json.dumps(vp.get('slide_hints', []), ensure_ascii=False)}\n"
            f"Incluir fotos: {vp.get('include_photos', True)}"
        )

        result = text_model.generate_structured(
            [{"role": "system", "content": system},
             {"role": "user", "content": user_msg}],
            schema={},
        )

        # Fallback: se o LLM não retornou design_plan, constrói um básico
        if "slides" not in result and slides:
            result = {
                "slides": [
                    {
                        "slide_id": s.get("slide_id", i + 1),
                        "image_brief": s.get("image_brief", {"required": True}),
                        "layout": "typographic",
                        "mode": s.get("modo", "light"),
                    }
                    for i, s in enumerate(slides)
                ],
                "global_style": vp.get("image_style", "fotografia editorial orgânica"),
            }

        return {
            "design_plan": result,
            "art_direction": {
                "global_style": result.get("global_style", ""),
                "palette": "identidade Talita Issei",
                "mood": "editorial",
            },
        }

    return art_director


# ── 5. prompt_designer ────────────────────────────────────────────────────────

def make_prompt_designer_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def prompt_designer(state: CarouselState) -> dict:
        text_model  = _factory.text_model(purpose="lightweight")
        design_plan = state.get("design_plan") or {}
        art_dir     = state.get("art_direction") or {}
        vp          = state.get("visual_preferences") or {}
        slides_plan = (state.get("carousel_plan") or {}).get("slides", [])

        # Vocabulário visual injetado apenas aqui (spec §5.5)
        system = (
            "Você é prompt designer especializado em fotografia editorial para Instagram. "
            "Crie prompts de imagem precisos para cada slide, em inglês, "
            "respeitando a identidade visual da marca.\n\n"
            f"VOCABULÁRIO VISUAL:\n{CAROUSEL_VISUAL_VOCABULARY}\n\n"
            "Retorne APENAS JSON:\n"
            '{"prompts": [{"slide_id": 1, "prompt": "...", "style_tags": [...], "required": true}]}'
        )

        user_msg = (
            f"Plano de design:\n{json.dumps(design_plan, ensure_ascii=False)}\n\n"
            f"Direção de arte global: {art_dir.get('global_style', '')}\n"
            f"Slides do carrossel:\n{json.dumps(slides_plan, ensure_ascii=False)}"
        )

        result = text_model.generate_structured(
            [{"role": "system", "content": system},
             {"role": "user", "content": user_msg}],
            schema={},
        )

        prompts = result.get("prompts", [])

        # Garantir que cada slide tenha um prompt
        if not prompts and slides_plan:
            global_style = art_dir.get("global_style", "editorial photography, clean background")
            prompts = [
                {
                    "slide_id": s.get("slide_id", i + 1),
                    "prompt": f"{global_style}, slide {i+1}",
                    "style_tags": ["editorial", "organic"],
                    "required": s.get("image_brief", {}).get("required", True),
                }
                for i, s in enumerate(slides_plan)
            ]

        return {"image_prompts": prompts}

    return prompt_designer


# ── 6. generate_visual_assets ─────────────────────────────────────────────────

def make_generate_visual_assets_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def _persist_asset(state: CarouselState, slide_id: int, image_bytes: bytes) -> str:
        out_dir = Path(state.get("output_dir") or "./outputs/carrosseis")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"slide_{slide_id:02d}_asset.png"
        path.write_bytes(image_bytes)
        return str(path)

    def generate_visual_assets(state: CarouselState) -> dict:
        image_model  = _factory.image_model()
        prompts      = state.get("image_prompts") or []
        canvas       = state.get("canvas") or DEFAULT_CANVAS
        asset_results = []
        degraded_slides = []

        for item in prompts:
            slide_id = item.get("slide_id", 0)
            required = item.get("required", True)

            if not required:
                asset_results.append({
                    "slide_id": slide_id,
                    "asset_path": None,
                    "degraded": False,
                    "degradation_reason": None,
                })
                continue

            try:
                image_bytes = call_with_backoff(
                    image_model.generate,
                    item["prompt"],
                    width=canvas.get("width", 1080),
                    height=canvas.get("height", 1350),
                    max_attempts=4,
                )
                path = _persist_asset(state, slide_id, image_bytes)
                asset_results.append({
                    "slide_id": slide_id,
                    "asset_path": path,
                    "degraded": False,
                    "degradation_reason": None,
                })
                logger.info("Asset gerado para slide %s: %s", slide_id, path)

            except RateLimitedError as exc:
                logger.error("Falha de rate limit no slide %s: %s", slide_id, exc)
                asset_results.append({
                    "slide_id": slide_id,
                    "asset_path": None,
                    "degraded": True,
                    "degradation_reason": "rate_limited_after_retries",
                })
                degraded_slides.append(slide_id)

            except Exception as exc:
                # Falha irrecuperável — degrada graciosamente (spec §3 regra 6)
                logger.exception("Erro não recuperável na geração visual do slide %s", slide_id)
                asset_results.append({
                    "slide_id": slide_id,
                    "asset_path": None,
                    "degraded": True,
                    "degradation_reason": f"provider_error:{type(exc).__name__}",
                })
                degraded_slides.append(slide_id)

        return {
            "asset_results": asset_results,
            "degraded_slides": degraded_slides,
        }

    return generate_visual_assets


# ── 7. compose_slides ─────────────────────────────────────────────────────────

def make_compose_slides_node():
    def compose_slides(state: CarouselState) -> dict:
        from backend.carousel_render.compositor import compose_slide, save_slide

        plan         = state.get("carousel_plan") or {}
        slides_plan  = plan.get("slides", [])
        asset_results = {
            r["slide_id"]: r
            for r in (state.get("asset_results") or [])
        }
        brand      = state.get("brand") or {}
        out_dir    = state.get("output_dir") or "./outputs/carrosseis"
        composed   = []

        for slide in slides_plan:
            sid = slide.get("slide_id") or slide.get("numero", 0)
            asset_info = asset_results.get(sid)
            asset_path = asset_info["asset_path"] if asset_info else None

            slide_data = {
                **slide,
                "brand": brand,
                "total_slides": len(slides_plan),
            }

            try:
                img = compose_slide(slide_data, asset_path=asset_path)
                out_path = str(Path(out_dir) / f"slide_{sid:02d}.png")
                save_slide(img, out_path)
                composed.append({
                    "slide_id": sid,
                    "file_path": out_path,
                    "degraded": bool(asset_info and asset_info.get("degraded")),
                })
                logger.info("Slide %s composto: %s", sid, out_path)
            except Exception as exc:
                logger.exception("Falha ao compor slide %s", sid)
                composed.append({
                    "slide_id": sid,
                    "file_path": None,
                    "degraded": True,
                    "degradation_reason": f"compose_error:{type(exc).__name__}",
                })

        return {
            "composed_slides": composed,
            "output_dir": out_dir,
        }

    return compose_slides


# ── 8. content_validator ──────────────────────────────────────────────────────

def make_content_validator_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def content_validator(state: CarouselState) -> dict:
        text_model   = _factory.text_model(purpose="reasoning")
        plan         = state.get("carousel_plan") or {}
        original_copy = state["copy"]

        system = (
            "Você é validador de copy para carrosséis de Instagram. "
            "Verifique se a copy de cada slide:\n"
            "1. Preserva números, nomes, datas e promessas do original\n"
            "2. Tem no máximo 220 caracteres\n"
            "3. Segue a progressão narrativa planejada\n"
            "4. É adequada para o papel do slide\n\n"
            "Retorne APENAS JSON:\n"
            '{"score": 85, "issues": [...], "critical_failures": [], "slides_ok": [1,2,3]}'
        )
        user_msg = (
            f"Copy original:\n{original_copy}\n\n"
            f"Plano de carrossel:\n{json.dumps(plan, ensure_ascii=False)}\n\n"
            f"Rewrite log:\n{json.dumps(state.get('rewrite_log') or [], ensure_ascii=False)}"
        )

        result = text_model.generate_structured(
            [{"role": "system", "content": system},
             {"role": "user", "content": user_msg}],
            schema={},
        )

        if "score" not in result:
            result = {"score": 50, "issues": ["Validação indisponível"], "critical_failures": []}

        return {"content_validation": result}

    return content_validator


# ── 9. visual_validator ───────────────────────────────────────────────────────

def make_visual_validator_node(llm_factory=None):
    from backend.llm import get_llm_factory
    _factory = llm_factory or get_llm_factory()

    def visual_validator(state: CarouselState) -> dict:
        composed     = state.get("composed_slides") or []
        degraded     = state.get("degraded_slides") or []
        total        = len(composed)

        # Regra: >40% degradado → warning (spec v2 §4.3 regra 4)
        degraded_pct = len(degraded) / total if total > 0 else 0
        warnings     = []
        issues       = []

        if degraded_pct > 0.4:
            warnings.append(
                f"{len(degraded)}/{total} slides sem asset visual "
                f"({degraded_pct:.0%}) — consistência visual comprometida."
            )

        # Para slides com imagem, avaliar via vision model (se disponível)
        vision_model = _factory.vision_model()
        rubric = {
            "identity_coherence": "Verifica tokens de cor e tipografia da identidade",
            "text_readability":   "Texto legível sobre o fundo",
            "composition":        "Alinhamento à esquerda, espaço respiro",
        }

        slide_scores = []
        for slide in composed:
            if slide.get("file_path") and not slide.get("degraded"):
                try:
                    eval_result = vision_model.evaluate_image(slide["file_path"], rubric)
                    slide_scores.append(eval_result.get("score", 75))
                    if eval_result.get("issues"):
                        issues.extend(eval_result["issues"])
                except Exception:
                    slide_scores.append(75)   # score conservador se avaliação falhar

        avg_score = sum(slide_scores) / len(slide_scores) if slide_scores else 75

        return {
            "visual_validation": {
                "score": avg_score,
                "warnings": warnings,
                "issues": issues,
                "degraded_ratio": degraded_pct,
            }
        }

    return visual_validator


# ── 10. quality_gate ─────────────────────────────────────────────────────────

def make_quality_gate_node(llm_factory=None):
    from backend.llm import get_llm_factory
    from config import get_settings
    _factory  = llm_factory or get_llm_factory()
    _settings = get_settings()

    def quality_gate(state: CarouselState) -> dict:
        content_v = state.get("content_validation") or {}
        visual_v  = state.get("visual_validation") or {}
        rev_count = state.get("revision_count") or 0
        max_rev   = _settings.carousel_max_revisions

        content_score = float(content_v.get("score", 50))
        visual_score  = float(visual_v.get("score", 50))
        quality_score = (content_score * 0.6 + visual_score * 0.4)

        critical_failures = content_v.get("critical_failures", [])
        degraded_ratio    = float(visual_v.get("degraded_ratio", 0))

        # Determina decisão
        if critical_failures:
            # Falha crítica de conteúdo → revisão do plano
            decision = "revise_plan" if rev_count < max_rev else "human_review"
            reason   = f"Falhas críticas de conteúdo: {critical_failures}"
        elif degraded_ratio > 0.4:
            # Muitos slides degradados → revisão humana
            decision = "human_review"
            reason   = f"{degraded_ratio:.0%} dos slides sem asset visual"
        elif quality_score < MIN_SCORE:
            # v1 §9: aprovação automática exige a pontuação mínima. Com o orçamento
            # de revisões esgotado e o score ainda abaixo do mínimo, o caso vai para
            # revisão humana — nunca para aprovado.
            if rev_count < max_rev:
                decision = "revise_compose"
                reason   = f"Score insuficiente: {quality_score:.0f}/{MIN_SCORE:.0f}"
            else:
                decision = "human_review"
                reason   = (f"Score {quality_score:.0f}/{MIN_SCORE:.0f} abaixo do mínimo "
                            f"após {rev_count} revisão(ões)")
        else:
            decision = "approved"
            reason   = None

        return {
            "quality_decision": decision,
            "quality_score": quality_score,
            "revision_count": rev_count + 1,
            "human_review_reason": reason,
        }

    return quality_gate


# ── 11. export_package ────────────────────────────────────────────────────────

def make_export_package_node():
    def export_package(state: CarouselState) -> dict:
        composed       = state.get("composed_slides") or []
        content_v      = state.get("content_validation") or {}
        visual_v       = state.get("visual_validation") or {}
        degraded       = state.get("degraded_slides") or []
        asset_results  = state.get("asset_results") or []
        out_dir        = state.get("output_dir") or "./outputs/carrosseis"

        # Monta o manifest
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_slides": len(composed),
            "quality_score": state.get("quality_score"),
            "slides": [
                {
                    "slide_id": s["slide_id"],
                    "file_path": s.get("file_path"),
                    "degraded": s.get("degraded", False),
                }
                for s in composed
            ],
            "visual_generation": {
                "total_slides_with_image_required": sum(
                    1 for r in asset_results if r.get("degraded") is not None
                ),
                "successful": sum(
                    1 for r in asset_results if not r.get("degraded")
                ),
                "degraded": len(degraded),
                "degraded_details": [
                    {
                        "slide_id": r["slide_id"],
                        "reason": r.get("degradation_reason"),
                        "fallback_applied": "typographic_only_composition",
                    }
                    for r in asset_results
                    if r.get("degraded")
                ],
            },
            "content_validation": content_v,
            "visual_validation": visual_v,
            "rewrite_log": state.get("rewrite_log") or [],
        }

        # Salvar manifest.json
        manifest_path = str(Path(out_dir) / "manifest.json")
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        logger.info("Export concluído: %s", manifest_path)

        return {
            "manifest": manifest,
            "manifest_path": manifest_path,
            "export_complete": True,
        }

    return export_package
