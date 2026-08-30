"""
backend/llm.py

Contém:
  - get_llm(): singleton do ChatGoogleGenerativeAI para o grafo principal (inalterado)
  - LLMClientFactory: fábrica de clientes de IA para o módulo de carrossel
  - Protocolos: TextModel, VisionModel, ImageModel
  - Implementações: GeminiTextModel, GeminiVisionModel, GeminiImageModel

Nenhuma chave de API é lida por os.environ dentro do módulo de carrossel —
toda configuração passa por config.get_settings() e é resolvida nos construtores
privados da Factory (D5 da SPEC).
"""
from __future__ import annotations

import os
import logging
from typing import Protocol, runtime_checkable

import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from config import GOOGLE_API_KEY, GEMINI_MODEL, TEMPERATURE

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

logger = logging.getLogger("carousel.llm")


# ── get_llm: singleton existente (inalterado) ─────────────────────────────────

@st.cache_resource
def get_llm() -> ChatGoogleGenerativeAI:
    """LLM singleton — instanciado uma única vez por sessão do servidor."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=TEMPERATURE,
        api_key=GOOGLE_API_KEY,
    )


# ── Protocolos de interface ────────────────────────────────────────────────────

@runtime_checkable
class TextModel(Protocol):
    """Interface para geração de texto estruturado."""
    def generate_structured(self, messages: list[dict], schema: dict) -> dict:
        ...

    def generate(self, messages: list[dict]) -> str:
        ...


@runtime_checkable
class VisionModel(Protocol):
    """Interface para avaliação multimodal de imagens."""
    def evaluate_image(self, image_path: str, rubric: dict) -> dict:
        ...


@runtime_checkable
class ImageModel(Protocol):
    """Interface para geração de imagens."""
    def generate(self, prompt: str, *, width: int, height: int, seed: int | None = None) -> bytes:
        ...


# ── Implementações Gemini ──────────────────────────────────────────────────────

class GeminiTextModel:
    """
    Adaptador de TextModel sobre ChatGoogleGenerativeAI.
    Usado nos nós de texto do grafo de carrossel.
    """

    def __init__(self, settings: "config.Settings", purpose: str = "default"):
        import config
        _model_map = {
            "default":     settings.text_model,
            "lightweight": settings.text_model,
            "reasoning":   settings.text_model_reasoning,
        }
        model_id = _model_map.get(purpose, settings.text_model)
        self._llm = ChatGoogleGenerativeAI(
            model=model_id,
            temperature=settings.temperature,
            api_key=settings.google_api_key,
        )

    def generate(self, messages: list[dict]) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        lc_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        response = self._llm.invoke(lc_messages)
        return response.content

    def generate_structured(self, messages: list[dict], schema: dict) -> dict:
        import json
        import re
        raw = self.generate(messages)
        # Tenta extrair JSON do texto
        for pattern in [r"```json\s*([\s\S]+?)\s*```", r"```\s*([\s\S]+?)\s*```"]:
            m = re.search(pattern, raw)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
        # Tenta JSON direto
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Extrai primeiro {...}
        m = re.search(r"\{[\s\S]+\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"error": "json_parse_failed", "raw_content": raw}


class GeminiVisionModel:
    """
    Adaptador de VisionModel para avaliação multimodal.
    Usa o modelo vision configurado em settings.
    """

    def __init__(self, settings: "config.Settings"):
        self._llm = ChatGoogleGenerativeAI(
            model=settings.vision_model,
            temperature=0.1,   # baixa temperatura para avaliação mais determinística
            api_key=settings.google_api_key,
        )

    def evaluate_image(self, image_path: str, rubric: dict) -> dict:
        import base64
        import json
        from pathlib import Path
        from langchain_core.messages import HumanMessage

        img_bytes = Path(image_path).read_bytes()
        img_b64   = base64.b64encode(img_bytes).decode()
        ext       = Path(image_path).suffix.lstrip(".")
        mime_type = f"image/{ext.lower()}"

        prompt = (
            f"Avalie esta imagem conforme a rubrica a seguir e retorne APENAS JSON válido:\n"
            f"{json.dumps(rubric, ensure_ascii=False)}\n\n"
            f"Responda com: {{\"score\": <0-100>, \"feedback\": \"...\", \"issues\": [...]}}"
        )

        msg = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}},
            ]
        )
        response = self._llm.invoke([msg])
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"score": 0, "feedback": response.content, "issues": []}


# Proporções aceitas pela API de imagem. A API não recebe pixels: escolher a
# mais próxima é o que faz `width`/`height` deixarem de ser decorativos.
_ASPECT_RATIOS = ("1:1", "2:3", "3:4", "4:5", "5:4", "4:3", "3:2", "9:16", "16:9", "21:9")


def _aspect_ratio(width: int, height: int) -> str:
    """Proporção suportada mais próxima de width/height. 1080×1350 → '4:5'."""
    alvo = width / height

    def distancia(r: str) -> float:
        a, b = r.split(":")
        return abs(alvo - int(a) / int(b))

    return min(_ASPECT_RATIOS, key=distancia)


class GeminiImageModel:
    """
    Adaptador de ImageModel usando google.genai diretamente.
    ChatGoogleGenerativeAI é chat e não devolve imagem utilizável (spec §6.3).

    HTTP 429 é traduzido para RateLimitedError, preservando Retry-After.
    """

    def __init__(self, settings: "config.Settings"):
        from google import genai as _genai
        self._client = _genai.Client(api_key=settings.google_api_key)
        self._model  = settings.image_model

    def generate(self, prompt: str, *, width: int, height: int, seed: int | None = None) -> bytes:
        from google.genai import types
        from backend.carousel_resilience import RateLimitedError

        try:
            resposta = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    # Sem isto a API devolve 1:1 e o compositor recorta um quadrado
                    # para 4:5, jogando fora metade do enquadramento.
                    image_config=types.ImageConfig(aspect_ratio=_aspect_ratio(width, height)),
                ),
            )
            # Candidato bloqueado (safety, recitation) vem com content=None: sem
            # guarda isso vira AttributeError e mascara o motivo real.
            candidato = (resposta.candidates or [None])[0]
            partes = getattr(getattr(candidato, "content", None), "parts", None) or []
            for parte in partes:
                if parte.inline_data:
                    return parte.inline_data.data
            raise RuntimeError(
                f"resposta sem imagem (finish_reason={getattr(candidato, 'finish_reason', None)})"
            )
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                # Extrair Retry-After se presente
                import re
                m = re.search(r"[Rr]etry.?[Aa]fter['\": ]+(\d+)", msg)
                retry_after = int(m.group(1)) if m else None
                raise RateLimitedError(
                    f"Rate limit atingido no modelo de imagem: {msg}",
                    retry_after=retry_after,
                ) from exc
            raise


# ── LLMClientFactory ──────────────────────────────────────────────────────────

class LLMClientFactory:
    """
    Fábrica única de clientes de IA para todo o projeto.

    Reaproveita as credenciais já centralizadas em config.py. Qualquer
    módulo do projeto — incluindo o pipeline de copy existente e o novo
    módulo de carrossel — deve obter clientes através desta fábrica em
    vez de instanciar SDKs de provedor diretamente.

    Nenhuma chave de API é lida por os.environ aqui — tudo passa por
    config.get_settings() (D5 da SPEC).
    """

    def __init__(self, settings=None):
        import config
        self._settings = settings or config.get_settings()
        self._cache: dict[str, object] = {}

    def text_model(self, *, purpose: str = "default") -> GeminiTextModel:
        """
        purpose: 'default' | 'lightweight' | 'reasoning'
        Permite escolher modelo mais barato para tarefas leves ou mais capaz
        para julgamento ambíguo, sem fixar IDs de modelo no código.
        """
        return self._cached(
            key=f"text:{purpose}",
            builder=lambda: GeminiTextModel(self._settings, purpose),
        )

    def vision_model(self) -> GeminiVisionModel:
        return self._cached(key="vision", builder=lambda: GeminiVisionModel(self._settings))

    def image_model(self) -> GeminiImageModel:
        return self._cached(key="image", builder=lambda: GeminiImageModel(self._settings))

    def _cached(self, key: str, builder):
        if key not in self._cache:
            self._cache[key] = builder()
        return self._cache[key]


def get_llm_factory() -> LLMClientFactory:
    """Ponto único de acesso à factory — injetado nos nós do carrossel."""
    return LLMClientFactory()

