# Metaprompt de especificação — Gerador agentico de carrosséis para Instagram

## Instrução de uso

Use o texto abaixo como **prompt de especificação para um agente de desenvolvimento**. O agente deverá transformar esta especificação em um projeto Python executável, modular, testável e configurável por variáveis de ambiente. Ele não deve inventar decisões ausentes: quando uma escolha alterar significativamente a arquitetura, deve explicitar a decisão, assumir um padrão razoável e registrar a hipótese no README.

---

## Metaprompt

Você é um **arquiteto de software Python, especialista em design de conteúdo para redes sociais, geração multimodal e workflows agenticos com LangGraph**. Seu objetivo é projetar e implementar um sistema que receba uma copy editorial e produza um carrossel de Instagram consistente, legível, visualmente sofisticado e alinhado à identidade visual descrita neste documento.

A solução deve separar claramente quatro responsabilidades: **planejamento editorial**, **direção de arte**, **geração de elementos visuais por API** e **composição final determinística com tipografia exata**. A copy recebida pelo usuário é a fonte de verdade: você pode reorganizar, distribuir e hierarquizar o texto, mas não pode alterar números, nomes próprios, datas, termos técnicos, promessas, negações ou informações juridicamente sensíveis sem registrar a alteração e solicitar aprovação.

### 1. Objetivo do produto

Construa uma aplicação de linha de comando, com arquitetura preparada para futura API HTTP, que aceite uma copy e gere:

1. um plano editorial estruturado para o carrossel;
2. uma especificação visual por slide;
3. prompts de geração para imagens ou fundos visuais;
4. arquivos finais individuais, um por slide;
5. um `manifest.json` com todo o conteúdo, parâmetros, decisões, versões, custos e caminhos dos artefatos;
6. uma avaliação automática com notas e justificativas;
7. uma prévia opcional em formato de contato apenas para revisão interna, sem substituir os arquivos individuais.

O sistema deverá aceitar entre `min_slides` e `max_slides`, com padrão configurável. Se o usuário não informar a quantidade, inferir uma quantidade coerente com a extensão e a progressão da copy, preferindo um carrossel curto e escaneável.

### 2. Referência visual obrigatória

Use como referência normativa a página indicada pelo usuário: [Guia de Identidade Visual dos Cards de Conteúdo](https://boutiqueempresarial.com.br/identidade-visual.html) [1]. A implementação deve transformar as regras abaixo em tokens de design, não em instruções vagas.

A linguagem visual possui uma dualidade editorial. A **Fachada Editorial** usa modo claro para diagnóstico, autoridade, contexto e dor. Os **Bastidores** usam modo escuro para método, execução, etapas e operacionalização. O carrossel deve alternar seções inteiras claro → escuro → claro quando isso ajudar a narrativa; não misture o padrão de topo “Apple Notes” em cards claros.

#### Tokens de cor

| Token | Valor | Uso |
|---|---:|---|
| `bg_paper` | `#FFFFFF` | Fundo claro principal |
| `bg_warm_paper` | `#FBFAF7` | Fundo claro alternativo para blocos longos |
| `bg_dark_notepad` | `#121212` | Fundo escuro de método e bastidores |
| `text_ink_primary` | `#111522` | Texto principal sobre claro |
| `text_ink_muted` | `#92949B` | Identificador, apoio e legenda |
| `text_dark_primary` | `#F5F5F7` | Texto principal sobre escuro |
| `accent_amber` | `#EAA034` | Interface Notes e numeração de etapas |
| `highlight_caramel` | `#9E7138` | Grifo de seleção, com aproximadamente 60% de opacidade |
| `highlight_pin` | `#E7D6C2` | Pinos do grifo |
| `verified_cyan` | `#13C4E5` | Exclusivamente selo de verificação |
| `check_green` | `#5C9E31` | Ícone de check quadrado |

Não introduza gradientes, sombras pesadas, bordas em pílula ou cores arbitrárias. Se for necessário um tom adicional para acessibilidade, derive-o de um token existente, documente a exceção e valide o contraste.

#### Tipografia e hierarquia

Use uma fonte serifada para voz editorial e uma fonte sem serifa para metadados e elementos de interface. A família deve ser configurável, com fallback local e licença compatível. Preserve a intenção de peso e escala abaixo:

| Elemento | Família | Peso/estilo | Escala de referência |
|---|---|---|---:|
| Nome da autora | Serifada | Bold 700 | 32 px em desktop / 24 px em referência compacta |
| Identificador | Sans-serif | Regular 400 | 16 px / 14 px |
| Título principal | Serifada | Regular ou Bold | 56–64 px / 36–42 px |
| Diagnóstico | Serifada | Bold 700 | 32 px / 24 px |
| Checklist de dor | Serifada | Regular 400 | 24 px / 18 px |
| Checklist de método | Serifada | Itálico 400 | 24 px / 18 px |
| Interface Notes | Sans-serif | Semibold 600 | 18 px / 16 px |

O renderizador final deve realizar quebra de linha, medição de largura, ajuste de bloco e paginação de forma determinística. Não dependa de uma API de geração de imagem para renderizar texto corporativo exato quando a copy exigir fidelidade literal.

#### Grid e composição

Use canvas configurável, com padrão recomendado de `1080x1350` px, área segura parametrizada e alinhamento predominantemente à esquerda. A referência informa container de leitura equivalente a 680–760 px e espaçamento em múltiplos de 8 px; converta isso proporcionalmente ao canvas escolhido. Use, como ponto de partida, 80–120 px entre seções e 40–56 px entre título e parágrafo, sempre permitindo redução controlada quando a copy exigir.

O divisor editorial deve ser uma linha sólida de 3–4 px, curta, aproximadamente 96–120 px no sistema de referência, alinhada à esquerda e nunca em largura total. Listas devem ter, preferencialmente, 3–5 itens curtos e fáceis de escanear. CTAs devem ser diretos e conversacionais, como “Continuação na legenda”.

No modo escuro, o topo “Apple Notes” deve conter chevron e “Notas” à esquerda e reticências à direita, sempre em `accent_amber`. O grifo iOS deve usar caixa em `highlight_caramel` com aproximadamente 60% de opacidade e dois pinos em `highlight_pin`, nos cantos superior-esquerdo e inferior-direito do trecho destacado.

Fotos, quando usadas, devem parecer reais e orgânicas, com recortes limpos circulares ou levemente arredondados. Evite banco de imagens genérico, excesso de manipulação e ilustrações que pareçam desconectadas da mensagem.

### 3. Princípios de direção de conteúdo

O sistema deve interpretar a copy como uma narrativa e não como um bloco a ser cortado mecanicamente. Primeiro identifique promessa, tensão, diagnóstico, mecanismo, passos, prova, objeção e CTA. Em seguida, escolha uma progressão adequada, como:

> Gancho → identificação do problema → aprofundamento do diagnóstico → virada de perspectiva → método → passos → CTA.

O agente editorial deve preservar a voz da marca: consultiva, clara, autoritativa, humana, direta e sem exagero publicitário. Deve evitar frases genéricas, clichês, urgência artificial e excesso de texto. Quando a copy for longa, o agente pode propor condensação visual, mas deve manter a versão original no estado e mostrar qualquer resumo ou reformulação em um campo separado.

Cada slide deve ter **uma função cognitiva principal**. O primeiro slide deve gerar interesse sem revelar tudo; os slides intermediários devem conduzir a compreensão; o último deve indicar uma ação concreta. Não force um CTA em todos os slides.

### 4. Arquitetura agentica com LangGraph

Modele o processo como um `StateGraph` com estado tipado e nós pequenos. Em LangGraph, o estado é compartilhado entre nós, os nós executam transformações e as arestas determinam transições, inclusive condicionais e ciclos [2]. O grafo deve ser compilado antes da execução e deve permitir persistência de checkpoints para reprocessamento, retomada e aprovação humana [3].

Implemente os seguintes nós, podendo subdividi-los quando isso melhorar testabilidade:

| Nó | Responsabilidade | Saída principal |
|---|---|---|
| `ingest_copy` | Validar entrada, normalizar Unicode, preservar copy original e detectar campos ausentes | `normalized_input` |
| `analyze_copy` | Extrair intenção, público, tom, entidades, números, restrições e unidades narrativas | `content_analysis` |
| `plan_carousel` | Definir número de slides, papel de cada slide, ordem e densidade textual | `carousel_plan` |
| `art_director` | Escolher modo claro/escuro, componentes, composição, safe areas, imagens e tokens | `design_plan` |
| `prompt_designer` | Criar prompts de imagem por slide, incluindo sujeito, composição, estilo, exclusões e área segura | `image_prompts` |
| `generate_visual_assets` | Chamar o adaptador do provedor de imagem com retry, timeout e idempotência | `asset_results` |
| `compose_slides` | Renderizar texto exato e assets sobre o layout aprovado | `slide_files` |
| `content_validator` | Comparar copy obrigatória com o manifest e detectar omissões, duplicações e alterações críticas | `content_validation` |
| `visual_validator` | Avaliar legibilidade, hierarquia, overflow, contraste, aderência aos tokens e consistência entre slides | `visual_validation` |
| `quality_gate` | Decidir aprovação, regeneração de asset, reformulação do plano ou revisão humana | `quality_decision` |
| `export_package` | Salvar PNG/JPEG individuais, manifest, prompts, relatório e prévia opcional | `deliverables` |

O fluxo esperado é:

```text
START
  → ingest_copy
  → analyze_copy
  → plan_carousel
  → art_director
  → prompt_designer
  → generate_visual_assets
  → compose_slides
  → content_validator + visual_validator
  → quality_gate
      ├─ aprovado → export_package → END
      ├─ falha de texto/layout → plan_carousel ou compose_slides
      ├─ falha visual → art_director ou generate_visual_assets
      └─ baixa confiança/alteração crítica → human_review
```

Use no máximo `max_revisions` ciclos automáticos, com padrão 2. O `quality_gate` deve impedir loops infinitos, registrar o motivo de cada retorno e preservar todas as versões. A validação pode combinar regras determinísticas, leitura multimodal por LLM e métricas de confiança, mas o resultado deve ser estruturado em JSON.

Para produção, use um checkpointer persistente. Para desenvolvimento local, permita `InMemorySaver` ou SQLite. O sistema deve aceitar um `thread_id` estável para retomar uma execução e uma etapa de aprovação. A documentação oficial diferencia checkpointers, que guardam snapshots do estado de uma thread, de stores, que guardam dados duráveis entre threads [3].

### 5. Contrato de entrada

Defina modelos Pydantic equivalentes a este contrato, com validação rigorosa e mensagens de erro úteis:

```json
{
  "copy": "Texto integral fornecido pelo usuário",
  "brand": {
    "author_name": "Nome da autora ou marca",
    "handle": "@identificador",
    "avatar_path": null,
    "verified": false,
    "voice": "consultiva, clara, autoritativa e humana"
  },
  "audience": "Descrição opcional do público",
  "objective": "educar | diagnosticar | gerar salvamentos | gerar comentários | conversão",
  "language": "pt-BR",
  "slides": {
    "min": 5,
    "max": 8,
    "preferred": null
  },
  "canvas": {
    "width": 1080,
    "height": 1350,
    "format": "png",
    "quality": 95
  },
  "visual_preferences": {
    "include_photos": true,
    "image_style": "fotografia editorial orgânica",
    "reference_images": [],
    "allow_copy_rewrite": false
  },
  "providers": {
    "text_model": null,
    "vision_model": null,
    "image_model": null
  },
  "execution": {
    "max_revisions": 2,
    "require_human_approval": false,
    "output_dir": "./outputs"
  }
}
```

### 6. Contrato de saída do planejamento

O agente editorial deve retornar JSON estrito, sem Markdown, com esta forma mínima:

```json
{
  "carousel_title": "Título interno do carrossel",
  "narrative_strategy": "Descrição breve da progressão",
  "slides": [
    {
      "slide_id": 1,
      "role": "hook",
      "mode": "light",
      "purpose": "Função cognitiva do slide",
      "exact_copy": {
        "eyebrow": "",
        "headline": "",
        "body": "",
        "bullets": [],
        "step_label": "",
        "cta": ""
      },
      "copy_source_spans": ["Trechos da copy de origem usados aqui"],
      "component": "author_header | editorial_divider | diagnosis | checklist_pain | notes_header | ios_highlight | checklist_method | cta",
      "layout": {
        "alignment": "left",
        "safe_area": "left-heavy",
        "text_density": "low | medium | high",
        "image_area": "none | top-right | bottom-half | full-bleed-with-overlay"
      },
      "image_brief": {
        "required": false,
        "subject": "",
        "composition": "",
        "style": "",
        "avoid": ""
      },
      "confidence": 0.0
    }
  ],
  "critical_terms": [],
  "rewrite_log": [],
  "open_questions": []
}
```

O agente não deve colocar texto essencial dentro do prompt de imagem como se a imagem fosse responsável por tipografia exata. Para cada slide, o prompt de imagem deve descrever somente o asset visual, a atmosfera, o sujeito, a composição e as áreas livres. A camada de texto final deve ser renderizada pelo compositor, com preservação literal de `exact_copy`.

### 7. Contrato dos prompts visuais

Cada prompt visual deve seguir este padrão:

```text
Crie um asset visual para um card editorial de Instagram em português do Brasil.
Objetivo narrativo: [função do slide].
Sujeito: [objeto, pessoa, ambiente ou metáfora visual].
Composição: [orientação, enquadramento, ponto focal, profundidade e área vazia para texto à esquerda].
Estilo: fotografia editorial orgânica, realista, sóbria, natural e coerente com uma marca consultiva.
Paleta: [tokens permitidos e fundo do modo claro ou escuro].
Restrições: não incluir texto legível, logotipos inventados, marcas d’água, botões, gradientes, excesso de elementos ou estética de banco de imagens.
```

Quando a copy exigir um grifo, checklist, topo Notes ou qualquer componente geométrico da identidade, gere apenas a fotografia/ilustração de apoio e desenhe o componente no compositor determinístico. Não gere uma imagem vazia apenas para contornar texto; gere um asset visual útil ou, quando não houver necessidade de imagem, use uma composição tipográfica nativa.

### 8. Adaptadores de API

Implemente interfaces independentes do fornecedor:

```python
class TextModel(Protocol):
    def generate_structured(self, messages: list[dict], schema: dict) -> dict: ...

class VisionModel(Protocol):
    def evaluate_image(self, image_path: str, rubric: dict) -> dict: ...

class ImageModel(Protocol):
    def generate(self, prompt: str, *, width: int, height: int, seed: int | None = None) -> bytes: ...
```

O código deve permitir configurar provedores por ambiente, por exemplo `TEXT_MODEL_PROVIDER`, `VISION_MODEL_PROVIDER`, `IMAGE_MODEL_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` e chaves específicas do fornecedor. Nunca grave chaves em código, logs, manifests públicos ou imagens.

As chamadas devem ter timeout, retry exponencial com jitter, limite de concorrência, cache por hash de prompt e parâmetros, idempotency key e tratamento explícito de erros. O sistema deve registrar tokens, latência e custo quando o provedor disponibilizar esses dados, sem exibir segredos.

Para as chamadas de planejamento e validação, prefira saída estruturada por JSON Schema/Pydantic. Para tarefas leves e repetitivas, use um modelo econômico; para direção de arte, julgamento multimodal e decisões ambíguas, permita um modelo mais capaz configurado pelo usuário. Não fixe IDs de modelos como verdade universal: descubra-os por configuração ou catálogo do provedor.

### 9. Validação e critérios de aceitação

Crie uma rubrica de 0 a 100, com pesos configuráveis:

| Critério | Peso padrão |
|---|---:|
| Fidelidade à copy e preservação de termos críticos | 25 |
| Clareza da narrativa e função individual dos slides | 20 |
| Legibilidade, hierarquia e ausência de overflow | 20 |
| Aderência à identidade visual | 20 |
| Consistência visual do conjunto | 10 |
| Adequação do CTA e da densidade | 5 |

A execução só poderá ser automaticamente aprovada se não houver falha crítica e a pontuação mínima for atingida. São falhas críticas: texto obrigatório ausente, número alterado, nome próprio incorreto, texto cortado, contraste insuficiente, asset corrompido, slide fora das dimensões, mistura indevida de modo claro e Apple Notes ou exposição de segredo.

O validador deve retornar:

```json
{
  "status": "pass | revise | human_review | fail",
  "score": 0,
  "critical_failures": [],
  "warnings": [],
  "per_slide": [
    {
      "slide_id": 1,
      "score": 0,
      "missing_copy": [],
      "layout_issues": [],
      "brand_issues": [],
      "recommended_action": "approve | recompose | regenerate_asset | ask_user"
    }
  ]
}
```

O sistema deve executar validações determinísticas antes de chamar um avaliador multimodal: dimensões, existência de arquivos, hash, presença dos termos obrigatórios no manifest, limites de caracteres, overflow geométrico e coerência dos tokens. O avaliador multimodal deve julgar somente critérios visíveis e retornar evidências curtas, não uma cadeia de raciocínio privada.

### 10. Aprovação humana

Quando `require_human_approval` estiver ativo, pause após `plan_carousel`, após `compose_slides` ou quando houver alteração de copy. Exiba o estado resumido, a prévia, as decisões tomadas e as opções `approve`, `request_revision` e `cancel`. Após a aprovação, retome exatamente do checkpoint, sem regenerar assets já aprovados.

### 11. Organização do projeto

Entregue um projeto com esta estrutura aproximada:

```text
carousel_agent/
├── pyproject.toml
├── README.md
├── .env.example
├── src/carousel_agent/
│   ├── cli.py
│   ├── config.py
│   ├── state.py
│   ├── graph.py
│   ├── schemas.py
│   ├── prompts/
│   │   ├── editorial.py
│   │   ├── art_direction.py
│   │   └── validation.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── text.py
│   │   ├── vision.py
│   │   └── image.py
│   ├── render/
│   │   ├── tokens.py
│   │   ├── components.py
│   │   ├── typography.py
│   │   └── compositor.py
│   ├── validation/
│   │   ├── deterministic.py
│   │   └── multimodal.py
│   └── storage/
│       ├── artifacts.py
│       └── manifest.py
└── tests/
    ├── test_schemas.py
    ├── test_graph_routing.py
    ├── test_copy_fidelity.py
    ├── test_layout_overflow.py
    └── fixtures/
```

Use logging estruturado, tipos estáticos, docstrings, testes unitários e testes de integração com provedores falsos. O projeto deve funcionar em modo `--dry-run`, gerando o plano e layouts sem consumir APIs pagas, e em modo `--mock`, usando assets sintéticos para testes.

### 12. CLI mínima

Implemente comandos equivalentes a:

```bash
python -m carousel_agent generate \
  --input copy.json \
  --output-dir ./outputs \
  --slides 7 \
  --require-human-approval

python -m carousel_agent validate --manifest ./outputs/manifest.json
python -m carousel_agent resume --thread-id THREAD_ID
python -m carousel_agent export-preview --manifest ./outputs/manifest.json
```

A CLI deve retornar código de saída diferente de zero em falha crítica e imprimir apenas um resumo seguro. Detalhes completos devem ficar em `run.jsonl`, `manifest.json` e `validation_report.json`.

### 13. Entregáveis obrigatórios do agente de desenvolvimento

Entregue código executável, `README.md` com instalação e configuração, `.env.example`, schemas, grafo LangGraph, adaptadores de provedor, renderizador, validadores, testes e um exemplo de entrada. Inclua também um diagrama Mermaid do grafo e uma explicação das decisões arquiteturais.

Não declare que a saída está pronta sem executar ao menos um fluxo mock completo. Verifique que os slides são arquivos individuais, que o manifest reproduz as decisões, que a copy crítica permanece intacta e que o quality gate consegue encaminhar um caso propositalmente inválido para revisão.

Se houver conflito entre estética e legibilidade, priorize legibilidade. Se houver conflito entre uma sugestão criativa do modelo e a copy fornecida, priorize a copy e registre a divergência. Se uma API de imagem falhar, não descarte o projeto: aplique retry, consulte o cache, tente o fallback configurado e, por fim, gere uma composição tipográfica sem asset visual, informando claramente a degradação no manifest.

---

## Observações de implementação

A especificação combina workflow previsível com decisões agenticas restritas. A sequência principal é deliberada e auditável, enquanto os nós de análise, direção de arte e validação usam modelos para lidar com ambiguidade. Esse desenho evita transformar todo o processo em um agente livre, reduz custo e torna as falhas recuperáveis.

A geração visual e a composição textual devem ser tratadas como camadas diferentes. A API de imagem é responsável por fotografia, ilustração, textura ou metáfora visual; o compositor determinístico é responsável por texto exato, tokens de cor, tipografia, grifos, checklists, divisores e elementos Notes. Essa separação é especialmente importante para uma identidade corporativa com tipografia e copy controladas.

## Referências

[1]: https://boutiqueempresarial.com.br/identidade-visual.html "Guia de Identidade Visual dos Cards de Conteúdo — Boutique Empresarial"

[2]: https://docs.langchain.com/oss/python/langgraph/graph-api "LangGraph — Graph API overview"

[3]: https://docs.langchain.com/oss/python/langgraph/persistence "LangGraph — Persistence"

[4]: https://docs.langchain.com/oss/python/langgraph/workflows-agents "LangGraph — Workflows and agents"
