# Metaprompt de especificação v2.0 — Módulo agentico de carrosséis integrado ao CopyWriter

## Instrução de uso

Use o texto abaixo como **prompt de especificação para um agente de desenvolvimento** que irá trabalhar **dentro do repositório existente `CopyWriter`** (gerador de copy baseado em RAG). Esta é uma revisão da especificação original de "Gerador agentico de carrosséis para Instagram", reescrita para respeitar a arquitetura, as convenções e a infraestrutura já em produção do projeto anfitrião. O agente não deve inventar decisões ausentes: quando uma escolha alterar significativamente a arquitetura, deve explicitar a decisão, assumir um padrão razoável e registrar a hipótese no README.

Esta versão **não substitui** o conteúdo de direção de conteúdo, tokens visuais, tipografia, grid e rubrica de qualidade da especificação original — esses continuam valendo integralmente. O que muda é **onde e como** esse pipeline é implementado dentro de um sistema que já existe e está em uso.

---

## 0. Contexto do projeto anfitrião

O `CopyWriter` é hoje um gerador de copy baseado em RAG com esta estrutura:

```text
CopyWriter/
├── app.py                  # ponto de entrada da aplicação (UI)
├── config.py                # configuração central, incluindo credenciais de IA
├── backend/
│   ├── llm.py                # acesso a modelos de linguagem
│   ├── rag.py                 # recuperação aumentada por geração
│   └── graph.py                # grafo LangGraph do fluxo de copy existente
└── frontend/
    ├── ui_form.py              # formulário de entrada do usuário
    ├── ui_historico.py          # histórico de execuções
    └── ui_results.py             # exibição de resultados
```

Pontos relevantes para a nova especificação:

- `config.py` já centraliza as credenciais de IA (API keys, base URLs). O módulo de carrossel **não deve** introduzir um segundo mecanismo de configuração de credenciais.
- `backend/graph.py` já implementa um `StateGraph` funcional para o fluxo de copy. Esse grafo está em produção e **não pode ser modificado, importado de forma acoplada, nem ter seu estado compartilhado** com o novo pipeline.
- `frontend/ui_form.py`, `ui_historico.py` e `ui_results.py` seguem um padrão de composição de UI que deve ser estendido, não reescrito.
- Não há, hoje, mecanismo assíncrono nem persistência de `thread_id` em banco de dados — isso é uma capacidade nova a ser introduzida exclusivamente para o módulo de carrossel, mas de forma que possa ser reaproveitada no futuro pelo restante do sistema.

Esta especificação assume que o agente de desenvolvimento tem acesso de leitura e escrita ao repositório e deve tratar todo arquivo fora do escopo abaixo como **somente leitura conceitual**: pode ser lido para entender convenções, mas não deve ser alterado, exceto pelas extensões pontuais e explicitamente autorizadas na Seção 3 (Factory em `llm.py`) e na Seção 6 (evolução de UI).

---

## 1. Objetivo da v2.0

Adicionar ao `CopyWriter` a capacidade de, a partir de uma copy já existente (ou de uma nova copy fornecida na hora), gerar um carrossel de Instagram completo — plano editorial, direção de arte, assets visuais, composição tipográfica determinística, validação e manifest — **como um módulo adjacente**, sem tocar no pipeline de geração de copy já validado em produção.

O critério de sucesso arquitetural desta versão é: **o diff da implementação não deve conter alterações em `backend/graph.py`**, e qualquer alteração em `backend/llm.py` deve ser estritamente aditiva (novas classes/funções), nunca uma reescrita de comportamento existente.

---

## 2. Restrição arquitetural central — isolamento do grafo

### 2.1 Novo arquivo: `backend/carousel_graph.py`

Todo o pipeline agentico de carrossel — os onze nós descritos na especificação original (`ingest_copy`, `analyze_copy`, `plan_carousel`, `art_director`, `prompt_designer`, `generate_visual_assets`, `compose_slides`, `content_validator`, `visual_validator`, `quality_gate`, `export_package`) — deve ser implementado em um novo módulo `backend/carousel_graph.py`, com seu próprio `StateGraph`, seu próprio `TypedDict`/modelo Pydantic de estado, e seu próprio checkpointer.

Regras obrigatórias:

1. `backend/carousel_graph.py` **não importa** `backend/graph.py` e vice-versa. Os dois grafos são compilados de forma independente. Se houver necessidade de reaproveitar uma copy já gerada pelo pipeline de `graph.py`, isso é feito **fora do grafo**, na camada de orquestração do `app.py`, passando o texto já pronto como entrada do novo grafo — nunca por acoplamento de estado entre os dois `StateGraph`.
2. O estado do carrossel (`CarouselState`) é um tipo novo, independente do estado usado em `graph.py`. Nenhum campo é compartilhado por referência.
3. O checkpointer do carrossel é configurado de forma independente (Seção 5) e usa um namespace de `thread_id` próprio, para não colidir com identificadores eventualmente usados pelo pipeline de copy.
4. Caso `backend/graph.py` exponha utilitários genuinamente genéricos (por exemplo, um wrapper de retry, um logger estruturado, um parser de JSON estrito) que não seja duplicação óbvia, esses utilitários podem ser **extraídos** para um módulo compartilhado neutro (ex.: `backend/common.py`), desde que a extração seja um refactor puro sem alterar o comportamento de `graph.py`. Qualquer extração desse tipo deve ser feita como um commit isolado, com testes de regressão do pipeline de copy executados antes e depois, e documentada no README como uma decisão explícita.
5. Estrutura recomendada do novo arquivo, mantendo os nós pequenos e testáveis conforme o documento original:

```python
# backend/carousel_graph.py
from langgraph.graph import StateGraph, START, END
from backend.carousel_state import CarouselState
from backend.carousel_nodes import (
    ingest_copy, analyze_copy, plan_carousel, art_director,
    prompt_designer, generate_visual_assets, compose_slides,
    content_validator, visual_validator, quality_gate, export_package,
)

def build_carousel_graph(checkpointer):
    graph = StateGraph(CarouselState)
    graph.add_node("ingest_copy", ingest_copy)
    graph.add_node("analyze_copy", analyze_copy)
    graph.add_node("plan_carousel", plan_carousel)
    graph.add_node("art_director", art_director)
    graph.add_node("prompt_designer", prompt_designer)
    graph.add_node("generate_visual_assets", generate_visual_assets)
    graph.add_node("compose_slides", compose_slides)
    graph.add_node("content_validator", content_validator)
    graph.add_node("visual_validator", visual_validator)
    graph.add_node("quality_gate", quality_gate)
    graph.add_node("export_package", export_package)

    graph.add_edge(START, "ingest_copy")
    graph.add_edge("ingest_copy", "analyze_copy")
    graph.add_edge("analyze_copy", "plan_carousel")
    graph.add_edge("plan_carousel", "art_director")
    graph.add_edge("art_director", "prompt_designer")
    graph.add_edge("prompt_designer", "generate_visual_assets")
    graph.add_edge("generate_visual_assets", "compose_slides")
    graph.add_edge("compose_slides", "content_validator")
    graph.add_edge("compose_slides", "visual_validator")
    graph.add_edge(["content_validator", "visual_validator"], "quality_gate")
    graph.add_conditional_edges(
        "quality_gate",
        route_quality_gate,
        {
            "approved": "export_package",
            "revise_plan": "plan_carousel",
            "revise_compose": "compose_slides",
            "revise_art": "art_director",
            "regenerate_asset": "generate_visual_assets",
            "human_review": END,  # retomado depois via checkpoint (ver Seção 5)
        },
    )
    graph.add_edge("export_package", END)
    return graph.compile(checkpointer=checkpointer)
```

Os módulos `backend/carousel_state.py` e `backend/carousel_nodes.py` (ou um pacote `backend/carousel/` com submódulos, se a equipe preferir granularidade maior — `nodes/plan.py`, `nodes/art_direction.py`, `nodes/generation.py`, `nodes/validation.py`) contêm, respectivamente, o estado tipado e a implementação de cada nó, seguindo integralmente as regras de conteúdo, tokens visuais, contratos de entrada/saída e rubrica de qualidade já definidas na especificação original (Seções 2 a 9 do documento v1).

### 2.2 Reuso de `backend/rag.py`

O `rag.py` existente pode ser reaproveitado, de forma opcional, dentro de `analyze_copy` ou `plan_carousel`, caso a copy de origem já esteja indexada e o time queira enriquecer o plano editorial com contexto recuperado (por exemplo, materiais de marca, glossário de termos técnicos protegidos). Esse uso é uma **chamada de função**, não uma dependência estrutural: `carousel_graph.py` importa e invoca funções utilitárias de `rag.py` (leitura), mas não estende nem modifica seu comportamento.

---

## 3. Reuso de infraestrutura de IA — `backend/llm.py` como Factory

### 3.1 Problema

A especificação original define três interfaces independentes de provedor (`TextModel`, `VisionModel`, `ImageModel`) e espera configuração via variáveis de ambiente dedicadas (`TEXT_MODEL_PROVIDER`, `OPENAI_API_KEY` etc.). Isso duplicaria a gestão de credenciais que `config.py` já centraliza para o restante do `CopyWriter`.

### 3.2 Solução — extensão aditiva de `backend/llm.py`

`backend/llm.py` deve ganhar uma **Factory** que constrói instâncias configuradas dos três adaptadores, reutilizando exclusivamente as credenciais e endpoints já expostos por `config.py`. Nenhuma chave nova é lida diretamente de variável de ambiente dentro do módulo de carrossel; toda configuração passa por essa Factory.

```python
# backend/llm.py  (adição — não remover nada existente)
from __future__ import annotations
from typing import Protocol
import config


class TextModel(Protocol):
    def generate_structured(self, messages: list[dict], schema: dict) -> dict: ...


class VisionModel(Protocol):
    def evaluate_image(self, image_path: str, rubric: dict) -> dict: ...


class ImageModel(Protocol):
    def generate(self, prompt: str, *, width: int, height: int, seed: int | None = None) -> bytes: ...


class LLMClientFactory:
    """Fábrica única de clientes de IA para todo o projeto.

    Reaproveita as credenciais já centralizadas em config.py. Qualquer
    módulo do projeto — incluindo o pipeline de copy existente e o novo
    módulo de carrossel — deve obter clientes através desta fábrica em
    vez de instanciar SDKs de provedor diretamente.
    """

    def __init__(self, settings: "config.Settings" | None = None):
        self._settings = settings or config.get_settings()
        self._cache: dict[str, object] = {}

    def text_model(self, *, purpose: str = "default") -> TextModel:
        """purpose permite escolher um modelo mais barato para tarefas
        leves (ex.: 'lightweight') ou mais capaz para julgamento
        ambíguo (ex.: 'reasoning'), sem fixar IDs de modelo no código."""
        return self._cached(
            key=f"text:{purpose}",
            builder=lambda: self._build_text_model(purpose),
        )

    def vision_model(self) -> VisionModel:
        return self._cached(key="vision", builder=self._build_vision_model)

    def image_model(self) -> ImageModel:
        return self._cached(key="image", builder=self._build_image_model)

    # -- construtores internos, únicos pontos que conhecem o SDK concreto --
    def _build_text_model(self, purpose: str) -> TextModel: ...
    def _build_vision_model(self) -> VisionModel: ...
    def _build_image_model(self) -> ImageModel: ...

    def _cached(self, key: str, builder):
        if key not in self._cache:
            self._cache[key] = builder()
        return self._cache[key]


def get_llm_factory() -> LLMClientFactory:
    """Ponto único de acesso, injetado nos nós do carrossel."""
    return LLMClientFactory()
```

### 3.3 Injeção de dependência nos nós

Os nós do grafo de carrossel **nunca** instanciam a Factory diretamente dentro da função do nó — isso dificultaria testes com mocks. Em vez disso, a Factory (ou os três clientes já resolvidos) é fechada em contexto no momento da construção do grafo, via `functools.partial` ou fábrica de nós:

```python
# backend/carousel_nodes.py
from functools import partial
from backend.llm import get_llm_factory

def make_prompt_designer_node(llm_factory=None):
    llm_factory = llm_factory or get_llm_factory()
    text_model = llm_factory.text_model(purpose="lightweight")

    def prompt_designer(state: CarouselState) -> dict:
        # usa text_model.generate_structured(...) — nunca instancia SDK aqui
        ...

    return prompt_designer
```

Isso permite, em testes (`test_graph_routing.py`, `test_copy_fidelity.py`), injetar um `FakeLLMFactory` inteiro sem tocar em `config.py` ou em segredos reais — mantendo a filosofia de modo `--dry-run`/`--mock` do documento original.

### 3.4 Regras de configuração

- Nenhuma chave de API é lida por `os.environ` dentro de `backend/carousel_*`. Toda leitura de credencial passa por `config.get_settings()` e é resolvida dentro dos construtores privados da Factory.
- Se o carrossel precisar de um parâmetro de configuração que `config.py` ainda não expõe (por exemplo, `IMAGE_MODEL_PROVIDER` ou `CAROUSEL_MAX_REVISIONS`), a extensão é feita **em `config.py`**, como novos campos opcionais com valor padrão, nunca redefinindo campos existentes. Essa extensão deve ser o único ponto de contato do módulo de carrossel com `config.py`.
- Tokens, latência e custo de cada chamada são registrados pelo nó chamador (não pela Factory), para manter a Factory livre de estado de execução e reaproveitável entre threads concorrentes.

---

## 4. Resiliência — rate limits e degradação graciosa

### 4.1 Escopo

Esta seção aplica-se principalmente ao nó `generate_visual_assets`, que depende de uma API de geração de imagem sujeita a *throttling*, mas o padrão de retry/timeout deve ser o mesmo padrão usado por `text_model` e `vision_model`, para consistência.

### 4.2 Estratégia de retry

```python
# backend/carousel_resilience.py
import time
import random
import logging

logger = logging.getLogger("carousel.resilience")

class RateLimitedError(Exception):
    """Erro específico para HTTP 429, distinto de erros irrecuperáveis."""

def call_with_backoff(
    fn,
    *args,
    max_attempts: int = 4,
    base_delay: float = 1.5,
    max_delay: float = 20.0,
    retriable_exceptions=(RateLimitedError, TimeoutError, ConnectionError),
    **kwargs,
):
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except retriable_exceptions as exc:
            attempt += 1
            if attempt >= max_attempts:
                logger.warning(
                    "Esgotadas %s tentativas para %s: %s",
                    attempt, getattr(fn, "__name__", fn), exc,
                )
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.25)  # jitter
            logger.info(
                "Tentativa %s falhou (%s). Retentando em %.1fs.",
                attempt, exc, delay,
            )
            time.sleep(delay)
```

O adaptador `ImageModel` concreto (dentro de `backend/llm.py`) deve traduzir o HTTP 429 do provedor para `RateLimitedError`, preservando o cabeçalho `Retry-After` quando disponível e respeitando-o como piso do próximo `delay`.

### 4.3 Degradação graciosa no nó `generate_visual_assets`

```python
# backend/carousel_nodes.py (trecho)
from backend.carousel_resilience import call_with_backoff, RateLimitedError

def make_generate_visual_assets_node(llm_factory=None):
    llm_factory = llm_factory or get_llm_factory()
    image_model = llm_factory.image_model()

    def generate_visual_assets(state: CarouselState) -> dict:
        asset_results = []
        degraded_slides = []

        for slide in state["design_plan"]["slides"]:
            if not slide["image_brief"]["required"]:
                asset_results.append({"slide_id": slide["slide_id"], "asset_path": None, "degraded": False})
                continue

            try:
                image_bytes = call_with_backoff(
                    image_model.generate,
                    slide["image_prompt"],
                    width=state["canvas"]["width"],
                    height=state["canvas"]["height"],
                    max_attempts=4,
                )
                path = _persist_asset(state, slide["slide_id"], image_bytes)
                asset_results.append({"slide_id": slide["slide_id"], "asset_path": path, "degraded": False})

            except RateLimitedError as exc:
                logger.error("Falha definitiva de geração visual no slide %s: %s", slide["slide_id"], exc)
                asset_results.append({
                    "slide_id": slide["slide_id"],
                    "asset_path": None,
                    "degraded": True,
                    "degradation_reason": "rate_limited_after_retries",
                })
                degraded_slides.append(slide["slide_id"])

            except Exception as exc:  # erro irrecuperável do provedor
                logger.exception("Erro não recuperável na geração visual do slide %s", slide["slide_id"])
                asset_results.append({
                    "slide_id": slide["slide_id"],
                    "asset_path": None,
                    "degraded": True,
                    "degradation_reason": f"provider_error:{type(exc).__name__}",
                })
                degraded_slides.append(slide["slide_id"])

        return {
            "asset_results": asset_results,
            "degraded_slides": degraded_slides,
        }

    return generate_visual_assets
```

Regras obrigatórias de degradação:

1. Uma falha de geração de imagem **nunca** interrompe o grafo. O nó sempre retorna um `asset_results` completo, com um registro por slide, marcando `degraded: true` onde aplicável.
2. `compose_slides` deve tratar `asset_path: null` como sinal explícito para renderizar uma **composição puramente tipográfica** para aquele slide — ou seja, usar apenas os tokens de cor de fundo (`bg_paper`, `bg_warm_paper`, `bg_dark_notepad`), tipografia e componentes geométricos (divisor, checklist, grifo, topo Notes), sem área de imagem. Isso está alinhado à separação de camadas definida na especificação original (texto/tokens no compositor determinístico; fotografia/ilustração apenas na API de imagem).
3. Toda ocorrência de degradação é registrada no `manifest.json` (Seção 4.4), nunca silenciada.
4. `quality_gate` não deve tratar `degraded: true` isoladamente como falha crítica — a degradação é uma condição esperada e recuperável, não um erro de qualidade de conteúdo. O `visual_validator`, porém, deve sinalizar como `warning` (não `critical_failure`) quando a densidade de slides degradados comprometer a consistência visual do conjunto (por exemplo, mais de 40% dos slides sem asset visual), permitindo que `quality_gate` encaminhe para `human_review` nesse cenário específico.

### 4.4 Registro no manifest

```json
{
  "visual_generation": {
    "provider": "…",
    "total_slides_with_image_required": 5,
    "successful": 4,
    "degraded": 1,
    "degraded_details": [
      {
        "slide_id": 3,
        "reason": "rate_limited_after_retries",
        "attempts": 4,
        "fallback_applied": "typographic_only_composition"
      }
    ]
  }
}
```

---

## 5. Estado assíncrono e acompanhamento por polling

### 5.1 Motivação

O pipeline multimodal (planejamento + direção de arte + geração de imagem + composição + validação) pode levar dezenas de segundos a minutos por execução. `app.py` não deve bloquear a UI enquanto o grafo roda — isso vale tanto para uma execução isolada quanto para o caso de aprovação humana no meio do fluxo (Seção 10 do documento original), em que o processo pode ficar pausado por tempo indefinido.

### 5.2 Modelo de execução

1. Ao receber uma solicitação de carrossel, `app.py` **não invoca o grafo de forma síncrona no mesmo request/thread da UI**. Em vez disso:
   - gera um `thread_id` (UUID) estável;
   - grava uma linha inicial de job na tabela de execuções (Seção 5.3), com status `queued`;
   - despacha a execução do grafo (`backend/carousel_graph.py`) em um worker separado — thread em background, processo, ou fila de tarefas (Celery/RQ/`concurrent.futures`, a depender do que já existe ou é aceitável no ambiente de deploy do CopyWriter; se nada estiver disponível, o padrão mínimo aceitável é `concurrent.futures.ThreadPoolExecutor` com um worker dedicado, documentando a limitação de escala no README);
   - retorna imediatamente o `thread_id` para a UI.
2. O worker invoca `graph.invoke(inputs, config={"configurable": {"thread_id": thread_id}})` (ou `.stream(...)` se o time preferir progresso incremental) usando o checkpointer persistente configurado na Seção 5.4.
3. A cada transição relevante de nó (ao menos ao final de `plan_carousel`, `generate_visual_assets`, `compose_slides`, `quality_gate`), o worker atualiza a linha de job com o nó atual, um payload de progresso resumido e, quando aplicável, o motivo de uma pausa para aprovação humana.
4. Quando o grafo chega a um ponto de `human_review` (roteamento condicional do `quality_gate` para `END`, conforme Seção 2.1), o job muda para status `awaiting_approval` e a execução do grafo termina normalmente (o checkpoint persistido é o que permite retomar depois, sem reprocessar nós já concluídos).
5. Uma ação de aprovação do usuário (`approve`, `request_revision`, `cancel`) dispara uma nova invocação do grafo com o **mesmo** `thread_id`, retomando do checkpoint, nunca do zero.

### 5.3 Persistência de `thread_id` em banco de dados

Estrutura mínima da tabela `carousel_jobs` (pode ser SQLite local, reaproveitando o que `config.py` já apontar como banco do projeto, ou uma tabela nova em um banco já existente do CopyWriter — não introduzir um novo motor de banco de dados só para isso):

| Coluna | Tipo | Descrição |
|---|---|---|
| `thread_id` | `TEXT PRIMARY KEY` | Identificador estável usado também como `thread_id` do checkpointer do LangGraph |
| `status` | `TEXT` | `queued` \| `running` \| `awaiting_approval` \| `completed` \| `failed` \| `cancelled` |
| `current_node` | `TEXT` | Último nó concluído, para exibição de progresso |
| `progress_summary` | `TEXT (JSON)` | Resumo seguro do estado (sem segredos), usado pelo polling |
| `manifest_path` | `TEXT` | Caminho do `manifest.json`, preenchido ao final |
| `created_at` / `updated_at` | `DATETIME` | Auditoria |
| `error_message` | `TEXT` | Preenchido apenas em `failed`, mensagem segura (sem stack trace bruto exposto na UI) |

```python
# backend/carousel_jobs.py
import sqlite3
import json
import uuid
from datetime import datetime, timezone

def create_job(conn: sqlite3.Connection) -> str:
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO carousel_jobs
           (thread_id, status, current_node, progress_summary, created_at, updated_at)
           VALUES (?, 'queued', NULL, '{}', ?, ?)""",
        (thread_id, now, now),
    )
    conn.commit()
    return thread_id

def update_job(conn: sqlite3.Connection, thread_id: str, **fields) -> None:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "progress_summary" in fields and not isinstance(fields["progress_summary"], str):
        fields["progress_summary"] = json.dumps(fields["progress_summary"])
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE carousel_jobs SET {set_clause} WHERE thread_id = ?",
        (*fields.values(), thread_id),
    )
    conn.commit()

def get_job(conn: sqlite3.Connection, thread_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM carousel_jobs WHERE thread_id = ?", (thread_id,)
    ).fetchone()
    return dict(row) if row else None
```

### 5.4 Checkpointer

Para desenvolvimento local, use `SqliteSaver` (ou `InMemorySaver` em testes) do próprio LangGraph, apontando para um arquivo dedicado (ex.: `data/carousel_checkpoints.sqlite`), independente da tabela `carousel_jobs` — uma guarda o *snapshot* de estado do grafo (usado pelo LangGraph para retomar), a outra guarda o *status de negócio* consultado pela UI. Para produção, o time pode evoluir para um checkpointer compatível com o banco já usado pelo CopyWriter, se houver um adaptador oficial do LangGraph para ele; caso não haja, documentar essa limitação no README e manter o SQLite como padrão até uma migração futura.

### 5.5 Padrão de polling no frontend

`app.py` deve expor (ou reaproveitar, se o CopyWriter já tiver algo equivalente) um pequeno endpoint/função de consulta de status, chamado pela UI em intervalo curto (ex.: 2–3 segundos) enquanto o status não for terminal:

```python
# app.py (trecho de orquestração, ilustrativo)
def start_carousel_job(payload: dict) -> str:
    thread_id = carousel_jobs.create_job(db_conn)
    executor.submit(_run_carousel_graph_background, thread_id, payload)
    return thread_id

def get_carousel_job_status(thread_id: str) -> dict:
    return carousel_jobs.get_job(db_conn, thread_id)
```

No `frontend/ui_results.py` (Seção 6.2), o polling deve:

- parar assim que o status for `completed`, `failed` ou `cancelled`;
- exibir uma barra ou indicador de etapa atual com base em `current_node`, mapeando nomes técnicos de nó para rótulos amigáveis (“Planejando estrutura”, “Definindo direção de arte”, “Gerando elementos visuais”, “Compondo slides”, “Validando qualidade”);
- quando `status == "awaiting_approval"`, renderizar a tela de aprovação humana descrita na Seção 6.2, em vez de continuar o polling silencioso.

---

## 6. Evolução da interface

### 6.1 `frontend/ui_form.py`

Adicionar, como uma seção nova e claramente demarcada do formulário (não misturada aos campos existentes do fluxo de copy), os campos exigidos pelo contrato de entrada da especificação original (Seção 5 do documento v1):

- Fonte da copy: reutilizar a copy já gerada na sessão atual do CopyWriter **ou** permitir colar/editar uma copy própria para o carrossel.
- Marca: nome da autora/marca, identificador (`@handle`), avatar (opcional), selo de verificado (opcional), tom de voz (com valor padrão pré-preenchido conforme a especificação de identidade visual).
- Público-alvo (opcional).
- Objetivo do carrossel: seleção entre `educar`, `diagnosticar`, `gerar salvamentos`, `gerar comentários`, `conversão`.
- Quantidade de slides: campo de faixa (`min`/`max`) mais um campo opcional de quantidade preferida; se vazio, o sistema infere conforme a Seção 1 do documento original.
- Preferências visuais: incluir fotos (sim/não), estilo de imagem (texto livre com sugestão padrão “fotografia editorial orgânica”), permitir reescrita de copy para condensação (sim/não, com padrão não).
- Exigir aprovação humana: alternância (sim/não).
- Diretório de saída: campo avançado, com padrão já sensato, oculto por padrão.

O formulário deve validar client-side os campos obrigatórios mínimos (copy não vazia, `min ≤ max`, `min ≥ 1`) antes de habilitar o botão de geração, mas a validação de contrato completo (Pydantic) ocorre no backend, como de costume.

### 6.2 `frontend/ui_results.py`

Adicionar três estados de renderização, todos condicionados ao `status` retornado pelo polling (Seção 5.5):

1. **Em andamento** (`queued`, `running`): indicador de progresso com o nó atual traduzido para linguagem amigável, sem bloquear o restante da interface do CopyWriter (o usuário deve poder navegar para outras abas/telas enquanto aguarda).
2. **Aguardando aprovação humana** (`awaiting_approval`): tela dedicada mostrando:
   - resumo do plano editorial atual (`carousel_plan`) ou a prévia de contato dos slides já compostos, dependendo de em qual checkpoint a pausa ocorreu;
   - lista de decisões relevantes tomadas até aqui (modo claro/escuro por slide, reescritas de copy registradas em `rewrite_log`, slides com degradação visual);
   - três ações explícitas: `Aprovar`, `Solicitar revisão` (com campo de texto livre para instruções) e `Cancelar`, mapeadas para uma nova invocação do grafo com o mesmo `thread_id` (Seção 5.2, passo 5).
3. **Concluído** (`completed`): grade de cards visuais, um por slide, na ordem final, com:
   - miniatura de cada slide (o arquivo individual gerado, respeitando a degradação tipográfica quando aplicável, sem tratamento diferenciado na UI — a degradação já foi resolvida visualmente pelo compositor);
   - indicador discreto (ícone ou selo) nos slides que sofreram degradação de asset visual, com tooltip explicando a causa, para transparência com o usuário;
   - acesso ao `manifest.json`, ao relatório de validação e à prévia de contato, como downloads/links, reaproveitando o padrão visual já usado por `ui_historico.py` para artefatos de execuções passadas;
   - opção de reenviar para nova rodada de geração (novo `thread_id`) a partir do mesmo plano, caso o usuário queira apenas regenerar assets visuais específicos.

Em caso de `status == "failed"`, exibir uma mensagem segura (sem stack trace) com o `error_message` registrado no job, e um botão para tentar novamente do zero.

---

## 7. Contratos reaproveitados sem alteração

As seções a seguir do documento original **permanecem válidas integralmente** e devem ser implementadas dentro de `backend/carousel_*` exatamente como descrito, apenas trocando o local de implementação:

- Seção 2 (Referência visual obrigatória — tokens de cor, tipografia, grid e composição);
- Seção 3 (Princípios de direção de conteúdo);
- Seção 5 (Contrato de entrada, adaptado apenas para remover o bloco `providers`, já que a escolha de provedor passa a ser resolvida pela Factory de `backend/llm.py` e por `config.py`, não por campos do próprio payload de entrada — a não ser que o time queira permitir override pontual por execução, caso em que o campo pode ser mantido como opcional e repassado à Factory como parâmetro de `purpose`/preferência);
- Seção 6 (Contrato de saída do planejamento);
- Seção 7 (Contrato dos prompts visuais);
- Seção 8 (Adaptadores de API — as interfaces `TextModel`, `VisionModel`, `ImageModel` são as mesmas; o que muda é apenas onde são construídas, conforme Seção 3 deste documento);
- Seção 9 (Validação e critérios de aceitação, rubrica de 0–100 e schema de saída do validador);
- Seção 10 (Aprovação humana — cujo mecanismo de pausa/retomada agora é concretizado pela infraestrutura da Seção 5 deste documento).

---

## 8. Estrutura final de arquivos dentro do `CopyWriter`

```text
CopyWriter/
├── app.py                        # + orquestração assíncrona de jobs de carrossel
├── config.py                      # + campos opcionais de configuração do carrossel
├── data/
│   └── carousel_checkpoints.sqlite   # checkpointer do LangGraph (novo)
├── backend/
│   ├── llm.py                      # + LLMClientFactory (aditivo)
│   ├── rag.py                       # inalterado (reaproveitado por leitura, se necessário)
│   ├── graph.py                      # INALTERADO
│   ├── carousel_graph.py              # novo — grafo do carrossel
│   ├── carousel_state.py               # novo — estado tipado do carrossel
│   ├── carousel_nodes.py                # novo — implementação dos 11 nós (ou pacote carousel/)
│   ├── carousel_resilience.py            # novo — retry/backoff/rate-limit
│   ├── carousel_jobs.py                   # novo — persistência de thread_id/status
│   └── carousel_render/                    # novo — compositor determinístico
│       ├── tokens.py
│       ├── components.py
│       ├── typography.py
│       └── compositor.py
├── frontend/
│   ├── ui_form.py                  # + seção de entrada do carrossel
│   ├── ui_historico.py              # + listagem de execuções de carrossel (opcional, ver Seção 9)
│   └── ui_results.py                 # + três estados de renderização (Seção 6.2)
└── tests/
    ├── test_carousel_graph_routing.py
    ├── test_carousel_copy_fidelity.py
    ├── test_carousel_layout_overflow.py
    ├── test_carousel_resilience.py
    ├── test_carousel_jobs.py
    └── fixtures/carousel/
```

---

## 9. Passos de refatoração segura

O agente de desenvolvimento deve seguir esta ordem, cada etapa com testes de regressão do pipeline de copy existente executados **antes de avançar para a próxima**:

1. **Baseline**: rodar a suíte de testes atual do CopyWriter (se existir) e registrar o resultado como referência de não-regressão.
2. **Extensão de `config.py`**: adicionar apenas campos novos e opcionais (com valor padrão), nunca renomear ou remover campos existentes. Rodar baseline novamente.
3. **Factory em `backend/llm.py`**: adicionar `LLMClientFactory` e as interfaces `TextModel`/`VisionModel`/`ImageModel` como código novo no mesmo arquivo (ou, se o time preferir isolamento maior, em `backend/llm_factory.py`, importado por `llm.py` para manter um único ponto público). Nenhuma função ou classe existente é removida ou tem sua assinatura alterada. Rodar baseline novamente.
4. **Novo grafo isolado**: implementar `backend/carousel_state.py`, `backend/carousel_nodes.py` e `backend/carousel_graph.py` de forma independente, com testes próprios (`--dry-run`/`--mock`, conforme filosofia do documento original), sem qualquer integração com `app.py` ainda. Rodar baseline novamente.
5. **Compositor determinístico**: implementar `backend/carousel_render/` e validar isoladamente com fixtures de copy sintética, sem depender de API de imagem real (modo `--mock`).
6. **Resiliência**: implementar `carousel_resilience.py` e testar cenários de 429 simulados com um `ImageModel` falso.
7. **Persistência assíncrona**: implementar `carousel_jobs.py` e a tabela `carousel_jobs`, com testes unitários de transição de estado, ainda sem integração com `app.py`.
8. **Integração em `app.py`**: adicionar a orquestração de despacho assíncrono e consulta de status, como funções novas, sem alterar o fluxo de rota/comando já existente para geração de copy. Rodar baseline novamente.
9. **Evolução de UI**: estender `ui_form.py` e `ui_results.py` conforme Seção 6, mantendo o fluxo de copy existente 100% funcional e visualmente inalterado para quem não usa o carrossel.
10. **Fluxo completo em modo mock**: executar ao menos uma geração completa de carrossel em `--mock`, verificando manifest, arquivos individuais de slide, fidelidade de copy crítica e o caminho de `quality_gate` para `human_review` com um caso propositalmente inválido — replicando a exigência de validação final do documento original, agora dentro do contexto do CopyWriter.
11. **Rodada final de regressão**: rodar baseline do CopyWriter mais uma vez, garantindo zero impacto no pipeline de copy original.

Cada etapa deve ser um commit (ou conjunto pequeno de commits) isolado e reversível, com a hipótese de design correspondente registrada no `README.md`, conforme a instrução de uso geral desta especificação.

---

## 10. Observações de implementação

A filosofia determinística e de validação agentica do documento original é preservada integralmente: a sequência principal do grafo continua previsível e auditável, os nós de análise, direção de arte e validação continuam usando modelos para lidar com ambiguidade, e a separação entre camada de geração visual (API de imagem) e camada de composição determinística (texto exato, tokens, tipografia) continua sendo o ponto central da identidade visual da marca.

O que esta versão 2.0 adiciona é disciplina de integração: o novo pipeline se comporta como um **hóspede bem-comportado** dentro do CopyWriter — reaproveita credenciais e convenções existentes, não modifica o que já funciona, é resiliente a falhas de provedores externos sem quebrar o restante do sistema, e expõe seu progresso de forma assíncrona e não bloqueante, de um jeito que poderia, no futuro, ser generalizado para o próprio pipeline de copy caso o time deseje.

Se houver conflito entre uma conveniência de implementação e o isolamento do grafo existente (Seção 2), o isolamento vence. Se houver conflito entre velocidade de entrega e a extração de utilitários compartilhados (Seção 2.1, item 4), adie a extração — duplicar um pequeno trecho de código é preferível a acoplar dois grafos em produção.

## Referências

Esta especificação herda as referências normativas do documento original (guia de identidade visual, documentação de `StateGraph`, persistência e workflows do LangGraph) — consulte o documento v1 (`carrossel_metaprompt_especificacao.md`) para os links completos.
