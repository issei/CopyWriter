"""
carousel_resilience.py — Retry, backoff e rate-limit para o carrossel.

Implementa a estratégia de resiliência da spec v2 §4.
Usado principalmente no nó generate_visual_assets, mas o padrão de
retry/timeout é o mesmo para text_model e vision_model (consistência).

Nenhuma dependência do Streamlit ou de estado de sessão aqui.
"""
from __future__ import annotations

import logging
import random
import time

logger = logging.getLogger("carousel.resilience")


# ── RateLimitedError ──────────────────────────────────────────────────────────

class RateLimitedError(Exception):
    """
    Erro específico para HTTP 429, distinto de erros irrecuperáveis.
    Preserva retry_after (em segundos) quando disponível no cabeçalho da API.
    """

    def __init__(self, message: str = "Rate limit atingido", retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


# ── call_with_backoff ─────────────────────────────────────────────────────────

def call_with_backoff(
    fn,
    *args,
    max_attempts: int = 4,
    base_delay: float = 1.5,
    max_delay: float = 20.0,
    retriable_exceptions: tuple = (RateLimitedError, TimeoutError, ConnectionError),
    **kwargs,
):
    """
    Invoca fn(*args, **kwargs) com retry exponencial + jitter.

    - Retry apenas para retriable_exceptions (não para erros irrecuperáveis).
    - Se RateLimitedError.retry_after estiver definido, usa-o como piso do delay.
    - Após max_attempts sem sucesso, relança a última exceção.

    Exemplo de uso:
        image_bytes = call_with_backoff(
            image_model.generate,
            prompt,
            width=1080, height=1350,
            max_attempts=4,
        )
    """
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except retriable_exceptions as exc:
            attempt += 1
            if attempt >= max_attempts:
                logger.warning(
                    "Esgotadas %s tentativas para %s: %s",
                    attempt,
                    getattr(fn, "__name__", str(fn)),
                    exc,
                )
                raise

            # Calcula delay: exponencial com jitter + floor do Retry-After
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.25)   # jitter 25%

            # Respeitar Retry-After como piso (D spec v2 §4.2)
            if isinstance(exc, RateLimitedError) and exc.retry_after is not None:
                delay = max(delay, float(exc.retry_after))

            logger.info(
                "Tentativa %s falhou (%s). Retentando em %.1fs.",
                attempt,
                type(exc).__name__,
                delay,
            )
            time.sleep(delay)
