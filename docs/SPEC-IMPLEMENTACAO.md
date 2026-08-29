# SPEC de implementação consolidada — Carrossel visual

Documento **autoritativo**. Consolida quatro fontes que se contradizem em pontos concretos e
registra a resolução de cada contradição. Onde este documento diverge de uma fonte, ele vence.

---

## 1. Documentos-fonte e precedência

| # | Documento | Papel |
|---|---|---|
| 1 | **Este arquivo** | Resolve contradições. Precedência máxima. |
| 2 | `carrossel_metaprompt_especificacao_v2.md` | Integração no CopyWriter (isolamento, Factory, resiliência, jobs, UI) |
| 3 | `carrossel_metaprompt_especificacao.md` (v1) | Contratos de conteúdo, planejamento, prompts visuais, rubrica |
| 4 | `Especificação de Identidade Visual e Design UI.md` | Tokens, tipografia, componentes, grid |
| 5 | `SPEC-formulario-canais.md` | Fase 1, independente. Continua válida como está. |

A v2 **não substitui** o v1: ela move o *onde* implementar. O documento de identidade é a fonte
normativa da Seção 2 do v1.

> **Não busque a URL de referência do v1** (`boutiqueempresarial.com.br/identidade-visual.html`).
> A identidade local é a fonte normativa. Nenhum nó faz requisição de rede para obter regra visual.

---

## 2. Decisões consolidadas

Cada linha resolve uma contradição real entre as fontes ou entre uma fonte e o código.

| # | Questão | Decisão |
|---|---|---|
| D1 | Proporção dos slides | **4:5 — 1080×1350**. Confirmado pelo v1 §2 (canvas padrão recomendado) e pela identidade (“formato retrato 4:5”). O prompt em produção diz 1:1 → **corrigir**. |
| D2 | v2 exige `graph.py` INALTERADO, mas a Fase 1 o altera | A regra da v2 é sobre **o diff do pipeline de imagem**, não um congelamento do arquivo. A Fase 1 é diff separado, sobre seleção de canais. Não conflitam. |
| D3 | Como reaproveitar a copy validada | `geracao_carrossel` (já em produção, roda após o crítico) entrega `copy_por_canal["carrossel"]`. `app.py` passa esse dict como entrada de `ingest_copy`. **Zero acoplamento de estado entre os dois grafos.** |
| D4 | `config.get_settings()` não existe | Adicionar `Settings` + `get_settings()` a `config.py` de forma **aditiva**. As constantes de módulo permanecem — `llm.py` e `rag.py` as importam diretamente. |
| D5 | v1 §8 pressupõe `OPENAI_API_KEY`, `TEXT_MODEL_PROVIDER` etc. | O projeto é Gemini. A Factory resolve os três modelos a partir de `config.py`. **Nenhuma variável de ambiente nova** é lida dentro de `backend/carousel_*`. O bloco `providers` do contrato de entrada (v1 §5) é removido — autorizado pela v2 §7. |
| D6 | DM Serif Display não tem Bold | A família só tem Regular e Italic. Onde a identidade pede **Serifada Bold 700**, usar **DM Serif Display Regular** — é uma display de alto contraste que já lê como peso forte em tamanho grande. **Proibido bold sintético** (traço artificial), que destrói a modulação da serifada. Registrar como exceção no README, conforme v1 manda. |
| D7 | Onde ficam as fontes | Mover `docs/DM_Serif_Display/` e `docs/Inter/` para **`assets/fonts/`** — são asset de runtime, não documentação. Manter os `OFL.txt` junto. |
| D8 | Escala tipográfica no canvas | Derivada, não arbitrada. Ver §5.2. |
| D9 | Modelo assíncrono da v2 pressupõe request/response | O Streamlit não tem rotas e **thread de fundo perde o `ScriptRunContext`**. O worker **nunca** chama API do Streamlit: escreve só na tabela `carousel_jobs`. A UI faz polling lendo o SQLite e se redesenha com `st.rerun()` temporizado. |
| D10 | CLI do v1 §12 | **Adiada.** A v2 define o Streamlit como superfície de entrega. Os modos `--dry-run`/`--mock` permanecem, como modos de teste (`pytest`), não como CLI pública. |
| D11 | Faixa de slides | v1 sugere 5–8; o formulário em produção usa **5–10**. Mantém 5–10 — o v1 declara a faixa configurável. |
| D12 | Ponte Pomelli (PR #1) | **Permanece**, como caminho manual alternativo. Não é substituída pela geração de imagem. |

---

## 3. Regras invioláveis

1. `backend/carousel_*` **não importa** `backend/graph.py`, e vice-versa. Grafos compilados de forma independente.
2. A suíte existente (`pytest tests/ -q`) precisa passar **antes e depois de cada etapa**. É a linha de base de não-regressão.
3. **A copy é fonte de verdade.** Números, nomes próprios, datas, termos técnicos, promessas e negações não podem ser alterados sem registro em `rewrite_log`.
4. **Texto exato nunca é renderizado pela API de imagem.** A API gera fotografia/ilustração/textura; o compositor determinístico desenha texto, tokens, grifos, checklists, divisores e o topo Notes.
5. Nenhuma chave de API é lida por `os.environ` dentro de `backend/carousel_*`. Tudo passa pela Factory.
6. Falha de geração de imagem **nunca** interrompe o grafo — degrada para composição tipográfica e registra no manifest.
7. Em conflito entre estética e legibilidade, **legibilidade vence**. Em conflito entre sugestão do modelo e a copy, **a copy vence**.

---

## 4. Fase 0 — Pré-requisitos

Sem esta fase o código de exemplo da v2 não roda e o compositor não tem tipografia.

### 4.1 `config.py` — extensão aditiva

Manter todas as constantes atuais. Acrescentar:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    """Configuração tipada. As constantes de módulo acima permanecem como estão —
    llm.py e rag.py as importam diretamente e não podem quebrar."""
    google_api_key: str = GOOGLE_API_KEY
    text_model: str = GEMINI_MODEL
    text_model_reasoning: str = "gemini-2.5-flash"     # julgamento ambíguo
    vision_model: str = "gemini-2.5-flash"             # validação multimodal
    image_model: str = "gemini-2.5-flash-image"        # geração de asset visual
    temperature: float = TEMPERATURE
    embedding_model: str = EMBEDDING_MODEL
    chroma_path: str = CHROMA_PATH
    db_path: str = DB_PATH
    # Carrossel
    carousel_max_revisions: int = 2
    carousel_output_dir: str = "./outputs/carrosseis"
    carousel_checkpoints: str = "./data/carousel_checkpoints.sqlite"
    fonts_dir: str = "./assets/fonts"


def get_settings() -> Settings:
    return Settings()
```

> O id do modelo de imagem é **configuração, não verdade universal** (v1 §8). Validar na primeira
> execução real e registrar no README o que respondeu.

### 4.2 Dependências

```diff
  langchain-text-splitters
  python-dotenv
  pypdf
  python-docx
  pytest
- google-generativeai
+ langgraph-checkpoint-sqlite
+ pillow
```

`google-generativeai` é o SDK antigo: **não está instalado e não é importado em lugar nenhum**.
O stack real usa `google-genai`, que vem via `langchain-google-genai`. Pillow já está presente,
mas só transitivamente pelo Streamlit — precisa ser declarado.

### 4.3 Fontes

```bash
mkdir -p assets/fonts
git mv docs/DM_Serif_Display assets/fonts/DM_Serif_Display
git mv docs/Inter            assets/fonts/Inter
```

**Verificação obrigatória** (a acentuação pt-BR é o risco real):

```bash
python3 -c "
from PIL import ImageFont
t='Ação estratégica: não é só ânimo — é método'
for f in ['assets/fonts/DM_Serif_Display/DMSerifDisplay-Regular.ttf',
          'assets/fonts/DM_Serif_Display/DMSerifDisplay-Italic.ttf',
          'assets/fonts/Inter/static/Inter_18pt-Regular.ttf',
          'assets/fonts/Inter/static/Inter_18pt-SemiBold.ttf']:
    ft = ImageFont.truetype(f, 32)
    faltando = [c for c in set(t) if c.strip() and ft.getmask(c).getbbox() is None]
    assert not faltando, (f, faltando)
print('fontes OK, sem glifo ausente')
"
```

---

## 5. Fase 2 — Identidade como módulo determinístico

`backend/carousel_render/`. Testável isoladamente, **sem nenhuma chamada a API de imagem**.
Entrega valor sozinha: já produz slides tipográficos na identidade correta — que é exatamente o
caminho de degradação exigido pela v2 §4.3.

### 5.1 `tokens.py` — valores exatos

```python
CANVAS = {"width": 1080, "height": 1350, "format": "png", "quality": 95}
MARGEM = 80          # múltiplo de 8
CONTENT_W = 920      # 1080 - 2*80

CORES = {
    "bg_paper":          "#FFFFFF",
    "bg_warm_paper":     "#FBFAF7",
    "bg_dark_notepad":   "#121212",
    "text_ink_primary":  "#111522",
    "text_ink_muted":    "#92949B",
    "text_dark_primary": "#F5F5F7",
    "accent_amber":      "#EAA034",
    "highlight_caramel": "#9E7138",   # aplicar a ~60% de opacidade
    "highlight_pin":     "#E7D6C2",
    "verified_cyan":     "#13C4E5",   # exclusivo do selo
    "check_green":       "#5C9E31",
}
HIGHLIGHT_OPACITY = 0.60
```

Estes valores são **constantes aplicadas literalmente**. Não indexe a identidade no Chroma: os
tokens são exatos, e recuperação por similaridade é a ferramenta errada para constante.

### 5.2 `typography.py` — escala derivada, não arbitrada

A identidade define um container de leitura de 680–760 px. Adotando 720 px como referência e
920 px de conteúdo no canvas, o fator é `920 / 720 = 1,278`. Cada tamanho é arredondado ao
múltiplo de 8 mais próximo, conforme o grid da identidade.

| Elemento | Família | Peso | Ref. | **Canvas** |
|---|---|---|---:|---:|
| Nome da autora | DM Serif Display | Regular *(ver D6)* | 32 | **40** |
| Identificador @ | Inter | Regular 400 | 16 | **24** |
| Título principal | DM Serif Display | Regular | 60 | **80** |
| Diagnóstico | DM Serif Display | Regular *(ver D6)* | 32 | **40** |
| Checklist (dor) | DM Serif Display | Regular | 24 | **32** |
| Checklist (método) | DM Serif Display | **Italic** | 24 | **32** |
| Interface Notes | Inter | SemiBold 600 | 18 | **24** |

Entrelinha 1,15 para títulos, 1,40 para corpo. Espaçamento entre seções 96–152 px, entre título e
parágrafo 48–72 px (a régua 80–120 / 40–56 da identidade × 1,278, no grid de 8).

Arquivos: `DMSerifDisplay-Regular.ttf`, `DMSerifDisplay-Italic.ttf`, `Inter_18pt-Regular.ttf`,
`Inter_18pt-SemiBold.ttf`. **Nunca** cair em fonte de sistema — se um TTF não carregar, é erro
duro, não fallback silencioso.

Validado por medição: uma headline de 80 caracteres em pt-BR quebra em 4 linhas ocupando 368 px,
dentro da área de título.

### 5.3 `components.py` — os elementos de assinatura

Funções de desenho Pillow, uma por componente, cada uma testável por dimensão e cor:

- `author_header` — avatar circular 1:1 (48–64 px × 1,278 → **64–80 px**), nome + selo, @handle abaixo em `text_ink_muted`
- `verified_badge` — roseta em `verified_cyan` com check branco, imediatamente após o nome
- `ios_highlight` — caixa em `highlight_caramel` a 60%, com dois pinos em `highlight_pin`: superior-esquerdo e inferior-direito do trecho
- `notes_header` — chevron `<` + “Notas” à esquerda, reticências à direita, ambos em `accent_amber`. **Só existe no modo escuro**
- `editorial_divider` — linha sólida 3–4 px × 1,278 → **4–5 px**, largura 96–120 px × 1,278 → **123–153 px**, alinhada à esquerda, nunca largura total
- `checklist_pain` — marcador quadrado arredondado em `check_green` com check branco, serifada Regular
- `checklist_method` — marcador textual `[ ]` em cinza/âmbar, serifada **Itálica**

### 5.4 `compositor.py` — layout

Alinhamento à esquerda como padrão ouro. Grid de 8 px. Quebra de linha, medição e paginação
determinísticas. Recebe `exact_copy` e o desenha **literalmente** — nenhuma reescrita nesta camada.

`asset_path: None` → composição puramente tipográfica, usando só fundo, tipografia e componentes
geométricos. É o caminho normal de degradação, não um erro.

### 5.5 Vocabulário para os agentes

Além das constantes, um bloco de texto condensado — em `data/prompts.py` — injetado **apenas** nos
prompts de `art_director` e `prompt_designer`. Nunca no contexto geral: email, VSL e ads não pagam
tokens de vocabulário visual que não usam.

Conteúdo: a dualidade Fachada Editorial (claro: diagnóstico, autoridade, dor) × Bastidores
(escuro: método, execução, etapas); a personalidade da marca (inteligente, direta, acolhedora,
elegante, prática, sem jargão); e os *don'ts* que importam para geração de imagem — sem gradiente,
sem sombra pesada, sem borda em pílula, sem estética de banco de imagens, foto real e orgânica com
recorte limpo.

---

## 6. Fase 3 — Pipeline de imagem

Onze nós em `backend/carousel_graph.py`, conforme v2 §2.1. Contratos de conteúdo, planejamento,
prompts visuais e rubrica **exatamente como no v1** §§3, 5–7 e 9, com as três correções de D5, D10
e D11.

### 6.1 Entrada — a passagem de bastão

```python
# app.py — orquestração, FORA de qualquer grafo
carrossel = st.session_state.final_copy.get("carrossel", {})   # já aprovado pelo crítico
payload = {
    "copy": "\n\n".join(s["texto_slide"] for s in carrossel.get("slides", [])),
    "brand": {...},                                   # do formulário
    "slides": {"min": 5, "max": 10, "preferred": len(carrossel.get("slides", []))},
    "canvas": CANVAS,
    "visual_preferences": {
        # a direção de arte já validada no PR #1 entra como semente
        "image_style": carrossel.get("estilo_visual_global", "fotografia editorial orgânica"),
        "slide_hints": [s.get("prompt_visual_pomelli", "") for s in carrossel.get("slides", [])],
        "include_photos": True,
        "allow_copy_rewrite": False,
    },
    "execution": {...},
}
thread_id = start_carousel_job(payload)
```

`estilo_visual_global` e `prompt_visual_pomelli` deixam de ser só texto para colar e viram
**semente** do `art_director` e do `prompt_designer`. É o “aproveitar os textos já validados”.

### 6.2 Adaptação do modelo assíncrono ao Streamlit (D9)

```python
# worker — roda em ThreadPoolExecutor, NUNCA chama st.*
def _run_carousel_graph_background(thread_id, payload):
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    try:
        update_job(conn, thread_id, status="running")
        graph = build_carousel_graph(SqliteSaver.from_conn_string(settings.carousel_checkpoints))
        for evento in graph.stream(payload, config={"configurable": {"thread_id": thread_id}}):
            for no in evento:
                update_job(conn, thread_id, current_node=no)   # só escrita em SQLite
        update_job(conn, thread_id, status="completed")
    except Exception as exc:
        update_job(conn, thread_id, status="failed", error_message=str(exc)[:500])
```

Na UI, o polling é redesenho, não requisição:

```python
job = get_job(conn, thread_id)
if job["status"] in ("queued", "running"):
    st.progress(...)                       # rótulo amigável a partir de current_node
    time.sleep(2); st.rerun()
```

`check_same_thread=False` é obrigatório: a conexão é usada em thread diferente da que a criou.

### 6.3 Geração de imagem — cliente próprio

`ChatGoogleGenerativeAI` é chat e não devolve imagem utilizável. O adaptador `ImageModel` usa o
`google-genai` direto, dentro da Factory:

```python
from google import genai
from google.genai import types

class GeminiImageModel:
    def __init__(self, settings):
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.image_model

    def generate(self, prompt: str, *, width: int, height: int, seed=None) -> bytes:
        resposta = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        for parte in resposta.candidates[0].content.parts:
            if parte.inline_data:
                return parte.inline_data.data
        raise RuntimeError("resposta sem imagem")
```

Traduzir HTTP 429 do provedor para `RateLimitedError` (v2 §4.2), respeitando `Retry-After` como
piso do próximo delay.

### 6.4 Ordem de execução

A da v2 §9, com regressão da suíte entre cada etapa. Fases 0 e 2 deste documento já cobrem os
passos 2, 3 e 5 dela.

---

## 7. Fases e ordem

| Fase | Escopo | Depende de |
|---|---|---|
| **0** | `config.Settings`, dependências, fontes em `assets/` | — |
| **1** | `SPEC-formulario-canais.md`, mais a correção 1:1 → 4:5 (D1) | — |
| **2** | `backend/carousel_render/` + vocabulário dos agentes | 0 |
| **3** | Os 11 nós, Factory, resiliência, jobs, UI | 0, 2 |

Fases 0 e 1 são independentes entre si e podem ser feitas em paralelo. A Fase 2 precisa vir antes
da 3: o compositor tipográfico é o caminho de degradação obrigatório e precisa existir **antes**
de a geração de imagem poder falhar com elegância.

---

## 8. Checklist final

- [ ] `pytest tests/ -q` passa — nenhum teste existente quebrado
- [ ] `python3 -c "import app"` sem erro
- [ ] Fontes carregam de `assets/fonts/` sem glifo ausente para pt-BR
- [ ] Nenhum uso de bold sintético na serifada (D6)
- [ ] `grep -rn "1:1" data/prompts.py` não retorna nada — proporção é 4:5 (D1)
- [ ] `grep -rn "google-generativeai" requirements.txt` não retorna nada
- [ ] `backend/carousel_*` não importa `backend/graph.py` (e vice-versa)
- [ ] `grep -rn "os.environ" backend/carousel_*` não retorna nada
- [ ] Nenhuma chamada `st.` dentro do worker de background
- [ ] Um fluxo completo em modo mock: slides individuais, manifest reproduzindo as decisões, copy
      crítica intacta, e um caso propositalmente inválido encaminhado para `human_review`
- [ ] README registra as hipóteses assumidas — no mínimo D5, D6 e D10
